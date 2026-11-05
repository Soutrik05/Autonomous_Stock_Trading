"""
Integration tests for Week 2:
1. Multi-agent watchlist funnel audit across all 5 LLM personas (differentiation & stage counts).
2. Funnel audit logging to activity_log with stage0, stage1, and final counts.
3. Bear market starvation behavior: graceful degradation when no stocks pass hurdles (hold cash, no crashes).
4. End-to-end execution of execute_nightly_pipeline_pass for all personas.
See Plan_v3 §3.1, §6, §Week 2 Objectives.
"""
from datetime import date, datetime, timedelta
import json
import sqlite3
from typing import Dict

import pytest

from agents.personas import all_personas
from agents.runner import run as run_agents
from core.clock import FakeClock
from ingestion.sync_ohlcv import ensure_schema as ensure_ohlcv_schema
from llm.client import FakeLLMClient
from watchlist.watchlist_refresh import get_review_pool, run as run_watchlist_refresh
from scheduler import execute_nightly_pipeline_pass, is_nightly_pipeline_complete
from scripts.init_db import init_db
from tests.conftest import (
    make_passing_lynch_features,
    make_passing_marks_features,
    make_passing_rj_features,
    make_passing_simons_features,
    make_passing_varsity_features,
    make_portfolio_db,
)

RUN_DATE = "2026-10-19"
NOW_ISO = "2026-10-19T20:00:00+05:30"


def make_ohlcv_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:", isolation_level=None)
    conn.row_factory = sqlite3.Row
    ensure_ohlcv_schema(conn)
    return conn


def insert_symbol(conn: sqlite3.Connection, ticker: str, sector: str) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO symbols (ticker, instrument_key, isin, company_name, sector, is_active) "
        "VALUES (?, ?, 'ISIN0000000', 'Test Company', ?, 1)",
        (ticker, f"NSE_EQ|{ticker}", sector),
    )


def insert_ohlcv(
    ohlcv_conn: sqlite3.Connection,
    ticker: str,
    as_of: str = RUN_DATE,
    n_days: int = 25,
    volume: int = 600_000,
    close: float = 100.0,
    boost_last_n: int = 5,
    boost_volume: int = 900_000,
) -> None:
    end = date.fromisoformat(as_of)
    for i in range(n_days):
        d = end - timedelta(days=n_days - 1 - i)
        v = boost_volume if (boost_last_n and i >= n_days - boost_last_n) else volume
        ohlcv_conn.execute(
            "INSERT OR REPLACE INTO ohlcv (ticker, trade_date, open, high, low, close, volume) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (ticker, d.isoformat(), close, close, close, close, v),
        )
    ohlcv_conn.execute(
        "INSERT OR REPLACE INTO ticker_status (ticker, status, updated_at) VALUES (?, 'OK', ?)",
        (ticker, NOW_ISO),
    )


def insert_snapshot(portfolio_conn: sqlite3.Connection, ticker: str, features: dict, as_of: str = RUN_DATE) -> None:
    portfolio_conn.execute(
        "INSERT OR REPLACE INTO feature_snapshots (ticker, as_of_date, schema_version, features_json, created_at) "
        "VALUES (?, ?, 1, ?, ?)",
        (ticker, as_of, json.dumps(features), NOW_ISO),
    )


def mark_pipeline_job(portfolio_conn: sqlite3.Connection, job: str, status: str = "SUCCESS", as_of: str = RUN_DATE) -> None:
    portfolio_conn.execute(
        """
        INSERT INTO pipeline_runs (job, run_date, status, started_at, finished_at, detail)
        VALUES (?, ?, ?, ?, ?, NULL)
        ON CONFLICT(job, run_date) DO UPDATE SET
            status = excluded.status, started_at = excluded.started_at, finished_at = excluded.finished_at
        """,
        (job, as_of, status, NOW_ISO, NOW_ISO),
    )


