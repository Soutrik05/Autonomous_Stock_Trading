"""
Shared infrastructure for baseline rules agents:
decision lifecycle, idempotency checks, order placement, and CLI invocation.
"""

import argparse
import json
import logging
import sqlite3
from typing import Callable

from broker.engine import Broker
from core.clock import Clock, SystemClock
from core.config import settings
from core.database import get_connection
from core.money import rupees_to_paise

logger = logging.getLogger(__name__)


def delete_baseline_decisions(conn: sqlite3.Connection, agent_id: str, run_date: str) -> None:
    """Removes existing decisions and associated pending order/return references for an agent run."""
    decision_rows = conn.execute(
        "SELECT id FROM decisions WHERE agent_id = ? AND run_date = ?", (agent_id, run_date)
    ).fetchall()
    if not decision_rows:
        return
    placeholders = ",".join("?" * len(decision_rows))
    dids = [r["id"] for r in decision_rows]

    conn.execute(f"UPDATE pending_orders SET decision_id = NULL WHERE decision_id IN ({placeholders})", dids)
    conn.execute(f"DELETE FROM forward_returns WHERE decision_id IN ({placeholders})", dids)
    conn.execute(f"DELETE FROM heuristic_applications WHERE decision_id IN ({placeholders})", dids)
    conn.execute("DELETE FROM decisions WHERE agent_id = ? AND run_date = ?", (agent_id, run_date))


def persist_baseline_decisions(
    portfolio_conn: sqlite3.Connection,
    agent_id: str,
    run_date: str,
    decisions: list[dict],
    clock: Clock,
) -> None:
    """Persists evaluated baseline candidate decisions to the decisions table."""
    now = clock.now_iso()
    for d in decisions:
        action = d["action"]
        shares = d["shares"]
        entry_low_p = rupees_to_paise(d["entry_low"]) if d.get("entry_low") else None
        entry_high_p = rupees_to_paise(d["entry_high"]) if d.get("entry_high") else None
        stop_p = rupees_to_paise(d["stop_loss_price"]) if d.get("stop_loss_price") else None
        target_p = rupees_to_paise(d["target_price"]) if d.get("target_price") else None
        cited_json = json.dumps(d["cited_metrics"]) if d.get("cited_metrics") else None

        portfolio_conn.execute(
            """
            INSERT INTO decisions
                (run_date, agent_id, ticker, source, action, shares, entry_low_paise, entry_high_paise,
                 stop_paise, target_paise, reasoning, pre_mortem_risk, cited_metrics_json,
                 faithfulness_score, snapshot_id, llm_call_id, created_at)
            VALUES (?, ?, ?, 'BASELINE', ?, ?, ?, ?, ?, ?, ?, NULL, ?, 1.0, ?, NULL, ?)
            ON CONFLICT(agent_id, ticker, run_date) DO UPDATE SET
                source = excluded.source, action = excluded.action, shares = excluded.shares,
                entry_low_paise = excluded.entry_low_paise, entry_high_paise = excluded.entry_high_paise,
                stop_paise = excluded.stop_paise, target_paise = excluded.target_paise,
                reasoning = excluded.reasoning, cited_metrics_json = excluded.cited_metrics_json,
                faithfulness_score = excluded.faithfulness_score, snapshot_id = excluded.snapshot_id,
                created_at = excluded.created_at
            """,
            (
                run_date,
                agent_id,
                d["ticker"],
                action,
                shares,
                entry_low_p,
                entry_high_p,
                stop_p,
                target_p,
                d["reasoning"],
                cited_json,
                d.get("snapshot_id"),
                now,
            ),
        )


def run_baseline_agent(
    agent_id: str,
    evaluate_fn: Callable[[sqlite3.Connection, str, Clock], list[dict]],
    run_date: str,
    clock: Clock,
    portfolio_conn: sqlite3.Connection,
    dry_run: bool = False,
    force: bool = False,
    no_orders: bool = False,
) -> dict:
    """Generic coordinator for baseline agent execution."""
    if not dry_run:
        w_status = portfolio_conn.execute(
            "SELECT status FROM pipeline_runs WHERE job = 'watchlist' AND run_date = ?", (run_date,)
        ).fetchone()
        status = w_status["status"] if w_status else None
        if status != "SUCCESS":
            return {"status": "FAILED", "detail": f"watchlist job for {run_date} is {status!r}, expected SUCCESS"}

        decisions_exist = portfolio_conn.execute(
            "SELECT 1 FROM decisions WHERE agent_id = ? AND run_date = ? LIMIT 1", (agent_id, run_date)
        ).fetchone()
        if decisions_exist:
            if not force:
                return {"status": "SKIPPED", "detail": "decisions already exist for baseline on this date"}
            has_filled = portfolio_conn.execute(
                """
                SELECT 1 FROM pending_orders WHERE status = 'filled'
                AND decision_id IN (SELECT id FROM decisions WHERE agent_id = ? AND run_date = ?)
                LIMIT 1
                """,
                (agent_id, run_date),
            ).fetchone()
            if has_filled:
                return {"status": "REFUSED", "detail": "cannot --force: order already filled"}

            Broker(portfolio_conn, clock).cancel_pending_for_run(agent_id, run_date)
            delete_baseline_decisions(portfolio_conn, agent_id, run_date)

    decisions = evaluate_fn(portfolio_conn, run_date, clock)

    if not dry_run:
        persist_baseline_decisions(portfolio_conn, agent_id, run_date, decisions, clock)

        order_summary = {}
        if not no_orders:
            broker = Broker(portfolio_conn, clock)
            order_summary = broker.place_orders_for_run(agent_id, run_date)

        return {"status": "SUCCESS", "decisions": len(decisions), "order_summary": order_summary}

    return {"status": "SUCCESS", "decisions": len(decisions), "dry_run": True}


def run_baseline_cli(agent_id: str, run_fn: Callable, description: str) -> None:
    """Standard CLI entrypoint for baseline scripts."""
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--date", dest="date_str", default=None, help="YYYY-MM-DD, default: today (IST)")
    parser.add_argument("--force", action="store_true", help="Regenerate decisions for this date")
    parser.add_argument("--dry-run", action="store_true", help="Evaluate rules without writing")
    parser.add_argument("--no-orders", action="store_true", help="Generate decisions but place no orders")
    args = parser.parse_args()

    clock = SystemClock()
    conn = get_connection(settings.PORTFOLIO_DB_PATH)
    try:
        run_date = args.date_str or clock.today().isoformat()
        res = run_fn(run_date, clock, conn, dry_run=args.dry_run, force=args.force, no_orders=args.no_orders)
        print(f"{agent_id}: {res}")
    finally:
        conn.close()

