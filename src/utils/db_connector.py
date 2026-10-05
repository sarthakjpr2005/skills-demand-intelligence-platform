"""
Database Utilities
Provides the SQLAlchemy engine, psycopg2 connection pool, and schema initialization.
"""

import logging
import psycopg2
from psycopg2.extras import execute_values
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from config.settings import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD

logger = logging.getLogger("utils.db_connector")


# =============================================================================
# Engine & Connection Factories
# =============================================================================

def get_sqlalchemy_engine() -> Engine:
    """Returns a SQLAlchemy Engine for the skills_platform database."""
    url = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    engine = create_engine(url, pool_pre_ping=True)
    return engine


def get_psycopg2_connection():
    """Returns a raw psycopg2 connection for bulk COPY/execute_values operations."""
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )


# =============================================================================
# Schema Initialization
# =============================================================================

def create_database_if_not_exists():
    """
    Creates the skills_platform database if it does not already exist.
    Must connect to the 'postgres' maintenance database first.
    """
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname="postgres",
        user=DB_USER,
        password=DB_PASSWORD
    )
    conn.autocommit = True  # Required for CREATE DATABASE
    cur = conn.cursor()

    cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (DB_NAME,))
    exists = cur.fetchone()

    if not exists:
        logger.info("Creating database: %s", DB_NAME)
        cur.execute(f"CREATE DATABASE {DB_NAME}")
        logger.info("Database '%s' created successfully.", DB_NAME)
    else:
        logger.info("Database '%s' already exists. Skipping creation.", DB_NAME)

    cur.close()
    conn.close()


def apply_schema(sql_file_path: str):
    """Reads and executes a SQL DDL file against the skills_platform database."""
    with open(sql_file_path, "r", encoding="utf-8") as f:
        sql = f.read()

    # Strip lines that are pure SQL comments (-- ...) or blank to clean up the script
    # but preserve multi-line statement bodies (e.g. COMMENT ON TABLE ... IS '...')
    # Execute the full cleaned script via psycopg2 which handles semicolons properly.
    conn = get_psycopg2_connection()
    conn.autocommit = True
    cur = conn.cursor()

    # Filter out comment-only lines and PSQL backslash meta-commands (\c, \d)
    cleaned_lines = []
    for line in sql.splitlines():
        stripped = line.strip()
        if stripped.startswith("--") or stripped.startswith("\\") or stripped == "":
            continue
        cleaned_lines.append(line)

    cleaned_sql = "\n".join(cleaned_lines)
    cur.execute(cleaned_sql)

    logger.info("Applied DDL from %s", sql_file_path)
    cur.close()
    conn.close()


def initialize_schema(sql_file_path: str = "sql/01_create_staging_schema.sql"):
    """Full initialization: create DB if needed, then apply DDL."""
    create_database_if_not_exists()
    apply_schema(sql_file_path)
    logger.info("Schema initialization complete.")
