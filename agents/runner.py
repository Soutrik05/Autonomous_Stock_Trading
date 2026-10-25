"""
One runner for all personas; idempotent per run date. After decisions are saved, it places
orders from them via broker.engine.Broker (no monitor, expiry or settlement yet -- orders just
sit 'pending' until those jobs exist).
Run as `python -m agents.runner --date YYYY-MM-DD --agent simons
    [--dry-run] [--fake-llm] [--force] [--no-orders]`.
See Plan_v3 §3.2, §4.2-§4.3.
"""
import argparse
import json
import sqlite3
import time
from typing import List, Optional

from agents.context_assembler import build_user_prompt, estimate_tokens
from agents.parsers import parse_with_repair_and_fallback
from agents.personas import get_persona
from broker.engine import Broker
from core.build_features import MAX_STALE_FRACTION, check_data_freshness
from core.clock import Clock, SystemClock
from core.database import get_connection
from core.money import rupees_to_paise
from core.schemas import AdjustDecision, BuyDecision, DecisionBatch, HoldDecision, SellDecision
from evaluation.faithfulness import compute_faithfulness
from llm.client import FakeLLMClient, LLMClient, LLMConfigError, build_provider, require_setting
from precompute.watchlist_refresh import get_review_pool
from settings import settings

JOB_NAME = "agents"
DECISION_BATCH_SCHEMA = DecisionBatch.model_json_schema()


# --- pipeline_runs wiring (same small pattern as ingestion/cli.py, core/build_features.py) ------

def _pipeline_status(conn, job: str, run_date: str) -> Optional[str]:
    row = conn.execute("SELECT status FROM pipeline_runs WHERE job = ? AND run_date = ?", (job, run_date)).fetchone()
    return row["status"] if row else None


def _upsert_terminal_run(conn, run_date: str, status: str, clock: Clock, detail: str = None) -> None:
    now = clock.now_iso()
    conn.execute(
        """
        INSERT INTO pipeline_runs (job, run_date, status, started_at, finished_at, detail)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(job, run_date) DO UPDATE SET
            status = excluded.status, started_at = excluded.started_at,
            finished_at = excluded.finished_at, detail = excluded.detail
        """,
        (JOB_NAME, run_date, status, now, now, detail),
    )


def _start_run(conn, run_date: str, clock: Clock) -> None:
    conn.execute(
        """
        INSERT INTO pipeline_runs (job, run_date, status, started_at, finished_at, detail)
        VALUES (?, ?, 'RUNNING', ?, NULL, NULL)
        ON CONFLICT(job, run_date) DO UPDATE SET
            status = 'RUNNING', started_at = excluded.started_at, finished_at = NULL, detail = NULL
        """,
        (JOB_NAME, run_date, clock.now_iso()),
    )


def _finish_run(conn, run_date: str, status: str, clock: Clock, detail: str = None) -> None:
    conn.execute(
        "UPDATE pipeline_runs SET status = ?, finished_at = ?, detail = ? WHERE job = ? AND run_date = ?",
        (status, clock.now_iso(), detail, JOB_NAME, run_date),
    )


# --- idempotency ----------------------------------------------------------------------------------

def _decisions_exist(conn, agent_id: str, run_date: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM decisions WHERE agent_id = ? AND run_date = ? LIMIT 1", (agent_id, run_date)
    ).fetchone()
    return row is not None


def _any_order_is_filled(conn, agent_id: str, run_date: str) -> bool:
    """--force may cancel still-pending orders and regenerate decisions, but never undo a fill."""
    row = conn.execute(
        """
        SELECT 1 FROM pending_orders
        WHERE status = 'filled'
          AND decision_id IN (SELECT id FROM decisions WHERE agent_id = ? AND run_date = ?)
        LIMIT 1
        """,
        (agent_id, run_date),
    ).fetchone()
    return row is not None


