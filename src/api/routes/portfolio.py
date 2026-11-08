"""
GET /api/agents/{id}/positions, /orders and /decisions: open/closed positions, pending/past
orders, and decisions with cited-metric faithfulness detail.
See Plan_v3 Part IV.
"""

import json
import sqlite3
from typing import Optional

from fastapi import APIRouter, Depends, Query

from api.deps import portfolio_conn, require_agent, to_ist_iso
from api.schemas import CitedMetric, Decision, Order, Position

router = APIRouter(prefix="/api/agents", tags=["portfolio"])


@router.get("/{agent_id}/positions", response_model=list[Position])
def get_agent_positions(
    agent_id: str,
    status: Optional[str] = Query(None, pattern="^(OPEN|CLOSED)$"),
    conn: sqlite3.Connection = Depends(portfolio_conn),
) -> list[Position]:
    require_agent(conn, agent_id)

    query = """
        SELECT p.id, p.agent_id, p.ticker, p.sector, p.shares, p.avg_entry_price_paise,
               p.stop_paise, p.target_paise, p.last_price_paise, p.status, p.frozen_reason,
               p.entry_date, p.entry_reasoning, p.exit_date, p.exit_price_paise, p.exit_reason,
               p.hold_days, p.realized_pnl_paise, p.realized_pnl_pct, p.forensics_type,
               s.company_name
        FROM positions p
        LEFT JOIN symbols s ON s.ticker = p.ticker
        """
    params: list = []
    where_parts = []
    if agent_id != "all":
        where_parts.append("p.agent_id = ?")
        params.append(agent_id)
    if status:
        where_parts.append("p.status = ?")
        params.append(status)
    if where_parts:
        query += " WHERE " + " AND ".join(where_parts)
    query += " ORDER BY p.id DESC"

    rows = conn.execute(query, params).fetchall()
    positions = []
    for r in rows:
        is_open = r["status"] == "OPEN"
        cost_paise = r["shares"] * r["avg_entry_price_paise"]
        if is_open:
            unrealized_pnl_paise = (r["last_price_paise"] - r["avg_entry_price_paise"]) * r["shares"]
            unrealized_pnl_pct = round((unrealized_pnl_paise / cost_paise) * 100.0, 2) if cost_paise else 0.0
        else:
            unrealized_pnl_paise = 0
            unrealized_pnl_pct = 0.0
        positions.append(
            Position(
                id=r["id"],
                agent_id=r["agent_id"],
                symbol=r["ticker"],
                company_name=r["company_name"],
                sector=r["sector"],
                quantity=r["shares"],
                entry_price_paise=r["avg_entry_price_paise"],
                current_price_paise=r["last_price_paise"],
                exit_price_paise=r["exit_price_paise"],
                stop_loss_paise=r["stop_paise"],
                target_price_paise=r["target_paise"],
                status=r["status"],
                unrealized_pnl_paise=unrealized_pnl_paise,
                unrealized_pnl_pct=unrealized_pnl_pct,
                realized_pnl_paise=r["realized_pnl_paise"] if not is_open else None,
                realized_pnl_pct=r["realized_pnl_pct"] if not is_open else None,
                opened_at=to_ist_iso(r["entry_date"]),
                closed_at=to_ist_iso(r["exit_date"]),
                hold_days=r["hold_days"],
                forensic_tag=r["forensics_type"],
                is_frozen=r["frozen_reason"] is not None,
                thesis_summary=r["entry_reasoning"],
            )
        )
    return positions


@router.get("/{agent_id}/orders", response_model=list[Order])
def get_agent_orders(agent_id: str, conn: sqlite3.Connection = Depends(portfolio_conn)) -> list[Order]:
    require_agent(conn, agent_id)

    rows = conn.execute(
        """
        SELECT o.id, o.agent_id, o.ticker, o.side, o.shares, o.entry_low_paise, o.entry_high_paise,
               o.status, o.rejection_reason, o.created_at, o.updated_at,
               f.price_paise AS filled_price_paise, f.charges_paise, f.executed_at
        FROM pending_orders o
        LEFT JOIN fills f ON f.order_id = o.id
        """ + (" WHERE o.agent_id = ?" if agent_id != "all" else "") + """
        ORDER BY o.id DESC
        """,
        (() if agent_id == "all" else (agent_id,)),
    ).fetchall()

    return [
        Order(
            id=r["id"],
            agent_id=r["agent_id"],
            symbol=r["ticker"],
            side=r["side"],
            order_type=None,  # not persisted: every order is an entry-band limit order
            quantity=r["shares"],
            limit_price_paise=None,  # no single limit price stored; see entry_low/high_paise
            entry_low_paise=r["entry_low_paise"],
            entry_high_paise=r["entry_high_paise"],
            filled_price_paise=r["filled_price_paise"],
            status=r["status"].upper(),
            rejection_reason=r["rejection_reason"],
            submitted_at=to_ist_iso(r["created_at"]),
            filled_at=to_ist_iso(r["executed_at"]),
            statutory_charges_paise=r["charges_paise"],
            slippage_paise=None,  # fills.price_paise already includes slippage; not isolated
        )
        for r in rows
    ]


@router.get("/{agent_id}/decisions", response_model=list[Decision])
def get_agent_decisions(agent_id: str, conn: sqlite3.Connection = Depends(portfolio_conn)) -> list[Decision]:
    require_agent(conn, agent_id)

    rows = conn.execute(
        """
        SELECT id, agent_id, ticker, run_date, action, reasoning, pre_mortem_risk, faithfulness_score,
               sizing_fidelity_score, cited_metrics_json
        FROM decisions
        """ + (" WHERE agent_id = ?" if agent_id != "all" else "") + """
        ORDER BY id DESC
        """,
        (() if agent_id == "all" else (agent_id,)),
    ).fetchall()

    decisions = []
    for r in rows:
        # cited_metrics is null only when the column is really empty (NULL, '', or '{}') --
        # anything else is parsed into the list, never silently dropped to [].
        cited_metrics = None
        if r["cited_metrics_json"]:
            try:
                raw = json.loads(r["cited_metrics_json"])
                if isinstance(raw, dict) and raw:
                    cited_metrics = [CitedMetric(name=k, cited_value=v) for k, v in raw.items()]
            except (json.JSONDecodeError, TypeError):
                pass
        decisions.append(
            Decision(
                id=r["id"],
                agent_id=r["agent_id"],
                symbol=r["ticker"],
                decision_date=r["run_date"],
                action=r["action"],
                rationale=r["reasoning"],
                pre_mortem_risk=r["pre_mortem_risk"],
                faithfulness_score=r["faithfulness_score"],
                sizing_fidelity_score=r["sizing_fidelity_score"],
                candidate_rank=None,  # not recorded
                stage_reached=None,  # not recorded
                allocated_paise=None,  # not recorded at decision time
                cited_metrics=cited_metrics,
            )
        )
    return decisions
