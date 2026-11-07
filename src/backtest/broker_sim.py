"""
Fast daily candle broker simulation for historical backtests.
Reuses broker/engine.py Broker class for all state transitions, charges, and slippage.
Provides daily candle price resolution, stop-loss / target matching, order expiry,
and daily NAV mark-to-market settlement.
See Plan_v3 §5.6.
"""

import logging
import sqlite3
from datetime import date
from typing import Any
from zoneinfo import ZoneInfo

from backtest.config import CADENCE_TABLE
from broker.engine import Broker
from broker.expiry import expire_pending_orders
from broker.quotes import ReplayQuoteProvider
from broker.settlement import run_settlement
from broker.trailing import compute_graduated_stop
from core.clock import Clock
from core.config import settings
from core.money import rupees_to_paise

logger = logging.getLogger(__name__)
IST = ZoneInfo("Asia/Kolkata")


def resolve_day(
    conn: sqlite3.Connection,
    ohlcv_conn: sqlite3.Connection,
    clock: Clock,
    trade_date: str,
    nifty500_close: float = 24000.0,
    intraday_conn: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    """
    Executes a complete simulated trading session:
    - If intraday_conn is provided and has data, runs high-fidelity multi-bar matching.
    - Otherwise runs hardened daily candle matching with Minimax tie-breaking,
      pre-open price improvement on gap-downs, sequenced ratchet, and same-day stop checks.
    """
    broker = Broker(conn, clock)

    # 0. Check for granular historical intraday data (e.g. Upstox 30m/1m candles)
    if intraday_conn is not None:
        try:
            # Query active tickers (open positions + pending orders) to avoid loading 500 idle tickers
            active_tickers = [
                r[0]
                for r in conn.execute(
                    "SELECT ticker FROM positions WHERE status = 'OPEN' "
                    "UNION SELECT ticker FROM pending_orders WHERE status = 'pending' AND (valid_for_date = ? OR valid_for_date IS NULL)",
                    (trade_date,),
                ).fetchall()
            ]
            if active_tickers:
                placeholders = ",".join(["?"] * len(active_tickers))
                intraday_rows = intraday_conn.execute(
                    f"""
                    SELECT ticker, candle_time, open, high, low, close, volume
                    FROM ohlcv_intraday
                    WHERE trade_date = ? AND ticker IN ({placeholders})
                    ORDER BY candle_time ASC
                    """,
                    (trade_date, *active_tickers),
                ).fetchall()
                if intraday_rows:
                    return _resolve_day_intraday(conn, intraday_rows, broker, clock, trade_date, nifty500_close)
        except Exception as exc:
            logger.debug("Intraday resolution fell back to daily for %s: %s", trade_date, exc)

    # 1. Fetch OHLCV candles for trade_date
    candle_rows = ohlcv_conn.execute(
        """
        SELECT ticker, open, high, low, close, volume
        FROM ohlcv
        WHERE trade_date = ?
        """,
        (trade_date,),
    ).fetchall()

    if not candle_rows:
        return {"status": "NO_CANDLES", "trade_date": trade_date, "fills": 0, "stops": 0, "targets": 0}

    candles: dict[str, dict[str, int]] = {
        r["ticker"]: {
            "open": rupees_to_paise(float(r["open"])),
            "high": rupees_to_paise(float(r["high"])),
            "low": rupees_to_paise(float(r["low"])),
            "close": rupees_to_paise(float(r["close"])),
        }
        for r in candle_rows
    }

    fills_count = 0
    stops_count = 0
    targets_count = 0

    # 2. Check OPEN Positions for Stops, Targets, Trailing Ratchet, and Time/Decay Exits
    open_positions = conn.execute(
        """
        SELECT *
        FROM positions WHERE status = 'OPEN'
        """
    ).fetchall()
    conn.commit()

    for pos in open_positions:
        ticker = pos["ticker"]
        if ticker not in candles:
            continue
        c = candles[ticker]
        stop = pos["stop_paise"]
        target = pos["target_paise"]
        entry_price = pos["avg_entry_price_paise"]
        agent_id = pos["agent_id"]
        entry_date_str = pos["entry_date"]

        # Calculate hold sessions so far
        hold_sessions = 0
        if entry_date_str:
            try:
                entry_dt = date.fromisoformat(entry_date_str)
                cur_dt = clock.today()
                hold_sessions = broker._trading_days_between(entry_dt, cur_dt)
            except Exception:
                hold_sessions = 0

        # 2a. Immediate Gap-Down at Market Open Check:
        # If open is at or below the stop, exit immediately at open
        if stop and stop > 0 and c["open"] <= stop:
            exit_price = c["open"]
            broker.close_position(pos["id"], exit_price, "STOP_HIT")
            stops_count += 1
            continue

        # 2b. Price Action Stop-Loss
        # For long-horizon fundamental/value compounders (RJ, Lynch, Marks), require close-confirmed breach
        # to prevent premature shakeouts from transient intraday wick volatility.
        # For quantitative/momentum swing personas (Simons, Varsity), trigger on intraday low breach.
        is_long_horizon = agent_id in (
            "jhunjhunwala",
            "baseline-rj-rules",
            "lynch",
            "baseline-lynch-rules",
            "marks",
            "baseline-marks-rules",
        )
        stop_breached = (c["close"] <= stop) if is_long_horizon else (c["low"] <= stop)

        if stop and stop > 0 and stop_breached:
            exit_price = min(stop, c["close"] if is_long_horizon else c["open"])
            broker.close_position(pos["id"], exit_price, "STOP_HIT")
            stops_count += 1
            continue
        elif target and target > 0 and c["high"] >= target:
            # Soft target telemetry: broker records TARGET_REACHED; position remains OPEN for agent deliberation
            already_logged = conn.execute(
                "SELECT 1 FROM activity_log WHERE event_type = 'TARGET_REACHED' "
                "AND agent_id = ? AND ticker = ? AND created_at LIKE ?",
                (agent_id, ticker, f"{trade_date}%"),
            ).fetchone()
            if not already_logged:
                broker._log_activity(
                    agent_id,
                    "TARGET_REACHED",
                    ticker,
                    f"Target reached for {ticker} @ {c['high']} paise (target: {target})",
                    {
                        "position_id": pos["id"],
                        "target_paise": target,
                        "high_paise": c["high"],
                        "close_paise": c["close"],
                        "trade_date": trade_date,
                    },
                )
            targets_count += 1

        # 2d. Mechanical Max Hold Horizon Ceiling
        rule = CADENCE_TABLE.get(agent_id)
        if rule and hold_sessions >= rule.max_hold_days:
            exit_price = c["open"]
            broker.close_position(pos["id"], exit_price, "TIME_STOP_HIT")
            stops_count += 1
            continue

        # 2e. Mechanical Alpha-Decay Stop (for Simons / Baseline)
        # If held >= 8 sessions and current price has not gained at least 1.0x ATR from entry
        if agent_id in ("simons", "baseline-simons-rules") and hold_sessions >= 8:
            initial_risk = max(1, entry_price - (stop or int(entry_price * 0.94)))
            atr_approx = int(initial_risk / 2.5)
            if c["open"] < entry_price + atr_approx:
                exit_price = c["open"]
                broker.close_position(pos["id"], exit_price, "ALPHA_DECAY_HIT")
                stops_count += 1
                continue

        # 2f. Broker-Level Graduated Trailing Stop Protection
        pos_keys = pos.keys()
        initial_stop = pos["initial_stop_paise"] if "initial_stop_paise" in pos_keys else None
        stored_peak = (
            pos["peak_price_paise"] if ("peak_price_paise" in pos_keys and pos["peak_price_paise"]) else entry_price
        )
        new_peak = max(stored_peak, c["high"])
        candidate_stop = compute_graduated_stop(
            avg_entry_price_paise=entry_price,
            current_stop_paise=stop,
            initial_stop_paise=initial_stop,
            peak_price_paise=new_peak,
        )

        if candidate_stop > stop:
            if c["close"] <= candidate_stop:
                exit_price = candidate_stop
                broker.close_position(pos["id"], exit_price, "STOP_HIT")
                stops_count += 1
                continue
            else:
                if "peak_price_paise" in pos_keys:
                    conn.execute(
                        "UPDATE positions SET stop_paise = ?, peak_price_paise = ? WHERE id = ?",
                        (candidate_stop, new_peak, pos["id"]),
                    )
                else:
                    conn.execute(
                        "UPDATE positions SET stop_paise = ? WHERE id = ?",
                        (candidate_stop, pos["id"]),
                    )
                conn.commit()

    # 3. Match Pending Orders
    pending_orders = conn.execute(
        """
        SELECT id, ticker, side, entry_low_paise, entry_high_paise, stop_paise, target_paise, agent_id
        FROM pending_orders
        WHERE status = 'pending' AND (valid_for_date = ? OR valid_for_date IS NULL)
        ORDER BY id ASC
        """,
        (trade_date,),
    ).fetchall()
    conn.commit()

    overshoot_multiplier = 1.0 + (settings.BUY_OVERSHOOT_PCT / 100.0)

    for order in pending_orders:
        ticker = order["ticker"]
        if ticker not in candles:
            continue
        c = candles[ticker]
        side = order["side"]

        if side == "BUY":
            entry_low = order["entry_low_paise"] or 0
            entry_high = order["entry_high_paise"] or 0
            allowed_high = int(entry_high * overshoot_multiplier)

            # Candle must intersect or trade through entry range
            if c["low"] <= allowed_high and c["high"] >= entry_low:
                # Real exchange auction & limit mechanics:
                # If market opened at or below entry_high, fill at open (providing price improvement on gap-downs)
                if c["open"] <= entry_high:
                    fill_price = c["open"]
                elif c["low"] <= entry_high:
                    fill_price = entry_high
                else:
                    fill_price = allowed_high

                if broker.fill_buy(order["id"], fill_price):
                    fills_count += 1

                    # Bug Fix: Eliminate same-day stop-loss immunity
                    # Check whether the candle breached the stop on the day of entry
                    stop = order["stop_paise"]
                    target = order["target_paise"]
                    pos = broker._get_open_position(order["agent_id"], order["ticker"])
                    is_long_horizon = order["agent_id"] in (
                        "jhunjhunwala",
                        "baseline-rj-rules",
                        "lynch",
                        "baseline-lynch-rules",
                        "marks",
                        "baseline-marks-rules",
                    )
                    entry_stop_breached = (c["close"] <= stop) if is_long_horizon else (c["low"] <= stop)
                    if pos and stop and stop > 0 and entry_stop_breached:
                        exit_price = min(stop, c["close"] if is_long_horizon else fill_price)
                        broker.close_position(pos["id"], exit_price, "STOP_HIT")
                        stops_count += 1
                    elif pos and target and target > 0 and c["high"] >= target:
                        # Soft target telemetry on entry day
                        already_logged = conn.execute(
                            "SELECT 1 FROM activity_log WHERE event_type = 'TARGET_REACHED' "
                            "AND agent_id = ? AND ticker = ? AND created_at LIKE ?",
                            (order["agent_id"], order["ticker"], f"{trade_date}%"),
                        ).fetchone()
                        if not already_logged:
                            broker._log_activity(
                                order["agent_id"],
                                "TARGET_REACHED",
                                order["ticker"],
                                f"Target reached on entry day for {order['ticker']} @ {c['high']} paise (target: {target})",
                                {
                                    "position_id": pos["id"],
                                    "target_paise": target,
                                    "high_paise": c["high"],
                                    "close_paise": c["close"],
                                    "trade_date": trade_date,
                                },
                            )
                        targets_count += 1

                    # Graduated trailing stop evaluation on entry day
                    if pos:
                        pos_keys = pos.keys()
                        new_peak = max(fill_price, c["high"])
                        candidate_stop = compute_graduated_stop(
                            avg_entry_price_paise=fill_price,
                            current_stop_paise=stop or 0,
                            initial_stop_paise=stop or 0,
                            peak_price_paise=new_peak,
                        )
                        if stop and candidate_stop > stop:
                            if c["close"] <= candidate_stop:
                                broker.close_position(pos["id"], candidate_stop, "STOP_HIT")
                                stops_count += 1
                            else:
                                if "peak_price_paise" in pos_keys:
                                    conn.execute(
                                        "UPDATE positions SET stop_paise = ?, peak_price_paise = ? WHERE id = ?",
                                        (candidate_stop, new_peak, pos["id"]),
                                    )
                                else:
                                    conn.execute(
                                        "UPDATE positions SET stop_paise = ? WHERE id = ?",
                                        (candidate_stop, pos["id"]),
                                    )
                                conn.commit()
        elif side == "SELL":
            # Sell fills at day open
            if broker.fill_sell(order["id"], c["open"]):
                fills_count += 1

    # 4. Expire Unfilled Pending Orders
    expire_pending_orders(conn, clock, run_date_str=trade_date)

    # 5. Settlement & Daily NAV Calculation
    quote_map = {t: c["close"] for t, c in candles.items()}
    replay_provider = ReplayQuoteProvider(quote_map)
    run_settlement(conn, clock, quote_provider=replay_provider, run_date_str=trade_date, nifty500_close=nifty500_close)

    return {
        "status": "SUCCESS",
        "trade_date": trade_date,
        "fills": fills_count,
        "stops": stops_count,
        "targets": targets_count,
    }


def _resolve_day_intraday(
    conn: sqlite3.Connection,
    intraday_rows: list[sqlite3.Row],
    broker: Broker,
    clock: Clock,
    trade_date: str,
    nifty500_close: float,
) -> dict[str, Any]:
    """
    High-fidelity multi-bar intraday matching across time-sliced bars (e.g. Upstox 30m or 1m).
    Resolves order fills, stops, and targets in strict chronological sequence.
    """
    fills_count = 0
    stops_count = 0
    targets_count = 0

    slices: dict[str, dict[str, dict[str, int]]] = {}
    last_close: dict[str, int] = {}
    for r in intraday_rows:
        t_slice = r["candle_time"]
        ticker = r["ticker"]
        c_dict = {
            "open": rupees_to_paise(float(r["open"])),
            "high": rupees_to_paise(float(r["high"])),
            "low": rupees_to_paise(float(r["low"])),
            "close": rupees_to_paise(float(r["close"])),
        }
        slices.setdefault(t_slice, {})[ticker] = c_dict
        last_close[ticker] = c_dict["close"]

    overshoot_multiplier = 1.0 + (settings.BUY_OVERSHOOT_PCT / 100.0)

    for t_slice, candle_map in sorted(slices.items()):
        open_pos = conn.execute("SELECT * FROM positions WHERE status = 'OPEN'").fetchall()

        for pos in open_pos:
            ticker = pos["ticker"]
            if ticker not in candle_map:
                continue
            bar = candle_map[ticker]
            stop = pos["stop_paise"]
            target = pos["target_paise"]
            entry_price = pos["avg_entry_price_paise"]

            if stop and stop > 0 and bar["low"] <= stop:
                exit_price = min(stop, bar["open"])
                broker.close_position(pos["id"], exit_price, "STOP_HIT")
                stops_count += 1
                continue
            elif target and target > 0 and bar["high"] >= target:
                already_logged = conn.execute(
                    "SELECT 1 FROM activity_log WHERE event_type = 'TARGET_REACHED' "
                    "AND agent_id = ? AND ticker = ? AND created_at LIKE ?",
                    (pos["agent_id"], ticker, f"{trade_date}%"),
                ).fetchone()
                if not already_logged:
                    broker._log_activity(
                        pos["agent_id"],
                        "TARGET_REACHED",
                        ticker,
                        f"Target reached for {ticker} @ {bar['high']} paise (target: {target})",
                        {
                            "position_id": pos["id"],
                            "target_paise": target,
                            "high_paise": bar["high"],
                            "close_paise": bar["close"],
                            "trade_date": trade_date,
                        },
                    )
                targets_count += 1

            # Graduated trailing stop evaluation per intraday bar
            pos_keys = pos.keys()
            initial_stop = pos["initial_stop_paise"] if "initial_stop_paise" in pos_keys else None
            stored_peak = (
                pos["peak_price_paise"] if ("peak_price_paise" in pos_keys and pos["peak_price_paise"]) else entry_price
            )
            new_peak = max(stored_peak, bar["high"])
            candidate_stop = compute_graduated_stop(
                avg_entry_price_paise=entry_price,
                current_stop_paise=stop,
                initial_stop_paise=initial_stop,
                peak_price_paise=new_peak,
            )
            if candidate_stop > stop:
                if bar["close"] <= candidate_stop:
                    broker.close_position(pos["id"], candidate_stop, "STOP_HIT")
                    stops_count += 1
                    continue
                else:
                    if "peak_price_paise" in pos_keys:
                        conn.execute(
                            "UPDATE positions SET stop_paise = ?, peak_price_paise = ? WHERE id = ?",
                            (candidate_stop, new_peak, pos["id"]),
                        )
                    else:
                        conn.execute(
                            "UPDATE positions SET stop_paise = ? WHERE id = ?",
                            (candidate_stop, pos["id"]),
                        )
                    conn.commit()

        pending = conn.execute(
            "SELECT id, ticker, side, entry_low_paise, entry_high_paise, stop_paise, target_paise, agent_id "
            "FROM pending_orders WHERE status = 'pending' AND (valid_for_date = ? OR valid_for_date IS NULL)",
            (trade_date,),
        ).fetchall()

        for order in pending:
            ticker = order["ticker"]
            if ticker not in candle_map:
                continue
            bar = candle_map[ticker]

            if order["side"] == "BUY":
                entry_low = order["entry_low_paise"] or 0
                entry_high = order["entry_high_paise"] or 0
                allowed_high = int(entry_high * overshoot_multiplier)

                if bar["low"] <= allowed_high and bar["high"] >= entry_low:
                    fill_price = (
                        bar["open"]
                        if bar["open"] <= entry_high
                        else (entry_high if bar["low"] <= entry_high else allowed_high)
                    )
                    if broker.fill_buy(order["id"], fill_price):
                        fills_count += 1
                        new_pos = broker._get_open_position(order["agent_id"], order["ticker"])
                        if new_pos and order["stop_paise"] and bar["low"] <= order["stop_paise"]:
                            broker.close_position(new_pos["id"], min(order["stop_paise"], fill_price), "STOP_HIT")
                            stops_count += 1
                        elif new_pos:
                            pos_keys = new_pos.keys()
                            new_peak = max(fill_price, bar["high"])
                            cand = compute_graduated_stop(
                                avg_entry_price_paise=fill_price,
                                current_stop_paise=order["stop_paise"],
                                initial_stop_paise=order["stop_paise"],
                                peak_price_paise=new_peak,
                            )
                            if cand > order["stop_paise"]:
                                if bar["close"] <= cand:
                                    broker.close_position(new_pos["id"], cand, "STOP_HIT")
                                    stops_count += 1
                                else:
                                    if "peak_price_paise" in pos_keys:
                                        conn.execute(
                                            "UPDATE positions SET stop_paise = ?, peak_price_paise = ? WHERE id = ?",
                                            (cand, new_peak, new_pos["id"]),
                                        )
                                    else:
                                        conn.execute(
                                            "UPDATE positions SET stop_paise = ? WHERE id = ?",
                                            (cand, new_pos["id"]),
                                        )
                                    conn.commit()
            elif order["side"] == "SELL":
                if broker.fill_sell(order["id"], bar["open"]):
                    fills_count += 1

    expire_pending_orders(conn, clock, run_date_str=trade_date)
    replay_provider = ReplayQuoteProvider(last_close)
    run_settlement(conn, clock, quote_provider=replay_provider, run_date_str=trade_date, nifty500_close=nifty500_close)

    return {
        "status": "SUCCESS",
        "trade_date": trade_date,
        "fills": fills_count,
        "stops": stops_count,
        "targets": targets_count,
        "mode": "INTRADAY",
    }


def simulate_market_session(
    conn: sqlite3.Connection,
    ohlcv_conn: sqlite3.Connection,
    clock: Clock,
    trade_date: str,
    nifty500_close: float = 24000.0,
    intraday_conn: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    """Compatibility alias for resolve_day."""
    return resolve_day(conn, ohlcv_conn, clock, trade_date, nifty500_close=nifty500_close, intraday_conn=intraday_conn)
