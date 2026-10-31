"""
Live Agent Readiness Check (Week 2 Objective):
1. Verifies prompt generation & context assembly across all 5 LLM personas in dry-run mode.
2. Verifies decision parsing, schema validation, and order placement across all 5 LLM personas.
3. Verifies primary -> fallback failover (e.g. Gemini failure -> Groq fallback recovery) and llm_calls logging.
4. Verifies prompt token budgeting and metric alignment per persona.
See Plan_v3 §3.1, §3.2, §Week 2 Objectives.
"""
from datetime import datetime
import json
import sqlite3

import pytest

from agents.personas import all_personas, get_persona
from agents.runner import run as run_agents
from broker.engine import Broker
from core.clock import FakeClock
from core.money import rupees_to_paise
from ingestion.sync_ohlcv import ensure_schema as ensure_ohlcv_schema
from llm.client import FakeLLMClient
from scripts.init_db import init_db
from settings import settings
from tests.conftest import make_portfolio_db

RUN_DATE = "2026-10-19"
NOW_ISO = "2026-10-19T22:00:00+05:30"


def make_ohlcv_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:", isolation_level=None)
    conn.row_factory = sqlite3.Row
    ensure_ohlcv_schema(conn)
    return conn


def setup_multi_agent_environment(portfolio_conn: sqlite3.Connection, ohlcv_conn: sqlite3.Connection, clock: FakeClock):
    """Initializes tables, seeds agents, symbols, market calendar, feature snapshots, and watchlists."""
    init_db(portfolio_conn, clock)

    # 1. Pipeline status for watchlist must be SUCCESS
    portfolio_conn.execute(
        """
        INSERT INTO pipeline_runs (job, run_date, status, started_at, finished_at, detail)
        VALUES ('watchlist', ?, 'SUCCESS', ?, ?, NULL)
        ON CONFLICT(job, run_date) DO UPDATE SET status = 'SUCCESS'
        """,
        (RUN_DATE, NOW_ISO, NOW_ISO),
    )

    # 2. Add test symbols across sectors
    symbols = [
        ("TATAMOTORS", "Automobiles"),
        ("INFY", "Technology"),
        ("ITC", "FMCG"),
        ("SUNPHARMA", "Healthcare"),
        ("HDFCBANK", "Financial Services"),
    ]
    for ticker, sector in symbols:
        portfolio_conn.execute(
            "INSERT OR REPLACE INTO symbols (ticker, instrument_key, isin, company_name, sector, is_active) "
            "VALUES (?, ?, 'ISIN000000', ?, ?, 1)",
            (ticker, f"NSE_EQ|{ticker}", ticker, sector),
        )
        # Ensure fresh OHLCV candle for data-date integrity guard
        ohlcv_conn.execute(
            "INSERT OR REPLACE INTO ohlcv (ticker, trade_date, open, high, low, close, volume) "
            "VALUES (?, ?, 1000.0, 1020.0, 990.0, 1000.0, 500000)",
            (ticker, RUN_DATE),
        )

    # 3. Add rich feature snapshots
    features_base = {
        "close": 1000.0,
        "ema_20": 980.0,
        "ema_50": 960.0,
        "ema_200": 900.0,
        "ema_20_above_50": True,
        "rsi_14": 60.0,
        "macd_hist": 2.5,
        "volume_surge": 1.4,
        "atr_14": 20.0,
        "adx_14": 26.0,
        "dist_52w_high_pct": -4.0,
        "dist_52w_low_pct": 18.0,
        "roce_pct": 20.0,
        "roe_pct": 18.0,
        "pe": 18.0,
        "pb": 2.8,
        "peg": 0.8,
        "debt_to_equity": 0.4,
        "cfo_to_pat": 1.1,
        "pat_growth_yoy_pct": 16.0,
        "promoter_holding_pct": 52.0,
        "india_vix": 14.2,
        "regime": "NORMAL",
    }
    for ticker, _ in symbols:
        portfolio_conn.execute(
            "INSERT OR REPLACE INTO feature_snapshots (ticker, as_of_date, schema_version, features_json, created_at) "
            "VALUES (?, ?, 1, ?, ?)",
            (ticker, RUN_DATE, json.dumps(features_base), NOW_ISO),
        )

    # 4. Add watchlists for all 5 personas
    for persona in all_personas():
        for ticker, sector in symbols[:3]:  # Top 3 candidates on watchlist
            portfolio_conn.execute(
                """
                INSERT OR REPLACE INTO agent_watchlist (agent_id, ticker, sector, added_on, ttl_days, expires_on, intensity_score)
                VALUES (?, ?, ?, ?, ?, '2026-10-25', 2.5)
                """,
                (persona.id, ticker, sector, RUN_DATE, persona.ttl_days),
            )


