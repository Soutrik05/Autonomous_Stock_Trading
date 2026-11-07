"""
Baseline rules-based agent for Howard Marks (baseline-marks-rules).
Pure Python deterministic entry/exit rules executing textbook Howard Marks contrarian value principles
(The Most Important Thing, Ch. 1, 3, 5, 8, 9, 11, 16; Mastering the Market Cycle, Ch. 8-10) without LLM calls.
Evaluates the exact candidate review pool that LLM Marks saw.
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
AGENT_ID = "baseline-marks-rules"
JOB_NAME = "baseline-marks-rules"


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
    Generates rules-based decisions for baseline-marks-rules:
    1. Evaluates all currently held positions for exit/ratchet triggers:
       - Target hit: >= 1:2.0 RRR reached.
       - Mean reversion completed: RSI-14 >= 65.0 with profit.
       - Stop loss hit: 2.5x ATR-14 volatility breathing room line.
       - Breakeven ratchet: trailing stop moved to entry once +1.0x risk distance is achieved.
       - Story deterioration: CFO/PAT < 0.40 or D/E > 1.20.
       - Time cycle exit: held >= 120 trading sessions.
    2. Filters unheld candidates against textbook Howard Marks Method A contrarian criteria:
       - RSI-14 <= 45.0 (cyclically unloved / oversold).
       - dist_52w_low_pct <= 35.0% (trading in lower half of 52-week range).
       - P/E <= 30.0 (reasonable/cheap valuation multiple).
       - Debt/Equity <= 1.0 (solvency moat; survivability is mandatory).
       - CFO/PAT >= 0.60 (cash flow reality check).
       - ROCE >= 10.0% (underlying business viability).
    3. Ranks passing candidates by 5-Factor Contrarian intensity_score.
    4. Sizing: 1.25% account risk budget, 12.5% maximum equity allocation, up to 8 positions.
    """
    from agents.personas import get_persona

    marks_cfg = get_persona("marks")
    max_candidates = getattr(marks_cfg, "max_candidates", 15)
    max_positions = getattr(marks_cfg, "max_open_positions", 8)
    atr_mult = getattr(marks_cfg, "atr_stop_multiplier", 2.5)
    target_risk_pct = getattr(marks_cfg, "target_risk_pct", 1.25)
    max_pos_pct = getattr(marks_cfg, "max_position_pct", 12.5)
    sector_cap = getattr(marks_cfg, "sector_cap", 2)

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

    # 2. Watchlist candidates from Marks' Stage-3 funnel
    watchlist_rows = portfolio_conn.execute(
        "SELECT ticker, intensity_score FROM agent_watchlist WHERE agent_id = 'marks' ORDER BY intensity_score DESC"
    ).fetchall()
    watchlist_intensity = {r["ticker"]: float(r["intensity_score"] or 0.0) for r in watchlist_rows}
    watchlist_not_held = [r["ticker"] for r in watchlist_rows if r["ticker"] not in held_tickers]

    # Assembled review pool: baseline open positions + Marks' top unheld watchlist candidates
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
        rsi_14 = feats.get("rsi_14")
        cfo_to_pat = feats.get("cfo_to_pat")
        debt_to_equity = feats.get("debt_to_equity")
        atr_14 = feats.get("atr_14")
        pos = held_by_ticker[ticker]

        target_event_today = False
        try:
            ev = portfolio_conn.execute(
                "SELECT 1 FROM activity_log WHERE agent_id IN (?, 'marks') AND ticker = ? AND event_type = 'TARGET_REACHED' AND created_at LIKE ? LIMIT 1",
                (AGENT_ID, ticker, f"{run_date}%"),
            ).fetchone()
            target_event_today = ev is not None
        except Exception:
            pass

        target_reached = target_event_today or (
            close is not None and pos["target_paise"] is not None and close * 100 >= pos["target_paise"]
        )
        stop_hit = close is not None and pos["stop_paise"] is not None and close * 100 <= pos["stop_paise"]

        # Mean reversion completed: RSI recovers >= 65.0 with profit
        entry_p = pos["avg_entry_price_paise"] / 100.0 if pos["avg_entry_price_paise"] else None
        mean_reversion_complete = (
            close is not None and entry_p is not None and close > entry_p and rsi_14 is not None and rsi_14 >= 65.0
        )

        # Story deterioration: solvency collapse or severe cash bleed
        story_broken = (cfo_to_pat is not None and cfo_to_pat < 0.40) or (
            debt_to_equity is not None and debt_to_equity > 1.20
        )

        # Intermediate time cycle exit (held >= 120 trading sessions)
        time_exit = False
        if pos["entry_date"]:
            try:
                hold_days = (date.fromisoformat(run_date) - date.fromisoformat(pos["entry_date"])).days
                if hold_days >= 120:
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
                    "reasoning": f"Marks rule adjust on TARGET_REACHED: ratcheted stop to Rs{ratchet_stop:.2f} (locked 50% gain) and trailed target to Rs{new_target:.2f}.",
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
                    "reasoning": "Marks rule exit: volatility stop hit (2.5x ATR risk line)",
                    "cited_metrics": None,
                    "snapshot_id": snapshot_id,
                }
            )
        elif mean_reversion_complete:
            decisions.append(
                {
                    "ticker": ticker,
                    "action": "SELL",
                    "shares": None,
                    "entry_low": None,
                    "entry_high": None,
                    "stop_loss_price": None,
                    "target_price": None,
                    "reasoning": f"Marks rule exit: mean reversion completed (RSI={rsi_14:.1f} >= 65), taking contrarian profits",
                    "cited_metrics": {"rsi_14": rsi_14},
                    "snapshot_id": snapshot_id,
                }
            )
        elif story_broken:
            decisions.append(
                {
                    "ticker": ticker,
                    "action": "SELL",
                    "shares": None,
                    "entry_low": None,
                    "entry_high": None,
                    "stop_loss_price": None,
                    "target_price": None,
                    "reasoning": f"Marks rule exit: balance sheet / cash flow deterioration (CFO/PAT={cfo_to_pat}, D/E={debt_to_equity})",
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
                    "reasoning": "Marks rule exit: 120-day contrarian holding cycle completed",
                    "cited_metrics": None,
                    "snapshot_id": snapshot_id,
                }
            )
        else:
            # Trailing stop breakeven ratchet check
            stop_p = pos["stop_paise"] / 100.0 if pos["stop_paise"] else None
            if entry_p and stop_p and close and atr_14 and stop_p < entry_p:
                profit = close - entry_p
                # If unrealized profit >= 2.5x ATR (1.0x risk distance), ratchet stop to breakeven
                if profit >= 2.5 * atr_14:
                    decisions.append(
                        {
                            "ticker": ticker,
                            "action": "ADJUST",
                            "shares": None,
                            "entry_low": None,
                            "entry_high": None,
                            "stop_loss_price": round(entry_p, 2),
                            "target_price": None,
                            "reasoning": "Marks trailing stop: ratcheted stop to breakeven after +1.0x risk profit expansion",
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
                    "reasoning": "Marks rule hold: contrarian thesis, balance sheet survivability, and mean-reversion potential intact",
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
        atr_14 = feats.get("atr_14")
        rsi_14 = feats.get("rsi_14")
        dist_52w_low = feats.get("dist_52w_low_pct")
        pe = feats.get("pe")
        feats.get("pb")
        debt_to_equity = feats.get("debt_to_equity")
        cfo_to_pat = feats.get("cfo_to_pat")
        roce_pct = feats.get("roce_pct")
        news_sentiment = feats.get("news_sentiment")
        intensity = watchlist_intensity.get(ticker, 0.0)

        # Severe governance/fraud news veto
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
                    "reasoning": "Marks rule veto: severe negative news sentiment (governance/fraud existential risk)",
                    "cited_metrics": {"news_sentiment": news_sentiment},
                    "snapshot_id": snapshot_id,
                }
            )
            continue

        # Method A Contrarian Hurdles:
        # 1. RSI-14 <= 45.0 (cyclically unloved / oversold)
        # 2. dist_52w_low_pct <= 35.0% (lower half of 52-week range)
        # 3. P/E <= 30.0 (reasonable/cheap valuation)
        # 4. Debt/Equity <= 1.0 (solvency moat)
        # 5. CFO/PAT >= 0.60 (cash flow reality check)
        # 6. ROCE >= 10.0% (underlying business viability)
        passes_contrarian = (
            close is not None
            and close > 0
            and atr_14 is not None
            and atr_14 > 0
            and rsi_14 is not None
            and rsi_14 <= 45.0
            and dist_52w_low is not None
            and dist_52w_low <= 35.0
            and pe is not None
            and 0.0 < pe <= 30.0
            and debt_to_equity is not None
            and debt_to_equity <= 1.0
            and cfo_to_pat is not None
            and cfo_to_pat >= 0.60
            and roce_pct is not None
            and roce_pct >= 10.0
        )

        if passes_contrarian:
            qualifying_unheld.append(
                {
                    "ticker": ticker,
                    "snapshot_id": snapshot_id,
                    "feats": feats,
                    "intensity": intensity,
                    "close": close,
                    "atr_14": atr_14,
                    "rsi_14": rsi_14,
                    "dist_52w_low_pct": dist_52w_low,
                    "pe": pe,
                    "debt_to_equity": debt_to_equity,
                    "cfo_to_pat": cfo_to_pat,
                    "roce_pct": roce_pct,
                }
            )
        else:
            reasons = []
            if rsi_14 is None or rsi_14 > 45.0:
                reasons.append(f"RSI {rsi_14} > 45.0 (not oversold)")
            if dist_52w_low is None or dist_52w_low > 35.0:
                reasons.append(f"dist_52w_low {dist_52w_low}% > 35%")
            if pe is None or pe <= 0 or pe > 30.0:
                reasons.append(f"PE {pe} > 30.0 or negative")
            if debt_to_equity is None or debt_to_equity > 1.0:
                reasons.append(f"D/E {debt_to_equity} > 1.0")
            if cfo_to_pat is None or cfo_to_pat < 0.60:
                reasons.append(f"CFO/PAT {cfo_to_pat} < 0.60")
            if roce_pct is None or roce_pct < 10.0:
                reasons.append(f"ROCE {roce_pct}% < 10%")

            decisions.append(
                {
                    "ticker": ticker,
                    "action": "HOLD",
                    "shares": None,
                    "entry_low": None,
                    "entry_high": None,
                    "stop_loss_price": None,
                    "target_price": None,
                    "reasoning": f"Marks contrarian criteria not met: {'; '.join(reasons)}",
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
        if intensity > 0 and intensity < 0.45:
            decisions.append(
                {
                    "ticker": ticker,
                    "action": "HOLD",
                    "shares": None,
                    "entry_low": None,
                    "entry_high": None,
                    "stop_loss_price": None,
                    "target_price": None,
                    "reasoning": f"Passed contrarian hurdles but rejected: intensity {intensity:.2f} below conviction floor (0.45)",
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
                    "reasoning": f"Passed contrarian hurdles (intensity {intensity:.2f}) but rejected: max position capacity reached ({max_positions}/{max_positions})",
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
                    "reasoning": f"Passed contrarian hurdles but rejected: sector {sector} reached cap ({sector_cap} stocks)",
                    "cited_metrics": None,
                    "snapshot_id": snapshot_id,
                }
            )
            continue

        # Price Brackets & Volatility Stop (2.5x ATR-14)
        entry_low = round(close - 0.25 * atr_14, 2)
        entry_high = round(close + 0.25 * atr_14, 2)
        stop_loss = round(close - atr_mult * atr_14, 2)
        if stop_loss <= 0:
            stop_loss = round(entry_low * 0.85, 2)

        risk_distance = max(0.01, entry_high - stop_loss)

        # Enforce Minimum 1:2.0 Risk-to-Reward Ratio (Howard Marks Asymmetry)
        target = round(close + max(2.0 * risk_distance, 5.0 * atr_14), 2)

        # Position Sizing: 1.25% Capital Risk Budget
        risk_rupees = account_value_rupees * (target_risk_pct / 100.0)
        shares_by_risk = int(risk_rupees // risk_distance)

        # 12.5% Capital Cap (Diversified 8-position book)
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
                "dist_52w_low_pct": cand["dist_52w_low_pct"],
                "pe": cand["pe"],
                "debt_to_equity": cand["debt_to_equity"],
                "cfo_to_pat": cand["cfo_to_pat"],
                "roce_pct": cand["roce_pct"],
            }

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
                        f"Marks baseline BUY [Contrarian Dislocation] (intensity {intensity:.2f}): "
                        f"RSI {cand['rsi_14']:.1f}, 52w-low dist {cand['dist_52w_low_pct']}%, P/E {cand['pe']:.1f}, "
                        f"D/E {cand['debt_to_equity']}, CFO/PAT {cand['cfo_to_pat']:.2f}, ROCE {cand['roce_pct']}%, "
                        f"1:2.0 RRR with 2.5x ATR stop"
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
                    "reasoning": f"Passed contrarian hurdles (intensity {intensity:.2f}) but rejected: spendable cash exhausted by higher-conviction dislocations",
                    "cited_metrics": None,
                    "snapshot_id": snapshot_id,
                }
            )

    return decisions


def run_baseline_marks(
    run_date: str,
    clock: Clock,
    portfolio_conn: sqlite3.Connection,
    dry_run: bool = False,
    force: bool = False,
    no_orders: bool = False,
) -> dict:
    """Executes the rules baseline agent on Marks' candidates for run_date."""
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
    parser = argparse.ArgumentParser(description="Baseline Marks Rules runner.")
    parser.add_argument("--date", dest="date_str", default=None, help="YYYY-MM-DD, default: today (IST)")
    parser.add_argument("--force", action="store_true", help="Regenerate decisions for this date")
    parser.add_argument("--dry-run", action="store_true", help="Evaluate rules without writing")
    parser.add_argument("--no-orders", action="store_true", help="Generate decisions but place no orders")
    args = parser.parse_args()

    clock = SystemClock()
    conn = get_connection(settings.PORTFOLIO_DB_PATH)
    try:
        run_date = args.date_str or clock.today().isoformat()
        res = run_baseline_marks(
            run_date, clock, conn, dry_run=args.dry_run, force=args.force, no_orders=args.no_orders
        )
        print(f"baseline-marks: {res}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
