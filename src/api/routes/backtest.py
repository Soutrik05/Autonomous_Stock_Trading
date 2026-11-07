"""
FastAPI route handlers for historical walk-forward backtest results.
Exposes windows, runs, leaderboards, NAV curves, and Question B evaluation metrics.
All responses are permanently tagged with evidence_label='BACKTEST_DERIVED'.
See Plan_v3 Part IV.
"""

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

from api.deps import get_ro_conn
from backtest.config import get_curated_regime_windows, get_rolling_windows
from core.config import settings
from core.database import get_connection
from evaluation.comparison import compare_simons_vs_baseline
from evaluation.performance import evaluate_all_agents

router = APIRouter(prefix="/api/backtest", tags=["backtest"])

BACKTEST_DIR = Path(settings.BACKTEST_DB_DIR)


def _get_window_db(window_id: str) -> Path:
    # Reject anything that could escape BACKTEST_DIR (path separators or "..") -- window_id
    # comes straight from the URL path.
    if "/" in window_id or "\\" in window_id or ".." in window_id:
        raise HTTPException(status_code=400, detail="Invalid run id.")
    db_p = BACKTEST_DIR / f"{window_id}.db"
    if not db_p.exists():
        raise HTTPException(status_code=404, detail=f"Backtest run '{window_id}' not found on disk.")
    return db_p


@router.get("/windows")
def list_windows() -> dict[str, Any]:
    """Lists all available rolling and regime walk-forward windows."""
    ohlcv_conn = get_connection(settings.OHLCV_DB_PATH)
    try:
        rolling = get_rolling_windows(ohlcv_conn)
        curated = get_curated_regime_windows(ohlcv_conn)
        return {
            "evidence_label": "BACKTEST_DERIVED",
            "is_backtest": True,
            "disclaimer": "Historical walk-forward backtest definitions for Question B validation.",
            "total_windows": len(rolling),
            "rolling_windows": [w.__dict__ for w in rolling],
            "curated_regimes": [w.__dict__ for w in curated],
        }
    finally:
        ohlcv_conn.close()


@router.get("/runs")
def list_completed_runs() -> dict[str, Any]:
    """Lists all completed backtest run databases present in storage/backtest/."""
    BACKTEST_DIR.mkdir(parents=True, exist_ok=True)
    dbs = list(BACKTEST_DIR.glob("*.db"))
    runs = []
    for db in dbs:
        win_id = db.stem
        conn = get_ro_conn(db)
        try:
            # Query min/max nav dates and count
            row = conn.execute(
                "SELECT MIN(nav_date) as start_d, MAX(nav_date) as end_d, COUNT(DISTINCT nav_date) as days FROM daily_nav"
            ).fetchone()
            trade_count = conn.execute("SELECT count(*) FROM positions WHERE status = 'CLOSED'").fetchone()[0]
            runs.append(
                {
                    "window_id": win_id,
                    "database_name": db.name,
                    "start_date": row["start_d"] if row else None,
                    "end_date": row["end_d"] if row else None,
                    "sessions_completed": row["days"] if row else 0,
                    "closed_trades": trade_count,
                    "evidence_label": "BACKTEST_DERIVED",
                    "is_backtest": True,
                }
            )
        except Exception:
            continue
        finally:
            conn.close()

    return {
        "evidence_label": "BACKTEST_DERIVED",
        "is_backtest": True,
        "runs": runs,
    }


@router.get("/runs/{window_id}/leaderboard")
def get_run_leaderboard(window_id: str) -> dict[str, Any]:
    """Returns agent performance leaderboard for a specific backtest run."""
    db_path = _get_window_db(window_id)
    conn = get_ro_conn(db_path)
    try:
        perf = evaluate_all_agents(conn, is_backtest=True)
        return {
            "window_id": window_id,
            "evidence_label": "BACKTEST_DERIVED",
            "is_backtest": True,
            "disclaimer": "BACKTEST-DERIVED RESULTS — QUESTION B EVIDENCE ONLY (NOT LIVE PILOT EQUIVALENT)",
            "leaderboard": perf,
        }
    finally:
        conn.close()


@router.get("/runs/{window_id}/nav")
def get_run_nav_curves(window_id: str) -> dict[str, Any]:
    """Returns time-series daily NAV and benchmark curves for Recharts visualization."""
    db_path = _get_window_db(window_id)
    conn = get_ro_conn(db_path)
    try:
        rows = conn.execute(
            """
            SELECT agent_id, nav_date, total_paise, nifty500_close
            FROM daily_nav
            ORDER BY nav_date ASC, agent_id ASC
            """
        ).fetchall()

        # Reshape for multi-agent Recharts line chart: {date: "2026-...", simons: 1050000, marks: ...}
        # Values are integer paise (not rupees) -- money is integer paise in every response.
        dates_map: dict[str, dict[str, Any]] = {}
        for r in rows:
            d = r["nav_date"]
            if d not in dates_map:
                dates_map[d] = {"date": d, "nifty500": r["nifty500_close"]}
            dates_map[d][r["agent_id"]] = r["total_paise"]

        series = list(dates_map.values())
        series.sort(key=lambda x: x["date"])

        return {
            "window_id": window_id,
            "evidence_label": "BACKTEST_DERIVED",
            "is_backtest": True,
            "nav_series": series,
        }
    finally:
        conn.close()


@router.get("/runs/{window_id}/positions")
def get_run_positions(window_id: str, agent_id: str | None = None) -> dict[str, Any]:
    """Returns position records with holding days, PnL %, and forensics classifications."""
    db_path = _get_window_db(window_id)
    conn = get_ro_conn(db_path)
    try:
        query = """
        SELECT id, agent_id, ticker, sector, shares, avg_entry_price_paise, realized_pnl_paise,
               realized_pnl_pct, hold_days, exit_reason, status, forensics_type, entry_date, exit_date
        FROM positions
        """
        params = []
        if agent_id:
            query += " WHERE agent_id = ?"
            params.append(agent_id)
        query += " ORDER BY hold_days DESC, id DESC"

        rows = conn.execute(query, params).fetchall()
        positions = [
            {
                "id": r["id"],
                "agent_id": r["agent_id"],
                "ticker": r["ticker"],
                "sector": r["sector"],
                "shares": r["shares"],
                "avg_entry_price_paise": r["avg_entry_price_paise"],
                "realized_pnl_paise": r["realized_pnl_paise"],
                "realized_pnl_pct": r["realized_pnl_pct"],
                "hold_days": r["hold_days"] or 0,
                "exit_reason": r["exit_reason"],
                "status": r["status"],
                "forensics_type": r["forensics_type"],
                "opened_at": r["entry_date"],
                "closed_at": r["exit_date"],
            }
            for r in rows
        ]

        return {
            "window_id": window_id,
            "evidence_label": "BACKTEST_DERIVED",
            "is_backtest": True,
            "positions": positions,
        }
    finally:
        conn.close()


@router.get("/runs/{window_id}/comparison")
def get_run_comparison(window_id: str) -> dict[str, Any]:
    """Returns Simons vs Baseline comparison for this backtest run."""
    db_path = _get_window_db(window_id)
    conn = get_ro_conn(db_path)
    try:
        cmp = compare_simons_vs_baseline(conn, is_backtest=True)
        return cmp
    finally:
        conn.close()
