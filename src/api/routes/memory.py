"""
GET /api/agents/{id}/memory: heuristics (kind, trigger, status, confidence) and post-mortems.
See Plan_v3 Part IV.
"""

import json
import sqlite3
from typing import Optional

from fastapi import APIRouter, Depends, Query

from api.deps import portfolio_conn, require_agent, to_ist_iso
from api.schemas import Heuristic
from core.config import settings

router = APIRouter(prefix="/api/agents", tags=["memory"])


def _recent_success_rate(conn: sqlite3.Connection, heuristic_id: int, window: int) -> Optional[float]:
    """Success rate over the most recent `window` resolved applications (fewer if that many
    don't exist yet). None if nothing has resolved at all."""
    rows = conn.execute(
        "SELECT outcome FROM heuristic_applications WHERE heuristic_id = ? "
        "AND outcome IN ('SUCCESS', 'FAILURE') ORDER BY resolved_on DESC, id DESC LIMIT ?",
        (heuristic_id, window),
    ).fetchall()
    if not rows:
        return None
    successes = sum(1 for r in rows if r["outcome"] == "SUCCESS")
    return round(successes / len(rows) * 100.0, 1)


def _lifecycle_reasons(conn: sqlite3.Connection, agent_id: str) -> dict[int, str]:
    """Latest HEURISTIC_STATUS_CHANGED reason per heuristic_id for this agent (the lifecycle
    reason is only ever recorded in activity_log.metadata_json, never on agent_memory itself --
    see learning/memory_manager.py::update_lifecycle)."""
    rows = conn.execute(
        "SELECT metadata_json FROM activity_log "
        "WHERE agent_id = ? AND event_type = 'HEURISTIC_STATUS_CHANGED' "
        "ORDER BY created_at DESC, id DESC",
        (agent_id,),
    ).fetchall()
    reasons: dict[int, str] = {}
    for r in rows:
        if not r["metadata_json"]:
            continue
        try:
            meta = json.loads(r["metadata_json"])
        except (json.JSONDecodeError, TypeError):
            continue
        hid = meta.get("heuristic_id")
        reason = meta.get("reason")
        if hid is not None and reason is not None and hid not in reasons:
            reasons[hid] = reason
    return reasons


@router.get("/{agent_id}/memory", response_model=list[Heuristic])
def get_agent_memory(
    agent_id: str,
    status: Optional[str] = Query(None, pattern="^(testing|active|reinforced|deprecated)$"),
    conn: sqlite3.Connection = Depends(portfolio_conn),
) -> list[Heuristic]:
    require_agent(conn, agent_id)

    query = (
        "SELECT id, agent_id, kind, heuristic_text, context, status, confidence, "
        "times_triggered, times_successful, created_at, updated_at "
        "FROM agent_memory WHERE agent_id = ?"
    )
    params: list = [agent_id]
    if status:
        query += " AND status = ?"
        params.append(status)
    query += " ORDER BY id DESC"

    rows = conn.execute(query, params).fetchall()
    reasons = _lifecycle_reasons(conn, agent_id)
    window = settings.HEURISTIC_ROLLING_WINDOW

    return [
        Heuristic(
            id=r["id"],
            agent_id=r["agent_id"],
            kind=r["kind"],
            rule_text=r["heuristic_text"],
            context=r["context"] if "context" in r.keys() and r["context"] else "ENTRY",
            status=r["status"],
            confidence=r["confidence"],
            applications=r["times_triggered"],
            successes=r["times_successful"],
            recent_success_rate=_recent_success_rate(conn, r["id"], window),
            created_at=to_ist_iso(r["created_at"]),
            updated_at=to_ist_iso(r["updated_at"]),
            lifecycle_reason=reasons.get(r["id"]),
        )
        for r in rows
    ]
