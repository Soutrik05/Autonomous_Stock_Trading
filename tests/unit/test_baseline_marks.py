"""
Unit tests for baselines/marks_rules.py: rules-only baseline agent for Howard Marks (baseline-marks-rules).
Tests Method A contrarian filtering (RSI <= 45.0, dist_52w_low <= 35%, PE <= 30, D/E <= 1.0, CFO/PAT >= 0.60, ROCE >= 10%),
2.5x ATR volatility stops, 1:2.0 minimum RRR, mean reversion exits (RSI >= 65),
solvency/cash deterioration exits, breakeven ratcheting, and sector caps.
"""

import json
import sqlite3
from datetime import datetime

from baselines.marks_rules import run_baseline_marks
from core.clock import FakeClock
from tests.conftest import make_portfolio_db

NOW = "2026-10-16T22:00:00+05:30"
RUN_DATE = "2026-10-16"


def seed_marks_baseline_test(conn: sqlite3.Connection):
    conn.execute(
        "INSERT OR IGNORE INTO agents (id, name, philosophy, kind, starting_cash_paise, cash_paise, created_at, updated_at) "
        "VALUES ('baseline-marks-rules', 'Baseline Marks Rules', 'Contrarian Rules', 'BASELINE', 10000000, 10000000, ?, ?)",
        (NOW, NOW),
    )
    conn.execute(
        "INSERT OR IGNORE INTO agents (id, name, philosophy, kind, starting_cash_paise, cash_paise, created_at, updated_at) "
        "VALUES ('marks', 'Howard Marks', 'Contrarian', 'LLM', 10000000, 10000000, ?, ?)",
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
    conn.execute(
        "INSERT OR IGNORE INTO symbols (ticker, instrument_key, isin, company_name, sector, is_active) "
        "VALUES ('HDFCBANK', 'NSE_EQ|INE040A01034', 'INE040A01034', 'HDFC Bank Ltd', 'Banking', 1)"
    )
    # Add to Marks' watchlist
    conn.execute(
        "INSERT OR IGNORE INTO agent_watchlist (agent_id, ticker, sector, added_on, ttl_days, expires_on, intensity_score) "
        "VALUES ('marks', 'TATAMOTORS', 'Automobile', ?, 21, '2026-11-06', 0.88)",
        (RUN_DATE,),
    )
    conn.execute(
        "INSERT OR IGNORE INTO agent_watchlist (agent_id, ticker, sector, added_on, ttl_days, expires_on, intensity_score) "
        "VALUES ('marks', 'INFY', 'IT', ?, 21, '2026-11-06', 0.82)",
        (RUN_DATE,),
    )
    conn.execute(
        "INSERT OR IGNORE INTO agent_watchlist (agent_id, ticker, sector, added_on, ttl_days, expires_on, intensity_score) "
        "VALUES ('marks', 'TCS', 'IT', ?, 21, '2026-11-06', 0.78)",
        (RUN_DATE,),
    )
    conn.execute(
        "INSERT OR IGNORE INTO agent_watchlist (agent_id, ticker, sector, added_on, ttl_days, expires_on, intensity_score) "
        "VALUES ('marks', 'HDFCBANK', 'Banking', ?, 21, '2026-11-06', 0.74)",
        (RUN_DATE,),
    )


def test_baseline_marks_buys_when_all_contrarian_rules_pass():
    conn = make_portfolio_db()
    seed_marks_baseline_test(conn)
    clock = FakeClock(datetime(2026, 10, 16, 22, 0, 0))

    # TATAMOTORS passes full Howard Marks Method A Contrarian criteria:
    # RSI 38.0 (<= 45.0), dist_52w_low 15% (<= 35%), PE 18.0 (<= 30.0), D/E 0.45 (<= 1.0), CFO/PAT 0.95 (>= 0.60), ROCE 16% (>= 10%)
    tata_features = {
        "close": 500.0,
        "atr_14": 15.0,
        "rsi_14": 38.0,
        "dist_52w_low_pct": 15.0,
        "pe": 18.0,
        "pb": 2.2,
        "debt_to_equity": 0.45,
        "cfo_to_pat": 0.95,
        "roce_pct": 16.0,
        "news_sentiment": 0.05,
    }
    conn.execute(
        "INSERT INTO feature_snapshots (ticker, as_of_date, schema_version, features_json, created_at) "
        "VALUES ('TATAMOTORS', ?, 1, ?, ?)",
        (RUN_DATE, json.dumps(tata_features), NOW),
    )

    res = run_baseline_marks(RUN_DATE, clock, conn)
    assert res["status"] == "SUCCESS"
    assert res["decisions"] == 4

    tata_dec = conn.execute(
        "SELECT * FROM decisions WHERE agent_id = 'baseline-marks-rules' AND ticker = 'TATAMOTORS'"
    ).fetchone()
    assert tata_dec is not None
    assert tata_dec["source"] == "BASELINE"
    assert tata_dec["action"] == "BUY"
    assert "Contrarian Dislocation" in tata_dec["reasoning"]

    # Verify stop loss: close - 2.5 * ATR = 500 - 2.5*15 = 462.5 (46250 paise)
    # Entry High: close + 0.25 * ATR = 500 + 3.75 = 503.75 (50375 paise)
    # Target: close + max(2.0 * (503.75 - 462.5), 5.0 * 15) = 500 + max(82.5, 75) = 582.5 (58250 paise)
    assert tata_dec["stop_paise"] == 46250
    assert tata_dec["entry_high_paise"] == 50375
    assert tata_dec["target_paise"] == 58250

    # Verify 1:2.0 minimum Risk-to-Reward Ratio
    risk_paise = tata_dec["entry_high_paise"] - tata_dec["stop_paise"]
    reward_paise = tata_dec["target_paise"] - tata_dec["entry_high_paise"]
    assert reward_paise / risk_paise >= 1.90


def test_baseline_marks_holds_when_rsi_not_oversold():
    conn = make_portfolio_db()
    seed_marks_baseline_test(conn)
    clock = FakeClock(datetime(2026, 10, 16, 22, 0, 0))

    # RSI = 52.0 (> 45.0) -> Not cyclically oversold/depressed
    warm_features = {
        "close": 500.0,
        "atr_14": 15.0,
        "rsi_14": 52.0,
        "dist_52w_low_pct": 15.0,
        "pe": 18.0,
        "debt_to_equity": 0.45,
        "cfo_to_pat": 0.95,
        "roce_pct": 16.0,
    }
    conn.execute(
        "INSERT INTO feature_snapshots (ticker, as_of_date, schema_version, features_json, created_at) "
        "VALUES ('TATAMOTORS', ?, 1, ?, ?)",
        (RUN_DATE, json.dumps(warm_features), NOW),
    )

    res = run_baseline_marks(RUN_DATE, clock, conn)
    assert res["status"] == "SUCCESS"
    dec = conn.execute(
        "SELECT * FROM decisions WHERE agent_id = 'baseline-marks-rules' AND ticker = 'TATAMOTORS'"
    ).fetchone()
    assert dec["action"] == "HOLD"
    assert "RSI 52.0 > 45.0" in dec["reasoning"]


def test_baseline_marks_holds_when_dist_52w_low_too_high():
    conn = make_portfolio_db()
    seed_marks_baseline_test(conn)
    clock = FakeClock(datetime(2026, 10, 16, 22, 0, 0))

    # dist_52w_low_pct = 45.0 (> 35.0%) -> Stock is near highs, not cyclically beaten down
    high_features = {
        "close": 500.0,
        "atr_14": 15.0,
        "rsi_14": 40.0,
        "dist_52w_low_pct": 45.0,
        "pe": 18.0,
        "debt_to_equity": 0.45,
        "cfo_to_pat": 0.95,
        "roce_pct": 16.0,
    }
    conn.execute(
        "INSERT INTO feature_snapshots (ticker, as_of_date, schema_version, features_json, created_at) "
        "VALUES ('TATAMOTORS', ?, 1, ?, ?)",
        (RUN_DATE, json.dumps(high_features), NOW),
    )

    res = run_baseline_marks(RUN_DATE, clock, conn)
    assert res["status"] == "SUCCESS"
    dec = conn.execute(
        "SELECT * FROM decisions WHERE agent_id = 'baseline-marks-rules' AND ticker = 'TATAMOTORS'"
    ).fetchone()
    assert dec["action"] == "HOLD"
    assert "dist_52w_low 45.0% > 35%" in dec["reasoning"]


def test_baseline_marks_holds_when_pe_too_high():
    conn = make_portfolio_db()
    seed_marks_baseline_test(conn)
    clock = FakeClock(datetime(2026, 10, 16, 22, 0, 0))

    # P/E = 42.0 (> 30.0) -> No valuation margin of safety
    rich_features = {
        "close": 500.0,
        "atr_14": 15.0,
        "rsi_14": 38.0,
        "dist_52w_low_pct": 15.0,
        "pe": 42.0,
        "debt_to_equity": 0.45,
        "cfo_to_pat": 0.95,
        "roce_pct": 16.0,
    }
    conn.execute(
        "INSERT INTO feature_snapshots (ticker, as_of_date, schema_version, features_json, created_at) "
        "VALUES ('TATAMOTORS', ?, 1, ?, ?)",
        (RUN_DATE, json.dumps(rich_features), NOW),
    )

    res = run_baseline_marks(RUN_DATE, clock, conn)
    assert res["status"] == "SUCCESS"
    dec = conn.execute(
        "SELECT * FROM decisions WHERE agent_id = 'baseline-marks-rules' AND ticker = 'TATAMOTORS'"
    ).fetchone()
    assert dec["action"] == "HOLD"
    assert "PE 42.0 > 30.0" in dec["reasoning"]


def test_baseline_marks_holds_when_debt_too_high():
    conn = make_portfolio_db()
    seed_marks_baseline_test(conn)
    clock = FakeClock(datetime(2026, 10, 16, 22, 0, 0))

    # D/E = 1.35 (> 1.0) -> Solvency failure; Marks mandates survivability
    overleveraged_features = {
        "close": 500.0,
        "atr_14": 15.0,
        "rsi_14": 38.0,
        "dist_52w_low_pct": 15.0,
        "pe": 18.0,
        "debt_to_equity": 1.35,
        "cfo_to_pat": 0.95,
        "roce_pct": 16.0,
    }
    conn.execute(
        "INSERT INTO feature_snapshots (ticker, as_of_date, schema_version, features_json, created_at) "
        "VALUES ('TATAMOTORS', ?, 1, ?, ?)",
        (RUN_DATE, json.dumps(overleveraged_features), NOW),
    )

    res = run_baseline_marks(RUN_DATE, clock, conn)
    assert res["status"] == "SUCCESS"
    dec = conn.execute(
        "SELECT * FROM decisions WHERE agent_id = 'baseline-marks-rules' AND ticker = 'TATAMOTORS'"
    ).fetchone()
    assert dec["action"] == "HOLD"
    assert "D/E 1.35 > 1.0" in dec["reasoning"]


def test_baseline_marks_holds_when_cfo_to_pat_fails():
    conn = make_portfolio_db()
    seed_marks_baseline_test(conn)
    clock = FakeClock(datetime(2026, 10, 16, 22, 0, 0))

    # CFO/PAT = 0.45 (< 0.60) -> Cash flow reality check fails
    low_cash_features = {
        "close": 500.0,
        "atr_14": 15.0,
        "rsi_14": 38.0,
        "dist_52w_low_pct": 15.0,
        "pe": 18.0,
        "debt_to_equity": 0.45,
        "cfo_to_pat": 0.45,
        "roce_pct": 16.0,
    }
    conn.execute(
        "INSERT INTO feature_snapshots (ticker, as_of_date, schema_version, features_json, created_at) "
        "VALUES ('TATAMOTORS', ?, 1, ?, ?)",
        (RUN_DATE, json.dumps(low_cash_features), NOW),
    )

    res = run_baseline_marks(RUN_DATE, clock, conn)
    assert res["status"] == "SUCCESS"
    dec = conn.execute(
        "SELECT * FROM decisions WHERE agent_id = 'baseline-marks-rules' AND ticker = 'TATAMOTORS'"
    ).fetchone()
    assert dec["action"] == "HOLD"
    assert "CFO/PAT 0.45 < 0.60" in dec["reasoning"]


def test_baseline_marks_holds_on_severe_negative_news():
    conn = make_portfolio_db()
    seed_marks_baseline_test(conn)
    clock = FakeClock(datetime(2026, 10, 16, 22, 0, 0))

    # Severe negative news sentiment (-0.35 < -0.25) -> Governance/fraud veto
    bad_news_features = {
        "close": 500.0,
        "atr_14": 15.0,
        "rsi_14": 38.0,
        "dist_52w_low_pct": 15.0,
        "pe": 18.0,
        "debt_to_equity": 0.45,
        "cfo_to_pat": 0.95,
        "roce_pct": 16.0,
        "news_sentiment": -0.35,
    }
    conn.execute(
        "INSERT INTO feature_snapshots (ticker, as_of_date, schema_version, features_json, created_at) "
        "VALUES ('TATAMOTORS', ?, 1, ?, ?)",
        (RUN_DATE, json.dumps(bad_news_features), NOW),
    )

    res = run_baseline_marks(RUN_DATE, clock, conn)
    assert res["status"] == "SUCCESS"
    dec = conn.execute(
        "SELECT * FROM decisions WHERE agent_id = 'baseline-marks-rules' AND ticker = 'TATAMOTORS'"
    ).fetchone()
    assert dec["action"] == "HOLD"
    assert "governance/fraud existential risk" in dec["reasoning"]


def test_baseline_marks_exits_on_target_reached():
    conn = make_portfolio_db()
    seed_marks_baseline_test(conn)
    clock = FakeClock(datetime(2026, 10, 16, 22, 0, 0))

    # Open position with target 58000 paise (Rs 580)
    conn.execute(
        "INSERT INTO positions (agent_id, ticker, sector, shares, avg_entry_price_paise, stop_paise, target_paise, last_price_paise, status, entry_date) "
        "VALUES ('baseline-marks-rules', 'TATAMOTORS', 'Automobile', 10, 50000, 46000, 58000, 50000, 'OPEN', '2026-09-01')"
    )
    # Current close is 585.0 (exceeds target 580.0)
    current_features = {
        "close": 585.0,
        "atr_14": 15.0,
        "rsi_14": 60.0,
        "cfo_to_pat": 0.9,
        "debt_to_equity": 0.4,
    }
    conn.execute(
        "INSERT INTO feature_snapshots (ticker, as_of_date, schema_version, features_json, created_at) "
        "VALUES ('TATAMOTORS', ?, 1, ?, ?)",
        (RUN_DATE, json.dumps(current_features), NOW),
    )

    res = run_baseline_marks(RUN_DATE, clock, conn)
    assert res["status"] == "SUCCESS"
    dec = conn.execute(
        "SELECT * FROM decisions WHERE agent_id = 'baseline-marks-rules' AND ticker = 'TATAMOTORS'"
    ).fetchone()
    assert dec["action"] == "ADJUST"
    assert dec["stop_paise"] >= 50000  # Ratcheted above entry (500.0) to lock in profit
    assert dec["target_paise"] > 58500  # Trailed above current price
    assert "TARGET_REACHED" in dec["reasoning"]


def test_baseline_marks_exits_on_mean_reversion_completed():
    conn = make_portfolio_db()
    seed_marks_baseline_test(conn)
    clock = FakeClock(datetime(2026, 10, 16, 22, 0, 0))

    # Open position entered at Rs 500. Stop is 460, target is 600.
    conn.execute(
        "INSERT INTO positions (agent_id, ticker, sector, shares, avg_entry_price_paise, stop_paise, target_paise, last_price_paise, status, entry_date) "
        "VALUES ('baseline-marks-rules', 'TATAMOTORS', 'Automobile', 10, 50000, 46000, 60000, 50000, 'OPEN', '2026-09-01')"
    )
    # Stock rallies from 500 to 550, and RSI reaches 68.0 (>= 65.0: mean reversion completed)
    mean_rev_features = {
        "close": 550.0,
        "atr_14": 15.0,
        "rsi_14": 68.0,
        "cfo_to_pat": 0.9,
        "debt_to_equity": 0.4,
    }
    conn.execute(
        "INSERT INTO feature_snapshots (ticker, as_of_date, schema_version, features_json, created_at) "
        "VALUES ('TATAMOTORS', ?, 1, ?, ?)",
        (RUN_DATE, json.dumps(mean_rev_features), NOW),
    )

    res = run_baseline_marks(RUN_DATE, clock, conn)
    assert res["status"] == "SUCCESS"
    dec = conn.execute(
        "SELECT * FROM decisions WHERE agent_id = 'baseline-marks-rules' AND ticker = 'TATAMOTORS'"
    ).fetchone()
    assert dec["action"] == "SELL"
    assert "mean reversion completed" in dec["reasoning"]


def test_baseline_marks_exits_on_story_deterioration():
    conn = make_portfolio_db()
    seed_marks_baseline_test(conn)
    clock = FakeClock(datetime(2026, 10, 16, 22, 0, 0))

    # Open position entered at Rs 500.
    conn.execute(
        "INSERT INTO positions (agent_id, ticker, sector, shares, avg_entry_price_paise, stop_paise, target_paise, last_price_paise, status, entry_date) "
        "VALUES ('baseline-marks-rules', 'TATAMOTORS', 'Automobile', 10, 50000, 45000, 60000, 50000, 'OPEN', '2026-09-01')"
    )
    # Severe cash bleed occurs: CFO/PAT collapses to 0.30 (< 0.40)
    broken_features = {
        "close": 490.0,
        "atr_14": 15.0,
        "rsi_14": 42.0,
        "cfo_to_pat": 0.30,
        "debt_to_equity": 0.50,
    }
    conn.execute(
        "INSERT INTO feature_snapshots (ticker, as_of_date, schema_version, features_json, created_at) "
        "VALUES ('TATAMOTORS', ?, 1, ?, ?)",
        (RUN_DATE, json.dumps(broken_features), NOW),
    )

    res = run_baseline_marks(RUN_DATE, clock, conn)
    assert res["status"] == "SUCCESS"
    dec = conn.execute(
        "SELECT * FROM decisions WHERE agent_id = 'baseline-marks-rules' AND ticker = 'TATAMOTORS'"
    ).fetchone()
    assert dec["action"] == "SELL"
    assert "balance sheet / cash flow deterioration" in dec["reasoning"]


def test_baseline_marks_ratchets_stop_to_breakeven_on_profit():
    conn = make_portfolio_db()
    seed_marks_baseline_test(conn)
    clock = FakeClock(datetime(2026, 10, 16, 22, 0, 0))

    # Entry at Rs 500, initial stop at Rs 462.5 (2.5x ATR = 37.5). Target Rs 580.
    conn.execute(
        "INSERT INTO positions (agent_id, ticker, sector, shares, avg_entry_price_paise, stop_paise, target_paise, last_price_paise, status, entry_date) "
        "VALUES ('baseline-marks-rules', 'TATAMOTORS', 'Automobile', 10, 50000, 46250, 58000, 50000, 'OPEN', '2026-10-01')"
    )
    # Price advances to Rs 540 (+40 profit >= 2.5 * ATR [2.5*15 = 37.5])
    # RSI is 58.0 (< 65 so mean reversion exit does not trigger)
    gaining_features = {
        "close": 540.0,
        "atr_14": 15.0,
        "rsi_14": 58.0,
        "cfo_to_pat": 0.95,
        "debt_to_equity": 0.45,
    }
    conn.execute(
        "INSERT INTO feature_snapshots (ticker, as_of_date, schema_version, features_json, created_at) "
        "VALUES ('TATAMOTORS', ?, 1, ?, ?)",
        (RUN_DATE, json.dumps(gaining_features), NOW),
    )

    res = run_baseline_marks(RUN_DATE, clock, conn)
    assert res["status"] == "SUCCESS"
    dec = conn.execute(
        "SELECT * FROM decisions WHERE agent_id = 'baseline-marks-rules' AND ticker = 'TATAMOTORS'"
    ).fetchone()
    assert dec["action"] == "ADJUST"
    assert dec["stop_paise"] == 50000  # Ratcheted to entry price
    assert "ratcheted stop to breakeven" in dec["reasoning"]


def test_baseline_marks_enforces_sector_cap():
    conn = make_portfolio_db()
    seed_marks_baseline_test(conn)
    clock = FakeClock(datetime(2026, 10, 16, 22, 0, 0))

    # Add 2 open positions in IT sector already (INFY and TCS)
    conn.execute(
        "INSERT INTO positions (agent_id, ticker, sector, shares, avg_entry_price_paise, stop_paise, target_paise, last_price_paise, status, entry_date) "
        "VALUES ('baseline-marks-rules', 'INFY', 'IT', 10, 150000, 142000, 168000, 150000, 'OPEN', '2026-10-01')"
    )
    conn.execute(
        "INSERT INTO positions (agent_id, ticker, sector, shares, avg_entry_price_paise, stop_paise, target_paise, last_price_paise, status, entry_date) "
        "VALUES ('baseline-marks-rules', 'TCS', 'IT', 10, 350000, 335000, 385000, 350000, 'OPEN', '2026-10-01')"
    )

    # A 3rd IT stock (WIPRO) is added to symbols and watchlist
    conn.execute(
        "INSERT OR IGNORE INTO symbols (ticker, instrument_key, isin, company_name, sector, is_active) "
        "VALUES ('WIPRO', 'NSE_EQ|INE075A01022', 'INE075A01022', 'Wipro Ltd', 'IT', 1)"
    )
    conn.execute(
        "INSERT OR IGNORE INTO agent_watchlist (agent_id, ticker, sector, added_on, ttl_days, expires_on, intensity_score) "
        "VALUES ('marks', 'WIPRO', 'IT', ?, 21, '2026-11-06', 0.90)",
        (RUN_DATE,),
    )
    wipro_features = {
        "close": 400.0,
        "atr_14": 12.0,
        "rsi_14": 35.0,
        "dist_52w_low_pct": 10.0,
        "pe": 16.0,
        "debt_to_equity": 0.20,
        "cfo_to_pat": 0.95,
        "roce_pct": 15.0,
    }
    conn.execute(
        "INSERT INTO feature_snapshots (ticker, as_of_date, schema_version, features_json, created_at) "
        "VALUES ('WIPRO', ?, 1, ?, ?)",
        (RUN_DATE, json.dumps(wipro_features), NOW),
    )

    res = run_baseline_marks(RUN_DATE, clock, conn)
    assert res["status"] == "SUCCESS"
    dec = conn.execute(
        "SELECT * FROM decisions WHERE agent_id = 'baseline-marks-rules' AND ticker = 'WIPRO'"
    ).fetchone()
    assert dec["action"] == "HOLD"
    assert "sector IT reached cap" in dec["reasoning"]
