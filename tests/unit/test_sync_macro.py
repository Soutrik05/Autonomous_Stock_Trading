"""
Unit tests for ingestion/sync_macro.py: regime computation, FII/DII net cash flow extraction,
advance/decline breadth calculation, index trend derivation, and database persistence/upsert.
"""
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path

from core.clock import FakeClock
from ingestion.sync_macro import (
    ensure_schema,
    sync_macro,
    compute_regime,
    _extract_net_cr,
    compute_advance_decline,
    compute_index_trends,
)

PORTFOLIO_SCHEMA_PATH = Path(__file__).resolve().parents[2] / "db" / "schema.sql"


def make_portfolio_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(PORTFOLIO_SCHEMA_PATH.read_text(encoding="utf-8"))
    return conn


def make_macro_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_schema(conn)
    return conn


def make_ohlcv_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE ohlcv (
            ticker      TEXT NOT NULL,
            trade_date  TEXT NOT NULL,
            open        REAL NOT NULL,
            high        REAL NOT NULL,
            low         REAL NOT NULL,
            close       REAL NOT NULL,
            volume      INTEGER NOT NULL,
            PRIMARY KEY (ticker, trade_date)
        )
        """
    )
    return conn


class FakeMacroClient:
    def __init__(self, vix=15.0, fii_records=None, dii_records=None, candles=None, quotes=None):
        self._vix = vix
        self._fii_records = fii_records or []
        self._dii_records = dii_records or []
        self._candles = candles or {}
        self._quotes = quotes or {}

    def get_india_vix(self):
        return {"last_price": self._vix} if self._vix is not None else None

    def get_fii_data(self, data_type="NSE_EQ|CASH", interval="1D"):
        return self._fii_records

    def get_dii_data(self, data_type="NSE_EQ|CASH", interval="1D"):
        return self._dii_records

    def get_daily_candles(self, instrument_key, from_date, to_date):
        return self._candles.get(instrument_key, [])

    def get_quotes(self, instrument_keys):
        res = {}
        for k in instrument_keys:
            colon_k = k.replace("|", ":")
            pipe_k = k.replace(":", "|")
            if colon_k in self._quotes:
                res[colon_k] = self._quotes[colon_k]
            elif pipe_k in self._quotes:
                res[pipe_k] = self._quotes[pipe_k]
        return res


def test_compute_regime():
    assert compute_regime(11.0) == "LOW_VOL"
    assert compute_regime(15.0) == "NORMAL"
    assert compute_regime(21.0) == "ELEVATED"
    assert compute_regime(26.0) == "PANIC"


def test_extract_net_cr():
    ts = int(datetime(2026, 10, 26, 0, 0, 0, tzinfo=timezone(timedelta(hours=5, minutes=30))).timestamp() * 1000)
    records = [
        {"time_stamp": ts, "buy_amount": 9324.9, "sell_amount": 10787.39},
        {"time_stamp": ts - 86400000, "buy_amount": 8000.0, "sell_amount": 7000.0},
    ]
    net_today = _extract_net_cr(records, "2026-10-26")
    assert net_today == -1462.49

    net_missing = _extract_net_cr(records, "2026-10-20")
    assert net_missing is None


def test_compute_advance_decline_with_prior_day():
    ohlcv_db = make_ohlcv_db()
    # Insert 60 advancing and 30 declining tickers across 2 dates
    for i in range(1, 91):
        ticker = f"TICK{i}"
        # Prior date 2026-10-25
        ohlcv_db.execute(
            "INSERT INTO ohlcv VALUES (?, '2026-10-25', 100, 105, 95, 100, 1000)",
            (ticker,),
        )
        # Current date 2026-10-26: first 60 advance (close=110), remaining 30 decline (close=90)
        close_price = 110.0 if i <= 60 else 90.0
        ohlcv_db.execute(
            "INSERT INTO ohlcv VALUES (?, '2026-10-26', 100, 115, 85, ?, 1000)",
            (ticker, close_price),
        )

    ad_ratio = compute_advance_decline(ohlcv_db, "2026-10-26")
    assert ad_ratio == 2.0  # 60 / 30


def test_compute_advance_decline_intraday_fallback():
    ohlcv_db = make_ohlcv_db()
    # Single date: 40 close > open (advance), 10 close < open (decline)
    for i in range(1, 51):
        ticker = f"TICK{i}"
        close_price = 110.0 if i <= 40 else 90.0
        ohlcv_db.execute(
            "INSERT INTO ohlcv VALUES (?, '2026-10-26', 100, 115, 85, ?, 1000)",
            (ticker, close_price),
        )

    ad_ratio = compute_advance_decline(ohlcv_db, "2026-10-26")
    assert ad_ratio == 4.0  # 40 / 10


def test_compute_advance_decline_zero_declines():
    ohlcv_db = make_ohlcv_db()
    for i in range(1, 21):
        ticker = f"TICK{i}"
        ohlcv_db.execute(
            "INSERT INTO ohlcv VALUES (?, '2026-10-26', 100, 115, 95, 110, 1000)",
            (ticker,),
        )
    ad_ratio = compute_advance_decline(ohlcv_db, "2026-10-26")
    assert ad_ratio == 20.0


def test_compute_index_trends_from_candles():
    # 20 sessions of candles where close rises steadily
    candles_50 = [
        [f"2026-10-{i:02d}T00:00:00+05:30", 22000, 22100, 21900, 22000 + i * 50, 0, 0]
        for i in range(1, 21)
    ]
    # 20 sessions of candles where close falls steadily
    candles_500 = [
        [f"2026-10-{i:02d}T00:00:00+05:30", 22000, 22100, 21900, 22000 - i * 50, 0, 0]
        for i in range(1, 21)
    ]
    client = FakeMacroClient(
        candles={"NSE_INDEX|Nifty 50": candles_50, "NSE_INDEX|Nifty 500": candles_500}
    )
    n50_trend, n500_trend = compute_index_trends(client, "2026-10-20")
    assert n50_trend == "BULLISH"
    assert n500_trend == "BEARISH"


def test_compute_index_trends_from_quotes():
    client = FakeMacroClient(
        quotes={
            "NSE_INDEX:Nifty 50": {
                "last_price": 23100.0,
                "net_change": 150.0,
                "ohlc": {"close": 22950.0},
            },
            "NSE_INDEX:Nifty 500": {
                "last_price": 21800.0,
                "net_change": -120.0,
                "ohlc": {"close": 21920.0},
            },
        }
    )
    n50_trend, n500_trend = compute_index_trends(client, "2026-10-26")
    assert n50_trend == "BULLISH"
    assert n500_trend == "BEARISH"


def test_compute_index_trends_breadth_fallback():
    client = FakeMacroClient()
    # Bullish breadth
    t50, t500 = compute_index_trends(client, "2026-10-26", advance_decline=1.8)
    assert t50 == "BULLISH"
    assert t500 == "BULLISH"

    # Bearish breadth
    t50, t500 = compute_index_trends(client, "2026-10-26", advance_decline=0.4)
    assert t50 == "BEARISH"
    assert t500 == "BEARISH"

    # Sideways breadth
    t50, t500 = compute_index_trends(client, "2026-10-26", advance_decline=1.0)
    assert t50 == "SIDEWAYS"
    assert t500 == "SIDEWAYS"


def test_sync_macro_persists_trends_and_breadth():
    macro_db = make_macro_db()
    port_db = make_portfolio_db()
    ohlcv_db = make_ohlcv_db()
    clock = FakeClock(datetime(2026, 10, 26, 20, 0, 0))

    # Populate ohlcv with 60 advance / 30 decline
    for i in range(1, 91):
        ticker = f"TICK{i}"
        ohlcv_db.execute(
            "INSERT INTO ohlcv VALUES (?, '2026-10-25', 100, 105, 95, 100, 1000)",
            (ticker,),
        )
        close_price = 110.0 if i <= 60 else 90.0
        ohlcv_db.execute(
            "INSERT INTO ohlcv VALUES (?, '2026-10-26', 100, 115, 85, ?, 1000)",
            (ticker, close_price),
        )

    quotes = {
        "NSE_INDEX:Nifty 50": {
            "last_price": 23000.0,
            "net_change": 100.0,
            "ohlc": {"close": 22900.0},
        },
        "NSE_INDEX:Nifty 500": {
            "last_price": 21800.0,
            "net_change": 10.0,
            "ohlc": {"close": 21790.0},  # ~0.04% -> SIDEWAYS
        },
    }
    client = FakeMacroClient(vix=16.5, quotes=quotes)

    row = sync_macro(
        client,
        clock,
        macro_conn=macro_db,
        portfolio_conn=port_db,
        ohlcv_conn=ohlcv_db,
    )

    assert row["trade_date"] == "2026-10-26"
    assert row["regime"] == "NORMAL"
    assert row["advance_decline"] == 2.0
    assert row["nifty50_trend"] == "BULLISH"
    assert row["nifty500_trend"] == "SIDEWAYS"

    db_row = macro_db.execute("SELECT * FROM macro_daily WHERE trade_date = '2026-10-26'").fetchone()
    assert db_row["advance_decline"] == 2.0
    assert db_row["nifty50_trend"] == "BULLISH"
    assert db_row["nifty500_trend"] == "SIDEWAYS"
