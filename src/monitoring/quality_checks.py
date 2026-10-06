"""
Data Quality Assertions & Observability Engine
──────────────────────────────────────────────
Executes automated quality checks across staging and dbt mart tables:
  1. Freshness SLA: Verifies data recency against max elapsed hours.
  2. Volume Anomaly: Flags sudden ingestion drops compared to historical runs.
  3. Quarantine / Rejection Rate: Monitors % of bad records failed at validation.
  4. Zero-Skills Rate: Flags taxonomy/parsing drift if descriptions yield no skills.
  5. Column Completeness: Enforces null-rate thresholds on critical fields.
  6. Referential Integrity: Asserts 0 orphaned records between facts and dimensions.
"""

import logging
from dataclasses import dataclass
from typing import List, Optional, Tuple
from datetime import datetime

from config.settings import (
    FRESHNESS_MAX_HOURS,
    QUARANTINE_MAX_FAIL_RATE,
    ZERO_SKILLS_MAX_RATE,
    MIN_BATCH_VOLUME,
)
from src.utils.db_connector import get_psycopg2_connection

logger = logging.getLogger("monitoring.quality_checks")


@dataclass
class CheckResult:
    name: str
    category: str         # FRESHNESS | VOLUME_ANOMALY | COMPLETENESS | QUARANTINE_RATE | INTEGRITY
    table_name: str
    column_name: Optional[str]
    status: str           # PASS | WARN | FAIL
    observed_value: Optional[float]
    threshold_value: Optional[float]
    details: str

    def to_tuple(self, run_id: Optional[str] = None) -> Tuple:
        return (
            run_id,
            self.name,
            self.category,
            self.table_name,
            self.column_name,
            self.status,
            self.observed_value,
            self.threshold_value,
            self.details,
        )


def check_staging_freshness(max_hours: float = FRESHNESS_MAX_HOURS) -> CheckResult:
    """Checks the time elapsed since the latest record landed in staging.raw_postings."""
    sql = """
        SELECT
            MAX(loaded_at) AS last_loaded,
            EXTRACT(EPOCH FROM (now() - MAX(loaded_at))) / 3600.0 AS hours_since_load
        FROM staging.raw_postings;
    """
    conn = get_psycopg2_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql)
        row = cur.fetchone()
        cur.close()
    finally:
        conn.close()

    if not row or row[0] is None:
        return CheckResult(
            name="freshness_staging_raw_postings",
            category="FRESHNESS",
            table_name="staging.raw_postings",
            column_name="loaded_at",
            status="FAIL",
            observed_value=None,
            threshold_value=max_hours,
            details="staging.raw_postings contains 0 records. SLA breached."
        )

    hours = float(row[1]) if row[1] is not None else 999.0
    status = "PASS" if hours <= max_hours else ("WARN" if hours <= max_hours * 1.5 else "FAIL")
    return CheckResult(
        name="freshness_staging_raw_postings",
        category="FRESHNESS",
        table_name="staging.raw_postings",
        column_name="loaded_at",
        status=status,
        observed_value=round(hours, 2),
        threshold_value=max_hours,
        details=f"Last loaded {hours:.2f}h ago (SLA limit: {max_hours:.1f}h). Status: {status}."
    )


def check_marts_freshness(max_hours: float = FRESHNESS_MAX_HOURS) -> CheckResult:
    """Checks the time elapsed since the latest record was built in marts.fct_postings."""
    sql = """
        SELECT
            MAX(loaded_at) AS last_loaded,
            EXTRACT(EPOCH FROM (now() - MAX(loaded_at))) / 3600.0 AS hours_since_load
        FROM marts.fct_postings;
    """
    conn = get_psycopg2_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql)
        row = cur.fetchone()
        cur.close()
    except Exception as exc:
        conn.close()
        return CheckResult(
            name="freshness_marts_fct_postings",
            category="FRESHNESS",
            table_name="marts.fct_postings",
            column_name="loaded_at",
            status="FAIL",
            observed_value=None,
            threshold_value=max_hours,
            details=f"Could not query marts.fct_postings: {exc}"
        )
    finally:
        if not conn.closed:
            conn.close()

    if not row or row[0] is None:
        return CheckResult(
            name="freshness_marts_fct_postings",
            category="FRESHNESS",
            table_name="marts.fct_postings",
            column_name="loaded_at",
            status="FAIL",
            observed_value=None,
            threshold_value=max_hours,
            details="marts.fct_postings contains 0 records or has not been built."
        )

    hours = float(row[1]) if row[1] is not None else 999.0
    status = "PASS" if hours <= max_hours else ("WARN" if hours <= max_hours * 1.5 else "FAIL")
    return CheckResult(
        name="freshness_marts_fct_postings",
        category="FRESHNESS",
        table_name="marts.fct_postings",
        column_name="loaded_at",
        status=status,
        observed_value=round(hours, 2),
        threshold_value=max_hours,
        details=f"Last mart refresh {hours:.2f}h ago (SLA limit: {max_hours:.1f}h)."
    )


