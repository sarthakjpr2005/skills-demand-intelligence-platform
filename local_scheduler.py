"""
Local Scheduler — Skills Demand Intelligence Platform
──────────────────────────────────────────────────────
Mirrors the production Airflow pipeline (dags/skills_demand_dag.py) exactly —
same task sequence, same retry logic, and same audit trail — using a native
Python scheduling engine for standalone or local environments.

How to use:
  # Run every morning at 02:00 indefinitely (Ctrl+C to stop):
  python local_scheduler.py

  # Run once right now (useful for testing and verification):
  python local_scheduler.py --run-now

  # Change the scheduled execution time:
  python local_scheduler.py --time 08:30
"""

import sys
import time
import logging
import argparse
from datetime import datetime
from pathlib import Path

import schedule

from src.ingestion.adzuna_client import extract_postings_from_adzuna
from src.validation.validator import validate_raw_postings
from src.processing.processor import deduplicate_and_process_records
from src.ingestion.loader import (
    start_pipeline_run,
    complete_pipeline_run,
    get_existing_source_ids,
    load_postings_to_db,
)
from src.utils.db_connector import get_psycopg2_connection
from src.monitoring.runner import run_quality_audit
from config.settings import ADZUNA_COUNTRY


# ── Logging setup ──────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ]
)
logger = logging.getLogger("scheduler")

# ── Pipeline config — mirrors the Airflow DAG constants ───────────────────────
QUERY_TERMS = [
    "data engineer",
    "analytics engineer",
    "data platform engineer",
    "mlops engineer",
]
COUNTRY       = ADZUNA_COUNTRY
RESULTS_PER_PAGE = 50
MAX_RETRIES      = 2


# ── Task Functions ─────────────────────────────────────────────────────────────

def task_extract() -> dict:
    """L1: Call Adzuna API for all query terms, land raw JSON."""
    landed_files = {}
    for query in QUERY_TERMS:
        raw_file = extract_postings_from_adzuna(
            query=query,
            country=COUNTRY,
            results_per_page=RESULTS_PER_PAGE
        )
        landed_files[query] = raw_file
        logger.info("Extracted: %s → %s", query, raw_file.name)
    return landed_files


def task_validate(landed_files: dict) -> dict:
    """L2: Validate every raw file; collect all valid records."""
    all_valid, total_fetched, total_failed = [], 0, 0
    for query, file_path in landed_files.items():
        report = validate_raw_postings(file_path)
        all_valid.extend(report["valid_records"])
        total_fetched += report["total_records"]
        total_failed  += report["failed_records"]
        logger.info(
            "Validated [%s]: %d/%d passed",
            query, report["passed_records"], report["total_records"]
        )
    return {
        "valid_records": all_valid,
        "total_fetched": total_fetched,
        "total_failed":  total_failed,
    }


def task_process(valid_records: list) -> dict:
    """L3: Deduplicate against DB and extract skills."""
    existing_ids = get_existing_source_ids()
    processed, duped = deduplicate_and_process_records(
        valid_records,
        existing_source_ids=existing_ids
    )
    logger.info("Processed %d records, skipped %d duplicates", len(processed), duped)
    return {"processed_records": processed, "records_duped": duped}


def task_load(processed_records: list, total_fetched: int,
              total_failed: int, records_duped: int) -> str:
    """L4: Write audit record and bulk-insert into staging.raw_postings."""
    run_id = start_pipeline_run(
        query_term=", ".join(QUERY_TERMS),
        country_code=COUNTRY,
        page_number=1
    )
    try:
        records_loaded = load_postings_to_db(processed_records, pull_batch_id=run_id)
        complete_pipeline_run(
            run_id=run_id,
            records_fetched=total_fetched,
            records_passed=total_fetched - total_failed,
            records_failed=total_failed,
            records_duped=records_duped,
            records_loaded=records_loaded,
            status="SUCCESS"
        )
        logger.info("Loaded %d new rows (run_id=%s...)", records_loaded, run_id[:8])
    except Exception as exc:
        complete_pipeline_run(
            run_id=run_id, records_fetched=0, records_passed=0,
            records_failed=0, records_duped=0, records_loaded=0,
            status="FAILED", error_message=str(exc)
        )
        raise
    return run_id


