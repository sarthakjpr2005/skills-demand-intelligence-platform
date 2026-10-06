"""
Skills Demand Intelligence Platform — Web Application Backend
FastAPI server serving live REST APIs querying PostgreSQL marts & monitoring schemas,
and serving the frontend SPA dashboard.
"""

import sys
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware

from src.utils.db_connector import get_psycopg2_connection
from src.monitoring.runner import run_quality_audit, get_latest_run_id
from src.monitoring.metrics_collector import get_pipeline_health_summary, get_warehouse_table_counts

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("web.app")

app = FastAPI(
    title="Skills Demand Intelligence Platform",
    description="Interactive Executive Intelligence & Observability Dashboard",
    version="1.0.0"
)

# Enable CORS for local development flexibility
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent
REPO_ROOT = BASE_DIR.parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"
ASSETS_DIR = REPO_ROOT / "assets"
FONTS_DIR = REPO_ROOT / "fonts"

STATIC_DIR.mkdir(parents=True, exist_ok=True)
TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
if ASSETS_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(ASSETS_DIR)), name="assets")
if FONTS_DIR.exists():
    app.mount("/fonts", StaticFiles(directory=str(FONTS_DIR)), name="fonts")


@app.get("/styles.css")
def serve_styles():
    css_file = REPO_ROOT / "styles.css"
    if css_file.exists():
        return FileResponse(css_file, media_type="text/css")
    raise HTTPException(status_code=404, detail="styles.css not found")


@app.get("/main.js")
def serve_main_js():
    js_file = REPO_ROOT / "main.js"
    if js_file.exists():
        return FileResponse(js_file, media_type="application/javascript")
    raise HTTPException(status_code=404, detail="main.js not found")


def run_query(sql: str, params: Optional[tuple] = None) -> List[Dict[str, Any]]:
    """Helper to execute SQL and return records as list of dictionaries."""
    conn = get_psycopg2_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql, params or ())
        if cur.description:
            cols = [col[0] for col in cur.description]
            rows = cur.fetchall()
            return [dict(zip(cols, row)) for row in rows]
        conn.commit()
        return []
    finally:
        conn.close()


# ── REST API Endpoints ─────────────────────────────────────────────────────────

@app.get("/api/overview")
def get_overview_kpis():
    """Returns top-level platform KPIs: total postings, companies, skills, salary, and SLA status."""
    stats_sql = """
        SELECT
            (SELECT COUNT(*) FROM marts.fct_postings) AS total_postings,
            (SELECT COUNT(*) FROM marts.dim_company WHERE company_name != 'Unknown') AS total_companies,
            (SELECT COUNT(*) FROM marts.dim_skill) AS tracked_skills,
            (SELECT COUNT(*) FROM marts.fct_posting_skills) AS total_skill_mentions,
            (SELECT ROUND(AVG(salary_midpoint), 0) FROM marts.fct_postings WHERE salary_midpoint IS NOT NULL) AS avg_salary,
            (SELECT MAX(loaded_at) FROM staging.raw_postings) AS last_ingested_at,
            (SELECT MAX(loaded_at) FROM marts.fct_postings) AS last_mart_build_at
    """
    rows = run_query(stats_sql)
    stats = rows[0] if rows else {}

    # SLA health determination
    last_load = stats.get("last_mart_build_at")
    hours_ago = 0.0
    sla_healthy = True
    if last_load:
        delta = datetime.now(last_load.tzinfo) - last_load
        hours_ago = round(delta.total_seconds() / 3600.0, 1)
        sla_healthy = hours_ago <= 24.0

    table_counts = get_warehouse_table_counts()

    return {
        "total_postings": stats.get("total_postings", 0),
        "total_companies": stats.get("total_companies", 0),
        "tracked_skills": stats.get("tracked_skills", 0),
        "total_skill_mentions": stats.get("total_skill_mentions", 0),
        "avg_salary": float(stats.get("avg_salary") or 0),
        "hours_since_last_load": hours_ago,
        "sla_healthy": sla_healthy,
        "table_counts": table_counts
    }


