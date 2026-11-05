"""
GET /api/activity: transparency feed (orders, fills, CAP_BREACH, FUNNEL_COUNTS, ...), newest first.
See Plan_v3 Part IV. Cursor pagination via before_id.
"""
import sqlite3
from typing import Optional

from fastapi import APIRouter, Depends, Query

from api.deps import AuthDep, Page, get_db, parse_json, rows

router = APIRouter(prefix="/api", tags=["activity"], dependencies=[AuthDep])


@router.get("/activity")
def activity(agent_id: Optional[str] = None, event_type: Optional[str] = None,
             before_id: Optional[int] = Query(None, ge=1),
             page: Page = Depends(), conn: sqlite3.Connection = Depends(get_db)):
    sql, args = "SELECT * FROM activity_log WHERE 1=1", []
    for col, val in (("agent_id", agent_id), ("event_type", event_type)):
        if val:
            sql, args = sql + f" AND {col} = ?", args + [val]
    if before_id:
        sql, args = sql + " AND id < ?", args + [before_id]
    out = rows(conn.execute(sql + " ORDER BY id DESC LIMIT ?", args + [page.limit]))
    for e in out:
        e["metadata"] = parse_json(e.pop("metadata_json"))
    return {"events": out, "next_before_id": out[-1]["id"] if len(out) == page.limit else None}
