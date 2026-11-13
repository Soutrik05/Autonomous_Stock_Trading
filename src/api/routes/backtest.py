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


def _pair_base_id(window_id: str) -> tuple[str, str | None]:
    """Splits a window_id like 'rolling_w2_heuristics_on' into ('rolling_w2', 'on'). A window_id
    with neither suffix pairs with nothing (its own base, heuristics_variant=None)."""
    for suffix, variant in (("_heuristics_on", "on"), ("_heuristics_off", "off")):
        if window_id.endswith(suffix):
            return window_id[: -len(suffix)], variant
    return window_id, None


@router.get("/runs")
def list_completed_runs() -> dict[str, Any]:
    """Lists all completed backtest run databases present in storage/backtest/, paired by
    window so the dashboard can show a heuristics-ON run next to its heuristics-OFF counterpart.
    A run with no counterpart on disk still appears, with the other side set to null."""
    BACKTEST_DIR.mkdir(parents=True, exist_ok=True)
    dbs = list(BACKTEST_DIR.glob("*.db"))
    pairs: dict[str, dict[str, Any]] = {}
    for db in dbs:
        win_id = db.stem
        conn = get_ro_conn(db)
        try:
            row = conn.execute(
                "SELECT MIN(nav_date) as start_d, MAX(nav_date) as end_d, COUNT(DISTINCT nav_date) as days FROM daily_nav"
            ).fetchone()
            trade_count = conn.execute("SELECT count(*) FROM positions WHERE status = 'CLOSED'").fetchone()[0]
            run_entry = {
                "window_id": win_id,
                "database_name": db.name,
                "start_date": row["start_d"] if row else None,
                "end_date": row["end_d"] if row else None,
                "sessions_completed": row["days"] if row else 0,
                "closed_trades": trade_count,
                "evidence_label": "BACKTEST_DERIVED",
                "is_backtest": True,
            }
        except Exception:
            continue
        finally:
            conn.close()

        base_id, variant = _pair_base_id(win_id)
        pair = pairs.setdefault(base_id, {"pair_id": base_id, "heuristics_on": None, "heuristics_off": None})
        if variant == "on":
            pair["heuristics_on"] = run_entry
        elif variant == "off":
            pair["heuristics_off"] = run_entry
        else:
            # Neither suffix -- not an on/off pair; surface it under heuristics_on by
            # convention so it's never silently dropped from the listing.
            pair["heuristics_on"] = run_entry

    return {
        "evidence_label": "BACKTEST_DERIVED",
        "is_backtest": True,
        "runs": sorted(pairs.values(), key=lambda p: p["pair_id"]),
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


@router.get("/runs/{window_id}/holding-duration")
def get_run_holding_duration(window_id: str) -> dict[str, Any]:
    """Question B evidence: per-persona average and median hold_days, and the closed-trade
    count they're computed from, for this backtest run."""
    db_path = _get_window_db(window_id)
    conn = get_ro_conn(db_path)
    try:
        rows = conn.execute(
            "SELECT agent_id, hold_days FROM positions "
            "WHERE status = 'CLOSED' AND hold_days IS NOT NULL ORDER BY agent_id"
        ).fetchall()

        by_agent: dict[str, list[int]] = {}
        for r in rows:
            by_agent.setdefault(r["agent_id"], []).append(r["hold_days"])

        personas = []
        for agent_id, durations in sorted(by_agent.items()):
            durations.sort()
            n = len(durations)
            mid = n // 2
            median = durations[mid] if n % 2 else (durations[mid - 1] + durations[mid]) / 2.0
            personas.append(
                {
                    "agent_id": agent_id,
                    "closed_trades": n,
                    "avg_hold_days": round(sum(durations) / n, 1),
                    "median_hold_days": median,
                }
            )

        return {
            "window_id": window_id,
            "evidence_label": "BACKTEST_DERIVED",
            "is_backtest": True,
            "personas": personas,
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
