"""
Trading-day helpers reading market_calendar, and a function to seed it from the Upstox holiday
list. All dates are IST strings 'YYYY-MM-DD' (as date objects at the function boundary).
See Plan_v3 §1.5.
"""
import sqlite3
from datetime import date, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.clock import Clock
    from ingestion.upstox_client import UpstoxClient

_MAX_SCAN_DAYS = 30  # safety bound against an unreasonably long holiday streak


def is_trading_day(conn: sqlite3.Connection, trade_date: date) -> bool:
    """Weekends are always non-trading. A weekday with no market_calendar row is assumed a
    trading day; a row's is_trading_day flag is authoritative when present."""
    if trade_date.weekday() >= 5:  # Saturday=5, Sunday=6
        return False
    row = conn.execute(
        "SELECT is_trading_day FROM market_calendar WHERE trade_date = ?",
        (trade_date.isoformat(),),
    ).fetchone()
    if row is None:
        return True
    return bool(row["is_trading_day"] if isinstance(row, sqlite3.Row) else row[0])


def next_trading_day(conn: sqlite3.Connection, trade_date: date) -> date:
    candidate = trade_date + timedelta(days=1)
    for _ in range(_MAX_SCAN_DAYS):
        if is_trading_day(conn, candidate):
            return candidate
        candidate += timedelta(days=1)
    raise RuntimeError(f"No trading day found within {_MAX_SCAN_DAYS} days after {trade_date}")


def previous_trading_day(conn: sqlite3.Connection, trade_date: date) -> date:
    candidate = trade_date - timedelta(days=1)
    for _ in range(_MAX_SCAN_DAYS):
        if is_trading_day(conn, candidate):
            return candidate
        candidate -= timedelta(days=1)
    raise RuntimeError(f"No trading day found within {_MAX_SCAN_DAYS} days before {trade_date}")


def seed_calendar(client: "UpstoxClient", conn: sqlite3.Connection) -> int:
    """Loads the Upstox holiday list into market_calendar (upsert by trade_date). A holiday that
    closes NSE is recorded as is_trading_day=0/session_type='CLOSED'; a Muhurat-type entry (NSE
    stays open for a special/truncated session) is recorded as is_trading_day=1/'MUHURAT'.
    Returns the number of rows written."""
    holidays = client.get_holidays()
    written = 0
    for holiday in holidays:
        closed_exchanges = holiday.get("closed_exchanges") or []
        holiday_type = (holiday.get("holiday_type") or "").upper()
        trade_date = holiday.get("date")
        if not trade_date:
            continue
        if "NSE" in closed_exchanges:
            is_trading, session_type = 0, "CLOSED"
        elif "MUHURAT" in holiday_type:
            is_trading, session_type = 1, "MUHURAT"
        else:
            continue  # irrelevant to NSE equities (e.g. only MCX/other exchanges affected)
        conn.execute(
            """
            INSERT INTO market_calendar (trade_date, is_trading_day, session_type, note)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(trade_date) DO UPDATE SET
                is_trading_day = excluded.is_trading_day,
                session_type = excluded.session_type,
                note = excluded.note
            """,
            (trade_date, is_trading, session_type, holiday.get("description")),
        )
        written += 1
    return written
