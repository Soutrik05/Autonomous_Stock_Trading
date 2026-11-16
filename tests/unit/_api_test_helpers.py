"""
Shared helpers for the API test modules (tests/unit/test_api_*.py). The API's read-only
dependency (api.deps.get_ro_conn) opens its SQLite connection with the `file:...?mode=ro` URI,
which requires a real on-disk file -- tests/conftest.py's usual make_portfolio_db() uses
`:memory:`, which mode=ro cannot attach to from a second connection. These helpers build a real
temp file instead, so the tests exercise the exact same read-only code path the live app uses.
"""

import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from api.deps import get_ro_conn, portfolio_conn
from api.main import app

_DB_DIR = Path(__file__).resolve().parents[2] / "db"
_SCHEMA_PATH = _DB_DIR / "schema.sql"
_MIGRATIONS_DIR = _DB_DIR / "migrations"

NOW = "2026-11-06T20:00:00+05:30"


def build_file_db(path: str) -> None:
    """Writes a fresh portfolio schema (schema.sql + every migration after 0001) to `path`."""
    conn = sqlite3.connect(path, isolation_level=None)
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(_SCHEMA_PATH.read_text(encoding="utf-8"))
    for migration_path in sorted(_MIGRATIONS_DIR.glob("*.sql")):
        if migration_path.name.startswith("0001_"):
            continue
        conn.executescript(migration_path.read_text(encoding="utf-8"))
    conn.close()


def seed_agent(path: str, agent_id: str, name: str, philosophy: str, kind: str = "LLM") -> None:
    conn = sqlite3.connect(path, isolation_level=None)
    conn.execute(
        "INSERT INTO agents (id, name, philosophy, kind, starting_cash_paise, cash_paise, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, 100000000, 100000000, ?, ?)",
        (agent_id, name, philosophy, kind, NOW, NOW),
    )
    conn.close()


def seed_symbol(path: str, ticker: str, company_name: str, sector: str) -> None:
    conn = sqlite3.connect(path, isolation_level=None)
    conn.execute(
        "INSERT INTO symbols (ticker, instrument_key, isin, company_name, sector, is_active) "
        "VALUES (?, ?, ?, ?, ?, 1)",
        (ticker, f"NSE_EQ|{ticker}", f"INE{ticker[:6]}01", company_name, sector),
    )
    conn.close()


def make_client(db_path: str) -> TestClient:
    """A TestClient whose portfolio_conn dependency is overridden to read `db_path` (mode=ro)
    instead of the real settings.PORTFOLIO_DB_PATH. Call clear_overrides() in a test's teardown."""

    def _override():
        conn = get_ro_conn(db_path)
        try:
            yield conn
        finally:
            conn.close()

    app.dependency_overrides[portfolio_conn] = _override
    return TestClient(app)


def clear_overrides() -> None:
    app.dependency_overrides.clear()
