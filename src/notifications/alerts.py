"""
Pipeline failure alerting and health monitoring.
Logs structured alerts to activity_log and computes consecutive failure metrics.
"""
import json
import logging
import sqlite3
from typing import Dict, Optional

from core.clock import Clock, SystemClock

logger = logging.getLogger("notifications.alerts")


def count_consecutive_failures(conn: sqlite3.Connection, job_name: str) -> int:
    """Returns the number of consecutive FAILED runs for `job_name` ordered by run_date DESC."""
    rows = conn.execute(
        """
        SELECT status FROM pipeline_runs
        WHERE job = ?
        ORDER BY run_date DESC
        LIMIT 10
        """,
        (job_name,),
    ).fetchall()

    consecutive = 0
    for r in rows:
        status = r["status"] if isinstance(r, sqlite3.Row) else r[0]
        if status == "FAILED":
            consecutive += 1
        elif status in ("SUCCESS", "SKIPPED_HOLIDAY"):
            break
    return consecutive


def record_pipeline_failure(
    conn: sqlite3.Connection,
    job_name: str,
    run_date: str,
    error_detail: str,
    clock: Optional[Clock] = None,
) -> Dict[str, any]:
    """
    Records a PIPELINE_FAILED event into activity_log and determines severity based on
    consecutive failures.
    """
    clock = clock or SystemClock()
    now_iso = clock.now_iso()

    consecutive = count_consecutive_failures(conn, job_name)
    severity = "CRITICAL" if consecutive >= 2 else "WARNING"

    description = (
        f"[{severity}] Pipeline job '{job_name}' failed for {run_date} "
        f"({consecutive} consecutive failure(s)). Detail: {error_detail}"
    )

    metadata = {
        "job_name": job_name,
        "run_date": run_date,
        "consecutive_failures": consecutive,
        "severity": severity,
        "error_detail": error_detail[:500],
    }

    try:
        conn.execute(
            """
            INSERT INTO activity_log (agent_id, event_type, ticker, description, metadata_json, created_at)
            VALUES (NULL, 'PIPELINE_FAILED', NULL, ?, ?, ?)
            """,
            (description, json.dumps(metadata), now_iso),
        )
    except sqlite3.OperationalError as exc:
        logger.error("Could not write to activity_log: %s", exc)

    if severity == "CRITICAL":
        logger.critical("=" * 70)
        logger.critical("CRITICAL ALERT: %s", description)
        logger.critical("Immediate developer intervention required.")
        logger.critical("=" * 70)
    else:
        logger.warning(description)

    return {
        "job_name": job_name,
        "run_date": run_date,
        "consecutive_failures": consecutive,
        "severity": severity,
        "description": description,
    }
