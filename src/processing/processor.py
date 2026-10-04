"""
Data Processing (Deduplication & Skill Extraction)
Cleans raw validated job records, deduplicates across sources/batches,
and extracts tech skills from unstructured text descriptions using regex pattern matching.
"""

import re
import html
import logging
from datetime import datetime
from typing import Dict, List, Set, Tuple, Any, Optional

from config.skills_taxonomy import SKILLS_TAXONOMY

logger = logging.getLogger("processing.processor")

# Precompile regex patterns for performance
COMPILED_SKILL_PATTERNS = {
    skill: (re.compile(meta["pattern"], re.IGNORECASE), meta["category"])
    for skill, meta in SKILLS_TAXONOMY.items()
}


def clean_html_text(raw_text: Optional[str]) -> str:
    """Removes HTML tags and unescapes entities while normalizing whitespace."""
    if not raw_text:
        return ""
    # Strip real HTML tags first (e.g. <p>, <br>, <strong>)
    text = re.sub(r"<[^>]+>", " ", raw_text)
    # Unescape HTML entities (e.g. &amp; -> &, &lt; -> <)
    text = html.unescape(text)
    # Normalize multiple whitespace characters
    return " ".join(text.split()).strip()


def extract_skills_from_text(text: str) -> List[Dict[str, str]]:
    """
    Scans free-text using precompiled regex boundaries to detect mentioned skills.
    
    Returns:
        List of dicts: [{"skill": "python", "category": "language"}, ...]
    """
    if not text:
        return []

    matched_skills = []
    # Search for all registered skills
    for skill_name, (pattern, category) in COMPILED_SKILL_PATTERNS.items():
        if pattern.search(text):
            matched_skills.append({
                "skill": skill_name,
                "category": category
            })

    return matched_skills


def parse_location(location_data: Any) -> Dict[str, Optional[str]]:
    """Extracts structured city, state, country from Adzuna location object."""
    loc_dict = {
        "location_raw": None,
        "city": None,
        "state": None,
        "country": None
    }

    if isinstance(location_data, dict):
        loc_dict["location_raw"] = location_data.get("display_name")
        area_list = location_data.get("area", [])
        if isinstance(area_list, list) and len(area_list) > 0:
            loc_dict["country"] = area_list[0] if len(area_list) > 0 else None
            loc_dict["state"] = area_list[1] if len(area_list) > 1 else None
            loc_dict["city"] = area_list[-1] if len(area_list) > 2 else None
    elif isinstance(location_data, str):
        loc_dict["location_raw"] = location_data

    return loc_dict


def process_record(raw_record: Dict[str, Any]) -> Dict[str, Any]:
    """
    Cleans, normalizes, and enriches a single validated job posting record.
    """
    source_id = str(raw_record.get("id")).strip()
    title = clean_html_text(raw_record.get("title"))
    
    company_obj = raw_record.get("company", {})
    company_name = clean_html_text(company_obj.get("display_name") if isinstance(company_obj, dict) else str(company_obj))

    loc_info = parse_location(raw_record.get("location"))

    raw_created = raw_record.get("created", "")
    try:
        # Standardize timestamp to YYYY-MM-DD HH:MM:SS
        dt = datetime.fromisoformat(raw_created.replace("Z", "+00:00"))
        posted_date = dt.strftime("%Y-%m-%d %H:%M:%S")
        date_id = dt.strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        posted_date = raw_created
        date_id = raw_created[:10] if len(raw_created) >= 10 else None

    raw_description = raw_record.get("description", "")
    description = clean_html_text(raw_description)

    # Search for skills across both title and full description
    combined_search_text = f"{title} {description}"
    extracted_skills_meta = extract_skills_from_text(combined_search_text)
    skill_names = [s["skill"] for s in extracted_skills_meta]

    return {
        "source_id": source_id,
        "title": title,
        "company": company_name,
        "location_raw": loc_info["location_raw"],
        "city": loc_info["city"],
        "state": loc_info["state"],
        "country": loc_info["country"],
        "posted_date": posted_date,
        "date_id": date_id,
        "salary_min": raw_record.get("salary_min"),
        "salary_max": raw_record.get("salary_max"),
        "description": description,
        "skills": skill_names,
        "skills_metadata": extracted_skills_meta
    }


def deduplicate_and_process_records(
    valid_records: List[Dict[str, Any]],
    existing_source_ids: Optional[Set[str]] = None
) -> Tuple[List[Dict[str, Any]], int]:
    """
    Deduplicates records within the current batch and against known existing source IDs.
    Extracts skills and formats clean records.
    
    Returns:
        (processed_records, duplicate_count)
    """
    seen_ids = set(existing_source_ids or [])
    processed_records = []
    duplicate_count = 0

    for rec in valid_records:
        source_id = str(rec.get("id")).strip()
        if source_id in seen_ids:
            duplicate_count += 1
            logger.debug("Skipping duplicate posting source_id=%s", source_id)
            continue

        seen_ids.add(source_id)
        processed = process_record(rec)
        processed_records.append(processed)

    logger.info(
        "Processing complete: %d records processed, %d duplicates skipped",
        len(processed_records), duplicate_count
    )
    return processed_records, duplicate_count


if __name__ == "__main__":
    import argparse
    import sys
    from pathlib import Path
    from src.validation.validator import validate_raw_postings

    parser = argparse.ArgumentParser(description="Process validated job postings and extract skills.")
    parser.add_argument("--file", type=str, required=True, help="Path to raw JSON file")
    args = parser.parse_args()

    try:
        report = validate_raw_postings(Path(args.file))
        processed, dupes = deduplicate_and_process_records(report["valid_records"])
        print("\n=== Processing & Skill Extraction Summary ===")
        print(f"Validated Input : {len(report['valid_records'])}")
        print(f"Duplicates      : {dupes}")
        print(f"Final Processed : {len(processed)}")
        print("\nSample Extracted Skills:")
        for p in processed[:5]:
            print(f"- [{p['source_id']}] {p['title']} @ {p['company']}")
            print(f"  Skills: {', '.join(p['skills']) if p['skills'] else '(None detected)'}")
            print(f"  Location: {p['city'] or p['location_raw']}, {p['country']}")
        print("==============================================")
    except Exception as exc:
        print(f"[ERROR] Processing failed: {exc}", file=sys.stderr)
        sys.exit(1)
