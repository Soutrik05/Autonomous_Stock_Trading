"""
Shared FastAPI dependencies: a strictly read-only connection to the live portfolio ledger, and
small helpers (IST formatting, activity-log severity mapping) used across route handlers.
Evidence isolation: this module only ever opens settings.PORTFOLIO_DB_PATH. The backtest router
is the only place storage/backtest/ is opened (src/api/routes/backtest.py).
See Plan_v3 Part IV, docs/backend_implementation_guide_week5.md §1.1-1.2.
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from zoneinfo import ZoneInfo

from fastapi import HTTPException

from core.config import settings

IST = ZoneInfo(settings.TIMEZONE)


def get_ro_conn(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Opens a read-only SQLite connection to the live portfolio ledger (or db_path, for tests).
    Never used to open anything under storage/backtest/ -- that isolation is enforced by only
    ever calling this with no argument (defaulting to settings.PORTFOLIO_DB_PATH) from the live
    routes, and is proven by tests/unit/test_api_isolation.py."""
    path = db_path or settings.PORTFOLIO_DB_PATH
    resolved = Path(path).resolve()
    conn = sqlite3.connect(
        f"file:{resolved.as_posix()}?mode=ro", uri=True, timeout=10, check_same_thread=False
    )
    conn.row_factory = sqlite3.Row
    return conn


def portfolio_conn():
    """FastAPI dependency: yields a read-only connection to the live portfolio ledger, closed
    after the request. Overridden in tests to point at a temp database."""
    conn = get_ro_conn()
    try:
        yield conn
    finally:
        conn.close()


def require_agent(conn: sqlite3.Connection, agent_id: str) -> None:
    """Raises 404 for an agent_id not present in `agents`. Shared by every /api/agents/{id}/...
    route so "unknown agent" behaves identically everywhere."""
    row = conn.execute("SELECT 1 FROM agents WHERE id = ?", (agent_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Unknown agent '{agent_id}'.")


def to_ist_iso(value: Optional[str]) -> Optional[str]:
    """Normalizes a stored timestamp string to an IST ISO string. Values written by the system
    are already IST ISO text (via the injected Clock); this only guards against a bare date
    string (e.g. positions.entry_date, 'YYYY-MM-DD') by returning it unchanged -- a date has no
    time-of-day to attach, so it is not a timestamp to convert."""
    if value is None:
        return None
    if "T" not in value:
        return value  # a plain date string ('YYYY-MM-DD'); nothing to convert
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return value
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=IST)
    return dt.isoformat()


def duration_seconds(started_at: Optional[str], finished_at: Optional[str]) -> Optional[int]:
    """Whole-second duration between two IST ISO timestamps, or None if either is missing/still
    running."""
    if not started_at or not finished_at:
        return None
    try:
        start = datetime.fromisoformat(started_at)
        end = datetime.fromisoformat(finished_at)
    except ValueError:
        return None
    return max(0, int((end - start).total_seconds()))


# event_type -> severity, for activity_log rows that carry no explicit severity of their own.
# A PIPELINE_FAILED row's own metadata_json.severity (CRITICAL/WARNING, set by
# notifications/alerts.py::record_pipeline_failure) always takes precedence over this map.
_EVENT_TYPE_SEVERITY: dict[str, str] = {
    "PIPELINE_FAILED": "ERROR",
    "VALIDATION_FAILED": "ERROR",
    "LOCKED_CIRCUIT": "ERROR",
    "CAP_BREACH": "WARNING",
    "CRASH_CANCELLED": "WARNING",
    "STOP_HIT": "WARNING",
    "CORP_ACTION_FROZEN": "WARNING",
    "ORDER_EXPIRED": "INFO",
    "BUY_FILLED": "SUCCESS",
    "SELL_FILLED": "SUCCESS",
    "TARGET_REACHED": "SUCCESS",
    "ADJUSTED": "SUCCESS",
    "HEURISTIC_CREATED": "SUCCESS",
    "ORDER_SUBMITTED": "INFO",
    "WATCHLIST_REFRESH": "INFO",
    "FUNNEL_COUNTS": "INFO",
    "HEURISTIC_STATUS_CHANGED": "INFO",
    "DAILY_SETTLEMENT": "SUCCESS",
}


def severity_for_event(event_type: str, metadata_json: Optional[str]) -> str:
    """Derives a severity for an activity_log row. A CRITICAL severity recorded in the row's own
    metadata (PIPELINE_FAILED rows from notifications/alerts.py) is remapped to ERROR -- the API
    only ever emits SUCCESS|INFO|WARNING|ERROR, a smaller, stable set for the dashboard to
    switch on. Falls back to the static event_type map, then to INFO for an unknown event_type."""
    if metadata_json:
        try:
            meta = json.loads(metadata_json)
            own_severity = meta.get("severity") if isinstance(meta, dict) else None
            if own_severity == "CRITICAL":
                return "ERROR"
            if own_severity in ("SUCCESS", "INFO", "WARNING", "ERROR"):
                return own_severity
        except (json.JSONDecodeError, TypeError):
            pass
    return _EVENT_TYPE_SEVERITY.get(event_type, "INFO")


def parse_metadata(metadata_json: Optional[str]) -> Optional[dict[str, Any]]:
    if not metadata_json:
        return None
    try:
        return json.loads(metadata_json)
    except (json.JSONDecodeError, TypeError):
        return None
