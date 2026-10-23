"""
Unit tests for agents/runner.py idempotency and the day-3c date-integrity guard. Uses
FakeLLMClient and in-memory databases (no network, no real OHLCV/features/watchlist pipeline --
those are seeded directly).
See Plan_v3 §3.2.
"""
import json
import sqlite3
from datetime import datetime
from pathlib import Path

from agents.runner import run
from core.clock import FakeClock
from ingestion.sync_ohlcv import ensure_schema as ensure_ohlcv_schema
from llm.client import FakeLLMClient
from tests.conftest import make_portfolio_db

RUN_DATE = "2026-10-16"  # a Friday: a trading day
NOW = "2026-10-16T22:00:00+05:30"

HOLD_RESPONSE = json.dumps({"decisions": [{"ticker": "TATAMOTORS", "action": "HOLD", "reasoning": "no clear edge"}]})


def make_ohlcv_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_ohlcv_schema(conn)
    return conn


def seed(portfolio_conn, ohlcv_conn, ohlcv_trade_date: str = RUN_DATE):
    portfolio_conn.execute(
        "INSERT INTO agents (id, name, philosophy, kind, starting_cash_paise, cash_paise, created_at, updated_at) "
        "VALUES ('simons', 'Jim Simons', 'Quant', 'LLM', 10000000, 10000000, ?, ?)",
        (NOW, NOW),
    )
    portfolio_conn.execute(
        "INSERT INTO symbols (ticker, instrument_key, isin, company_name, sector, is_active) "
        "VALUES ('TATAMOTORS', 'NSE_EQ|KEY1', 'ISIN0000000', 'Tata Motors', 'Automobiles', 1)"
    )
    features = {
        "close": 948.2, "ema_20": 931.0, "ema_50": 918.0, "ema_200": 871.0, "ema_20_above_50": True,
        "rsi_14": 62.4, "macd_hist": 1.8, "adx_14": 24.0, "atr_14": 21.4, "volume_surge": 1.82,
        "obv_slope_sign": 1, "dist_52w_high_pct": -4.1, "dist_52w_low_pct": 12.0,
        "india_vix": 14.06, "regime": "NORMAL",
    }
    portfolio_conn.execute(
        "INSERT INTO feature_snapshots (ticker, as_of_date, schema_version, features_json, created_at) "
        "VALUES ('TATAMOTORS', ?, 1, ?, ?)",
        (RUN_DATE, json.dumps(features), NOW),
    )
    portfolio_conn.execute(
        "INSERT INTO agent_watchlist (agent_id, ticker, sector, added_on, ttl_days, expires_on, intensity_score) "
        "VALUES ('simons', 'TATAMOTORS', 'Automobiles', ?, 3, '2026-10-19', 2.0)",
        (RUN_DATE,),
    )
    portfolio_conn.execute(
        "INSERT INTO pipeline_runs (job, run_date, status, started_at, finished_at, detail) "
        "VALUES ('watchlist', ?, 'SUCCESS', ?, ?, NULL)",
        (RUN_DATE, NOW, NOW),
    )
    ohlcv_conn.execute(
        "INSERT INTO ticker_status (ticker, status, updated_at) VALUES ('TATAMOTORS', 'OK', ?)", (NOW,)
    )
    ohlcv_conn.execute(
        "INSERT INTO ohlcv (ticker, trade_date, open, high, low, close, volume) "
        "VALUES ('TATAMOTORS', ?, 940.0, 950.0, 930.0, 948.2, 1000000)",
        (ohlcv_trade_date,),
    )


def test_running_the_runner_twice_does_not_duplicate_decisions():
    conn = make_portfolio_db()
    ohlcv = make_ohlcv_db()
    seed(conn, ohlcv)
    clock = FakeClock(datetime(2026, 10, 16, 22, 0, 0))

    first = run(["simons"], as_of_date=RUN_DATE, clock=clock, portfolio_conn=conn, ohlcv_conn=ohlcv,
                llm_client=FakeLLMClient(responses=[HOLD_RESPONSE]), fake_llm=True)
    assert first["simons"]["status"] == "SUCCESS"
    count_after_first = conn.execute("SELECT COUNT(*) AS n FROM decisions").fetchone()["n"]
    assert count_after_first == 1

    second = run(["simons"], as_of_date=RUN_DATE, clock=clock, portfolio_conn=conn, ohlcv_conn=ohlcv,
                 llm_client=FakeLLMClient(responses=[HOLD_RESPONSE]), fake_llm=True)
    assert second["simons"]["status"] == "SKIPPED"
    count_after_second = conn.execute("SELECT COUNT(*) AS n FROM decisions").fetchone()["n"]
    assert count_after_second == 1


def test_force_rerun_without_pending_orders_replaces_decisions():
    conn = make_portfolio_db()
    ohlcv = make_ohlcv_db()
    seed(conn, ohlcv)
    clock = FakeClock(datetime(2026, 10, 16, 22, 0, 0))

    run(["simons"], as_of_date=RUN_DATE, clock=clock, portfolio_conn=conn, ohlcv_conn=ohlcv,
        llm_client=FakeLLMClient(responses=[HOLD_RESPONSE]), fake_llm=True)

    second = run(["simons"], as_of_date=RUN_DATE, clock=clock, portfolio_conn=conn, ohlcv_conn=ohlcv,
                 llm_client=FakeLLMClient(responses=[HOLD_RESPONSE]), fake_llm=True, force=True)
    assert second["simons"]["status"] == "SUCCESS"
    count = conn.execute("SELECT COUNT(*) AS n FROM decisions").fetchone()["n"]
    assert count == 1  # replaced, not duplicated


