"""
Backtest reporting and Question B performance synthesizer.
Generates structured cross-window reports analyzing holding durations, win rates,
P&L, Sharpe ratios, and drawdowns across all personas and market regimes.
Enforces permanent 'BACKTEST_DERIVED' tagging across all outputs.
See Plan_v3 §System Overview.
"""

import sqlite3
from pathlib import Path
from typing import Any

from backtest.config import CADENCE_TABLE
from evaluation.comparison import (
    compare_lynch_vs_baseline,
    compare_marks_vs_baseline,
    compare_rj_vs_baseline,
    compare_simons_vs_baseline,
    compare_varsity_vs_baseline,
)
from evaluation.forensics_mining import extract_forensics_summary
from evaluation.performance import evaluate_all_agents


def generate_window_report(db_path: Path, window_meta: Any) -> dict[str, Any]:
    """Generates detailed quantitative report for a single backtest window database."""
    import dataclasses

    if dataclasses.is_dataclass(window_meta):
        window_dict = dataclasses.asdict(window_meta)  # type: ignore[arg-type]
    elif isinstance(window_meta, dict):
        window_dict = window_meta
    else:
        window_dict = vars(window_meta) if hasattr(window_meta, "__dict__") else {}

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        perf = evaluate_all_agents(conn, is_backtest=True)
        comparison = compare_simons_vs_baseline(conn, is_backtest=True)
        varsity_comparison = compare_varsity_vs_baseline(conn, is_backtest=True)
        lynch_comparison = compare_lynch_vs_baseline(conn, is_backtest=True)
        marks_comparison = compare_marks_vs_baseline(conn, is_backtest=True)
        rj_comparison = compare_rj_vs_baseline(conn, is_backtest=True)

        sessions_count = window_dict.get("sessions_count", 0)
        for p in perf:
            aid = p["agent_id"]
            rule = CADENCE_TABLE.get(aid)
            if rule and sessions_count > 0 and sessions_count < rule.max_hold_days:
                p["is_applicable"] = False
                p["sample_notice"] = (
                    f"STRUCTURALLY_INAPPLICABLE ({sessions_count} sessions < {rule.max_hold_days}d max_hold)"
                )

        # Persona holding horizon resolution details
        positions = conn.execute(
            """
            SELECT agent_id, ticker, status, hold_days, realized_pnl_pct, exit_reason, forensics_type
            FROM positions
            ORDER BY hold_days DESC
            """
        ).fetchall()

        # Group positions by agent
        agent_positions: dict[str, list[dict[str, Any]]] = {}
        for p in positions:
            aid = p["agent_id"]
            if aid not in agent_positions:
                agent_positions[aid] = []
            agent_positions[aid].append(
                {
                    "ticker": p["ticker"],
                    "status": p["status"],
                    "hold_days": p["hold_days"] or 0,
                    "realized_pnl_pct": p["realized_pnl_pct"] or 0.0,
                    "exit_reason": p["exit_reason"],
                    "forensics_type": p["forensics_type"],
                }
            )

        # Holding duration distribution per agent
        holding_stats: dict[str, dict[str, Any]] = {}
        for aid, plist in agent_positions.items():
            closed = [p for p in plist if p["status"] == "CLOSED"]
            durations = [p["hold_days"] for p in closed]
            holding_stats[aid] = {
                "total_trades": len(closed),
                "open_trades": len(plist) - len(closed),
                "min_hold_days": min(durations) if durations else 0,
                "max_hold_days": max(durations) if durations else 0,
                "avg_hold_days": round(sum(durations) / len(durations), 1) if durations else 0.0,
                "full_cycles_completed": len([d for d in durations if d >= 14]),
            }

        return {
            "window": window_dict,
            "evidence_label": "BACKTEST_DERIVED",
            "is_backtest": True,
            "disclaimer": "EVIDENCE FOR QUESTION B ONLY — HISTORICAL SIMULATION (NOT LIVE PILOT RESULTS)",
            "performance": perf,
            "comparison": comparison,
            "varsity_comparison": varsity_comparison,
            "lynch_comparison": lynch_comparison,
            "marks_comparison": marks_comparison,
            "rj_comparison": rj_comparison,
            "holding_stats": holding_stats,
            "forensics": extract_forensics_summary(conn),
            "positions_summary": agent_positions,
        }
    finally:
        conn.close()


