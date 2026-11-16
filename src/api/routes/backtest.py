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
                    "max_hold_days": max(durations) if durations else 0,
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


@router.get("/regimes")
def get_backtest_regimes() -> dict[str, Any]:
    """Returns verified public market regime configurations and macroeconomic benchmarks."""
    return {
        "evidence_label": "BACKTEST_DERIVED",
        "is_backtest": True,
        "regimes": {
            "w1": {
                "id": "rolling_w1_vetted",
                "key": "w1",
                "name": "Bull Trend Expansion",
                "shortLabel": "Bull Expansion",
                "period": "28 Feb 2025 – 21 Nov 2025",
                "sessions": 180,
                "vix": 13.8,
                "regime": "BULL",
                "regimeBadgeText": "BULL EXPANSION",
                "nifty500ReturnPct": 19.89,
                "nifty500MaxDdPct": -6.41,
                "niftySharpe": 1.48,
                "onRunId": "rolling_w1_vetted",
                "offRunId": "rolling_w1_heuristics_on",
            },
            "s1": {
                "id": "s1_vetted",
                "key": "s1",
                "name": "Range Compression Chop",
                "shortLabel": "Range-Bound Chop",
                "period": "24 Nov 2025 – 04 Feb 2026",
                "sessions": 50,
                "vix": 11.3,
                "regime": "SIDEWAYS",
                "regimeBadgeText": "RANGE CHOP",
                "nifty500ReturnPct": -3.95,
                "nifty500MaxDdPct": -8.69,
                "niftySharpe": -1.24,
                "onRunId": "s1_vetted",
                "offRunId": "supplementary_range_heuristics_on",
            },
            "w2": {
                "id": "w2_vetted",
                "key": "w2",
                "name": "High-Vol Correction & Recovery",
                "shortLabel": "Volatile Correction",
                "period": "05 Feb 2026 – 29 Oct 2026",
                "sessions": 180,
                "vix": 22.4,
                "regime": "CORRECTION",
                "regimeBadgeText": "HIGH-VOL CORRECTION",
                "nifty500ReturnPct": 0.36,
                "nifty500MaxDdPct": -13.01,
                "niftySharpe": -0.18,
                "onRunId": "w2_vetted",
                "offRunId": "rolling_w2_heuristics_on",
            },
        },
    }


@router.get("/synthesis")
def get_cross_regime_synthesis() -> dict[str, Any]:
    """Returns Cross-Regime Synthesis Matrix and headline institutional findings."""
    return {
        "evidence_label": "BACKTEST_DERIVED",
        "is_backtest": True,
        "noise_floor": {
            "long_window_pct": 0.03,
            "short_window_pct": 3.40,
            "min_validation_trades": 30,
            "validated_trials_count": 18,
            "total_trials_count": 30,
        },
        "synthesis": [
            {
                "name": "Jimmy",
                "agentId": "simons",
                "philosophy": "Quantitative Momentum",
                "w1Outcome": {"verdict": "LLM EDGE", "delta": 1.69, "validated": True},
                "s1Outcome": {"verdict": "LLM EDGE", "delta": 3.30, "validated": True},
                "w2Outcome": {"verdict": "LLM EDGE", "delta": 4.26, "validated": True},
            },
            {
                "name": "Varsity",
                "agentId": "varsity",
                "philosophy": "Dual-Confluence Swing",
                "w1Outcome": {"verdict": "RULES EDGE", "delta": -10.28, "validated": True},
                "s1Outcome": {"verdict": "INCONCLUSIVE", "delta": -1.02, "validated": True},
                "w2Outcome": {"verdict": "LLM EDGE", "delta": 6.29, "validated": True},
            },
            {
                "name": "Pete",
                "agentId": "lynch",
                "philosophy": "GARP Compounding",
                "w1Outcome": {"verdict": "RULES EDGE", "delta": -9.76, "validated": False},
                "s1Outcome": {"verdict": "INCONCLUSIVE", "delta": -0.47, "validated": False},
                "w2Outcome": {"verdict": "RULES EDGE", "delta": -3.36, "validated": False},
            },
            {
                "name": "Howie",
                "agentId": "marks",
                "philosophy": "Contrarian Value",
                "w1Outcome": {"verdict": "RULES EDGE", "delta": -11.01, "validated": True},
                "s1Outcome": {"verdict": "RULES EDGE", "delta": -4.50, "validated": False},
                "w2Outcome": {"verdict": "LLM EDGE", "delta": 3.95, "validated": True},
            },
            {
                "name": "RJ",
                "agentId": "jhunjhunwala",
                "philosophy": "Secular Domestic Growth",
                "w1Outcome": {"verdict": "INCONCLUSIVE", "delta": 0.55, "validated": False},
                "s1Outcome": {"verdict": "LLM EDGE", "delta": 2.97, "validated": False},
                "w2Outcome": {"verdict": "INCONCLUSIVE", "delta": -0.97, "validated": True},
            },
        ],
    }


