"""
GET /api/agents/{id}/memory: heuristics (kind, trigger, status, confidence) and post-mortems.
See Plan_v3 Part IV.
"""
import sqlite3

from fastapi import APIRouter, Depends

from api.deps import AuthDep, Page, ensure_agent, get_db, parse_json, rows

router = APIRouter(prefix="/api/agents/{agent_id}", tags=["memory"], dependencies=[AuthDep])


@router.get("/memory")
def memory(agent_id: str, page: Page = Depends(), conn: sqlite3.Connection = Depends(get_db)):
    ensure_agent(conn, agent_id)
    heuristics = rows(conn.execute(
        "SELECT * FROM agent_memory WHERE agent_id = ? ORDER BY confidence DESC, id DESC", (agent_id,)))
    for h in heuristics:
        h["trigger"] = parse_json(h.pop("trigger_json"))
    post_mortems = rows(conn.execute(
        "SELECT id AS position_id, ticker, exit_date, exit_reason, realized_pnl_paise, realized_pnl_pct, "
        "hold_days, forensics_type, regime_at_exit, diagnosis_json FROM positions "
        "WHERE agent_id = ? AND status = 'CLOSED' AND (diagnosis_json IS NOT NULL OR forensics_type IS NOT NULL) "
        "ORDER BY exit_date DESC, id DESC LIMIT ? OFFSET ?", (agent_id, page.limit, page.offset)))
    for p in post_mortems:
        p["diagnosis"] = parse_json(p.pop("diagnosis_json"))
    return {"heuristics": heuristics, "post_mortems": post_mortems}
