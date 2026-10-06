# Production Deployment & Operations Guide
## Skills Demand Intelligence Platform

---

## 1. Prerequisites & System Requirements

- **Operating System:** Linux (Ubuntu 22.04 LTS recommended), macOS, or Windows 10/11 with WSL2 / Native PowerShell.
- **Python:** Version 3.10+
- **Database:** PostgreSQL 14+
- **Memory:** Minimum 2 GB RAM (4 GB recommended if running Airflow webserver and scheduler).
- **Disk:** 5 GB free disk space.

---

## 2. Environment Variables & Secrets Management

Store secrets exclusively in `.env` (or cloud secrets manager). Never commit credentials to version control.

```bash
# Copy example template
cp .env.example .env
```

Key environment configurations:

```ini
# Adzuna Developer Credentials
ADZUNA_APP_ID=your_app_id
ADZUNA_APP_KEY=your_app_key
ADZUNA_COUNTRY=gb

# PostgreSQL Warehouse Connection
DB_HOST=localhost
DB_PORT=5432
DB_NAME=skills_platform
DB_USER=postgres
DB_PASSWORD=your_secure_password

# Data Quality & SLA Thresholds
FRESHNESS_MAX_HOURS=24.0
QUARANTINE_MAX_FAIL_RATE=0.15
ZERO_SKILLS_MAX_RATE=0.85
MIN_BATCH_VOLUME=5

# Optional Webhook Alerts (Leave blank for console-only logging)
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/T00/B00/XXXX
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/XXXX/YYYY
```

---

## 3. Docker Compose Deployment Blueprint

For containerized cloud deployment (e.g. AWS EC2, GCP Compute Engine, Azure VM), use Docker Compose to run PostgreSQL and Airflow together:

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:15-alpine
    container_name: skills_postgres
    restart: always
    environment:
      POSTGRES_DB: skills_platform
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./sql/01_create_staging_schema.sql:/docker-entrypoint-initdb.d/01_init.sql
      - ./sql/02_create_monitoring_schema.sql:/docker-entrypoint-initdb.d/02_init.sql

  scheduler:
    build: .
    container_name: skills_scheduler
    restart: always
    depends_on:
      - postgres
    env_file:
      - .env
    command: python local_scheduler.py --time 02:00

volumes:
  pgdata:
```

---

## 4. Deploying to Native Apache Airflow

To deploy onto a dedicated Airflow instance:

1. Copy the DAG file to your Airflow DAGs directory:
   ```bash
   cp dags/skills_demand_dag.py $AIRFLOW_HOME/dags/
   ```
2. Configure Airflow Variables in the Airflow UI (**Admin → Variables**):
   - `PROJECT_ROOT`: Absolute path to project root.
   - `DB_HOST`: Hostname of PostgreSQL database.
   - `DB_PORT`: Port (5432).
   - `DB_NAME`: Database name (`skills_platform`).
   - `DB_USER`: Database username.
   - `DB_PASSWORD`: Database password.
3. Enable and unpause the DAG:
   ```bash
   airflow dags unpause skills_demand_pipeline
   ```

---

## 5. Setting Up Slack & Discord Webhooks

### Slack Integration
1. Create an Incoming Webhook in your Slack Workspace ([api.slack.com/messaging/webhooks](https://api.slack.com/messaging/webhooks)).
2. Copy Webhook URL to `SLACK_WEBHOOK_URL` in `.env`.
3. Test alert dispatch:
   ```bash
   python check_pipeline_health.py
   ```

### Discord Integration
1. Go to Discord Server Settings → Integrations → Webhooks → New Webhook.
2. Copy Webhook URL to `DISCORD_WEBHOOK_URL` in `.env`.

---

## 6. Database Maintenance & Operations Runbook

### Database Backups (pg_dump)
Run daily or weekly logical backups:
```bash
pg_dump -h localhost -U postgres -d skills_platform -Fc -f "skills_platform_$(date +%F).dump"
```

### Routine VACUUM and ANALYZE
PostgreSQL creates dead tuples during batch updates and dbt rebuilds. Schedule periodic vacuuming:
```sql
VACUUM ANALYZE staging.raw_postings;
VACUUM ANALYZE marts.fct_postings;
VACUUM ANALYZE marts.fct_posting_skills;
```

### Table Partitioning Strategy (Scale > 1 Million Records)
When `staging.raw_postings` exceeds 1,000,000 rows, convert it to a partitioned table by range on `date_id`:
```sql
CREATE TABLE staging.raw_postings_partitioned (
    LIKE staging.raw_postings INCLUDING ALL
) PARTITION BY RANGE (date_id);

CREATE TABLE staging.raw_postings_2026_q1 PARTITION OF staging.raw_postings_partitioned
    FOR VALUES FROM ('2026-01-01') TO ('2026-04-01');
```
