"""
Unit tests for agents/runner.py idempotency: running the runner twice for the same agent/date
does not duplicate decisions. Uses FakeLLMClient and an in-memory portfolio.db (no network,
no real OHLCV/features/watchlist pipeline -- those are seeded directly).
See Plan_v3 §3.2.
"""
import json
import sqlite3
from datetime import datetime
from pathlib import Path

from agents.runner import run
from core.clock import FakeClock
from llm.client import FakeLLMClient

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "db" / "schema.sql"
RUN_DATE = "2026-10-16"
NOW = "2026-10-16T22:00:00+05:30"

HOLD_RESPONSE = json.dumps({"decisions": [{"ticker": "TATAMOTORS", "action": "HOLD", "reasoning": "no clear edge"}]})


def make_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    return conn


def seed(conn):
    conn.execute(
        "INSERT INTO agents (id, name, philosophy, kind, starting_cash_paise, cash_paise, created_at, updated_at) "
        "VALUES ('simons', 'Jim Simons', 'Quant', 'LLM', 10000000, 10000000, ?, ?)",
        (NOW, NOW),
    )
    conn.execute(
        "INSERT INTO symbols (ticker, instrument_key, isin, company_name, sector, is_active) "
        "VALUES ('TATAMOTORS', 'NSE_EQ|KEY1', 'ISIN0000000', 'Tata Motors', 'Automobiles', 1)"
    )
    features = {
        "close": 948.2, "ema_20": 931.0, "ema_50": 918.0, "ema_200": 871.0, "ema_20_above_50": True,
        "rsi_14": 62.4, "macd_hist": 1.8, "adx_14": 24.0, "atr_14": 21.4, "volume_surge": 1.82,
        "obv_slope_sign": 1, "dist_52w_high_pct": -4.1, "dist_52w_low_pct": 12.0,
        "india_vix": 14.06, "regime": "NORMAL",
    }
    conn.execute(
        "INSERT INTO feature_snapshots (ticker, as_of_date, schema_version, features_json, created_at) "
        "VALUES ('TATAMOTORS', ?, 1, ?, ?)",
        (RUN_DATE, json.dumps(features), NOW),
    )
    conn.execute(
        "INSERT INTO agent_watchlist (agent_id, ticker, sector, added_on, ttl_days, expires_on, intensity_score) "
        "VALUES ('simons', 'TATAMOTORS', 'Automobiles', ?, 3, '2026-10-19', 2.0)",
        (RUN_DATE,),
    )
    conn.execute(
        "INSERT INTO pipeline_runs (job, run_date, status, started_at, finished_at, detail) "
        "VALUES ('watchlist', ?, 'SUCCESS', ?, ?, NULL)",
        (RUN_DATE, NOW, NOW),
    )


def test_running_the_runner_twice_does_not_duplicate_decisions():
    conn = make_db()
    seed(conn)
    clock = FakeClock(datetime(2026, 10, 16, 22, 0, 0))

    first = run(["simons"], as_of_date=RUN_DATE, clock=clock, portfolio_conn=conn,
                llm_client=FakeLLMClient(responses=[HOLD_RESPONSE]), fake_llm=True)
    assert first["simons"]["status"] == "SUCCESS"
    count_after_first = conn.execute("SELECT COUNT(*) AS n FROM decisions").fetchone()["n"]
    assert count_after_first == 1

    second = run(["simons"], as_of_date=RUN_DATE, clock=clock, portfolio_conn=conn,
                 llm_client=FakeLLMClient(responses=[HOLD_RESPONSE]), fake_llm=True)
    assert second["simons"]["status"] == "SKIPPED"
    count_after_second = conn.execute("SELECT COUNT(*) AS n FROM decisions").fetchone()["n"]
    assert count_after_second == 1


def test_force_rerun_without_pending_orders_replaces_decisions():
    conn = make_db()
    seed(conn)
    clock = FakeClock(datetime(2026, 10, 16, 22, 0, 0))

    run(["simons"], as_of_date=RUN_DATE, clock=clock, portfolio_conn=conn,
        llm_client=FakeLLMClient(responses=[HOLD_RESPONSE]), fake_llm=True)

    second = run(["simons"], as_of_date=RUN_DATE, clock=clock, portfolio_conn=conn,
                 llm_client=FakeLLMClient(responses=[HOLD_RESPONSE]), fake_llm=True, force=True)
    assert second["simons"]["status"] == "SUCCESS"
    count = conn.execute("SELECT COUNT(*) AS n FROM decisions").fetchone()["n"]
    assert count == 1  # replaced, not duplicated


def test_force_rerun_refused_when_a_pending_order_references_the_decision():
    conn = make_db()
    seed(conn)
    clock = FakeClock(datetime(2026, 10, 16, 22, 0, 0))

    run(["simons"], as_of_date=RUN_DATE, clock=clock, portfolio_conn=conn,
        llm_client=FakeLLMClient(responses=[HOLD_RESPONSE]), fake_llm=True)
    decision_id = conn.execute("SELECT id FROM decisions LIMIT 1").fetchone()["id"]
    conn.execute(
        "INSERT INTO pending_orders (agent_id, ticker, side, shares, reserved_amount_paise, "
        "decision_id, status, valid_for_date, created_at, updated_at) "
        "VALUES ('simons', 'TATAMOTORS', 'BUY', 10, 100000, ?, 'pending', '2026-10-17', ?, ?)",
        (decision_id, NOW, NOW),
    )

    second = run(["simons"], as_of_date=RUN_DATE, clock=clock, portfolio_conn=conn,
                 llm_client=FakeLLMClient(responses=[HOLD_RESPONSE]), fake_llm=True, force=True)
    assert second["simons"]["status"] == "REFUSED"
