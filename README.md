# Skills Demand Intelligence Platform

An end-to-end Data Engineering and Analytics platform that continuously extracts job postings from the Adzuna API, deduplicates multi-board postings, extracts tech skills from unstructured free-text descriptions, models data into an analytics-ready Star Schema using dbt in PostgreSQL, orchestrates scheduled pipelines with Apache Airflow, enforces automated data quality & SLA observability, and serves real-time insights via a FastAPI analytics dashboard.

---

## 🎯 Overview & Problem Statement
Job postings across the tech industry are fragmented, unstructured, and heavily duplicated across boards (e.g., "Data Engineer", "Big Data Engineer", "Python Platform SDE" often describe overlapping skill requirements). Furthermore, critical technical skills are buried inside free-text job descriptions rather than clean categorical fields.

This platform automates the ELT lifecycle to turn raw, noisy job market data into reliable, structured intelligence:
- **Market Skill Trends:** Quantify high-velocity tech skills across languages, cloud providers, orchestrators, and databases.
- **Tech Stack Co-occurrences:** Identify which technologies are most frequently required together (e.g., `Python + AWS + Snowflake`).
- **Salary Benchmarking:** Track median and percentile compensation bands normalized by skill and location.
- **Automated Observability:** Continuous verification of data freshness SLAs, volume anomalies, quarantine rejection rates, and referential integrity.

---

## 🏗️ Architecture & Pipeline Flow

```text
[Adzuna REST API]
       │
       ▼ (1. Ingestion)
[Raw Landing Layer: data/raw/YYYY-MM-DD_query.json]
       │
       ▼ (2. Validation & Quarantine)
[Schema & Rule Check -> data/bad_records/ for quarantine]
       │
       ▼ (3. Processing & Extraction)
[Cross-pull Dedup + Regex Skill Extraction Engine]
       │
       ▼ (4. PostgreSQL Warehouse Staging)
[staging.raw_postings Staging Table with pull_batch_id]
       │
       ▼ (5. dbt Dimensional Modeling)
[Star Schema: fct_postings, dim_skill, dim_company, dim_location, dim_date, fct_posting_skills]
       │
       ▼ (6. Workflow Orchestration)
[Apache Airflow Daily DAG / Local Scheduler with retries & idempotency]
       │
       ▼ (7. Data Observability & Quality Engine)
[11 automated assertions + freshness SLAs + anomaly detection + multi-channel alerts]
       │
       ▼ (8. Analytics & Visualization)
[FastAPI REST API & Interactive Observability Dashboard]
```

---

## 🗺️ Core Architecture Components

| Component | Responsibility | Technology Stack |
|---|---|---|
| **Data Ingestion** | Extract job postings from Adzuna REST API; land raw JSON untouched for auditability | Python, Requests, REST API |
| **Validation & Quarantine** | Strict schema validation, type checking, quarantining invalid records | Python, JSON Schema |
| **Processing & Extraction** | Idempotent title deduplication and regex boundary skill extraction | Python, Precompiled Regex |
| **Warehouse Staging** | High-performance batch ingestion with execution UUID audit tracking | PostgreSQL 15, Psycopg2 |
| **Dimensional Modeling** | Kimball star schema transformation with surrogate MD5 keys and 32 schema tests | dbt Core, SQL |
| **Pipeline Orchestration** | Scheduled daily execution with exponential backoff retries and dependency graph | Apache Airflow, Python `schedule` |
| **Quality & Observability** | 11 automated assertions checking freshness SLAs, volume anomalies, and null rates | SQL, Webhook Alerting (Slack/Discord) |
| **Analytics & UI Dashboard** | Interactive live dashboard, tech co-occurrence matrices, and warehouse metrics | FastAPI, Chart.js, HTML5/CSS3 |

---

## 🚀 Setup & Getting Started

### 1. Prerequisites
- Python 3.10+
- PostgreSQL 14+
- Git

### 2. Environment Setup
```bash
python -m venv venv

# On Windows:
.\venv\Scripts\activate

# On Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
```

