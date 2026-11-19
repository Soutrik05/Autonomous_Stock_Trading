"""
Tests for GET /api/agents/{id}/memory.
See docs/backend_implementation_guide_week5.md (Portfolio.tsx consumes /memory).
"""

import json
import sqlite3

import pytest

from ._api_test_helpers import NOW, build_file_db, clear_overrides, make_client, seed_agent


@pytest.fixture(autouse=True)
def _reset_overrides():
    yield
    clear_overrides()


def _insert_heuristic(
    db_path, agent_id="simons", kind="SEEK", status="active", context="ENTRY",
    confidence=0.6, times_triggered=10, times_successful=7,
    created_at="2026-10-01T10:00:00+05:30", updated_at="2026-10-20T10:00:00+05:30",
):
    conn = sqlite3.connect(db_path, isolation_level=None)
    cur = conn.execute(
        "INSERT INTO agent_memory (agent_id, kind, heuristic_text, trigger_json, prescribed_action, "
        "status, confidence, times_triggered, times_successful, context, created_at, updated_at) "
        "VALUES (?, ?, 'Seek volume breakouts above 2x average.', '{}', 'size up', ?, ?, ?, ?, ?, ?, ?)",
        (agent_id, kind, status, confidence, times_triggered, times_successful, context, created_at, updated_at),
    )
    heuristic_id = cur.lastrowid
    conn.close()
    return heuristic_id


def test_unknown_agent_returns_404(tmp_path):
    db_path = str(tmp_path / "portfolio.db")
    build_file_db(db_path)
    client = make_client(db_path)

    resp = client.get("/api/agents/nobody/memory")

    assert resp.status_code == 404


def test_no_heuristics_returns_200_with_empty_list(tmp_path):
    db_path = str(tmp_path / "portfolio.db")
    build_file_db(db_path)
    seed_agent(db_path, "simons", "Jim Simons", "Quant Momentum")
    client = make_client(db_path)

    resp = client.get("/api/agents/simons/memory")

    assert resp.status_code == 200
    assert resp.json() == []


def test_heuristic_fields_and_recent_success_rate(tmp_path):
    db_path = str(tmp_path / "portfolio.db")
    build_file_db(db_path)
    seed_agent(db_path, "simons", "Jim Simons", "Quant Momentum")
    heuristic_id = _insert_heuristic(db_path)

    conn = sqlite3.connect(db_path, isolation_level=None)
    for i, (outcome, resolved_on) in enumerate(
        (("SUCCESS", "2026-10-16"), ("SUCCESS", "2026-10-17"), ("FAILURE", "2026-10-18"))
    ):
        cur = conn.execute(
            "INSERT INTO decisions (run_date, agent_id, ticker, source, action, created_at) "
            "VALUES ('2026-10-15', 'simons', ?, 'LLM', 'BUY', ?)", (f"TICKER{i}", NOW),
        )
        decision_id = cur.lastrowid
        conn.execute(
            "INSERT INTO heuristic_applications (heuristic_id, decision_id, context, fired_on, "
            "horizon_days, outcome, resolved_on) VALUES (?, ?, 'ENTRY', '2026-10-15', 5, ?, ?)",
            (heuristic_id, decision_id, outcome, resolved_on),
        )
    conn.close()
    client = make_client(db_path)

    resp = client.get("/api/agents/simons/memory")

    assert resp.status_code == 200
    h = resp.json()[0]
    assert h["id"] == heuristic_id
    assert h["kind"] == "SEEK"
    assert h["status"] == "active"
    assert h["context"] == "ENTRY"
    assert h["confidence"] == 0.6
    assert h["applications"] == 10
    assert h["successes"] == 7
    assert h["recent_success_rate"] == pytest.approx(66.7, abs=0.1)  # 2/3
    assert h["created_at"] == "2026-10-01T10:00:00+05:30"
    assert h["lifecycle_reason"] is None  # no HEURISTIC_STATUS_CHANGED row logged


def test_status_filter(tmp_path):
    db_path = str(tmp_path / "portfolio.db")
    build_file_db(db_path)
    seed_agent(db_path, "simons", "Jim Simons", "Quant Momentum")
    _insert_heuristic(db_path, status="active")
    _insert_heuristic(db_path, status="deprecated")
    client = make_client(db_path)

    resp = client.get("/api/agents/simons/memory?status=deprecated")

    statuses = [h["status"] for h in resp.json()]
    assert statuses == ["deprecated"]


def test_lifecycle_reason_from_activity_log(tmp_path):
    db_path = str(tmp_path / "portfolio.db")
    build_file_db(db_path)
    seed_agent(db_path, "simons", "Jim Simons", "Quant Momentum")
    heuristic_id = _insert_heuristic(db_path, status="reinforced")

    conn = sqlite3.connect(db_path, isolation_level=None)
    conn.execute(
        "INSERT INTO activity_log (agent_id, event_type, description, metadata_json, created_at) "
        "VALUES ('simons', 'HEURISTIC_STATUS_CHANGED', 'promoted', ?, ?)",
        (json.dumps({"heuristic_id": heuristic_id, "reason": "promotion_epoch"}), NOW),
    )
    conn.close()
    client = make_client(db_path)

    resp = client.get("/api/agents/simons/memory")

    assert resp.json()[0]["lifecycle_reason"] == "promotion_epoch"
