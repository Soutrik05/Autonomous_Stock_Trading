"""
Stateless monitor: one poll per run against pending-order and open-position tickers, applies fill rules.
See Plan_v3 §4.3, §4.4.
"""
import argparse
import json
import logging
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from broker.engine import Broker
from broker.quotes import LiveQuoteProvider
from core.calendar import is_trading_day
from core.clock import Clock, SystemClock
from core.database import get_connection
from core.interfaces import QuoteProvider
from settings import settings

logger = logging.getLogger(__name__)


def _entry_high_with_overshoot_paise(entry_high_paise: int) -> int:
    overshoot = Decimal(1) + Decimal(str(settings.BUY_OVERSHOOT_PCT)) / Decimal(100)
    return int((Decimal(entry_high_paise) * overshoot).to_integral_value(rounding=ROUND_HALF_UP))


def poll_once(
    portfolio_conn,
    clock: Clock,
    quote_provider: QuoteProvider,
    run_date_str: Optional[str] = None,
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
            if price <= pos["stop_paise"]:
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
                stop_paise = order["stop_paise"]
                entry_low = order["entry_low_paise"]
                entry_high_overshoot = _entry_high_with_overshoot_paise(order["entry_high_paise"])

                if price <= stop_paise:
                    # Crash cancellation: price hit stop before filling
                    if broker.cancel_order(order["id"], "CRASH_CANCELLED"):
                        summary["crashes_cancelled"] += 1
                elif entry_low <= price <= entry_high_overshoot:
                    if broker.fill_buy(order["id"], price):
                        summary["buys_filled"] += 1
                # Otherwise, price is either below entry_low (waiting) or above overshoot (waiting)

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
