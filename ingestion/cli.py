"""
Ingestion entry point run nightly at 20:00 IST; orchestrates OHLCV, fundamentals, news and macro syncs.
See Plan_v3 §1.4.
"""
import argparse
import sqlite3
from datetime import date

from core.calendar import is_trading_day
from core.clock import Clock, SystemClock
from core.database import get_connection
from ingestion.sync_macro import sync_macro
from ingestion.sync_ohlcv import sync_ohlcv
from ingestion.upstox_client import UpstoxClient
from settings import settings

JOB_NAME = "ingestion"


def _upsert_terminal_run(conn: sqlite3.Connection, run_date_str: str, status: str, clock: Clock, detail: str = None) -> None:
    """One-shot run that starts and finishes at once (used for SKIPPED_HOLIDAY)."""
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


def _start_run(conn: sqlite3.Connection, run_date_str: str, clock: Clock) -> None:
    conn.execute(
        """
        INSERT INTO pipeline_runs (job, run_date, status, started_at, finished_at, detail)
        VALUES (?, ?, 'RUNNING', ?, NULL, NULL)
        ON CONFLICT(job, run_date) DO UPDATE SET
            status = 'RUNNING', started_at = excluded.started_at, finished_at = NULL, detail = NULL
        """,
        (JOB_NAME, run_date_str, clock.now_iso()),
    )


def _finish_run(conn: sqlite3.Connection, run_date_str: str, status: str, clock: Clock, detail: str = None) -> None:
    conn.execute(
        "UPDATE pipeline_runs SET status = ?, finished_at = ?, detail = ? WHERE job = ? AND run_date = ?",
        (status, clock.now_iso(), detail, JOB_NAME, run_date_str),
    )


def run(clock: Clock = None, client=None, date_str: str = None, limit: int = None,
        portfolio_conn: sqlite3.Connection = None, ohlcv_conn: sqlite3.Connection = None,
        macro_conn: sqlite3.Connection = None) -> str:
    """Runs one ingestion pass for the given date (default clock.today()). Returns the final
    pipeline_runs status: SKIPPED_HOLIDAY, SUCCESS or FAILED."""
    clock = clock or SystemClock()
    owns_conn = portfolio_conn is None
    conn = portfolio_conn or get_connection(settings.PORTFOLIO_DB_PATH)
    try:
        run_date: date = date.fromisoformat(date_str) if date_str else clock.today()
        run_date_str = run_date.isoformat()

        if not is_trading_day(conn, run_date):
            _upsert_terminal_run(conn, run_date_str, "SKIPPED_HOLIDAY", clock, detail="Not a trading day.")
            return "SKIPPED_HOLIDAY"

        _start_run(conn, run_date_str, clock)
        run_client = client or UpstoxClient()
        try:
            sync_ohlcv(run_client, clock, ohlcv_conn=ohlcv_conn, portfolio_conn=conn, limit=limit)
            sync_macro(run_client, clock, macro_conn=macro_conn, portfolio_conn=conn, as_of_date=run_date_str)
        except Exception as exc:  # noqa: BLE001 - a failed nightly job must still write FAILED, not crash the process
            _finish_run(conn, run_date_str, "FAILED", clock, detail=str(exc)[:500])
            return "FAILED"

        _finish_run(conn, run_date_str, "SUCCESS", clock)
        return "SUCCESS"
    finally:
        if owns_conn:
            conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Nightly ingestion entry point.")
    parser.add_argument("--date", dest="date_str", default=None, help="YYYY-MM-DD, default: today (IST)")
    parser.add_argument("--limit", dest="limit", type=int, default=None, help="Only the first N active tickers")
    args = parser.parse_args()
    status = run(date_str=args.date_str, limit=args.limit)
    print(f"ingestion: {status}")


if __name__ == "__main__":
    main()
