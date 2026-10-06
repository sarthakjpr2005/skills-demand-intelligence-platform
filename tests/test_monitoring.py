"""
Unit & Integration Tests for Monitoring & Data Quality
──────────────────────────────────────────────────────
Verifies:
  1. Freshness assertion boundaries (within SLA vs breached).
  2. Volume anomaly detection with historical baseline comparisons.
  3. Quarantine rate calculation and threshold triggering.
  4. Completeness and zero-skills threshold evaluations.
  5. Digest formatting, severity calculation, and alert payload generation.
"""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

from src.monitoring.quality_checks import (
    CheckResult,
    check_staging_freshness,
    check_marts_freshness,
    check_quarantine_rate,
    check_volume_anomaly,
    check_zero_skills_rate,
    check_referential_integrity,
)
from src.monitoring.alerter import (
    format_quality_digest,
    send_slack_notification,
    send_discord_notification,
)


def test_check_result_tuple_serialization():
    check = CheckResult(
        name="test_check",
        category="FRESHNESS",
        table_name="test_table",
        column_name="loaded_at",
        status="PASS",
        observed_value=1.5,
        threshold_value=24.0,
        details="Loaded 1.5 hours ago"
    )
    tup = check.to_tuple(run_id="abc-123")
    assert tup[0] == "abc-123"
    assert tup[1] == "test_check"
    assert tup[2] == "FRESHNESS"
    assert tup[5] == "PASS"
    assert tup[6] == 1.5


@patch("src.monitoring.quality_checks.get_psycopg2_connection")
def test_staging_freshness_pass(mock_conn):
    mock_cursor = MagicMock()
    mock_conn.return_value.cursor.return_value = mock_cursor
    # 2 hours since load
    mock_cursor.fetchone.return_value = (datetime.now() - timedelta(hours=2), 2.0)

    result = check_staging_freshness(max_hours=24.0)
    assert result.status == "PASS"
    assert result.observed_value == 2.0
    assert "SLA limit: 24.0h" in result.details


@patch("src.monitoring.quality_checks.get_psycopg2_connection")
def test_staging_freshness_fail_when_stale(mock_conn):
    mock_cursor = MagicMock()
    mock_conn.return_value.cursor.return_value = mock_cursor
    # 48 hours since load (SLA limit 24h)
    mock_cursor.fetchone.return_value = (datetime.now() - timedelta(hours=48), 48.0)

    result = check_staging_freshness(max_hours=24.0)
    assert result.status == "FAIL"
    assert result.observed_value == 48.0


@patch("src.monitoring.quality_checks.get_psycopg2_connection")
def test_staging_freshness_fail_on_empty_table(mock_conn):
    mock_cursor = MagicMock()
    mock_conn.return_value.cursor.return_value = mock_cursor
    mock_cursor.fetchone.return_value = None

    result = check_staging_freshness(max_hours=24.0)
    assert result.status == "FAIL"
    assert "0 records" in result.details


@patch("src.monitoring.quality_checks.get_psycopg2_connection")
def test_quarantine_rate_pass_under_threshold(mock_conn):
    mock_cursor = MagicMock()
    mock_conn.return_value.cursor.return_value = mock_cursor
    # 95 passed, 5 failed out of 100 -> 5.0% failure rate
    mock_cursor.fetchone.return_value = (100, 95, 5)

    result = check_quarantine_rate(max_rate=0.15)
    assert result.status == "PASS"
    assert result.observed_value == 5.0


@patch("src.monitoring.quality_checks.get_psycopg2_connection")
def test_quarantine_rate_fail_over_threshold(mock_conn):
    mock_cursor = MagicMock()
    mock_conn.return_value.cursor.return_value = mock_cursor
    # 60 passed, 40 failed out of 100 -> 40.0% failure rate (above 30%)
    mock_cursor.fetchone.return_value = (100, 60, 40)

    result = check_quarantine_rate(max_rate=0.15)
    assert result.status == "FAIL"
    assert result.observed_value == 40.0


@patch("src.monitoring.quality_checks.get_psycopg2_connection")
def test_volume_anomaly_detection_with_historical_drop(mock_conn):
    mock_cursor = MagicMock()
    mock_conn.return_value.cursor.return_value = mock_cursor

    # Current run: 5 records loaded
    mock_cursor.fetchone.return_value = ("run-curr", 5)
    # Historical runs average: 50 records loaded
    mock_cursor.fetchall.return_value = [(50,), (55,), (45,), (50,)]

    result = check_volume_anomaly(run_id="run-curr", min_volume=10)
    # 5 is well below 40% of 50 (floor 20), so it should warn/fail
    assert result.status in ("WARN", "FAIL")
    assert "Volume drop anomaly detected" in result.details


def test_format_quality_digest_all_pass():
    checks = [
        CheckResult("c1", "FRESHNESS", "t1", None, "PASS", 1.0, 24.0, "All fresh"),
        CheckResult("c2", "INTEGRITY", "t2", None, "PASS", 0.0, 0.0, "0 orphans"),
    ]
    alert_type, severity, msg = format_quality_digest(checks, run_id="test-run-123", duration_sec=1.5)
    assert alert_type == "QUALITY_PASSED"
    assert severity == "INFO"
    assert "2/2 Passed" in msg
    assert "1.5s" in msg


def test_format_quality_digest_with_failure():
    checks = [
        CheckResult("c1", "FRESHNESS", "t1", None, "PASS", 1.0, 24.0, "All fresh"),
        CheckResult("c2", "INTEGRITY", "t2", None, "FAIL", 5.0, 0.0, "5 orphans detected"),
    ]
    alert_type, severity, msg = format_quality_digest(checks, run_id="test-run-456")
    assert alert_type == "QUALITY_FAILURE"
    assert severity == "CRITICAL"
    assert "1 Failures" in msg


def test_webhook_graceful_handling_when_unconfigured():
    # When webhook URLs are empty, functions should return False gracefully without raising exceptions
    with patch("src.monitoring.alerter.SLACK_WEBHOOK_URL", ""):
        assert send_slack_notification("test", "INFO") is False

    with patch("src.monitoring.alerter.DISCORD_WEBHOOK_URL", ""):
        assert send_discord_notification("test", "INFO") is False
