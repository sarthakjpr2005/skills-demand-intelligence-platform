"""
Batch Loader
Inserts processed, deduplicated job postings into staging.raw_postings.
Each run creates a pipeline_run audit record and links every inserted row to it.
"""

import uuid
import logging
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional

from psycopg2.extras import execute_values

from src.utils.db_connector import get_psycopg2_connection

logger = logging.getLogger("ingestion.loader")


def start_pipeline_run(
    query_term: str,
    country_code: str,
    page_number: int
) -> str:
    """
    Creates a new pipeline_run record and returns its run_id (UUID).
    This UUID is the pull_batch_id stamped on every raw_posting loaded in this run.
    """
    run_id = str(uuid.uuid4())
    conn = get_psycopg2_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO staging.pipeline_runs
                (run_id, query_term, country_code, page_number, status)
            VALUES (%s, %s, %s, %s, 'RUNNING')
            """,
            (run_id, query_term, country_code, page_number)
        )
        conn.commit()
        logger.info("Pipeline run started: run_id=%s", run_id)
    finally:
        conn.close()

    return run_id


def complete_pipeline_run(
    run_id: str,
    records_fetched: int,
    records_passed: int,
    records_failed: int,
    records_duped: int,
    records_loaded: int,
    status: str = "SUCCESS",
    error_message: Optional[str] = None
):
    """Updates the pipeline_run audit record with final statistics."""
    conn = get_psycopg2_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE staging.pipeline_runs SET
                completed_at    = now(),
                records_fetched = %s,
                records_passed  = %s,
                records_failed  = %s,
                records_duped   = %s,
                records_loaded  = %s,
                status          = %s,
                error_message   = %s
            WHERE run_id = %s
            """,
            (
                records_fetched, records_passed, records_failed,
                records_duped, records_loaded,
                status, error_message, run_id
            )
        )
        conn.commit()
        logger.info(
            "Pipeline run %s completed: status=%s, loaded=%d, duped=%d, failed=%d",
            run_id, status, records_loaded, records_duped, records_failed
        )
    finally:
        conn.close()


def get_existing_source_ids() -> set:
    """
    Fetches all source_ids already stored in staging.raw_postings.
    Used to deduplicate new batches against previously loaded records.
    """
    conn = get_psycopg2_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT source_id FROM staging.raw_postings")
        rows = cur.fetchall()
        return {row[0] for row in rows}
    finally:
        conn.close()


def load_postings_to_db(
    processed_records: List[Dict[str, Any]],
    pull_batch_id: str
) -> int:
    """
    Bulk-inserts processed records into staging.raw_postings using execute_values.
    ON CONFLICT DO NOTHING ensures idempotency against the unique (source_id, batch) constraint.

    Returns:
        Number of rows actually inserted.
    """
    if not processed_records:
        logger.info("No records to load for batch %s", pull_batch_id)
        return 0

    rows = []
    for rec in processed_records:
        # Convert posted_date string to a timezone-aware datetime object
        posted_dt = None
        if rec.get("posted_date"):
            try:
                posted_dt = datetime.fromisoformat(
                    rec["posted_date"].replace("Z", "+00:00")
                )
            except ValueError:
                posted_dt = None

        date_id = None
        if rec.get("date_id"):
            try:
                date_id = datetime.strptime(rec["date_id"], "%Y-%m-%d").date()
            except ValueError:
                date_id = None

        rows.append((
            pull_batch_id,
            rec["source_id"],
            rec["title"],
            rec.get("company"),
            rec.get("location_raw"),
            rec.get("city"),
            rec.get("state"),
            rec.get("country"),
            posted_dt,
            date_id,
            rec.get("salary_min"),
            rec.get("salary_max"),
            rec.get("description"),
            rec.get("skills") or []           # Stored as PostgreSQL TEXT[]
        ))

    conn = get_psycopg2_connection()
    try:
        cur = conn.cursor()
        execute_values(
            cur,
            """
            INSERT INTO staging.raw_postings (
                pull_batch_id, source_id, title, company,
                location_raw, city, state, country,
                posted_date, date_id,
                salary_min, salary_max,
                description, extracted_skills
            )
            VALUES %s
            ON CONFLICT (source_id, pull_batch_id) DO NOTHING
            """,
            rows,
            template="(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::text[])"
        )
        inserted = cur.rowcount
        conn.commit()
        logger.info("Inserted %d rows into staging.raw_postings (batch=%s)", inserted, pull_batch_id)
    finally:
        conn.close()

    return inserted
