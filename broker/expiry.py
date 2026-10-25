"""
Order expiry job run at 15:30 IST: marks all still-pending orders as expired.
See Plan_v3 §4.3 item 10, §4.4.
"""
import argparse
import logging
import sqlite3
from typing import Optional

from broker.engine import Broker
from core.calendar import is_trading_day
from core.clock import Clock, SystemClock
from core.database import get_connection
from settings import settings

logger = logging.getLogger(__name__)
JOB_NAME = "expiry"


def _upsert_terminal_run(conn: sqlite3.Connection, run_date_str: str, status: str, clock: Clock, detail: str = None) -> None:
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


def expire_pending_orders(
    portfolio_conn: sqlite3.Connection,
    clock: Clock,
    run_date_str: Optional[str] = None,
) -> dict:
    """Cancels all still-pending orders with reason 'EXPIRED' and records status in pipeline_runs."""
    today = clock.today()
    run_date = run_date_str or today.isoformat()
    run_date_obj = clock.today() if run_date_str is None else today.fromisoformat(run_date)

    if not is_trading_day(portfolio_conn, run_date_obj):
        _upsert_terminal_run(portfolio_conn, run_date, "SKIPPED_HOLIDAY", clock, detail="Not a trading day.")
        return {"status": "SKIPPED_HOLIDAY", "expired_count": 0}

    broker = Broker(portfolio_conn, clock)
    pending = portfolio_conn.execute(
        "SELECT id FROM pending_orders WHERE status = 'pending' AND valid_for_date <= ?",
        (run_date,),
    ).fetchall()

    expired_count = 0
    for row in pending:
        if broker.cancel_order(row["id"], "EXPIRED"):
            expired_count += 1

    detail = f"Expired {expired_count} pending orders."
    _upsert_terminal_run(portfolio_conn, run_date, "SUCCESS", clock, detail=detail)
    return {"status": "SUCCESS", "expired_count": expired_count}


def main() -> None:
    parser = argparse.ArgumentParser(description="15:30 IST order expiry job.")
    parser.add_argument("--date", dest="date_str", default=None, help="YYYY-MM-DD run date (default: today)")
    args = parser.parse_args()

    clock = SystemClock()
    conn = get_connection(settings.PORTFOLIO_DB_PATH)
    try:
        res = expire_pending_orders(conn, clock, run_date_str=args.date_str)
        print(f"expiry: {res}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
