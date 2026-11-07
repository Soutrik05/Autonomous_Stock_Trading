"""
Unit tests for evaluation/forward_returns.py:
Backfilling forward returns (T+1, T+5, etc.) and Nifty 500 benchmark proxy returns.
"""

import sqlite3
from datetime import datetime

import pytest

from core.clock import FakeClock
from evaluation.forward_returns import compute_forward_returns
from ingestion.sync_ohlcv import ensure_schema as ensure_ohlcv_schema
from tests.conftest import make_portfolio_db

NOW = "2026-03-10T22:00:00+05:30"


def make_ohlcv_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_ohlcv_schema(conn)
    return conn


def insert_ohlcv_bar(conn, ticker, trade_date, close, volume=100000):
    conn.execute(
        "INSERT INTO ohlcv (ticker, trade_date, open, high, low, close, volume) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (ticker, trade_date, close, close, close, close, volume),
    )


def test_forward_returns_backfill_and_benchmark():
    portfolio = make_portfolio_db(foreign_keys=False)
    ohlcv = make_ohlcv_db()

    # Seed decisions on 2026-03-02
    portfolio.execute(
        """
        INSERT INTO decisions (id, run_date, agent_id, ticker, source, action, shares, created_at)
        VALUES (1, '2026-03-02', 'simons', 'TATA', 'LLM', 'BUY', 10, ?)
        """,
        (NOW,),
    )

    # Seed T0 prices on 2026-03-02
    insert_ohlcv_bar(ohlcv, "TATA", "2026-03-02", 100.0)
    insert_ohlcv_bar(ohlcv, "INFY", "2026-03-02", 500.0)

    # Seed T+1 on 2026-03-03 (TATA up 5% to 105, INFY flat at 500)
    insert_ohlcv_bar(ohlcv, "TATA", "2026-03-03", 105.0)
    insert_ohlcv_bar(ohlcv, "INFY", "2026-03-03", 500.0)

    # Seed T+2 on 2026-03-04 (TATA at 110, INFY at 525)
    insert_ohlcv_bar(ohlcv, "TATA", "2026-03-04", 110.0)
    insert_ohlcv_bar(ohlcv, "INFY", "2026-03-04", 525.0)

    clock = FakeClock(datetime(2026, 3, 5, 20, 0))

    # Run for horizon [1, 2] with min_date_coverage=1
    res = compute_forward_returns(portfolio, ohlcv, clock=clock, horizons=[1, 2], min_date_coverage=1)
    assert res["status"] == "SUCCESS"
    assert res["rows_written"] == 2

    # Verify T+1 row
    t1_row = portfolio.execute("SELECT * FROM forward_returns WHERE decision_id = 1 AND horizon_days = 1").fetchone()
    assert t1_row is not None
    assert t1_row["ret_pct"] == pytest.approx(5.0)
    # Benchmark average return on T+1: (5% + 0%) / 2 = 2.5%
    assert t1_row["nifty_ret_pct"] == pytest.approx(2.5)

    # Verify T+2 row
    t2_row = portfolio.execute("SELECT * FROM forward_returns WHERE decision_id = 1 AND horizon_days = 2").fetchone()
    assert t2_row is not None
    assert t2_row["ret_pct"] == pytest.approx(10.0)
    # Benchmark return on T+2: (10% + 5%) / 2 = 7.5%
    assert t2_row["nifty_ret_pct"] == pytest.approx(7.5)

    # Re-running is idempotent and writes 0 new rows
    res2 = compute_forward_returns(portfolio, ohlcv, clock=clock, horizons=[1, 2], min_date_coverage=1)
    assert res2["rows_written"] == 0


def test_forward_returns_negative_and_missing_future_bars():
    portfolio = make_portfolio_db(foreign_keys=False)
    ohlcv = make_ohlcv_db()

    # Decision on 2026-03-02 for INFY
    portfolio.execute(
        """
        INSERT INTO decisions (id, run_date, agent_id, ticker, source, action, shares, created_at)
        VALUES (2, '2026-03-02', 'simons', 'INFY', 'LLM', 'BUY', 5, ?)
        """,
        (NOW,),
    )

    # T0 prices
    insert_ohlcv_bar(ohlcv, "INFY", "2026-03-02", 200.0)
    insert_ohlcv_bar(ohlcv, "TCS", "2026-03-02", 400.0)

    # T+1 price drops -8% for INFY (184.0), TCS flat (400.0)
    insert_ohlcv_bar(ohlcv, "INFY", "2026-03-03", 184.0)
    insert_ohlcv_bar(ohlcv, "TCS", "2026-03-03", 400.0)

    # No T+5 data in ohlcv DB
    clock = FakeClock(datetime(2026, 3, 5, 20, 0))

    # Horizon [1, 5] with min_date_coverage=1: T+1 succeeds, T+5 is skipped without crashing
    res = compute_forward_returns(portfolio, ohlcv, clock=clock, horizons=[1, 5], min_date_coverage=1)
    assert res["status"] == "SUCCESS"
    assert res["rows_written"] == 1

    t1_row = portfolio.execute("SELECT * FROM forward_returns WHERE decision_id = 2 AND horizon_days = 1").fetchone()
    assert t1_row is not None
    assert t1_row["ret_pct"] == pytest.approx(-8.0)

    # T+5 row was not computed due to missing future bar
    t5_row = portfolio.execute("SELECT * FROM forward_returns WHERE decision_id = 2 AND horizon_days = 5").fetchone()
    assert t5_row is None
