"""
Unit Tests for Data Processing (Deduplication & Skill Extraction)
"""

import pytest
from src.processing.processor import (
    extract_skills_from_text,
    clean_html_text,
    process_record,
    deduplicate_and_process_records
)


def test_clean_html_text():
    raw = "Senior Engineer &amp; Architect <br> looking for talent &lt;fast&gt;"
    cleaned = clean_html_text(raw)
    assert cleaned == "Senior Engineer & Architect looking for talent <fast>"


def test_skill_extraction_keywords():
    text = "We are seeking a Data Engineer experienced with Python, SQL, Airflow, and dbt on AWS."
    skills_meta = extract_skills_from_text(text)
    skill_names = [s["skill"] for s in skills_meta]

    assert "python" in skill_names
    assert "sql" in skill_names
    assert "airflow" in skill_names
    assert "dbt" in skill_names
    assert "aws" in skill_names
    assert "kafka" not in skill_names


def test_skill_extraction_case_insensitivity():
    text = "PYTHON and PostgreSQL with APACHE AIRFLOW"
    skills_meta = extract_skills_from_text(text)
    skill_names = [s["skill"] for s in skills_meta]

    assert "python" in skill_names
    assert "postgresql" in skill_names
    assert "airflow" in skill_names


def test_deduplication_within_batch():
    records = [
        {
            "id": "1001",
            "title": "Data Engineer",
            "company": {"display_name": "Company A"},
            "created": "2026-10-01T10:00:00Z",
            "description": "Python, SQL"
        },
        {
            "id": "1001",  # duplicate ID
            "title": "Data Engineer (Republished)",
            "company": {"display_name": "Company A"},
            "created": "2026-10-01T10:00:00Z",
            "description": "Python, SQL"
        },
        {
            "id": "1002",
            "title": "Analytics Engineer",
            "company": {"display_name": "Company B"},
            "created": "2026-10-01T11:00:00Z",
            "description": "dbt, Snowflake"
        }
    ]

    processed, dupes = deduplicate_and_process_records(records)
    assert len(processed) == 2
    assert dupes == 1
    assert processed[0]["source_id"] == "1001"
    assert processed[1]["source_id"] == "1002"


def test_deduplication_against_existing_ids():
    records = [
        {
            "id": "1001",  # Already in database
            "title": "Data Engineer",
            "company": {"display_name": "Company A"},
            "created": "2026-10-01T10:00:00Z",
            "description": "Python, SQL"
        },
        {
            "id": "1003",  # Brand new
            "title": "BI Developer",
            "company": {"display_name": "Company C"},
            "created": "2026-10-01T12:00:00Z",
            "description": "Tableau and SQL"
        }
    ]

    existing_ids = {"1001"}
    processed, dupes = deduplicate_and_process_records(records, existing_source_ids=existing_ids)
    assert len(processed) == 1
    assert dupes == 1
    assert processed[0]["source_id"] == "1003"
    assert "tableau" in processed[0]["skills"]