def _delete_decisions(conn, agent_id: str, run_date: str) -> None:
    decision_rows = conn.execute(
        "SELECT id FROM decisions WHERE agent_id = ? AND run_date = ?", (agent_id, run_date)
    ).fetchall()
    if not decision_rows:
        return
    placeholders = ",".join("?" * len(decision_rows))
    dids = [r["id"] for r in decision_rows]

    conn.execute(
        f"UPDATE pending_orders SET decision_id = NULL WHERE decision_id IN ({placeholders})", dids
    )
    conn.execute(
        f"DELETE FROM forward_returns WHERE decision_id IN ({placeholders})", dids
    )
    conn.execute(
        f"DELETE FROM heuristic_applications WHERE decision_id IN ({placeholders})", dids
    )
    conn.execute("DELETE FROM decisions WHERE agent_id = ? AND run_date = ?", (agent_id, run_date))


# --- data loading ----------------------------------------------------------------------------------

def _load_features_with_ids(conn: sqlite3.Connection, tickers: List[str], run_date: str):
    """Returns {ticker: (snapshot_id, features_dict)}."""
    if not tickers:
        return {}
    placeholders = ",".join("?" * len(tickers))
    rows = conn.execute(
        f"SELECT id, ticker, features_json FROM feature_snapshots "
        f"WHERE as_of_date = ? AND ticker IN ({placeholders})",
        (run_date, *tickers),
    ).fetchall()
    return {r["ticker"]: (r["id"], json.loads(r["features_json"])) for r in rows}


def _sector_by_ticker(conn: sqlite3.Connection, tickers: List[str]):
    if not tickers:
        return {}
    placeholders = ",".join("?" * len(tickers))
    rows = conn.execute(f"SELECT ticker, sector FROM symbols WHERE ticker IN ({placeholders})", tickers).fetchall()
    return {r["ticker"]: r["sector"] for r in rows}


def _intensity_by_ticker(conn: sqlite3.Connection, agent_id: str):
    rows = conn.execute("SELECT ticker, intensity_score FROM agent_watchlist WHERE agent_id = ?", (agent_id,)).fetchall()
    return {r["ticker"]: r["intensity_score"] for r in rows}


# --- writing decisions -------------------------------------------------------------------------------

def _decision_row_values(decision, agent_id, run_date, source, snapshot_id, llm_call_id, features, clock):
    base = dict(
        run_date=run_date, agent_id=agent_id, ticker=decision.ticker, source=source,
        action=decision.action, shares=None, entry_low_paise=None, entry_high_paise=None,
        stop_paise=None, target_paise=None, reasoning=getattr(decision, "reasoning", None),
        pre_mortem_risk=None, cited_metrics_json=None, faithfulness_score=None,
        snapshot_id=snapshot_id, llm_call_id=llm_call_id, created_at=clock.now_iso(),
    )
    if isinstance(decision, BuyDecision):
        base.update(
            shares=decision.shares,
            entry_low_paise=rupees_to_paise(decision.entry_low),
            entry_high_paise=rupees_to_paise(decision.entry_high),
            stop_paise=rupees_to_paise(decision.stop_loss_price),
            target_paise=rupees_to_paise(decision.target_price),
            pre_mortem_risk=decision.pre_mortem_risk,
            cited_metrics_json=json.dumps(decision.cited_metrics),
            faithfulness_score=compute_faithfulness(decision.cited_metrics, features or {}),
        )
    elif isinstance(decision, AdjustDecision):
        base.update(
            stop_paise=rupees_to_paise(decision.stop_loss_price) if decision.stop_loss_price is not None else None,
            target_paise=rupees_to_paise(decision.target_price) if decision.target_price is not None else None,
        )
    return base


