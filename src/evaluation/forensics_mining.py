"""
Trade Forensics Mining and Diagnostics Engine.
Extracts post-mortem execution analytics from closed positions, including:
- Loss class distributions (FALSE_BREAKOUT, BROAD_MARKET_DRAG, etc.)
- Secondary tag counts (LATE_ENTRY, GAP_DOWN, STOP_TOO_TIGHT, etc.)
- MAE (Maximum Adverse Excursion) and MFE (Maximum Favorable Excursion) profiles
- Post-exit drift dynamics
"""

import json
import logging
import sqlite3
from typing import Any

logger = logging.getLogger(__name__)


def extract_forensics_summary(conn: sqlite3.Connection) -> dict[str, Any]:
    """
    Extracts structured forensics metrics from the positions table across all agents.
    Returns a dictionary keyed by agent_id with loss classes, secondary tags, and excursion metrics.
    """
    rows = conn.execute(
        """
        SELECT agent_id, ticker, realized_pnl_pct, exit_reason, forensics_type, diagnosis_json
        FROM positions
        WHERE status = 'CLOSED'
        """
    ).fetchall()

    summary_by_agent: dict[str, dict[str, Any]] = {}

    for r in rows:
        aid = r[0] if isinstance(r, (tuple, list)) else r["agent_id"]
        pnl = r[2] if isinstance(r, (tuple, list)) else r["realized_pnl_pct"]
        f_type = r[4] if isinstance(r, (tuple, list)) else r["forensics_type"]
        diag_raw = r[5] if isinstance(r, (tuple, list)) else r["diagnosis_json"]

        if aid not in summary_by_agent:
            summary_by_agent[aid] = {
                "total_closed": 0,
                "loss_trades": 0,
                "win_trades": 0,
                "loss_classes": {},
                "secondary_tags": {},
                "mae_values": [],
                "mfe_values": [],
                "give_back_values": [],
                "post_exit_5d_values": [],
                "post_exit_20d_values": [],
                "premature_exit_count": 0,
                "fb_total": 0,
                "fb_no_follow": 0,
                "fb_give_back": 0,
            }

        s = summary_by_agent[aid]
        s["total_closed"] += 1
        is_loss = (pnl or 0.0) <= 0.0
        if is_loss:
            s["loss_trades"] += 1
            l_class = f_type or "UNCLASSIFIED"
            s["loss_classes"][l_class] = s["loss_classes"].get(l_class, 0) + 1
        else:
            s["win_trades"] += 1

        mfe = None
        tags: list[str] = []
        if diag_raw:
            try:
                diag = json.loads(diag_raw)
                mae = diag.get("mae_pct")
                if mae is not None:
                    s["mae_values"].append(mae)

                mfe = diag.get("mfe_pct")
                if mfe is not None:
                    s["mfe_values"].append(mfe)

                pgb = diag.get("profit_given_back_pct")
                if pgb is not None:
                    s["give_back_values"].append(pgb)

                tags = diag.get("secondary_tags") or []
                for t in tags:
                    s["secondary_tags"][t] = s["secondary_tags"].get(t, 0) + 1

                post_exit = diag.get("post_exit") or {}
                if isinstance(post_exit, dict):
                    p5 = post_exit.get("post_exit_ret_5d_pct")
                    if p5 is not None:
                        s["post_exit_5d_values"].append(p5)
                    p20 = post_exit.get("post_exit_ret_20d_pct")
                    if p20 is not None:
                        s["post_exit_20d_values"].append(p20)
            except Exception:
                pass

        if f_type == "PREMATURE_TECHNICAL_STOPOUT" or "EXITED_TOO_EARLY" in tags or "STOP_TOO_TIGHT" in tags:
            s["premature_exit_count"] += 1

        if f_type == "FALSE_BREAKOUT":
            s["fb_total"] += 1
            if ("GAVE_BACK_PROFIT" in tags) or (mfe is not None and mfe >= 2.0):
                s["fb_give_back"] += 1
            else:
                s["fb_no_follow"] += 1

    result: dict[str, Any] = {}
    for aid, s in summary_by_agent.items():
        mae_list = s["mae_values"]
        mfe_list = s["mfe_values"]
        pgb_list = s["give_back_values"]
        pe5_list = s["post_exit_5d_values"]
        pe20_list = s["post_exit_20d_values"]

        result[aid] = {
            "total_closed": s["total_closed"],
            "win_trades": s["win_trades"],
            "loss_trades": s["loss_trades"],
            "avg_mae_pct": round(sum(mae_list) / len(mae_list), 2) if mae_list else None,
            "avg_mfe_pct": round(sum(mfe_list) / len(mfe_list), 2) if mfe_list else None,
            "avg_give_back_pct": round(sum(pgb_list) / len(pgb_list), 2) if pgb_list else None,
            "avg_post_exit_5d_pct": round(sum(pe5_list) / len(pe5_list), 2) if pe5_list else None,
            "avg_post_exit_20d_pct": round(sum(pe20_list) / len(pe20_list), 2) if pe20_list else None,
            "premature_exit_count": s["premature_exit_count"],
            "loss_classes": s["loss_classes"],
            "secondary_tags": s["secondary_tags"],
            "fb_split": {
                "total": s["fb_total"],
                "no_follow": s["fb_no_follow"],
                "give_back": s["fb_give_back"],
                "no_follow_pct": round(s["fb_no_follow"] / s["fb_total"] * 100.0, 1) if s["fb_total"] else 0.0,
                "give_back_pct": round(s["fb_give_back"] / s["fb_total"] * 100.0, 1) if s["fb_total"] else 0.0,
            },
        }

    return result
