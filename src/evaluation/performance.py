"""
Performance evaluation module: Sharpe ratio, maximum drawdown, alpha vs Nifty 500, win rate,
profit factor, and small-sample flagging.
See Plan_v3 §Goals, §Roadmap Week 3.
"""

import math
import sqlite3
from typing import Any

from core.config import settings
from core.money import paise_to_rupees
from evaluation.philosophy import evaluate_agent_philosophy_adherence


def calculate_sharpe_ratio(
    daily_returns: list[float],
    risk_free_annual_rate: float = 0.06,
    trading_days_per_year: int = 252,
) -> float:
    """
    Computes annualized Sharpe ratio from daily fractional returns.
    rf_daily = (1 + rf_annual)**(1/252) - 1.
    """
    if not daily_returns or len(daily_returns) < 5:
        return 0.0

    rf_daily = (1.0 + risk_free_annual_rate) ** (1.0 / trading_days_per_year) - 1.0
    excess_returns = [r - rf_daily for r in daily_returns]

    n = len(excess_returns)
    mean_excess = sum(excess_returns) / n
    variance = sum((r - mean_excess) ** 2 for r in excess_returns) / (n - 1) if n > 1 else 0.0
    std_dev = math.sqrt(variance)

    if std_dev < 1e-8:
        return 0.0

    return (mean_excess / std_dev) * math.sqrt(trading_days_per_year)


def calculate_sortino_ratio(
    daily_returns: list[float],
    risk_free_annual_rate: float = 0.06,
    trading_days_per_year: int = 252,
) -> float:
    """
    Computes annualized Sortino ratio from daily fractional returns.
    Downside deviation penalizes only returns falling below the risk-free rate.
    """
    if not daily_returns or len(daily_returns) < 5:
        return 0.0

    rf_daily = (1.0 + risk_free_annual_rate) ** (1.0 / trading_days_per_year) - 1.0
    excess_returns = [r - rf_daily for r in daily_returns]

    n = len(excess_returns)
    mean_excess = sum(excess_returns) / n
    downside_squared = [min(0.0, r) ** 2 for r in excess_returns]
    downside_variance = sum(downside_squared) / (n - 1) if n > 1 else 0.0
    downside_dev = math.sqrt(downside_variance)

    if downside_dev < 1e-8:
        return 999.0 if mean_excess > 0 else 0.0

    return (mean_excess / downside_dev) * math.sqrt(trading_days_per_year)


def calculate_max_drawdown(nav_values: list[int]) -> float:
    """
    Computes maximum percentage drawdown from a series of NAV values (in paise or float).
    Returns a non-positive percentage (e.g. -12.4 for a 12.4% drop).
    """
    if not nav_values or len(nav_values) < 2:
        return 0.0

    peak = nav_values[0]
    max_dd_pct = 0.0

    for val in nav_values:
        if val > peak:
            peak = val
        if peak > 0:
            dd_pct = ((val - peak) / peak) * 100.0
            if dd_pct < max_dd_pct:
                max_dd_pct = dd_pct

    return round(max_dd_pct, 2)


