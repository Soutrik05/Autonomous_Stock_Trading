"""
GET /api/leaderboard: NAV, return %, alpha, Sharpe, drawdown, win rate, faithfulness, small-sample
notice. GET /api/agents/nav: daily NAV series for every agent plus the Nifty 500 benchmark.
See Plan_v3 Part IV.
"""

import sqlite3
from typing import Optional

from fastapi import APIRouter, Depends

from api.deps import portfolio_conn
from api.schemas import LeaderboardEntry, NavPoint
from evaluation.performance import evaluate_all_agents

router = APIRouter(prefix="/api", tags=["leaderboard"])


def _badge(kind: str) -> str:
    return "RULES" if kind == "BASELINE" else "LLM"


def _foundation_model(conn: sqlite3.Connection, agent_id: str, kind: str) -> Optional[str]:
    if kind == "BASELINE":
        return None
    row = conn.execute(
        "SELECT model FROM llm_calls WHERE agent_id = ? ORDER BY id DESC LIMIT 1", (agent_id,)
    ).fetchone()
    return row["model"] if row else None


def _position_counts(conn: sqlite3.Connection, agent_id: str) -> tuple[int, int]:
    """Returns (total_positions, active_positions)."""
    row = conn.execute(
        "SELECT count(*) AS total, SUM(CASE WHEN status = 'OPEN' THEN 1 ELSE 0 END) AS active "
        "FROM positions WHERE agent_id = ?",
        (agent_id,),
    ).fetchone()
    return (row["total"] or 0, row["active"] or 0)


@router.get("/leaderboard", response_model=list[LeaderboardEntry])
def get_leaderboard(conn: sqlite3.Connection = Depends(portfolio_conn)) -> list[LeaderboardEntry]:
    agent_rows = {r["id"]: r for r in conn.execute("SELECT id, name, philosophy, kind, starting_cash_paise FROM agents").fetchall()}
    perf_list = evaluate_all_agents(conn, is_backtest=False)

    entries = []
    for perf in perf_list:
        agent_id = perf["agent_id"]
        a = agent_rows.get(agent_id)
        if a is None:
            continue
        total_positions, active_positions = _position_counts(conn, agent_id)
        entries.append(
            LeaderboardEntry(
                id=agent_id,
                name=a["name"],
                badge=_badge(a["kind"]),
                strategy_family=a["philosophy"],
                nav_paise=perf["current_nav_paise"],
                starting_capital_paise=a["starting_cash_paise"],
                return_pct=perf["total_return_pct"],
                alpha_vs_benchmark_pct=perf["alpha_pct"],
                sharpe_ratio=perf["sharpe_ratio"],
                max_drawdown_pct=perf["max_drawdown_pct"],
                win_rate_pct=perf["win_rate_pct"],
                faithfulness_rate_pct=round(perf["avg_faithfulness"] * 100.0, 1),
                total_trades=total_positions,
                closed_trades=perf["total_closed_trades"],
                active_positions_count=active_positions,
                is_provisional=perf["is_provisional"],
                sample_notice=perf["sample_notice"],
                foundation_model=_foundation_model(conn, agent_id, a["kind"]),
                evidence_label=perf["evidence_label"],
            )
        )
    return entries


@router.get("/agents/nav", response_model=list[NavPoint])
def get_agents_nav(conn: sqlite3.Connection = Depends(portfolio_conn)) -> list[NavPoint]:
    rows = conn.execute(
        "SELECT agent_id, nav_date, total_paise, nifty500_close FROM daily_nav ORDER BY nav_date ASC, agent_id ASC"
    ).fetchall()

    starting_cash_rows = conn.execute("SELECT id, starting_cash_paise FROM agents").fetchall()
    default_starting_cash = (
        starting_cash_rows[0]["starting_cash_paise"] if starting_cash_rows else 100_000_000
    )

    by_date: dict[str, dict[str, int]] = {}
    first_nifty_close: Optional[float] = None
    for r in rows:
        d = r["nav_date"]
        by_date.setdefault(d, {})
        by_date[d][r["agent_id"]] = r["total_paise"]
        if first_nifty_close is None and r["nifty500_close"]:
            first_nifty_close = r["nifty500_close"]
        if r["nifty500_close"] and first_nifty_close:
            by_date[d]["nifty500"] = round(default_starting_cash * (r["nifty500_close"] / first_nifty_close))

    return [NavPoint(date=d, values=vals) for d, vals in sorted(by_date.items())]
