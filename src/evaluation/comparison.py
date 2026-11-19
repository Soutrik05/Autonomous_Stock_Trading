"""
Paired comparison engine: LLM personas vs Rules baselines vs Nifty 500 benchmark,
and candidate selection alpha (BUY vs HOLD forward returns).
See Plan_v3 §Goals 2.
"""

import sqlite3
from typing import Any

from evaluation.performance import calculate_agent_performance


def compare_simons_vs_baseline(
    conn: sqlite3.Connection,
    is_backtest: bool = False,
) -> dict[str, Any]:
    """
    Compares LLM Simons directly against baseline-simons-rules and Nifty 500 benchmark.
    Both agents operate on the same candidate sets, broker rules, charges, and starting capital.
    """
    llm_simons = calculate_agent_performance(conn, "simons", is_backtest=is_backtest)
    rules_simons = calculate_agent_performance(conn, "baseline-simons-rules", is_backtest=is_backtest)

    return_delta = round(llm_simons["total_return_pct"] - rules_simons["total_return_pct"], 2)
    sharpe_delta = round(llm_simons["sharpe_ratio"] - rules_simons["sharpe_ratio"], 2)
    alpha_delta = round(llm_simons["alpha_pct"] - rules_simons["alpha_pct"], 2)
    win_rate_delta = round(llm_simons["win_rate_pct"] - rules_simons["win_rate_pct"], 1)

    return {
        "is_backtest": is_backtest,
        "evidence_label": "BACKTEST_DERIVED" if is_backtest else "LIVE_PILOT",
        "llm_simons": llm_simons,
        "rules_simons": rules_simons,
        "deltas": {
            "excess_return_pct": return_delta,
            "excess_sharpe": sharpe_delta,
            "excess_alpha_pct": alpha_delta,
            "excess_win_rate_pct": win_rate_delta,
        },
        "llm_adds_value": return_delta > 0,
    }


def compare_varsity_vs_baseline(
    conn: sqlite3.Connection,
    is_backtest: bool = False,
) -> dict[str, Any]:
    """
    Compares LLM Varsity directly against baseline-varsity-rules and Nifty 500 benchmark.
    Both agents operate on the same candidate sets, broker rules, charges, and starting capital.
    """
    llm_varsity = calculate_agent_performance(conn, "varsity", is_backtest=is_backtest)
    rules_varsity = calculate_agent_performance(conn, "baseline-varsity-rules", is_backtest=is_backtest)

    return_delta = round(llm_varsity["total_return_pct"] - rules_varsity["total_return_pct"], 2)
    sharpe_delta = round(llm_varsity["sharpe_ratio"] - rules_varsity["sharpe_ratio"], 2)
    alpha_delta = round(llm_varsity["alpha_pct"] - rules_varsity["alpha_pct"], 2)
    win_rate_delta = round(llm_varsity["win_rate_pct"] - rules_varsity["win_rate_pct"], 1)

    return {
        "is_backtest": is_backtest,
        "evidence_label": "BACKTEST_DERIVED" if is_backtest else "LIVE_PILOT",
        "llm_varsity": llm_varsity,
        "rules_varsity": rules_varsity,
        "deltas": {
            "excess_return_pct": return_delta,
            "excess_sharpe": sharpe_delta,
            "excess_alpha_pct": alpha_delta,
            "excess_win_rate_pct": win_rate_delta,
        },
        "llm_adds_value": return_delta > 0,
    }


def compare_lynch_vs_baseline(
    conn: sqlite3.Connection,
    is_backtest: bool = False,
) -> dict[str, Any]:
    """
    Compares LLM Lynch directly against baseline-lynch-rules and Nifty 500 benchmark.
    Both agents operate on the same candidate sets, broker rules, charges, and starting capital.
    """
    llm_lynch = calculate_agent_performance(conn, "lynch", is_backtest=is_backtest)
    rules_lynch = calculate_agent_performance(conn, "baseline-lynch-rules", is_backtest=is_backtest)

    return_delta = round(llm_lynch["total_return_pct"] - rules_lynch["total_return_pct"], 2)
    sharpe_delta = round(llm_lynch["sharpe_ratio"] - rules_lynch["sharpe_ratio"], 2)
    alpha_delta = round(llm_lynch["alpha_pct"] - rules_lynch["alpha_pct"], 2)
    win_rate_delta = round(llm_lynch["win_rate_pct"] - rules_lynch["win_rate_pct"], 1)

    return {
        "is_backtest": is_backtest,
        "evidence_label": "BACKTEST_DERIVED" if is_backtest else "LIVE_PILOT",
        "llm_lynch": llm_lynch,
        "rules_lynch": rules_lynch,
        "deltas": {
            "excess_return_pct": return_delta,
            "excess_sharpe": sharpe_delta,
            "excess_alpha_pct": alpha_delta,
            "excess_win_rate_pct": win_rate_delta,
        },
        "llm_adds_value": return_delta > 0,
    }


