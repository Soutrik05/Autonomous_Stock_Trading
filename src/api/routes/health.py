"""
GET /api/health: latest pipeline_runs status for each job. Public (used by ALB, uptime checks, dashboard).
See Plan_v3 Part IV.
"""
import sqlite3

from fastapi import APIRouter, Depends

from api.deps import get_db, rows

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
def health(conn: sqlite3.Connection = Depends(get_db)):
    jobs = rows(conn.execute(
        "SELECT job, run_date, status, started_at, finished_at, detail FROM pipeline_runs p "
        "WHERE id = (SELECT MAX(id) FROM pipeline_runs WHERE job = p.job) ORDER BY job"))
    last_nav = conn.execute("SELECT MAX(nav_date) AS d FROM daily_nav").fetchone()["d"]
    failed = [j["job"] for j in jobs if j["status"] == "FAILED"]
    return {"status": "degraded" if failed else "ok", "failed_jobs": failed, "latest_nav_date": last_nav, "jobs": jobs}
