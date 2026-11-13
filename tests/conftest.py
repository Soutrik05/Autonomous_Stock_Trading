"""
Shared test fixtures: fake OHLCV data, FakeClock, FakeLLM and ReplayQuoteProvider.
See Plan_v3 §5 (Core Architectural Principles 5-6 interfaces).
"""

import sqlite3
from datetime import datetime
from pathlib import Path

import pytest

from core.clock import FakeClock
from core.config import settings
from ingestion.sync_macro import ensure_schema as ensure_macro_schema
from ingestion.sync_ohlcv import ensure_schema as ensure_ohlcv_schema

_DB_DIR = Path(__file__).resolve().parents[1] / "db"
_SCHEMA_PATH = _DB_DIR / "schema.sql"
_MIGRATIONS_DIR = _DB_DIR / "migrations"


def make_portfolio_db(foreign_keys: bool = True) -> sqlite3.Connection:
    """An in-memory portfolio.db with the baseline schema plus every migration after 0001
    (e.g. llm_calls.finish_reason/reasoning_tokens from migration 0002), for tests that need
    columns schema.sql alone does not have. isolation_level=None (autocommit) matches
    core.database.get_connection() exactly -- broker/engine.py's explicit BEGIN IMMEDIATE/COMMIT
    transactions require it; the default (implicit-transaction) mode would raise 'cannot start a
    transaction within a transaction'."""
    conn = sqlite3.connect(":memory:", isolation_level=None)
    if foreign_keys:
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
        "VALUES ('simons', 'Jim Simons', 'Quant Momentum', 'LLM', ?, ?, ?, ?)",
        (settings.INITIAL_CASH_PER_AGENT_PAISE, settings.INITIAL_CASH_PER_AGENT_PAISE, now, now),
    )
    portfolio_conn.execute(
        "INSERT INTO agents (id, name, philosophy, kind, starting_cash_paise, cash_paise, created_at, updated_at) "
        "VALUES ('baseline-simons-rules', 'Baseline Simons Rules', 'Rules Momentum', 'BASELINE', ?, ?, ?, ?)",
        (settings.INITIAL_CASH_PER_AGENT_PAISE, settings.INITIAL_CASH_PER_AGENT_PAISE, now, now),
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

    def get_intraday_daily_candle(self, instrument_key: str):
        return [["2026-10-19T15:30:00+05:30", 1000.0, 1010.0, 990.0, 1000.0, 150_000, 0]]

    def get_india_vix(self):
        return {"last_price": 14.5}

    def get_fii_data(self, data_type: str = "NSE_EQ|CASH", interval: str = "1D"):
        return [{"time_stamp": 1792348200000, "buy_amount": 10000.0, "sell_amount": 9000.0}]

    def get_dii_data(self, data_type: str = "NSE_EQ|CASH", interval: str = "1D"):
        return [{"time_stamp": 1792348200000, "buy_amount": 8000.0, "sell_amount": 7500.0}]

    def get_corporate_actions(self, isin: str):
        return [{"name": "Dividend", "expiry_date": "2026-10-19", "amount": 5.0, "ratio": None, "event_details": []}]

    def get_news(self, instrument_keys):
        return {key: [] for key in instrument_keys}

    def get_key_ratios(self, isin: str):
        return [
            {"name": "P/E", "company_value": 20.0},
            {"name": "P/B", "company_value": 2.5},
            {"name": "ROCE", "company_value": 18.0},
            {"name": "ROE", "company_value": 15.0},
        ]

    def get_income_statement(self, isin: str, time_period: str = "yearly"):
        return {
            "income_statement": [
                {"category": "net_profit", "history": [{"change": 15.0}]},
                {"category": "revenue", "history": [{"change": 12.0}]},
            ],
            "full_statement": [
                {"category": "Profit After Tax", "history": [{"amount": 5000.0}]},
            ],
        }

    def get_balance_sheet(self, isin: str):
        return {
            "full_statement": [
                {"category": "Equity Capital", "history": [{"amount": 10000.0}]},
                {"category": "Current Liabilities", "history": [{"amount": 2000.0}]},
                {"category": "Non-Current Liabilities", "history": [{"amount": 1000.0}]},
            ]
        }

    def get_cash_flow(self, isin: str):
        return {
            "full_statement": [
                {"category": "Cash flow from Operations", "history": [{"amount": 6000.0}]},
            ]
        }

    def get_share_holdings(self, isin: str):
        return [
            {"category": "promoters", "history": [{"value": 52.0}]},
            {"category": "fii", "history": [{"value": 20.0}]},
            {"category": "dii", "history": [{"value": 15.0}]},
        ]


@pytest.fixture
def mock_upstox_client() -> MockUpstoxClient:
    """Mock Upstox client returning deterministic candle and quote fixtures."""
    return MockUpstoxClient()


# =================================================================================================
# Canonical Synthetic Feature Snapshot Builders for Unit and Integration Testing
# Ensures all persona Stage 1 hurdles and Stage 2 ranker inputs are cleanly satisfied by default.
# =================================================================================================


def make_passing_simons_features(**overrides) -> dict:
    """Features satisfying Jim Simons quant-momentum hurdles and Stage 2 inputs."""
    feat = {
        "close": 1000.0,
        "ema_20": 990.0,
        "ema_50": 980.0,
        "ema_200": 920.0,
        "ema_20_above_50": True,
        "rsi_14": 60.0,
        "volume_surge": 1.5,
        "macd_hist": 1.5,
        "atr_14": 15.0,
        "adx_14": 25.0,
        "kaufman_er_20": 0.50,
        "obv_slope_sign": 1,
    }
    feat.update(overrides)
    return feat


def make_passing_lynch_features(**overrides) -> dict:
    """Features satisfying Peter Lynch GARP hurdles and Stage 2 inputs."""
    feat = {
        "close": 500.0,
        "ema_200": 480.0,
        "peg": 0.65,
        "roce_pct": 22.0,
        "debt_to_equity": 0.4,
        "cfo_to_pat": 1.2,
        "pat_growth_yoy_pct": 18.0,
        "rsi_14": 52.0,
        "volume_surge": 1.1,
    }
    feat.update(overrides)
    return feat


def make_passing_marks_features(**overrides) -> dict:
    """Features satisfying Howard Marks contrarian quality-oversold hurdles."""
    feat = {
        "close": 120.0,
        "ema_200": 150.0,  # Trading below 200 EMA during distress
        "rsi_14": 26.0,
        "dist_52w_low_pct": 6.0,
        "pe": 16.0,
        "roce_pct": 18.0,
        "debt_to_equity": 0.3,
        "cfo_to_pat": 1.1,
        "regime": "NORMAL",
    }
    feat.update(overrides)
    return feat


def make_passing_rj_features(**overrides) -> dict:
    """Features satisfying Rakesh Jhunjhunwala compounder hurdles and Stage 2 inputs."""
    feat = {
        "close": 400.0,
        "ema_200": 360.0,
        "ema_20_above_50": True,
        "volume_surge": 1.6,
        "promoter_holding_pct": 54.0,
        "pat_growth_yoy_pct": 22.0,
        "roce_pct": 20.0,
        "debt_to_equity": 0.4,
        "pe": 28.0,
        "fii_dii_qoq_delta_pct": 1.5,
        "atr_14": 10.0,
    }
    feat.update(overrides)
    return feat


def make_passing_varsity_features(**overrides) -> dict:
    """Features satisfying StockMinds Core / Varsity balanced confluence hurdles."""
    feat = {
        "close": 250.0,
        "ema_200": 230.0,
        "ema_20_above_50": True,
        "rsi_14": 56.0,
        "volume_surge": 1.3,
        "roce_pct": 18.0,
        "roe_pct": 16.0,
        "debt_to_equity": 0.5,
        "dcf_discount_pct": 15.0,
        "news_sentiment": 0.2,
    }
    feat.update(overrides)
    return feat


CANONICAL_FEATURE_BUILDERS = {
    "simons": make_passing_simons_features,
    "lynch": make_passing_lynch_features,
    "marks": make_passing_marks_features,
    "jhunjhunwala": make_passing_rj_features,
    "varsity": make_passing_varsity_features,
}


def make_canonical_features(agent_id: str, **overrides) -> dict:
    """Returns canonical passing features for the specified agent persona."""
    builder = CANONICAL_FEATURE_BUILDERS.get(agent_id, make_passing_simons_features)
    return builder(**overrides)