### 3. Environment Variables
Copy `.env.example` to `.env` and configure your database and Adzuna Developer API credentials:
```bash
cp .env.example .env
```

Configuration parameters:
```ini
ADZUNA_APP_ID=your_adzuna_app_id
ADZUNA_APP_KEY=your_adzuna_app_key
ADZUNA_COUNTRY=gb

DB_HOST=localhost
DB_PORT=5432
DB_NAME=skills_platform
DB_USER=postgres
DB_PASSWORD=your_password
```

---

## ⚡ Running the Pipeline

### 1. End-to-End Pipeline Execution
Run the complete extract, validate, process, and load sequence:
```bash
python run_pipeline.py --query "data engineer" --country "gb" --results 50
```

### 2. Execute dbt Dimensional Transformations & Tests
```bash
cd dbt_project
dbt run
dbt test
cd ..
```

### 3. Run Pipeline Scheduler
```bash
# Execute immediate one-off pipeline run:
python local_scheduler.py --run-now

# Run daily scheduled service (defaults to 02:00 AM UTC):
python local_scheduler.py --time 02:00
```

### 4. Airflow Orchestration
The production Airflow DAG is located at `dags/skills_demand_dag.py`:
- Deploy by copying `dags/skills_demand_dag.py` to `$AIRFLOW_HOME/dags/`.
- Configured with max active runs = 1, exponential backoff retries, and comprehensive task dependencies.

---

## 🛡️ Data Quality & Observability Suite

The platform executes 11 automated assertions spanning freshness, volume anomalies, null integrity, and referential constraints:
- **Freshness SLA:** Verifies staging and dimensional mart tables have been updated within the configured SLA window (<= 24h).
- **Volume Anomaly Detection:** Compares current batch size against a moving baseline to flag ingestion drops (< 40% of average).
- **Quarantine Rejection Rate:** Guarantees validation failure rate remains below critical threshold (<= 15%).
- **Taxonomy Drift:** Verifies that zero-skill posting rates remain within expected statistical bounds.
- **Referential Integrity:** Guarantees zero orphan records between facts and dimensional tables.

```bash
# Run complete observability audit:
python check_pipeline_health.py

# View pipeline execution summary & anomaly history:
python check_pipeline_health.py --health-summary

# Run automated test suite:
pytest -v
```

---

## 📊 Analytical Showcase & Web Dashboard

### 1. CLI Intelligence Reports
Run pre-built analytical reports against the dbt Star Schema:
```bash
# Run all analytical reports:
python run_analytics.py --report all

# Run specific reports:
python run_analytics.py --report skills       # Top in-demand tech skills
python run_analytics.py --report categories   # Demand distribution by category
python run_analytics.py --report cooccur      # Tech stack co-occurrence pairs
python run_analytics.py --report salary       # Compensation percentiles by skill
python run_analytics.py --report companies    # Top hiring companies and stacks
python run_analytics.py --report geo          # Geographic tech hiring clusters
```

### 2. Interactive Web Dashboard
Launch the FastAPI real-time intelligence dashboard:
```bash
python run_web.py
```
Open **`http://127.0.0.1:8000`** in your browser to view:
- **Executive Overview:** Live platform KPIs, salary benchmarks, and category distributions.
- **Skills Explorer:** Interactive filtering across languages, cloud tools, databases, and frameworks.
- **Tech Stacks & Co-occurrences:** Technology correlation matrices and multi-skill pair analysis.
- **Observability Hub:** Automated check status rings, warehouse table counters, and real-time audit triggers.

---

## 📚 Technical Documentation

- **[System Architecture & Design Decisions](docs/ARCHITECTURE.md)**: In-depth technical breakdown of the ELT design, Kimball dimensional star schema, surrogate key strategies, and regex parsing engine.
- **[Production Deployment & Operations Guide](docs/DEPLOYMENT_GUIDE.md)**: Containerization blueprint, Docker Compose configuration, Airflow setup, database maintenance, and alert integrations.
- **[Analytical SQL Showcase](sql/03_analytical_queries.sql)**: Production SQL queries for skill demand analysis, co-occurrence pairs, and salary percentiles.
