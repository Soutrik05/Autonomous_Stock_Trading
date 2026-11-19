"""
Unit tests for baselines/varsity_rules.py: rules-only baseline agent for Zerodha Varsity.
Tests dual technical-fundamental confluence, 1:1.5 RRR floor, 2.0x ATR stop loss,
breakeven ratcheting, sector caps, and exit triggers.
"""

import json
import sqlite3
from datetime import datetime

from baselines.varsity_rules import run_baseline_varsity
from core.clock import FakeClock
from tests.conftest import make_portfolio_db

NOW = "2026-10-16T22:00:00+05:30"
RUN_DATE = "2026-10-16"


def seed_varsity_baseline_test(conn: sqlite3.Connection):
    conn.execute(
        "INSERT OR IGNORE INTO agents (id, name, philosophy, kind, starting_cash_paise, cash_paise, created_at, updated_at) "
        "VALUES ('baseline-varsity-rules', 'Baseline Varsity Rules', 'Rules', 'BASELINE', 10000000, 10000000, ?, ?)",
        (NOW, NOW),
    )
    conn.execute(
        "INSERT OR IGNORE INTO agents (id, name, philosophy, kind, starting_cash_paise, cash_paise, created_at, updated_at) "
        "VALUES ('varsity', 'StockMinds Core', 'Confluence', 'LLM', 10000000, 10000000, ?, ?)",
        (NOW, NOW),
    )
    conn.execute(
        "INSERT OR IGNORE INTO pipeline_runs (job, run_date, status, started_at, finished_at) "
        "VALUES ('watchlist', ?, 'SUCCESS', ?, ?)",
        (RUN_DATE, NOW, NOW),
    )
    conn.execute(
        "INSERT OR IGNORE INTO symbols (ticker, instrument_key, isin, company_name, sector, is_active) "
        "VALUES ('TATAMOTORS', 'NSE_EQ|INE155A01022', 'INE155A01022', 'Tata Motors Ltd', 'Automobile', 1)"
    )
    conn.execute(
        "INSERT OR IGNORE INTO symbols (ticker, instrument_key, isin, company_name, sector, is_active) "
        "VALUES ('INFY', 'NSE_EQ|INE009A01021', 'INE009A01021', 'Infosys Ltd', 'IT', 1)"
    )
    conn.execute(
        "INSERT OR IGNORE INTO symbols (ticker, instrument_key, isin, company_name, sector, is_active) "
        "VALUES ('TCS', 'NSE_EQ|INE467B01029', 'INE467B01029', 'Tata Consultancy Services', 'IT', 1)"
    )
    # Add to Varsity's watchlist
    conn.execute(
        "INSERT OR IGNORE INTO agent_watchlist (agent_id, ticker, sector, added_on, ttl_days, expires_on, intensity_score) "
        "VALUES ('varsity', 'TATAMOTORS', 'Automobile', ?, 14, '2026-10-30', 0.85)",
        (RUN_DATE,),
    )
    conn.execute(
        "INSERT OR IGNORE INTO agent_watchlist (agent_id, ticker, sector, added_on, ttl_days, expires_on, intensity_score) "
        "VALUES ('varsity', 'INFY', 'IT', ?, 14, '2026-10-30', 0.80)",
        (RUN_DATE,),
    )
    conn.execute(
        "INSERT OR IGNORE INTO agent_watchlist (agent_id, ticker, sector, added_on, ttl_days, expires_on, intensity_score) "
        "VALUES ('varsity', 'TCS', 'IT', ?, 14, '2026-10-30', 0.75)",
        (RUN_DATE,),
    )


