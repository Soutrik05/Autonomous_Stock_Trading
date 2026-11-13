"""
Unit tests for baselines/rj_rules.py: rules-only baseline agent for Rakesh Jhunjhunwala (baseline-rj-rules).
Tests Method A compounder filtering (Close > EMA-200, EMA-20 > EMA-50, Volume Surge >= 1.1x,
PAT YoY >= 15%, ROCE >= 15%, Promoter >= 45%, D/E <= 1.20, PE <= 45.0),
3.0x ATR volatility stops, 1:2.0 minimum RRR, fundamental breakdown exits,
breakeven ratcheting, and sector caps.
"""

import json
import sqlite3
from datetime import datetime

from baselines.rj_rules import run_baseline_rj
from core.clock import FakeClock
from tests.conftest import make_portfolio_db

NOW = "2026-10-16T22:00:00+05:30"
RUN_DATE = "2026-10-16"


def seed_rj_baseline_test(conn: sqlite3.Connection):
    conn.execute(
        "INSERT OR IGNORE INTO agents (id, name, philosophy, kind, starting_cash_paise, cash_paise, created_at, updated_at) "
        "VALUES ('baseline-rj-rules', 'Baseline Jhunjhunwala Rules', 'Compounder Rules', 'BASELINE', 10000000, 10000000, ?, ?)",
        (NOW, NOW),
    )
    conn.execute(
        "INSERT OR IGNORE INTO agents (id, name, philosophy, kind, starting_cash_paise, cash_paise, created_at, updated_at) "
        "VALUES ('jhunjhunwala', 'Rakesh Jhunjhunwala', 'Compounder', 'LLM', 10000000, 10000000, ?, ?)",
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
    # Add to Jhunjhunwala's watchlist
    conn.execute(
        "INSERT OR IGNORE INTO agent_watchlist (agent_id, ticker, sector, added_on, ttl_days, expires_on, intensity_score) "
        "VALUES ('jhunjhunwala', 'TATAMOTORS', 'Automobile', ?, 21, '2026-11-06', 0.88)",
        (RUN_DATE,),
    )
    conn.execute(
        "INSERT OR IGNORE INTO agent_watchlist (agent_id, ticker, sector, added_on, ttl_days, expires_on, intensity_score) "
        "VALUES ('jhunjhunwala', 'INFY', 'IT', ?, 21, '2026-11-06', 0.82)",
        (RUN_DATE,),
    )
    conn.execute(
        "INSERT OR IGNORE INTO agent_watchlist (agent_id, ticker, sector, added_on, ttl_days, expires_on, intensity_score) "
        "VALUES ('jhunjhunwala', 'TCS', 'IT', ?, 21, '2026-11-06', 0.78)",
        (RUN_DATE,),
    )
    conn.execute(
        "INSERT OR IGNORE INTO agent_watchlist (agent_id, ticker, sector, added_on, ttl_days, expires_on, intensity_score) "
        "VALUES ('jhunjhunwala', 'HDFCBANK', 'Banking', ?, 21, '2026-11-06', 0.74)",
        (RUN_DATE,),
    )


def test_baseline_rj_buys_when_all_compounder_rules_pass():
    conn = make_portfolio_db()
    seed_rj_baseline_test(conn)
    clock = FakeClock(datetime(2026, 10, 16, 22, 0, 0))

    # TATAMOTORS passes full Rakesh Jhunjhunwala Method A Compounder criteria:
    # Close > EMA-200, EMA-20 > EMA-50, Volume surge >= 1.1x, PAT growth YoY 24% (>= 15%),
    # ROCE 22% (>= 15%), Promoter 52% (>= 45%), D/E 0.35 (<= 1.20), P/E 28.0 (<= 45.0)
    tata_features = {
        "close": 1000.0,
        "atr_14": 25.0,
        "ema_200": 920.0,
        "ema_20_above_50": True,
        "volume_surge": 1.4,
        "pat_growth_yoy_pct": 24.0,
        "roce_pct": 22.0,
        "promoter_holding_pct": 52.0,
        "debt_to_equity": 0.35,
        "pe": 28.0,
        "fii_dii_qoq_delta_pct": 1.2,
        "news_sentiment": 0.10,
    }
    conn.execute(
        "INSERT INTO feature_snapshots (ticker, as_of_date, schema_version, features_json, created_at) "
        "VALUES ('TATAMOTORS', ?, 1, ?, ?)",
        (RUN_DATE, json.dumps(tata_features), NOW),
    )

    res = run_baseline_rj(RUN_DATE, clock, conn)
    assert res["status"] == "SUCCESS"
    assert res["decisions"] == 4

    tata_dec = conn.execute(
        "SELECT * FROM decisions WHERE agent_id = 'baseline-rj-rules' AND ticker = 'TATAMOTORS'"
    ).fetchone()
    assert tata_dec is not None
    assert tata_dec["source"] == "BASELINE"
    assert tata_dec["action"] == "BUY"
    assert "Secular Compounder" in tata_dec["reasoning"]

    # Verify stop loss: close - 3.0 * ATR = 1000 - 3*25 = 925 (92500 paise)
    # Entry High: close + 0.25 * ATR = 1000 + 6.25 = 1006.25 (100625 paise)
    # Target: close + max(2.0 * (1006.25 - 925), 6.0 * 25) = 1000 + max(162.5, 150) = 1162.5 (116250 paise)
    assert tata_dec["stop_paise"] == 92500
    assert tata_dec["entry_high_paise"] == 100625
    assert tata_dec["target_paise"] == 116250

    # Verify 1:2.0 minimum Risk-to-Reward Ratio
    risk_paise = tata_dec["entry_high_paise"] - tata_dec["stop_paise"]
    reward_paise = tata_dec["target_paise"] - tata_dec["entry_high_paise"]
    assert reward_paise / risk_paise >= 1.90


def test_baseline_rj_holds_when_pat_growth_too_low():
    conn = make_portfolio_db()
    seed_rj_baseline_test(conn)
    clock = FakeClock(datetime(2026, 10, 16, 22, 0, 0))

    # PAT growth = 8.0% (< 15.0%) -> Fails earnings velocity requirement
    slow_features = {
        "close": 1000.0,
        "atr_14": 25.0,
        "ema_200": 920.0,
        "ema_20_above_50": True,
        "volume_surge": 1.4,
        "pat_growth_yoy_pct": 8.0,
        "roce_pct": 22.0,
        "promoter_holding_pct": 52.0,
        "debt_to_equity": 0.35,
        "pe": 28.0,
    }
    conn.execute(
        "INSERT INTO feature_snapshots (ticker, as_of_date, schema_version, features_json, created_at) "
        "VALUES ('TATAMOTORS', ?, 1, ?, ?)",
        (RUN_DATE, json.dumps(slow_features), NOW),
    )

    res = run_baseline_rj(RUN_DATE, clock, conn)
    assert res["status"] == "SUCCESS"
    dec = conn.execute(
        "SELECT * FROM decisions WHERE agent_id = 'baseline-rj-rules' AND ticker = 'TATAMOTORS'"
    ).fetchone()
    assert dec["action"] == "HOLD"
    assert "PAT growth 8.0% < 15%" in dec["reasoning"]


def test_baseline_rj_holds_when_roce_too_low():
    conn = make_portfolio_db()
    seed_rj_baseline_test(conn)
    clock = FakeClock(datetime(2026, 10, 16, 22, 0, 0))

    # ROCE = 11.0% (< 15.0%) -> Capital efficiency too low
    low_roce_features = {
        "close": 1000.0,
        "atr_14": 25.0,
        "ema_200": 920.0,
        "ema_20_above_50": True,
        "volume_surge": 1.4,
        "pat_growth_yoy_pct": 22.0,
        "roce_pct": 11.0,
        "promoter_holding_pct": 52.0,
        "debt_to_equity": 0.35,
        "pe": 28.0,
    }
    conn.execute(
        "INSERT INTO feature_snapshots (ticker, as_of_date, schema_version, features_json, created_at) "
        "VALUES ('TATAMOTORS', ?, 1, ?, ?)",
        (RUN_DATE, json.dumps(low_roce_features), NOW),
    )

    res = run_baseline_rj(RUN_DATE, clock, conn)
    assert res["status"] == "SUCCESS"
    dec = conn.execute(
        "SELECT * FROM decisions WHERE agent_id = 'baseline-rj-rules' AND ticker = 'TATAMOTORS'"
    ).fetchone()
    assert dec["action"] == "HOLD"
    assert "ROCE 11.0% < 15%" in dec["reasoning"]


def test_baseline_rj_holds_when_promoter_holding_too_low():
    conn = make_portfolio_db()
    seed_rj_baseline_test(conn)
    clock = FakeClock(datetime(2026, 10, 16, 22, 0, 0))

    # Promoter holding = 38.0% (< 45.0%) -> Lack of promoter skin-in-the-game
    low_promoter_features = {
        "close": 1000.0,
        "atr_14": 25.0,
        "ema_200": 920.0,
        "ema_20_above_50": True,
        "volume_surge": 1.4,
        "pat_growth_yoy_pct": 22.0,
        "roce_pct": 20.0,
        "promoter_holding_pct": 38.0,
        "debt_to_equity": 0.35,
        "pe": 28.0,
    }
    conn.execute(
        "INSERT INTO feature_snapshots (ticker, as_of_date, schema_version, features_json, created_at) "
        "VALUES ('TATAMOTORS', ?, 1, ?, ?)",
        (RUN_DATE, json.dumps(low_promoter_features), NOW),
    )

    res = run_baseline_rj(RUN_DATE, clock, conn)
    assert res["status"] == "SUCCESS"
    dec = conn.execute(
        "SELECT * FROM decisions WHERE agent_id = 'baseline-rj-rules' AND ticker = 'TATAMOTORS'"
    ).fetchone()
    assert dec["action"] == "HOLD"
    assert "Promoter holding 38.0% < 45%" in dec["reasoning"]


def test_baseline_rj_holds_when_debt_too_high():
    conn = make_portfolio_db()
    seed_rj_baseline_test(conn)
    clock = FakeClock(datetime(2026, 10, 16, 22, 0, 0))

    # D/E = 1.45 (> 1.20) -> Excessive balance sheet debt leverage
    indebted_features = {
        "close": 1000.0,
        "atr_14": 25.0,
        "ema_200": 920.0,
        "ema_20_above_50": True,
        "volume_surge": 1.4,
        "pat_growth_yoy_pct": 22.0,
        "roce_pct": 20.0,
        "promoter_holding_pct": 52.0,
        "debt_to_equity": 1.45,
        "pe": 28.0,
    }
    conn.execute(
        "INSERT INTO feature_snapshots (ticker, as_of_date, schema_version, features_json, created_at) "
        "VALUES ('TATAMOTORS', ?, 1, ?, ?)",
        (RUN_DATE, json.dumps(indebted_features), NOW),
    )

    res = run_baseline_rj(RUN_DATE, clock, conn)
    assert res["status"] == "SUCCESS"
    dec = conn.execute(
        "SELECT * FROM decisions WHERE agent_id = 'baseline-rj-rules' AND ticker = 'TATAMOTORS'"
    ).fetchone()
    assert dec["action"] == "HOLD"
    assert "D/E 1.45 > 1.20" in dec["reasoning"]


def test_baseline_rj_holds_when_pe_too_high():
    conn = make_portfolio_db()
    seed_rj_baseline_test(conn)
    clock = FakeClock(datetime(2026, 10, 16, 22, 0, 0))

    # P/E = 55.0 (> 45.0) -> Overhyped multiple; no re-rating headroom
    expensive_features = {
        "close": 1000.0,
        "atr_14": 25.0,
        "ema_200": 920.0,
        "ema_20_above_50": True,
        "volume_surge": 1.4,
        "pat_growth_yoy_pct": 22.0,
        "roce_pct": 20.0,
        "promoter_holding_pct": 52.0,
        "debt_to_equity": 0.35,
        "pe": 55.0,
    }
    conn.execute(
        "INSERT INTO feature_snapshots (ticker, as_of_date, schema_version, features_json, created_at) "
        "VALUES ('TATAMOTORS', ?, 1, ?, ?)",
        (RUN_DATE, json.dumps(expensive_features), NOW),
    )

    res = run_baseline_rj(RUN_DATE, clock, conn)
    assert res["status"] == "SUCCESS"
    dec = conn.execute(
        "SELECT * FROM decisions WHERE agent_id = 'baseline-rj-rules' AND ticker = 'TATAMOTORS'"
    ).fetchone()
    assert dec["action"] == "HOLD"
    assert "PE 55.0 > 45.0" in dec["reasoning"]


def test_baseline_rj_holds_when_below_ema200():
    conn = make_portfolio_db()
    seed_rj_baseline_test(conn)
    clock = FakeClock(datetime(2026, 10, 16, 22, 0, 0))

    # Close = 880 <= EMA-200 920 -> Secular bear regime
    bear_features = {
        "close": 880.0,
        "atr_14": 25.0,
        "ema_200": 920.0,
        "ema_20_above_50": True,
        "volume_surge": 1.4,
        "pat_growth_yoy_pct": 22.0,
        "roce_pct": 20.0,
        "promoter_holding_pct": 52.0,
        "debt_to_equity": 0.35,
        "pe": 28.0,
    }
    conn.execute(
        "INSERT INTO feature_snapshots (ticker, as_of_date, schema_version, features_json, created_at) "
        "VALUES ('TATAMOTORS', ?, 1, ?, ?)",
        (RUN_DATE, json.dumps(bear_features), NOW),
    )

    res = run_baseline_rj(RUN_DATE, clock, conn)
    assert res["status"] == "SUCCESS"
    dec = conn.execute(
        "SELECT * FROM decisions WHERE agent_id = 'baseline-rj-rules' AND ticker = 'TATAMOTORS'"
    ).fetchone()
    assert dec["action"] == "HOLD"
    assert "close 880.0 <= EMA-200 920.0" in dec["reasoning"]


def test_baseline_rj_holds_on_severe_negative_news():
    conn = make_portfolio_db()
    seed_rj_baseline_test(conn)
    clock = FakeClock(datetime(2026, 10, 16, 22, 0, 0))

    # Severe negative news sentiment (-0.35 < -0.25) -> Governance/fraud risk
    bad_news_features = {
        "close": 1000.0,
        "atr_14": 25.0,
        "ema_200": 920.0,
        "ema_20_above_50": True,
        "volume_surge": 1.4,
        "pat_growth_yoy_pct": 22.0,
        "roce_pct": 20.0,
        "promoter_holding_pct": 52.0,
        "debt_to_equity": 0.35,
        "pe": 28.0,
        "news_sentiment": -0.35,
    }
    conn.execute(
        "INSERT INTO feature_snapshots (ticker, as_of_date, schema_version, features_json, created_at) "
        "VALUES ('TATAMOTORS', ?, 1, ?, ?)",
        (RUN_DATE, json.dumps(bad_news_features), NOW),
    )

    res = run_baseline_rj(RUN_DATE, clock, conn)
    assert res["status"] == "SUCCESS"
    dec = conn.execute(
        "SELECT * FROM decisions WHERE agent_id = 'baseline-rj-rules' AND ticker = 'TATAMOTORS'"
    ).fetchone()
    assert dec["action"] == "HOLD"
    assert "governance/fraud risk" in dec["reasoning"]


def test_baseline_rj_exits_on_target_reached():
    conn = make_portfolio_db()
    seed_rj_baseline_test(conn)
    clock = FakeClock(datetime(2026, 10, 16, 22, 0, 0))

    # Open position with target 116000 paise (Rs 1160)
    conn.execute(
        "INSERT INTO positions (agent_id, ticker, sector, shares, avg_entry_price_paise, stop_paise, target_paise, last_price_paise, status, entry_date) "
        "VALUES ('baseline-rj-rules', 'TATAMOTORS', 'Automobile', 10, 100000, 92500, 116000, 100000, 'OPEN', '2026-09-01')"
    )
    # Current close is 1165.0 (exceeds target 1160.0)
    current_features = {
        "close": 1165.0,
        "atr_14": 25.0,
        "pat_growth_yoy_pct": 22.0,
        "promoter_holding_pct": 52.0,
        "debt_to_equity": 0.35,
    }
    conn.execute(
        "INSERT INTO feature_snapshots (ticker, as_of_date, schema_version, features_json, created_at) "
        "VALUES ('TATAMOTORS', ?, 1, ?, ?)",
        (RUN_DATE, json.dumps(current_features), NOW),
    )

    res = run_baseline_rj(RUN_DATE, clock, conn)
    assert res["status"] == "SUCCESS"
    dec = conn.execute(
        "SELECT * FROM decisions WHERE agent_id = 'baseline-rj-rules' AND ticker = 'TATAMOTORS'"
    ).fetchone()
    assert dec["action"] == "ADJUST"
    assert dec["stop_paise"] >= 100000  # Ratcheted above entry (1000.0) to lock in profit
    assert dec["target_paise"] > 116500  # Trailed above current price
    assert "TARGET_REACHED" in dec["reasoning"]


def test_baseline_rj_exits_on_stop_loss_hit():
    conn = make_portfolio_db()
    seed_rj_baseline_test(conn)
    clock = FakeClock(datetime(2026, 10, 16, 22, 0, 0))

    # Open position with stop 92500 paise (Rs 925)
    conn.execute(
        "INSERT INTO positions (agent_id, ticker, sector, shares, avg_entry_price_paise, stop_paise, target_paise, last_price_paise, status, entry_date) "
        "VALUES ('baseline-rj-rules', 'TATAMOTORS', 'Automobile', 10, 100000, 92500, 116000, 100000, 'OPEN', '2026-09-01')"
    )
    # Current close is 920.0 (drops below stop 925.0)
    current_features = {
        "close": 920.0,
        "atr_14": 25.0,
        "pat_growth_yoy_pct": 22.0,
        "promoter_holding_pct": 52.0,
        "debt_to_equity": 0.35,
    }
    conn.execute(
        "INSERT INTO feature_snapshots (ticker, as_of_date, schema_version, features_json, created_at) "
        "VALUES ('TATAMOTORS', ?, 1, ?, ?)",
        (RUN_DATE, json.dumps(current_features), NOW),
    )

    res = run_baseline_rj(RUN_DATE, clock, conn)
    assert res["status"] == "SUCCESS"
    dec = conn.execute(
        "SELECT * FROM decisions WHERE agent_id = 'baseline-rj-rules' AND ticker = 'TATAMOTORS'"
    ).fetchone()
    assert dec["action"] == "SELL"
    assert "volatility stop hit" in dec["reasoning"]


def test_baseline_rj_exits_on_fundamental_thesis_broken():
    conn = make_portfolio_db()
    seed_rj_baseline_test(conn)
    clock = FakeClock(datetime(2026, 10, 16, 22, 0, 0))

    # Open position entered at Rs 1000.
    conn.execute(
        "INSERT INTO positions (agent_id, ticker, sector, shares, avg_entry_price_paise, stop_paise, target_paise, last_price_paise, status, entry_date) "
        "VALUES ('baseline-rj-rules', 'TATAMOTORS', 'Automobile', 10, 100000, 92500, 116000, 100000, 'OPEN', '2026-09-01')"
    )
    # Secular compounder thesis breaks: PAT growth contracts negative (-5.0%)
    broken_features = {
        "close": 980.0,
        "atr_14": 25.0,
        "pat_growth_yoy_pct": -5.0,
        "promoter_holding_pct": 52.0,
        "debt_to_equity": 0.40,
    }
    conn.execute(
        "INSERT INTO feature_snapshots (ticker, as_of_date, schema_version, features_json, created_at) "
        "VALUES ('TATAMOTORS', ?, 1, ?, ?)",
        (RUN_DATE, json.dumps(broken_features), NOW),
    )

    res = run_baseline_rj(RUN_DATE, clock, conn)
    assert res["status"] == "SUCCESS"
    dec = conn.execute(
        "SELECT * FROM decisions WHERE agent_id = 'baseline-rj-rules' AND ticker = 'TATAMOTORS'"
    ).fetchone()
    assert dec["action"] == "SELL"
    assert "secular compounder thesis broken" in dec["reasoning"]


def test_baseline_rj_ratchets_stop_to_breakeven_on_profit():
    conn = make_portfolio_db()
    seed_rj_baseline_test(conn)
    clock = FakeClock(datetime(2026, 10, 16, 22, 0, 0))

    # Entry at Rs 1000, initial stop at Rs 925 (3.0x ATR = 75). Target Rs 1180.
    conn.execute(
        "INSERT INTO positions (agent_id, ticker, sector, shares, avg_entry_price_paise, stop_paise, target_paise, last_price_paise, status, entry_date) "
        "VALUES ('baseline-rj-rules', 'TATAMOTORS', 'Automobile', 10, 100000, 92500, 118000, 100000, 'OPEN', '2026-10-01')"
    )
    # Price advances to Rs 1080 (+80 profit >= 3.0 * ATR [3.0*25 = 75])
    gaining_features = {
        "close": 1080.0,
        "atr_14": 25.0,
        "pat_growth_yoy_pct": 22.0,
        "promoter_holding_pct": 52.0,
        "debt_to_equity": 0.35,
    }
    conn.execute(
        "INSERT INTO feature_snapshots (ticker, as_of_date, schema_version, features_json, created_at) "
        "VALUES ('TATAMOTORS', ?, 1, ?, ?)",
        (RUN_DATE, json.dumps(gaining_features), NOW),
    )

    res = run_baseline_rj(RUN_DATE, clock, conn)
    assert res["status"] == "SUCCESS"
    dec = conn.execute(
        "SELECT * FROM decisions WHERE agent_id = 'baseline-rj-rules' AND ticker = 'TATAMOTORS'"
    ).fetchone()
    assert dec["action"] == "ADJUST"
    assert dec["stop_paise"] == 100000  # Ratcheted to entry price
    assert "ratcheted stop to breakeven" in dec["reasoning"]


def test_baseline_rj_enforces_sector_cap():
    conn = make_portfolio_db()
    seed_rj_baseline_test(conn)
    clock = FakeClock(datetime(2026, 10, 16, 22, 0, 0))

    # Add 2 open positions in IT sector already (INFY and TCS)
    conn.execute(
        "INSERT INTO positions (agent_id, ticker, sector, shares, avg_entry_price_paise, stop_paise, target_paise, last_price_paise, status, entry_date) "
        "VALUES ('baseline-rj-rules', 'INFY', 'IT', 10, 150000, 142000, 168000, 150000, 'OPEN', '2026-10-01')"
    )
    conn.execute(
        "INSERT INTO positions (agent_id, ticker, sector, shares, avg_entry_price_paise, stop_paise, target_paise, last_price_paise, status, entry_date) "
        "VALUES ('baseline-rj-rules', 'TCS', 'IT', 10, 350000, 335000, 385000, 350000, 'OPEN', '2026-10-01')"
    )

    # A 3rd IT stock (WIPRO) is added to symbols and watchlist
    conn.execute(
        "INSERT OR IGNORE INTO symbols (ticker, instrument_key, isin, company_name, sector, is_active) "
        "VALUES ('WIPRO', 'NSE_EQ|INE075A01022', 'INE075A01022', 'Wipro Ltd', 'IT', 1)"
    )
    conn.execute(
        "INSERT OR IGNORE INTO agent_watchlist (agent_id, ticker, sector, added_on, ttl_days, expires_on, intensity_score) "
        "VALUES ('jhunjhunwala', 'WIPRO', 'IT', ?, 21, '2026-11-06', 0.90)",
        (RUN_DATE,),
    )
    wipro_features = {
        "close": 500.0,
        "atr_14": 12.0,
        "ema_200": 460.0,
        "ema_20_above_50": True,
        "volume_surge": 1.3,
        "pat_growth_yoy_pct": 20.0,
        "roce_pct": 18.0,
        "promoter_holding_pct": 55.0,
        "debt_to_equity": 0.20,
        "pe": 22.0,
    }
    conn.execute(
        "INSERT INTO feature_snapshots (ticker, as_of_date, schema_version, features_json, created_at) "
        "VALUES ('WIPRO', ?, 1, ?, ?)",
        (RUN_DATE, json.dumps(wipro_features), NOW),
    )

    res = run_baseline_rj(RUN_DATE, clock, conn)
    assert res["status"] == "SUCCESS"
    dec = conn.execute("SELECT * FROM decisions WHERE agent_id = 'baseline-rj-rules' AND ticker = 'WIPRO'").fetchone()
    assert dec["action"] == "HOLD"
    assert "sector IT reached cap" in dec["reasoning"]
