"""
Computes Sharpe ratio, max drawdown, alpha vs Nifty 500 and win rate per agent.
See Plan_v3 §Goals.

All returns are measured over the agent's NAV window (first to last row of daily_nav) so the
agent and the Nifty 500 are compared over exactly the same dates.
"""
import math
import sqlite3
from typing import Dict, List, Optional

from settings import settings


def load_nav_series(conn: sqlite3.Connection, agent_id: str) -> List[sqlite3.Row]:
    """Returns the agent's daily_nav rows ordered by date."""
    return conn.execute(
        "SELECT nav_date, cash_paise, invested_paise, total_paise, nifty500_close "
        "FROM daily_nav WHERE agent_id = ? ORDER BY nav_date",
        (agent_id,),
    ).fetchall()


def sharpe_ratio(totals: List[int]) -> Optional[float]:
    """Annualised Sharpe from daily NAV totals; None when fewer than 2 daily returns or zero variance."""
    rets = [totals[i] / totals[i - 1] - 1.0 for i in range(1, len(totals)) if totals[i - 1] > 0]
    if len(rets) < 2:
        return None
    rf_daily = settings.RISK_FREE_RATE_ANNUAL / settings.TRADING_DAYS_PER_YEAR
    excess = [r - rf_daily for r in rets]
    mean = sum(excess) / len(excess)
    var = sum((x - mean) ** 2 for x in excess) / (len(excess) - 1)
    if var <= 0:
        return None
    return round(mean / math.sqrt(var) * math.sqrt(settings.TRADING_DAYS_PER_YEAR), 4)


def max_drawdown_pct(totals: List[int]) -> Optional[float]:
    """Largest peak-to-trough fall as a negative percentage (0.0 when never below a prior peak)."""
    if not totals:
        return None
    peak, worst = totals[0], 0.0
    for t in totals:
        peak = max(peak, t)
        if peak > 0:
            worst = min(worst, t / peak - 1.0)
    return round(worst * 100, 4)


def trade_stats(conn: sqlite3.Connection, agent_id: str) -> Dict:
    """Closed-trade counts, win rate and open-position count from positions."""
    row = conn.execute(
        "SELECT SUM(status='CLOSED') AS closed, "
        "SUM(status='CLOSED' AND realized_pnl_paise > 0) AS wins, "
        "SUM(status='OPEN') AS open_n, COUNT(*) AS total "
        "FROM positions WHERE agent_id = ?",
        (agent_id,),
    ).fetchone()
    closed, wins = row["closed"] or 0, row["wins"] or 0
    return {
        "closed_trades": closed,
        "open_positions": row["open_n"] or 0,
        "total_trades": row["total"] or 0,
        "win_rate_pct": round(wins / closed * 100, 2) if closed else None,
    }


def faithfulness_rate(conn: sqlite3.Connection, agent_id: str) -> Optional[float]:
    """Mean faithfulness_score (0-1) across the agent's scored decisions."""
    row = conn.execute(
        "SELECT AVG(faithfulness_score) AS f FROM decisions "
        "WHERE agent_id = ? AND faithfulness_score IS NOT NULL",
        (agent_id,),
    ).fetchone()
    return round(row["f"], 4) if row["f"] is not None else None


def compute_agent_metrics(conn: sqlite3.Connection, agent_id: str) -> Dict:
    """Full leaderboard row for one agent, including a small-sample notice."""
    agent = conn.execute("SELECT * FROM agents WHERE id = ?", (agent_id,)).fetchone()
    if agent is None:
        raise KeyError(agent_id)
    nav = load_nav_series(conn, agent_id)
    totals = [r["total_paise"] for r in nav]
    stats = trade_stats(conn, agent_id)

    nav_paise = totals[-1] if totals else agent["cash_paise"]
    start = agent["starting_cash_paise"]
    return_pct = round((nav_paise / start - 1.0) * 100, 4) if start else None

    alpha = nifty_ret = window_ret = None
    if len(nav) >= 2 and totals[0] > 0 and nav[0]["nifty500_close"]:
        window_ret = (totals[-1] / totals[0] - 1.0) * 100
        nifty_ret = (nav[-1]["nifty500_close"] / nav[0]["nifty500_close"] - 1.0) * 100
        alpha = round(window_ret - nifty_ret, 4)

    reasons = []
    if len(nav) < settings.SMALL_SAMPLE_MIN_NAV_DAYS:
        reasons.append(f"{len(nav)} of {settings.SMALL_SAMPLE_MIN_NAV_DAYS} NAV days")
    if stats["closed_trades"] < settings.SMALL_SAMPLE_MIN_CLOSED_TRADES:
        reasons.append(f"{stats['closed_trades']} of {settings.SMALL_SAMPLE_MIN_CLOSED_TRADES} closed trades")

    return {
        "agent_id": agent_id,
        "name": agent["name"],
        "kind": agent["kind"],
        "is_active": bool(agent["is_active"]),
        "nav_paise": nav_paise,
        "starting_cash_paise": start,
        "return_pct": return_pct,
        "nifty_return_pct": round(nifty_ret, 4) if nifty_ret is not None else None,
        "alpha_pct": alpha,
        "sharpe": sharpe_ratio(totals),
        "max_drawdown_pct": max_drawdown_pct(totals),
        "faithfulness_rate": faithfulness_rate(conn, agent_id) if agent["kind"] == "LLM" else None,
        "nav_days": len(nav),
        "small_sample": bool(reasons),
        "small_sample_notice": ("Small sample, treat with caution (" + "; ".join(reasons) + ")") if reasons else None,
        **stats,
    }