def test_dry_run_prompt_generation_all_personas():
    """
    Verifies that all 5 personas generate compliant system and user prompts in dry-run mode,
    with estimated tokens safely within the PROMPT_TOKEN_CEILING.
    """
    clock = FakeClock(datetime(2026, 10, 19, 22, 0, 0))
    portfolio_conn = make_portfolio_db()
    ohlcv_conn = make_ohlcv_db()

    setup_multi_agent_environment(portfolio_conn, ohlcv_conn, clock)

    personas = all_personas()
    assert len(personas) == 5

    agent_ids = [p.id for p in personas]
    results = run_agents(
        agent_ids,
        as_of_date=RUN_DATE,
        clock=clock,
        portfolio_conn=portfolio_conn,
        ohlcv_conn=ohlcv_conn,
        dry_run=True,
    )

    for persona in personas:
        res = results[persona.id]
        assert res["status"] == "DRY_RUN", f"Agent {persona.id} failed dry run: {res}"
        assert res["token_estimate"] > 0
        assert res["token_estimate"] <= settings.PROMPT_TOKEN_CEILING, (
            f"Agent {persona.id} exceeded ceiling ({res['token_estimate']} > {settings.PROMPT_TOKEN_CEILING})"
        )


def test_decision_execution_and_orders_all_personas():
    """
    Verifies that all 5 personas can execute decisions with valid schema,
    save decisions with faithfulness checks, and place corresponding broker orders.
    """
    clock = FakeClock(datetime(2026, 10, 19, 22, 0, 0))
    portfolio_conn = make_portfolio_db()
    ohlcv_conn = make_ohlcv_db()

    setup_multi_agent_environment(portfolio_conn, ohlcv_conn, clock)

    # Mock Decision payloads tailored for each persona
    responses = {
        "simons": json.dumps({
            "decisions": [{
                "ticker": "TATAMOTORS",
                "action": "BUY",
                "shares": 10,
                "entry_low": 995.0,
                "entry_high": 1005.0,
                "stop_loss_price": 960.0,
                "target_price": 1080.0,
                "pre_mortem_risk": "Momentum exhaustion near resistance.",
                "reasoning": "Breakout confirmed by RSI and MACD expansion.",
                "cited_metrics": {"rsi_14": 60.0, "volume_surge": 1.4, "macd_hist": 2.5},
            }]
        }),
        "lynch": json.dumps({
            "decisions": [{
                "ticker": "ITC",
                "action": "BUY",
                "shares": 15,
                "entry_low": 990.0,
                "entry_high": 1010.0,
                "stop_loss_price": 950.0,
                "target_price": 1120.0,
                "pre_mortem_risk": "Input inflation impacting operating margins.",
                "reasoning": "High ROCE and favorable PEG below 1.0.",
                "cited_metrics": {"roce_pct": 20.0, "peg": 0.8, "debt_to_equity": 0.4},
            }]
        }),
        "marks": json.dumps({
            "decisions": [{
                "ticker": "TATAMOTORS",
                "action": "HOLD",
                "reasoning": "Market conditions not showing sufficient margin of safety.",
                "cited_metrics": {"dist_52w_low_pct": 18.0},
            }]
        }),
        "jhunjhunwala": json.dumps({
            "decisions": [{
                "ticker": "INFY",
                "action": "BUY",
                "shares": 8,
                "entry_low": 995.0,
                "entry_high": 1005.0,
                "stop_loss_price": 955.0,
                "target_price": 1150.0,
                "pre_mortem_risk": "Slowdown in BFSI client tech spending.",
                "reasoning": "High promoter quality and persistent compounding growth.",
                "cited_metrics": {"promoter_holding_pct": 52.0, "pat_growth_yoy_pct": 16.0, "volume_surge": 1.4},
            }]
        }),
        "varsity": json.dumps({
            "decisions": [{
                "ticker": "HDFCBANK",
                "action": "BUY",
                "shares": 10,
                "entry_low": 990.0,
                "entry_high": 1010.0,
                "stop_loss_price": 960.0,
                "target_price": 1100.0,
                "pre_mortem_risk": "Asset quality deterioration in retail unsecured book.",
                "reasoning": "Disciplined multi-indicator alignment with manageable leverage.",
                "cited_metrics": {"rsi_14": 60.0, "roce_pct": 20.0, "debt_to_equity": 0.4},
            }]
        }),
    }

    for persona in all_personas():
        client = FakeLLMClient(responses=[responses[persona.id]], model=settings.LLM_MODEL, provider="gemini")
        res = run_agents(
            [persona.id],
            as_of_date=RUN_DATE,
            clock=clock,
            portfolio_conn=portfolio_conn,
            ohlcv_conn=ohlcv_conn,
            llm_client=client,
            fake_llm=True,
        )
        assert res[persona.id]["status"] == "SUCCESS", f"Execution failed for {persona.id}: {res[persona.id]}"

        # Verify decision rows exist in portfolio.db for all candidates
        dec_rows = portfolio_conn.execute(
            "SELECT * FROM decisions WHERE agent_id = ? AND run_date = ?", (persona.id, RUN_DATE)
        ).fetchall()
        assert len(dec_rows) == 3, f"Expected 3 decisions (1 explicit + 2 auto-hold) for {persona.id}, got {len(dec_rows)}"

        buy_decs = [d for d in dec_rows if d["action"] == "BUY"]
        if buy_decs:
            dec = buy_decs[0]
            assert dec["shares"] > 0
            assert dec["entry_low_paise"] is not None
            assert dec["stop_paise"] is not None
            assert dec["target_paise"] is not None
            assert dec["faithfulness_score"] is not None
            assert dec["faithfulness_score"] >= 0.9  # Cited valid features

            # Verify broker placed a pending order
            orders = portfolio_conn.execute(
                "SELECT * FROM pending_orders WHERE agent_id = ? AND ticker = ? AND status = 'pending'",
                (persona.id, dec["ticker"]),
            ).fetchall()
            assert len(orders) == 1, f"Expected pending order for {persona.id} on {dec['ticker']}"