def test_multi_agent_funnel_audit_and_persona_differentiation():
    """
    Sets up 5 stocks representing distinct archetypes.
    Verifies that Stage 0-3 funnel partitions them into the right persona watchlists,
    and records accurate FUNNEL_COUNTS into activity_log for all 5 personas.
    """
    clock = FakeClock(datetime(2026, 10, 19, 20, 0, 0))
    portfolio_conn = make_portfolio_db()
    ohlcv_conn = make_ohlcv_db()

    init_db(portfolio_conn, clock)
    mark_pipeline_job(portfolio_conn, "features", "SUCCESS", RUN_DATE)

    # 1. Tech Momentum Leader -> Targets Simons
    insert_symbol(portfolio_conn, "TECH_MOM", "Technology")
    insert_ohlcv(ohlcv_conn, "TECH_MOM")
    insert_snapshot(
        portfolio_conn,
        "TECH_MOM",
        make_passing_simons_features(
            close=500.0,
            ema_20=490.0,
            ema_50=480.0,
            ema_200=450.0,
            rsi_14=62.0,
            volume_surge=1.6,
            macd_hist=3.0,
            atr_14=12.0,
            adx_14=25.0,
            kaufman_er_20=0.40,
            # Fundamental: Fails Lynch (peg high, roce low, d/e high)
            peg=1.8,
            roce_pct=10.0,
            debt_to_equity=1.4,
            cfo_to_pat=0.6,
            pat_growth_yoy_pct=5.0,
            promoter_holding_pct=35.0,
            dist_52w_low_pct=40.0,
        ),
    )

    # 2. Consumer GARP Leader -> Targets Lynch
    insert_symbol(portfolio_conn, "CONS_GARP", "FMCG")
    insert_ohlcv(ohlcv_conn, "CONS_GARP")
    insert_snapshot(
        portfolio_conn,
        "CONS_GARP",
        make_passing_lynch_features(
            close=200.0,
            ema_200=180.0,
            ema_20_above_50=False,
            rsi_14=52.0,
            volume_surge=0.9,
            macd_hist=-0.5,
            # Fundamental: High ROCE, low PEG, low D/E, strong CFO/PAT & growth
            peg=0.65,
            roce_pct=24.0,
            debt_to_equity=0.25,
            cfo_to_pat=1.3,
            pat_growth_yoy_pct=22.0,
            promoter_holding_pct=52.0,
            dist_52w_low_pct=25.0,
        ),
    )

    # 3. Industrial Contrarian Leader -> Targets Marks
    insert_symbol(portfolio_conn, "IND_CONT", "Industrials")
    insert_ohlcv(ohlcv_conn, "IND_CONT")
    insert_snapshot(
        portfolio_conn,
        "IND_CONT",
        make_passing_marks_features(
            close=80.0,
            ema_200=75.0,
            ema_20_above_50=False,
            rsi_14=29.0,  # Oversold (< 35)
            volume_surge=0.8,
            macd_hist=-1.2,
            # Fundamental: Low debt, decent promoter holding, near 52w low
            peg=1.5,
            roce_pct=8.0,
            debt_to_equity=0.4,
            cfo_to_pat=0.5,
            pat_growth_yoy_pct=-4.0,
            promoter_holding_pct=48.0,
            dist_52w_low_pct=12.0,  # <= 20%
        ),
    )

    # 4. Pharma Growth Compounder -> Targets Jhunjhunwala
    insert_symbol(portfolio_conn, "PHAR_GROW", "Healthcare")
    insert_ohlcv(ohlcv_conn, "PHAR_GROW")
    insert_snapshot(
        portfolio_conn,
        "PHAR_GROW",
        make_passing_rj_features(
            close=350.0,
            ema_20=340.0,
            ema_50=330.0,
            ema_200=300.0,
            ema_20_above_50=True,
            rsi_14=58.0,
            volume_surge=1.5,
            macd_hist=1.2,
            # Fundamental: High promoter holding, strong earnings expansion
            peg=1.2,
            roce_pct=16.0,
            debt_to_equity=0.3,
            pat_growth_yoy_pct=20.0,
            promoter_holding_pct=58.0,
            dist_52w_low_pct=30.0,
        ),
    )

    # 5. Financials Balanced Hybrid -> Targets Varsity
    insert_symbol(portfolio_conn, "FIN_BAL", "Financial Services")
    insert_ohlcv(ohlcv_conn, "FIN_BAL")
    insert_snapshot(
        portfolio_conn,
        "FIN_BAL",
        make_passing_varsity_features(
            close=150.0,
            ema_20=148.0,
            ema_50=145.0,
            ema_200=140.0,
            ema_20_above_50=True,
            rsi_14=54.0,  # Between 45 and 68
            volume_surge=1.0,
            macd_hist=0.2,
            # Fundamental: ROCE >= 12, ROE >= 12, D/E <= 1.5
            peg=1.1,
            roce_pct=15.0,
            roe_pct=14.0,
            debt_to_equity=1.1,
            cfo_to_pat=0.9,
            pat_growth_yoy_pct=11.0,
            promoter_holding_pct=42.0,
            dist_52w_low_pct=22.0,
        ),
    )

    # Execute watchlist refresh for all personas in one call
    result = run_watchlist_refresh(
        as_of_date=RUN_DATE,
        agent_id="all",
        clock=clock,
        portfolio_conn=portfolio_conn,
        ohlcv_conn=ohlcv_conn,
    )
    assert result["status"] == "SUCCESS", f"Expected SUCCESS but got: {result}"

    # Verify Simons watchlist
    simons_wl = [r["ticker"] for r in result["results"]["simons"]["watchlist"]]
    assert "TECH_MOM" in simons_wl
    assert "CONS_GARP" not in simons_wl
    assert "IND_CONT" not in simons_wl

    # Verify Lynch watchlist
    lynch_wl = [r["ticker"] for r in result["results"]["lynch"]["watchlist"]]
    assert "CONS_GARP" in lynch_wl
    assert "TECH_MOM" not in lynch_wl
    assert "IND_CONT" not in lynch_wl

    # Verify Marks watchlist
    marks_wl = [r["ticker"] for r in result["results"]["marks"]["watchlist"]]
    assert "IND_CONT" in marks_wl
    assert "TECH_MOM" not in marks_wl
    assert "CONS_GARP" not in marks_wl

    # Verify Jhunjhunwala watchlist
    rj_wl = [r["ticker"] for r in result["results"]["jhunjhunwala"]["watchlist"]]
    assert "PHAR_GROW" in rj_wl
    assert "IND_CONT" not in rj_wl

    # Verify StockMinds Core / Varsity watchlist
    core_wl = [r["ticker"] for r in result["results"]["varsity"]["watchlist"]]
    assert "FIN_BAL" in core_wl
    assert "IND_CONT" not in core_wl

    # Audit Funnel Counts in activity_log
    log_rows = portfolio_conn.execute(
        "SELECT agent_id, description, metadata_json FROM activity_log WHERE event_type = 'FUNNEL_COUNTS'"
    ).fetchall()
    assert len(log_rows) == 5, f"Expected 5 FUNNEL_COUNTS logs, found {len(log_rows)}"

    logged_agents = {r["agent_id"] for r in log_rows}
    assert logged_agents == {"simons", "lynch", "marks", "jhunjhunwala", "varsity"}

    for r in log_rows:
        meta = json.loads(r["metadata_json"])
        assert "stage0" in meta
        assert "stage1" in meta
        assert "final" in meta
        assert meta["stage0"] == 5  # all 5 stocks passed Stage 0 turnover/liquidity
        assert meta["stage1"] >= 1  # each persona had at least 1 survivor


