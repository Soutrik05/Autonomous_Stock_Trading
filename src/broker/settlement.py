"""
Settlement and daily NAV job run at 15:35 IST:
Updates positions.last_price, computes cash/invested/total paise for each agent,
and writes daily_nav with the Nifty 500 close.
See Plan_v3 §4.4.
"""

import argparse
import logging
import sqlite3

from broker.quotes import LiveQuoteProvider
from core.calendar import is_trading_day
from core.clock import Clock, SystemClock
from core.config import settings
from core.database import get_connection
from core.interfaces import QuoteProvider
from core.money import paise_to_rupees

logger = logging.getLogger(__name__)
JOB_NAME = "settlement"


def _upsert_terminal_run(
    conn: sqlite3.Connection, run_date_str: str, status: str, clock: Clock, detail: str | None = None
) -> None:
    now = clock.now_iso()
    conn.execute(
        """
        INSERT INTO pipeline_runs (job, run_date, status, started_at, finished_at, detail)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(job, run_date) DO UPDATE SET
            status = excluded.status, started_at = excluded.started_at,
            finished_at = excluded.finished_at, detail = excluded.detail
        """,
        (JOB_NAME, run_date_str, status, now, now, detail),
    )


def run_settlement(
    portfolio_conn: sqlite3.Connection,
    clock: Clock,
    quote_provider: QuoteProvider | None = None,
    run_date_str: str | None = None,
    nifty500_close: float | None = None,
) -> dict:
    """Computes daily NAV for all active agents and writes one daily_nav row per agent."""
    today = clock.today()
    run_date = run_date_str or today.isoformat()
    run_date_obj = clock.today() if run_date_str is None else today.fromisoformat(run_date)

    if not is_trading_day(portfolio_conn, run_date_obj):
        _upsert_terminal_run(portfolio_conn, run_date, "SKIPPED_HOLIDAY", clock, detail="Not a trading day.")
        return {"status": "SKIPPED_HOLIDAY", "agents_settled": 0}

    # 1. Update last prices on open positions if quote_provider is present
    open_positions = portfolio_conn.execute("SELECT id, ticker FROM positions WHERE status = 'OPEN'").fetchall()
    if open_positions and quote_provider is not None:
        tickers = list({p["ticker"] for p in open_positions})
        quotes = quote_provider.get_quotes(tickers)
        for p in open_positions:
            price = quotes.get(p["ticker"])
            if price is not None and price > 0:
                portfolio_conn.execute("UPDATE positions SET last_price_paise = ? WHERE id = ?", (price, p["id"]))

    # 2. Determine Nifty 500 close
    nifty_close = nifty500_close
    if nifty_close is None and quote_provider is not None:
        index_quotes = quote_provider.get_quotes(["NIFTY_500"])
        if "NIFTY_500" in index_quotes:
            nifty_close = float(paise_to_rupees(index_quotes["NIFTY_500"]))
    if nifty_close is None:
        nifty_close = 0.0
    else:
        nifty_close = float(nifty_close)

    # 3. Compute and store daily NAV for all active agents
    agents = portfolio_conn.execute("SELECT id, cash_paise FROM agents WHERE is_active = 1").fetchall()
    settled_count = 0

    for agent in agents:
        agent_id = agent["id"]
        cash_paise = agent["cash_paise"]
        invested_row = portfolio_conn.execute(
            "SELECT COALESCE(SUM(shares * last_price_paise), 0) AS total FROM positions "
            "WHERE agent_id = ? AND status = 'OPEN'",
            (agent_id,),
        ).fetchone()
        invested_paise = invested_row["total"]
        total_paise = cash_paise + invested_paise

        portfolio_conn.execute(
            """
            INSERT INTO daily_nav (agent_id, nav_date, cash_paise, invested_paise, total_paise, nifty500_close)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(agent_id, nav_date) DO UPDATE SET
                cash_paise = excluded.cash_paise,
                invested_paise = excluded.invested_paise,
                total_paise = excluded.total_paise,
                nifty500_close = excluded.nifty500_close
            """,
            (agent_id, run_date, cash_paise, invested_paise, total_paise, nifty_close),
        )
        settled_count += 1

    detail = f"Settled {settled_count} agents; Nifty 500 close: {nifty_close}."
    _upsert_terminal_run(portfolio_conn, run_date, "SUCCESS", clock, detail=detail)
    return {"status": "SUCCESS", "agents_settled": settled_count, "nifty500_close": nifty_close}


def main() -> None:
    parser = argparse.ArgumentParser(description="15:35 IST settlement & daily NAV job.")
    parser.add_argument("--date", dest="date_str", default=None, help="YYYY-MM-DD run date (default: today)")
    parser.add_argument("--nifty-close", dest="nifty_close", type=float, default=None, help="Nifty 500 closing price")
    args = parser.parse_args()

    clock = SystemClock()
    conn = get_connection(settings.PORTFOLIO_DB_PATH)
    try:
        quote_provider = LiveQuoteProvider(conn)
        res = run_settlement(
            conn, clock, quote_provider=quote_provider, run_date_str=args.date_str, nifty500_close=args.nifty_close
        )
        print(f"settlement: {res}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