def check_quarantine_rate(run_id: Optional[str] = None, max_rate: float = QUARANTINE_MAX_FAIL_RATE) -> CheckResult:
    """Verifies that the validation rejection / quarantine rate stays below acceptable threshold."""
    conn = get_psycopg2_connection()
    try:
        cur = conn.cursor()
        if run_id:
            cur.execute("""
                SELECT records_fetched, records_passed, records_failed
                FROM staging.pipeline_runs
                WHERE run_id = %s;
            """, (run_id,))
        else:
            cur.execute("""
                SELECT records_fetched, records_passed, records_failed
                FROM staging.pipeline_runs
                ORDER BY started_at DESC
                LIMIT 1;
            """)
        row = cur.fetchone()
        cur.close()
    finally:
        conn.close()

    if not row:
        return CheckResult(
            name="quarantine_rejection_rate",
            category="QUARANTINE_RATE",
            table_name="staging.pipeline_runs",
            column_name="records_failed",
            status="WARN",
            observed_value=None,
            threshold_value=max_rate,
            details="No pipeline run audit records found."
        )

    fetched, passed, failed = row
    total_evaluated = (passed or 0) + (failed or 0)
    if total_evaluated == 0:
        return CheckResult(
            name="quarantine_rejection_rate",
            category="QUARANTINE_RATE",
            table_name="staging.pipeline_runs",
            column_name="records_failed",
            status="PASS",
            observed_value=0.0,
            threshold_value=max_rate,
            details="0 records evaluated in this run."
        )

    fail_rate = failed / total_evaluated
    pct = fail_rate * 100.0
    threshold_pct = max_rate * 100.0

    if fail_rate <= max_rate:
        status = "PASS"
    elif fail_rate <= max_rate * 2.0:
        status = "WARN"
    else:
        status = "FAIL"

    return CheckResult(
        name="quarantine_rejection_rate",
        category="QUARANTINE_RATE",
        table_name="staging.pipeline_runs",
        column_name="records_failed",
        status=status,
        observed_value=round(pct, 2),
        threshold_value=round(threshold_pct, 2),
        details=f"{failed}/{total_evaluated} records quarantined ({pct:.1f}% vs max allowed {threshold_pct:.1f}%)."
    )


def check_volume_anomaly(run_id: Optional[str] = None, min_volume: int = MIN_BATCH_VOLUME) -> CheckResult:
    """
    Checks for sudden drops or anomalies in ingested record volume
    compared against the moving average of previous successful runs.
    """
    conn = get_psycopg2_connection()
    try:
        cur = conn.cursor()
        # Fetch current run records
        if run_id:
            cur.execute("SELECT run_id, records_loaded FROM staging.pipeline_runs WHERE run_id = %s;", (run_id,))
        else:
            cur.execute("SELECT run_id, records_loaded FROM staging.pipeline_runs ORDER BY started_at DESC LIMIT 1;")
        current_row = cur.fetchone()

        if not current_row:
            cur.close()
            return CheckResult(
                name="volume_anomaly_detection",
                category="VOLUME_ANOMALY",
                table_name="staging.pipeline_runs",
                column_name="records_loaded",
                status="WARN",
                observed_value=None,
                threshold_value=float(min_volume),
                details="No pipeline runs recorded."
            )

        curr_id, curr_loaded = current_row
        curr_loaded = curr_loaded or 0

        # Fetch up to 10 previous runs for baseline
        cur.execute("""
            SELECT records_loaded
            FROM staging.pipeline_runs
            WHERE status = 'SUCCESS' AND run_id != %s
            ORDER BY started_at DESC
            LIMIT 10;
        """, (curr_id,))
        hist_rows = cur.fetchall()
        cur.close()
    finally:
        conn.close()

    hist_volumes = [r[0] for r in hist_rows if r[0] is not None]

    if not hist_volumes:
        # First or second run: just check min volume
        status = "PASS" if curr_loaded >= min_volume else "WARN"
        return CheckResult(
            name="volume_anomaly_detection",
            category="VOLUME_ANOMALY",
            table_name="staging.pipeline_runs",
            column_name="records_loaded",
            status=status,
            observed_value=float(curr_loaded),
            threshold_value=float(min_volume),
            details=f"Initial run baseline: {curr_loaded} records loaded (min threshold: {min_volume})."
        )

    avg_volume = sum(hist_volumes) / len(hist_volumes)
    # If loaded volume drops below 40% of baseline historical average
    lower_bound = max(avg_volume * 0.40, float(min_volume))

    if curr_loaded < lower_bound:
        status = "WARN" if curr_loaded > 0 else "FAIL"
        details = (
            f"Volume drop anomaly detected: {curr_loaded} records loaded vs "
            f"historical avg {avg_volume:.1f} (expected >= {lower_bound:.1f})."
        )
    else:
        status = "PASS"
        details = (
            f"Volume normal: {curr_loaded} records loaded "
            f"(historical avg: {avg_volume:.1f}, floor: {lower_bound:.1f})."
        )

    return CheckResult(
        name="volume_anomaly_detection",
        category="VOLUME_ANOMALY",
        table_name="staging.pipeline_runs",
        column_name="records_loaded",
        status=status,
        observed_value=float(curr_loaded),
        threshold_value=round(lower_bound, 1),
        details=details
    )


