"""
Unit tests for baselines/simons_rules.py: rules-only baseline agent.
See Plan_v3 §6.1.
"""
from datetime import datetime
import json
import sqlite3

from baselines.simons_rules import run_baseline_simons
from core.clock import FakeClock
from tests.conftest import make_portfolio_db

NOW = "2026-10-16T22:00:00+05:30"
RUN_DATE = "2026-10-16"


def seed_baseline_test(conn: sqlite3.Connection):
    conn.execute(
        "INSERT OR IGNORE INTO agents (id, name, philosophy, kind, starting_cash_paise, cash_paise, created_at, updated_at) "
        "VALUES ('baseline-simons-rules', 'Baseline Simons Rules', 'Rules', 'BASELINE', 10000000, 10000000, ?, ?)",
        (NOW, NOW),
    )
    conn.execute(
        "INSERT OR IGNORE INTO agents (id, name, philosophy, kind, starting_cash_paise, cash_paise, created_at, updated_at) "
        "VALUES ('simons', 'Jim Simons', 'Quant', 'LLM', 10000000, 10000000, ?, ?)",
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
    # Add to Simons' watchlist so get_review_pool finds them
    conn.execute(
        "INSERT OR IGNORE INTO agent_watchlist (agent_id, ticker, sector, added_on, ttl_days, expires_on, intensity_score) "
        "VALUES ('simons', 'TATAMOTORS', 'Automobile', ?, 3, '2026-10-25', 5.5)",
        (RUN_DATE,),
    )
    conn.execute(
        "INSERT OR IGNORE INTO agent_watchlist (agent_id, ticker, sector, added_on, ttl_days, expires_on, intensity_score) "
        "VALUES ('simons', 'INFY', 'IT', ?, 3, '2026-10-25', 2.0)",
        (RUN_DATE,),
    )


def test_baseline_buys_when_all_rules_pass():
    conn = make_portfolio_db()
    seed_baseline_test(conn)
    clock = FakeClock(datetime(2026, 10, 16, 22, 0, 0))

    # TATAMOTORS passes all criteria: EMA alignment, RSI 62, volume 1.5x, MACD hist > 0, ATR > 0
    tata_features = {
        "close": 1000.0, "ema_20": 980.0, "ema_50": 950.0, "ema_200": 900.0,
        "ema_20_above_50": True, "rsi_14": 62.0, "volume_surge": 1.5, "macd_hist": 2.5,
        "atr_14": 20.0, "obv_slope_sign": 1, "dist_52w_high_pct": -2.0, "dist_52w_low_pct": 20.0,
    }
    # INFY fails volume surge (< 1.2)
    infy_features = {
        "close": 1800.0, "ema_20": 1780.0, "ema_50": 1750.0, "ema_200": 1700.0,
        "ema_20_above_50": True, "rsi_14": 60.0, "volume_surge": 0.9, "macd_hist": 1.5,
        "atr_14": 25.0, "obv_slope_sign": 1, "dist_52w_high_pct": -5.0, "dist_52w_low_pct": 15.0,
    }
    conn.execute(
        "INSERT INTO feature_snapshots (ticker, as_of_date, schema_version, features_json, created_at) "
        "VALUES ('TATAMOTORS', ?, 1, ?, ?)",
        (RUN_DATE, json.dumps(tata_features), NOW),
    )
    conn.execute(
        "INSERT INTO feature_snapshots (ticker, as_of_date, schema_version, features_json, created_at) "
        "VALUES ('INFY', ?, 1, ?, ?)",
        (RUN_DATE, json.dumps(infy_features), NOW),
    )

    res = run_baseline_simons(RUN_DATE, clock, conn)
    assert res["status"] == "SUCCESS"
    assert res["decisions"] == 2

    # Verify decisions
    tata_dec = conn.execute(
        "SELECT * FROM decisions WHERE agent_id = 'baseline-simons-rules' AND ticker = 'TATAMOTORS'"
    ).fetchone()
    assert tata_dec is not None
    assert tata_dec["source"] == "BASELINE"
    assert tata_dec["action"] == "BUY"
    # Entry low = 1000 - 0.25*20 = 995 -> 99500 paise
    # Entry high = 1000 + 0.25*20 = 1005 -> 100500 paise
    # Stop = 1000 - 2*20 = 960 -> 96000 paise
    # Target = 1000 + 3*20 = 1060 -> 106000 paise
    assert tata_dec["entry_low_paise"] == 99500
    assert tata_dec["entry_high_paise"] == 100500
    assert tata_dec["stop_paise"] == 96000
    assert tata_dec["target_paise"] == 106000
    # Sizing: 10% of 100,000 = 10,000 Rs / 1005 = 9 shares
    assert tata_dec["shares"] == 9

    infy_dec = conn.execute(
        "SELECT * FROM decisions WHERE agent_id = 'baseline-simons-rules' AND ticker = 'INFY'"
    ).fetchone()
    assert infy_dec["action"] == "HOLD"

    # Pending order was placed for TATAMOTORS
    order = conn.execute(
        "SELECT * FROM pending_orders WHERE agent_id = 'baseline-simons-rules' AND ticker = 'TATAMOTORS'"
    ).fetchone()
    assert order is not None
    assert order["status"] == "pending"


def test_baseline_sells_when_close_below_ema20():
    conn = make_portfolio_db()
    seed_baseline_test(conn)
    clock = FakeClock(datetime(2026, 10, 16, 22, 0, 0))

    # Add an OPEN position for baseline
    conn.execute(
        "INSERT INTO positions (agent_id, ticker, sector, shares, avg_entry_price_paise, stop_paise, target_paise, last_price_paise, status, entry_date) "
        "VALUES ('baseline-simons-rules', 'TATAMOTORS', 'Automobile', 10, 100000, 96000, 106000, 97000, 'OPEN', '2026-10-10')"
    )

    # Price dropped below 20 EMA (close = 970, ema_20 = 980)
    features = {
        "close": 970.0, "ema_20": 980.0, "ema_50": 950.0, "ema_200": 900.0,
        "ema_20_above_50": True, "rsi_14": 48.0, "volume_surge": 1.1, "macd_hist": -1.0, "atr_14": 20.0,
    }
    conn.execute(
        "INSERT INTO feature_snapshots (ticker, as_of_date, schema_version, features_json, created_at) "
        "VALUES ('TATAMOTORS', ?, 1, ?, ?)",
        (RUN_DATE, json.dumps(features), NOW),
    )

    res = run_baseline_simons(RUN_DATE, clock, conn)
    assert res["status"] == "SUCCESS"

    dec = conn.execute(
        "SELECT * FROM decisions WHERE agent_id = 'baseline-simons-rules' AND ticker = 'TATAMOTORS'"
    ).fetchone()
    assert dec["action"] == "SELL"
    assert "close < ema_20" in dec["reasoning"]

    # Pending SELL order placed
    order = conn.execute(
        "SELECT * FROM pending_orders WHERE agent_id = 'baseline-simons-rules' AND ticker = 'TATAMOTORS'"
    ).fetchone()
    assert order["side"] == "SELL"
    assert order["status"] == "pending"
