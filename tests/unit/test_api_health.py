"""
Tests for GET /api/health. Uses a real temp SQLite file (not :memory:) so the dependency's
mode=ro URI connection -- the exact code path the live app uses -- is actually exercised.
See docs/backend_implementation_guide_week5.md §3.8.
"""

import pytest

from ._api_test_helpers import NOW, build_file_db, clear_overrides, make_client


@pytest.fixture(autouse=True)
def _reset_overrides():
    yield
    clear_overrides()


def test_empty_db_returns_200_with_no_jobs(tmp_path):
    db_path = str(tmp_path / "portfolio.db")
    build_file_db(db_path)
    client = make_client(db_path)

    resp = client.get("/api/health")

    assert resp.status_code == 200
    body = resp.json()
    assert body["database_reachable"] is True
    assert body["jobs"] == []


def test_seeded_pipeline_runs_returns_latest_row_per_job_with_duration(tmp_path):
    db_path = str(tmp_path / "portfolio.db")
    build_file_db(db_path)
    import sqlite3

    conn = sqlite3.connect(db_path, isolation_level=None)
    conn.execute(
        "INSERT INTO pipeline_runs (job, run_date, status, started_at, finished_at, detail) "
        "VALUES ('ingestion', '2026-11-04', 'SUCCESS', "
        "'2026-11-04T20:00:00+05:30', '2026-11-04T20:02:30+05:30', NULL)"
    )
    conn.execute(
        "INSERT INTO pipeline_runs (job, run_date, status, started_at, finished_at, detail) "
        "VALUES ('ingestion', '2026-11-05', 'FAILED', "
        "'2026-11-05T20:00:00+05:30', '2026-11-05T20:00:05+05:30', 'upstream timeout')"
    )
    conn.close()
    client = make_client(db_path)

    resp = client.get("/api/health")

    assert resp.status_code == 200
    jobs = resp.json()["jobs"]
    assert len(jobs) == 1  # only the latest run_date for the job, not every row
    job = jobs[0]
    assert job["job_name"] == "ingestion"
    assert job["status"] == "FAILED"
    assert job["duration_sec"] == 5
    assert job["error_message"] == "upstream timeout"
    assert job["cadence"] == "Daily 20:00 IST (Mon-Fri)"


def test_unknown_job_name_still_appears_with_null_cadence(tmp_path):
    db_path = str(tmp_path / "portfolio.db")
    build_file_db(db_path)
    import sqlite3

    conn = sqlite3.connect(db_path, isolation_level=None)
    conn.execute(
        "INSERT INTO pipeline_runs (job, run_date, status, started_at, finished_at, detail) "
        "VALUES ('some_future_job', '2026-11-04', 'SUCCESS', ?, ?, NULL)",
        (NOW, NOW),
    )
    conn.close()
    client = make_client(db_path)

    resp = client.get("/api/health")

    jobs = resp.json()["jobs"]
    assert len(jobs) == 1
    assert jobs[0]["job_name"] == "some_future_job"
    assert jobs[0]["cadence"] is None