def test_force_rerun_refused_when_an_order_is_already_filled():
    conn = make_portfolio_db()
    ohlcv = make_ohlcv_db()
    seed(conn, ohlcv)
    clock = FakeClock(datetime(2026, 10, 16, 22, 0, 0))

    run(["simons"], as_of_date=RUN_DATE, clock=clock, portfolio_conn=conn, ohlcv_conn=ohlcv,
        llm_client=FakeLLMClient(responses=[HOLD_RESPONSE]), fake_llm=True)
    decision_id = conn.execute("SELECT id FROM decisions LIMIT 1").fetchone()["id"]
    conn.execute(
        "INSERT INTO pending_orders (agent_id, ticker, side, shares, reserved_amount_paise, "
        "decision_id, status, valid_for_date, created_at, updated_at) "
        "VALUES ('simons', 'TATAMOTORS', 'BUY', 10, 100000, ?, 'filled', '2026-10-17', ?, ?)",
        (decision_id, NOW, NOW),
    )

    second = run(["simons"], as_of_date=RUN_DATE, clock=clock, portfolio_conn=conn, ohlcv_conn=ohlcv,
                 llm_client=FakeLLMClient(responses=[HOLD_RESPONSE]), fake_llm=True, force=True)
    assert second["simons"]["status"] == "REFUSED"


def test_force_rerun_cancels_a_merely_pending_order_and_proceeds():
    conn = make_portfolio_db()
    ohlcv = make_ohlcv_db()
    seed(conn, ohlcv)
    clock = FakeClock(datetime(2026, 10, 16, 22, 0, 0))

    run(["simons"], as_of_date=RUN_DATE, clock=clock, portfolio_conn=conn, ohlcv_conn=ohlcv,
        llm_client=FakeLLMClient(responses=[HOLD_RESPONSE]), fake_llm=True)
    decision_id = conn.execute("SELECT id FROM decisions LIMIT 1").fetchone()["id"]
    conn.execute(
        "INSERT INTO pending_orders (agent_id, ticker, side, shares, reserved_amount_paise, "
        "decision_id, status, valid_for_date, created_at, updated_at) "
        "VALUES ('simons', 'TATAMOTORS', 'BUY', 10, 100000, ?, 'pending', '2026-10-17', ?, ?)",
        (decision_id, NOW, NOW),
    )

    second = run(["simons"], as_of_date=RUN_DATE, clock=clock, portfolio_conn=conn, ohlcv_conn=ohlcv,
                 llm_client=FakeLLMClient(responses=[HOLD_RESPONSE]), fake_llm=True, force=True)
    assert second["simons"]["status"] == "SUCCESS"
    # cancel_pending_for_run must have cancelled the old order before decisions were deleted.
    old_order = conn.execute("SELECT status FROM pending_orders WHERE decision_id = ?", (decision_id,)).fetchone()
    assert old_order["status"] == "cancelled"


def test_llm_calls_row_records_finish_reason():
    conn = make_portfolio_db()
    ohlcv = make_ohlcv_db()
    seed(conn, ohlcv)
    clock = FakeClock(datetime(2026, 10, 16, 22, 0, 0))

    run(["simons"], as_of_date=RUN_DATE, clock=clock, portfolio_conn=conn, ohlcv_conn=ohlcv,
        llm_client=FakeLLMClient(responses=[HOLD_RESPONSE]), fake_llm=True)

    row = conn.execute("SELECT finish_reason, parse_status FROM llm_calls ORDER BY id DESC LIMIT 1").fetchone()
    assert row["finish_reason"] == "stop"
    assert row["parse_status"] == "SUCCESS"


def test_date_integrity_check_fails_the_job_when_review_pool_data_is_stale():
    conn = make_portfolio_db()
    ohlcv = make_ohlcv_db()
    # The OHLCV candle is dated a day BEFORE run_date -- simulating the exact real-world
    # scenario this guard exists for (same-day candle not yet published by Upstox).
    seed(conn, ohlcv, ohlcv_trade_date="2026-10-15")
    clock = FakeClock(datetime(2026, 10, 16, 22, 0, 0))

    result = run(["simons"], as_of_date=RUN_DATE, clock=clock, portfolio_conn=conn, ohlcv_conn=ohlcv,
                 llm_client=FakeLLMClient(responses=[HOLD_RESPONSE]), fake_llm=True)

    assert result["simons"]["status"] == "FAILED"
    assert "data-date integrity" in result["simons"]["detail"]
    assert conn.execute("SELECT COUNT(*) AS n FROM decisions").fetchone()["n"] == 0
    row = conn.execute("SELECT status FROM pipeline_runs WHERE job='agents' AND run_date=?", (RUN_DATE,)).fetchone()
    assert row["status"] == "FAILED"
