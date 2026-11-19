"""
Tests for GET /api/funnel.
See docs/handin_week2.md (4-stage multi-agent watchlist funnel) and
docs/frontend_implementation_plan_week5.md's (mock) 500->350->20->3-5 funnel, which does not
match the real 3-stage shape -- see docs/api.md Deviations.
"""

import json
import sqlite3

import pytest

from ._api_test_helpers import build_file_db, clear_overrides, make_client, seed_agent


@pytest.fixture(autouse=True)
def _reset_overrides():
    yield
    clear_overrides()


def _insert_funnel_event(db_path, agent_id, stages: dict, created_at: str):
    conn = sqlite3.connect(db_path, isolation_level=None)
    conn.execute(
        "INSERT INTO activity_log (agent_id, event_type, description, metadata_json, created_at) "
        "VALUES (?, 'FUNNEL_COUNTS', 'funnel', ?, ?)",
        (agent_id, json.dumps(stages), created_at),
    )
    conn.close()


def test_no_rows_returns_200_with_empty_list(tmp_path):
    db_path = str(tmp_path / "portfolio.db")
    build_file_db(db_path)
    client = make_client(db_path)

    resp = client.get("/api/funnel")

    assert resp.status_code == 200
    assert resp.json() == []


def test_returns_real_stage_keys_in_stored_order(tmp_path):
    db_path = str(tmp_path / "portfolio.db")
    build_file_db(db_path)
    seed_agent(db_path, "simons", "Jim Simons", "Quant Momentum")
    _insert_funnel_event(
        db_path, "simons", {"stage0": 248, "stage1": 9, "final": 8}, "2026-10-29T20:05:00+05:30"
    )
    client = make_client(db_path)

    resp = client.get("/api/funnel")

    assert resp.status_code == 200
    entry = resp.json()[0]
    assert entry["agent_id"] == "simons"
    assert entry["run_date"] == "2026-10-29"
    assert entry["stages"] == [
        {"key": "stage0", "count": 248},
        {"key": "stage1", "count": 9},
        {"key": "final", "count": 8},
    ]


def test_newest_row_is_chosen_per_agent(tmp_path):
    db_path = str(tmp_path / "portfolio.db")
    build_file_db(db_path)
    seed_agent(db_path, "simons", "Jim Simons", "Quant Momentum")
    _insert_funnel_event(db_path, "simons", {"stage0": 100, "final": 5}, "2026-10-01T20:05:00+05:30")
    _insert_funnel_event(db_path, "simons", {"stage0": 200, "final": 9}, "2026-10-29T20:05:00+05:30")
    client = make_client(db_path)

    resp = client.get("/api/funnel")

    entry = resp.json()[0]
    assert entry["run_date"] == "2026-10-29"
    assert entry["stages"][0]["count"] == 200


def test_agent_filter_returns_only_that_agent(tmp_path):
    db_path = str(tmp_path / "portfolio.db")
    build_file_db(db_path)
    seed_agent(db_path, "simons", "Jim Simons", "Quant Momentum")
    seed_agent(db_path, "lynch", "Peter Lynch", "GARP")
    _insert_funnel_event(db_path, "simons", {"stage0": 100, "final": 5}, "2026-10-29T20:05:00+05:30")
    _insert_funnel_event(db_path, "lynch", {"stage0": 200, "final": 9}, "2026-10-29T20:05:00+05:30")
    client = make_client(db_path)

    resp = client.get("/api/funnel?agent_id=simons")

    assert len(resp.json()) == 1
    assert resp.json()[0]["agent_id"] == "simons"


def test_unknown_agent_id_returns_404(tmp_path):
    db_path = str(tmp_path / "portfolio.db")
    build_file_db(db_path)
    client = make_client(db_path)

    resp = client.get("/api/funnel?agent_id=nobody")

    assert resp.status_code == 404


def test_bad_metadata_json_skips_that_row_not_a_500(tmp_path):
    db_path = str(tmp_path / "portfolio.db")
    build_file_db(db_path)
    seed_agent(db_path, "simons", "Jim Simons", "Quant Momentum")
    conn = sqlite3.connect(db_path, isolation_level=None)
    conn.execute(
        "INSERT INTO activity_log (agent_id, event_type, description, metadata_json, created_at) "
        "VALUES ('simons', 'FUNNEL_COUNTS', 'funnel', 'not valid json {{{', '2026-10-29T20:05:00+05:30')"
    )
    conn.close()
    client = make_client(db_path)

    resp = client.get("/api/funnel")

    assert resp.status_code == 200
    assert resp.json() == []


def test_bad_metadata_json_falls_back_to_an_older_valid_row(tmp_path):
    db_path = str(tmp_path / "portfolio.db")
    build_file_db(db_path)
    seed_agent(db_path, "simons", "Jim Simons", "Quant Momentum")
    _insert_funnel_event(db_path, "simons", {"stage0": 100, "final": 5}, "2026-10-01T20:05:00+05:30")
    conn = sqlite3.connect(db_path, isolation_level=None)
    conn.execute(
        "INSERT INTO activity_log (agent_id, event_type, description, metadata_json, created_at) "
        "VALUES ('simons', 'FUNNEL_COUNTS', 'funnel', 'not valid json {{{', '2026-10-29T20:05:00+05:30')"
    )
    conn.close()
    client = make_client(db_path)

    resp = client.get("/api/funnel")

    assert resp.status_code == 200
    assert resp.json()[0]["run_date"] == "2026-10-01"
