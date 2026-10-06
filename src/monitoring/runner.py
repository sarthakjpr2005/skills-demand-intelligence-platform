"""
Quality & Observability Audit Runner
─────────────────────────────────────
Entry point to run all automated quality assertions, log results into
the monitoring schema, dispatch operational alerts, and report warehouse health.
"""

import sys
import time
import logging
import argparse
from typing import Optional

from src.monitoring.quality_checks import run_all_quality_checks
from src.monitoring.metrics_collector import (
    persist_check_results,
    get_warehouse_table_counts,
    get_pipeline_health_summary,
    get_recent_anomalies,
)
from src.monitoring.alerter import (
    format_quality_digest,
    dispatch_alert,
)
from src.utils.db_connector import get_psycopg2_connection

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("monitoring.runner")


def get_latest_run_id() -> Optional[str]:
    """Retrieves the run_id of the most recent pipeline execution."""
    conn = get_psycopg2_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT run_id FROM staging.pipeline_runs ORDER BY started_at DESC LIMIT 1;")
        row = cur.fetchone()
        cur.close()
        return str(row[0]) if row else None
    except Exception as exc:
        logger.warning("Could not fetch latest run_id: %s", exc)
        return None
    finally:
        conn.close()


def run_quality_audit(run_id: Optional[str] = None, fail_on_warning: bool = False) -> int:
    """
    Executes the complete Data Quality & Observability Suite:
      1. Discovers or accepts run_id
      2. Runs all 6 quality check dimensions (freshness, volume, quarantine, zero-skills, completeness, integrity)
      3. Persists check assertions into monitoring.data_quality_checks
      4. Prints table counts & warehouse status
      5. Dispatches alerts across configured channels
      6. Returns exit code (0 = success, 1 = failure)
    """
    start_time = time.time()
    if not run_id:
        run_id = get_latest_run_id()

    logger.info("Executing Quality & Observability Audit for run_id=%s", run_id or "NONE")

    # 1. Run checks
    results = run_all_quality_checks(run_id=run_id)

    # 2. Persist results
    persist_check_results(results, run_id=run_id)

    elapsed = time.time() - start_time

    # 3. Format and dispatch alert
    alert_type, severity, message = format_quality_digest(results, run_id=run_id, duration_sec=elapsed)
    channels = dispatch_alert(
        alert_type=alert_type,
        severity=severity,
        message=message,
        check_results=results,
        run_id=run_id,
        title="Pipeline Observability Audit"
    )

    # 4. Display warehouse storage overview
    counts = get_warehouse_table_counts()
    print("  --- WAREHOUSE ROW COUNTS ---")
    for tbl, count in counts.items():
        print(f"    * {tbl:<28}: {count:>6} rows")
    print(f"  Dispatched Alert Channels : {', '.join(channels)}")
    print(f"  Audit Execution Time     : {elapsed:.2f}s\n")


    # Determine exit code
    has_failures = any(r.status == "FAIL" for r in results)
    has_warnings = any(r.status == "WARN" for r in results)

    if has_failures:
        logger.error("Quality Audit FAILED with critical assertions.")
        return 1
    if has_warnings and fail_on_warning:
        logger.warning("Quality Audit finished with WARNINGS (fail-on-warning is ON).")
        return 1

    logger.info("Quality Audit PASSED cleanly.")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Skills Demand Intelligence Platform — Data Quality & Observability Auditor"
    )
    parser.add_argument(
        "--run-id",
        type=str,
        default=None,
        help="Optional UUID of specific pipeline run to audit. Defaults to latest."
    )
    parser.add_argument(
        "--fail-on-warning",
        action="store_true",
        help="Exit with non-zero status if any check produces a WARNING."
    )
    parser.add_argument(
        "--health-summary",
        action="store_true",
        help="Print the historical health summary view and exit."
    )
    args = parser.parse_args()

    if args.health_summary:
        summary = get_pipeline_health_summary(limit=5)
        print("\n" + "=" * 75)
        print("  HISTORICAL PIPELINE HEALTH SUMMARY (monitoring.v_pipeline_health)")
        print("=" * 75)
        for s in summary:
            print(
                f"  Run: {str(s['run_id'])[:8]}... | Status: {s['status']:<7} | "
                f"Fetched: {s['records_fetched']:>3} | Loaded: {s['records_loaded']:>3} | "
                f"Checks: {s['checks_passed'] or 0}P/{s['checks_warned'] or 0}W/{s['checks_failed'] or 0}F"
            )
        print("=" * 75 + "\n")
        return

    exit_code = run_quality_audit(run_id=args.run_id, fail_on_warning=args.fail_on_warning)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
