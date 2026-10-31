"""
Unit tests for ingestion/sync_ohlcv.py: corporate-action detection + freeze, idempotency,
STALE_DATA and LOCKED_CIRCUIT, using fake clients and in-memory databases (no live network).
See Plan_v3 §1.5.
"""
import sqlite3
from datetime import datetime
from pathlib import Path

from core.clock import FakeClock
from ingestion.sync_ohlcv import ensure_schema, sync_ohlcv, sync_ticker
from ingestion.upstox_client import UpstoxAPIError

PORTFOLIO_SCHEMA_PATH = Path(__file__).resolve().parents[2] / "db" / "schema.sql"
NOW = "2026-10-16T09:00:00+05:30"


def make_portfolio_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(PORTFOLIO_SCHEMA_PATH.read_text(encoding="utf-8"))
    return conn


def make_ohlcv_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_schema(conn)
    return conn


def insert_symbol(conn, ticker, instrument_key):
    conn.execute(
        "INSERT INTO symbols (ticker, instrument_key, isin, company_name, sector, is_active) "
        "VALUES (?, ?, 'ISIN0000000', 'Test Co', 'Test Sector', 1)",
        (ticker, instrument_key),
    )


def insert_agent(conn, agent_id="simons"):
    conn.execute(
        "INSERT INTO agents (id, name, philosophy, kind, starting_cash_paise, cash_paise, created_at, updated_at) "
        "VALUES (?, 'Test', 'Test', 'LLM', 10000000, 10000000, ?, ?)",
        (agent_id, NOW, NOW),
    )


def insert_open_position(conn, agent_id, ticker):
    conn.execute(
        "INSERT INTO positions (agent_id, ticker, sector, shares, avg_entry_price_paise, stop_paise, "
        "target_paise, last_price_paise, status, entry_date) "
        "VALUES (?, ?, 'Test Sector', 10, 20000, 18000, 24000, 20000, 'OPEN', '2026-10-01')",
        (agent_id, ticker),
    )


class FakeClient:
    def __init__(self, candles_by_key=None, raise_for_keys=None, intraday_by_key=None, raise_intraday_for_keys=None):
        self.candles_by_key = candles_by_key or {}
        self.raise_for_keys = raise_for_keys or set()
        self.intraday_by_key = intraday_by_key or {}
        self.raise_intraday_for_keys = raise_intraday_for_keys or set()
        self.calls = []
        self.intraday_calls = []

    def get_daily_candles(self, instrument_key, from_date, to_date):
        self.calls.append((instrument_key, from_date, to_date))
        if instrument_key in self.raise_for_keys:
            raise UpstoxAPIError("simulated failure")
        return list(self.candles_by_key.get(instrument_key, []))

    def get_intraday_daily_candle(self, instrument_key):
        self.intraday_calls.append(instrument_key)
        if instrument_key in self.raise_intraday_for_keys:
            raise UpstoxAPIError("simulated intraday failure")
        return list(self.intraday_by_key.get(instrument_key, []))


def test_sync_is_idempotent():
    portfolio = make_portfolio_db()
    ohlcv = make_ohlcv_db()
    insert_symbol(portfolio, "TATAMOTORS", "NSE_EQ|KEY1")
    candles = [
        ["2026-10-14T00:00:00+05:30", 100, 105, 99, 104, 1000, 0],
        ["2026-10-15T00:00:00+05:30", 104, 108, 103, 107, 1200, 0],
    ]
    client = FakeClient(candles_by_key={"NSE_EQ|KEY1": candles})
    clock = FakeClock(datetime(2026, 10, 16, 9, 0, 0))

    sync_ohlcv(client, clock, ohlcv_conn=ohlcv, portfolio_conn=portfolio)
    rows_1 = ohlcv.execute("SELECT * FROM ohlcv ORDER BY trade_date").fetchall()

    sync_ohlcv(client, clock, ohlcv_conn=ohlcv, portfolio_conn=portfolio)
    rows_2 = ohlcv.execute("SELECT * FROM ohlcv ORDER BY trade_date").fetchall()

    assert len(rows_1) == 2
    assert [dict(r) for r in rows_1] == [dict(r) for r in rows_2]
    status = ohlcv.execute("SELECT status FROM ticker_status WHERE ticker = 'TATAMOTORS'").fetchone()
    assert status["status"] == "OK"


