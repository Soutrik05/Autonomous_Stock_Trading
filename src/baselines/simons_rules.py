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

from baselines.common import delete_baseline_decisions, run_baseline_agent, run_baseline_cli
from broker.engine import Broker
from core.clock import Clock, SystemClock
from core.config import settings
from core.database import get_connection
from core.money import rupees_to_paise

logger = logging.getLogger(__name__)
AGENT_ID = "baseline-simons-rules"
JOB_NAME = "baseline-simons-rules"


def _delete_baseline_decisions(conn: sqlite3.Connection, run_date: str) -> None:
    delete_baseline_decisions(conn, AGENT_ID, run_date)

def evaluate_baseline_candidates(
    portfolio_conn: sqlite3.Connection,
    run_date: str,
    clock: Clock,
) -> list[dict]:
    """Generates rules-based decisions for baseline-simons-rules:
    1. Evaluates all currently held positions for exit triggers (target, breakdown, KER collapse, time decay).
    2. Filters unheld candidates against quantitative momentum hurdles (trend, ADX, KER, RSI, volume, skew).
    3. Ranks passing candidates by Percentile Rank Composite intensity_score.
    4. Allocates capital strictly by conviction rank with a 5% cash liquidity reserve floor.
    """
    from agents.personas import get_persona

    simons_cfg = get_persona("simons")
    max_candidates = getattr(simons_cfg, "max_candidates", 8)
    max_positions = getattr(simons_cfg, "max_open_positions", 6)
    atr_mult = getattr(simons_cfg, "atr_stop_multiplier", 1.5)
    target_risk_pct = getattr(simons_cfg, "target_risk_pct", 0.75)
    max_pos_pct = getattr(simons_cfg, "max_position_pct", 10.0)

    # Regime-adaptive risk scaling
    cur_regime_row = portfolio_conn.execute(
        "SELECT features_json FROM feature_snapshots WHERE as_of_date = ? LIMIT 1",
        (run_date,),
    ).fetchone()
    current_regime = "NORMAL"
    if cur_regime_row:
        try:
            current_regime = json.loads(cur_regime_row["features_json"]).get("regime", "NORMAL")
        except Exception:
            pass

    if current_regime == "HIGH_VOLATILITY":
        max_positions = min(max_positions, 3)
        target_risk_pct = 0.40
    elif current_regime == "RANGE_BOUND":
        # Simons Regime Defense: trend breakouts have negative expectancy in range chop (~90% false breakouts)
        max_positions = 0

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
        ema_20 = feats.get("ema_20")
        adx_14 = feats.get("adx_14")
        kaufman_er = feats.get("kaufman_er_20")
        atr_14 = feats.get("atr_14")
        pos = held_by_ticker[ticker]

        target_event_today = False
        try:
            ev = portfolio_conn.execute(
                "SELECT 1 FROM activity_log WHERE agent_id IN (?, 'simons') AND ticker = ? AND event_type = 'TARGET_REACHED' AND created_at LIKE ? LIMIT 1",
                (AGENT_ID, ticker, f"{run_date}%"),
            ).fetchone()
            target_event_today = ev is not None
        except Exception:
            pass

        target_reached = target_event_today or (
            close is not None and pos["target_paise"] is not None and close * 100 >= pos["target_paise"]
        )
        trend_broken = ema_20 is not None and close is not None and close < ema_20
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
            entry_rupees = (pos["avg_entry_price_paise"] or 0) / 100.0
            tgt_rupees = (pos["target_paise"] or 0) / 100.0
            cur_stop_rupees = (pos["stop_paise"] or 0) / 100.0
            cur_price = close or tgt_rupees
            # Ratchet stop to lock in 50% of the gain above entry (Option A: Agent-side ratchet)
            ratchet_stop = max(cur_stop_rupees, entry_rupees + max(0.0, tgt_rupees - entry_rupees) * 0.5)
            # Ensure new_stop < cur_price
            if ratchet_stop >= cur_price:
                ratchet_stop = cur_price * 0.98
            # Trail target 25% higher to let winner run
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
                    "reasoning": f"Simons rule adjust on TARGET_REACHED: ratcheted stop to Rs{ratchet_stop:.2f} (locked 50% gain) and trailed target to Rs{new_target:.2f}.",
                    "cited_metrics": None,
                    "snapshot_id": snapshot_id,
                }
            )
        elif trend_broken:
            decisions.append(
                {
                    "ticker": ticker,
                    "action": "SELL",
                    "shares": None,
                    "entry_low": None,
                    "entry_high": None,
                    "stop_loss_price": None,
                    "target_price": None,
                    "reasoning": "Rule exit: trend breakdown (close < ema_20)",
                    "cited_metrics": None,
                    "snapshot_id": snapshot_id,
                }
            )
        elif efficiency_collapsed:
            decisions.append(
                {
                    "ticker": ticker,
                    "action": "SELL",
                    "shares": None,
                    "entry_low": None,
                    "entry_high": None,
                    "stop_loss_price": None,
                    "target_price": None,
                    "reasoning": "Rule exit: trend efficiency collapsed (KER < 0.20 or ADX < 18)",
                    "cited_metrics": None,
                    "snapshot_id": snapshot_id,
                }
            )
        elif time_decay:
            decisions.append(
                {
                    "ticker": ticker,
                    "action": "SELL",
                    "shares": None,
                    "entry_low": None,
                    "entry_high": None,
                    "stop_loss_price": None,
                    "target_price": None,
                    "reasoning": "Rule exit: time decay (held >= 8 sessions without 1.0x ATR profit)",
                    "cited_metrics": None,
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
                    "reasoning": "Rules hold: above 20 EMA, momentum and trend efficiency intact",
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
        zscore = feats.get("zscore_close_20")
        parkinson_vol = feats.get("parkinson_vol_ratio")
        intensity = watchlist_intensity.get(ticker, 0.0)

        # Dual-Engine Entry Filters: Setup A (Trend Continuation) OR Setup B (Mean-Reversion Dislocation)
        passes_trend = (
            ema_20_above_50 is True
            and close is not None
            and ema_20 is not None
            and close > ema_20
            and (ema_200 is None or close > ema_200)
            and rsi_14 is not None
            and 52.0 <= rsi_14 <= 72.0
            and volume_surge is not None
            and volume_surge >= 1.2
            and macd_hist is not None
            and macd_hist > 0.0
            and (adx_14 is None or adx_14 >= 25.0)
            and (kaufman_er is None or kaufman_er >= 0.35)
            and (skew is None or skew >= -0.5)
            and atr_14 is not None
            and atr_14 > 0
            and close is not None
            and close > 0
        )

        passes_reversion = (
            close is not None
            and close > 0
            and atr_14 is not None
            and atr_14 > 0
            and (ema_200 is None or close > ema_200)
            and zscore is not None
            and zscore <= -1.2
            and rsi_14 is not None
            and 20.0 <= rsi_14 <= 42.0
            and volume_surge is not None
            and volume_surge >= 1.2
            and (skew is None or skew >= -0.5)
        )

        if passes_trend or passes_reversion:
            setup_type = "TREND" if passes_trend else "REVERSION"
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
                    "macd_hist": macd_hist,
                    "adx_14": adx_14,
                    "kaufman_er": kaufman_er,
                    "zscore": zscore,
                    "parkinson_vol": parkinson_vol,
                    "setup_type": setup_type,
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
                    "reasoning": "Rules entry criteria not met (trend/momentum/efficiency filter failed)",
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

        # Minimum Conviction Floor check
        if intensity > 0 and intensity < 0.65:
            decisions.append(
                {
                    "ticker": ticker,
                    "action": "HOLD",
                    "shares": None,
                    "entry_low": None,
                    "entry_high": None,
                    "stop_loss_price": None,
                    "target_price": None,
                    "reasoning": f"Passed filters but rejected: intensity {intensity:.2f} below conviction floor (0.65)",
                    "cited_metrics": None,
                    "snapshot_id": snapshot_id,
                }
            )
            continue

        if available_position_slots <= 0:
            reason = (
                "RANGE_BOUND regime cash defense: momentum breakout edge has negative expectancy in sideways consolidation"
                if current_regime == "RANGE_BOUND"
                else f"Passed filters (intensity {intensity:.2f}) but rejected: max position capacity reached ({max_positions}/{max_positions})"
            )
            decisions.append(
                {
                    "ticker": ticker,
                    "action": "HOLD",
                    "shares": None,
                    "entry_low": None,
                    "entry_high": None,
                    "stop_loss_price": None,
                    "target_price": None,
                    "reasoning": reason,
                    "cited_metrics": None,
                    "snapshot_id": snapshot_id,
                }
            )
            continue

        # Volatility Parity Sizing
        entry_low = round(close - 0.25 * atr_14, 2)
        entry_high = round(close + 0.25 * atr_14, 2)
        stop_loss = round(close - atr_mult * atr_14, 2)
        if cand.get("parkinson_vol") is not None and cand["parkinson_vol"] > 3.0:
            parkinson_floor = round(close - (close * (cand["parkinson_vol"] / 100.0) * 0.75), 2)
            stop_loss = min(stop_loss, parkinson_floor)
        if stop_loss <= 0:
            stop_loss = round(entry_low * 0.90, 2)

        if cand.get("setup_type") == "REVERSION":
            ema_20 = cand["feats"].get("ema_20")
            if ema_20 and ema_20 > close:
                target = round(max(ema_20, close + 3.5 * atr_14), 2)
            else:
                target = round(close + 3.5 * atr_14, 2)
        else:
            target = round(close + 4.5 * atr_14, 2)

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
            if cand.get("setup_type") == "REVERSION":
                cited = {
                    "zscore_close_20": cand["zscore"],
                    "rsi_14": cand["rsi_14"],
                    "volume_surge": cand["volume_surge"],
                }
                if cand.get("parkinson_vol") is not None:
                    cited["parkinson_vol_ratio"] = cand["parkinson_vol"]
                reasoning = (
                    f"Rules baseline BUY [REVERSION] (intensity {intensity:.2f}): "
                    f"statistical zscore dislocation, oversold RSI, volume absorption"
                )
            else:
                cited = {"rsi_14": cand["rsi_14"], "volume_surge": cand["volume_surge"], "macd_hist": cand["macd_hist"]}
                if cand["adx_14"] is not None:
                    cited["adx_14"] = cand["adx_14"]
                if cand["kaufman_er"] is not None:
                    cited["kaufman_er_20"] = cand["kaufman_er"]
                reasoning = (
                    f"Rules baseline BUY [TREND] (intensity {intensity:.2f}): "
                    f"EMA alignment, RSI, volume surge, ADX/KER confirmed"
                )

            decisions.append(
                {
                    "ticker": ticker,
                    "action": "BUY",
                    "shares": shares,
                    "entry_low": entry_low,
                    "entry_high": entry_high,
                    "stop_loss_price": stop_loss,
                    "target_price": target,
                    "reasoning": reasoning,
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
                    "reasoning": f"Passed filters (intensity {intensity:.2f}) but rejected: spendable cash exhausted by higher-conviction candidates",
                    "cited_metrics": None,
                    "snapshot_id": snapshot_id,
                }
            )

    return decisions


def run_baseline_simons(
    run_date: str,
    clock: Clock,
    portfolio_conn: sqlite3.Connection,
    dry_run: bool = False,
    force: bool = False,
    no_orders: bool = False,
) -> dict:
    """Executes the rules baseline agent for baseline-simons-rules on run_date."""
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
    run_baseline_cli(AGENT_ID, run_baseline_simons, "Baseline Simons Rules runner.")


if __name__ == "__main__":
    main()