def test_baseline_varsity_buys_when_all_rules_pass():
    conn = make_portfolio_db()
    seed_varsity_baseline_test(conn)
    clock = FakeClock(datetime(2026, 10, 16, 22, 0, 0))

    # TATAMOTORS passes full dual confluence:
    # 20 EMA > 50 EMA, close > 200 EMA, RSI 58 (sweet spot), Volume 1.4x, ROCE 18%, ROE 16%, D/E 0.6, DCF +15%
    tata_features = {
        "close": 1000.0,
        "ema_20": 980.0,
        "ema_50": 950.0,
        "ema_200": 900.0,
        "ema_20_above_50": True,
        "rsi_14": 58.0,
        "volume_surge": 1.4,
        "atr_14": 20.0,
        "roce_pct": 18.0,
        "roe_pct": 16.0,
        "debt_to_equity": 0.6,
        "dcf_discount_pct": 15.0,
        "news_sentiment": 0.15,
    }
    conn.execute(
        "INSERT INTO feature_snapshots (ticker, as_of_date, schema_version, features_json, created_at) "
        "VALUES ('TATAMOTORS', ?, 1, ?, ?)",
        (RUN_DATE, json.dumps(tata_features), NOW),
    )

    res = run_baseline_varsity(RUN_DATE, clock, conn)
    assert res["status"] == "SUCCESS"
    assert res["decisions"] == 3

    tata_dec = conn.execute(
        "SELECT * FROM decisions WHERE agent_id = 'baseline-varsity-rules' AND ticker = 'TATAMOTORS'"
    ).fetchone()
    assert tata_dec is not None
    assert tata_dec["source"] == "BASELINE"
    assert tata_dec["action"] == "BUY"

    # Verify INFY and TCS (which had no feature snapshot) were evaluated as HOLD
    for other in ("INFY", "TCS"):
        dec = conn.execute(
            "SELECT * FROM decisions WHERE agent_id = 'baseline-varsity-rules' AND ticker = ?",
            (other,),
        ).fetchone()
        assert dec["action"] == "HOLD"

    # Stop Loss: close - 2.0 * ATR = 1000 - 2*20 = 960 (96000 paise)
    # Entry High: 1000 + 0.25 * 20 = 1005 (100500 paise)
    # Risk distance: 1005 - 960 = 45
    # Target: close + max(1.75 * 45, 3.5 * 20) = 1000 + 78.75 = 1078.75 (107875 paise)
    assert tata_dec["stop_paise"] == 96000
    assert tata_dec["entry_high_paise"] == 100500
    assert tata_dec["target_paise"] >= 107000

    # Verify 1:1.5 minimum RRR
    risk_paise = tata_dec["entry_high_paise"] - tata_dec["stop_paise"]
    reward_paise = tata_dec["target_paise"] - tata_dec["entry_high_paise"]
    assert reward_paise / risk_paise >= 1.50


def test_baseline_varsity_holds_when_technical_fails():
    conn = make_portfolio_db()
    seed_varsity_baseline_test(conn)
    clock = FakeClock(datetime(2026, 10, 16, 22, 0, 0))

    # Good fundamentals, but RSI is overextended at 76 (> 68 overbought FOMO)
    overbought_features = {
        "close": 1000.0,
        "ema_20": 980.0,
        "ema_50": 950.0,
        "ema_200": 900.0,
        "ema_20_above_50": True,
        "rsi_14": 76.0,
        "volume_surge": 1.4,
        "atr_14": 20.0,
        "roce_pct": 20.0,
        "roe_pct": 18.0,
        "debt_to_equity": 0.5,
        "dcf_discount_pct": 10.0,
    }
    conn.execute(
        "INSERT INTO feature_snapshots (ticker, as_of_date, schema_version, features_json, created_at) "
        "VALUES ('TATAMOTORS', ?, 1, ?, ?)",
        (RUN_DATE, json.dumps(overbought_features), NOW),
    )

    res = run_baseline_varsity(RUN_DATE, clock, conn)
    assert res["status"] == "SUCCESS"
    dec = conn.execute(
        "SELECT * FROM decisions WHERE agent_id = 'baseline-varsity-rules' AND ticker = 'TATAMOTORS'"
    ).fetchone()
    assert dec["action"] == "HOLD"
    assert "technical confluence failed" in dec["reasoning"]


def test_baseline_varsity_holds_when_fundamental_fails():
    conn = make_portfolio_db()
    seed_varsity_baseline_test(conn)
    clock = FakeClock(datetime(2026, 10, 16, 22, 0, 0))

    # Great technical chart, but high debt (D/E = 2.5 > 1.5) and poor ROCE (6% < 12%)
    fragile_fund_features = {
        "close": 1000.0,
        "ema_20": 980.0,
        "ema_50": 950.0,
        "ema_200": 900.0,
        "ema_20_above_50": True,
        "rsi_14": 56.0,
        "volume_surge": 1.5,
        "atr_14": 20.0,
        "roce_pct": 6.0,
        "roe_pct": 5.0,
        "debt_to_equity": 2.5,
        "dcf_discount_pct": -30.0,
    }
    conn.execute(
        "INSERT INTO feature_snapshots (ticker, as_of_date, schema_version, features_json, created_at) "
        "VALUES ('TATAMOTORS', ?, 1, ?, ?)",
        (RUN_DATE, json.dumps(fragile_fund_features), NOW),
    )

    res = run_baseline_varsity(RUN_DATE, clock, conn)
    assert res["status"] == "SUCCESS"
    dec = conn.execute(
        "SELECT * FROM decisions WHERE agent_id = 'baseline-varsity-rules' AND ticker = 'TATAMOTORS'"
    ).fetchone()
    assert dec["action"] == "HOLD"
    assert "fundamental quality failed" in dec["reasoning"]