def test_corporate_action_purges_cache_and_freezes_position():
    portfolio = make_portfolio_db()
    ohlcv = make_ohlcv_db()
    insert_symbol(portfolio, "TATAMOTORS", "NSE_EQ|KEY1")
    insert_agent(portfolio, "simons")
    insert_open_position(portfolio, "simons", "TATAMOTORS")

    # Cache holds the pre-split price (200); the fresh adjusted candle for the same date is 100
    # (a 1:2 split), a 100% difference, well past CORP_ACTION_DIFF_PCT.
    ohlcv.execute(
        "INSERT INTO ohlcv (ticker, trade_date, open, high, low, close, volume) "
        "VALUES ('TATAMOTORS', '2026-10-15', 198, 202, 196, 200, 1000)"
    )
    fresh_candle = [["2026-10-15T00:00:00+05:30", 99, 101, 98, 100, 2000, 0]]
    client = FakeClient(candles_by_key={"NSE_EQ|KEY1": fresh_candle})
    clock = FakeClock(datetime(2026, 10, 16, 9, 0, 0))

    status = sync_ticker(client, ohlcv, portfolio, "TATAMOTORS", "NSE_EQ|KEY1", clock)

    assert status == "OK"
    row = ohlcv.execute("SELECT close FROM ohlcv WHERE ticker='TATAMOTORS' AND trade_date='2026-10-15'").fetchone()
    assert row["close"] == 100  # old 200 value is gone; reload wrote the adjusted price

    position = portfolio.execute("SELECT frozen_reason FROM positions WHERE ticker='TATAMOTORS'").fetchone()
    assert position["frozen_reason"] == "CORP_ACTION"

    log_row = portfolio.execute(
        "SELECT * FROM activity_log WHERE ticker='TATAMOTORS' AND event_type='CORP_ACTION_FROZEN'"
    ).fetchone()
    assert log_row is not None
    assert log_row["agent_id"] == "simons"

    # Client was called twice: once for the overlap check, once to reload after the purge.
    assert len(client.calls) == 2


def test_stale_data_after_client_failure():
    portfolio = make_portfolio_db()
    ohlcv = make_ohlcv_db()
    insert_symbol(portfolio, "BADTICKER", "NSE_EQ|KEY2")
    client = FakeClient(raise_for_keys={"NSE_EQ|KEY2"})
    clock = FakeClock(datetime(2026, 10, 16, 9, 0, 0))

    status = sync_ticker(client, ohlcv, portfolio, "BADTICKER", "NSE_EQ|KEY2", clock)

    assert status == "STALE_DATA"
    row = ohlcv.execute("SELECT status FROM ticker_status WHERE ticker='BADTICKER'").fetchone()
    assert row["status"] == "STALE_DATA"


def test_locked_circuit_when_latest_volume_is_zero():
    portfolio = make_portfolio_db()
    ohlcv = make_ohlcv_db()
    insert_symbol(portfolio, "FROZENSTOCK", "NSE_EQ|KEY3")
    candles = [["2026-10-15T00:00:00+05:30", 100, 100, 100, 100, 0, 0]]
    client = FakeClient(candles_by_key={"NSE_EQ|KEY3": candles})
    clock = FakeClock(datetime(2026, 10, 16, 9, 0, 0))

    status = sync_ticker(client, ohlcv, portfolio, "FROZENSTOCK", "NSE_EQ|KEY3", clock)

    assert status == "LOCKED_CIRCUIT"


def test_merges_intraday_today_candle_when_historical_storage_lacks_today():
    portfolio = make_portfolio_db()
    ohlcv = make_ohlcv_db()
    insert_symbol(portfolio, "RELIANCE", "NSE_EQ|KEY_RELIANCE")
    # Historical storage only has candles up to yesterday (2026-10-25)
    hist_candles = [["2026-10-25T00:00:00+05:30", 1180, 1200, 1170, 1190, 500000, 0]]
    # Intraday endpoint has today's finalized candle (2026-10-26)
    intra_candle = [["2026-10-26T00:00:00+05:30", 1190, 1210, 1185, 1205, 600000, 0]]
    client = FakeClient(
        candles_by_key={"NSE_EQ|KEY_RELIANCE": hist_candles},
        intraday_by_key={"NSE_EQ|KEY_RELIANCE": intra_candle},
    )
    clock = FakeClock(datetime(2026, 10, 26, 20, 0, 0))

    status = sync_ticker(client, ohlcv, portfolio, "RELIANCE", "NSE_EQ|KEY_RELIANCE", clock)

    assert status == "OK"
    assert len(client.intraday_calls) == 1
    # Verify today's candle was written to ohlcv.db
    today_row = ohlcv.execute("SELECT * FROM ohlcv WHERE ticker='RELIANCE' AND trade_date='2026-10-26'").fetchone()
    assert today_row is not None
    assert today_row["close"] == 1205
    assert today_row["volume"] == 600000


def test_handles_intraday_failure_gracefully_when_historical_present():
    portfolio = make_portfolio_db()
    ohlcv = make_ohlcv_db()
    insert_symbol(portfolio, "INFY", "NSE_EQ|KEY_INFY")
    hist_candles = [["2026-10-25T00:00:00+05:30", 1500, 1520, 1490, 1510, 300000, 0]]
    client = FakeClient(
        candles_by_key={"NSE_EQ|KEY_INFY": hist_candles},
        raise_intraday_for_keys={"NSE_EQ|KEY_INFY"},
    )
    clock = FakeClock(datetime(2026, 10, 26, 20, 0, 0))

    status = sync_ticker(client, ohlcv, portfolio, "INFY", "NSE_EQ|KEY_INFY", clock)

    # Intraday error does not abort pipeline if historical candles exist
    assert status == "OK"
    row = ohlcv.execute("SELECT * FROM ohlcv WHERE ticker='INFY' AND trade_date='2026-10-25'").fetchone()
    assert row is not None
    assert row["close"] == 1510
