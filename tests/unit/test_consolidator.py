"""
Unit tests for Persona-Aligned Memory Consolidator (src/learning/consolidator.py).
"""

import json
import sqlite3
import pytest
from datetime import datetime, timezone

from core.clock import FakeClock
from learning.consolidator import (
    audit_persona_drift,
    detect_predicate_collisions,
    reconcile_active_vs_reinforced,
    consolidate_persona_memory,
    MAX_TOTAL_HEURISTICS_PER_PERSONA,
)


@pytest.fixture
def test_clock():
    return FakeClock(datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc))


@pytest.fixture
def memory_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE agent_memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_id TEXT NOT NULL,
            kind TEXT NOT NULL,
            context TEXT NOT NULL DEFAULT 'ENTRY',
            heuristic_text TEXT NOT NULL,
            trigger_json TEXT NOT NULL,
            prescribed_action TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'testing',
            confidence REAL NOT NULL DEFAULT 0.5,
            times_triggered INTEGER NOT NULL DEFAULT 0,
            times_successful INTEGER NOT NULL DEFAULT 0,
            last_fired_on TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            lifecycle_epoch_start TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            agent_id TEXT NOT NULL,
            activity_type TEXT NOT NULL,
            summary TEXT NOT NULL,
            details TEXT
        )
        """
    )
    return conn


def test_audit_persona_drift_simons():
    # Simons with valid technical rule
    valid_h = {
        "context": "ENTRY",
        "trigger_json": json.dumps({"feature": "rsi_14", "op": ">=", "value": 55}),
    }
    aligned, reason = audit_persona_drift(valid_h, "simons")
    assert aligned is True
    assert reason == ""

    # Simons with forbidden fundamental PE metric
    drift_h = {
        "context": "ENTRY",
        "trigger_json": json.dumps({"feature": "pe", "op": "<=", "value": 25}),
    }
    aligned, reason = audit_persona_drift(drift_h, "simons")
    assert aligned is False
    assert "PHILOSOPHY_DRIFT" in reason
    assert "forbidden metric" in reason or "forbidden group" in reason


def test_audit_persona_drift_lynch_fast_exit():
    # Lynch with valid PEG rule
    valid_h = {
        "context": "ENTRY",
        "trigger_json": json.dumps({"feature": "peg", "op": "<=", "value": 1.2}),
    }
    aligned, _ = audit_persona_drift(valid_h, "lynch")
    assert aligned is True

    # Lynch with fast RSI exit (forbidden for fundamental personas)
    drift_h = {
        "context": "EXIT",
        "trigger_json": json.dumps({"feature": "rsi_14", "op": ">=", "value": 75}),
    }
    aligned, reason = audit_persona_drift(drift_h, "lynch")
    assert aligned is False
    assert "PHILOSOPHY_DRIFT" in reason


def test_detect_predicate_collisions():
    h1 = {
        "kind": "SEEK",
        "context": "ENTRY",
        "trigger_json": json.dumps({"feature": "rsi_14", "op": ">=", "value": 60}),
    }
    h2 = {
        "kind": "AVOID",
        "context": "ENTRY",
        "trigger_json": json.dumps({"feature": "rsi_14", "op": ">=", "value": 65}),
    }
    assert detect_predicate_collisions(h1, h2) is True

    # Different context: ENTRY vs EXIT -> no collision
    h3 = {
        "kind": "AVOID",
        "context": "EXIT",
        "trigger_json": json.dumps({"feature": "rsi_14", "op": ">=", "value": 65}),
    }
    assert detect_predicate_collisions(h1, h3) is False


def test_reconcile_active_vs_reinforced(memory_db, test_clock):
    # Insert reinforced rule
    memory_db.execute(
        """
        INSERT INTO agent_memory (agent_id, kind, context, heuristic_text, trigger_json, prescribed_action, status, confidence, created_at, updated_at)
        VALUES ('simons', 'SEEK', 'ENTRY', 'Seek RSI breakout', '{"feature": "rsi_14", "op": ">=", "value": 60}', 'BUY', 'reinforced', 0.85, '2026-03-01T00:00:00Z', '2026-03-01T00:00:00Z')
        """
    )
    # Insert conflicting active rule
    memory_db.execute(
        """
        INSERT INTO agent_memory (agent_id, kind, context, heuristic_text, trigger_json, prescribed_action, status, confidence, created_at, updated_at)
        VALUES ('simons', 'AVOID', 'ENTRY', 'Avoid high RSI', '{"feature": "rsi_14", "op": ">=", "value": 65}', 'HOLD', 'active', 0.60, '2026-03-01T00:00:00Z', '2026-03-01T00:00:00Z')
        """
    )

    deprecated_ids = reconcile_active_vs_reinforced(memory_db, "simons", test_clock)
    assert len(deprecated_ids) == 1

    # Check status in DB
    status = memory_db.execute("SELECT status FROM agent_memory WHERE id = 2").fetchone()[0]
    assert status == "deprecated"


def test_consolidate_persona_memory_capacity_cap(memory_db, test_clock):
    # Insert 7 reinforced rules (exceeds cap of 5)
    for i in range(1, 8):
        trig = json.dumps({"feature": "adx_14", "op": ">=", "value": 20 + i})
        memory_db.execute(
            """
            INSERT INTO agent_memory (agent_id, kind, context, heuristic_text, trigger_json, prescribed_action, status, confidence, created_at, updated_at)
            VALUES ('simons', 'SEEK', 'ENTRY', ?, ?, 'BUY', 'reinforced', ?, '2026-03-01T00:00:00Z', '2026-03-01T00:00:00Z')
            """,
            (f"Rule {i}", trig, 0.50 + (i * 0.05)),
        )

    res = consolidate_persona_memory(memory_db, "simons", test_clock)
    assert res["status"] == "CONSOLIDATION_COMPLETE"
    assert res["final_count"] == MAX_TOTAL_HEURISTICS_PER_PERSONA
    assert len(res["pruned_reinforced"]) == 2  # 7 - 5 = 2 pruned
