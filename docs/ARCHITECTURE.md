# Architecture & Technical Deep-Dive
## Skills Demand Intelligence Platform

---

## 1. System Overview

The **Skills Demand Intelligence Platform** is an end-to-end, production-grade data engineering platform. It continuously extracts job postings from external job board APIs (Adzuna), validates and sanitizes incoming semi-structured payloads, deduplicates postings across daily batch runs, extracts tech skills from unstructured free-text descriptions using regex pattern matching against a curated taxonomy, models data into an analytics-ready Star Schema using dbt in PostgreSQL, orchestrates execution via Apache Airflow, and enforces data observability through an 11-assertion automated data quality engine with multi-channel alerting.

---

## 2. End-to-End Pipeline Architecture

```mermaid
flowchart TD
    subgraph L1["Ingestion Layer"]
        API["Adzuna REST API"] -->|"HTTP GET (JSON)"| RAW["data/raw/YYYY-MM-DD_query.json\n(Raw Landing Layer)"]
    end

    subgraph L2["Validation & Quarantine"]
        RAW --> VAL{"Rule-Based Schema Validator"}
        VAL -->|"Failed Schema / Missing Fields"| BAD["data/bad_records/\n(Quarantine JSON)"]
        VAL -->|"Valid Records"| CLEAN_REC["Validated Records Queue"]
    end

    subgraph L3["Processing & Deduplication"]
        CLEAN_REC --> DEDUP["In-Memory & DB Cross-Batch Dedup\n(source_id hashing)"]
        DEDUP --> SKILL_EXT["Regex Skill Extraction Engine\n(Precompiled Boundaries)"]
        SKILL_EXT --> PROCESSED["Normalized Records\n+ Extracted Skills Array"]
    end

    subgraph L4["Warehousing & Staging"]
        PROCESSED --> BATCH_AUDIT["staging.pipeline_runs\n(UUID Audit Trail)"]
        BATCH_AUDIT --> RAW_POST["staging.raw_postings\n(PostgreSQL Staging Table)"]
    end

    subgraph L5["Dimensional Modeling (dbt Star Schema)"]
        RAW_POST --> STG_VIEW["staging.stg_raw_postings (View)"]
        STG_VIEW --> INT_SKILLS["intermediate.int_posting_skills_unnested (View)"]
        
        STG_VIEW --> DIM_DATE["marts.dim_date (Table)"]
        STG_VIEW --> DIM_COMP["marts.dim_company (Table)"]
        STG_VIEW --> DIM_LOC["marts.dim_location (Table)"]
        INT_SKILLS --> DIM_SKILL["marts.dim_skill (Table)"]
        
        STG_VIEW --> FCT_POST["marts.fct_postings (Table)"]
        INT_SKILLS --> FCT_BRIDGE["marts.fct_posting_skills (Bridge Fact Table)"]
    end

    subgraph L6["Orchestration Layer"]
        SCHED["Apache Airflow DAG / Local Scheduler\n(02:00 Daily Cron)"]
        SCHED -.->|Controls Task Graph| L1
        SCHED -.->|Controls Task Graph| L2
        SCHED -.->|Controls Task Graph| L3
        SCHED -.->|Controls Task Graph| L4
        SCHED -.->|Controls Task Graph| L5
    end

    subgraph L7["Quality & Observability Suite"]
        L5 --> QA["Data Quality & SLA Auditor"]
        QA --> DQ_LOG["monitoring.data_quality_checks"]
        QA --> ALERTS["monitoring.pipeline_run_alerts"]
        ALERTS --> SLACK["Slack / Discord Webhooks"]
        ALERTS --> CLI["Console Operational Cards"]
    end

    subgraph L8["Analytics & Dashboard"]
        FCT_POST & FCT_BRIDGE & DIM_SKILL & DIM_COMP --> BI["FastAPI & Analytical SQL Reports\n(run_analytics.py / Web UI)"]
    end
```

---

## 3. Dimensional Data Model (Star Schema ERD)

To eliminate duplication and allow flexible slicing across skill, company, geography, and time, the analytical layer is modeled as a Kimball-style **Star Schema with a Many-to-Many Bridge Table**:

```mermaid
erDiagram
    dim_date {
        date date_id PK "YYYY-MM-DD"
        int year
        int quarter
        int month
        text month_name
        int day
        text day_name
        int day_of_week
        boolean is_weekend
    }

    dim_company {
        text company_sk PK "MD5(lower(company_name))"
        text company_name
        timestamptz first_seen_at
    }

    dim_location {
        text location_sk PK "MD5(city | state | country)"
        text city
        text state
        text country
        text raw_location_sample
    }

    dim_skill {
        text skill_sk PK "MD5(lower(skill_name))"
        text skill_name
        text skill_display_name
        text skill_category "language, cloud, warehouse, etc."
    }

    fct_postings {
        text posting_sk PK "Inherited surrogate key"
        text source_id "Natural key from source"
        uuid batch_id FK "References staging.pipeline_runs"
        text company_sk FK "References dim_company"
        text location_sk FK "References dim_location"
        date date_id FK "References dim_date"
        timestamptz posted_at
        numeric salary_min
        numeric salary_max
        numeric salary_midpoint
        int skill_count
        text title
        timestamptz loaded_at
    }

    fct_posting_skills {
        text posting_sk FK "References fct_postings"
        text skill_sk FK "References dim_skill"
        text company_sk FK "References dim_company"
        text location_sk FK "References dim_location"
        date date_id FK "References dim_date"
        text skill_name
        int skill_position
    }

    dim_date ||--o{ fct_postings : "has"
    dim_company ||--o{ fct_postings : "hires"
    dim_location ||--o{ fct_postings : "located in"
    fct_postings ||--|{ fct_posting_skills : "requires"
    dim_skill ||--|{ fct_posting_skills : "categorized by"
```

---

## 4. Key Design Decisions & Trade-Offs

### 1. ELT vs. ETL Landing Pattern
- **Decision:** Land untouched raw JSON responses directly in `data/raw/` before any parsing.
- **Trade-off:** Uses modest disk space (~1-2 MB per 1,000 postings).
- **Rationale:** If validation rules or skills taxonomy change later, raw data can be re-parsed without re-fetching from rate-limited external APIs.

### 2. Deterministic MD5 Surrogate Keys vs. Serial Auto-Increment IDs
- **Decision:** Dimensions use `MD5(LOWER(TRIM(natural_key)))` as surrogate primary keys.
- **Trade-off:** 32-character string keys require slightly more storage than 4-byte integers.
- **Rationale:** MD5 hashing produces **deterministic keys across idempotent rebuilds**. Running `dbt run` 50 times produces the exact same surrogate key for `"Google"` or `"Snowflake"`. A database sequence (`SERIAL`) would increment on every truncate/rebuild, invalidating downstream foreign keys.

### 3. Many-to-Many Bridge Table (`fct_posting_skills`) vs. Array Aggregations
- **Decision:** Decompose skills arrays into a bridge fact table connecting `fct_postings` and `dim_skill`.
- **Trade-off:** Bridge table has multiple rows per posting.
- **Rationale:** Enables standard relational joins, indexing, and high-performance aggregations (e.g. self-joining to generate tech stack co-occurrence pairs, calculating market penetration percentages, and computing average salary by skill) without needing database-specific unnest operators in every analytical query.

### 4. Cross-Batch Deduplication & Idempotency
- **Decision:** Deduplicate against existing database records using natural key `source_id` before loading, with a secondary constraint `UNIQUE (source_id, pull_batch_id)` in `staging.raw_postings` and `DISTINCT ON (source_id) ORDER BY loaded_at DESC` in `marts.fct_postings`.
- **Trade-off:** Slight pre-load index check overhead.
- **Rationale:** Eliminates duplicate counting while preserving historical batch traceability.

### 5. Regex Precompilation vs. Heavy NLP Models
- **Decision:** Precompile regex boundary patterns `\b(?:apache\s*)?airflow\b` against a curated 30-skill taxonomy.
- **Trade-off:** Does not extract unlisted emergent technologies until added to taxonomy.
- **Rationale:** Extreme speed (processing 1,000 postings takes <0.15s), zero external GPU/cloud dependencies, and zero hallucination risk compared to LLMs.

---

## 5. Automated Data Quality & Observability Architecture

The platform embeds automated quality gates across every execution:

```
Pipeline Run
    │
    ▼
[Tasks 1-4: Extract → Validate → Process → Load]
    │
    ▼
[Task 5: dbt Run & Test (32 Schema Assertions)]
    │
    ▼
[Task 6: Data Quality & Observability Suite (11 Checks)]
    ├── Freshness SLA (<= 24h)
    ├── Volume Anomaly (< 40% of rolling avg)
    ├── Quarantine Rejection Rate (<= 15%)
    ├── Zero-Skills Drift Rate (<= 85%)
    ├── Column Completeness (Title 0% null, Company < 15%)
    └── Referential Integrity (0 orphan keys)
    │
    ▼
[Multi-Channel Alert Dispatcher]
    ├── Persist to monitoring.data_quality_checks
    ├── Render ASCII console summary card
    └── Dispatch Webhook to Slack & Discord (if configured)
```
