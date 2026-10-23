"""
Unit tests for core/build_features.py's day-3c data-date integrity guard: check_data_freshness()
and the job-level FAIL-vs-skip behaviour around the 5% stale-ticker tolerance.
See Plan_v3 §1.4, §2.1.
"""
import sqlite3
from datetime import datetime

import pytest

from core.build_features import check_data_freshness, run
from core.clock import FakeClock
from ingestion.sync_ohlcv import ensure_schema as ensure_ohlcv_schema
from tests.conftest import make_portfolio_db

AS_OF = "2026-10-16"  # a Friday: a trading day
NOW = "2026-10-16T20:00:00+05:30"


def make_ohlcv_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_ohlcv_schema(conn)
    return conn


def make_macro_db() -> sqlite3.Connection:
    from ingestion.sync_macro import ensure_schema as ensure_macro_schema

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_macro_schema(conn)
    return conn


def insert_symbol(conn, ticker):
    conn.execute(
        "INSERT INTO symbols (ticker, instrument_key, isin, company_name, sector, is_active) "
        "VALUES (?, ?, 'ISIN0000000', 'Test Co', 'Test Sector', 1)",
        (ticker, f"NSE_EQ|{ticker}"),
    )


def insert_ohlcv_history(ohlcv_conn, ticker, latest_date, n=250):
    from datetime import date, timedelta

    end = date.fromisoformat(latest_date)
    for i in range(n):
        d = end - timedelta(days=n - 1 - i)
        ohlcv_conn.execute(
            "INSERT INTO ohlcv (ticker, trade_date, open, high, low, close, volume) VALUES (?,?,?,?,?,?,?)",
            (ticker, d.isoformat(), 100.0, 101.0, 99.0, 100.0, 10000),
        )
    ohlcv_conn.execute(
        "INSERT INTO ticker_status (ticker, status, updated_at) VALUES (?, 'OK', ?)", (ticker, NOW)
    )


def test_check_data_freshness_flags_a_stale_ticker():
    portfolio = make_portfolio_db()
    ohlcv = make_ohlcv_db()
    insert_symbol(portfolio, "FRESH")
    insert_ohlcv_history(ohlcv, "FRESH", AS_OF)
    insert_symbol(portfolio, "STALE")
    insert_ohlcv_history(ohlcv, "STALE", "2026-10-15")  # one day behind

    result = check_data_freshness(ohlcv, portfolio, ["FRESH", "STALE"], AS_OF)
    assert result["applicable"] is True
    assert result["checked"] == 2
    assert result["stale"] == 1
    assert result["stale_tickers"] == ["STALE"]
    assert result["stale_fraction"] == pytest.approx(0.5)


def test_check_data_freshness_not_applicable_on_a_non_trading_day():
    portfolio = make_portfolio_db()
    ohlcv = make_ohlcv_db()
    saturday = "2026-10-17"
    result = check_data_freshness(ohlcv, portfolio, ["ANY"], saturday)
    assert result["applicable"] is False
    assert result["stale_fraction"] == 0.0


def test_build_features_fails_the_job_when_more_than_5pct_stale():
    portfolio = make_portfolio_db()
    ohlcv = make_ohlcv_db()
    macro = make_macro_db()
    portfolio.execute(
        "INSERT INTO pipeline_runs (job, run_date, status, started_at, finished_at, detail) "
        "VALUES ('ingestion', ?, 'SUCCESS', ?, ?, NULL)",
        (AS_OF, NOW, NOW),
    )
    # 2 tickers, both stale -> 100% > 5% tolerance -> whole job FAILS.
    for t in ["A", "B"]:
        insert_symbol(portfolio, t)
        insert_ohlcv_history(ohlcv, t, "2026-10-15")

    result = run(as_of_date=AS_OF, clock=FakeClock(datetime(2026, 10, 16, 20, 0, 0)),
                 portfolio_conn=portfolio, ohlcv_conn=ohlcv, macro_conn=macro)

    assert result["status"] == "FAILED"
    assert "data-date integrity" in result["detail"]
    assert result["written"] == 0
    assert portfolio.execute("SELECT COUNT(*) AS n FROM feature_snapshots").fetchone()["n"] == 0
    row = portfolio.execute("SELECT status FROM pipeline_runs WHERE job='features' AND run_date=?", (AS_OF,)).fetchone()
    assert row["status"] == "FAILED"


def test_build_features_skips_only_the_stale_ticker_within_tolerance():
    portfolio = make_portfolio_db()
    ohlcv = make_ohlcv_db()
    macro = make_macro_db()
    portfolio.execute(
        "INSERT INTO pipeline_runs (job, run_date, status, started_at, finished_at, detail) "
        "VALUES ('ingestion', ?, 'SUCCESS', ?, ?, NULL)",
        (AS_OF, NOW, NOW),
    )
    # 100 fresh tickers + 1 stale ticker = 1/101 ~= 0.99% stale, within the 5% tolerance.
    for i in range(100):
        t = f"OK{i}"
        insert_symbol(portfolio, t)
        insert_ohlcv_history(ohlcv, t, AS_OF)
    insert_symbol(portfolio, "ONESTALE")
    insert_ohlcv_history(ohlcv, "ONESTALE", "2026-10-15")

    result = run(as_of_date=AS_OF, clock=FakeClock(datetime(2026, 10, 16, 20, 0, 0)),
                 portfolio_conn=portfolio, ohlcv_conn=ohlcv, macro_conn=macro)

    assert result["status"] == "SUCCESS"
    assert result["written"] == 100
    assert result["skipped"] == 1
    snap = portfolio.execute("SELECT 1 FROM feature_snapshots WHERE ticker='ONESTALE'").fetchone()
    assert snap is None
