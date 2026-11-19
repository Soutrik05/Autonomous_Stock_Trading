"""
Unit tests for core/calendar.py trading-day helpers and seed_calendar, against an in-memory db.
See Plan_v3 §1.5.
"""

import sqlite3
from datetime import date
from pathlib import Path

from core.calendar import is_trading_day, next_trading_day, previous_trading_day, seed_calendar

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "db" / "schema.sql"


def make_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    return conn


class FakeUpstoxClient:
    def __init__(self, holidays):
        self._holidays = holidays

    def get_holidays(self):
        return self._holidays


def test_weekend_is_never_a_trading_day():
    conn = make_db()
    saturday = date(2026, 10, 17)
    sunday = date(2026, 10, 18)
    assert is_trading_day(conn, saturday) is False
    assert is_trading_day(conn, sunday) is False


def test_weekday_with_no_row_defaults_to_trading_day():
    conn = make_db()
    monday = date(2026, 10, 19)
    assert is_trading_day(conn, monday) is True


def test_seeded_holiday_is_not_a_trading_day():
    conn = make_db()
    holiday = date(2026, 10, 21)
    conn.execute(
        "INSERT INTO market_calendar (trade_date, is_trading_day, session_type, note) VALUES (?, 0, 'CLOSED', 'Diwali')",
        (holiday.isoformat(),),
    )
    assert is_trading_day(conn, holiday) is False


def test_next_trading_day_skips_weekend_and_holiday():
    conn = make_db()
    # Friday 2026-10-16 is a trading day; Mon 2026-10-19 is seeded as a holiday.
    conn.execute(
        "INSERT INTO market_calendar (trade_date, is_trading_day, session_type, note) VALUES ('2026-10-19', 0, 'CLOSED', 'Holiday')"
    )
    friday = date(2026, 10, 16)
    assert next_trading_day(conn, friday) == date(2026, 10, 20)  # Sat/Sun/Mon(holiday) skipped


def test_previous_trading_day_skips_weekend():
    conn = make_db()
    monday = date(2026, 10, 19)
    assert previous_trading_day(conn, monday) == date(2026, 10, 16)  # skips Sat/Sun


def test_seed_calendar_writes_only_nse_closed_and_muhurat_rows():
    conn = make_db()
    client = FakeUpstoxClient(
        [
            {
                "date": "2026-01-15",
                "description": "Election",
                "holiday_type": "TRADING_HOLIDAY",
                "closed_exchanges": ["NSE", "BSE"],
            },
            {
                "date": "2026-02-01",
                "description": "MCX-only holiday",
                "holiday_type": "TRADING_HOLIDAY",
                "closed_exchanges": ["MCX"],
            },
            {
                "date": "2026-11-09",
                "description": "Diwali Muhurat",
                "holiday_type": "MUHURAT_TRADING",
                "closed_exchanges": [],
            },
        ]
    )
    written = seed_calendar(client, conn)
    assert written == 2  # the MCX-only row is irrelevant to NSE and is skipped

    assert is_trading_day(conn, date(2026, 1, 15)) is False
    row = conn.execute("SELECT session_type FROM market_calendar WHERE trade_date = '2026-11-09'").fetchone()
    assert row["session_type"] == "MUHURAT"
    assert is_trading_day(conn, date(2026, 11, 9)) is True
    assert conn.execute("SELECT 1 FROM market_calendar WHERE trade_date = '2026-02-01'").fetchone() is None