@app.get("/api/skills")
def get_skills_demand(category: Optional[str] = None, search: Optional[str] = None):
    """Returns skill rankings, categories, market penetration %, and avg salaries."""
    conditions = ["1=1"]
    params = []

    if category and category.lower() != "all":
        conditions.append("s.skill_category = %s")
        params.append(category.lower())

    if search:
        conditions.append("s.skill_display_name ILIKE %s")
        params.append(f"%{search}%")

    sql = f"""
        WITH total_market AS (
            SELECT COUNT(*) AS total_postings FROM marts.fct_postings
        )
        SELECT
            s.skill_sk,
            s.skill_display_name,
            s.skill_category,
            COUNT(DISTINCT f.posting_sk) AS posting_count,
            ROUND(100.0 * COUNT(DISTINCT f.posting_sk) / NULLIF((SELECT total_postings FROM total_market), 0), 2) AS market_penetration_pct,
            COALESCE(ROUND(AVG(p.salary_midpoint), 0), 0) AS avg_midpoint_salary,
            COALESCE(ROUND(MIN(p.salary_min), 0), 0) AS min_disclosed_salary,
            COALESCE(ROUND(MAX(p.salary_max), 0), 0) AS max_disclosed_salary
        FROM marts.dim_skill s
        LEFT JOIN marts.fct_posting_skills f ON s.skill_sk = f.skill_sk
        LEFT JOIN marts.fct_postings p ON f.posting_sk = p.posting_sk AND p.salary_midpoint IS NOT NULL
        WHERE {" AND ".join(conditions)}
        GROUP BY s.skill_sk, s.skill_display_name, s.skill_category
        ORDER BY posting_count DESC, s.skill_display_name ASC;
    """
    return run_query(sql, tuple(params))


@app.get("/api/categories")
def get_category_metrics():
    """Returns aggregated demand distribution across skill taxonomy categories."""
    sql = """
        SELECT
            s.skill_category,
            COUNT(DISTINCT s.skill_sk) AS skills_count,
            COUNT(f.posting_sk) AS total_mentions,
            COALESCE(ROUND(AVG(p.salary_midpoint), 0), 0) AS avg_salary
        FROM marts.dim_skill s
        LEFT JOIN marts.fct_posting_skills f ON s.skill_sk = f.skill_sk
        LEFT JOIN marts.fct_postings p ON f.posting_sk = p.posting_sk AND p.salary_midpoint IS NOT NULL
        GROUP BY s.skill_category
        ORDER BY total_mentions DESC;
    """
    return run_query(sql)


@app.get("/api/cooccurrences")
def get_cooccurrences():
    """Returns top skill pairs frequently required together in the same job postings."""
    sql = """
        SELECT
            s1.skill_display_name AS skill_a,
            s1.skill_category AS category_a,
            s2.skill_display_name AS skill_b,
            s2.skill_category AS category_b,
            COUNT(*) AS pair_count
        FROM marts.fct_posting_skills f1
        JOIN marts.fct_posting_skills f2
            ON f1.posting_sk = f2.posting_sk
            AND f1.skill_sk < f2.skill_sk
        JOIN marts.dim_skill s1 ON f1.skill_sk = s1.skill_sk
        JOIN marts.dim_skill s2 ON f2.skill_sk = s2.skill_sk
        GROUP BY s1.skill_display_name, s1.skill_category, s2.skill_display_name, s2.skill_category
        ORDER BY pair_count DESC
        LIMIT 15;
    """
    return run_query(sql)


