"""
Unit and integration tests for pipeline retries, alerts, and startup catch-up.
Verifies consecutive failure counting, activity_log alert emissions, retry checkpoints,
and scheduler recovery behavior.
"""

import json
import sqlite3
from datetime import datetime
from unittest.mock import patch

import pytest

from core.clock import FakeClock
from notifications.alerts import count_consecutive_failures, record_pipeline_failure
from scheduler import (
    check_and_run_startup_catchup,
    is_nightly_pipeline_complete,
    job_nightly_pipeline_retry,
)
from scripts.init_db import init_db


@pytest.fixture
def test_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn, FakeClock(datetime(2026, 10, 19, 10, 0, 0)))
    yield conn
    conn.close()


class TestAlerts:
    def test_count_consecutive_failures(self, test_db):
        conn = test_db
        # No runs yet
        assert count_consecutive_failures(conn, "ingestion") == 0

        # One SUCCESS
        conn.execute(
            "INSERT INTO pipeline_runs (job, run_date, status, started_at) VALUES ('ingestion', '2026-10-15', 'SUCCESS', 't')"
        )
        assert count_consecutive_failures(conn, "ingestion") == 0

        # One FAILED
        conn.execute(
            "INSERT INTO pipeline_runs (job, run_date, status, started_at) VALUES ('ingestion', '2026-10-16', 'FAILED', 't')"
        )
        assert count_consecutive_failures(conn, "ingestion") == 1

        # Second FAILED
        conn.execute(
            "INSERT INTO pipeline_runs (job, run_date, status, started_at) VALUES ('ingestion', '2026-10-17', 'FAILED', 't')"
        )
        assert count_consecutive_failures(conn, "ingestion") == 2

        # A newer SUCCESS breaks the streak
        conn.execute(
            "INSERT INTO pipeline_runs (job, run_date, status, started_at) VALUES ('ingestion', '2026-10-18', 'SUCCESS', 't')"
        )
        assert count_consecutive_failures(conn, "ingestion") == 0

    def test_record_pipeline_failure_warning(self, test_db):
        conn = test_db
        clock = FakeClock(datetime(2026, 10, 19, 21, 0, 0))

        # Single failure -> WARNING
        conn.execute(
            "INSERT INTO pipeline_runs (job, run_date, status, started_at) VALUES ('nightly_pipeline', '2026-10-19', 'FAILED', 't')"
        )
        res = record_pipeline_failure(conn, "nightly_pipeline", "2026-10-19", "Timeout connecting to Upstox", clock)

        assert res["severity"] == "WARNING"
        assert res["consecutive_failures"] == 1

        row = conn.execute("SELECT * FROM activity_log WHERE event_type = 'PIPELINE_FAILED'").fetchone()
        assert row is not None
        assert "Timeout connecting to Upstox" in row["description"]
        meta = json.loads(row["metadata_json"])
        assert meta["severity"] == "WARNING"

    def test_record_pipeline_failure_critical_on_second_failure(self, test_db):
        conn = test_db
        clock = FakeClock(datetime(2026, 10, 20, 21, 0, 0))

        # Two consecutive failures -> CRITICAL
        conn.execute(
            "INSERT INTO pipeline_runs (job, run_date, status, started_at) VALUES ('nightly_pipeline', '2026-10-19', 'FAILED', 't')"
        )
        conn.execute(
            "INSERT INTO pipeline_runs (job, run_date, status, started_at) VALUES ('nightly_pipeline', '2026-10-20', 'FAILED', 't')"
        )

        res = record_pipeline_failure(conn, "nightly_pipeline", "2026-10-20", "Persistent API 500 error", clock)

        assert res["severity"] == "CRITICAL"
        assert res["consecutive_failures"] == 2

        row = conn.execute(
            "SELECT * FROM activity_log WHERE event_type = 'PIPELINE_FAILED' ORDER BY id DESC LIMIT 1"
        ).fetchone()
        assert "[CRITICAL]" in row["description"]


class TestSchedulerRetriesAndCatchup:
    def test_is_nightly_pipeline_complete(self, test_db):
        conn = test_db
        run_date = "2026-10-19"
        assert not is_nightly_pipeline_complete(conn, run_date)

        # Ingestion marked SKIPPED_HOLIDAY -> complete
        conn.execute(
            "INSERT INTO pipeline_runs (job, run_date, status, started_at) VALUES ('ingestion', ?, 'SKIPPED_HOLIDAY', 't')",
            (run_date,),
        )
        assert is_nightly_pipeline_complete(conn, run_date)

        # Or watchlist marked SUCCESS -> complete
        conn.execute("DELETE FROM pipeline_runs")
        conn.execute(
            "INSERT INTO pipeline_runs (job, run_date, status, started_at) VALUES ('watchlist', ?, 'SUCCESS', 't')",
            (run_date,),
        )
        assert is_nightly_pipeline_complete(conn, run_date)

    def test_retry_skips_when_pipeline_complete(self, test_db, monkeypatch):
        conn = test_db
        run_date = "2026-10-19"
        conn.execute(
            "INSERT INTO pipeline_runs (job, run_date, status, started_at) VALUES ('watchlist', ?, 'SUCCESS', 't')",
            (run_date,),
        )
        monkeypatch.setattr("scheduler.get_connection", lambda _: conn)
        monkeypatch.setattr("scheduler.SystemClock", lambda: FakeClock(datetime(2026, 10, 19, 20, 30, 0)))

        with patch("scheduler.execute_nightly_pipeline_pass") as mock_exec:
            job_nightly_pipeline_retry("20:30_checkpoint", is_final=False)
            mock_exec.assert_not_called()

    def test_retry_executes_pass_and_records_alert_on_final_failure(self, test_db, monkeypatch):
        conn = test_db
        run_date = "2026-10-19"
        monkeypatch.setattr("scheduler.get_connection", lambda _: conn)
        monkeypatch.setattr("scheduler.SystemClock", lambda: FakeClock(datetime(2026, 10, 19, 21, 0, 0)))

        with (
            patch("scheduler.execute_nightly_pipeline_pass", return_value="FAILED"),
            patch("notifications.alerts.record_pipeline_failure") as mock_alert,
        ):
            job_nightly_pipeline_retry("21:00_checkpoint", is_final=True)

            mock_alert.assert_called_once()
            args, _ = mock_alert.call_args
            assert args[1] == "nightly_pipeline"
            assert args[2] == run_date

    def test_startup_catchup_triggers_between_2000_and_2200(self, test_db):
        conn = test_db
        # Monday at 20:45 IST
        clock_2045 = FakeClock(datetime(2026, 10, 19, 20, 45, 0))

        with patch("scheduler.execute_nightly_pipeline_pass") as mock_exec:
            check_and_run_startup_catchup(clock_2045, conn)
            mock_exec.assert_called_once_with(clock_2045, conn, "2026-10-19")

    def test_startup_catchup_skips_outside_window_or_on_weekend(self, test_db):
        conn = test_db

        # 1. Daytime (15:00 IST) -> do not catch up nightly ingestion yet
        clock_1500 = FakeClock(datetime(2026, 10, 19, 15, 0, 0))
        with patch("scheduler.execute_nightly_pipeline_pass") as mock_exec:
            check_and_run_startup_catchup(clock_1500, conn)
            mock_exec.assert_not_called()

        # 2. Weekend (Saturday) -> do not run
        clock_sat = FakeClock(datetime(2026, 10, 24, 20, 30, 0))
        with patch("scheduler.execute_nightly_pipeline_pass") as mock_exec:
            check_and_run_startup_catchup(clock_sat, conn)
            mock_exec.assert_not_called()