def check_zero_skills_rate(max_rate: float = ZERO_SKILLS_MAX_RATE) -> CheckResult:
    """Verifies that the percentage of postings with empty skills array does not exceed threshold."""
    sql = """
        SELECT
            COUNT(*) AS total_postings,
            COUNT(CASE WHEN cardinality(extracted_skills) = 0 OR extracted_skills IS NULL THEN 1 END) AS zero_skills_count
        FROM staging.raw_postings;
    """
    conn = get_psycopg2_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql)
        row = cur.fetchone()
        cur.close()
    finally:
        conn.close()

    total, zero_count = row if row else (0, 0)
    if total == 0:
        return CheckResult(
            name="zero_skills_extraction_rate",
            category="COMPLETENESS",
            table_name="staging.raw_postings",
            column_name="extracted_skills",
            status="WARN",
            observed_value=0.0,
            threshold_value=max_rate * 100.0,
            details="staging.raw_postings has 0 rows."
        )

    zero_pct = (zero_count / total) * 100.0
    thresh_pct = max_rate * 100.0

    if zero_pct <= thresh_pct:
        status = "PASS"
    elif zero_pct <= thresh_pct * 1.5:
        status = "WARN"
    else:
        status = "FAIL"

    return CheckResult(
        name="zero_skills_extraction_rate",
        category="COMPLETENESS",
        table_name="staging.raw_postings",
        column_name="extracted_skills",
        status=status,
        observed_value=round(zero_pct, 2),
        threshold_value=round(thresh_pct, 2),
        details=f"{zero_count}/{total} postings ({zero_pct:.1f}%) have 0 extracted skills (limit: {thresh_pct:.1f}%)."
    )


def check_column_completeness() -> List[CheckResult]:
    """Enforces non-null assertions on essential analytical fields in staging & marts."""
    checks = []
    conn = get_psycopg2_connection()
    try:
        cur = conn.cursor()

        # Check 1: staging.raw_postings title null rate (must be 0.0%)
        cur.execute("""
            SELECT COUNT(*), COUNT(CASE WHEN title IS NULL OR TRIM(title) = '' THEN 1 END)
            FROM staging.raw_postings;
        """)
        total, nulls = cur.fetchone()
        null_pct = (nulls / total * 100.0) if total > 0 else 0.0
        checks.append(CheckResult(
            name="completeness_staging_title",
            category="COMPLETENESS",
            table_name="staging.raw_postings",
            column_name="title",
            status="PASS" if nulls == 0 else "FAIL",
            observed_value=round(null_pct, 2),
            threshold_value=0.0,
            details=f"Found {nulls}/{total} null or empty titles ({null_pct:.2f}%)."
        ))

        # Check 2: staging.raw_postings company null rate (warn if > 15%)
        cur.execute("""
            SELECT COUNT(*), COUNT(CASE WHEN company IS NULL OR TRIM(company) = '' THEN 1 END)
            FROM staging.raw_postings;
        """)
        total, nulls = cur.fetchone()
        null_pct = (nulls / total * 100.0) if total > 0 else 0.0
        status = "PASS" if null_pct <= 15.0 else ("WARN" if null_pct <= 30.0 else "FAIL")
        checks.append(CheckResult(
            name="completeness_staging_company",
            category="COMPLETENESS",
            table_name="staging.raw_postings",
            column_name="company",
            status=status,
            observed_value=round(null_pct, 2),
            threshold_value=15.0,
            details=f"Found {nulls}/{total} null companies ({null_pct:.2f}% vs max 15.0%)."
        ))

        # Check 3: marts.fct_postings date_id null rate (must be 0.0%)
        cur.execute("""
            SELECT COUNT(*), COUNT(CASE WHEN date_id IS NULL THEN 1 END)
            FROM marts.fct_postings;
        """)
        total, nulls = cur.fetchone()
        null_pct = (nulls / total * 100.0) if total > 0 else 0.0
        checks.append(CheckResult(
            name="completeness_marts_date_id",
            category="COMPLETENESS",
            table_name="marts.fct_postings",
            column_name="date_id",
            status="PASS" if nulls == 0 else "FAIL",
            observed_value=round(null_pct, 2),
            threshold_value=0.0,
            details=f"Found {nulls}/{total} null date_id values in marts.fct_postings."
        ))

        cur.close()
    finally:
        conn.close()

    return checks


