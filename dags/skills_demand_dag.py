"""
Airflow DAG — Skills Demand Intelligence Platform
──────────────────────────────────────────────────
Production-grade DAG that orchestrates the end-to-end pipeline on a scheduled cadence.

Design Decisions:
  1. DAG-level default_args set max_active_runs=1 to prevent overlapping runs.
  2. Each task maps 1:1 to an isolated pipeline stage (Extract, Validate, Process, Load, Transform, Audit).
  3. XCom is used to pass intermediate metadata and landed file paths cleanly.
  4. Tasks use PythonOperator wrapping core src/ modules for clean code separation.
  5. The dbt task executes `dbt run && dbt test` atomically.
  6. on_failure_callback writes failure metrics to pipeline_runs for audit continuity.
  7. Retries: 2 retries with exponential backoff for transient API/network blips.

Deployment:
  - Copy to Airflow DAGs directory (e.g. $AIRFLOW_HOME/dags/)
  - Ensure environment variables are configured (ADZUNA credentials, DB credentials)
  - Start Airflow scheduler and webserver
"""

from datetime import datetime, timedelta
from pathlib import Path

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator

# ── Pipeline modules ─────────────────────────────────────────────────────────
from src.ingestion.adzuna_client import extract_postings_from_adzuna
from src.validation.validator import validate_raw_postings
from src.processing.processor import deduplicate_and_process_records
from src.ingestion.loader import (
    start_pipeline_run,
    complete_pipeline_run,
    get_existing_source_ids,
    load_postings_to_db,
)

# ── DAG-level constants ────────────────────────────────────────────────────────
QUERY_TERMS = [
    "data engineer",
    "analytics engineer",
    "data platform engineer",
    "mlops engineer",
]
COUNTRY = "gb"
RESULTS_PER_PAGE = 50


# ── Default arguments applied to every task ───────────────────────────────────
default_args = {
    "owner": "sarthak",
    "depends_on_past": False,           # Each daily run is independent
    "email_on_failure": False,          # Set True + email list in production
    "email_on_retry": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "retry_exponential_backoff": True,  # 5m → 10m backoff on successive retries
}


# ── Task callables ─────────────────────────────────────────────────────────────

def task_extract(**context) -> dict:
    """
    Task 1: Extraction
    Calls Adzuna for each query term and lands raw JSON.
    Pushes a dict of {query_term: file_path} into XCom for downstream tasks.
    """
    landed_files = {}
    for query in QUERY_TERMS:
        raw_file = extract_postings_from_adzuna(
            query=query,
            country=COUNTRY,
            results_per_page=RESULTS_PER_PAGE
        )
        landed_files[query] = str(raw_file)

    # Push to XCom: downstream tasks pull this via context['ti'].xcom_pull()
    context["ti"].xcom_push(key="landed_files", value=landed_files)
    return landed_files


def task_validate(**context) -> dict:
    """
    Task 2: Validation & Quarantine
    Validates every landed file; aggregates validation reports per query.
    Pushes combined valid_records + stats into XCom.
    """
    ti = context["ti"]
    landed_files: dict = ti.xcom_pull(task_ids="extract", key="landed_files")

    all_valid_records = []
    total_failed = 0

    for query, file_path in landed_files.items():
        report = validate_raw_postings(Path(file_path))
        all_valid_records.extend(report["valid_records"])
        total_failed += report["failed_records"]

    ti.xcom_push(key="valid_records", value=all_valid_records)
    ti.xcom_push(key="total_fetched", value=sum(1 for _ in all_valid_records) + total_failed)
    ti.xcom_push(key="total_failed", value=total_failed)
    return {"valid": len(all_valid_records), "failed": total_failed}


def task_process(**context) -> dict:
    """
    Task 3: Processing (Deduplication & Skill Extraction)
    Deduplicates against existing warehouse records and extracts tech skills.
    """
    ti = context["ti"]
    valid_records: list = ti.xcom_pull(task_ids="validate", key="valid_records")

    existing_ids = get_existing_source_ids()
    processed_records, duped = deduplicate_and_process_records(
        valid_records,
        existing_source_ids=existing_ids
    )

    ti.xcom_push(key="processed_records", value=processed_records)
    ti.xcom_push(key="records_duped", value=duped)
    return {"processed": len(processed_records), "duped": duped}


