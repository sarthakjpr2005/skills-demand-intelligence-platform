"""
Job Postings Data Validator
Performs deterministic schema and rule-based validation on raw job posting records.
Valid records pass through; broken records are quarantined with diagnostic failure reasons.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional

from config.settings import BAD_RECORDS_DIR

logger = logging.getLogger("validation.validator")


class JobRecordValidator:
    """
    Validates job records against non-negotiable operational requirements.
    
    Rules:
    1. source_id ('id'): Must be present, non-null, non-empty.
    2. title ('title'): Must be present, non-null, non-empty text.
    3. company ('company.display_name'): Company entity and name must be present.
    4. posted_date ('created'): Must be present and valid ISO-8601 formatted datetime.
    """

    @staticmethod
    def validate_record(record: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validates an individual record.
        Returns:
            Tuple of (is_valid: bool, failure_reasons: List[str])
        """
        reasons = []

        # Rule 1: source_id ('id' in Adzuna)
        source_id = record.get("id")
        if source_id is None or str(source_id).strip() == "":
            reasons.append("Missing or empty 'id' (source_id)")

        # Rule 2: title
        title = record.get("title")
        if title is None or not isinstance(title, str) or title.strip() == "":
            reasons.append("Missing or empty 'title'")

        # Rule 3: company
        company = record.get("company")
        if company is None or not isinstance(company, dict):
            reasons.append("Missing 'company' object")
        else:
            display_name = company.get("display_name")
            if display_name is None or str(display_name).strip() == "":
                reasons.append("Missing or empty 'company.display_name'")

        # Rule 4: posted_date ('created' in Adzuna)
        created = record.get("created")
        if not created or not isinstance(created, str) or created.strip() == "":
            reasons.append("Missing or empty 'created' timestamp")
        else:
            try:
                # Adzuna format typically: '2026-10-01T03:42:29Z'
                datetime.fromisoformat(created.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                reasons.append(f"Invalid date format for 'created': '{created}'")

        is_valid = len(reasons) == 0
        return is_valid, reasons

    @classmethod
    def validate_batch(
        cls,
        raw_records: List[Dict[str, Any]],
        batch_name: str = "batch"
    ) -> Dict[str, Any]:
        """
        Validates a list of raw records, quarantining invalid records.
        """
        valid_records = []
        bad_records = []
        failure_counts: Dict[str, int] = {}

        for rec in raw_records:
            is_valid, reasons = cls.validate_record(rec)
            if is_valid:
                valid_records.append(rec)
            else:
                bad_record_entry = {
                    "source_id": rec.get("id"),
                    "title": rec.get("title"),
                    "failure_reasons": reasons,
                    "quarantined_at": datetime.now().isoformat(),
                    "raw_record": rec
                }
                bad_records.append(bad_record_entry)
                for reason in reasons:
                    failure_counts[reason] = failure_counts.get(reason, 0) + 1

        total = len(raw_records)
        passed = len(valid_records)
        failed = len(bad_records)
        pass_rate = (passed / total * 100.0) if total > 0 else 0.0

        bad_records_file: Optional[Path] = None
        if bad_records:
            timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
            bad_records_file = BAD_RECORDS_DIR / f"{timestamp}_{batch_name}_bad_records.json"
            with open(bad_records_file, "w", encoding="utf-8") as f:
                json.dump(bad_records, f, ensure_ascii=False, indent=2)
            logger.warning(
                "Quarantined %d bad records to %s", failed, bad_records_file
            )

        report = {
            "total_records": total,
            "passed_records": passed,
            "failed_records": failed,
            "pass_rate_pct": round(pass_rate, 2),
            "failure_reasons_summary": failure_counts,
            "bad_records_file": str(bad_records_file) if bad_records_file else None,
            "valid_records": valid_records
        }

        logger.info(
            "Batch Validation Complete: Total=%d, Passed=%d (%.1f%%), Failed=%d",
            total, passed, pass_rate, failed
        )
        return report

    @classmethod
    def validate_file(cls, raw_json_path: Path) -> Dict[str, Any]:
        """
        Validates a raw landed JSON file directly.
        """
        path = Path(raw_json_path)
        if not path.exists():
            raise FileNotFoundError(f"Raw data file not found: {raw_json_path}")

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        records = data.get("results", []) if isinstance(data, dict) else data
        return cls.validate_batch(records, batch_name=path.stem)


def validate_raw_postings(raw_json_path: Path) -> Dict[str, Any]:
    """Top-level entrypoint for pipeline tasks."""
    return JobRecordValidator.validate_file(raw_json_path)


if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Validate raw job posting JSON files.")
    parser.add_argument("--file", type=str, required=True, help="Path to raw JSON file")
    args = parser.parse_args()

    try:
        report = validate_raw_postings(Path(args.file))
        print("\n=== Validation Report ===")
        print(f"Total Records : {report['total_records']}")
        print(f"Passed        : {report['passed_records']} ({report['pass_rate_pct']}%)")
        print(f"Failed        : {report['failed_records']}")
        if report["failure_reasons_summary"]:
            print(f"Reasons       : {report['failure_reasons_summary']}")
        if report["bad_records_file"]:
            print(f"Quarantined To: {report['bad_records_file']}")
        print("=========================")
    except Exception as exc:
        print(f"[ERROR] Validation failed: {exc}", file=sys.stderr)
        sys.exit(1)
