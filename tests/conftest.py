"""
Shared test fixtures: fake OHLCV data, FakeClock, FakeLLM and ReplayQuoteProvider.
See Plan_v3 §5 (Core Architectural Principles 5-6 interfaces).
"""
import sqlite3
from pathlib import Path

_DB_DIR = Path(__file__).resolve().parents[1] / "db"
_SCHEMA_PATH = _DB_DIR / "schema.sql"
_MIGRATIONS_DIR = _DB_DIR / "migrations"


def make_portfolio_db() -> sqlite3.Connection:
    """An in-memory portfolio.db with the baseline schema plus every migration after 0001
    (e.g. llm_calls.finish_reason/reasoning_tokens from migration 0002), for tests that need
    columns schema.sql alone does not have. isolation_level=None (autocommit) matches
    core.database.get_connection() exactly -- broker/engine.py's explicit BEGIN IMMEDIATE/COMMIT
    transactions require it; the default (implicit-transaction) mode would raise 'cannot start a
    transaction within a transaction'."""
    conn = sqlite3.connect(":memory:", isolation_level=None)
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA_PATH.read_text(encoding="utf-8"))
    for path in sorted(_MIGRATIONS_DIR.glob("*.sql")):
        if path.name.startswith("0001_"):
            continue  # already applied via schema.sql
        conn.executescript(path.read_text(encoding="utf-8"))
    return conn
