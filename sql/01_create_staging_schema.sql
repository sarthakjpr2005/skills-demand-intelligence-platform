-- =============================================================================
-- Raw Staging Table DDL
-- Purpose: Land processed job postings into PostgreSQL with full batch tracking.
-- Design Decisions:
--   1. source_id is NOT the PK to allow multi-batch tracking of the same posting.
--      We assign a surrogate serial PK (id).
--   2. UNIQUE (source_id, pull_batch_id) prevents double-loading within a batch run.
--   3. pull_batch_id (UUID) lets us trace every record back to the exact pipeline run.
--   4. loaded_at is set automatically by the DB on INSERT.
-- =============================================================================

-- Create the database (run this separately as postgres superuser if needed)
-- CREATE DATABASE skills_platform;

-- Connect to skills_platform before running the rest
-- \c skills_platform

-- Staging schema to isolate raw data from transformed/analytics layers
CREATE SCHEMA IF NOT EXISTS staging;

-- =============================================================================
-- pipeline_runs: Audit log for every pipeline execution
-- =============================================================================
CREATE TABLE IF NOT EXISTS staging.pipeline_runs (
    run_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    started_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at    TIMESTAMPTZ,
    query_term      TEXT,
    country_code    TEXT,
    page_number     INT,
    records_fetched INT,
    records_passed  INT,
    records_failed  INT,
    records_duped   INT,
    records_loaded  INT,
    status          TEXT NOT NULL DEFAULT 'RUNNING',   -- RUNNING | SUCCESS | FAILED
    error_message   TEXT
);

-- =============================================================================
-- raw_postings: Landing pad for every processed job posting
-- =============================================================================
CREATE TABLE IF NOT EXISTS staging.raw_postings (
    id                  BIGSERIAL PRIMARY KEY,
    pull_batch_id       UUID NOT NULL REFERENCES staging.pipeline_runs(run_id),
    source_id           TEXT NOT NULL,
    title               TEXT NOT NULL,
    company             TEXT,
    location_raw        TEXT,
    city                TEXT,
    state               TEXT,
    country             TEXT,
    posted_date         TIMESTAMPTZ,
    date_id             DATE,
    salary_min          NUMERIC(12, 2),
    salary_max          NUMERIC(12, 2),
    description         TEXT,
    extracted_skills    TEXT[],          -- array of skill names e.g. {python,sql,airflow}
    loaded_at           TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- Prevent double-loading the same posting in the same pipeline run
    CONSTRAINT uq_source_id_per_batch UNIQUE (source_id, pull_batch_id)
);

-- Index on source_id for fast duplicate lookups across batches
CREATE INDEX IF NOT EXISTS idx_raw_postings_source_id
    ON staging.raw_postings (source_id);

-- Index on pull_batch_id for fast batch-level queries and purges
CREATE INDEX IF NOT EXISTS idx_raw_postings_batch
    ON staging.raw_postings (pull_batch_id);

-- Composite index for analytics on date and country
CREATE INDEX IF NOT EXISTS idx_raw_postings_date_country
    ON staging.raw_postings (date_id, country);

COMMENT ON TABLE staging.pipeline_runs IS
    'One row per pipeline execution; tracks run metadata and record-level counts.';

COMMENT ON TABLE staging.raw_postings IS
    'Raw processed job postings landed from the Adzuna API. One row per unique (source_id, batch).';

COMMENT ON COLUMN staging.raw_postings.pull_batch_id IS
    'UUID of the pipeline_run that loaded this record. Enables full audit trail.';

COMMENT ON COLUMN staging.raw_postings.extracted_skills IS
    'PostgreSQL text array of skill names extracted from title + description.';
