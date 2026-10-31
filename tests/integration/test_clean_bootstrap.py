"""
Integration tests for clean-slate database bootstrapping and scheduler resilience.
Ensures that if the service starts up with a completely blank/uninitialized SQLite file
(such as in a newly deployed container or mounted volume), schema migrations and holiday
calendars are bootstrapped automatically without failing on missing tables.
"""
import sqlite3
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from core.clock import FakeClock
from core.database import get_connection
from ingestion.cli import run as run_ingestion
from scheduler import job_nightly_ingestion_and_features
from scripts.init_db import init_db
from settings import settings


def test_clean_slate_ingestion_bootstraps_schema(tmp_path):
    """
    Simulates starting ingestion on a non-existent/empty portfolio database file.
    Must self-heal by applying migrations, creating market_calendar, checking
    is_trading_day, and writing pipeline_runs without raising 'no such table: market_calendar'.
    """
    clean_db_path = tmp_path / "fresh_portfolio.db"
    assert not clean_db_path.exists()

    old_path = settings.PORTFOLIO_DB_PATH
    object.__setattr__(settings, "PORTFOLIO_DB_PATH", str(clean_db_path))

    try:
        clock = FakeClock(datetime(2026, 10, 19, 20, 0, 0))  # Monday
        mock_client = MagicMock()
        mock_client.get_holidays.return_value = []
        mock_client.get_daily_candles.return_value = []
        mock_client.get_market_quote.return_value = {}

        status = run_ingestion(
            clock=clock,
            client=mock_client,
            date_str="2026-10-19",
            portfolio_conn=None,  # Forces opening settings.PORTFOLIO_DB_PATH
        )

        assert clean_db_path.exists()
        conn = get_connection(str(clean_db_path))
        try:
            # Verify schema tables exist
            tables = {
                r[0]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            assert "market_calendar" in tables
            assert "pipeline_runs" in tables
            assert "agents" in tables
            assert "symbols" in tables

            # Verify agents were seeded
            agent_count = conn.execute("SELECT COUNT(*) FROM agents").fetchone()[0]
            assert agent_count >= 6

            # Verify pipeline_runs recorded a run
            run_row = conn.execute(
                "SELECT * FROM pipeline_runs WHERE job = 'ingestion' AND run_date = '2026-10-19'"
            ).fetchone()
            assert run_row is not None
            assert run_row["status"] in ("SUCCESS", "FAILED", "SKIPPED_HOLIDAY")
        finally:
            conn.close()
    finally:
        object.__setattr__(settings, "PORTFOLIO_DB_PATH", old_path)


def test_scheduler_job_on_uninitialized_database(tmp_path):
    """
    Simulates the exact crash scenario seen in container deployment:
    job_nightly_ingestion_and_features invoked when portfolio.db is an empty file.
    """
    empty_db_path = tmp_path / "empty_portfolio.db"
    # Create a 0-byte file
    empty_db_path.touch()

    old_path = settings.PORTFOLIO_DB_PATH
    object.__setattr__(settings, "PORTFOLIO_DB_PATH", str(empty_db_path))

    try:
        mock_client = MagicMock()
        mock_client.get_holidays.return_value = []
        mock_client.get_daily_candles.return_value = []
        mock_client.get_market_quote.return_value = {}

        with patch("ingestion.cli.UpstoxClient", return_value=mock_client), \
             patch("features.builder.run", return_value={"status": "SUCCESS", "written": 0, "skipped": 0}), \
             patch("watchlist.watchlist_refresh.run", return_value={"status": "SUCCESS", "symbols": []}):

            # Must not raise sqlite3.OperationalError: no such table: market_calendar
            job_nightly_ingestion_and_features()

        conn = get_connection(str(empty_db_path))
        try:
            tables = {
                r[0]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            assert "market_calendar" in tables
            assert "pipeline_runs" in tables
            assert "agents" in tables
        finally:
            conn.close()
    finally:
        object.__setattr__(settings, "PORTFOLIO_DB_PATH", old_path)


def test_init_db_idempotency_multiple_executions(tmp_path):
    """
    Verifies that calling init_db repeatedly on the same connection is completely idempotent
    and does not fail on duplicate column or table creation errors.
    """
    db_path = tmp_path / "idempotent.db"
    clock = FakeClock(datetime(2026, 10, 19, 10, 0, 0))

    conn = get_connection(str(db_path))
    try:
        # First execution
        init_db(conn, clock)
        count1 = conn.execute("SELECT COUNT(*) FROM agents").fetchone()[0]

        # Second execution
        init_db(conn, clock)
        count2 = conn.execute("SELECT COUNT(*) FROM agents").fetchone()[0]

        assert count1 == count2
        assert count1 >= 6
    finally:
        conn.close()
