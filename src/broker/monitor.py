"""
Stateless monitor: one poll per run against pending-order and open-position tickers, applies fill rules.
See Plan_v3 §4.3, §4.4.
"""

import argparse
import logging
from decimal import ROUND_HALF_UP, Decimal

from broker.engine import Broker
from broker.quotes import LiveQuoteProvider
from broker.trailing import compute_graduated_stop
from core.calendar import is_trading_day
from core.clock import Clock, SystemClock
from core.config import settings
from core.database import get_connection
from core.interfaces import QuoteProvider

logger = logging.getLogger(__name__)


def _entry_high_with_overshoot_paise(entry_high_paise: int) -> int:
    overshoot = Decimal(1) + Decimal(str(settings.BUY_OVERSHOOT_PCT)) / Decimal(100)
    return int((Decimal(entry_high_paise) * overshoot).to_integral_value(rounding=ROUND_HALF_UP))


def poll_once(
    portfolio_conn,
    clock: Clock,
    quote_provider: QuoteProvider,
    run_date_str: str | None = None,
) -> dict:
    """Executes a single stateless monitor poll over pending orders and open positions."""
    today = clock.today()
    run_date = run_date_str or today.isoformat()
    run_date_obj = clock.today() if run_date_str is None else today.fromisoformat(run_date)

    if not is_trading_day(portfolio_conn, run_date_obj):
        return {"status": "SKIPPED_HOLIDAY", "detail": f"{run_date} is not a trading day."}

    broker = Broker(portfolio_conn, clock)

    # 1. Gather all pending orders valid for this run date and open positions
    pending_orders = portfolio_conn.execute(
        "SELECT * FROM pending_orders WHERE status = 'pending' AND valid_for_date <= ?",
        (run_date,),
    ).fetchall()

    open_positions = portfolio_conn.execute(
        "SELECT * FROM positions WHERE status = 'OPEN'",
    ).fetchall()

    tickers = sorted(list({o["ticker"] for o in pending_orders} | {p["ticker"] for p in open_positions}))
    if not tickers:
        return {
            "status": "SUCCESS",
            "tickers_checked": 0,
            "buys_filled": 0,
            "sells_filled": 0,
            "stops_hit": 0,
            "crashes_cancelled": 0,
            "targets_reached": 0,
        }

    # 2. Fetch market quotes
    quotes = quote_provider.get_quotes(tickers)

    summary = {
        "status": "SUCCESS",
        "tickers_checked": len(tickers),
        "buys_filled": 0,
        "sells_filled": 0,
        "stops_hit": 0,
        "crashes_cancelled": 0,
        "targets_reached": 0,
    }

    # 3. Process each ticker
    for ticker in tickers:
        price = quotes.get(ticker)
        if price is None or price <= 0:
            continue

        # (a) Check open positions for this ticker: Stop-loss & Target
        positions_for_ticker = portfolio_conn.execute(
            "SELECT * FROM positions WHERE ticker = ? AND status = 'OPEN'", (ticker,)
        ).fetchall()

        for pos in positions_for_ticker:
            # Update last price
            portfolio_conn.execute(
                "UPDATE positions SET last_price_paise = ? WHERE id = ? AND status = 'OPEN'",
                (price, pos["id"]),
            )

            if pos["frozen_reason"] is not None:
                continue

            # Stop-loss check
            if pos["stop_paise"] and price <= pos["stop_paise"]:
                is_long_horizon = pos["agent_id"] in (
                    "jhunjhunwala",
                    "baseline-rj-rules",
                    "lynch",
                    "baseline-lynch-rules",
                    "marks",
                    "baseline-marks-rules",
                )
                now_dt = clock.now()
                is_closing_window = (now_dt.hour == 15 and now_dt.minute >= 15) or now_dt.hour > 15
                severe_crash = price <= int(pos["stop_paise"] * 0.90)

                if (not is_long_horizon) or is_closing_window or severe_crash:
                    if broker.close_position(pos["id"], price, "STOP_HIT"):
                        summary["stops_hit"] += 1
                    continue

            # Target check (soft signal, logged at most once per position per day)
            if price >= pos["target_paise"]:
                already_logged = portfolio_conn.execute(
                    "SELECT 1 FROM activity_log WHERE event_type = 'TARGET_REACHED' "
                    "AND agent_id = ? AND ticker = ? AND created_at LIKE ?",
                    (pos["agent_id"], pos["ticker"], f"{run_date}%"),
                ).fetchone()
                if not already_logged:
                    broker._log_activity(
                        pos["agent_id"],
                        "TARGET_REACHED",
                        pos["ticker"],
                        f"Target reached for {pos['ticker']} @ {price} paise",
                        {
                            "position_id": pos["id"],
                            "target_paise": pos["target_paise"],
                            "price_paise": price,
                        },
                    )
                    summary["targets_reached"] += 1

            # (a.3) Broker-Level Graduated Trailing Stop Protection
            pos_keys = pos.keys()
            initial_stop = pos["initial_stop_paise"] if "initial_stop_paise" in pos_keys else None
            stored_peak = (
                pos["peak_price_paise"]
                if ("peak_price_paise" in pos_keys and pos["peak_price_paise"])
                else pos["avg_entry_price_paise"]
            )
            new_peak = max(stored_peak, price)
            candidate_stop = compute_graduated_stop(
                avg_entry_price_paise=pos["avg_entry_price_paise"],
                current_stop_paise=pos["stop_paise"],
                initial_stop_paise=initial_stop,
                peak_price_paise=new_peak,
            )
            if candidate_stop > pos["stop_paise"]:
                if "peak_price_paise" in pos_keys:
                    portfolio_conn.execute(
                        "UPDATE positions SET stop_paise = ?, peak_price_paise = ? WHERE id = ?",
                        (candidate_stop, new_peak, pos["id"]),
                    )
                else:
                    portfolio_conn.execute(
                        "UPDATE positions SET stop_paise = ? WHERE id = ?",
                        (candidate_stop, pos["id"]),
                    )

        # (b) Check pending orders for this ticker
        orders_for_ticker = portfolio_conn.execute(
            "SELECT * FROM pending_orders WHERE ticker = ? AND status = 'pending' AND valid_for_date <= ?",
            (ticker, run_date),
        ).fetchall()

        for order in orders_for_ticker:
            side = order["side"]
            if side == "SELL":
                # Fills at the first poll of the valid day at prevailing price
                if broker.fill_sell(order["id"], price):
                    summary["sells_filled"] += 1
            elif side == "BUY":
                stop_paise = order["stop_paise"] or 0
                entry_high_overshoot = _entry_high_with_overshoot_paise(order["entry_high_paise"])

                if stop_paise > 0 and price <= stop_paise:
                    # Crash cancellation: price hit stop before filling
                    if broker.cancel_order(order["id"], "CRASH_CANCELLED"):
                        summary["crashes_cancelled"] += 1
                elif price <= entry_high_overshoot:
                    # Exchange limit buy mechanics: fill at prevailing price when price <= limit high
                    # (provides price improvement on gap-downs below entry_low)
                    if broker.fill_buy(order["id"], price):
                        summary["buys_filled"] += 1
                # Otherwise, price is above overshoot (waiting)

    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Stateless market monitor poll.")
    parser.add_argument("--date", dest="date_str", default=None, help="YYYY-MM-DD run date (default: today)")
    args = parser.parse_args()

    clock = SystemClock()
    conn = get_connection(settings.PORTFOLIO_DB_PATH)
    try:
        quote_provider = LiveQuoteProvider(conn)
        res = poll_once(conn, clock, quote_provider, run_date_str=args.date_str)
        print(f"monitor poll: {res}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
