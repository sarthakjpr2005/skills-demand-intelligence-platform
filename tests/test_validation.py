"""
Unit Tests for Job Record Schema Validation
"""

import pytest
from src.validation.validator import JobRecordValidator


@pytest.fixture
def valid_record():
    return {
        "id": "12345678",
        "title": "Senior Data Engineer",
        "company": {"display_name": "Acme Corp"},
        "location": {"display_name": "London, UK"},
        "created": "2026-10-01T12:00:00Z",
        "description": "Looking for Python, SQL, and Airflow experience."
    }


def test_valid_record_passes(valid_record):
    is_valid, reasons = JobRecordValidator.validate_record(valid_record)
    assert is_valid is True
    assert reasons == []


def test_missing_source_id(valid_record):
    record = valid_record.copy()
    record["id"] = None
    is_valid, reasons = JobRecordValidator.validate_record(record)
    assert is_valid is False
    assert any("source_id" in r for r in reasons)


def test_missing_title(valid_record):
    record = valid_record.copy()
    record["title"] = "   "
    is_valid, reasons = JobRecordValidator.validate_record(record)
    assert is_valid is False
    assert any("title" in r for r in reasons)


def test_missing_company_name(valid_record):
    record = valid_record.copy()
    record["company"] = {}
    is_valid, reasons = JobRecordValidator.validate_record(record)
    assert is_valid is False
    assert any("company.display_name" in r for r in reasons)


def test_invalid_date(valid_record):
    record = valid_record.copy()
    record["created"] = "not-a-real-date"
    is_valid, reasons = JobRecordValidator.validate_record(record)
    assert is_valid is False
    assert any("Invalid date format" in r for r in reasons)


def test_batch_validation_summary(valid_record):
    bad_record = {
        "id": "",
        "title": None,
        "company": None,
        "created": "invalid"
    }
    report = JobRecordValidator.validate_batch([valid_record, bad_record], batch_name="test_batch")
    assert report["total_records"] == 2
    assert report["passed_records"] == 1
    assert report["failed_records"] == 1
    assert report["pass_rate_pct"] == 50.0
    assert len(report["valid_records"]) == 1