def test_bear_market_starvation_behavior():
    """
    Simulates a harsh bear market where:
    - All tickers trade below EMA200 (trend filter fail)
    - RSI values are out of bounds
    - Earnings growth is deeply negative and D/E is excessive.
    Verifies:
    - Funnel completes with 0 survivors gracefully.
    - Zero rows in agent_watchlist.
    - get_review_pool returns empty list.
    - Agent runner runs cleanly with 0 decisions, 0 orders, preserving 100% cash.
    """
    clock = FakeClock(datetime(2026, 10, 19, 20, 0, 0))
    portfolio_conn = make_portfolio_db()
    ohlcv_conn = make_ohlcv_db()

    init_db(portfolio_conn, clock)
    mark_pipeline_job(portfolio_conn, "features", "SUCCESS", RUN_DATE)

    for i in range(3):
        ticker = f"BEAR_STOCK_{i}"
        insert_symbol(portfolio_conn, ticker, "Capital Goods")
        insert_ohlcv(ohlcv_conn, ticker)
        insert_snapshot(
            portfolio_conn,
            ticker,
            {
                "close": 50.0,
                "ema_200": 100.0,  # Below EMA200
                "ema_20_above_50": False,
                "rsi_14": 88.0,  # Extreme overbought
                "volume_surge": 0.4,
                "macd_hist": -2.0,
                "peg": 5.0,
                "roce_pct": -8.0,
                "debt_to_equity": 4.5,
                "cfo_to_pat": -0.5,
                "pat_growth_yoy_pct": -30.0,
                "promoter_holding_pct": 15.0,
                "dist_52w_low_pct": 60.0,
            },
        )

    # Run watchlist refresh for all personas
    res = run_watchlist_refresh(
        as_of_date=RUN_DATE,
        agent_id="all",
        clock=clock,
        portfolio_conn=portfolio_conn,
        ohlcv_conn=ohlcv_conn,
    )
    assert res["status"] == "SUCCESS"

    for persona in all_personas():
        agent_counts = res["results"][persona.id]["counts"]
        assert agent_counts["stage1"] == 0, f"Expected 0 stage1 survivors for {persona.id}"
        assert agent_counts["final"] == 0, f"Expected 0 final watchlist for {persona.id}"

        # Review pool must be completely empty
        pool = get_review_pool(portfolio_conn, persona.id, RUN_DATE)
        assert pool == [], f"Expected empty review pool for {persona.id}, got {pool}"

    # Verify agent runner starvation execution
    clock_2200 = FakeClock(datetime(2026, 10, 19, 22, 0, 0))
    agent_ids = [p.id for p in all_personas()] + ["baseline-simons-rules"]

    agent_results = run_agents(
        agent_ids,
        as_of_date=RUN_DATE,
        clock=clock_2200,
        portfolio_conn=portfolio_conn,
        ohlcv_conn=ohlcv_conn,
        fake_llm=True,
    )

    for agent_id in agent_ids:
        assert agent_results[agent_id]["status"] == "SUCCESS"

    # Invariants: 0 decisions, 0 orders, 0 trades, cash fully intact
    total_decisions = portfolio_conn.execute("SELECT COUNT(*) FROM decisions").fetchone()[0]
    total_orders = portfolio_conn.execute("SELECT COUNT(*) FROM pending_orders").fetchone()[0]
    assert total_decisions == 0
    assert total_orders == 0

    for agent_id in agent_ids:
        cash = portfolio_conn.execute(
            "SELECT cash_paise FROM agents WHERE id = ?", (agent_id,)
        ).fetchone()[0]
        assert cash == 10_000_000, f"Cash altered for {agent_id}: {cash}"


