"""
The sixth agent, baseline-simons-rules: pure Python entry/exit rules trading through the same broker.
Evaluates the exact candidate review pool that LLM Simons saw, with zero LLM calls.
See Plan_v3 §6.1.
"""
import argparse
import json
import logging
import sqlite3
from datetime import date
from typing import List, Optional

from broker.engine import Broker
from core.clock import Clock, SystemClock
from core.database import get_connection
from core.money import rupees_to_paise
from core.schemas import BuyDecision, DecisionBatch, HoldDecision, SellDecision
from evaluation.faithfulness import compute_faithfulness
from precompute.watchlist_refresh import get_review_pool
from settings import settings

logger = logging.getLogger(__name__)
AGENT_ID = "baseline-simons-rules"
JOB_NAME = "baseline-simons-rules"


def _delete_baseline_decisions(conn: sqlite3.Connection, run_date: str) -> None:
    decision_rows = conn.execute(
        "SELECT id FROM decisions WHERE agent_id = ? AND run_date = ?", (AGENT_ID, run_date)
    ).fetchall()
    if not decision_rows:
        return
    placeholders = ",".join("?" * len(decision_rows))
    dids = [r["id"] for r in decision_rows]

    conn.execute(f"UPDATE pending_orders SET decision_id = NULL WHERE decision_id IN ({placeholders})", dids)
    conn.execute(f"DELETE FROM forward_returns WHERE decision_id IN ({placeholders})", dids)
    conn.execute(f"DELETE FROM heuristic_applications WHERE decision_id IN ({placeholders})", dids)
    conn.execute("DELETE FROM decisions WHERE agent_id = ? AND run_date = ?", (AGENT_ID, run_date))


