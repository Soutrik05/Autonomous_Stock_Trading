"""
Tests for GET /api/activity: pagination, filters, and severity derivation.
See docs/backend_implementation_guide_week5.md §3.7.
"""

import json
import sqlite3

import pytest

from ._api_test_helpers import build_file_db, clear_overrides, make_client


@pytest.fixture(autouse=True)
def _reset_overrides():
    yield
    clear_overrides()


def _insert_event(db_path, event_type, agent_id=None, ticker=None, description="desc", metadata=None, created_at="2026-11-04T10:00:00+05:30"):
    conn = sqlite3.connect(db_path, isolation_level=None)
    conn.execute(
        "INSERT INTO activity_log (agent_id, event_type, ticker, description, metadata_json, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (agent_id, event_type, ticker, description, json.dumps(metadata) if metadata else None, created_at),
    )
    conn.close()


def test_empty_db_returns_200_with_no_events(tmp_path):
    db_path = str(tmp_path / "portfolio.db")
    build_file_db(db_path)
    client = make_client(db_path)

    resp = client.get("/api/activity")

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 0
    assert body["events"] == []


def test_severity_mapping_by_event_type(tmp_path):
    db_path = str(tmp_path / "portfolio.db")
    build_file_db(db_path)
    _insert_event(db_path, "BUY_FILLED", created_at="2026-11-04T10:00:01+05:30")
    _insert_event(db_path, "CAP_BREACH", created_at="2026-11-04T10:00:02+05:30")
    _insert_event(db_path, "WATCHLIST_REFRESH", created_at="2026-11-04T10:00:03+05:30")
    client = make_client(db_path)

    resp = client.get("/api/activity")

    by_type = {e["event_type"]: e["severity"] for e in resp.json()["events"]}
    assert by_type["BUY_FILLED"] == "SUCCESS"
    assert by_type["CAP_BREACH"] == "WARNING"
    assert by_type["WATCHLIST_REFRESH"] == "INFO"


def test_pipeline_failed_critical_metadata_remaps_to_error(tmp_path):
    db_path = str(tmp_path / "portfolio.db")
    build_file_db(db_path)
    _insert_event(db_path, "PIPELINE_FAILED", metadata={"severity": "CRITICAL", "job_name": "ingestion"})
    client = make_client(db_path)

    resp = client.get("/api/activity")

    events = resp.json()["events"]
    assert events[0]["severity"] == "ERROR"
    assert events[0]["details"]["job_name"] == "ingestion"


def test_pagination_limit_and_offset(tmp_path):
    db_path = str(tmp_path / "portfolio.db")
    build_file_db(db_path)
    for i in range(5):
        _insert_event(db_path, "WATCHLIST_REFRESH", created_at=f"2026-11-04T10:00:{i:02d}+05:30")
    client = make_client(db_path)

    resp = client.get("/api/activity?limit=2&offset=1")

    body = resp.json()
    assert body["total"] == 5
    assert body["limit"] == 2
    assert body["offset"] == 1
    assert len(body["events"]) == 2


def test_pagination_is_correct_after_severity_filtering_across_multiple_pages(tmp_path):
    """Severity has no DB column, so it's derived and filtered in Python -- this proves the
    filter runs BEFORE pagination (both `total` and the page contents reflect the filtered set,
    not the unfiltered one), across more than two pages."""
    db_path = str(tmp_path / "portfolio.db")
    build_file_db(db_path)
    # 7 WARNING (CAP_BREACH) events interleaved with 4 INFO (WATCHLIST_REFRESH) events = 11 rows,
    # 7 of which match severity=WARNING.
    severities_in_order = ["CAP_BREACH", "WATCHLIST_REFRESH"] * 4 + ["CAP_BREACH"] * 3
    for i, event_type in enumerate(severities_in_order):
        _insert_event(db_path, event_type, created_at=f"2026-11-04T10:{i:02d}:00+05:30")
    client = make_client(db_path)

    seen_ids = []
    offset = 0
    limit = 3
    total_reported = None
    for _ in range(10):  # safety bound against an infinite loop if pagination were ever broken
        resp = client.get(f"/api/activity?severity=WARNING&limit={limit}&offset={offset}")
        body = resp.json()
        total_reported = body["total"]
        if not body["events"]:
            break
        seen_ids.extend(e["id"] for e in body["events"])
        assert all(e["severity"] == "WARNING" for e in body["events"])
        offset += limit

    assert total_reported == 7  # the filtered count, not the unfiltered 11
    assert len(seen_ids) == 7  # every WARNING event seen exactly once across all pages
    assert len(set(seen_ids)) == 7  # no duplicates, no gaps


def test_filters_by_agent_id_and_severity(tmp_path):
    db_path = str(tmp_path / "portfolio.db")
    build_file_db(db_path)
    _insert_event(db_path, "BUY_FILLED", agent_id="simons", created_at="2026-11-04T10:00:00+05:30")
    _insert_event(db_path, "CAP_BREACH", agent_id="lynch", created_at="2026-11-04T10:00:01+05:30")
    client = make_client(db_path)

    resp = client.get("/api/activity?agent_id=simons")
    events = resp.json()["events"]
    assert len(events) == 1
    assert events[0]["agent_id"] == "simons"

    resp2 = client.get("/api/activity?severity=WARNING")
    events2 = resp2.json()["events"]
    assert len(events2) == 1
    assert events2[0]["event_type"] == "CAP_BREACH"


def test_search_q_matches_description(tmp_path):
    db_path = str(tmp_path / "portfolio.db")
    build_file_db(db_path)
    _insert_event(db_path, "CAP_BREACH", description="Sector exposure breach for Financial Services")
    _insert_event(db_path, "WATCHLIST_REFRESH", description="Nothing special here")
    client = make_client(db_path)

    resp = client.get("/api/activity?q=breach")

    events = resp.json()["events"]
    assert len(events) == 1
    assert "breach" in events[0]["message"].lower()