def test_scheduler_execute_nightly_pipeline_pass(mock_upstox_client):
    """
    Verifies that scheduler.execute_nightly_pipeline_pass executes the full
    ingestion -> features -> watchlist (all personas) flow and marks the run complete.
    """
    clock = FakeClock(datetime(2026, 10, 19, 20, 0, 0))
    portfolio_conn = make_portfolio_db()

    # Pre-seed symbol & calendar
    portfolio_conn.execute(
        "INSERT INTO symbols (ticker, instrument_key, isin, company_name, sector, is_active) "
        "VALUES ('TATAMOTORS', 'NSE_EQ|INE155A01022', 'INE155A01022', 'Tata Motors Ltd', 'Automobiles', 1)"
    )
    for dt in ("2026-10-19", "2026-10-20"):
        portfolio_conn.execute(
            "INSERT OR REPLACE INTO market_calendar (trade_date, is_trading_day, session_type, note) "
            "VALUES (?, 1, 'NORMAL', 'Trading Day')",
            (dt,),
        )

    # Mock upstox client in ingestion.cli.run
    from unittest.mock import patch
    with patch("ingestion.cli.UpstoxClient", return_value=mock_upstox_client):
        status = execute_nightly_pipeline_pass(clock, portfolio_conn, RUN_DATE)

    assert status == "SUCCESS"
    assert is_nightly_pipeline_complete(portfolio_conn, RUN_DATE) is True

    # Check pipeline_runs records
    runs = {
        row["job"]: row["status"]
        for row in portfolio_conn.execute(
            "SELECT job, status FROM pipeline_runs WHERE run_date = ?", (RUN_DATE,)
        ).fetchall()
    }
    assert runs.get("ingestion") == "SUCCESS"
    assert runs.get("features") == "SUCCESS"
    assert runs.get("watchlist") == "SUCCESS"