def check_referential_integrity() -> List[CheckResult]:
    """Asserts that all foreign keys between facts and dimensions resolve cleanly."""
    checks = []
    conn = get_psycopg2_connection()
    try:
        cur = conn.cursor()

        # Check 1: Orphan postings in fct_posting_skills
        cur.execute("""
            SELECT COUNT(*)
            FROM marts.fct_posting_skills s
            LEFT JOIN marts.fct_postings f ON s.posting_sk = f.posting_sk
            WHERE f.posting_sk IS NULL;
        """)
        orphans = cur.fetchone()[0]
        checks.append(CheckResult(
            name="integrity_bridge_orphan_postings",
            category="INTEGRITY",
            table_name="marts.fct_posting_skills",
            column_name="posting_sk",
            status="PASS" if orphans == 0 else "FAIL",
            observed_value=float(orphans),
            threshold_value=0.0,
            details=f"{orphans} orphan postings in fct_posting_skills not in fct_postings."
        ))

        # Check 2: Orphan skills in fct_posting_skills
        cur.execute("""
            SELECT COUNT(*)
            FROM marts.fct_posting_skills s
            LEFT JOIN marts.dim_skill k ON s.skill_sk = k.skill_sk
            WHERE k.skill_sk IS NULL;
        """)
        orphans = cur.fetchone()[0]
        checks.append(CheckResult(
            name="integrity_bridge_orphan_skills",
            category="INTEGRITY",
            table_name="marts.fct_posting_skills",
            column_name="skill_sk",
            status="PASS" if orphans == 0 else "FAIL",
            observed_value=float(orphans),
            threshold_value=0.0,
            details=f"{orphans} orphan skill keys in fct_posting_skills not in dim_skill."
        ))

        # Check 3: Orphan companies in fct_postings
        cur.execute("""
            SELECT COUNT(*)
            FROM marts.fct_postings f
            LEFT JOIN marts.dim_company c ON f.company_sk = c.company_sk
            WHERE c.company_sk IS NULL;
        """)
        orphans = cur.fetchone()[0]
        checks.append(CheckResult(
            name="integrity_fct_postings_dim_company",
            category="INTEGRITY",
            table_name="marts.fct_postings",
            column_name="company_sk",
            status="PASS" if orphans == 0 else "FAIL",
            observed_value=float(orphans),
            threshold_value=0.0,
            details=f"{orphans} orphan company keys in fct_postings not in dim_company."
        ))

        cur.close()
    finally:
        conn.close()

    return checks


def run_all_quality_checks(run_id: Optional[str] = None) -> List[CheckResult]:
    """Executes the complete data quality suite and aggregates results."""
    logger.info("Starting automated Data Quality & Observability Suite...")
    results: List[CheckResult] = []

    # 1. Freshness Checks
    results.append(check_staging_freshness())
    results.append(check_marts_freshness())

    # 2. Quarantine Rate
    results.append(check_quarantine_rate(run_id=run_id))

    # 3. Volume Anomaly
    results.append(check_volume_anomaly(run_id=run_id))

    # 4. Zero Skills Rate
    results.append(check_zero_skills_rate())

    # 5. Completeness
    results.extend(check_column_completeness())

    # 6. Referential Integrity
    results.extend(check_referential_integrity())

    passed = sum(1 for r in results if r.status == "PASS")
    warned = sum(1 for r in results if r.status == "WARN")
    failed = sum(1 for r in results if r.status == "FAIL")

    logger.info(
        "Data Quality Suite Complete: %d checks run (%d PASSED, %d WARN, %d FAILED)",
        len(results), passed, warned, failed
    )
    return results
