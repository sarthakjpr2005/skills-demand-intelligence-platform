"""
Centralized Configuration Loader
Loads environment variables from .env using python-dotenv.
Credentials should NEVER be hardcoded.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Base project directory
BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env from root directory if present
ENV_PATH = BASE_DIR / ".env"
load_dotenv(dotenv_path=ENV_PATH)

# Adzuna API Configuration
ADZUNA_APP_ID = os.getenv("ADZUNA_APP_ID", "")
ADZUNA_APP_KEY = os.getenv("ADZUNA_APP_KEY", "")
ADZUNA_COUNTRY = os.getenv("ADZUNA_COUNTRY", "gb").lower()

# Database Configuration
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "skills_platform")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

# Directory Paths
DATA_DIR = BASE_DIR / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
BAD_RECORDS_DIR = DATA_DIR / "bad_records"

# Ensure data directories exist
RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
BAD_RECORDS_DIR.mkdir(parents=True, exist_ok=True)

# Data Quality & Monitoring Configuration
FRESHNESS_MAX_HOURS = float(os.getenv("FRESHNESS_MAX_HOURS", "24.0"))
QUARANTINE_MAX_FAIL_RATE = float(os.getenv("QUARANTINE_MAX_FAIL_RATE", "0.15"))  # 15% max failure rate
ZERO_SKILLS_MAX_RATE = float(os.getenv("ZERO_SKILLS_MAX_RATE", "0.85"))          # 85% calibrated for short Adzuna API snippets
MIN_BATCH_VOLUME = int(os.getenv("MIN_BATCH_VOLUME", "5"))                      # Minimum expected per batch


# Webhook Alerting (Slack / Discord)
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")