@app.get("/api/companies")
def get_top_companies(limit: int = 15):
    """Returns top hiring companies with active job counts, avg salary, and top required skills."""
    sql = """
        SELECT
            c.company_sk,
            c.company_name,
            COUNT(DISTINCT f.posting_sk) AS active_postings,
            COALESCE(ROUND(AVG(f.salary_midpoint), 0), 0) AS avg_salary,
            ARRAY_TO_STRING(
                ARRAY(
                    SELECT s.skill_display_name
                    FROM marts.fct_posting_skills fps
                    JOIN marts.dim_skill s ON fps.skill_sk = s.skill_sk
                    WHERE fps.company_sk = c.company_sk
                    GROUP BY s.skill_display_name
                    ORDER BY COUNT(*) DESC
                    LIMIT 4
                ), ', '
            ) AS top_skills
        FROM marts.fct_postings f
        JOIN marts.dim_company c ON f.company_sk = c.company_sk
        WHERE c.company_name != 'Unknown'
        GROUP BY c.company_sk, c.company_name
        ORDER BY active_postings DESC
        LIMIT %s;
    """
    return run_query(sql, (limit,))


@app.get("/api/locations")
def get_geographic_hubs(limit: int = 10):
    """Returns geographic hiring distribution across cities and countries."""
    sql = """
        SELECT
            INITCAP(COALESCE(l.city, 'Remote / Not Specified')) AS city,
            UPPER(COALESCE(l.country, 'UK')) AS country,
            COUNT(f.posting_sk) AS posting_count,
            COALESCE(ROUND(AVG(f.salary_midpoint), 0), 0) AS avg_salary
        FROM marts.fct_postings f
        JOIN marts.dim_location l ON f.location_sk = l.location_sk
        WHERE l.city != 'unknown' AND l.city IS NOT NULL
        GROUP BY l.city, l.country
        ORDER BY posting_count DESC
        LIMIT %s;
    """
    return run_query(sql, (limit,))


@app.get("/api/pipeline/health")
def get_pipeline_health():
    """Returns pipeline runs audit history and latest data quality check assertions."""
    runs = get_pipeline_health_summary(limit=6)

    # Convert timestamps and decimals to JSON serializable types
    for r in runs:
        if r.get("started_at"):
            r["started_at"] = r["started_at"].isoformat()
        if r.get("completed_at"):
            r["completed_at"] = r["completed_at"].isoformat()
        if r.get("duration_seconds") is not None:
            r["duration_seconds"] = float(r["duration_seconds"])
        if r.get("quarantine_failure_rate_pct") is not None:
            r["quarantine_failure_rate_pct"] = float(r["quarantine_failure_rate_pct"])

    # Recent quality checks
    checks_sql = """
        SELECT
            check_id,
            check_name,
            check_category,
            table_name,
            status,
            observed_value,
            threshold_value,
            details,
            executed_at
        FROM monitoring.data_quality_checks
        ORDER BY executed_at DESC, check_id DESC
        LIMIT 11;
    """
    checks = run_query(checks_sql)
    for c in checks:
        if c.get("executed_at"):
            c["executed_at"] = c["executed_at"].isoformat()
        if c.get("observed_value") is not None:
            c["observed_value"] = float(c["observed_value"])
        if c.get("threshold_value") is not None:
            c["threshold_value"] = float(c["threshold_value"])

    return {
        "runs": runs,
        "checks": checks,
        "table_counts": get_warehouse_table_counts()
    }


@app.post("/api/pipeline/run-audit")
def trigger_audit_endpoint(background_tasks: BackgroundTasks):
    """Triggers an on-demand Quality & Observability audit in the background."""
    run_id = get_latest_run_id()
    exit_code = run_quality_audit(run_id=run_id)
    return {
        "status": "COMPLETED",
        "exit_code": exit_code,
        "message": "Quality audit executed successfully. Metrics persisted to PostgreSQL."
    }


# ── Frontend Routes ────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def serve_index():
    """Serves the single-viewport full-bleed video landing page."""
    root_index = REPO_ROOT / "index.html"
    if root_index.exists():
        with open(root_index, "r", encoding="utf-8") as f:
            return f.read()
    index_file = TEMPLATES_DIR / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=404, detail="Frontend template not found")
    with open(index_file, "r", encoding="utf-8") as f:
        return f.read()


@app.get("/dashboard", response_class=HTMLResponse)
def serve_dashboard():
    """Serves the analytics & observability platform dashboard."""
    index_file = TEMPLATES_DIR / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=404, detail="Dashboard template not found")
    with open(index_file, "r", encoding="utf-8") as f:
        return f.read()