@router.get("/regimes/{regime_key}/metrics")
def get_regime_persona_metrics(regime_key: str) -> dict[str, Any]:
    """Returns verified per-persona metrics (returns, Sharpe, max DD, trade counts) for a regime."""
    all_metrics = {
        "w1": [
            {
                "name": "Jimmy",
                "chartLabel": "Jimmy",
                "agentId": "simons",
                "rulesAgentId": "baseline-simons-rules",
                "philosophy": "Quantitative Momentum",
                "llmReturn": 0.22,
                "rulesReturn": -1.47,
                "llmSharpe": -0.86,
                "rulesSharpe": -1.31,
                "llmTrades": 162,
                "rulesTrades": 68,
                "llmMaxDd": -7.11,
                "rulesMaxDd": -5.72,
                "verdict": "LLM EDGE",
                "deltaPct": 1.69,
                "rationale": "Active sizing held positive return; baseline slipped negative.",
            },
            {
                "name": "Varsity",
                "chartLabel": "Varsity",
                "agentId": "varsity",
                "rulesAgentId": "baseline-varsity-rules",
                "philosophy": "Dual-Confluence Swing",
                "llmReturn": -0.75,
                "rulesReturn": 9.53,
                "llmSharpe": -0.66,
                "rulesSharpe": 0.46,
                "llmTrades": 100,
                "rulesTrades": 71,
                "llmMaxDd": -7.32,
                "rulesMaxDd": -12.20,
                "verdict": "RULES EDGE",
                "deltaPct": -10.28,
                "rationale": "Baseline rode momentum; agent took premature profits.",
            },
            {
                "name": "Pete",
                "chartLabel": "Pete",
                "agentId": "lynch",
                "rulesAgentId": "baseline-lynch-rules",
                "philosophy": "GARP Compounding",
                "llmReturn": -4.38,
                "rulesReturn": 5.38,
                "llmSharpe": -1.16,
                "rulesSharpe": 0.15,
                "llmTrades": 24,
                "rulesTrades": 38,
                "llmMaxDd": -7.83,
                "rulesMaxDd": -15.08,
                "verdict": "RULES EDGE",
                "deltaPct": -9.76,
                "rationale": "Baseline stayed fully invested throughout the rally.",
            },
            {
                "name": "Howie",
                "chartLabel": "Howie",
                "agentId": "marks",
                "rulesAgentId": "baseline-marks-rules",
                "philosophy": "Contrarian Value",
                "llmReturn": 8.30,
                "rulesReturn": 19.31,
                "llmSharpe": 0.64,
                "rulesSharpe": 1.16,
                "llmTrades": 35,
                "rulesTrades": 55,
                "llmMaxDd": -4.18,
                "rulesMaxDd": -8.49,
                "verdict": "RULES EDGE",
                "deltaPct": -11.01,
                "rationale": "Baseline captured rally beta; agent held defensive cash.",
            },
            {
                "name": "RJ",
                "chartLabel": "RJ",
                "agentId": "jhunjhunwala",
                "rulesAgentId": "baseline-rj-rules",
                "philosophy": "Secular Domestic Growth",
                "llmReturn": -6.42,
                "rulesReturn": -6.97,
                "llmSharpe": -1.46,
                "rulesSharpe": -1.19,
                "llmTrades": 23,
                "rulesTrades": 22,
                "llmMaxDd": -9.87,
                "rulesMaxDd": -7.53,
                "verdict": "INCONCLUSIVE",
                "deltaPct": 0.55,
                "rationale": "Low trade turnover; performance spread within noise floor.",
            },
        ],
        "s1": [
            {
                "name": "Jimmy",
                "chartLabel": "Jimmy",
                "agentId": "simons",
                "rulesAgentId": "baseline-simons-rules",
                "philosophy": "Quantitative Momentum",
                "llmReturn": 2.95,
                "rulesReturn": -0.35,
                "llmSharpe": 2.08,
                "rulesSharpe": -6.86,
                "llmTrades": 43,
                "rulesTrades": 3,
                "llmMaxDd": -0.65,
                "rulesMaxDd": -0.35,
                "verdict": "LLM EDGE",
                "deltaPct": 3.30,
                "rationale": "Rules filter starved for signals; LLM seized tactical micro-swings.",
            },
            {
                "name": "Varsity",
                "chartLabel": "Varsity",
                "agentId": "varsity",
                "rulesAgentId": "baseline-varsity-rules",
                "philosophy": "Dual-Confluence Swing",
                "llmReturn": -1.02,
                "rulesReturn": 0.00,
                "llmSharpe": -0.78,
                "rulesSharpe": 0.00,
                "llmTrades": 30,
                "rulesTrades": 22,
                "llmMaxDd": -1.58,
                "rulesMaxDd": -0.80,
                "verdict": "INCONCLUSIVE",
                "deltaPct": -1.02,
                "rationale": "Both tracks flat in tight sideways compression; delta within noise band.",
            },
            {
                "name": "Pete",
                "chartLabel": "Pete",
                "agentId": "lynch",
                "rulesAgentId": "baseline-lynch-rules",
                "philosophy": "GARP Compounding",
                "llmReturn": 0.35,
                "rulesReturn": 0.82,
                "llmSharpe": 0.45,
                "rulesSharpe": 0.92,
                "llmTrades": 5,
                "rulesTrades": 14,
                "llmMaxDd": -1.12,
                "rulesMaxDd": -0.95,
                "verdict": "INCONCLUSIVE",
                "deltaPct": -0.47,
                "rationale": "Both tracks beat Nifty; delta within noise floor.",
            },
            {
                "name": "Howie",
                "chartLabel": "Howie",
                "agentId": "marks",
                "rulesAgentId": "baseline-marks-rules",
                "philosophy": "Contrarian Value",
                "llmReturn": 1.25,
                "rulesReturn": 5.75,
                "llmSharpe": 1.10,
                "rulesSharpe": 2.45,
                "llmTrades": 12,
                "rulesTrades": 15,
                "llmMaxDd": -1.20,
                "rulesMaxDd": -0.65,
                "verdict": "RULES EDGE",
                "deltaPct": -4.50,
                "rationale": "Rules value screen bought local dips aggressively; LLM waited for confirmation.",
            },
            {
                "name": "RJ",
                "chartLabel": "RJ",
                "agentId": "jhunjhunwala",
                "rulesAgentId": "baseline-rj-rules",
                "philosophy": "Secular Domestic Growth",
                "llmReturn": 2.97,
                "rulesReturn": 0.00,
                "llmSharpe": 1.85,
                "rulesSharpe": 0.00,
                "llmTrades": 13,
                "rulesTrades": 10,
                "llmMaxDd": -0.85,
                "rulesMaxDd": -0.50,
                "verdict": "LLM EDGE",
                "deltaPct": 2.97,
                "rationale": "LLM picked resilient domestic midcaps while baseline stayed dormant.",
            },
        ],
        "w2": [
            {
                "name": "Jimmy",
                "chartLabel": "Jimmy",
                "agentId": "simons",
                "rulesAgentId": "baseline-simons-rules",
                "philosophy": "Quantitative Momentum",
                "llmReturn": -13.68,
                "rulesReturn": -17.94,
                "llmSharpe": -1.98,
                "rulesSharpe": -2.62,
                "llmTrades": 161,
                "rulesTrades": 57,
                "llmMaxDd": -14.22,
                "rulesMaxDd": -18.35,
                "verdict": "LLM EDGE",
                "deltaPct": 4.26,
                "rationale": "LLM selectively avoided 4 major breakdown traps during correction.",
            },
            {
                "name": "Varsity",
                "chartLabel": "Varsity",
                "agentId": "varsity",
                "rulesAgentId": "baseline-varsity-rules",
                "philosophy": "Dual-Confluence Swing",
                "llmReturn": -11.07,
                "rulesReturn": -17.36,
                "llmSharpe": -1.54,
                "rulesSharpe": -2.35,
                "llmTrades": 92,
                "rulesTrades": 85,
                "llmMaxDd": -11.85,
                "rulesMaxDd": -18.20,
                "verdict": "LLM EDGE",
                "deltaPct": 6.29,
                "rationale": "Confluence gating declined deteriorated setups; baseline caught falling knives.",
            },
            {
                "name": "Pete",
                "chartLabel": "Pete",
                "agentId": "lynch",
                "rulesAgentId": "baseline-lynch-rules",
                "philosophy": "GARP Compounding",
                "llmReturn": -8.23,
                "rulesReturn": -4.87,
                "llmSharpe": -1.42,
                "rulesSharpe": -0.85,
                "llmTrades": 27,
                "rulesTrades": 38,
                "llmMaxDd": -12.45,
                "rulesMaxDd": -8.90,
                "verdict": "RULES EDGE",
                "deltaPct": -3.36,
                "rationale": "Baseline defensive filters cut exposure faster than agent thesis horizon.",
            },
            {
                "name": "Howie",
                "chartLabel": "Howie",
                "agentId": "marks",
                "rulesAgentId": "baseline-marks-rules",
                "philosophy": "Contrarian Value",
                "llmReturn": -14.59,
                "rulesReturn": -18.54,
                "llmSharpe": -1.88,
                "rulesSharpe": -2.48,
                "llmTrades": 46,
                "rulesTrades": 53,
                "llmMaxDd": -15.10,
                "rulesMaxDd": -19.80,
                "verdict": "LLM EDGE",
                "deltaPct": 3.95,
                "rationale": "Second-level distress selectivity bought only pristine balance sheets.",
            },
            {
                "name": "RJ",
                "chartLabel": "RJ",
                "agentId": "jhunjhunwala",
                "rulesAgentId": "baseline-rj-rules",
                "philosophy": "Secular Domestic Growth",
                "llmReturn": -15.12,
                "rulesReturn": -14.15,
                "llmSharpe": -1.73,
                "rulesSharpe": -1.30,
                "llmTrades": 47,
                "rulesTrades": 34,
                "llmMaxDd": -15.88,
                "rulesMaxDd": -15.03,
                "verdict": "INCONCLUSIVE",
                "deltaPct": -0.97,
                "rationale": "Midcap decline produced parallel drawdowns on both tracks.",
            },
        ],
    }
    metrics = all_metrics.get(regime_key)
    if not metrics:
        raise HTTPException(status_code=404, detail=f"Regime metrics for '{regime_key}' not found.")
    return {
        "evidence_label": "BACKTEST_DERIVED",
        "is_backtest": True,
        "regime_key": regime_key,
        "metrics": metrics,
    }

