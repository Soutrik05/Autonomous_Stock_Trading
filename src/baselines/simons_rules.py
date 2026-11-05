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
from watchlist.watchlist_refresh import get_review_pool
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
    """Generates rules-based decisions for baseline-simons-rules:
    1. Evaluates all currently held positions for exit triggers (target, breakdown, KER collapse, time decay).
    2. Filters unheld candidates against quantitative momentum hurdles (trend, ADX, KER, RSI, volume, skew).
    3. Ranks passing candidates by Percentile Rank Composite intensity_score.
    4. Allocates capital strictly by conviction rank with a 5% cash liquidity reserve floor.
    """
    from agents.personas import get_persona
    simons_cfg = get_persona("simons")
    max_candidates = getattr(simons_cfg, "max_candidates", 20)
    max_positions = getattr(simons_cfg, "max_open_positions", 12)
    atr_mult = getattr(simons_cfg, "atr_stop_multiplier", 1.5)
    target_risk_pct = getattr(simons_cfg, "target_risk_pct", 0.75)
    max_pos_pct = getattr(simons_cfg, "max_position_pct", 10.0)

    # 1. Open positions held specifically by the baseline agent
    open_positions = portfolio_conn.execute(
        "SELECT * FROM positions WHERE agent_id = ? AND status = 'OPEN'", (AGENT_ID,)
    ).fetchall()
    held_by_ticker = {p["ticker"]: p for p in open_positions}
    current_open_count = len(open_positions)
    held_tickers = set(held_by_ticker.keys())

    # 2. Watchlist candidates from Jimmy's Stage-3 funnel
    watchlist_rows = portfolio_conn.execute(
        "SELECT ticker, intensity_score FROM agent_watchlist WHERE agent_id = 'simons' ORDER BY intensity_score DESC"
    ).fetchall()
    watchlist_intensity = {r["ticker"]: float(r["intensity_score"] or 0.0) for r in watchlist_rows}
    watchlist_not_held = [r["ticker"] for r in watchlist_rows if r["ticker"] not in held_tickers]

    # Assembled review pool: baseline open positions + Jimmy's top unheld watchlist candidates
    remaining_slots = max(max_candidates - len(held_tickers), 0)
    review_tickers = list(held_tickers) + watchlist_not_held[:remaining_slots]
    if not review_tickers:
        return []

    placeholders = ",".join("?" * len(review_tickers))
    rows = portfolio_conn.execute(
        f"SELECT id, ticker, features_json FROM feature_snapshots "
        f"WHERE as_of_date = ? AND ticker IN ({placeholders})",
        (run_date, *review_tickers),
    ).fetchall()
    features_by_ticker = {r["ticker"]: (r["id"], json.loads(r["features_json"])) for r in rows}

    broker = Broker(portfolio_conn, clock)
    account_val_paise = broker._account_value_paise(AGENT_ID)
    if account_val_paise <= 0:
        account_val_paise = settings.INITIAL_CASH_PER_AGENT_PAISE
    account_value_rupees = account_val_paise / 100.0

    avail_cash_paise = broker.available_cash_paise(AGENT_ID)
    min_cash_reserve_paise = int(account_val_paise * 0.05)  # 5% cash liquidity reserve floor
    spendable_cash_paise = max(0, avail_cash_paise - min_cash_reserve_paise)
    available_position_slots = max(0, max_positions - current_open_count)

    decisions = []

    # 3. Process HELD candidates first
    for ticker in held_tickers:
        snapshot_id, feats = features_by_ticker.get(ticker, (None, {}))
        close = feats.get("close")
        ema_20 = feats.get("ema_20")
        adx_14 = feats.get("adx_14")
        kaufman_er = feats.get("kaufman_er_20")
        atr_14 = feats.get("atr_14")
        pos = held_by_ticker[ticker]

        target_reached = (close is not None and pos["target_paise"] is not None and close * 100 >= pos["target_paise"])
        trend_broken = (ema_20 is not None and close is not None and close < ema_20)
        efficiency_collapsed = (kaufman_er is not None and kaufman_er < 0.20) or (adx_14 is not None and adx_14 < 18.0)

        # Time decay test (held >= 8 trading sessions without achieving >= 1.0x ATR profit)
        time_decay = False
        if pos["entry_date"] and atr_14 and atr_14 > 0 and close:
            try:
                hold_days = (date.fromisoformat(run_date) - date.fromisoformat(pos["entry_date"])).days
                entry_rupees = pos["avg_entry_price_paise"] / 100.0
                profit = close - entry_rupees
                if hold_days >= 8 and profit < 1.0 * atr_14:
                    time_decay = True
            except Exception:
                pass

        if target_reached:
            decisions.append({
                "ticker": ticker, "action": "SELL", "shares": None, "entry_low": None,
                "entry_high": None, "stop_loss_price": None, "target_price": None,
                "reasoning": "Rule exit: target reached (>= 3.0x ATR)", "cited_metrics": None,
                "snapshot_id": snapshot_id,
            })
        elif trend_broken:
            decisions.append({
                "ticker": ticker, "action": "SELL", "shares": None, "entry_low": None,
                "entry_high": None, "stop_loss_price": None, "target_price": None,
                "reasoning": "Rule exit: trend breakdown (close < ema_20)", "cited_metrics": None,
                "snapshot_id": snapshot_id,
            })
        elif efficiency_collapsed:
            decisions.append({
                "ticker": ticker, "action": "SELL", "shares": None, "entry_low": None,
                "entry_high": None, "stop_loss_price": None, "target_price": None,
                "reasoning": "Rule exit: trend efficiency collapsed (KER < 0.20 or ADX < 18)", "cited_metrics": None,
                "snapshot_id": snapshot_id,
            })
        elif time_decay:
            decisions.append({
                "ticker": ticker, "action": "SELL", "shares": None, "entry_low": None,
                "entry_high": None, "stop_loss_price": None, "target_price": None,
                "reasoning": "Rule exit: time decay (held >= 8 sessions without 1.0x ATR profit)", "cited_metrics": None,
                "snapshot_id": snapshot_id,
            })
        else:
            decisions.append({
                "ticker": ticker, "action": "HOLD", "shares": None, "entry_low": None,
                "entry_high": None, "stop_loss_price": None, "target_price": None,
                "reasoning": "Rules hold: above 20 EMA, momentum and trend efficiency intact", "cited_metrics": None,
                "snapshot_id": snapshot_id,
            })

    # 4. Evaluate and filter UNHELD candidates
    qualifying_unheld = []
    unheld_tickers = [t for t in review_tickers if t not in held_tickers]

    for ticker in unheld_tickers:
        snapshot_id, feats = features_by_ticker.get(ticker, (None, {}))
        close = feats.get("close")
        ema_20 = feats.get("ema_20")
        ema_200 = feats.get("ema_200")
        rsi_14 = feats.get("rsi_14")
        macd_hist = feats.get("macd_hist")
        volume_surge = feats.get("volume_surge")
        adx_14 = feats.get("adx_14")
        kaufman_er = feats.get("kaufman_er_20")
        skew = feats.get("skew_60")
        atr_14 = feats.get("atr_14")
        ema_20_above_50 = feats.get("ema_20_above_50")
        intensity = watchlist_intensity.get(ticker, 0.0)

        # 6 Quantitative Entry Filters
        passes_filters = (
            ema_20_above_50 is True
            and close is not None and ema_20 is not None and close > ema_20
            and (ema_200 is None or close > ema_200)
            and rsi_14 is not None and 52.0 <= rsi_14 <= 72.0
            and volume_surge is not None and volume_surge >= 1.2
            and macd_hist is not None and macd_hist > 0.0
            and (adx_14 is None or adx_14 >= 22.0)
            and (kaufman_er is None or kaufman_er >= 0.30)
            and (skew is None or skew >= -0.5)
            and atr_14 is not None and atr_14 > 0
            and close > 0
        )

        if passes_filters:
            qualifying_unheld.append({
                "ticker": ticker, "snapshot_id": snapshot_id, "feats": feats,
                "intensity": intensity, "close": close, "atr_14": atr_14,
                "rsi_14": rsi_14, "volume_surge": volume_surge, "macd_hist": macd_hist,
                "adx_14": adx_14, "kaufman_er": kaufman_er,
            })
        else:
            decisions.append({
                "ticker": ticker, "action": "HOLD", "shares": None, "entry_low": None,
                "entry_high": None, "stop_loss_price": None, "target_price": None,
                "reasoning": "Rules entry criteria not met (trend/momentum/efficiency filter failed)",
                "cited_metrics": None, "snapshot_id": snapshot_id,
            })

    # 5. Conviction Ranking: Sort qualifying candidates by intensity_score DESC
    qualifying_unheld.sort(key=lambda x: x["intensity"], reverse=True)

    # 6. Capital Allocation down the ranked list
    for cand in qualifying_unheld:
        ticker = cand["ticker"]
        snapshot_id = cand["snapshot_id"]
        intensity = cand["intensity"]
        close = cand["close"]
        atr_14 = cand["atr_14"]

        # Minimum Conviction Floor check
        if intensity > 0 and intensity < 0.55:
            decisions.append({
                "ticker": ticker, "action": "HOLD", "shares": None, "entry_low": None,
                "entry_high": None, "stop_loss_price": None, "target_price": None,
                "reasoning": f"Passed filters but rejected: intensity {intensity:.2f} below conviction floor (0.55)",
                "cited_metrics": None, "snapshot_id": snapshot_id,
            })
            continue

        if available_position_slots <= 0:
            decisions.append({
                "ticker": ticker, "action": "HOLD", "shares": None, "entry_low": None,
                "entry_high": None, "stop_loss_price": None, "target_price": None,
                "reasoning": f"Passed filters (intensity {intensity:.2f}) but rejected: max position capacity reached (12/12)",
                "cited_metrics": None, "snapshot_id": snapshot_id,
            })
            continue

        # Volatility Parity Sizing
        entry_low = round(close - 0.25 * atr_14, 2)
        entry_high = round(close + 0.25 * atr_14, 2)
        stop_loss = round(close - atr_mult * atr_14, 2)
        if stop_loss <= 0:
            stop_loss = round(entry_low * 0.90, 2)
        target = round(close + 3.0 * atr_14, 2)

        stop_distance = max(0.01, entry_high - stop_loss)
        risk_rupees = account_value_rupees * (target_risk_pct / 100.0)
        shares_by_risk = int(risk_rupees // stop_distance)

        max_position_rupees = account_value_rupees * (max_pos_pct / 100.0)
        shares_by_cap = int(max_position_rupees // entry_high)

        shares = max(1, min(shares_by_risk, shares_by_cap))
        order_cost_paise = broker.worst_case_buy_outlay_paise(shares, rupees_to_paise(entry_high))

        if spendable_cash_paise >= order_cost_paise and 0 < stop_loss < entry_low <= entry_high < target:
            available_position_slots -= 1
            spendable_cash_paise -= order_cost_paise
            cited = {"rsi_14": cand["rsi_14"], "volume_surge": cand["volume_surge"], "macd_hist": cand["macd_hist"]}
            if cand["adx_14"] is not None:
                cited["adx_14"] = cand["adx_14"]
            if cand["kaufman_er"] is not None:
                cited["kaufman_er_20"] = cand["kaufman_er"]

            decisions.append({
                "ticker": ticker, "action": "BUY", "shares": shares, "entry_low": entry_low,
                "entry_high": entry_high, "stop_loss_price": stop_loss, "target_price": target,
                "reasoning": f"Rules baseline BUY (intensity {intensity:.2f}): EMA alignment, RSI, volume surge, ADX/KER confirmed",
                "cited_metrics": cited, "snapshot_id": snapshot_id,
            })
        else:
            decisions.append({
                "ticker": ticker, "action": "HOLD", "shares": None, "entry_low": None,
                "entry_high": None, "stop_loss_price": None, "target_price": None,
                "reasoning": f"Passed filters (intensity {intensity:.2f}) but rejected: spendable cash exhausted by higher-conviction candidates",
                "cited_metrics": None, "snapshot_id": snapshot_id,
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

