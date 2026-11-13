"""
Integration test for the nightly batch pipeline:
ingestion -> features -> watchlist -> backup -> agent runner (LLM Simons + baseline-simons-rules).
Stops once decisions are generated and pending orders are placed and reserved in the broker.
See Plan_v3 §1.4, §Day 5.
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from agents.runner import run as run_agents
from broker.engine import Broker
from core.clock import FakeClock
from core.money import rupees_to_paise
from features.builder import run as run_build_features
from ingestion.cli import run as run_ingestion
from llm.client import FakeLLMClient
from scripts.backup import backup_portfolio_db
from tests.conftest import make_passing_simons_features
from watchlist.watchlist_refresh import run as run_watchlist_refresh

RUN_DATE = "2026-10-19"


def test_nightly_pipeline_batch_flow(tmp_path, seeded_portfolio, ohlcv_conn, macro_conn, clock, mock_upstox_client):
    portfolio_conn = seeded_portfolio

    # Step 1: 20:00 IST - Ingestion
    ingest_status = run_ingestion(
        clock=clock,
        client=mock_upstox_client,
        date_str=RUN_DATE,
        portfolio_conn=portfolio_conn,
        ohlcv_conn=ohlcv_conn,
        macro_conn=macro_conn,
    )
    assert ingest_status == "SUCCESS"

    # Gating check: pipeline_runs for ingestion must be SUCCESS
    ingest_run = portfolio_conn.execute(
        "SELECT status FROM pipeline_runs WHERE job = 'ingestion' AND run_date = ?",
        (RUN_DATE,),
    ).fetchone()
    assert ingest_run is not None
    assert ingest_run["status"] == "SUCCESS"

    # Step 2: Feature snapshots
    feat_status = run_build_features(
        as_of_date=RUN_DATE,
        clock=clock,
        portfolio_conn=portfolio_conn,
        ohlcv_conn=ohlcv_conn,
        macro_conn=macro_conn,
    )
    assert feat_status["status"] == "SUCCESS"
    assert feat_status["written"] == 1

    # Gating check: pipeline_runs for features must be SUCCESS
    feat_run = portfolio_conn.execute(
        "SELECT status FROM pipeline_runs WHERE job = 'features' AND run_date = ?",
        (RUN_DATE,),
    ).fetchone()
    assert feat_run is not None
    assert feat_run["status"] == "SUCCESS"

    snapshot = portfolio_conn.execute(
        "SELECT * FROM feature_snapshots WHERE ticker = 'TATAMOTORS' AND as_of_date = ?",
        (RUN_DATE,),
    ).fetchone()
    assert snapshot is not None

    # Deliberate simplification: Patch features_json so Simons criteria are satisfied.
    # The minimal synthetic OHLCV series has constant prices, which yields zero momentum / flat RSI.
    # Real indicator calculations are thoroughly covered in tests/unit/test_indicators.py.
    # Here we set rsi_14, macd_hist, and volume_surge so downstream filters (watchlist & Simons rules)
    # naturally produce BUY candidates.
    raw_feats = json.loads(snapshot["features_json"])
    raw_feats.update(
        make_passing_simons_features(
            close=1000.0,
            ema_20=990.0,
            ema_50=980.0,
            ema_200=950.0,
            rsi_14=62.4,
            macd_hist=2.0,
            volume_surge=1.5,
            atr_14=20.0,
            adx_14=25.0,
            kaufman_er_20=0.45,
        )
    )
    portfolio_conn.execute(
        "UPDATE feature_snapshots SET features_json = ? WHERE ticker = 'TATAMOTORS' AND as_of_date = ?",
        (json.dumps(raw_feats), RUN_DATE),
    )

    # Step 3: Watchlist refresh
    # The real Stage 0-3 funnel runs. TATAMOTORS satisfies turnover, volume expansion, and Simons hurdles.
    wl_status = run_watchlist_refresh(
        as_of_date=RUN_DATE,
        agent_id="simons",
        clock=clock,
        portfolio_conn=portfolio_conn,
        ohlcv_conn=ohlcv_conn,
    )
    assert wl_status["status"] == "SUCCESS"

    # Gating check: pipeline_runs for watchlist must be SUCCESS
    wl_run = portfolio_conn.execute(
        "SELECT status FROM pipeline_runs WHERE job = 'watchlist' AND run_date = ?",
        (RUN_DATE,),
    ).fetchone()
    assert wl_run is not None
    assert wl_run["status"] == "SUCCESS"

    # Verify actual funnel output: TATAMOTORS is added to Simons' watchlist
    watchlist_row = portfolio_conn.execute(
        "SELECT * FROM agent_watchlist WHERE agent_id = 'simons' AND ticker = 'TATAMOTORS'"
    ).fetchone()
    assert watchlist_row is not None
    assert watchlist_row["sector"] == "Automobiles"

    # Step 4: 21:45 IST - Backup
    backup_src = tmp_path / "portfolio.db"
    file_conn = sqlite3.connect(str(backup_src))
    portfolio_conn.backup(file_conn)
    file_conn.close()

    backup_dest = backup_portfolio_db(
        source_path=str(backup_src),
        backup_dir=str(tmp_path / "backups"),
        clock=clock,
    )
    assert backup_dest is not None
    assert Path(backup_dest).exists()

    # Step 5: 22:00 IST - Agent runner (Simons with FakeLLM + Baseline Simons Rules)
    # LLM is scripted only for "simons"; "baseline-simons-rules" executes pure Python rules with zero LLM calls.
    # All monetary amounts are handled strictly in integer paise via core.money helpers.
    simons_shares = 8
    simons_entry_low_paise = rupees_to_paise(995.0)
    simons_entry_high_paise = rupees_to_paise(1005.0)
    simons_stop_paise = rupees_to_paise(945.0)
    simons_target_paise = rupees_to_paise(1080.0)

    simons_llm_response = json.dumps(
        {
            "decisions": [
                {
                    "ticker": "TATAMOTORS",
                    "action": "BUY",
                    "shares": simons_shares,
                    "entry_low": 995.0,
                    "entry_high": 1005.0,
                    "stop_loss_price": 945.0,
                    "target_price": 1080.0,
                    "pre_mortem_risk": "Margin pressure in CV segment.",
                    "reasoning": "Breakout above EMA20 with strong volume surge.",
                    "cited_metrics": {"rsi_14": 62.4, "volume_surge": 1.5, "macd_hist": 2.0},
                }
            ]
        }
    )

    clock_2200 = FakeClock(datetime(2026, 10, 19, 22, 0, 0))
    agent_results = run_agents(
        ["simons", "baseline-simons-rules"],
        as_of_date=RUN_DATE,
        clock=clock_2200,
        portfolio_conn=portfolio_conn,
        ohlcv_conn=ohlcv_conn,
        llm_client=FakeLLMClient(responses=[simons_llm_response]),
        fake_llm=True,
    )
    assert agent_results["simons"]["status"] == "SUCCESS"
    assert agent_results["baseline-simons-rules"]["status"] == "SUCCESS"

    # Gating check: pipeline_runs for agents must be SUCCESS
    agent_run = portfolio_conn.execute(
        "SELECT status FROM pipeline_runs WHERE job = 'agents' AND run_date = ?",
        (RUN_DATE,),
    ).fetchone()
    assert agent_run is not None
    assert agent_run["status"] == "SUCCESS"

    # Step 6: Verify decisions and pending orders for both agents
    broker = Broker(portfolio_conn, clock_2200)

    # 1. LLM Simons decision and order
    simons_decision = portfolio_conn.execute(
        "SELECT * FROM decisions WHERE agent_id = 'simons' AND ticker = 'TATAMOTORS' AND run_date = ?",
        (RUN_DATE,),
    ).fetchone()
    assert simons_decision is not None
    assert simons_decision["action"] == "BUY"
    assert simons_decision["shares"] == simons_shares
    assert simons_decision["entry_low_paise"] == simons_entry_low_paise
    assert simons_decision["entry_high_paise"] == simons_entry_high_paise
    assert simons_decision["stop_paise"] == simons_stop_paise
    assert simons_decision["target_paise"] == simons_target_paise

    simons_order = portfolio_conn.execute(
        "SELECT * FROM pending_orders WHERE agent_id = 'simons' AND ticker = 'TATAMOTORS'"
    ).fetchone()
    assert simons_order is not None
    assert simons_order["status"] == "pending"
    assert simons_order["decision_id"] == simons_decision["id"]
    assert simons_order["shares"] == simons_shares

    # Exact equality check for reserved_amount_paise using the broker's worst-case outlay formula:
    # worst_price = entry_high x (1 + BUY_OVERSHOOT_PCT) with slippage; outlay = shares x worst_price + BUY charges
    expected_simons_reserved = broker.worst_case_buy_outlay_paise(simons_shares, simons_entry_high_paise)
    assert simons_order["reserved_amount_paise"] == expected_simons_reserved

    # 2. Baseline Simons Rules decision and order
    baseline_decision = portfolio_conn.execute(
        "SELECT * FROM decisions WHERE agent_id = 'baseline-simons-rules' AND ticker = 'TATAMOTORS' AND run_date = ?",
        (RUN_DATE,),
    ).fetchone()
    assert baseline_decision is not None
    assert baseline_decision["action"] == "BUY"
    assert baseline_decision["shares"] >= 1

    baseline_order = portfolio_conn.execute(
        "SELECT * FROM pending_orders WHERE agent_id = 'baseline-simons-rules' AND ticker = 'TATAMOTORS'"
    ).fetchone()
    assert baseline_order is not None
    assert baseline_order["status"] == "pending"
    assert baseline_order["decision_id"] == baseline_decision["id"]
    assert baseline_order["shares"] == baseline_decision["shares"]

    expected_baseline_reserved = broker.worst_case_buy_outlay_paise(
        baseline_order["shares"], baseline_order["entry_high_paise"]
    )
    assert baseline_order["reserved_amount_paise"] == expected_baseline_reserved
