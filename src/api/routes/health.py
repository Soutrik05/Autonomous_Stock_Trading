"""
GET /api/health: latest pipeline_runs status for each nightly/intraday job.
See Plan_v3 Part IV.
"""

import sqlite3

from fastapi import APIRouter, Depends

from api.deps import duration_seconds, portfolio_conn, to_ist_iso
from api.schemas import HealthJob, HealthResponse

router = APIRouter(prefix="/api", tags=["health"])

# Cadence is not stored anywhere (pipeline_runs only has one row per job/run_date, not its
# schedule) -- this is a static lookup of scheduler.py's actual cron registration, keyed by the
# JOB_NAME constants each module writes to pipeline_runs.job. A job name not in this map still
# appears (the job list itself always comes from the table), just with cadence=None.
_CADENCE = {
    "ingestion": "Daily 20:00 IST (Mon-Fri)",
    "features": "Daily 20:00 IST (Mon-Fri)",
    "watchlist": "Daily 20:00 IST (Mon-Fri)",
    "agents": "Daily 22:00 IST (Mon-Fri)",
    "expiry": "Daily 15:30 IST (Mon-Fri)",
    "settlement": "Daily 15:35 IST (Mon-Fri)",
    "heuristic_nightly": "Daily 22:30 IST (Mon-Fri)",
    "weekly_reflection": "Sunday 10:00 IST",
    "sync_fundamentals": "Periodic (fundamental refetch)",
}


@router.get("/health", response_model=HealthResponse)
def get_health(conn: sqlite3.Connection = Depends(portfolio_conn)) -> HealthResponse:
    try:
        rows = conn.execute(
            """
            SELECT job, run_date, status, started_at, finished_at, detail
            FROM pipeline_runs
            WHERE (job, run_date) IN (
                SELECT job, MAX(run_date) FROM pipeline_runs GROUP BY job
            )
            ORDER BY job ASC
            """
        ).fetchall()
        database_reachable = True
    except sqlite3.OperationalError:
        rows = []
        database_reachable = False

    jobs = [
        HealthJob(
            job_name=r["job"],
            cadence=_CADENCE.get(r["job"]),
            status=r["status"],
            last_run_at=to_ist_iso(r["finished_at"] or r["started_at"]),
            duration_sec=duration_seconds(r["started_at"], r["finished_at"]),
            records_processed=None,  # not recorded anywhere (pipeline_runs.detail is free text)
            error_message=r["detail"] if r["status"] == "FAILED" else None,
        )
        for r in rows
    ]
    return HealthResponse(database_reachable=database_reachable, jobs=jobs)
