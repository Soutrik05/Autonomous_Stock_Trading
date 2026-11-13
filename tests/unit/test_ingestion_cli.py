"""
Unit tests for ingestion/cli.py pipeline_runs wiring, using an in-memory db and a fake clock
(no live network, no real client calls on a holiday).
See Plan_v3 §1.4.
"""

import sqlite3
from datetime import datetime
from pathlib import Path

from core.clock import FakeClock
from ingestion.cli import run
from ingestion.sync_macro import ensure_schema as ensure_macro_schema
from ingestion.sync_ohlcv import ensure_schema as ensure_ohlcv_schema

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "db" / "schema.sql"


def make_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    return conn


class FakeClient:
    def __init__(self):
        self.calls = 0

    def get_daily_candles(self, *a, **kw):
        self.calls += 1
        return []

    def get_india_vix(self):
        self.calls += 1
        return {"last_price": 13.5}


def test_cli_skips_a_weekend_holiday_without_calling_the_client():
    conn = make_db()
    saturday = datetime(2026, 10, 17, 20, 0, 0)  # a Saturday
    clock = FakeClock(saturday)
    client = FakeClient()

    status = run(clock=clock, client=client, portfolio_conn=conn)

    assert status == "SKIPPED_HOLIDAY"
    assert client.calls == 0
    row = conn.execute("SELECT status FROM pipeline_runs WHERE job='ingestion' AND run_date='2026-10-17'").fetchone()
    assert row["status"] == "SKIPPED_HOLIDAY"


def test_cli_skips_a_seeded_national_holiday():
    conn = make_db()
    conn.execute(
        "INSERT INTO market_calendar (trade_date, is_trading_day, session_type, note) "
        "VALUES ('2026-10-20', 0, 'CLOSED', 'Test holiday')"
    )
    clock = FakeClock(datetime(2026, 10, 20, 20, 0, 0))  # a Tuesday, seeded as closed
    client = FakeClient()

    status = run(clock=clock, client=client, portfolio_conn=conn)

    assert status == "SKIPPED_HOLIDAY"
    assert client.calls == 0


def test_cli_runs_and_succeeds_on_a_trading_day():
    conn = make_db()
    conn.execute(
        "INSERT INTO symbols (ticker, instrument_key, isin, company_name, sector, is_active) "
        "VALUES ('TATAMOTORS', 'NSE_EQ|KEY1', 'ISIN0000000', 'Test Co', 'Test Sector', 1)"
    )
    monday = datetime(2026, 10, 19, 20, 0, 0)
    clock = FakeClock(monday)
    client = FakeClient()
    ohlcv_conn = sqlite3.connect(":memory:")
    ohlcv_conn.row_factory = sqlite3.Row
    ensure_ohlcv_schema(ohlcv_conn)
    macro_conn = sqlite3.connect(":memory:")
    macro_conn.row_factory = sqlite3.Row
    ensure_macro_schema(macro_conn)

    status = run(clock=clock, client=client, portfolio_conn=conn, ohlcv_conn=ohlcv_conn, macro_conn=macro_conn)

    assert status == "SUCCESS"
    row = conn.execute(
        "SELECT status, started_at, finished_at FROM pipeline_runs WHERE job='ingestion' AND run_date='2026-10-19'"
    ).fetchone()
    assert row["status"] == "SUCCESS"
    assert row["started_at"] is not None
    assert row["finished_at"] is not None


def test_cli_runs_with_explicit_date_str_records_macro_for_that_date():
    conn = make_db()
    conn.execute(
        "INSERT INTO symbols (ticker, instrument_key, isin, company_name, sector, is_active) "
        "VALUES ('TATAMOTORS', 'NSE_EQ|KEY1', 'ISIN0000000', 'Test Co', 'Test Sector', 1)"
    )
    # Clock says Monday Oct 19, but we pass date_str for Friday Oct 16
    clock = FakeClock(datetime(2026, 10, 19, 20, 0, 0))
    client = FakeClient()
    ohlcv_conn = sqlite3.connect(":memory:")
    ohlcv_conn.row_factory = sqlite3.Row
    ensure_ohlcv_schema(ohlcv_conn)
    macro_conn = sqlite3.connect(":memory:")
    macro_conn.row_factory = sqlite3.Row
    ensure_macro_schema(macro_conn)

    status = run(
        clock=clock,
        client=client,
        date_str="2026-10-16",
        portfolio_conn=conn,
        ohlcv_conn=ohlcv_conn,
        macro_conn=macro_conn,
    )
    assert status == "SUCCESS"
    macro_row = macro_conn.execute(
        "SELECT trade_date, india_vix FROM macro_daily WHERE trade_date = '2026-10-16'"
    ).fetchone()
    assert macro_row is not None
    assert macro_row["trade_date"] == "2026-10-16"
    assert macro_row["india_vix"] == 13.5
