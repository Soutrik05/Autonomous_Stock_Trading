"""
GET /api/activity: the transparency feed (fills, CAP_BREACH, FUNNEL_COUNTS, and other events).
See Plan_v3 Part IV.
"""

import sqlite3
from typing import Optional

from fastapi import APIRouter, Depends, Query

from api.deps import parse_metadata, portfolio_conn, severity_for_event, to_ist_iso
from api.schemas import ActivityEvent, ActivityResponse

router = APIRouter(prefix="/api", tags=["activity"])


@router.get("/activity", response_model=ActivityResponse)
def get_activity(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    agent_id: Optional[str] = None,
    event_type: Optional[str] = None,
    severity: Optional[str] = None,
    q: Optional[str] = None,
    conn: sqlite3.Connection = Depends(portfolio_conn),
) -> ActivityResponse:
    where = []
    params: list = []
    if agent_id:
        where.append("agent_id = ?")
        params.append(agent_id)
    if event_type:
        where.append("event_type = ?")
        params.append(event_type)
    if q:
        where.append("(description LIKE ? OR ticker LIKE ?)")
        params.extend([f"%{q}%", f"%{q}%"])
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""

    try:
        rows = conn.execute(
            f"""
            SELECT id, agent_id, event_type, ticker, description, metadata_json, created_at
            FROM activity_log
            {where_sql}
            ORDER BY created_at DESC, id DESC
            """,
            params,
        ).fetchall()
    except sqlite3.OperationalError:
        rows = []

    events = []
    for r in rows:
        row_severity = severity_for_event(r["event_type"], r["metadata_json"])
        if severity and row_severity != severity.upper():
            continue
        events.append(
            ActivityEvent(
                id=f"evt-{r['id']}",
                timestamp=to_ist_iso(r["created_at"]),
                event_type=r["event_type"],
                agent_id=r["agent_id"],
                symbol=r["ticker"],
                message=r["description"],
                severity=row_severity,
                details=parse_metadata(r["metadata_json"]),
            )
        )

    total = len(events)
    page = events[offset : offset + limit]
    return ActivityResponse(total=total, limit=limit, offset=offset, events=page)
