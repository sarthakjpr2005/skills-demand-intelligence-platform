-- =============================================================================
-- Data Quality & Observability Schema
-- Purpose: Track automated data quality assertions, SLA freshness, volume
--          anomalies, and operational alert history.
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS monitoring;

-- =============================================================================
-- data_quality_checks: Individual assertion test run log
-- =============================================================================
CREATE TABLE IF NOT EXISTS monitoring.data_quality_checks (
    check_id        BIGSERIAL PRIMARY KEY,
    run_id          UUID,
    check_name      TEXT NOT NULL,
    check_category  TEXT NOT NULL,  -- FRESHNESS | VOLUME_ANOMALY | COMPLETENESS | QUARANTINE_RATE | INTEGRITY
    table_name      TEXT NOT NULL,
    column_name     TEXT,
    status          TEXT NOT NULL,  -- PASS | WARN | FAIL
    observed_value  NUMERIC,
    threshold_value NUMERIC,
    details         TEXT,
    executed_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_quality_checks_executed_at
    ON monitoring.data_quality_checks (executed_at DESC);

CREATE INDEX IF NOT EXISTS idx_quality_checks_run_id
    ON monitoring.data_quality_checks (run_id);

CREATE INDEX IF NOT EXISTS idx_quality_checks_status
    ON monitoring.data_quality_checks (status);

-- =============================================================================
-- pipeline_run_alerts: Dispatched alert log (Slack, Discord, Console)
-- =============================================================================
CREATE TABLE IF NOT EXISTS monitoring.pipeline_run_alerts (
    alert_id        BIGSERIAL PRIMARY KEY,
    run_id          UUID,
    alert_type      TEXT NOT NULL,  -- SUMMARY | ANOMALY | SLA_BREACH | ERROR
    severity        TEXT NOT NULL,  -- INFO | WARN | CRITICAL
    channel         TEXT NOT NULL,  -- CONSOLE | SLACK | DISCORD
    message         TEXT NOT NULL,
    sent_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_alerts_sent_at
    ON monitoring.pipeline_run_alerts (sent_at DESC);

-- =============================================================================
-- View: v_pipeline_health
-- Executive summary combining run audit, throughput, and error metrics
-- =============================================================================
CREATE OR REPLACE VIEW monitoring.v_pipeline_health AS
SELECT
    r.run_id,
    r.started_at,
    r.completed_at,
    ROUND(EXTRACT(EPOCH FROM (r.completed_at - r.started_at))::numeric, 2) AS duration_seconds,
    r.status,
    r.records_fetched,
    r.records_passed,
    r.records_failed,
    r.records_duped,
    r.records_loaded,
    CASE
        WHEN (r.records_passed + r.records_failed) > 0
        THEN ROUND(100.0 * r.records_failed / (r.records_passed + r.records_failed), 2)
        ELSE 0.00
    END AS quarantine_failure_rate_pct,
    COUNT(c.check_id) AS total_checks_run,
    COUNT(CASE WHEN c.status = 'PASS' THEN 1 END) AS checks_passed,
    COUNT(CASE WHEN c.status = 'WARN' THEN 1 END) AS checks_warned,
    COUNT(CASE WHEN c.status = 'FAIL' THEN 1 END) AS checks_failed
FROM staging.pipeline_runs r
LEFT JOIN monitoring.data_quality_checks c ON r.run_id = c.run_id
GROUP BY
    r.run_id,
    r.started_at,
    r.completed_at,
    r.status,
    r.records_fetched,
    r.records_passed,
    r.records_failed,
    r.records_duped,
    r.records_loaded
ORDER BY r.started_at DESC;

-- =============================================================================
-- View: v_recent_anomalies
-- Surfaces any recent failed or warning data quality checks
-- =============================================================================
CREATE OR REPLACE VIEW monitoring.v_recent_anomalies AS
SELECT
    c.check_id,
    c.run_id,
    c.check_name,
    c.check_category,
    c.table_name,
    c.column_name,
    c.status,
    c.observed_value,
    c.threshold_value,
    c.details,
    c.executed_at
FROM monitoring.data_quality_checks c
WHERE c.status IN ('WARN', 'FAIL')
ORDER BY c.executed_at DESC;

COMMENT ON SCHEMA monitoring IS
    'Observability and data quality tracking schema for pipeline runs and dbt marts.';
