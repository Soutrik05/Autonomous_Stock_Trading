"""
Baseline rules-based agent for Peter Lynch (baseline-lynch-rules).
Pure Python deterministic entry/exit rules executing textbook Peter Lynch GARP principles
(One Up On Wall Street, Ch. 7, 10, 13, 16, 17) without LLM calls.
Evaluates the exact candidate review pool that LLM Lynch saw.
"""

import argparse
import json
import logging
import sqlite3
from datetime import date

from baselines.common import delete_baseline_decisions, run_baseline_agent, run_baseline_cli
from broker.engine import Broker
from core.clock import Clock, SystemClock
from core.config import settings
from core.database import get_connection
from core.money import rupees_to_paise

logger = logging.getLogger(__name__)
AGENT_ID = "baseline-lynch-rules"
JOB_NAME = "baseline-lynch-rules"


def _delete_baseline_decisions(conn: sqlite3.Connection, run_date: str) -> None:
    delete_baseline_decisions(conn, AGENT_ID, run_date)

def evaluate_baseline_candidates(
    portfolio_conn: sqlite3.Connection,
    run_date: str,
    clock: Clock,
) -> list[dict]:
    """
    Generates rules-based decisions for baseline-lynch-rules:
    1. Evaluates all currently held positions for exit/ratchet triggers:
       - Valuation exit: PEG expands >= 1.8x (growth fully priced in / multiple stretched).
       - Target hit: >= 1:2.0 RRR reached.
       - Stop loss hit: 2.5x ATR-14 volatility breathing room line.
       - Story deterioration: CFO/PAT < 0.6x or earnings growth negative or D/E > 1.0.
       - Breakeven ratchet: trailing stop moved to entry once +1.5x risk distance is achieved.
       - Time cycle exit: held >= 90 trading sessions.
    2. Filters unheld candidates against textbook Peter Lynch GARP criteria:
       - PEG <= 1.20 (valuation anchor).
       - ROCE >= 12.0% (capital productivity).
       - Debt/Equity <= 0.80 ("companies with no debt cannot go bankrupt").
       - CFO/PAT >= 0.70 (earnings cash validation).
       - YoY PAT Growth >= 8.0% (Fast Growers & Stalwarts).
    3. Ranks passing candidates by 5-Factor GARP intensity_score.
    4. Sizing: 1.50% account risk budget, 20.0% maximum equity allocation, up to 5 focused positions.
    """
    from agents.personas import get_persona

    lynch_cfg = get_persona("lynch")
    max_candidates = getattr(lynch_cfg, "max_candidates", 10)
    max_positions = getattr(lynch_cfg, "max_open_positions", 5)
    atr_mult = getattr(lynch_cfg, "atr_stop_multiplier", 3.5)
    target_risk_pct = getattr(lynch_cfg, "target_risk_pct", 1.50)
    max_pos_pct = getattr(lynch_cfg, "max_position_pct", 20.0)
    sector_cap = getattr(lynch_cfg, "sector_cap", 2)

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

    # 2. Watchlist candidates from Lynch's Stage-3 funnel
    watchlist_rows = portfolio_conn.execute(
        "SELECT ticker, intensity_score FROM agent_watchlist WHERE agent_id = 'lynch' ORDER BY intensity_score DESC"
    ).fetchall()
    watchlist_intensity = {r["ticker"]: float(r["intensity_score"] or 0.0) for r in watchlist_rows}
    watchlist_not_held = [r["ticker"] for r in watchlist_rows if r["ticker"] not in held_tickers]

    # Assembled review pool: baseline open positions + Lynch's top unheld watchlist candidates
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
        peg = feats.get("peg")
        cfo_to_pat = feats.get("cfo_to_pat")
        pat_growth = feats.get("pat_growth_yoy_pct")
        debt_to_equity = feats.get("debt_to_equity")
        atr_14 = feats.get("atr_14")
        pos = held_by_ticker[ticker]

        target_event_today = False
        try:
            ev = portfolio_conn.execute(
                "SELECT 1 FROM activity_log WHERE agent_id IN (?, 'lynch') AND ticker = ? AND event_type = 'TARGET_REACHED' AND created_at LIKE ? LIMIT 1",
                (AGENT_ID, ticker, f"{run_date}%"),
            ).fetchone()
            target_event_today = ev is not None
        except Exception:
            pass

        target_reached = target_event_today or (
            close is not None and pos["target_paise"] is not None and close * 100 >= pos["target_paise"]
        )
        stop_hit = close is not None and pos["stop_paise"] is not None and close * 100 <= pos["stop_paise"]

        # Valuation exit: PEG expands >= 1.8x
        valuation_exhausted = peg is not None and peg >= 1.80

        # Story deterioration: cash flow collapse or negative profit growth or debt explosion
        story_broken = (
            (cfo_to_pat is not None and cfo_to_pat < 0.60)
            or (pat_growth is not None and pat_growth < 0.0)
            or (debt_to_equity is not None and debt_to_equity > 1.0)
        )

        # Intermediate time cycle exit (held >= 90 trading sessions)
        time_exit = False
        if pos["entry_date"]:
            try:
                hold_days = (date.fromisoformat(run_date) - date.fromisoformat(pos["entry_date"])).days
                if hold_days >= 90:
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
                    "reasoning": f"Lynch rule adjust on TARGET_REACHED: ratcheted stop to Rs{ratchet_stop:.2f} (locked 50% gain) and trailed target to Rs{new_target:.2f}.",
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
                    "reasoning": "Lynch rule exit: volatility stop hit (2.5x ATR risk line)",
                    "cited_metrics": None,
                    "snapshot_id": snapshot_id,
                }
            )
        elif valuation_exhausted:
            decisions.append(
                {
                    "ticker": ticker,
                    "action": "SELL",
                    "shares": None,
                    "entry_low": None,
                    "entry_high": None,
                    "stop_loss_price": None,
                    "target_price": None,
                    "reasoning": f"Lynch rule exit: valuation stretched (PEG={peg:.2f} >= 1.8), multiple expansion complete",
                    "cited_metrics": {"peg": peg},
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
                    "reasoning": f"Lynch rule exit: fundamental story deterioration (CFO/PAT={cfo_to_pat}, Growth={pat_growth}%, D/E={debt_to_equity})",
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
                    "reasoning": "Lynch rule exit: 90-day business compounding cycle completed",
                    "cited_metrics": None,
                    "snapshot_id": snapshot_id,
                }
            )
        else:
            # Trailing stop breakeven ratchet check
            entry_p = pos["avg_entry_price_paise"] / 100.0 if pos["avg_entry_price_paise"] else None
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
                            "reasoning": "Lynch trailing stop: ratcheted stop to breakeven after +1.0x risk profit expansion",
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
                    "reasoning": "Lynch rule hold: fundamental growth thesis, balance sheet, and earnings quality intact",
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
        peg = feats.get("peg")
        roce_pct = feats.get("roce_pct")
        roe_pct = feats.get("roe_pct")
        debt_to_equity = feats.get("debt_to_equity")
        cfo_to_pat = feats.get("cfo_to_pat")
        pat_growth = feats.get("pat_growth_yoy_pct")
        promoter = feats.get("promoter_holding_pct")
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
                    "reasoning": "Lynch rule veto: severe negative news sentiment (governance/accounting scandal risk)",
                    "cited_metrics": {"news_sentiment": news_sentiment},
                    "snapshot_id": snapshot_id,
                }
            )
            continue

        # Method 2A Textbook GARP Hurdles:
        # 1. PEG <= 1.20 (valuation anchor)
        # 2. ROCE >= 12.0% (capital productivity)
        # 3. Debt/Equity <= 0.80 ("companies with no debt cannot go bankrupt")
        # 4. CFO/PAT >= 0.70 (earnings cash validation)
        # 5. YoY PAT Growth >= 8.0% (Fast Growers & Stalwarts)
        passes_garp = (
            close is not None
            and close > 0
            and atr_14 is not None
            and atr_14 > 0
            and peg is not None
            and 0.0 < peg <= 1.20
            and roce_pct is not None
            and roce_pct >= 12.0
            and debt_to_equity is not None
            and debt_to_equity <= 0.80
            and cfo_to_pat is not None
            and cfo_to_pat >= 0.70
            and pat_growth is not None
            and pat_growth >= 8.0
        )

        if passes_garp:
            qualifying_unheld.append(
                {
                    "ticker": ticker,
                    "snapshot_id": snapshot_id,
                    "feats": feats,
                    "intensity": intensity,
                    "close": close,
                    "atr_14": atr_14,
                    "peg": peg,
                    "roce_pct": roce_pct,
                    "roe_pct": roe_pct,
                    "debt_to_equity": debt_to_equity,
                    "cfo_to_pat": cfo_to_pat,
                    "pat_growth_yoy_pct": pat_growth,
                    "promoter": promoter,
                }
            )
        else:
            reasons = []
            if peg is None or peg <= 0 or peg > 1.20:
                reasons.append(f"PEG {peg} exceeds 1.20 or invalid")
            if roce_pct is None or roce_pct < 12.0:
                reasons.append(f"ROCE {roce_pct}% < 12%")
            if debt_to_equity is None or debt_to_equity > 0.80:
                reasons.append(f"D/E {debt_to_equity} > 0.80")
            if cfo_to_pat is None or cfo_to_pat < 0.70:
                reasons.append(f"CFO/PAT {cfo_to_pat} < 0.70")
            if pat_growth is None or pat_growth < 8.0:
                reasons.append(f"PAT growth {pat_growth}% < 8%")

            decisions.append(
                {
                    "ticker": ticker,
                    "action": "HOLD",
                    "shares": None,
                    "entry_low": None,
                    "entry_high": None,
                    "stop_loss_price": None,
                    "target_price": None,
                    "reasoning": f"Lynch GARP criteria not met: {'; '.join(reasons)}",
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
                    "reasoning": f"Passed GARP but rejected: intensity {intensity:.2f} below conviction floor (0.50)",
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
                    "reasoning": f"Passed GARP (intensity {intensity:.2f}) but rejected: max position capacity reached ({max_positions}/{max_positions})",
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
                    "reasoning": f"Passed GARP but rejected: sector {sector} reached cap ({sector_cap} stocks)",
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

        # Enforce Minimum 1:2.0 Risk-to-Reward Ratio (Peter Lynch)
        # Target provides at least 2.25x risk distance (aiming above the 1:2.0 floor)
        target = round(close + max(2.25 * risk_distance, 5.5 * atr_14), 2)

        # Position Sizing: 1.50% Capital Risk Budget
        risk_rupees = account_value_rupees * (target_risk_pct / 100.0)
        shares_by_risk = int(risk_rupees // risk_distance)

        # 20.0% Capital Cap (Concentrated 5-position book)
        max_position_rupees = account_value_rupees * (max_pos_pct / 100.0)
        shares_by_cap = int(max_position_rupees // entry_high)

        shares = max(1, min(shares_by_risk, shares_by_cap))
        order_cost_paise = broker.worst_case_buy_outlay_paise(shares, rupees_to_paise(entry_high))

        if spendable_cash_paise >= order_cost_paise and 0 < stop_loss < entry_low <= entry_high < target:
            available_position_slots -= 1
            spendable_cash_paise -= order_cost_paise
            open_sector_counts[sector] = open_sector_counts.get(sector, 0) + 1

            category = "Fast Grower" if cand["pat_growth_yoy_pct"] >= 15.0 else "Stalwart"

            cited = {
                "peg": cand["peg"],
                "roce_pct": cand["roce_pct"],
                "debt_to_equity": cand["debt_to_equity"],
                "cfo_to_pat": cand["cfo_to_pat"],
                "pat_growth_yoy_pct": cand["pat_growth_yoy_pct"],
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
                        f"Lynch baseline BUY [{category}] (intensity {intensity:.2f}): "
                        f"PEG {cand['peg']:.2f}, ROCE {cand['roce_pct']}%, D/E {cand['debt_to_equity']}, "
                        f"CFO/PAT {cand['cfo_to_pat']:.2f}, PAT growth {cand['pat_growth_yoy_pct']}%, "
                        f"1:2.25 RRR with 2.5x ATR stop"
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
                    "reasoning": f"Passed GARP (intensity {intensity:.2f}) but rejected: spendable cash exhausted by higher-conviction compounders",
                    "cited_metrics": None,
                    "snapshot_id": snapshot_id,
                }
            )

    return decisions


def run_baseline_lynch(
    run_date: str,
    clock: Clock,
    portfolio_conn: sqlite3.Connection,
    dry_run: bool = False,
    force: bool = False,
    no_orders: bool = False,
) -> dict:
    """Executes the rules baseline agent for baseline-lynch-rules on run_date."""
    return run_baseline_agent(
        AGENT_ID,
        evaluate_baseline_candidates,
        run_date,
        clock,
        portfolio_conn,
        dry_run=dry_run,
        force=force,
        no_orders=no_orders,
    )


def main() -> None:
    run_baseline_cli(AGENT_ID, run_baseline_lynch, "Baseline Lynch Rules runner.")


if __name__ == "__main__":
    main()
