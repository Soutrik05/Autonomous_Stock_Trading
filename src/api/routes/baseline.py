"""
GET /api/baseline/comparison: LLM Simons vs rules Simons vs Nifty 500, plus forward-return comparison.
See Plan_v3 Part IV.
"""

import sqlite3
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from api.deps import portfolio_conn
from api.schemas import BaselineAgentStats, BaselineComparison, HorizonReturn
from evaluation.comparison import (
    compare_lynch_vs_baseline,
    compare_marks_vs_baseline,
    compare_rj_vs_baseline,
    compare_selection_alpha,
    compare_simons_vs_baseline,
    compare_varsity_vs_baseline,
)

router = APIRouter(prefix="/api/baseline", tags=["baseline"])

_HORIZONS = [1, 5, 10, 20, 60]

# persona_id -> (compare_*_vs_baseline function, llm agent_id, rules agent_id, result dict keys)
_PERSONAS: dict[str, dict] = {
    "simons": {"fn": compare_simons_vs_baseline, "llm_id": "simons", "rules_id": "baseline-simons-rules", "llm_key": "llm_simons", "rules_key": "rules_simons"},
    "lynch": {"fn": compare_lynch_vs_baseline, "llm_id": "lynch", "rules_id": "baseline-lynch-rules", "llm_key": "llm_lynch", "rules_key": "rules_lynch"},
    "marks": {"fn": compare_marks_vs_baseline, "llm_id": "marks", "rules_id": "baseline-marks-rules", "llm_key": "llm_marks", "rules_key": "rules_marks"},
    "jhunjhunwala": {"fn": compare_rj_vs_baseline, "llm_id": "jhunjhunwala", "rules_id": "baseline-rj-rules", "llm_key": "llm_rj", "rules_key": "rules_rj"},
    "varsity": {"fn": compare_varsity_vs_baseline, "llm_id": "varsity", "rules_id": "baseline-varsity-rules", "llm_key": "llm_varsity", "rules_key": "rules_varsity"},
}


def _agent_stats(perf: dict) -> BaselineAgentStats:
    return BaselineAgentStats(
        return_pct=perf["total_return_pct"],
        sharpe_ratio=perf["sharpe_ratio"],
        win_rate_pct=perf["win_rate_pct"],
        max_drawdown_pct=perf["max_drawdown_pct"],
        trades=perf["total_closed_trades"],
    )


def _horizon_return(conn: sqlite3.Connection, horizon_days: int, llm_id: str, rules_id: str) -> HorizonReturn:
    llm = compare_selection_alpha(conn, horizon_days=horizon_days, agent_id=llm_id)
    rules = compare_selection_alpha(conn, horizon_days=horizon_days, agent_id=rules_id)

    llm_buy = llm["buy_decisions"]
    llm_hold = llm["hold_decisions"]
    rules_buy = rules["buy_decisions"]

    # "no data" must mean null, never 0 -- a zero count means the dict is still the all-zero
    # default from compare_selection_alpha, not a real zero return.
    llm_buy_avg = llm_buy["avg_return_pct"] if llm_buy["count"] else None
    llm_hold_avg = llm_hold["avg_return_pct"] if llm_hold["count"] else None
    rules_buy_avg = rules_buy["avg_return_pct"] if rules_buy["count"] else None
    nifty500_avg = llm_buy["avg_benchmark_pct"] if llm_buy["count"] else None
    selection_alpha = (
        round(llm_buy_avg - llm_hold_avg, 2) if llm_buy_avg is not None and llm_hold_avg is not None else None
    )

    return HorizonReturn(
        horizon_days=horizon_days,
        llm_buy_avg_pct=llm_buy_avg,
        llm_hold_avg_pct=llm_hold_avg,
        rules_buy_avg_pct=rules_buy_avg,
        nifty500_avg_pct=nifty500_avg,
        selection_alpha_pct=selection_alpha,
        llm_buy_count=llm_buy["count"] or None,
        rules_buy_count=rules_buy["count"] or None,
    )


@router.get("/comparison", response_model=BaselineComparison)
def get_baseline_comparison(
    persona: str = Query("simons"),
    conn: sqlite3.Connection = Depends(portfolio_conn),
) -> BaselineComparison:
    meta = _PERSONAS.get(persona)
    if meta is None:
        raise HTTPException(
            status_code=422,
            detail=f"persona must be one of {sorted(_PERSONAS)}, got {persona!r}.",
        )

    result = meta["fn"](conn, is_backtest=False)
    llm_perf = result[meta["llm_key"]]
    rules_perf = result[meta["rules_key"]]

    horizon_returns = [_horizon_return(conn, h, meta["llm_id"], meta["rules_id"]) for h in _HORIZONS]

    return BaselineComparison(
        persona_id=persona,
        llm_agent=_agent_stats(llm_perf),
        rules_agent=_agent_stats(rules_perf),
        deltas=result["deltas"],
        is_provisional=llm_perf["is_provisional"],
        sample_notice=llm_perf["sample_notice"],
        evidence_label=result["evidence_label"],
        horizon_returns=horizon_returns,
    )
