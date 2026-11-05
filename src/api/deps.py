"""
Shared FastAPI dependencies: a read-only SQLite connection per request, optional API-key auth,
pagination bounds and row helpers.
"""
import hmac
import json
import sqlite3
from typing import Any, Dict, Iterator, List, Optional

from fastapi import Depends, Header, HTTPException, Query

from settings import settings


def get_db() -> Iterator[sqlite3.Connection]:
    """Yields a query-only connection to portfolio.db (the scheduler is the only writer)."""
    conn = sqlite3.connect(f"file:{settings.PORTFOLIO_DB_PATH}?mode=ro", uri=True, timeout=settings.DB_BUSY_TIMEOUT_MS / 1000)
    conn.row_factory = sqlite3.Row
    conn.execute(f"PRAGMA busy_timeout={settings.DB_BUSY_TIMEOUT_MS}")
    conn.execute("PRAGMA query_only=ON")
    try:
        yield conn
    finally:
        conn.close()


def require_api_key(x_api_key: Optional[str] = Header(default=None)) -> None:
    """Enforces X-API-Key only when API_KEY is configured; empty means a public read-only API."""
    if not settings.API_KEY:
        return
    if not x_api_key or not hmac.compare_digest(x_api_key, settings.API_KEY):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


class Page:
    """limit/offset query parameters bounded by settings.API_MAX_PAGE_SIZE."""

    def __init__(
        self,
        limit: int = Query(settings.API_DEFAULT_PAGE_SIZE, ge=1, le=settings.API_MAX_PAGE_SIZE),
        offset: int = Query(0, ge=0),
    ):
        self.limit, self.offset = limit, offset


def rows(cur_rows) -> List[Dict[str, Any]]:
    """sqlite3.Row list to plain dicts."""
    return [dict(r) for r in cur_rows]


def parse_json(value: Optional[str]) -> Any:
    """Decodes a *_json column, returning None for empty or invalid JSON."""
    if not value:
        return None
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return None


def ensure_agent(conn: sqlite3.Connection, agent_id: str) -> None:
    """404 unless the agent exists."""
    if conn.execute("SELECT 1 FROM agents WHERE id = ?", (agent_id,)).fetchone() is None:
        raise HTTPException(status_code=404, detail=f"Unknown agent '{agent_id}'")


AuthDep = Depends(require_api_key)