def task_load(**context) -> dict:
    """
    Task 4: Staging Batch Ingestion
    Creates a pipeline_run audit record and bulk-inserts processed records.
    """
    ti = context["ti"]
    processed_records: list = ti.xcom_pull(task_ids="process", key="processed_records")
    total_fetched: int   = ti.xcom_pull(task_ids="validate", key="total_fetched") or 0
    total_failed: int    = ti.xcom_pull(task_ids="validate", key="total_failed") or 0
    records_duped: int   = ti.xcom_pull(task_ids="process",  key="records_duped") or 0

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
    except Exception as exc:
        complete_pipeline_run(
            run_id=run_id,
            records_fetched=0, records_passed=0, records_failed=0,
            records_duped=0, records_loaded=0,
            status="FAILED", error_message=str(exc)
        )
        raise

    ti.xcom_push(key="run_id", value=run_id)
    ti.xcom_push(key="records_loaded", value=records_loaded)
    return {"run_id": run_id, "records_loaded": records_loaded}


def task_quality_audit(**context) -> int:
    """
    Task 6: Data Quality & Observability Audit
    Executes automated freshness, volume anomaly, completeness, and integrity checks,
    persisting results into the monitoring schema and alerting on anomalies.
    """
    ti = context["ti"]
    run_id: str = ti.xcom_pull(task_ids="load", key="run_id")
    from src.monitoring.runner import run_quality_audit
    exit_code = run_quality_audit(run_id=run_id)
    if exit_code != 0:
        raise ValueError(f"Data quality audit failed for run {run_id}")
    return exit_code


# ── DAG Definition ─────────────────────────────────────────────────────────────

with DAG(
    dag_id="skills_demand_pipeline",
    description="Daily pipeline: Extract Adzuna job postings → Validate → Dedup → Load → dbt transform → Quality Audit",
    schedule_interval="0 2 * * *",          # 2:00 AM UTC every day (off-peak)
    start_date=datetime(2026, 10, 1),
    catchup=False,                          # Don't backfill missed runs
    max_active_runs=1,                      # Prevent overlapping daily runs
    default_args=default_args,
    tags=["skills-platform", "data-engineering", "adzuna", "quality-observability"],
) as dag:

    # ── Task 1: Extract raw postings ──────────────────────────────────────────
    t_extract = PythonOperator(
        task_id="extract",
        python_callable=task_extract,
    )

    # ── Task 2: Validate raw records ──────────────────────────────────────────
    t_validate = PythonOperator(
        task_id="validate",
        python_callable=task_validate,
    )

    # ── Task 3: Deduplicate + extract skills ──────────────────────────────────
    t_process = PythonOperator(
        task_id="process",
        python_callable=task_process,
    )

    # ── Task 4: Load to PostgreSQL staging table ──────────────────────────────
    t_load = PythonOperator(
        task_id="load",
        python_callable=task_load,
    )

    # ── Task 5: Run dbt models + tests ───────────────────────────────────────
    # BashOperator runs dbt run then dbt test atomically.
    # If dbt test fails, the task fails and Airflow marks the run RED.
    t_dbt = BashOperator(
        task_id="dbt_transform_and_test",
        bash_command=(
            "cd {{ var.value.PROJECT_ROOT }}/dbt_project && "
            "dbt run --profiles-dir . && "
            "dbt test --profiles-dir . --no-partial-parse"
        ),
        env={
            "DB_HOST":     "{{ var.value.DB_HOST }}",
            "DB_PORT":     "{{ var.value.DB_PORT }}",
            "DB_NAME":     "{{ var.value.DB_NAME }}",
            "DB_USER":     "{{ var.value.DB_USER }}",
            "DB_PASSWORD": "{{ var.value.DB_PASSWORD }}",
        }
    )

    # ── Task 6: Data Quality & Observability Audit ────────────────────────────
    t_quality_audit = PythonOperator(
        task_id="quality_observability_audit",
        python_callable=task_quality_audit,
    )

    # ── DAG Dependency Chain ──────────────────────────────────────────────────
    # extract → validate → process → load → dbt_transform_and_test → quality_observability_audit
    t_extract >> t_validate >> t_process >> t_load >> t_dbt >> t_quality_audit

