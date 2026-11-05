"""
Builds the LLM-vs-baseline-vs-Nifty 500 comparison used by the API and report.
See Plan_v3 §Goals 2.
"""
import sqlite3
from typing import Dict, List

from evaluation.performance import load_nav_series
from settings import settings


def _indexed_curves(conn: sqlite3.Connection, llm_id: str, base_id: str) -> List[Dict]:
    """NAV for both agents and the Nifty 500, each rebased to 100 on the first shared date."""
    llm = {r["nav_date"]: r for r in load_nav_series(conn, llm_id)}
    base = {r["nav_date"]: r for r in load_nav_series(conn, base_id)}
    dates = sorted(set(llm) & set(base))
    if not dates:
        return []
    l0, b0, n0 = llm[dates[0]]["total_paise"], base[dates[0]]["total_paise"], llm[dates[0]]["nifty500_close"]
    return [
        {
            "date": d,
            "llm": round(llm[d]["total_paise"] / l0 * 100, 4),
            "baseline": round(base[d]["total_paise"] / b0 * 100, 4),
            "nifty500": round(llm[d]["nifty500_close"] / n0 * 100, 4) if n0 else None,
        }
        for d in dates
    ]


def _forward_stats(conn: sqlite3.Connection, agent_id: str) -> List[Dict]:
    """Per-horizon mean return, Nifty return and excess for all of an agent's decisions."""
    rows = conn.execute(
        "SELECT fr.horizon_days AS h, COUNT(*) AS n, AVG(fr.ret_pct) AS ret, AVG(fr.nifty_ret_pct) AS nifty "
        "FROM forward_returns fr JOIN decisions d ON d.id = fr.decision_id "
        "WHERE d.agent_id = ? GROUP BY fr.horizon_days ORDER BY fr.horizon_days",
        (agent_id,),
    ).fetchall()
    return [
        {"horizon_days": r["h"], "n": r["n"], "mean_ret_pct": round(r["ret"], 4),
         "mean_nifty_ret_pct": round(r["nifty"], 4), "mean_excess_pct": round(r["ret"] - r["nifty"], 4)}
        for r in rows
    ]


def _paired_deltas(conn: sqlite3.Connection, llm_id: str, base_id: str) -> List[Dict]:
    """Mean (LLM - baseline) forward return on the same ticker and date, per horizon."""
    rows = conn.execute(
        "SELECT a.horizon_days AS h, COUNT(*) AS n, AVG(a.ret_pct - b.ret_pct) AS delta "
        "FROM (SELECT d.ticker, d.run_date, fr.horizon_days, fr.ret_pct FROM forward_returns fr "
        "      JOIN decisions d ON d.id = fr.decision_id WHERE d.agent_id = ?) a "
        "JOIN (SELECT d.ticker, d.run_date, fr.horizon_days, fr.ret_pct FROM forward_returns fr "
        "      JOIN decisions d ON d.id = fr.decision_id WHERE d.agent_id = ?) b "
        "ON a.ticker = b.ticker AND a.run_date = b.run_date AND a.horizon_days = b.horizon_days "
        "GROUP BY a.horizon_days ORDER BY a.horizon_days",
        (llm_id, base_id),
    ).fetchall()
    return [{"horizon_days": r["h"], "paired_n": r["n"], "mean_llm_minus_baseline_pct": round(r["delta"], 4)} for r in rows]


def build_comparison(conn: sqlite3.Connection) -> Dict:
    """LLM Simons vs rules Simons vs Nifty 500: indexed curves, forward returns and paired deltas."""
    llm_id, base_id = settings.COMPARISON_LLM_AGENT_ID, settings.COMPARISON_BASELINE_AGENT_ID
    curves = _indexed_curves(conn, llm_id, base_id)
    return {
        "llm_agent_id": llm_id,
        "baseline_agent_id": base_id,
        "curves": curves,
        "forward_returns": {llm_id: _forward_stats(conn, llm_id), base_id: _forward_stats(conn, base_id)},
        "paired_deltas": _paired_deltas(conn, llm_id, base_id),
        "small_sample": len(curves) < settings.SMALL_SAMPLE_MIN_NAV_DAYS,
    }
