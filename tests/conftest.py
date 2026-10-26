"""
Shared test fixtures: fake OHLCV data, FakeClock, FakeLLM and ReplayQuoteProvider.
See Plan_v3 §5 (Core Architectural Principles 5-6 interfaces).
"""
import sqlite3
from datetime import datetime
from pathlib import Path

import pytest

from core.clock import FakeClock
from ingestion.sync_macro import ensure_schema as ensure_macro_schema
from ingestion.sync_ohlcv import ensure_schema as ensure_ohlcv_schema

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


@pytest.fixture
def portfolio_conn() -> sqlite3.Connection:
    """In-memory portfolio database fixture with complete schema and migrations."""
    conn = make_portfolio_db()
    try:
        yield conn
    finally:
        conn.close()


@pytest.fixture
def ohlcv_conn() -> sqlite3.Connection:
    """In-memory OHLCV database fixture with schema initialized."""
    conn = sqlite3.connect(":memory:", isolation_level=None)
    conn.row_factory = sqlite3.Row
    ensure_ohlcv_schema(conn)
    try:
        yield conn
    finally:
        conn.close()


@pytest.fixture
def macro_conn() -> sqlite3.Connection:
    """In-memory macro database fixture with schema initialized."""
    conn = sqlite3.connect(":memory:", isolation_level=None)
    conn.row_factory = sqlite3.Row
    ensure_macro_schema(conn)
    try:
        yield conn
    finally:
        conn.close()


@pytest.fixture
def seeded_portfolio(portfolio_conn: sqlite3.Connection) -> sqlite3.Connection:
    """Portfolio DB pre-seeded with baseline agents (simons, baseline-simons-rules),
    symbol TATAMOTORS, and market_calendar trading days for test execution."""
    now = "2026-10-19T20:00:00+05:30"
    portfolio_conn.execute(
        "INSERT INTO agents (id, name, philosophy, kind, starting_cash_paise, cash_paise, created_at, updated_at) "
        "VALUES ('simons', 'Jim Simons', 'Quant Momentum', 'LLM', 10000000, 10000000, ?, ?)",
        (now, now),
    )
    portfolio_conn.execute(
        "INSERT INTO agents (id, name, philosophy, kind, starting_cash_paise, cash_paise, created_at, updated_at) "
        "VALUES ('baseline-simons-rules', 'Baseline Simons Rules', 'Rules Momentum', 'BASELINE', 10000000, 10000000, ?, ?)",
        (now, now),
    )
    portfolio_conn.execute(
        "INSERT INTO symbols (ticker, instrument_key, isin, company_name, sector, is_active) "
        "VALUES ('TATAMOTORS', 'NSE_EQ|INE155A01022', 'INE155A01022', 'Tata Motors Ltd', 'Automobiles', 1)"
    )
    for dt in ("2026-10-19", "2026-10-20"):
        portfolio_conn.execute(
            "INSERT OR REPLACE INTO market_calendar (trade_date, is_trading_day, session_type, note) "
            "VALUES (?, 1, 'NORMAL', 'Trading Day')",
            (dt,),
        )
    return portfolio_conn


@pytest.fixture
def clock() -> FakeClock:
    """Fixed clock set to 2026-10-19 20:00:00 IST for nightly ingestion."""
    return FakeClock(datetime(2026, 10, 19, 20, 0, 0))


class MockUpstoxClient:
    """Mock Upstox client providing minimal daily candles and index quotes for batch pipeline tests."""

    def get_daily_candles(self, instrument_key: str, from_date: str, to_date: str):
        from datetime import date, timedelta
        end_date = date.fromisoformat("2026-10-19")
        candles = []
        # Trivial minimal OHLCV series: 210 sessions to satisfy MIN_SESSIONS_REQUIRED (200).
        # Base volume 100_000, last 5 days 150_000 so Stage 0 sma5 > adv20 volume rule passes.
        for i in range(210, 0, -1):
            d = end_date - timedelta(days=i)
            dt_str = f"{d.isoformat()}T09:15:00+05:30"
            vol = 150_000 if i <= 5 else 100_000
            candles.append([dt_str, 1000.0, 1010.0, 990.0, 1000.0, vol, 0])
        candles.append(["2026-10-19T15:30:00+05:30", 1000.0, 1010.0, 990.0, 1000.0, 150_000, 0])
        return candles

    def get_quotes(self, keys):
        return {
            "NSE_INDEX:Nifty 500": {"last_price": 22500.0, "symbol": "Nifty 500"},
            "NSE_INDEX:India VIX": {"last_price": 14.5, "symbol": "India VIX"},
        }

    def get_india_vix(self):
        return {"last_price": 14.5}


@pytest.fixture
def mock_upstox_client() -> MockUpstoxClient:
    """Mock Upstox client returning deterministic candle and quote fixtures."""
    return MockUpstoxClient()
