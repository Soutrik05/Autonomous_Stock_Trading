"""
GET /api/funnel: each agent's latest watchlist funnel stage counts (Stage 0 -> Stage 1 -> ... ->
final), sourced from activity_log's FUNNEL_COUNTS events. Live DB only.
See Plan_v3 Part IV, docs/handin_week2.md (4-stage multi-agent watchlist funnel).
"""

import json
import sqlite3
from typing import Optional

from fastapi import APIRouter, Depends, Query

from api.deps import portfolio_conn, require_agent, to_ist_iso
from api.schemas import FunnelEntry, FunnelStage

router = APIRouter(prefix="/api", tags=["funnel"])


@router.get("/funnel", response_model=list[FunnelEntry])
def get_funnel(
    agent_id: Optional[str] = Query(None),
    conn: sqlite3.Connection = Depends(portfolio_conn),
) -> list[FunnelEntry]:
    if agent_id:
        require_agent(conn, agent_id)

    query = "SELECT agent_id, metadata_json, created_at FROM activity_log WHERE event_type = 'FUNNEL_COUNTS'"
    params: list = []
    if agent_id:
        query += " AND agent_id = ?"
        params.append(agent_id)
    query += " ORDER BY agent_id ASC, created_at DESC, id DESC"

    rows = conn.execute(query, params).fetchall()

    entries: list[FunnelEntry] = []
    seen_agents: set[str] = set()
    for r in rows:
        aid = r["agent_id"]
        if aid in seen_agents:
            continue  # a later (older) row for an agent we already have the latest of
        if not r["metadata_json"]:
            continue
        try:
            meta = json.loads(r["metadata_json"])
        except (json.JSONDecodeError, TypeError):
            continue  # bad metadata_json: skip this row, no 500 -- an older row may still work
        if not isinstance(meta, dict):
            continue

        seen_agents.add(aid)
        stages = [FunnelStage(key=k, count=v) for k, v in meta.items() if isinstance(v, int)]
        entries.append(
            FunnelEntry(
                agent_id=aid,
                run_date=(to_ist_iso(r["created_at"]) or "")[:10],
                stages=stages,
            )
        )

    return entries
