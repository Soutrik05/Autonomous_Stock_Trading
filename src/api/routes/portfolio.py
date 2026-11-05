"""
GET /api/agents/{id}/positions and /orders: open/closed positions and pending/past orders.
See Plan_v3 Part IV. Also serves /decisions and /nav for the same agent.
"""
import sqlite3
from typing import Optional

from fastapi import APIRouter, Depends, Query

from api.deps import AuthDep, Page, ensure_agent, get_db, parse_json, rows

router = APIRouter(prefix="/api/agents/{agent_id}", tags=["agent"], dependencies=[AuthDep])


@router.get("/positions")
def positions(agent_id: str, status: Optional[str] = Query(None, pattern="^(OPEN|CLOSED)$"),
              page: Page = Depends(), conn: sqlite3.Connection = Depends(get_db)):
    ensure_agent(conn, agent_id)
    sql, args = "SELECT * FROM positions WHERE agent_id = ?", [agent_id]
    if status:
        sql, args = sql + " AND status = ?", args + [status]
    sql += " ORDER BY entry_date DESC, id DESC LIMIT ? OFFSET ?"
    out = rows(conn.execute(sql, args + [page.limit, page.offset]))
    for p in out:
        p["diagnosis"] = parse_json(p.pop("diagnosis_json"))
        p["is_frozen"] = p["frozen_reason"] is not None
    return {"positions": out}


@router.get("/orders")
def orders(agent_id: str, status: Optional[str] = Query(
    None, pattern="^(pending|filled|expired|cancelled|crash_cancelled|rejected)$"),
    page: Page = Depends(), conn: sqlite3.Connection = Depends(get_db)):
    ensure_agent(conn, agent_id)
    sql, args = "SELECT * FROM pending_orders WHERE agent_id = ?", [agent_id]
    if status:
        sql, args = sql + " AND status = ?", args + [status]
    sql += " ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?"
    return {"orders": rows(conn.execute(sql, args + [page.limit, page.offset]))}


@router.get("/decisions")
def decisions(agent_id: str, run_date: Optional[str] = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
              action: Optional[str] = Query(None, pattern="^(BUY|SELL|HOLD|ADJUST)$"),
              page: Page = Depends(), conn: sqlite3.Connection = Depends(get_db)):
    ensure_agent(conn, agent_id)
    sql, args = "SELECT * FROM decisions WHERE agent_id = ?", [agent_id]
    if run_date:
        sql, args = sql + " AND run_date = ?", args + [run_date]
    if action:
        sql, args = sql + " AND action = ?", args + [action]
    sql += " ORDER BY run_date DESC, id DESC LIMIT ? OFFSET ?"
    out = rows(conn.execute(sql, args + [page.limit, page.offset]))
    for d in out:
        d["cited_metrics"] = parse_json(d.pop("cited_metrics_json"))
    return {"decisions": out}


@router.get("/nav")
def nav(agent_id: str, conn: sqlite3.Connection = Depends(get_db)):
    ensure_agent(conn, agent_id)
    return {"nav": rows(conn.execute(
        "SELECT nav_date, cash_paise, invested_paise, total_paise, nifty500_close "
        "FROM daily_nav WHERE agent_id = ? ORDER BY nav_date", (agent_id,)))}
