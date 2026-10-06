"""
Operational Alerting & Notification Dispatcher
──────────────────────────────────────────────
Dispatches structured alerts across multiple channels:
  1. Console / Rich Terminal (Always active; formatted ASCII table & status cards)
  2. Slack Webhook (Configured via SLACK_WEBHOOK_URL)
  3. Discord Webhook (Configured via DISCORD_WEBHOOK_URL)
  4. PostgreSQL persistence (Logged to monitoring.pipeline_run_alerts)
"""

import sys
import json
import logging
from typing import List, Optional, Dict, Any, Tuple
import requests

from config.settings import SLACK_WEBHOOK_URL, DISCORD_WEBHOOK_URL
from src.utils.db_connector import get_psycopg2_connection
from src.monitoring.quality_checks import CheckResult

logger = logging.getLogger("monitoring.alerter")


# ── Severity styling ──────────────────────────────────────────────────────────
SEVERITY_COLORS = {
    "INFO":     {"hex": "#2eb886", "emoji": "✅", "prefix": "[INFO]"},
    "WARN":     {"hex": "#e0a800", "emoji": "⚠️", "prefix": "[WARN]"},
    "CRITICAL": {"hex": "#dc3545", "emoji": "🚨", "prefix": "[CRITICAL]"},
}


def log_alert_to_db(
    run_id: Optional[str],
    alert_type: str,
    severity: str,
    channel: str,
    message: str
) -> None:
    """Logs the dispatched alert into monitoring.pipeline_run_alerts for historical audit."""
    sql = """
        INSERT INTO monitoring.pipeline_run_alerts (
            run_id, alert_type, severity, channel, message
        ) VALUES (%s, %s, %s, %s, %s);
    """
    conn = get_psycopg2_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql, (run_id, alert_type, severity, channel, message))
        conn.commit()
        cur.close()
    except Exception as exc:
        conn.rollback()
        logger.warning("Could not persist alert to database: %s", exc)
    finally:
        conn.close()


def send_slack_notification(message: str, severity: str, title: str = "Skills Demand Platform Alert") -> bool:
    """Sends a rich formatted message to Slack via incoming webhook if configured."""
    if not SLACK_WEBHOOK_URL:
        return False

    color = SEVERITY_COLORS.get(severity, {}).get("hex", "#808080")
    emoji = SEVERITY_COLORS.get(severity, {}).get("emoji", "📢")

    payload = {
        "text": f"{emoji} *{title}* - {severity}",
        "attachments": [
            {
                "color": color,
                "title": title,
                "text": message,
                "mrkdwn_in": ["text"]
            }
        ]
    }

    try:
        resp = requests.post(SLACK_WEBHOOK_URL, json=payload, timeout=5)
        return resp.status_code == 200
    except Exception as exc:
        logger.warning("Failed to send Slack alert: %s", exc)
        return False


def send_discord_notification(message: str, severity: str, title: str = "Skills Demand Platform Alert") -> bool:
    """Sends an embed card to Discord via webhook if configured."""
    if not DISCORD_WEBHOOK_URL:
        return False

    color_int = int(SEVERITY_COLORS.get(severity, {}).get("hex", "#808080").lstrip("#"), 16)
    emoji = SEVERITY_COLORS.get(severity, {}).get("emoji", "📢")

    payload = {
        "embeds": [
            {
                "title": f"{emoji} {title} [{severity}]",
                "description": f"```\n{message[:1900]}\n```",
                "color": color_int,
            }
        ]
    }

    try:
        resp = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=5)
        return resp.status_code in (200, 204)
    except Exception as exc:
        logger.warning("Failed to send Discord alert: %s", exc)
        return False


def print_console_dashboard(
    title: str,
    severity: str,
    check_results: List[CheckResult],
    run_id: Optional[str] = None,
    extra_details: Optional[str] = None
) -> None:
    """Renders a clean, high-visibility terminal card for human operators."""
    ascii_badge = {
        "INFO": "[OK]",
        "WARN": "[!]",
        "CRITICAL": "[X]"
    }.get(severity, "[*]")
    sep = "=" * 75

    print(f"\n{sep}")
    print(f"  {ascii_badge} {title.upper()} [{severity}]")
    if run_id:
        print(f"  Run ID: {run_id}")
    print(f"{sep}")

    print(f"  {'STATUS':<8} | {'CATEGORY':<16} | {'CHECK NAME':<32} | {'DETAILS'}")
    print("  " + "-" * 71)

    for c in check_results:
        status_badge = f"[{c.status}]"
        print(f"  {status_badge:<8} | {c.category:<16} | {c.name:<32} | {c.details}")

    if extra_details:
        print("  " + "-" * 71)
        print(f"  Notes: {extra_details}")

    print(f"{sep}\n")



def format_quality_digest(
    results: List[CheckResult],
    run_id: Optional[str] = None,
    duration_sec: Optional[float] = None
) -> Tuple[str, str, str]:
    """
    Computes overall severity and produces a markdown summary digest.
    Returns: (alert_type, severity, message_string)
    """
    total = len(results)
    passed = sum(1 for r in results if r.status == "PASS")
    warned = sum(1 for r in results if r.status == "WARN")
    failed = sum(1 for r in results if r.status == "FAIL")

    if failed > 0:
        severity = "CRITICAL"
        alert_type = "QUALITY_FAILURE"
    elif warned > 0:
        severity = "WARN"
        alert_type = "QUALITY_WARNING"
    else:
        severity = "INFO"
        alert_type = "QUALITY_PASSED"

    lines = [
        f"Pipeline Run Quality Digest",
        f"Run ID: {run_id or 'N/A'}",
        f"Results: {passed}/{total} Passed | {warned} Warnings | {failed} Failures",
    ]
    if duration_sec is not None:
        lines.append(f"Execution Time: {duration_sec:.1f}s")

    lines.append("\nCheck Breakdown:")
    for r in results:
        lines.append(f"• [{r.status}] {r.name}: {r.details}")

    message = "\n".join(lines)
    return alert_type, severity, message


def dispatch_alert(
    alert_type: str,
    severity: str,
    message: str,
    check_results: Optional[List[CheckResult]] = None,
    run_id: Optional[str] = None,
    title: str = "Skills Demand Platform Alert"
) -> List[str]:
    """
    Dispatches alert across Console, DB, Slack, and Discord.
    Returns the list of channels successfully alerted.
    """
    dispatched_channels = []

    # 1. Console render
    if check_results:
        print_console_dashboard(title=title, severity=severity, check_results=check_results, run_id=run_id)
    else:
        print(f"\n[{severity}] {title}: {message}\n")
    dispatched_channels.append("CONSOLE")

    # 2. Database audit record
    log_alert_to_db(
        run_id=run_id,
        alert_type=alert_type,
        severity=severity,
        channel="CONSOLE",
        message=message
    )

    # 3. Slack Webhook (if configured)
    if send_slack_notification(message=message, severity=severity, title=title):
        dispatched_channels.append("SLACK")
        log_alert_to_db(run_id, alert_type, severity, "SLACK", message)

    # 4. Discord Webhook (if configured)
    if send_discord_notification(message=message, severity=severity, title=title):
        dispatched_channels.append("DISCORD")
        log_alert_to_db(run_id, alert_type, severity, "DISCORD", message)

    return dispatched_channels