def test_primary_to_fallback_failover_simulation():
    """
    Simulates a primary provider failure (truncated length or malformed JSON from Gemini)
    and asserts automatic failover to the Groq fallback provider with llm_calls audit tracking.
    """
    clock = FakeClock(datetime(2026, 10, 19, 22, 0, 0))
    portfolio_conn = make_portfolio_db()
    ohlcv_conn = make_ohlcv_db()

    setup_multi_agent_environment(portfolio_conn, ohlcv_conn, clock)

    # Primary client produces truncated/broken reply on attempts 1 and 2
    primary_client = FakeLLMClient(
        responses=[
            {"text": '{"decisions": [{"ticker": "TATAMOTORS", "action": "BUY", "shares":', "finish_reason": "length"},
            {"text": '{"decisions": [{"ticker": "TATAMOTORS", "action": "BUY", "shares":', "finish_reason": "length"},
        ],
        model=settings.LLM_MODEL,
        provider=settings.LLM_PROVIDER,
    )

    # Fallback client (Llama 3.3 70B on Groq) produces clean valid decision
    fallback_client = FakeLLMClient(
        responses=[
            json.dumps({
                "decisions": [{
                    "ticker": "TATAMOTORS",
                    "action": "BUY",
                    "shares": 10,
                    "entry_low": 995.0,
                    "entry_high": 1005.0,
                    "stop_loss_price": 960.0,
                    "target_price": 1080.0,
                    "pre_mortem_risk": "Breakout pullback into support.",
                    "reasoning": "Fallback model recovered valid breakout setup.",
                    "cited_metrics": {"rsi_14": 60.0, "volume_surge": 1.4, "macd_hist": 2.5},
                }]
            })
        ],
        model=settings.LLM_FALLBACK_MODEL,
        provider=settings.LLM_FALLBACK_PROVIDER,
    )

    results = run_agents(
        ["simons"],
        as_of_date=RUN_DATE,
        clock=clock,
        portfolio_conn=portfolio_conn,
        ohlcv_conn=ohlcv_conn,
        llm_client=primary_client,
        fallback_client=fallback_client,
        fake_llm=False,  # Enable real repair and fallback dispatch loop
    )

    assert results["simons"]["status"] == "SUCCESS"
    assert results["simons"]["parse_status"] == "FALLBACK_SUCCESS"

    # Verify llm_calls table recorded the primary attempts and the successful fallback attempt
    llm_calls = portfolio_conn.execute(
        "SELECT id, model, provider, finish_reason, fallback_used FROM llm_calls WHERE agent_id = 'simons' ORDER BY id"
    ).fetchall()
    assert len(llm_calls) >= 2, f"Expected at least 2 LLM calls (primary + fallback), found {len(llm_calls)}"

    # Check that fallback was flagged
    fallback_calls = [c for c in llm_calls if c["fallback_used"] == 1]
    assert len(fallback_calls) == 1
    assert fallback_calls[0]["model"] == settings.LLM_FALLBACK_MODEL
    assert fallback_calls[0]["provider"] == settings.LLM_FALLBACK_PROVIDER
