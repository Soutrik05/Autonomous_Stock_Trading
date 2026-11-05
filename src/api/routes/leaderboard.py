"""
GET /api/leaderboard: NAV, return %, alpha, Sharpe, drawdown, win rate, faithfulness and small-sample notice.
See Plan_v3 Part IV.
"""
import sqlite3

from fastapi import APIRouter, Depends

from api.deps import AuthDep, get_db, rows
from evaluation.performance import compute_agent_metrics

router = APIRouter(prefix="/api", tags=["leaderboard"], dependencies=[AuthDep])


@router.get("/leaderboard")
def leaderboard(conn: sqlite3.Connection = Depends(get_db)):
    ids = [r["id"] for r in conn.execute("SELECT id FROM agents ORDER BY id")]
    board = sorted((compute_agent_metrics(conn, i) for i in ids), key=lambda m: m["nav_paise"], reverse=True)
    return {"agents": board}


@router.get("/agents")
def agents(conn: sqlite3.Connection = Depends(get_db)):
    return {"agents": rows(conn.execute(
        "SELECT id, name, philosophy, kind, starting_cash_paise, cash_paise, started_on, is_active FROM agents ORDER BY id"))}
