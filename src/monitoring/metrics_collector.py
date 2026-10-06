"""
Metrics Collector & Observability Persistence
─────────────────────────────────────────────
Persists quality check execution results to PostgreSQL and extracts
operational health metrics, table row counts, and error summaries.
"""

import logging
from typing import List, Optional, Dict, Any
from psycopg2.extras import execute_values

from src.monitoring.quality_checks import CheckResult
from src.utils.db_connector import get_psycopg2_connection

logger = logging.getLogger("monitoring.metrics_collector")


def persist_check_results(results: List[CheckResult], run_id: Optional[str] = None) -> int:
    """
    Inserts a list of CheckResult instances into monitoring.data_quality_checks.
    Returns the number of check results persisted.
    """
    if not results:
        return 0

    sql = """
        INSERT INTO monitoring.data_quality_checks (
            run_id,
            check_name,
            check_category,
            table_name,
            column_name,
            status,
            observed_value,
            threshold_value,
            details
        ) VALUES %s;
    """

    records = [r.to_tuple(run_id=run_id) for r in results]
    conn = get_psycopg2_connection()
    try:
        cur = conn.cursor()
        execute_values(cur, sql, records)
        conn.commit()
        cur.close()
        logger.info("Persisted %d quality check results to monitoring.data_quality_checks", len(records))
    except Exception as exc:
        conn.rollback()
        logger.error("Failed to persist quality check results: %s", exc, exc_info=True)
        raise
    finally:
        conn.close()

    return len(records)


def get_pipeline_health_summary(limit: int = 5) -> List[Dict[str, Any]]:
    """Retrieves the most recent runs and their health metrics from monitoring.v_pipeline_health."""
    sql = """
        SELECT
            run_id,
            started_at,
            completed_at,
            duration_seconds,
            status,
            records_fetched,
            records_passed,
            records_failed,
            records_duped,
            records_loaded,
            quarantine_failure_rate_pct,
            total_checks_run,
            checks_passed,
            checks_warned,
            checks_failed
        FROM monitoring.v_pipeline_health
        ORDER BY started_at DESC
        LIMIT %s;
    """
    conn = get_psycopg2_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql, (limit,))
        columns = [desc[0] for desc in cur.description]
        rows = cur.fetchall()
        cur.close()
        return [dict(zip(columns, row)) for row in rows]
    finally:
        conn.close()


def get_recent_anomalies(limit: int = 10) -> List[Dict[str, Any]]:
    """Retrieves recent warnings or failed checks from monitoring.v_recent_anomalies."""
    sql = """
        SELECT
            check_id,
            run_id,
            check_name,
            check_category,
            table_name,
            column_name,
            status,
            observed_value,
            threshold_value,
            details,
            executed_at
        FROM monitoring.v_recent_anomalies
        ORDER BY executed_at DESC
        LIMIT %s;
    """
    conn = get_psycopg2_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql, (limit,))
        columns = [desc[0] for desc in cur.description]
        rows = cur.fetchall()
        cur.close()
        return [dict(zip(columns, row)) for row in rows]
    finally:
        conn.close()


def get_warehouse_table_counts() -> Dict[str, int]:
    """Retrieves current row counts across all warehouse layers (staging + marts)."""
    tables = [
        "staging.pipeline_runs",
        "staging.raw_postings",
        "marts.dim_date",
        "marts.dim_company",
        "marts.dim_location",
        "marts.dim_skill",
        "marts.fct_postings",
        "marts.fct_posting_skills",
    ]
    counts = {}
    conn = get_psycopg2_connection()
    try:
        cur = conn.cursor()
        for tbl in tables:
            try:
                cur.execute(f"SELECT COUNT(*) FROM {tbl};")
                counts[tbl] = cur.fetchone()[0]
            except Exception:
                conn.rollback()
                counts[tbl] = -1
        cur.close()
    finally:
        conn.close()

    return counts
