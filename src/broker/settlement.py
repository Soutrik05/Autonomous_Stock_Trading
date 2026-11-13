"""
Settlement and daily NAV job run at 15:35 IST:
Credits ex-date corporate action dividends, updates positions.last_price,
computes cash/invested/total paise for each agent, and writes daily_nav with
the Nifty 500 close.
See Plan_v3 §4.4.
"""

import argparse
import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path

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


def _normalize_date(date_str: str | None) -> str | None:
    """Normalizes various date formats (e.g. '23 Oct 2026', '2026-10-23') to ISO 'YYYY-MM-DD'."""
    if not date_str:
        return None
    cleaned = date_str.strip()
    for fmt in ("%Y-%m-%d", "%d %b %Y", "%d-%b-%Y", "%d %B %Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(cleaned, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return cleaned


def process_dividend_payouts(
    portfolio_conn: sqlite3.Connection,
    run_date_str: str,
    clock: Clock,
    fundamental_conn: sqlite3.Connection | None = None,
) -> list[dict]:
    """
    Identifies stocks held by agents that go ex-dividend on run_date_str.
    For each eligible held position, credits agents.cash_paise by
    (shares * amount_per_share * 100) paise, logs DIVIDEND_CREDITED to activity_log,
    and inserts an audit record in dividend_payouts.

    Under Indian equity settlement rules (Method A - Ex-Date Gross Credit), an investor
    holding shares into the ex-date (cum-dividend) receives the gross dividend payout.
    Eligibility rule:
      position.entry_date < ex_date AND (position.status = 'OPEN' OR position.exit_date >= ex_date)
    """
    close_fundamental = False
    f_conn = fundamental_conn
    if f_conn is None:
        db_path = Path(settings.FUNDAMENTAL_DB_PATH)
        if db_path.exists():
            try:
                f_conn = get_connection(str(db_path))
                close_fundamental = True
            except Exception as e:
                logger.warning("Could not open fundamental DB for dividend processing: %s", e)
                f_conn = None

    if f_conn is None:
        return []

    try:
        has_table = f_conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='corporate_actions'"
        ).fetchone()
        if not has_table:
            return []

        # Upstox returns expiry_date as 'DD Mon YYYY' (e.g. '23 Oct 2026') or ISO 'YYYY-MM-DD'
        candidate_dates = {run_date_str}
        try:
            d_obj = datetime.strptime(run_date_str, "%Y-%m-%d")
            candidate_dates.add(d_obj.strftime("%d %b %Y"))
            candidate_dates.add(f"{d_obj.day} {d_obj.strftime('%b %Y')}")
            candidate_dates.add(d_obj.strftime("%d-%b-%Y"))
        except Exception:
            pass

        placeholders = ",".join("?" for _ in candidate_dates)
        div_rows = f_conn.execute(
            f"""
            SELECT ticker, amount, expiry_date
            FROM corporate_actions
            WHERE expiry_date IN ({placeholders})
              AND LOWER(action_type) = 'dividend'
              AND amount IS NOT NULL
              AND amount > 0
            """,
            list(candidate_dates),
        ).fetchall()

        if not div_rows:
            return []

        credited_records = []
        now_iso = clock.now_iso()

        for div in div_rows:
            ticker = div["ticker"] if isinstance(div, sqlite3.Row) else div[0]
            amount = float(div["amount"] if isinstance(div, sqlite3.Row) else div[1])
            raw_expiry = div["expiry_date"] if isinstance(div, sqlite3.Row) else div[2]
            ex_date = _normalize_date(raw_expiry) or run_date_str

            # Find active agents holding this ticker across ex-date
            held_positions = portfolio_conn.execute(
                """
                SELECT p.id, p.agent_id, p.ticker, p.shares, p.entry_date, p.status, p.exit_date
                FROM positions p
                JOIN agents a ON p.agent_id = a.id
                WHERE p.ticker = ?
                  AND a.is_active = 1
                  AND p.shares > 0
                  AND p.entry_date < ?
                  AND (p.status = 'OPEN' OR p.exit_date >= ?)
                """,
                (ticker, ex_date, ex_date),
            ).fetchall()

            for pos in held_positions:
                pos_id = pos["id"]
                agent_id = pos["agent_id"]
                shares = pos["shares"]

                # Ensure idempotence - skip if already credited for this agent, ticker, and ex_date
                already_paid = portfolio_conn.execute(
                    "SELECT 1 FROM dividend_payouts WHERE agent_id = ? AND ticker = ? AND ex_date = ?",
                    (agent_id, ticker, ex_date),
                ).fetchone()
                if already_paid:
                    continue

                payout_paise = int(round(shares * amount * 100))
                if payout_paise <= 0:
                    continue

                # 1. Credit agent cash balance
                portfolio_conn.execute(
                    "UPDATE agents SET cash_paise = cash_paise + ?, updated_at = ? WHERE id = ?",
                    (payout_paise, now_iso, agent_id),
                )

                # 2. Insert audit record in dividend_payouts
                portfolio_conn.execute(
                    """
                    INSERT INTO dividend_payouts
                        (agent_id, ticker, position_id, ex_date, amount_per_share, shares, payout_paise, credited_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (agent_id, ticker, pos_id, ex_date, amount, shares, payout_paise, now_iso),
                )

                # 3. Log to activity_log
                description = (
                    f"Credited ₹{payout_paise / 100:,.2f} dividend for {shares} shares of {ticker} "
                    f"(₹{amount:.2f}/share, ex-date {ex_date})."
                )
                meta_json = json.dumps({
                    "shares": shares,
                    "amount_per_share": amount,
                    "payout_paise": payout_paise,
                    "ex_date": ex_date,
                    "position_id": pos_id,
                    "severity": "SUCCESS",
                })
                portfolio_conn.execute(
                    """
                    INSERT INTO activity_log (agent_id, event_type, ticker, description, metadata_json, created_at)
                    VALUES (?, 'DIVIDEND_CREDITED', ?, ?, ?, ?)
                    """,
                    (agent_id, ticker, description, meta_json, now_iso),
                )

                credited_records.append({
                    "agent_id": agent_id,
                    "ticker": ticker,
                    "position_id": pos_id,
                    "shares": shares,
                    "amount": amount,
                    "payout_paise": payout_paise,
                    "ex_date": ex_date,
                })
                logger.info(
                    "Credited dividend to agent %s: ₹%.2f on %d shares of %s (ex-date %s)",
                    agent_id,
                    payout_paise / 100.0,
                    shares,
                    ticker,
                    ex_date,
                )

        return credited_records
    finally:
        if close_fundamental and f_conn:
            f_conn.close()


def run_settlement(
    portfolio_conn: sqlite3.Connection,
    clock: Clock,
    quote_provider: QuoteProvider | None = None,
    run_date_str: str | None = None,
    nifty500_close: float | None = None,
    fundamental_conn: sqlite3.Connection | None = None,
) -> dict:
    """Computes daily NAV for all active agents and writes one daily_nav row per agent."""
    today = clock.today()
    run_date = run_date_str or today.isoformat()
    run_date_obj = clock.today() if run_date_str is None else today.fromisoformat(run_date)

    if not is_trading_day(portfolio_conn, run_date_obj):
        _upsert_terminal_run(portfolio_conn, run_date, "SKIPPED_HOLIDAY", clock, detail="Not a trading day.")
        return {"status": "SKIPPED_HOLIDAY", "agents_settled": 0, "dividends_credited": 0, "dividend_payout_paise": 0}

    # 1. Process corporate action dividend payouts for positions held into ex-date
    div_records = process_dividend_payouts(portfolio_conn, run_date, clock, fundamental_conn=fundamental_conn)
    div_count = len(div_records)
    total_div_paise = sum(r["payout_paise"] for r in div_records)

    # 2. Update last prices on open positions if quote_provider is present
    open_positions = portfolio_conn.execute("SELECT id, ticker FROM positions WHERE status = 'OPEN'").fetchall()
    if open_positions and quote_provider is not None:
        tickers = list({p["ticker"] for p in open_positions})
        quotes = quote_provider.get_quotes(tickers)
        for p in open_positions:
            price = quotes.get(p["ticker"])
            if price is not None and price > 0:
                portfolio_conn.execute("UPDATE positions SET last_price_paise = ? WHERE id = ?", (price, p["id"]))

    # 3. Determine Nifty 500 close
    nifty_close = nifty500_close
    if nifty_close is None and quote_provider is not None:
        index_quotes = quote_provider.get_quotes(["NIFTY_500"])
        if "NIFTY_500" in index_quotes:
            nifty_close = float(paise_to_rupees(index_quotes["NIFTY_500"]))
    if nifty_close is None:
        nifty_close = 0.0
    else:
        nifty_close = float(nifty_close)

    # 4. Compute and store daily NAV for all active agents
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

    detail = (
        f"Settled {settled_count} agents; Nifty 500 close: {nifty_close}; "
        f"Dividends credited: {div_count} (₹{total_div_paise / 100:,.2f})."
    )
    _upsert_terminal_run(portfolio_conn, run_date, "SUCCESS", clock, detail=detail)
    return {
        "status": "SUCCESS",
        "agents_settled": settled_count,
        "nifty500_close": nifty_close,
        "dividends_credited": div_count,
        "dividend_payout_paise": total_div_paise,
    }


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