def compare_marks_vs_baseline(
    conn: sqlite3.Connection,
    is_backtest: bool = False,
) -> dict[str, Any]:
    """
    Compares LLM Marks directly against baseline-marks-rules and Nifty 500 benchmark.
    Both agents operate on the same candidate sets, broker rules, charges, and starting capital.
    """
    llm_marks = calculate_agent_performance(conn, "marks", is_backtest=is_backtest)
    rules_marks = calculate_agent_performance(conn, "baseline-marks-rules", is_backtest=is_backtest)

    return_delta = round(llm_marks["total_return_pct"] - rules_marks["total_return_pct"], 2)
    sharpe_delta = round(llm_marks["sharpe_ratio"] - rules_marks["sharpe_ratio"], 2)
    alpha_delta = round(llm_marks["alpha_pct"] - rules_marks["alpha_pct"], 2)
    win_rate_delta = round(llm_marks["win_rate_pct"] - rules_marks["win_rate_pct"], 1)

    return {
        "is_backtest": is_backtest,
        "evidence_label": "BACKTEST_DERIVED" if is_backtest else "LIVE_PILOT",
        "llm_marks": llm_marks,
        "rules_marks": rules_marks,
        "deltas": {
            "excess_return_pct": return_delta,
            "excess_sharpe": sharpe_delta,
            "excess_alpha_pct": alpha_delta,
            "excess_win_rate_pct": win_rate_delta,
        },
        "llm_adds_value": return_delta > 0,
    }


def compare_rj_vs_baseline(
    conn: sqlite3.Connection,
    is_backtest: bool = False,
) -> dict[str, Any]:
    """
    Compares LLM Jhunjhunwala directly against baseline-rj-rules and Nifty 500 benchmark.
    Both agents operate on the same candidate sets, broker rules, charges, and starting capital.
    """
    llm_rj = calculate_agent_performance(conn, "jhunjhunwala", is_backtest=is_backtest)
    rules_rj = calculate_agent_performance(conn, "baseline-rj-rules", is_backtest=is_backtest)

    return_delta = round(llm_rj["total_return_pct"] - rules_rj["total_return_pct"], 2)
    sharpe_delta = round(llm_rj["sharpe_ratio"] - rules_rj["sharpe_ratio"], 2)
    alpha_delta = round(llm_rj["alpha_pct"] - rules_rj["alpha_pct"], 2)
    win_rate_delta = round(llm_rj["win_rate_pct"] - rules_rj["win_rate_pct"], 1)

    return {
        "is_backtest": is_backtest,
        "evidence_label": "BACKTEST_DERIVED" if is_backtest else "LIVE_PILOT",
        "llm_rj": llm_rj,
        "rules_rj": rules_rj,
        "deltas": {
            "excess_return_pct": return_delta,
            "excess_sharpe": sharpe_delta,
            "excess_alpha_pct": alpha_delta,
            "excess_win_rate_pct": win_rate_delta,
        },
        "llm_adds_value": return_delta > 0,
    }


def compare_selection_alpha(
    conn: sqlite3.Connection,
    horizon_days: int = 5,
    agent_id: str | None = None,
) -> dict[str, Any]:
    """
    Calculates selection alpha: average forward return of BUY decisions vs HOLD / rejected
    decisions. Across all decisions by default, or restricted to one agent_id.
    Requires populated forward_returns table.
    """
    # forward_returns has no `id` column (its primary key is decision_id, horizon_days) and no
    # benchmark_return_pct/excess_return_pct columns -- the real columns are ret_pct and
    # nifty_ret_pct; excess is computed here rather than in SQL.
    query = """
    SELECT
        d.action,
        count(*) as sample_count,
        AVG(f.ret_pct) as avg_return_pct,
        AVG(f.nifty_ret_pct) as avg_benchmark_pct
    FROM decisions d
    JOIN forward_returns f ON d.id = f.decision_id
    WHERE f.horizon_days = ?
    """
    params: list = [horizon_days]
    if agent_id is not None:
        query += " AND d.agent_id = ?"
        params.append(agent_id)
    query += " GROUP BY d.action"
    rows = conn.execute(query, params).fetchall()

    buy_stats: dict[str, Any] = {"count": 0, "avg_return_pct": 0.0, "avg_benchmark_pct": 0.0, "avg_excess_pct": 0.0}
    hold_stats: dict[str, Any] = {"count": 0, "avg_return_pct": 0.0, "avg_benchmark_pct": 0.0, "avg_excess_pct": 0.0}

    for r in rows:
        act = r["action"]
        avg_return_pct = round(float(r["avg_return_pct"] or 0.0), 2)
        avg_benchmark_pct = round(float(r["avg_benchmark_pct"] or 0.0), 2)
        data = {
            "count": r["sample_count"],
            "avg_return_pct": avg_return_pct,
            "avg_benchmark_pct": avg_benchmark_pct,
            "avg_excess_pct": round(avg_return_pct - avg_benchmark_pct, 2),
        }
        if act == "BUY":
            buy_stats = data
        elif act in ("HOLD", "REJECT"):
            hold_stats = data

    selection_alpha = round(buy_stats["avg_return_pct"] - hold_stats["avg_return_pct"], 2)

    return {
        "horizon_days": horizon_days,
        "buy_decisions": buy_stats,
        "hold_decisions": hold_stats,
        "selection_alpha_pct": selection_alpha,
        "positive_selection": selection_alpha > 0,
    }
