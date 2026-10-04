"""
Adzuna Job Postings Extractor
Calls the Adzuna REST API and lands the raw, untouched JSON response on disk.
"""

import os
import sys
import json
import logging
import argparse
from datetime import datetime
from pathlib import Path
import requests

from config.settings import ADZUNA_APP_ID, ADZUNA_APP_KEY, ADZUNA_COUNTRY, RAW_DATA_DIR

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("ingestion.adzuna")


def extract_postings_from_adzuna(
    query: str = "data engineer",
    country: str = ADZUNA_COUNTRY,
    page: int = 1,
    results_per_page: int = 20,
    output_dir: Path = RAW_DATA_DIR
) -> Path:
    """
    Fetch job postings from the Adzuna API and land raw JSON directly to disk.
    
    Args:
        query: Search term (e.g., 'data engineer', 'analytics engineer')
        country: Country code ('gb', 'us', etc.)
        page: Page number (1-indexed)
        results_per_page: Number of postings per page (max typically 50)
        output_dir: Directory where raw JSON is saved
        
    Returns:
        Path to the saved raw JSON file
    """
    if not ADZUNA_APP_ID or not ADZUNA_APP_KEY:
        raise ValueError(
            "Missing Adzuna credentials. Please ensure ADZUNA_APP_ID and ADZUNA_APP_KEY "
            "are set in your .env file."
        )

    base_url = f"https://api.adzuna.com/v1/api/jobs/{country}/search/{page}"
    params = {
        "app_id": ADZUNA_APP_ID,
        "app_key": ADZUNA_APP_KEY,
        "what": query,
        "results_per_page": results_per_page,
        "content-type": "application/json"
    }

    logger.info("Initiating request to Adzuna API for query='%s' (country=%s, page=%d)", query, country, page)

    try:
        response = requests.get(base_url, params=params, timeout=15)
        response.raise_for_status()
    except requests.exceptions.HTTPError as http_err:
        logger.error("HTTP error occurred while calling Adzuna API: %s", http_err)
        if response.status_code in (401, 403):
            logger.error("Authentication failed. Check ADZUNA_APP_ID and ADZUNA_APP_KEY in .env.")
        elif response.status_code == 429:
            logger.error("Rate limit exceeded on Adzuna API. Try again later.")
        raise
    except requests.exceptions.RequestException as req_err:
        logger.error("Network or connection error while contacting Adzuna API: %s", req_err)
        raise

    raw_data = response.json()
    total_matches = raw_data.get("count", 0)
    returned_count = len(raw_data.get("results", []))
    logger.info("Successfully fetched %d postings (total available: %d)", returned_count, total_matches)

    # Format output file name: YYYY-MM-DD_query.json
    pull_date = datetime.now().strftime("%Y-%m-%d")
    sanitized_query = query.lower().replace(" ", "-")
    output_filename = f"{pull_date}_{sanitized_query}.json"
    output_path = output_dir / output_filename

    # Save untouched raw JSON
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(raw_data, f, ensure_ascii=False, indent=2)

    logger.info("Landed untouched raw response to: %s", output_path)
    return output_path


def main():
    parser = argparse.ArgumentParser(description="Extract job postings from Adzuna API into raw storage.")
    parser.add_argument("--query", type=str, default="data engineer", help="Job query keyword (default: 'data engineer')")
    parser.add_argument("--country", type=str, default=ADZUNA_COUNTRY, help="Country code (default: 'gb')")
    parser.add_argument("--page", type=int, default=1, help="Page number (default: 1)")
    parser.add_argument("--results", type=int, default=20, help="Results count (default: 20)")
    
    args = parser.parse_args()
    try:
        saved_file = extract_postings_from_adzuna(
            query=args.query,
            country=args.country,
            page=args.page,
            results_per_page=args.results
        )
        print(f"\n[SUCCESS] Ingestion Complete. Raw file saved at: {saved_file}")
    except Exception as e:
        print(f"\n[ERROR] Ingestion failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