def _insert_decision(conn: sqlite3.Connection, values: dict) -> None:
    conn.execute(
        """
        INSERT INTO decisions
            (run_date, agent_id, ticker, source, action, shares, entry_low_paise, entry_high_paise,
             stop_paise, target_paise, reasoning, pre_mortem_risk, cited_metrics_json,
             faithfulness_score, snapshot_id, llm_call_id, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(agent_id, ticker, run_date) DO UPDATE SET
            source = excluded.source, action = excluded.action, shares = excluded.shares,
            entry_low_paise = excluded.entry_low_paise, entry_high_paise = excluded.entry_high_paise,
            stop_paise = excluded.stop_paise, target_paise = excluded.target_paise,
            reasoning = excluded.reasoning, pre_mortem_risk = excluded.pre_mortem_risk,
            cited_metrics_json = excluded.cited_metrics_json,
            faithfulness_score = excluded.faithfulness_score, snapshot_id = excluded.snapshot_id,
            llm_call_id = excluded.llm_call_id, created_at = excluded.created_at
        """,
        (
            values["run_date"], values["agent_id"], values["ticker"], values["source"], values["action"],
            values["shares"], values["entry_low_paise"], values["entry_high_paise"], values["stop_paise"],
            values["target_paise"], values["reasoning"], values["pre_mortem_risk"],
            values["cited_metrics_json"], values["faithfulness_score"], values["snapshot_id"],
            values["llm_call_id"], values["created_at"],
        ),
    )