def format_markdown_report(report_data: dict[str, Any]) -> str:
    """Formats a single or cross-window report as GitHub-flavored Markdown."""
    win = report_data.get("window", {})
    md = []
    md.append(f"# Historical Walk-Forward Backtest Report — {win.get('name', 'Simulation')}")
    md.append("")
    md.append("> [!IMPORTANT]")
    md.append(f"> **Evidence Classification:** `{report_data.get('evidence_label', 'BACKTEST_DERIVED')}`")
    md.append(f"> **Disclaimer:** {report_data.get('disclaimer')}")
    md.append("")
    md.append(f"- **Window ID:** `{win.get('window_id')}`")
    md.append(
        f"- **Historical Range:** `{win.get('start_date')}` to `{win.get('end_date')}` ({win.get('sessions_count', 0)} trading sessions)"
    )
    md.append(f"- **Market Regime:** `{win.get('regime_label')}` — {win.get('description')}")
    md.append("")
    if win.get("window_id") == "supplementary_range":
        md.append("> [!NOTE]")
        md.append(
            "> **Focal Test Scope (S1):** This supplementary window evaluates Simons (Quant Momentum LLM) against `baseline-simons-rules` under low-volatility range-bound conditions (51 sessions). Longer-horizon personas (`varsity` [75d], `lynch` [90d], `marks` [120d], `jhunjhunwala` [180d]) are barred from trading and marked `STRUCTURALLY_INAPPLICABLE` because their mandatory holding cycles exceed the window length."
        )
        md.append("")
    md.append("## 1. Multi-Agent Performance Summary")
    md.append("")
    md.append(
        "| Agent ID | Return % | Alpha % | Sharpe | Sortino | Max DD % | Calmar | Avg Exposure | Closed | Win % | Profit Factor | Payoff | Expectancy % | Adherence % | Status |"
    )
    md.append(
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |"
    )

    for p in report_data.get("performance", []):
        if not p.get("is_applicable", True):
            md.append(
                f"| **{p['agent_id']}** | — | — | — | — | — | — | — | 0 | — | — | — | — | — | `{p['sample_notice']}` |"
            )
        else:
            ret_str = f"{p['total_return_pct']:+.2f}%" if p.get("total_return_pct") is not None else "0.00%"
            alpha_str = f"{p['alpha_pct']:+.2f}%" if p.get("alpha_pct") is not None else "0.00%"
            sharpe_str = f"{p.get('sharpe_ratio', 0.0):.2f}"
            sortino_str = f"{p.get('sortino_ratio', 0.0):.2f}"
            dd_str = f"{p.get('max_drawdown_pct', 0.0):.2f}%"
            calmar_str = f"{p.get('calmar_ratio', 0.0):.2f}"
            exp_str = f"{p.get('avg_invested_pct', 0.0):.1f}%"
            win_str = f"{p.get('win_rate_pct', 0.0):.1f}%"
            pf_str = f"{p.get('profit_factor', 0.0):.2f}"
            payoff_str = f"{p.get('payoff_ratio', 0.0):.2f}"
            expect_str = f"{p.get('expectancy_pct', 0.0):+.2f}%"
            adh_str = f"{p.get('philosophy_adherence_pct', 100.0):.1f}%"
            md.append(
                f"| **{p['agent_id']}** | {ret_str} | {alpha_str} | "
                f"{sharpe_str} | {sortino_str} | {dd_str} | {calmar_str} | "
                f"{exp_str} | {p['total_closed_trades']} | {win_str} | "
                f"{pf_str} | {payoff_str} | {expect_str} | {adh_str} | `{p['sample_notice']}` |"
            )

    md.append("")
    md.append("## 2. Fundamental Data Quality & Sensitivity Split (Fairness Audit)")
    md.append("")
    md.append(
        "| Agent ID | BUY Decisions | Point-in-Time (PIT) | Frozen Current | PIT Coverage % | Avg Return (PIT Trades) | Avg Return (Frozen Trades) | Sensitivity Divergence |"
    )
    md.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |")

    for p in report_data.get("performance", []):
        if not p.get("is_applicable", True):
            md.append(f"| **{p['agent_id']}** | — | — | — | — | — | — | `{p['sample_notice']}` |")
            continue
        n_pit = p.get("pit_trades_count", 0)
        n_frz = p.get("frozen_trades_count", 0)
        ret_pit = (
            f"{p['avg_return_pit_pct']:+.2f}% (N={n_pit})"
            if p.get("avg_return_pit_pct") is not None
            else "N/A (0 trades)"
        )
        ret_frz = (
            f"{p['avg_return_frozen_pct']:+.2f}% (N={n_frz})"
            if p.get("avg_return_frozen_pct") is not None
            else "N/A (0 trades)"
        )
        if p.get("avg_return_pit_pct") is not None and p.get("avg_return_frozen_pct") is not None:
            raw_div = p["avg_return_pit_pct"] - p["avg_return_frozen_pct"]
            if p.get("pit_split_reliable", False):
                div = f"{raw_div:+.2f}%"
            else:
                div = f"{raw_div:+.2f}% (UNRELIABLE: min N < 5)"
        else:
            div = "0.00% (No split)"
        md.append(
            f"| **{p['agent_id']}** | {p.get('total_buys', 0)} | {p.get('pit_buys', 0)} | {p.get('frozen_buys', 0)} | "
            f"{p.get('pit_coverage_pct', 100.0):.1f}% | {ret_pit} | {ret_frz} | {div} |"
        )

    md.append("")
    md.append("## 3. Thesis Holding Horizon & Question B Resolution")
    md.append("")
    md.append(
        "| Agent ID | Closed Trades | Open Trades | Min Hold Days | Max Hold Days | Avg Hold Days | Cycle Resolved? |"
    )
    md.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- |")

    holding_stats = report_data.get("holding_stats", {})
    perf_list = report_data.get("performance", [])
    perf_by_id = {p["agent_id"]: p for p in perf_list}

    all_agent_ids = sorted(list(perf_by_id.keys())) if perf_by_id else sorted(list(holding_stats.keys()))
    for aid in all_agent_ids:
        p = perf_by_id.get(aid, {})
        s = holding_stats.get(aid)
        if not p.get("is_applicable", True):
            md.append(f"| **{aid}** | 0 | 0 | — | — | — | `{p.get('sample_notice', 'STRUCTURALLY_INAPPLICABLE')}` |")
        elif s:
            resolved_str = "YES (>=1 full cycle)" if s["max_hold_days"] >= 14 else "PARTIAL"
            md.append(
                f"| **{aid}** | {s['total_trades']} | {s['open_trades']} | {s['min_hold_days']}d | "
                f"{s['max_hold_days']}d | {s['avg_hold_days']}d | {resolved_str} |"
            )
        else:
            md.append(f"| **{aid}** | 0 | 0 | 0d | 0d | 0.0d | `NO TRADES (0 closed)` |")

    md.append("")
    md.append("## 4. Paired Baseline Comparisons")
    md.append("")

    perf_list = report_data.get("performance", [])
    applicable_map = {p["agent_id"]: p.get("is_applicable", True) for p in perf_list}
    closed_trades_map = {p["agent_id"]: p.get("total_closed_trades", 0) for p in perf_list}

    def _render_comparison(header: str, llm_id: str, baseline_id: str, cmp_data: dict[str, Any]) -> None:
        md.append(header)
        is_app = applicable_map.get(llm_id, True) and applicable_map.get(baseline_id, True)
        c_llm = closed_trades_map.get(llm_id, 0)
        c_base = closed_trades_map.get(baseline_id, 0)

        if not is_app:
            rule = CADENCE_TABLE.get(llm_id)
            sessions_count = win.get("sessions_count", 0)
            max_hold = rule.max_hold_days if rule else 0
            md.append(f"- **Status:** `STRUCTURALLY_INAPPLICABLE ({sessions_count} sessions < {max_hold}d max_hold)`")
            md.append("- **Conclusion:** `STRUCTURALLY_INAPPLICABLE`")
            md.append("")
            return

        if c_llm == 0 and c_base == 0:
            md.append("- **Status:** `NO TRADES (0 closed trades on both sides)`")
            md.append("- **Conclusion:** `NO_TRADES`")
            md.append("")
            return

        deltas = cmp_data.get("deltas", {}) if cmp_data else {}
        md.append(f"- **Excess Return (LLM - Rules):** `{deltas.get('excess_return_pct', 0.0):+.2f}%`")
        md.append(f"- **Excess Sharpe Ratio:** `{deltas.get('excess_sharpe', 0.0):+.2f}`")
        md.append(f"- **Excess Alpha vs Nifty 500:** `{deltas.get('excess_alpha_pct', 0.0):+.2f}%`")
        md.append(f"- **Excess Win Rate:** `{deltas.get('excess_win_rate_pct', 0.0):+.1f}%`")
        conclusion = (
            "LLM Adds Measurable Value"
            if (cmp_data and cmp_data.get("llm_adds_value"))
            else "Rules Baseline Outperformed"
        )
        md.append(f"- **Conclusion:** `{conclusion}`")
        md.append("")

    _render_comparison(
        "### 4.1 Jim Simons (LLM vs Rules Baseline)",
        "simons",
        "baseline-simons-rules",
        report_data.get("comparison", {}),
    )
    _render_comparison(
        "### 4.2 Zerodha Varsity (LLM vs Rules Baseline)",
        "varsity",
        "baseline-varsity-rules",
        report_data.get("varsity_comparison", {}),
    )
    _render_comparison(
        "### 4.3 Peter Lynch (LLM vs Rules Baseline)",
        "lynch",
        "baseline-lynch-rules",
        report_data.get("lynch_comparison", {}),
    )
    _render_comparison(
        "### 4.4 Howard Marks (LLM vs Rules Baseline)",
        "marks",
        "baseline-marks-rules",
        report_data.get("marks_comparison", {}),
    )
    _render_comparison(
        "### 4.5 Rakesh Jhunjhunwala (LLM vs Rules Baseline)",
        "jhunjhunwala",
        "baseline-rj-rules",
        report_data.get("rj_comparison", {}),
    )

    md.append("## 5. Trade Forensics & Execution Diagnostics (Post-Mortem Breakdown)")
    md.append("")
    forensics = report_data.get("forensics", {})
    if not forensics:
        md.append("_No closed trade forensics available for this window._")
    else:
        md.append(
            "| Agent ID | Closed | Losses | Premature Exits | Avg MAE % | Avg MFE % | Avg Give-Back % | Post-Exit 20d Drift | Dominant Loss Class | Top Secondary Tags |"
        )
        md.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
        for aid, f in sorted(forensics.items()):
            mae_str = f"{f['avg_mae_pct']:+.2f}%" if f.get("avg_mae_pct") is not None else "—"
            mfe_str = f"{f['avg_mfe_pct']:+.2f}%" if f.get("avg_mfe_pct") is not None else "—"
            pgb_str = f"{f['avg_give_back_pct']:.2f}%" if f.get("avg_give_back_pct") is not None else "—"
            pe20_str = f"{f['avg_post_exit_20d_pct']:+.2f}%" if f.get("avg_post_exit_20d_pct") is not None else "—"
            prem_cnt = f.get("premature_exit_count", 0)

            l_classes = f.get("loss_classes", {})
            dom_loss = max(l_classes.items(), key=lambda x: x[1])[0] if l_classes else "None"
            dom_loss_str = f"{dom_loss} ({l_classes[dom_loss]})" if l_classes else "None"

            s_tags = f.get("secondary_tags", {})
            top_tags = sorted(s_tags.items(), key=lambda x: x[1], reverse=True)[:3]
            tags_str = ", ".join(f"{k}: {v}" for k, v in top_tags) if top_tags else "None"

            md.append(
                f"| **{aid}** | {f['total_closed']} | {f['loss_trades']} | {prem_cnt} | {mae_str} | {mfe_str} | {pgb_str} | {pe20_str} | `{dom_loss_str}` | {tags_str} |"
            )
    md.append("")

    md.append("## 6. Persona Philosophy Adherence Audit (3-Dimensional Fidelity Engine)")
    md.append("")
    md.append(
        "| Agent ID | Total Buys | Selection Fid. | Horizon Fid. | Citation Fid. | Composite Adherence | Status | Tenet Pass Rate Breakdown |"
    )
    md.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
    for p in report_data.get("performance", []):
        if not p.get("is_applicable", True):
            continue
        aid = p["agent_id"]
        adh_pct = p.get("philosophy_composite_score", p.get("philosophy_adherence_pct", 100.0))
        sel_pct = p.get("philosophy_selection_fidelity", 100.0)
        hor_pct = p.get("philosophy_horizon_fidelity", 100.0)
        cit_pct = p.get("philosophy_citation_fidelity", 100.0)
        status = p.get("philosophy_status", "FAITHFUL")
        t_buys = p.get("total_buys", 0)
        t_stats = p.get("philosophy_tenet_stats", {})
        breakdown_str = (
            ", ".join(f"{k}: {v['pct']}% ({v['passed']}/{v['total']})" for k, v in t_stats.items()) if t_stats else "—"
        )
        md.append(
            f"| **{aid}** | {t_buys} | {sel_pct:.1f}% | {hor_pct:.1f}% | {cit_pct:.1f}% | **{adh_pct:.1f}%** | `{status}` | {breakdown_str} |"
        )
    md.append("")

    return "\n".join(md)