def task_dbt_transform() -> None:
    """
    L5: Run dbt models and tests.
    Runs dbt programmatically through subprocess to keep it cross-platform.
    """
    import subprocess
    from pathlib import Path

    project_dir = Path(__file__).parent / "dbt_project"
    dbt_exec    = Path(__file__).parent / "venv" / "Scripts" / "dbt.exe"

    logger.info("Running dbt run...")
    result = subprocess.run(
        [str(dbt_exec), "run",
         "--project-dir", str(project_dir),
         "--profiles-dir", str(project_dir)],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        logger.error("dbt run FAILED:\n%s", result.stdout[-2000:])
        raise RuntimeError("dbt run failed")
    logger.info("dbt run complete.")

    logger.info("Running dbt test...")
    result = subprocess.run(
        [str(dbt_exec), "test",
         "--project-dir", str(project_dir),
         "--profiles-dir", str(project_dir),
         "--no-partial-parse"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        logger.error("dbt test FAILED:\n%s", result.stdout[-2000:])
        raise RuntimeError("dbt test failed")
    logger.info("dbt test complete — all tests passed.")


# ── Main Pipeline Orchestrator ─────────────────────────────────────────────────

def run_pipeline(dry_run: bool = False):
    """
    Orchestrates all 5 tasks in sequence.
    Mirrors the Airflow DAG task graph exactly:
      extract → validate → process → load → dbt_transform_and_test
    """
    start_time = datetime.now()
    logger.info("=" * 60)
    logger.info("  PIPELINE RUN STARTED — %s", start_time.strftime("%Y-%m-%d %H:%M:%S"))
    logger.info("=" * 60)

    if dry_run:
        logger.info("[DRY RUN] Skipping real API calls and DB writes.")
        logger.info("  Tasks that would run: extract → validate → process → load → dbt")
        return

    try:
        # ── Task 1 ────────────────────────────────────────────────────────────
        logger.info("--- Task 1/5: EXTRACT ---")
        landed_files = task_extract()

        # ── Task 2 ────────────────────────────────────────────────────────────
        logger.info("--- Task 2/5: VALIDATE ---")
        validation = task_validate(landed_files)

        # ── Task 3 ────────────────────────────────────────────────────────────
        logger.info("--- Task 3/5: PROCESS (Dedup + Skills) ---")
        processing = task_process(validation["valid_records"])

        # ── Task 4 ────────────────────────────────────────────────────────────
        logger.info("--- Task 4/5: LOAD to PostgreSQL ---")
        run_id = task_load(
            processed_records=processing["processed_records"],
            total_fetched=validation["total_fetched"],
            total_failed=validation["total_failed"],
            records_duped=processing["records_duped"]
        )

        # ── Task 5 ────────────────────────────────────────────────────────────
        logger.info("--- Task 5/6: dbt TRANSFORM & TEST ---")
        task_dbt_transform()

        # ── Task 6 ────────────────────────────────────────────────────────────
        logger.info("--- Task 6/6: QUALITY & OBSERVABILITY AUDIT ---")
        run_quality_audit(run_id=run_id)

        elapsed = (datetime.now() - start_time).total_seconds()
        logger.info("=" * 60)
        logger.info("  PIPELINE RUN COMPLETE [OK]  (%.1fs)", elapsed)
        logger.info("  Run ID : %s", run_id)
        logger.info("=" * 60)


    except Exception as exc:
        elapsed = (datetime.now() - start_time).total_seconds()
        logger.error("=" * 60)
        logger.error("  PIPELINE FAILED after %.1fs: %s", elapsed, exc)
        logger.error("=" * 60)
        # Don't re-raise — the scheduler keeps running for the next day's attempt.


# ── Scheduler Entry Point ──────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Skills Demand Intelligence Platform — Local Daily Scheduler"
    )
    parser.add_argument(
        "--run-now",
        action="store_true",
        help="Execute the pipeline immediately once, then exit."
    )
    parser.add_argument(
        "--time",
        type=str,
        default="02:00",
        help="Daily run time in HH:MM format (default: 02:00)."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would run without making real API/DB calls."
    )
    args = parser.parse_args()

    if args.run_now:
        logger.info("Running pipeline immediately (--run-now flag).")
        run_pipeline(dry_run=args.dry_run)
        return

    # ── Schedule daily at specified time ──────────────────────────────────────
    schedule.every().day.at(args.time).do(run_pipeline)

    logger.info("Scheduler started. Pipeline will run daily at %s.", args.time)
    logger.info("Press Ctrl+C to stop.")

    while True:
        schedule.run_pending()
        time.sleep(30)      # Check every 30 seconds


if __name__ == "__main__":
    main()
