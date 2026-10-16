"""
Applies db/schema.sql to an in-memory database and proves the partial unique indexes and the
init_db seeding/idempotency contract.
See Plan_v3 §7.
"""
import sqlite3
from datetime import datetime
from pathlib import Path

import pytest

from core.clock import FakeClock
from scripts.init_db import AGENTS, init_db

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "db" / "schema.sql"
NOW_ISO = "2026-01-01T09:00:00+05:30"


def make_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    return conn


def insert_agent(conn: sqlite3.Connection, agent_id: str = "simons") -> None:
    conn.execute(
        """
        INSERT INTO agents
            (id, name, philosophy, kind, starting_cash_paise, cash_paise, created_at, updated_at)
        VALUES (?, 'Test Agent', 'Test', 'LLM', 10000000, 10000000, ?, ?)
        """,
        (agent_id, NOW_ISO, NOW_ISO),
    )


def insert_pending_order(conn: sqlite3.Connection, agent_id: str, ticker: str, status: str) -> None:
    conn.execute(
        """
        INSERT INTO pending_orders
            (agent_id, ticker, side, shares, entry_low_paise, entry_high_paise, stop_paise,
             target_paise, reserved_amount_paise, status, valid_for_date, created_at, updated_at)
        VALUES (?, ?, 'BUY', 10, 94000, 95500, 91000, 102000, 1000000, ?, '2026-01-02', ?, ?)
        """,
        (agent_id, ticker, status, NOW_ISO, NOW_ISO),
    )


def insert_position(conn: sqlite3.Connection, agent_id: str, ticker: str, status: str) -> None:
    conn.execute(
        """
        INSERT INTO positions
            (agent_id, ticker, sector, shares, avg_entry_price_paise, stop_paise, target_paise,
             last_price_paise, status, entry_date)
        VALUES (?, ?, 'ENG', 10, 94800, 91000, 102000, 94800, ?, '2026-01-01')
        """,
        (agent_id, ticker, status),
    )


# (a) pending_orders: one pending per (agent, ticker); pending + filled is allowed.

def test_two_pending_orders_same_agent_ticker_rejected():
    conn = make_db()
    insert_agent(conn)
    insert_pending_order(conn, "simons", "TATAMOTORS", "pending")
    with pytest.raises(sqlite3.IntegrityError):
        insert_pending_order(conn, "simons", "TATAMOTORS", "pending")


def test_pending_plus_filled_order_allowed():
    conn = make_db()
    insert_agent(conn)
    insert_pending_order(conn, "simons", "TATAMOTORS", "filled")
    insert_pending_order(conn, "simons", "TATAMOTORS", "pending")  # does not raise
    rows = conn.execute(
        "SELECT status FROM pending_orders WHERE agent_id='simons' AND ticker='TATAMOTORS' ORDER BY status"
    ).fetchall()
    assert {row["status"] for row in rows} == {"filled", "pending"}


# (b) positions: one OPEN per (agent, ticker); one OPEN + one CLOSED is allowed.

def test_two_open_positions_same_agent_ticker_rejected():
    conn = make_db()
    insert_agent(conn)
    insert_position(conn, "simons", "TATAMOTORS", "OPEN")
    with pytest.raises(sqlite3.IntegrityError):
        insert_position(conn, "simons", "TATAMOTORS", "OPEN")


def test_one_open_plus_one_closed_position_allowed():
    conn = make_db()
    insert_agent(conn)
    insert_position(conn, "simons", "TATAMOTORS", "CLOSED")
    insert_position(conn, "simons", "TATAMOTORS", "OPEN")  # does not raise
    rows = conn.execute(
        "SELECT status FROM positions WHERE agent_id='simons' AND ticker='TATAMOTORS' ORDER BY status"
    ).fetchall()
    assert {row["status"] for row in rows} == {"CLOSED", "OPEN"}


# (c) init_db seeds exactly 6 agents and is idempotent.

def test_init_db_seeds_six_agents_and_is_idempotent():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    clock = FakeClock(datetime(2026, 1, 1, 9, 0, 0))

    init_db(conn, clock)
    rows = conn.execute("SELECT id FROM agents ORDER BY id").fetchall()
    assert len(rows) == 6
    assert {row["id"] for row in rows} == {agent_id for agent_id, _, _, _ in AGENTS}

    init_db(conn, clock)  # run again: must not duplicate or raise
    rows_after = conn.execute("SELECT id FROM agents ORDER BY id").fetchall()
    assert len(rows_after) == 6
    version_rows = conn.execute("SELECT version FROM schema_version").fetchall()
    assert len(version_rows) == len({row["version"] for row in version_rows})