def evaluate_baseline_candidates(
    portfolio_conn: sqlite3.Connection,
    run_date: str,
    clock: Clock,
) -> List[dict]:
    """Generates rules-based decisions for every candidate in Simons' review pool."""
    # Input: the exact review pool LLM Simons evaluated
    review_pool = get_review_pool(portfolio_conn, "simons", run_date)
    tickers = [r["ticker"] for r in review_pool]
    if not tickers:
        return []

    placeholders = ",".join("?" * len(tickers))
    rows = portfolio_conn.execute(
        f"SELECT id, ticker, features_json FROM feature_snapshots "
        f"WHERE as_of_date = ? AND ticker IN ({placeholders})",
        (run_date, *tickers),
    ).fetchall()
    features_by_ticker = {r["ticker"]: (r["id"], json.loads(r["features_json"])) for r in rows}

    open_positions = portfolio_conn.execute(
        "SELECT * FROM positions WHERE agent_id = ? AND status = 'OPEN'", (AGENT_ID,)
    ).fetchall()
    held_by_ticker = {p["ticker"]: p for p in open_positions}
    current_open_count = len(open_positions)

    decisions = []
    for candidate in review_pool:
        ticker = candidate["ticker"]
        snapshot_id, feats = features_by_ticker.get(ticker, (None, {}))
        close = feats.get("close")
        ema_20 = feats.get("ema_20")
        rsi_14 = feats.get("rsi_14")
        macd_hist = feats.get("macd_hist")
        volume_surge = feats.get("volume_surge")
        atr_14 = feats.get("atr_14")
        ema_20_above_50 = feats.get("ema_20_above_50")

        if ticker in held_by_ticker:
            pos = held_by_ticker[ticker]
            # Exit rule: close < ema_20 OR target reached
            target_reached = (close is not None and pos["target_paise"] is not None and close * 100 >= pos["target_paise"])
            if (ema_20 is not None and close is not None and close < ema_20) or target_reached:
                reason = "Rule exit: close < ema_20" if (ema_20 and close and close < ema_20) else "Rule exit: target reached"
                decisions.append({
                    "ticker": ticker, "action": "SELL", "shares": None, "entry_low": None,
                    "entry_high": None, "stop_loss_price": None, "target_price": None,
                    "reasoning": reason, "cited_metrics": None, "snapshot_id": snapshot_id,
                })
            else:
                decisions.append({
                    "ticker": ticker, "action": "HOLD", "shares": None, "entry_low": None,
                    "entry_high": None, "stop_loss_price": None, "target_price": None,
                    "reasoning": "Rules hold: above 20 EMA and target not reached", "cited_metrics": None,
                    "snapshot_id": snapshot_id,
                })
        else:
            # Entry rule (BUY): ema_20_above_50, rsi in [55, 70], volume_surge >= 1.2, macd_hist > 0
            meets_criteria = (
                ema_20_above_50 is True
                and rsi_14 is not None and 55 <= rsi_14 <= 70
                and volume_surge is not None and volume_surge >= 1.2
                and macd_hist is not None and macd_hist > 0
                and atr_14 is not None and atr_14 > 0
                and close is not None and close > 0
            )
            can_buy = meets_criteria and current_open_count < settings.MAX_OPEN_POSITIONS_PER_AGENT

            if can_buy:
                entry_low = round(close - 0.25 * atr_14, 2)
                entry_high = round(close + 0.25 * atr_14, 2)
                stop_loss = round(close - 2.0 * atr_14, 2)
                target = round(close + 3.0 * atr_14, 2)

                # Size: 10% of initial capital
                budget_paise = int(settings.INITIAL_CASH_PER_AGENT_PAISE * 0.10)
                entry_high_paise = rupees_to_paise(entry_high)
                shares = int(budget_paise // entry_high_paise) if entry_high_paise > 0 else 0

                if shares >= 1 and 0 < stop_loss < entry_low <= entry_high < target:
                    current_open_count += 1
                    decisions.append({
                        "ticker": ticker, "action": "BUY", "shares": shares, "entry_low": entry_low,
                        "entry_high": entry_high, "stop_loss_price": stop_loss, "target_price": target,
                        "reasoning": "Rules baseline BUY: EMA alignment, RSI 55-70, volume surge >= 1.2, MACD hist > 0",
                        "cited_metrics": {"rsi_14": rsi_14, "volume_surge": volume_surge, "macd_hist": macd_hist},
                        "snapshot_id": snapshot_id,
                    })
                else:
                    decisions.append({
                        "ticker": ticker, "action": "HOLD", "shares": None, "entry_low": None,
                        "entry_high": None, "stop_loss_price": None, "target_price": None,
                        "reasoning": "Rules entry passed but sizing or price check failed", "cited_metrics": None,
                        "snapshot_id": snapshot_id,
                    })
            else:
                decisions.append({
                    "ticker": ticker, "action": "HOLD", "shares": None, "entry_low": None,
                    "entry_high": None, "stop_loss_price": None, "target_price": None,
                    "reasoning": "Rules entry criteria not met", "cited_metrics": None,
                    "snapshot_id": snapshot_id,
                })

    return decisions


def run_baseline_simons(
    run_date: str,
    clock: Clock,
    portfolio_conn: sqlite3.Connection,
    dry_run: bool = False,
    force: bool = False,
    no_orders: bool = False,
) -> dict:
    """Executes the rules baseline agent on Simons' candidates for run_date."""
    # Upstream check: watchlist for run_date must be SUCCESS
    if not dry_run:
        w_status = portfolio_conn.execute(
            "SELECT status FROM pipeline_runs WHERE job = 'watchlist' AND run_date = ?", (run_date,)
        ).fetchone()
        status = w_status["status"] if w_status else None
        if status != "SUCCESS":
            return {"status": "FAILED", "detail": f"watchlist job for {run_date} is {status!r}, expected SUCCESS"}

        decisions_exist = portfolio_conn.execute(
            "SELECT 1 FROM decisions WHERE agent_id = ? AND run_date = ? LIMIT 1", (AGENT_ID, run_date)
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
                (AGENT_ID, run_date),
            ).fetchone()
            if has_filled:
                return {"status": "REFUSED", "detail": "cannot --force: order already filled"}

            Broker(portfolio_conn, clock).cancel_pending_for_run(AGENT_ID, run_date)
            _delete_baseline_decisions(portfolio_conn, run_date)

    decisions = evaluate_baseline_candidates(portfolio_conn, run_date, clock)

    if not dry_run:
        now = clock.now_iso()
        for d in decisions:
            action = d["action"]
            shares = d["shares"]
            entry_low_p = rupees_to_paise(d["entry_low"]) if d["entry_low"] else None
            entry_high_p = rupees_to_paise(d["entry_high"]) if d["entry_high"] else None
            stop_p = rupees_to_paise(d["stop_loss_price"]) if d["stop_loss_price"] else None
            target_p = rupees_to_paise(d["target_price"]) if d["target_price"] else None
            cited_json = json.dumps(d["cited_metrics"]) if d["cited_metrics"] else None

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
                    run_date, AGENT_ID, d["ticker"], action, shares, entry_low_p, entry_high_p,
                    stop_p, target_p, d["reasoning"], cited_json, d["snapshot_id"], now,
                ),
            )

        order_summary = {}
        if not no_orders:
            broker = Broker(portfolio_conn, clock)
            order_summary = broker.place_orders_for_run(AGENT_ID, run_date)

        return {"status": "SUCCESS", "decisions": len(decisions), "order_summary": order_summary}

    return {"status": "SUCCESS", "decisions": len(decisions), "dry_run": True}


def main() -> None:
    parser = argparse.ArgumentParser(description="Baseline Simons Rules runner.")
    parser.add_argument("--date", dest="date_str", default=None, help="YYYY-MM-DD, default: today (IST)")
    parser.add_argument("--force", action="store_true", help="Regenerate decisions for this date")
    parser.add_argument("--dry-run", action="store_true", help="Evaluate rules without writing")
    parser.add_argument("--no-orders", action="store_true", help="Generate decisions but place no orders")
    args = parser.parse_args()

    clock = SystemClock()
    conn = get_connection(settings.PORTFOLIO_DB_PATH)
    try:
        run_date = args.date_str or clock.today().isoformat()
        res = run_baseline_simons(run_date, clock, conn, dry_run=args.dry_run, force=args.force, no_orders=args.no_orders)
        print(f"baseline-simons: {res}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
