"""
Baseline rules-based agent for Zerodha Varsity (baseline-varsity-rules).
Pure Python deterministic entry/exit rules executing textbook Zerodha Varsity principles
(Karthik Rangappa, Modules 2, 3, and 9) without LLM calls.
Evaluates the exact candidate review pool that LLM Varsity saw.
"""

import argparse
import json
import logging
import sqlite3
from datetime import date

from broker.engine import Broker
from core.clock import Clock, SystemClock
from core.config import settings
from core.database import get_connection
from core.money import rupees_to_paise

logger = logging.getLogger(__name__)
AGENT_ID = "baseline-varsity-rules"
JOB_NAME = "baseline-varsity-rules"


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
) -> list[dict]:
    """
    Generates rules-based decisions for baseline-varsity-rules:
    1. Evaluates all currently held positions for exit/ratchet triggers:
       - Target hit (minimum 1:1.5 RRR reached).
       - Stop loss hit (2.0x ATR-14 below entry / swing low).
       - Breakeven ratchet (trailing stop moved to entry once +1.0x risk distance is achieved).
       - Technical breakdown (close < 200 EMA or 20 EMA crossed below 50 EMA or RSI < 40).
       - Time cycle exit (held >= 75 trading sessions).
    2. Filters unheld candidates against textbook Zerodha Varsity dual confluence:
       - Technical: 20 EMA > 50 EMA, Close > 200 EMA, RSI in [45, 68], Volume Surge >= 1.0.
       - Fundamental: ROCE >= 12.0%, ROE >= 12.0%, Debt/Equity <= 1.5.
       - Valuation: DCF discount >= -15.0% (fair value band or undervalued; neutral for financials).
    3. Ranks passing candidates by Balanced 50/50 Confluence intensity_score.
    4. Sizing: 1.0% account risk budget, 10% maximum equity allocation, up to 10 diversified positions.
    """
    from agents.personas import get_persona

    varsity_cfg = get_persona("varsity")
    max_candidates = getattr(varsity_cfg, "max_candidates", 10)
    max_positions = getattr(varsity_cfg, "max_open_positions", 10)
    atr_mult = getattr(varsity_cfg, "atr_stop_multiplier", 2.0)
    target_risk_pct = getattr(varsity_cfg, "target_risk_pct", 1.0)
    max_pos_pct = getattr(varsity_cfg, "max_position_pct", 10.0)
    sector_cap = getattr(varsity_cfg, "sector_cap", 2)

    # 1. Open positions held specifically by the baseline agent
    open_positions = portfolio_conn.execute(
        "SELECT * FROM positions WHERE agent_id = ? AND status = 'OPEN'", (AGENT_ID,)
    ).fetchall()
    held_by_ticker = {p["ticker"]: p for p in open_positions}
    current_open_count = len(open_positions)
    held_tickers = set(held_by_ticker.keys())

    # Count sector exposures
    sectors_map = dict(portfolio_conn.execute("SELECT ticker, sector FROM symbols").fetchall())
    open_sector_counts = {}
    for p in open_positions:
        sec = sectors_map.get(p["ticker"], "UNKNOWN")
        open_sector_counts[sec] = open_sector_counts.get(sec, 0) + 1

    # 2. Watchlist candidates from Varsity's Stage-3 funnel
    watchlist_rows = portfolio_conn.execute(
        "SELECT ticker, intensity_score FROM agent_watchlist WHERE agent_id = 'varsity' ORDER BY intensity_score DESC"
    ).fetchall()
    watchlist_intensity = {r["ticker"]: float(r["intensity_score"] or 0.0) for r in watchlist_rows}
    watchlist_not_held = [r["ticker"] for r in watchlist_rows if r["ticker"] not in held_tickers]

    # Assembled review pool: baseline open positions + Varsity's top unheld watchlist candidates
    remaining_slots = max(max_candidates - len(held_tickers), 0)
    review_tickers = list(held_tickers) + watchlist_not_held[:remaining_slots]
    if not review_tickers:
        return []

    placeholders = ",".join("?" * len(review_tickers))
    rows = portfolio_conn.execute(
        f"SELECT id, ticker, features_json FROM feature_snapshots WHERE as_of_date = ? AND ticker IN ({placeholders})",
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
        feats.get("ema_20")
        feats.get("ema_50")
        ema_200 = feats.get("ema_200")
        ema_20_above_50 = feats.get("ema_20_above_50")
        rsi_14 = feats.get("rsi_14")
        atr_14 = feats.get("atr_14")
        pos = held_by_ticker[ticker]

        target_event_today = False
        try:
            ev = portfolio_conn.execute(
                "SELECT 1 FROM activity_log WHERE agent_id IN (?, 'varsity') AND ticker = ? AND event_type = 'TARGET_REACHED' AND created_at LIKE ? LIMIT 1",
                (AGENT_ID, ticker, f"{run_date}%"),
            ).fetchone()
            target_event_today = ev is not None
        except Exception:
            pass

        target_reached = target_event_today or (
            close is not None and pos["target_paise"] is not None and close * 100 >= pos["target_paise"]
        )
        stop_hit = close is not None and pos["stop_paise"] is not None and close * 100 <= pos["stop_paise"]

        # Technical breakdown: closing below 200 EMA (Mothership) or 20 EMA crossing below 50 EMA or RSI dropping below 40
        below_ema_200 = close is not None and ema_200 is not None and close < ema_200
        ma_bear_cross = ema_20_above_50 is False
        rsi_exhausted = rsi_14 is not None and rsi_14 < 40.0
        technical_breakdown = below_ema_200 or ma_bear_cross or rsi_exhausted

        # Intermediate time cycle exit (held >= 75 trading sessions)
        time_exit = False
        if pos["entry_date"]:
            try:
                hold_days = (date.fromisoformat(run_date) - date.fromisoformat(pos["entry_date"])).days
                if hold_days >= 75:
                    time_exit = True
            except Exception:
                pass

        if target_reached:
            entry_rupees = (pos["avg_entry_price_paise"] or 0) / 100.0
            tgt_rupees = (pos["target_paise"] or 0) / 100.0
            cur_stop_rupees = (pos["stop_paise"] or 0) / 100.0
            cur_price = close or tgt_rupees
            ratchet_stop = max(cur_stop_rupees, entry_rupees + max(0.0, tgt_rupees - entry_rupees) * 0.5)
            if ratchet_stop >= cur_price:
                ratchet_stop = cur_price * 0.98
            new_target = max(tgt_rupees * 1.25, cur_price * 1.10)
            decisions.append(
                {
                    "ticker": ticker,
                    "action": "ADJUST",
                    "shares": None,
                    "entry_low": None,
                    "entry_high": None,
                    "stop_loss_price": round(ratchet_stop, 2),
                    "target_price": round(new_target, 2),
                    "reasoning": f"Varsity rule adjust on TARGET_REACHED: ratcheted stop to Rs{ratchet_stop:.2f} (locked 50% gain) and trailed target to Rs{new_target:.2f}.",
                    "cited_metrics": None,
                    "snapshot_id": snapshot_id,
                }
            )
        elif stop_hit:
            decisions.append(
                {
                    "ticker": ticker,
                    "action": "SELL",
                    "shares": None,
                    "entry_low": None,
                    "entry_high": None,
                    "stop_loss_price": None,
                    "target_price": None,
                    "reasoning": "Varsity rule exit: volatility stop hit (2.0x ATR risk line)",
                    "cited_metrics": None,
                    "snapshot_id": snapshot_id,
                }
            )
        elif technical_breakdown:
            decisions.append(
                {
                    "ticker": ticker,
                    "action": "SELL",
                    "shares": None,
                    "entry_low": None,
                    "entry_high": None,
                    "stop_loss_price": None,
                    "target_price": None,
                    "reasoning": f"Varsity rule exit: technical trend breakdown (close < 200 EMA={below_ema_200}, 20<50 EMA={ma_bear_cross}, RSI<40={rsi_exhausted})",
                    "cited_metrics": None,
                    "snapshot_id": snapshot_id,
                }
            )
        elif time_exit:
            decisions.append(
                {
                    "ticker": ticker,
                    "action": "SELL",
                    "shares": None,
                    "entry_low": None,
                    "entry_high": None,
                    "stop_loss_price": None,
                    "target_price": None,
                    "reasoning": "Varsity rule exit: intermediate 75-day holding cycle completed",
                    "cited_metrics": None,
                    "snapshot_id": snapshot_id,
                }
            )
        else:
            # Trailing stop breakeven ratchet check (Module 9 Ch 7)
            entry_p = pos["avg_entry_price_paise"] / 100.0 if pos["avg_entry_price_paise"] else None
            stop_p = pos["stop_paise"] / 100.0 if pos["stop_paise"] else None
            if entry_p and stop_p and close and atr_14 and stop_p < entry_p:
                profit = close - entry_p
                # If unrealized profit >= 2.0x ATR (1.0x risk distance), ratchet stop to breakeven
                if profit >= 2.0 * atr_14:
                    decisions.append(
                        {
                            "ticker": ticker,
                            "action": "ADJUST",
                            "shares": None,
                            "entry_low": None,
                            "entry_high": None,
                            "stop_loss_price": round(entry_p, 2),
                            "target_price": None,
                            "reasoning": "Varsity trailing stop: ratcheted stop to breakeven after +1.0x risk profit expansion",
                            "cited_metrics": {"atr_14": atr_14},
                            "snapshot_id": snapshot_id,
                        }
                    )
                    continue

            decisions.append(
                {
                    "ticker": ticker,
                    "action": "HOLD",
                    "shares": None,
                    "entry_low": None,
                    "entry_high": None,
                    "stop_loss_price": None,
                    "target_price": None,
                    "reasoning": "Varsity rule hold: trend structure, momentum sweet spot, and solvency thesis intact",
                    "cited_metrics": None,
                    "snapshot_id": snapshot_id,
                }
            )

    # 4. Evaluate and filter UNHELD candidates
    qualifying_unheld = []
    unheld_tickers = [t for t in review_tickers if t not in held_tickers]

    for ticker in unheld_tickers:
        snapshot_id, feats = features_by_ticker.get(ticker, (None, {}))
        close = feats.get("close")
        feats.get("ema_20")
        feats.get("ema_50")
        ema_200 = feats.get("ema_200")
        ema_20_above_50 = feats.get("ema_20_above_50")
        rsi_14 = feats.get("rsi_14")
        volume_surge = feats.get("volume_surge")
        atr_14 = feats.get("atr_14")
        roce_pct = feats.get("roce_pct")
        roe_pct = feats.get("roe_pct")
        debt_to_equity = feats.get("debt_to_equity")
        dcf_discount_pct = feats.get("dcf_discount_pct")
        news_sentiment = feats.get("news_sentiment")
        intensity = watchlist_intensity.get(ticker, 0.0)

        # Negative news veto (regulatory probes, governance scandals)
        if news_sentiment is not None and news_sentiment < -0.25:
            decisions.append(
                {
                    "ticker": ticker,
                    "action": "HOLD",
                    "shares": None,
                    "entry_low": None,
                    "entry_high": None,
                    "stop_loss_price": None,
                    "target_price": None,
                    "reasoning": "Varsity rule veto: severe negative news sentiment (governance/regulatory risk)",
                    "cited_metrics": {"news_sentiment": news_sentiment},
                    "snapshot_id": snapshot_id,
                }
            )
            continue

        # Technical Confluence (Module 2):
        # 1. 20 EMA > 50 EMA
        # 2. Close > 200 EMA (The Mothership)
        # 3. RSI in [45, 68] (Momentum sweet spot, avoiding overbought FOMO)
        # 4. Volume surge >= 1.0 (Breakout confirmation)
        passes_technical = (
            close is not None
            and close > 0
            and atr_14 is not None
            and atr_14 > 0
            and ema_20_above_50 is True
            and (ema_200 is None or close > ema_200)
            and rsi_14 is not None
            and 45.0 <= rsi_14 <= 68.0
            and volume_surge is not None
            and volume_surge >= 1.0
        )

        # Fundamental Confluence (Module 3):
        # 1. ROCE >= 12.0%
        # 2. ROE >= 12.0%
        # 3. Debt/Equity <= 1.5
        # 4. DCF discount >= -15.0% (within fair value band or undervalued; banks/financials exempt if None)
        passes_fundamental = (
            roce_pct is not None
            and roce_pct >= 12.0
            and roe_pct is not None
            and roe_pct >= 12.0
            and debt_to_equity is not None
            and debt_to_equity <= 1.5
            and (dcf_discount_pct is None or dcf_discount_pct >= -15.0)
        )

        if passes_technical and passes_fundamental:
            qualifying_unheld.append(
                {
                    "ticker": ticker,
                    "snapshot_id": snapshot_id,
                    "feats": feats,
                    "intensity": intensity,
                    "close": close,
                    "atr_14": atr_14,
                    "rsi_14": rsi_14,
                    "volume_surge": volume_surge,
                    "roce_pct": roce_pct,
                    "roe_pct": roe_pct,
                    "debt_to_equity": debt_to_equity,
                    "dcf_discount_pct": dcf_discount_pct,
                }
            )
        else:
            reasons = []
            if not passes_technical:
                reasons.append("technical confluence failed (need 20>50 EMA, close>200 EMA, RSI 45-68, vol>=1.0)")
            if not passes_fundamental:
                reasons.append("fundamental quality failed (need ROCE>=12%, ROE>=12%, D/E<=1.5, DCF>=-15%)")
            decisions.append(
                {
                    "ticker": ticker,
                    "action": "HOLD",
                    "shares": None,
                    "entry_low": None,
                    "entry_high": None,
                    "stop_loss_price": None,
                    "target_price": None,
                    "reasoning": f"Varsity dual confluence not met: {'; '.join(reasons)}",
                    "cited_metrics": None,
                    "snapshot_id": snapshot_id,
                }
            )

    # 5. Conviction Ranking: Sort qualifying candidates by intensity_score DESC
    qualifying_unheld.sort(key=lambda x: x["intensity"], reverse=True)

    # 6. Capital Allocation down the ranked list
    for cand in qualifying_unheld:
        ticker = cand["ticker"]
        snapshot_id = cand["snapshot_id"]
        intensity = cand["intensity"]
        close = cand["close"]
        atr_14 = cand["atr_14"]
        sector = sectors_map.get(ticker, "UNKNOWN")

        # Minimum Conviction Floor check
        if intensity > 0 and intensity < 0.50:
            decisions.append(
                {
                    "ticker": ticker,
                    "action": "HOLD",
                    "shares": None,
                    "entry_low": None,
                    "entry_high": None,
                    "stop_loss_price": None,
                    "target_price": None,
                    "reasoning": f"Passed confluence but rejected: intensity {intensity:.2f} below conviction floor (0.50)",
                    "cited_metrics": None,
                    "snapshot_id": snapshot_id,
                }
            )
            continue

        if available_position_slots <= 0:
            decisions.append(
                {
                    "ticker": ticker,
                    "action": "HOLD",
                    "shares": None,
                    "entry_low": None,
                    "entry_high": None,
                    "stop_loss_price": None,
                    "target_price": None,
                    "reasoning": f"Passed confluence (intensity {intensity:.2f}) but rejected: max position capacity reached ({max_positions}/{max_positions})",
                    "cited_metrics": None,
                    "snapshot_id": snapshot_id,
                }
            )
            continue

        # Sector Cap Check
        if open_sector_counts.get(sector, 0) >= sector_cap:
            decisions.append(
                {
                    "ticker": ticker,
                    "action": "HOLD",
                    "shares": None,
                    "entry_low": None,
                    "entry_high": None,
                    "stop_loss_price": None,
                    "target_price": None,
                    "reasoning": f"Passed confluence but rejected: sector {sector} reached cap ({sector_cap} stocks)",
                    "cited_metrics": None,
                    "snapshot_id": snapshot_id,
                }
            )
            continue

        # Price Brackets & Volatility Stop (2.0x ATR-14)
        entry_low = round(close - 0.25 * atr_14, 2)
        entry_high = round(close + 0.25 * atr_14, 2)
        stop_loss = round(close - atr_mult * atr_14, 2)
        if stop_loss <= 0:
            stop_loss = round(entry_low * 0.90, 2)

        risk_distance = max(0.01, entry_high - stop_loss)

        # Enforce Minimum 1:1.5 Risk-to-Reward Ratio (Varsity Module 9)
        # Target provides at least 1.75x risk distance (aiming well above the 1:1.5 floor)
        target = round(close + max(1.75 * risk_distance, 3.5 * atr_14), 2)

        # Position Sizing: 1.0% Capital Risk Budget (The 2% Rule)
        risk_rupees = account_value_rupees * (target_risk_pct / 100.0)
        shares_by_risk = int(risk_rupees // risk_distance)

        # 10% Capital Cap
        max_position_rupees = account_value_rupees * (max_pos_pct / 100.0)
        shares_by_cap = int(max_position_rupees // entry_high)

        shares = max(1, min(shares_by_risk, shares_by_cap))
        order_cost_paise = broker.worst_case_buy_outlay_paise(shares, rupees_to_paise(entry_high))

        if spendable_cash_paise >= order_cost_paise and 0 < stop_loss < entry_low <= entry_high < target:
            available_position_slots -= 1
            spendable_cash_paise -= order_cost_paise
            open_sector_counts[sector] = open_sector_counts.get(sector, 0) + 1

            cited = {
                "rsi_14": cand["rsi_14"],
                "volume_surge": cand["volume_surge"],
                "roce_pct": cand["roce_pct"],
                "debt_to_equity": cand["debt_to_equity"],
            }
            if cand.get("dcf_discount_pct") is not None:
                cited["dcf_discount_pct"] = cand["dcf_discount_pct"]

            decisions.append(
                {
                    "ticker": ticker,
                    "action": "BUY",
                    "shares": shares,
                    "entry_low": entry_low,
                    "entry_high": entry_high,
                    "stop_loss_price": stop_loss,
                    "target_price": target,
                    "reasoning": (
                        f"Varsity baseline BUY (intensity {intensity:.2f}): "
                        f"20>50 EMA & 200 EMA trend, RSI 45-68 sweet spot, ROCE {cand['roce_pct']}%, D/E {cand['debt_to_equity']}, "
                        f"1:1.75 RRR with 2.0x ATR stop"
                    ),
                    "cited_metrics": cited,
                    "snapshot_id": snapshot_id,
                }
            )
        else:
            decisions.append(
                {
                    "ticker": ticker,
                    "action": "HOLD",
                    "shares": None,
                    "entry_low": None,
                    "entry_high": None,
                    "stop_loss_price": None,
                    "target_price": None,
                    "reasoning": f"Passed confluence (intensity {intensity:.2f}) but rejected: spendable cash exhausted by higher-conviction candidates",
                    "cited_metrics": None,
                    "snapshot_id": snapshot_id,
                }
            )

    return decisions


def run_baseline_varsity(
    run_date: str,
    clock: Clock,
    portfolio_conn: sqlite3.Connection,
    dry_run: bool = False,
    force: bool = False,
    no_orders: bool = False,
) -> dict:
    """Executes the rules baseline agent on Varsity's candidates for run_date."""
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
                    run_date,
                    AGENT_ID,
                    d["ticker"],
                    action,
                    shares,
                    entry_low_p,
                    entry_high_p,
                    stop_p,
                    target_p,
                    d["reasoning"],
                    cited_json,
                    d["snapshot_id"],
                    now,
                ),
            )

        order_summary = {}
        if not no_orders:
            broker = Broker(portfolio_conn, clock)
            order_summary = broker.place_orders_for_run(AGENT_ID, run_date)

        return {"status": "SUCCESS", "decisions": len(decisions), "order_summary": order_summary}

    return {"status": "SUCCESS", "decisions": len(decisions), "dry_run": True}


def main() -> None:
    parser = argparse.ArgumentParser(description="Baseline Varsity Rules runner.")
    parser.add_argument("--date", dest="date_str", default=None, help="YYYY-MM-DD, default: today (IST)")
    parser.add_argument("--force", action="store_true", help="Regenerate decisions for this date")
    parser.add_argument("--dry-run", action="store_true", help="Evaluate rules without writing")
    parser.add_argument("--no-orders", action="store_true", help="Generate decisions but place no orders")
    args = parser.parse_args()

    clock = SystemClock()
    conn = get_connection(settings.PORTFOLIO_DB_PATH)
    try:
        run_date = args.date_str or clock.today().isoformat()
        res = run_baseline_varsity(
            run_date, clock, conn, dry_run=args.dry_run, force=args.force, no_orders=args.no_orders
        )
        print(f"baseline-varsity: {res}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
