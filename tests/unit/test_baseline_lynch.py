"""
Unit tests for baselines/lynch_rules.py: rules-only baseline agent for Peter Lynch.
Tests GARP candidate filtering (PEG <= 1.2, ROCE >= 12%, D/E <= 0.8, CFO/PAT >= 0.7, Growth >= 8%),
2.5x ATR volatility stops, 1:2.0 minimum RRR, valuation exits (PEG >= 1.8),
fundamental deterioration exits, breakeven ratcheting, and 5-position concentration.
"""

import json
import sqlite3
from datetime import datetime

from baselines.lynch_rules import run_baseline_lynch
from core.clock import FakeClock
from tests.conftest import make_portfolio_db

NOW = "2026-10-16T22:00:00+05:30"
RUN_DATE = "2026-10-16"


def seed_lynch_baseline_test(conn: sqlite3.Connection):
    conn.execute(
        "INSERT OR IGNORE INTO agents (id, name, philosophy, kind, starting_cash_paise, cash_paise, created_at, updated_at) "
        "VALUES ('baseline-lynch-rules', 'Baseline Lynch Rules', 'GARP Rules', 'BASELINE', 10000000, 10000000, ?, ?)",
        (NOW, NOW),
    )
    conn.execute(
        "INSERT OR IGNORE INTO agents (id, name, philosophy, kind, starting_cash_paise, cash_paise, created_at, updated_at) "
        "VALUES ('lynch', 'Peter Lynch', 'GARP', 'LLM', 10000000, 10000000, ?, ?)",
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
    # Add to Lynch's watchlist
    conn.execute(
        "INSERT OR IGNORE INTO agent_watchlist (agent_id, ticker, sector, added_on, ttl_days, expires_on, intensity_score) "
        "VALUES ('lynch', 'TATAMOTORS', 'Automobile', ?, 21, '2026-11-06', 0.88)",
        (RUN_DATE,),
    )
    conn.execute(
        "INSERT OR IGNORE INTO agent_watchlist (agent_id, ticker, sector, added_on, ttl_days, expires_on, intensity_score) "
        "VALUES ('lynch', 'INFY', 'IT', ?, 21, '2026-11-06', 0.82)",
        (RUN_DATE,),
    )
    conn.execute(
        "INSERT OR IGNORE INTO agent_watchlist (agent_id, ticker, sector, added_on, ttl_days, expires_on, intensity_score) "
        "VALUES ('lynch', 'TCS', 'IT', ?, 21, '2026-11-06', 0.78)",
        (RUN_DATE,),
    )
    conn.execute(
        "INSERT OR IGNORE INTO agent_watchlist (agent_id, ticker, sector, added_on, ttl_days, expires_on, intensity_score) "
        "VALUES ('lynch', 'HDFCBANK', 'Banking', ?, 21, '2026-11-06', 0.74)",
        (RUN_DATE,),
    )


def test_baseline_lynch_buys_when_all_garp_rules_pass():
    conn = make_portfolio_db()
    seed_lynch_baseline_test(conn)
    clock = FakeClock(datetime(2026, 10, 16, 22, 0, 0))

    # TATAMOTORS passes full Peter Lynch GARP criteria:
    # PEG 0.85 (<= 1.20), ROCE 22.0% (>= 12%), D/E 0.35 (<= 0.80), CFO/PAT 1.15 (>= 0.70), PAT growth 24% (Fast Grower)
    tata_features = {
        "close": 1000.0,
        "atr_14": 20.0,
        "peg": 0.85,
        "roce_pct": 22.0,
        "roe_pct": 20.0,
        "debt_to_equity": 0.35,
        "cfo_to_pat": 1.15,
        "pat_growth_yoy_pct": 24.0,
        "promoter_holding_pct": 46.5,
        "news_sentiment": 0.10,
    }
    conn.execute(
        "INSERT INTO feature_snapshots (ticker, as_of_date, schema_version, features_json, created_at) "
        "VALUES ('TATAMOTORS', ?, 1, ?, ?)",
        (RUN_DATE, json.dumps(tata_features), NOW),
    )

    res = run_baseline_lynch(RUN_DATE, clock, conn)
    assert res["status"] == "SUCCESS"
    assert res["decisions"] == 4

    tata_dec = conn.execute(
        "SELECT * FROM decisions WHERE agent_id = 'baseline-lynch-rules' AND ticker = 'TATAMOTORS'"
    ).fetchone()
    assert tata_dec is not None
    assert tata_dec["source"] == "BASELINE"
    assert tata_dec["action"] == "BUY"
    assert "Fast Grower" in tata_dec["reasoning"]

    # Verify stop loss: close - 2.5 * ATR = 1000 - 2.5*20 = 950 (95000 paise)
    # Entry High: close + 0.25 * ATR = 1000 + 5 = 1005 (100500 paise)
    # Target: close + max(2.25 * (1005 - 950), 5.5 * 20) = 1000 + 123.75 = 1123.75 (112375 paise)
    assert tata_dec["stop_paise"] == 93000
    assert tata_dec["entry_high_paise"] == 100500
    assert tata_dec["target_paise"] >= 112000

    # Verify 1:2.0 minimum Risk-to-Reward Ratio
    risk_paise = tata_dec["entry_high_paise"] - tata_dec["stop_paise"]
    reward_paise = tata_dec["target_paise"] - tata_dec["entry_high_paise"]
    assert reward_paise / risk_paise >= 2.0


def test_baseline_lynch_holds_when_peg_too_high():
    conn = make_portfolio_db()
    seed_lynch_baseline_test(conn)
    clock = FakeClock(datetime(2026, 10, 16, 22, 0, 0))

    # High quality, but PEG = 1.65 (> 1.20)
    expensive_features = {
        "close": 1000.0,
        "atr_14": 20.0,
        "peg": 1.65,
        "roce_pct": 25.0,
        "roe_pct": 22.0,
        "debt_to_equity": 0.20,
        "cfo_to_pat": 1.10,
        "pat_growth_yoy_pct": 20.0,
    }
    conn.execute(
        "INSERT INTO feature_snapshots (ticker, as_of_date, schema_version, features_json, created_at) "
        "VALUES ('TATAMOTORS', ?, 1, ?, ?)",
        (RUN_DATE, json.dumps(expensive_features), NOW),
    )

    res = run_baseline_lynch(RUN_DATE, clock, conn)
    assert res["status"] == "SUCCESS"
    dec = conn.execute(
        "SELECT * FROM decisions WHERE agent_id = 'baseline-lynch-rules' AND ticker = 'TATAMOTORS'"
    ).fetchone()
    assert dec["action"] == "HOLD"
    assert "PEG 1.65 exceeds 1.20" in dec["reasoning"]


def test_baseline_lynch_holds_when_debt_too_high():
    conn = make_portfolio_db()
    seed_lynch_baseline_test(conn)
    clock = FakeClock(datetime(2026, 10, 16, 22, 0, 0))

    # Low PEG, but Debt/Equity = 1.45 (> 0.80)
    indebted_features = {
        "close": 1000.0,
        "atr_14": 20.0,
        "peg": 0.80,
        "roce_pct": 18.0,
        "roe_pct": 16.0,
        "debt_to_equity": 1.45,
        "cfo_to_pat": 0.95,
        "pat_growth_yoy_pct": 22.0,
    }
    conn.execute(
        "INSERT INTO feature_snapshots (ticker, as_of_date, schema_version, features_json, created_at) "
        "VALUES ('TATAMOTORS', ?, 1, ?, ?)",
        (RUN_DATE, json.dumps(indebted_features), NOW),
    )

    res = run_baseline_lynch(RUN_DATE, clock, conn)
    assert res["status"] == "SUCCESS"
    dec = conn.execute(
        "SELECT * FROM decisions WHERE agent_id = 'baseline-lynch-rules' AND ticker = 'TATAMOTORS'"
    ).fetchone()
    assert dec["action"] == "HOLD"
    assert "D/E 1.45 > 0.80" in dec["reasoning"]


def test_baseline_lynch_holds_when_cfo_to_pat_fails():
    conn = make_portfolio_db()
    seed_lynch_baseline_test(conn)
    clock = FakeClock(datetime(2026, 10, 16, 22, 0, 0))

    # Accounting profits without cash: CFO/PAT = 0.45 (< 0.70)
    low_cash_features = {
        "close": 1000.0,
        "atr_14": 20.0,
        "peg": 0.75,
        "roce_pct": 20.0,
        "roe_pct": 18.0,
        "debt_to_equity": 0.30,
        "cfo_to_pat": 0.45,
        "pat_growth_yoy_pct": 25.0,
    }
    conn.execute(
        "INSERT INTO feature_snapshots (ticker, as_of_date, schema_version, features_json, created_at) "
        "VALUES ('TATAMOTORS', ?, 1, ?, ?)",
        (RUN_DATE, json.dumps(low_cash_features), NOW),
    )

    res = run_baseline_lynch(RUN_DATE, clock, conn)
    assert res["status"] == "SUCCESS"
    dec = conn.execute(
        "SELECT * FROM decisions WHERE agent_id = 'baseline-lynch-rules' AND ticker = 'TATAMOTORS'"
    ).fetchone()
    assert dec["action"] == "HOLD"
    assert "CFO/PAT 0.45 < 0.70" in dec["reasoning"]


def test_baseline_lynch_exits_on_target_reached():
    conn = make_portfolio_db()
    seed_lynch_baseline_test(conn)
    clock = FakeClock(datetime(2026, 10, 16, 22, 0, 0))

    # Open position with target 112000 paise (Rs 1120)
    conn.execute(
        "INSERT INTO positions (agent_id, ticker, sector, shares, avg_entry_price_paise, stop_paise, target_paise, last_price_paise, status, entry_date) "
        "VALUES ('baseline-lynch-rules', 'TATAMOTORS', 'Automobile', 10, 100000, 95000, 112000, 100000, 'OPEN', '2026-09-01')"
    )
    # Current close is 1125.0 (exceeds target 1120.0)
    current_features = {
        "close": 1125.0,
        "atr_14": 20.0,
        "peg": 1.10,
        "cfo_to_pat": 1.0,
        "pat_growth_yoy_pct": 20.0,
    }
    conn.execute(
        "INSERT INTO feature_snapshots (ticker, as_of_date, schema_version, features_json, created_at) "
        "VALUES ('TATAMOTORS', ?, 1, ?, ?)",
        (RUN_DATE, json.dumps(current_features), NOW),
    )

    res = run_baseline_lynch(RUN_DATE, clock, conn)
    assert res["status"] == "SUCCESS"
    dec = conn.execute(
        "SELECT * FROM decisions WHERE agent_id = 'baseline-lynch-rules' AND ticker = 'TATAMOTORS'"
    ).fetchone()
    assert dec["action"] == "ADJUST"
    assert dec["stop_paise"] >= 100000  # Ratcheted above entry (1000.0) to lock in profit
    assert dec["target_paise"] > 112500  # Trailed above current price
    assert "TARGET_REACHED" in dec["reasoning"]


def test_baseline_lynch_exits_on_valuation_stretched():
    conn = make_portfolio_db()
    seed_lynch_baseline_test(conn)
    clock = FakeClock(datetime(2026, 10, 16, 22, 0, 0))

    # Open position entered at Rs 1000. Stop is 950, target is 1200.
    conn.execute(
        "INSERT INTO positions (agent_id, ticker, sector, shares, avg_entry_price_paise, stop_paise, target_paise, last_price_paise, status, entry_date) "
        "VALUES ('baseline-lynch-rules', 'TATAMOTORS', 'Automobile', 10, 100000, 95000, 120000, 100000, 'OPEN', '2026-09-01')"
    )
    # Stock rallied, but PEG expanded to 2.10 (>= 1.80 valuation exhausted)
    stretched_features = {
        "close": 1150.0,
        "atr_14": 20.0,
        "peg": 2.10,
        "cfo_to_pat": 1.0,
        "pat_growth_yoy_pct": 18.0,
    }
    conn.execute(
        "INSERT INTO feature_snapshots (ticker, as_of_date, schema_version, features_json, created_at) "
        "VALUES ('TATAMOTORS', ?, 1, ?, ?)",
        (RUN_DATE, json.dumps(stretched_features), NOW),
    )

    res = run_baseline_lynch(RUN_DATE, clock, conn)
    assert res["status"] == "SUCCESS"
    dec = conn.execute(
        "SELECT * FROM decisions WHERE agent_id = 'baseline-lynch-rules' AND ticker = 'TATAMOTORS'"
    ).fetchone()
    assert dec["action"] == "SELL"
    assert "valuation stretched" in dec["reasoning"]


def test_baseline_lynch_exits_on_fundamental_deterioration():
    conn = make_portfolio_db()
    seed_lynch_baseline_test(conn)
    clock = FakeClock(datetime(2026, 10, 16, 22, 0, 0))

    # Open position. Target not hit, stop not hit.
    conn.execute(
        "INSERT INTO positions (agent_id, ticker, sector, shares, avg_entry_price_paise, stop_paise, target_paise, last_price_paise, status, entry_date) "
        "VALUES ('baseline-lynch-rules', 'TATAMOTORS', 'Automobile', 10, 100000, 90000, 120000, 100000, 'OPEN', '2026-09-01')"
    )
    # Story breaks down: CFO/PAT collapses to 0.40 (< 0.60 threshold)
    broken_features = {
        "close": 980.0,
        "atr_14": 20.0,
        "peg": 1.10,
        "cfo_to_pat": 0.40,
        "pat_growth_yoy_pct": 10.0,
        "debt_to_equity": 0.50,
    }
    conn.execute(
        "INSERT INTO feature_snapshots (ticker, as_of_date, schema_version, features_json, created_at) "
        "VALUES ('TATAMOTORS', ?, 1, ?, ?)",
        (RUN_DATE, json.dumps(broken_features), NOW),
    )

    res = run_baseline_lynch(RUN_DATE, clock, conn)
    assert res["status"] == "SUCCESS"
    dec = conn.execute(
        "SELECT * FROM decisions WHERE agent_id = 'baseline-lynch-rules' AND ticker = 'TATAMOTORS'"
    ).fetchone()
    assert dec["action"] == "SELL"
    assert "fundamental story deterioration" in dec["reasoning"]


def test_baseline_lynch_ratchets_stop_to_breakeven_on_profit():
    conn = make_portfolio_db()
    seed_lynch_baseline_test(conn)
    clock = FakeClock(datetime(2026, 10, 16, 22, 0, 0))

    # Entry at Rs 1000, initial stop at Rs 950 (2.5x ATR = 50). Target Rs 1150.
    conn.execute(
        "INSERT INTO positions (agent_id, ticker, sector, shares, avg_entry_price_paise, stop_paise, target_paise, last_price_paise, status, entry_date) "
        "VALUES ('baseline-lynch-rules', 'TATAMOTORS', 'Automobile', 10, 100000, 95000, 115000, 100000, 'OPEN', '2026-10-01')"
    )
    # Price advances to Rs 1080 (+80 profit >= 3.75 * ATR [3.75*20 = 75])
    gaining_features = {
        "close": 1080.0,
        "atr_14": 20.0,
        "peg": 1.10,
        "cfo_to_pat": 1.05,
        "pat_growth_yoy_pct": 22.0,
        "debt_to_equity": 0.35,
    }
    conn.execute(
        "INSERT INTO feature_snapshots (ticker, as_of_date, schema_version, features_json, created_at) "
        "VALUES ('TATAMOTORS', ?, 1, ?, ?)",
        (RUN_DATE, json.dumps(gaining_features), NOW),
    )

    res = run_baseline_lynch(RUN_DATE, clock, conn)
    assert res["status"] == "SUCCESS"
    dec = conn.execute(
        "SELECT * FROM decisions WHERE agent_id = 'baseline-lynch-rules' AND ticker = 'TATAMOTORS'"
    ).fetchone()
    assert dec["action"] == "ADJUST"
    assert dec["stop_paise"] == 100000  # Ratcheted to entry price
    assert "ratcheted stop to breakeven" in dec["reasoning"]


def test_baseline_lynch_enforces_concentration_and_sector_cap():
    conn = make_portfolio_db()
    seed_lynch_baseline_test(conn)
    clock = FakeClock(datetime(2026, 10, 16, 22, 0, 0))

    # Add 2 open positions in IT sector already (INFY and TCS)
    conn.execute(
        "INSERT INTO positions (agent_id, ticker, sector, shares, avg_entry_price_paise, stop_paise, target_paise, last_price_paise, status, entry_date) "
        "VALUES ('baseline-lynch-rules', 'INFY', 'IT', 10, 150000, 142000, 168000, 150000, 'OPEN', '2026-10-01')"
    )
    conn.execute(
        "INSERT INTO positions (agent_id, ticker, sector, shares, avg_entry_price_paise, stop_paise, target_paise, last_price_paise, status, entry_date) "
        "VALUES ('baseline-lynch-rules', 'TCS', 'IT', 10, 350000, 335000, 385000, 350000, 'OPEN', '2026-10-01')"
    )

    # A 3rd IT stock (WIPRO) is added to symbols and watchlist
    conn.execute(
        "INSERT OR IGNORE INTO symbols (ticker, instrument_key, isin, company_name, sector, is_active) "
        "VALUES ('WIPRO', 'NSE_EQ|INE075A01022', 'INE075A01022', 'Wipro Ltd', 'IT', 1)"
    )
    conn.execute(
        "INSERT OR IGNORE INTO agent_watchlist (agent_id, ticker, sector, added_on, ttl_days, expires_on, intensity_score) "
        "VALUES ('lynch', 'WIPRO', 'IT', ?, 21, '2026-11-06', 0.90)",
        (RUN_DATE,),
    )
    wipro_features = {
        "close": 500.0,
        "atr_14": 10.0,
        "peg": 0.90,
        "roce_pct": 18.0,
        "roe_pct": 16.0,
        "debt_to_equity": 0.20,
        "cfo_to_pat": 1.0,
        "pat_growth_yoy_pct": 15.0,
    }
    conn.execute(
        "INSERT INTO feature_snapshots (ticker, as_of_date, schema_version, features_json, created_at) "
        "VALUES ('WIPRO', ?, 1, ?, ?)",
        (RUN_DATE, json.dumps(wipro_features), NOW),
    )

    res = run_baseline_lynch(RUN_DATE, clock, conn)
    assert res["status"] == "SUCCESS"
    dec = conn.execute(
        "SELECT * FROM decisions WHERE agent_id = 'baseline-lynch-rules' AND ticker = 'WIPRO'"
    ).fetchone()
    assert dec["action"] == "HOLD"
    assert "sector IT reached cap" in dec["reasoning"]