def test_baseline_varsity_exits_on_target_reached():
    conn = make_portfolio_db()
    seed_varsity_baseline_test(conn)
    clock = FakeClock(datetime(2026, 10, 16, 22, 0, 0))

    # Create an open position with target 108000 paise (Rs 1080)
    conn.execute(
        "INSERT INTO positions (agent_id, ticker, sector, shares, avg_entry_price_paise, stop_paise, target_paise, last_price_paise, status, entry_date) "
        "VALUES ('baseline-varsity-rules', 'TATAMOTORS', 'Automobile', 10, 100000, 96000, 108000, 100000, 'OPEN', '2026-10-01')"
    )
    # Current close is 1085.0 (exceeds target 1080.0)
    current_features = {
        "close": 1085.0,
        "ema_20": 1050.0,
        "ema_50": 1020.0,
        "ema_200": 950.0,
        "ema_20_above_50": True,
        "rsi_14": 65.0,
        "atr_14": 20.0,
    }
    conn.execute(
        "INSERT INTO feature_snapshots (ticker, as_of_date, schema_version, features_json, created_at) "
        "VALUES ('TATAMOTORS', ?, 1, ?, ?)",
        (RUN_DATE, json.dumps(current_features), NOW),
    )

    res = run_baseline_varsity(RUN_DATE, clock, conn)
    assert res["status"] == "SUCCESS"
    dec = conn.execute(
        "SELECT * FROM decisions WHERE agent_id = 'baseline-varsity-rules' AND ticker = 'TATAMOTORS'"
    ).fetchone()
    assert dec["action"] == "ADJUST"
    assert dec["stop_paise"] >= 100000  # Ratcheted above entry (1000.0) to lock in profit
    assert dec["target_paise"] > 108500  # Trailed above current price
    assert "TARGET_REACHED" in dec["reasoning"]


def test_baseline_varsity_exits_on_technical_breakdown():
    conn = make_portfolio_db()
    seed_varsity_baseline_test(conn)
    clock = FakeClock(datetime(2026, 10, 16, 22, 0, 0))

    # Open position with stop set low at 85000 paise so stop is not triggered before trend breakdown
    conn.execute(
        "INSERT INTO positions (agent_id, ticker, sector, shares, avg_entry_price_paise, stop_paise, target_paise, last_price_paise, status, entry_date) "
        "VALUES ('baseline-varsity-rules', 'TATAMOTORS', 'Automobile', 10, 100000, 85000, 110000, 100000, 'OPEN', '2026-10-01')"
    )
    # Price breaks down below 200 EMA (The Mothership) and 20 EMA crosses below 50 EMA
    broken_features = {
        "close": 890.0,
        "ema_20": 910.0,
        "ema_50": 930.0,
        "ema_200": 920.0,
        "ema_20_above_50": False,
        "rsi_14": 35.0,
        "atr_14": 25.0,
    }
    conn.execute(
        "INSERT INTO feature_snapshots (ticker, as_of_date, schema_version, features_json, created_at) "
        "VALUES ('TATAMOTORS', ?, 1, ?, ?)",
        (RUN_DATE, json.dumps(broken_features), NOW),
    )

    res = run_baseline_varsity(RUN_DATE, clock, conn)
    assert res["status"] == "SUCCESS"
    dec = conn.execute(
        "SELECT * FROM decisions WHERE agent_id = 'baseline-varsity-rules' AND ticker = 'TATAMOTORS'"
    ).fetchone()
    assert dec["action"] == "SELL"
    assert "technical trend breakdown" in dec["reasoning"]


def test_baseline_varsity_ratchets_stop_to_breakeven_on_profit():
    conn = make_portfolio_db()
    seed_varsity_baseline_test(conn)
    clock = FakeClock(datetime(2026, 10, 16, 22, 0, 0))

    # Entry at Rs 1000, initial stop at Rs 960 (2.0x ATR = 40). Target Rs 1100.
    conn.execute(
        "INSERT INTO positions (agent_id, ticker, sector, shares, avg_entry_price_paise, stop_paise, target_paise, last_price_paise, status, entry_date) "
        "VALUES ('baseline-varsity-rules', 'TATAMOTORS', 'Automobile', 10, 100000, 96000, 110000, 100000, 'OPEN', '2026-10-01')"
    )
    # Price moves to Rs 1045 (+45 profit >= 2.0 * ATR = 40)
    favorable_features = {
        "close": 1045.0,
        "ema_20": 1020.0,
        "ema_50": 990.0,
        "ema_200": 920.0,
        "ema_20_above_50": True,
        "rsi_14": 62.0,
        "atr_14": 20.0,
    }
    conn.execute(
        "INSERT INTO feature_snapshots (ticker, as_of_date, schema_version, features_json, created_at) "
        "VALUES ('TATAMOTORS', ?, 1, ?, ?)",
        (RUN_DATE, json.dumps(favorable_features), NOW),
    )

    res = run_baseline_varsity(RUN_DATE, clock, conn)
    assert res["status"] == "SUCCESS"
    dec = conn.execute(
        "SELECT * FROM decisions WHERE agent_id = 'baseline-varsity-rules' AND ticker = 'TATAMOTORS'"
    ).fetchone()
    assert dec["action"] == "ADJUST"
    assert dec["stop_paise"] == 100000  # Ratcheted to entry price (breakeven)
    assert "ratcheted stop to breakeven" in dec["reasoning"]