def calculate_agent_performance(
    conn: sqlite3.Connection,
    agent_id: str,
    is_backtest: bool = False,
    provisional_min_trades: int = 30,
) -> dict[str, Any]:
    """
    Calculates full quantitative performance summary for an agent from daily_nav and positions.
    """
    # 1. Query daily NAV series
    nav_rows = conn.execute(
        """
        SELECT nav_date, cash_paise, invested_paise, total_paise, nifty500_close
        FROM daily_nav
        WHERE agent_id = ?
        ORDER BY nav_date ASC
        """,
        (agent_id,),
    ).fetchall()

    initial_nav = settings.INITIAL_CASH_PER_AGENT_PAISE
    current_nav = initial_nav
    try:
        agent_row = conn.execute(
            "SELECT starting_cash_paise, cash_paise FROM agents WHERE id = ?", (agent_id,)
        ).fetchone()
        if agent_row:
            if "starting_cash_paise" in agent_row.keys() and agent_row["starting_cash_paise"]:
                initial_nav = agent_row["starting_cash_paise"]
            if "cash_paise" in agent_row.keys() and agent_row["cash_paise"]:
                current_nav = agent_row["cash_paise"]
            else:
                current_nav = initial_nav
    except sqlite3.OperationalError:
        pass
    total_return_pct = 0.0
    benchmark_return_pct = 0.0
    alpha_pct = 0.0
    sharpe_ratio = 0.0
    sortino_ratio = 0.0
    max_drawdown_pct = 0.0
    calmar_ratio = 0.0
    avg_invested_pct = 0.0
    max_invested_pct = 0.0
    cash_drag_pct = 100.0

    if nav_rows:
        first_nav = nav_rows[0]["total_paise"]
        initial_nav = first_nav if first_nav > 0 else initial_nav
        current_nav = nav_rows[-1]["total_paise"]
        total_return_pct = ((current_nav - initial_nav) / initial_nav) * 100.0

        # Benchmark return
        b_first = nav_rows[0]["nifty500_close"]
        b_last = nav_rows[-1]["nifty500_close"]
        if b_first and b_first > 0:
            benchmark_return_pct = ((b_last - b_first) / b_first) * 100.0
        alpha_pct = total_return_pct - benchmark_return_pct

        # Daily returns for Sharpe and Sortino
        totals = [r["total_paise"] for r in nav_rows]
        daily_returns = []
        for i in range(1, len(totals)):
            prev = totals[i - 1]
            if prev > 0:
                daily_returns.append((totals[i] - prev) / float(prev))

        sharpe_ratio = calculate_sharpe_ratio(daily_returns)
        sortino_ratio = calculate_sortino_ratio(daily_returns)
        max_drawdown_pct = calculate_max_drawdown(totals)
        calmar_ratio = round(total_return_pct / abs(max_drawdown_pct), 2) if max_drawdown_pct < 0 else 0.0

        # Capital exposure / Cash drag telemetry
        invested_series = [
            r["invested_paise"] / float(r["total_paise"]) * 100.0 for r in nav_rows if r["total_paise"] > 0
        ]
        avg_invested_pct = round(sum(invested_series) / len(invested_series), 1) if invested_series else 0.0
        max_invested_pct = round(max(invested_series), 1) if invested_series else 0.0
        cash_drag_pct = round(100.0 - avg_invested_pct, 1)

    # 2. Query closed positions for trade statistics
    closed_pos = conn.execute(
        """
        SELECT id, ticker, shares, avg_entry_price_paise, realized_pnl_paise, realized_pnl_pct, hold_days, exit_reason
        FROM positions
        WHERE agent_id = ? AND status = 'CLOSED'
        ORDER BY id ASC
        """,
        (agent_id,),
    ).fetchall()

    total_closed_trades = len(closed_pos)
    winning_trades = [p for p in closed_pos if (p["realized_pnl_paise"] or 0) > 0]
    losing_trades = [p for p in closed_pos if (p["realized_pnl_paise"] or 0) < 0]

    win_count = len(winning_trades)
    win_rate_pct = (win_count / total_closed_trades * 100.0) if total_closed_trades > 0 else 0.0

    gross_profit_paise = sum(p["realized_pnl_paise"] for p in winning_trades)
    gross_loss_paise = abs(sum(p["realized_pnl_paise"] for p in losing_trades))
    profit_factor = (
        round(gross_profit_paise / gross_loss_paise, 2)
        if gross_loss_paise > 0
        else (999.0 if gross_profit_paise > 0 else 0.0)
    )

    win_pnls = [p["realized_pnl_pct"] for p in winning_trades if p["realized_pnl_pct"] is not None]
    loss_pnls = [p["realized_pnl_pct"] for p in losing_trades if p["realized_pnl_pct"] is not None]

    avg_win_pct = round(sum(win_pnls) / len(win_pnls), 2) if win_pnls else 0.0
    avg_loss_pct = round(sum(loss_pnls) / len(loss_pnls), 2) if loss_pnls else 0.0
    payoff_ratio = (
        round(avg_win_pct / abs(avg_loss_pct), 2) if avg_loss_pct != 0 else (999.0 if avg_win_pct > 0 else 0.0)
    )
    loss_rate_pct = 100.0 - win_rate_pct
    expectancy_pct = round(((win_rate_pct / 100.0) * avg_win_pct) + ((loss_rate_pct / 100.0) * avg_loss_pct), 2)

    avg_hold_days = (
        sum(p["hold_days"] or 0 for p in closed_pos) / total_closed_trades if total_closed_trades > 0 else 0.0
    )

    # 3. Decision Faithfulness & Data Provenance (PIT Fairness)
    faith_row = conn.execute(
        """
        SELECT count(*) AS total_dec, AVG(faithfulness_score) AS avg_faith
        FROM decisions
        WHERE agent_id = ? AND action IN ('BUY', 'ADJUST')
        """,
        (agent_id,),
    ).fetchone()
    avg_faithfulness = (
        round(float(faith_row["avg_faith"]), 3) if faith_row and faith_row["avg_faith"] is not None else 1.0
    )

    # Data Provenance Coverage for BUY decisions (POINT_IN_TIME vs FROZEN_CURRENT)
    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    has_snapshots = "feature_snapshots" in tables
    dec_cols = (
        [col[1] for col in conn.execute("PRAGMA table_info(decisions)").fetchall()] if "decisions" in tables else []
    )
    has_prov_col = "data_provenance" in dec_cols

    pit_buys = 0
    frozen_buys = 0
    total_buys = 0
    pit_coverage_pct = 100.0

    if has_prov_col:
        prov_rows = conn.execute(
            """
            SELECT data_provenance, count(*) AS cnt
            FROM decisions
            WHERE agent_id = ? AND action = 'BUY'
            GROUP BY data_provenance
            """,
            (agent_id,),
        ).fetchall()
        prov_counts = {r["data_provenance"]: r["cnt"] for r in prov_rows}
        pit_buys = prov_counts.get("POINT_IN_TIME", 0)
        frozen_buys = prov_counts.get("FROZEN_CURRENT", 0)
        total_buys = pit_buys + frozen_buys
        pit_coverage_pct = round((pit_buys / total_buys * 100.0), 1) if total_buys > 0 else 100.0
    elif has_snapshots:
        try:
            prov_rows = conn.execute(
                """
                SELECT json_extract(fs.features_json, '$.fundamentals_source') AS data_provenance, count(*) AS cnt
                FROM decisions d
                JOIN feature_snapshots fs ON d.snapshot_id = fs.id
                WHERE d.agent_id = ? AND d.action = 'BUY'
                GROUP BY data_provenance
                """,
                (agent_id,),
            ).fetchall()
            prov_counts = {r["data_provenance"]: r["cnt"] for r in prov_rows}
            pit_buys = prov_counts.get("POINT_IN_TIME", 0)
            frozen_buys = prov_counts.get("FROZEN_CURRENT", 0)
            total_buys = pit_buys + frozen_buys
            pit_coverage_pct = round((pit_buys / total_buys * 100.0), 1) if total_buys > 0 else 100.0
        except Exception:
            pass

    # Sensitivity Split on Closed Positions (Alpha/PnL: PIT vs FROZEN)
    avg_return_pit_pct = None
    avg_return_frozen_pct = None
    pit_trades_count = 0
    frozen_trades_count = 0
    min_pit_sample = 5
    pit_split_reliable = False

    if has_prov_col or has_snapshots:
        try:
            if has_prov_col:
                prov_trades = conn.execute(
                    """
                    SELECT p.id, p.realized_pnl_pct, COALESCE(d.data_provenance, 'UNKNOWN') AS data_provenance
                    FROM positions p
                    LEFT JOIN decisions d ON p.entry_decision_id = d.id
                    WHERE p.agent_id = ? AND p.status = 'CLOSED'
                    """,
                    (agent_id,),
                ).fetchall()
            else:
                prov_trades = conn.execute(
                    """
                    SELECT p.id, p.realized_pnl_pct, COALESCE(json_extract(fs.features_json, '$.fundamentals_source'), 'UNKNOWN') AS data_provenance
                    FROM positions p
                    LEFT JOIN decisions d ON p.entry_decision_id = d.id
                    LEFT JOIN feature_snapshots fs ON d.snapshot_id = fs.id
                    WHERE p.agent_id = ? AND p.status = 'CLOSED'
                    """,
                    (agent_id,),
                ).fetchall()

            pit_trades = [
                p["realized_pnl_pct"]
                for p in prov_trades
                if p["data_provenance"] == "POINT_IN_TIME" and p["realized_pnl_pct"] is not None
            ]
            frozen_trades = [
                p["realized_pnl_pct"]
                for p in prov_trades
                if p["data_provenance"] == "FROZEN_CURRENT" and p["realized_pnl_pct"] is not None
            ]

            pit_trades_count = len(pit_trades)
            frozen_trades_count = len(frozen_trades)
            pit_split_reliable = pit_trades_count >= min_pit_sample and frozen_trades_count >= min_pit_sample

            avg_return_pit_pct = round(sum(pit_trades) / pit_trades_count, 2) if pit_trades_count > 0 else None
            avg_return_frozen_pct = (
                round(sum(frozen_trades) / frozen_trades_count, 2) if frozen_trades_count > 0 else None
            )
        except Exception:
            pass

    is_provisional = total_closed_trades < provisional_min_trades
    phil_eval = evaluate_agent_philosophy_adherence(conn, agent_id)
    philosophy_adherence_pct = phil_eval.get("adherence_pct", 100.0)
    philosophy_tenet_stats = phil_eval.get("tenet_stats", {})
    philosophy_selection_fidelity = phil_eval.get("selection_fidelity", 100.0)
    philosophy_horizon_fidelity = phil_eval.get("horizon_fidelity", 100.0)
    philosophy_citation_fidelity = phil_eval.get("citation_fidelity", 100.0)
    philosophy_status = phil_eval.get("status", "FAITHFUL")

    return {
        "agent_id": agent_id,
        "is_backtest": is_backtest,
        "is_applicable": True,
        "initial_nav_paise": initial_nav,
        "current_nav_paise": current_nav,
        "total_nav_rupees": paise_to_rupees(current_nav),
        "total_return_pct": round(total_return_pct, 2),
        "benchmark_return_pct": round(benchmark_return_pct, 2),
        "alpha_pct": round(alpha_pct, 2),
        "sharpe_ratio": round(sharpe_ratio, 2),
        "sortino_ratio": round(sortino_ratio, 2),
        "max_drawdown_pct": max_drawdown_pct,
        "calmar_ratio": calmar_ratio,
        "avg_invested_pct": avg_invested_pct,
        "max_invested_pct": max_invested_pct,
        "cash_drag_pct": cash_drag_pct,
        "total_closed_trades": total_closed_trades,
        "winning_trades": win_count,
        "losing_trades": len(losing_trades),
        "win_rate_pct": round(win_rate_pct, 1),
        "avg_win_pct": avg_win_pct,
        "avg_loss_pct": avg_loss_pct,
        "payoff_ratio": payoff_ratio,
        "expectancy_pct": expectancy_pct,
        "profit_factor": profit_factor,
        "avg_hold_days": round(avg_hold_days, 1),
        "avg_faithfulness": avg_faithfulness,
        "philosophy_adherence_pct": philosophy_adherence_pct,
        "philosophy_composite_score": philosophy_adherence_pct,
        "philosophy_selection_fidelity": philosophy_selection_fidelity,
        "philosophy_horizon_fidelity": philosophy_horizon_fidelity,
        "philosophy_citation_fidelity": philosophy_citation_fidelity,
        "philosophy_status": philosophy_status,
        "philosophy_tenet_stats": philosophy_tenet_stats,
        "pit_coverage_pct": pit_coverage_pct,
        "total_buys": total_buys,
        "pit_buys": pit_buys,
        "frozen_buys": frozen_buys,
        "avg_return_pit_pct": avg_return_pit_pct,
        "avg_return_frozen_pct": avg_return_frozen_pct,
        "pit_trades_count": pit_trades_count,
        "frozen_trades_count": frozen_trades_count,
        "pit_split_reliable": pit_split_reliable,
        "is_provisional": is_provisional,
        "sample_notice": (
            f"PROVISIONAL ({total_closed_trades}/{provisional_min_trades} closed trades)"
            if is_provisional
            else "VALIDATED (>=30 closed trades)"
        ),
        "evidence_label": "BACKTEST_DERIVED" if is_backtest else "LIVE_PILOT",
    }


def evaluate_all_agents(
    conn: sqlite3.Connection,
    is_backtest: bool = False,
    provisional_min_trades: int = 30,
) -> list[dict[str, Any]]:
    """
    Evaluates all registered agents in the provided database.
    """
    agent_rows = conn.execute("SELECT id FROM agents ORDER BY id ASC").fetchall()
    results = []
    for row in agent_rows:
        aid = row["id"]
        res = calculate_agent_performance(
            conn,
            aid,
            is_backtest=is_backtest,
            provisional_min_trades=provisional_min_trades,
        )
        results.append(res)
    return results
