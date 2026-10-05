"""
Pipeline Runner (Extract → Validate → Process → Load)
Orchestrates ingestion, schema validation, deduplication, and warehouse loading in an idempotent run.
"""

import sys
import logging
import argparse
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("pipeline.runner")

from src.ingestion.adzuna_client import extract_postings_from_adzuna
from src.validation.validator import validate_raw_postings
from src.processing.processor import deduplicate_and_process_records
from src.ingestion.loader import (
    start_pipeline_run,
    complete_pipeline_run,
    get_existing_source_ids,
    load_postings_to_db
)
from src.utils.db_connector import initialize_schema


def run_pipeline(
    query: str = "data engineer",
    country: str = "gb",
    page: int = 1,
    results_per_page: int = 20,
    init_schema: bool = False
):
    """
    Full end-to-end pipeline run:
      Stage 1: Extract from Adzuna API
      Stage 2: Validate and quarantine bad records
      Stage 3: Deduplicate and extract skills
      Stage 4: Load into staging.raw_postings with audit trail
    """

    # ── Optional: Bootstrap the database schema on first run ──────────────────
    if init_schema:
        logger.info("Initializing database schema...")
        initialize_schema()

    # ── Stage 1: Extract ──────────────────────────────────────────────────────
    logger.info("--- STAGE 1: Extraction ---")
    run_id = start_pipeline_run(query_term=query, country_code=country, page_number=page)

    try:
        raw_file = extract_postings_from_adzuna(
            query=query,
            country=country,
            page=page,
            results_per_page=results_per_page
        )

        # ── Stage 2: Validate ─────────────────────────────────────────────────
        logger.info("--- STAGE 2: Validation ---")
        validation_report = validate_raw_postings(raw_file)

        records_fetched  = validation_report["total_records"]
        records_passed   = validation_report["passed_records"]
        records_failed   = validation_report["failed_records"]
        valid_records    = validation_report["valid_records"]

        # ── Stage 3: Process (Dedup + Skills) ─────────────────────────────────
        logger.info("--- STAGE 3: Processing & Deduplication ---")
        existing_ids = get_existing_source_ids()
        processed_records, records_duped = deduplicate_and_process_records(
            valid_records,
            existing_source_ids=existing_ids
        )

        # ── Stage 4: Load ─────────────────────────────────────────────────────
        logger.info("--- STAGE 4: Loading to staging.raw_postings ---")
        records_loaded = load_postings_to_db(processed_records, pull_batch_id=run_id)

        # Finalize audit record
        complete_pipeline_run(
            run_id=run_id,
            records_fetched=records_fetched,
            records_passed=records_passed,
            records_failed=records_failed,
            records_duped=records_duped,
            records_loaded=records_loaded,
            status="SUCCESS"
        )

        print("\n" + "="*55)
        print("  PIPELINE RUN COMPLETE")
        print("="*55)
        print(f"  Run ID        : {run_id}")
        print(f"  Query         : '{query}' ({country.upper()}, page {page})")
        print(f"  Fetched       : {records_fetched}")
        print(f"  Validation    : {records_passed} passed / {records_failed} failed")
        print(f"  Deduped       : {records_duped} skipped")
        print(f"  Loaded to DB  : {records_loaded} new rows")
        print("="*55 + "\n")

    except Exception as exc:
        logger.error("Pipeline run FAILED: %s", exc, exc_info=True)
        complete_pipeline_run(
            run_id=run_id,
            records_fetched=0,
            records_passed=0,
            records_failed=0,
            records_duped=0,
            records_loaded=0,
            status="FAILED",
            error_message=str(exc)
        )
        raise


def main():
    parser = argparse.ArgumentParser(description="Run the full Skills Demand Intelligence Pipeline.")
    parser.add_argument("--query",   type=str, default="data engineer", help="Search term")
    parser.add_argument("--country", type=str, default="gb",            help="Country code")
    parser.add_argument("--page",    type=int, default=1,               help="Page number")
    parser.add_argument("--results", type=int, default=20,              help="Results per page")
    parser.add_argument(
        "--init-schema",
        action="store_true",
        help="Create DB and apply DDL before running (first-time setup only)"
    )
    args = parser.parse_args()

    run_pipeline(
        query=args.query,
        country=args.country,
        page=args.page,
        results_per_page=args.results,
        init_schema=args.init_schema
    )


if __name__ == "__main__":
    main()