def _insert_llm_call(conn: sqlite3.Connection, agent_id, run_date, model, prompt, response,
                      tokens_in, tokens_out, latency_ms, parse_status, finish_reason,
                      reasoning_tokens, clock: Clock, provider=None, thinking_tokens=None,
                      fallback_used=False) -> int:
    cur = conn.execute(
        """
        INSERT INTO llm_calls (agent_id, run_date, model, prompt, response, tokens_in, tokens_out,
                                latency_ms, parse_status, finish_reason, reasoning_tokens, created_at,
                                provider, thinking_tokens, fallback_used)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (agent_id, run_date, model, prompt, response, tokens_in, tokens_out, latency_ms,
         parse_status, finish_reason, reasoning_tokens, clock.now_iso(), provider, thinking_tokens,
         int(fallback_used)),
    )
    return cur.lastrowid


# --- the single-agent run --------------------------------------------------------------------------

def run_one_agent(
    agent_id: str, run_date: str, clock: Clock, portfolio_conn: sqlite3.Connection,
    ohlcv_conn: Optional[sqlite3.Connection] = None, llm_client: Optional[LLMClient] = None,
    dry_run: bool = False, force: bool = False, no_orders: bool = False,
    fallback_client: Optional[LLMClient] = None,
) -> dict:
    persona = get_persona(agent_id)

    if not dry_run:
        watchlist_status = _pipeline_status(portfolio_conn, "watchlist", run_date)
        if watchlist_status != "SUCCESS":
            detail = f"watchlist status for {run_date} is {watchlist_status!r}, expected SUCCESS"
            _upsert_terminal_run(portfolio_conn, run_date, "FAILED", clock, detail=detail)
            return {"status": "FAILED", "detail": detail}

        if _decisions_exist(portfolio_conn, agent_id, run_date):
            if not force:
                return {"status": "SKIPPED", "detail": "decisions already exist for this agent/date"}
            if _any_order_is_filled(portfolio_conn, agent_id, run_date):
                return {
                    "status": "REFUSED",
                    "detail": "cannot --force: an order for one of this agent's decisions for "
                    "this date has already been filled",
                }
            Broker(portfolio_conn, clock).cancel_pending_for_run(agent_id, run_date)
            _delete_decisions(portfolio_conn, agent_id, run_date)

    review_pool = get_review_pool(portfolio_conn, agent_id, run_date)
    tickers = [r["ticker"] for r in review_pool]

    if not dry_run and ohlcv_conn is not None and tickers:
        freshness = check_data_freshness(ohlcv_conn, portfolio_conn, tickers, run_date)
        if freshness["applicable"] and freshness["stale_fraction"] > MAX_STALE_FRACTION:
            detail = (
                f"data-date integrity check failed: {freshness['stale']}/{freshness['checked']} "
                f"review-pool tickers ({freshness['stale_fraction']:.1%}) have a latest OHLCV "
                f"candle date other than {run_date} (a trading day); exceeds the "
                f"{MAX_STALE_FRACTION:.0%} tolerance. Stale tickers: {freshness['stale_tickers']}"
            )
            _upsert_terminal_run(portfolio_conn, run_date, "FAILED", clock, detail=detail[:500])
            return {"status": "FAILED", "detail": detail}

    features_with_ids = _load_features_with_ids(portfolio_conn, tickers, run_date)
    features_by_ticker = {t: f for t, (sid, f) in features_with_ids.items()}
    sector_by_ticker = _sector_by_ticker(portfolio_conn, tickers)
    intensity_by_ticker = _intensity_by_ticker(portfolio_conn, agent_id)

    user_prompt, trim_info = build_user_prompt(
        portfolio_conn, agent_id, review_pool, features_by_ticker, sector_by_ticker,
        intensity_by_ticker, persona.system_prompt, persona.technical_hurdles, persona.fundamental_hurdles,
    )
    token_estimate = estimate_tokens(persona.system_prompt) + estimate_tokens(user_prompt)

    if dry_run:
        print(f"--- SYSTEM PROMPT ({estimate_tokens(persona.system_prompt)} est. tokens) ---")
        print(persona.system_prompt)
        print(f"\n--- USER PROMPT ({estimate_tokens(user_prompt)} est. tokens) ---")
        print(user_prompt)
        print(f"\n--- TOTAL estimated tokens: {token_estimate} (trim: {trim_info}) ---")
        return {"status": "DRY_RUN", "token_estimate": token_estimate, "trim_info": trim_info}

    _start_run(portfolio_conn, run_date, clock)
    try:
        decisions, parse_status, dropped, final_result, attempts = parse_with_repair_and_fallback(
            llm_client, persona.system_prompt, user_prompt, tickers, fallback=fallback_client,
            reasoning_effort=settings.LLM_REASONING_EFFORT, max_output_tokens=settings.LLM_MAX_OUTPUT_TOKENS,
            response_schema=DECISION_BATCH_SCHEMA,
        )

        llm_call_id = None
        for attempt in attempts:  # log every actual LLM call made (at most 3), per day-5a
            result = attempt["result"]
            llm_call_id = _insert_llm_call(
                portfolio_conn, agent_id, run_date, result.model, user_prompt, result.text,
                result.tokens_in, result.tokens_out, result.latency_ms, attempt["parse_status"],
                result.finish_reason, result.reasoning_tokens, clock, provider=result.provider,
                thinking_tokens=result.thinking_tokens, fallback_used=attempt["fallback_used"],
            )

        for decision in decisions:
            snapshot_id, features = features_with_ids.get(decision.ticker, (None, {}))
            values = _decision_row_values(
                decision, agent_id, run_date, "LLM", snapshot_id, llm_call_id, features, clock
            )
            _insert_decision(portfolio_conn, values)

        order_summary = None
        if not no_orders:
            order_summary = Broker(portfolio_conn, clock).place_orders_for_run(agent_id, run_date)
    except Exception as exc:
        _finish_run(portfolio_conn, run_date, "FAILED", clock, detail=str(exc)[:500])
        raise

    _finish_run(
        portfolio_conn, run_date, "SUCCESS", clock,
        detail=f"parse_status={parse_status} decisions={len(decisions)} dropped_unknown={dropped} "
        f"calls={len(attempts)} orders={order_summary}",
    )
    return {
        "status": "SUCCESS", "parse_status": parse_status, "decisions": len(decisions),
        "dropped_unknown": dropped, "llm_call_id": llm_call_id, "calls_made": len(attempts),
        "tokens_in": final_result.tokens_in, "tokens_out": final_result.tokens_out,
        "latency_ms": final_result.latency_ms, "model": final_result.model,
        "finish_reason": final_result.finish_reason, "reasoning_tokens": final_result.reasoning_tokens,
        "provider": final_result.provider, "thinking_tokens": final_result.thinking_tokens,
        "fallback_used": attempts[-1]["fallback_used"] if attempts else False,
        "token_estimate": token_estimate, "order_summary": order_summary,
    }


def run(
    agent_ids: List[str], as_of_date: str = None, clock: Clock = None, dry_run: bool = False,
    fake_llm: bool = False, force: bool = False, no_orders: bool = False,
    portfolio_conn: sqlite3.Connection = None, ohlcv_conn: Optional[sqlite3.Connection] = None,
    llm_client: Optional[LLMClient] = None, fallback_client: Optional[LLMClient] = None,
) -> dict:
    clock = clock or SystemClock()
    owns_conn = portfolio_conn is None
    owns_ohlcv = ohlcv_conn is None and not dry_run
    portfolio_conn = portfolio_conn or get_connection(settings.PORTFOLIO_DB_PATH)
    if ohlcv_conn is None and not dry_run:
        ohlcv_conn = get_connection(settings.OHLCV_DB_PATH)
    try:
        run_date = as_of_date or clock.today().isoformat()

        if llm_client is None and not dry_run:
            if fake_llm:
                llm_client = FakeLLMClient()
            else:
                llm_client = build_provider(
                    settings.LLM_PROVIDER, model=require_setting(settings.LLM_MODEL, "LLM_MODEL"),
                )
                try:
                    fallback_client = build_provider(
                        settings.LLM_FALLBACK_PROVIDER,
                        model=require_setting(settings.LLM_FALLBACK_MODEL, "LLM_FALLBACK_MODEL"),
                    )
                except LLMConfigError as exc:
                    print(f"warning: fallback provider {settings.LLM_FALLBACK_PROVIDER!r} unavailable "
                          f"({exc}); continuing with {settings.LLM_PROVIDER!r} only, no fallback.")
                    fallback_client = None

        results = {}
        for i, agent_id in enumerate(agent_ids):
            results[agent_id] = run_one_agent(
                agent_id, run_date, clock, portfolio_conn, ohlcv_conn=ohlcv_conn,
                llm_client=llm_client, dry_run=dry_run, force=force, no_orders=no_orders,
                fallback_client=fallback_client if not fake_llm else None,
            )
            is_last = i == len(agent_ids) - 1
            if not dry_run and not fake_llm and not is_last:
                time.sleep(settings.AGENT_RUN_DELAY_SEC)
        return results
    finally:
        if owns_conn:
            portfolio_conn.close()
        if owns_ohlcv and ohlcv_conn is not None:
            ohlcv_conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Nightly agent decision runner.")
    parser.add_argument("--date", dest="date_str", default=None, help="YYYY-MM-DD, default: today (IST)")
    parser.add_argument("--agent", dest="agent_id", default="simons", help="Persona id, e.g. simons")
    parser.add_argument("--dry-run", dest="dry_run", action="store_true", help="Print the prompt, make no LLM call")
    parser.add_argument("--fake-llm", dest="fake_llm", action="store_true", help="Use FakeLLMClient instead of a real provider")
    parser.add_argument("--force", dest="force", action="store_true", help="Re-run even if decisions already exist")
    parser.add_argument("--no-orders", dest="no_orders", action="store_true", help="Save decisions but place no orders")
    args = parser.parse_args()

    results = run(
        [args.agent_id], as_of_date=args.date_str, dry_run=args.dry_run, fake_llm=args.fake_llm,
        force=args.force, no_orders=args.no_orders,
    )
    for agent_id, result in results.items():
        print(f"{agent_id}: {result}")


if __name__ == "__main__":
    main()
