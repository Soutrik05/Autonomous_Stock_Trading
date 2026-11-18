"""
GET /api/agents/{id}/positions, /orders and /decisions: open/closed positions, pending/past
orders, and decisions with cited-metric faithfulness detail.
See Plan_v3 Part IV.
"""

import json
from pathlib import Path
import sqlite3
from typing import Optional

from fastapi import APIRouter, Depends, Query

from api.deps import portfolio_conn, require_agent, to_ist_iso
from api.schemas import CitedMetric, Decision, Order, Position, WatchlistItem
from core.clock import SystemClock
from core.config import settings

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

    # Query historical daily closes from OHLCV store for all tickers to calculate 1D price change
    ticker_history: dict[str, list[tuple[str, float]]] = {}
    tickers = list({r["ticker"] for r in rows if r["ticker"]})
    if tickers:
        ohlcv_path = Path(settings.OHLCV_DB_PATH).resolve()
        if ohlcv_path.exists():
            try:
                m_conn = sqlite3.connect(f"file:{ohlcv_path.as_posix()}?mode=ro", uri=True)
                placeholders = ",".join("?" for _ in tickers)
                c_rows = m_conn.execute(
                    f"""
                    WITH ranked AS (
                        SELECT ticker, trade_date, close, ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY trade_date DESC) as rn
                        FROM ohlcv
                        WHERE ticker IN ({placeholders})
                    )
                    SELECT ticker, trade_date, close
                    FROM ranked
                    WHERE rn <= 2
                    ORDER BY ticker, rn ASC
                    """,
                    tickers,
                ).fetchall()
                for cr in c_rows:
                    t, t_date, c = cr[0], cr[1], cr[2]
                    if t not in ticker_history:
                        ticker_history[t] = []
                    ticker_history[t].append((t_date, c))
                m_conn.close()
            except Exception:
                pass

    today_str = SystemClock().today().isoformat()
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

        # Calculate 1D change: current price (LTP) - previous trading session's close price
        d_paise = None
        d_pct = None
        current_price = r["last_price_paise"] or r["avg_entry_price_paise"]
        hist = ticker_history.get(r["ticker"], [])
        if current_price and hist:
            c1_date, c1_close = hist[0]
            c2_close = hist[1][1] if len(hist) > 1 else None

            # Determine previous trading day's close:
            # If c1 is already today's close (synced at EOD or close matches current price),
            # previous close is c2. Otherwise, c1 is yesterday's close (intraday trading).
            if (c1_date == today_str or round(c1_close * 100) == current_price) and c2_close is not None:
                prev_close = c2_close
            else:
                prev_close = c1_close

            if prev_close and prev_close > 0:
                prev_close_paise = round(prev_close * 100)
                d_paise = current_price - prev_close_paise
                d_pct = round((d_paise / prev_close_paise) * 100.0, 2)

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
                day_change_paise=d_paise,
                day_change_pct=d_pct,
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


@router.get("/{agent_id}/watchlist", response_model=list[WatchlistItem])
def get_agent_watchlist(
    agent_id: str,
    conn: sqlite3.Connection = Depends(portfolio_conn),
) -> list[WatchlistItem]:
    # Support baseline agents by mapping them to their underlying strategy watchlist
    lookup_id = (
        agent_id.replace("baseline-", "")
        .replace("-rules", "")
        .replace("rj", "jhunjhunwala")
        .replace("stockminds-core", "varsity")
    )
    rows = conn.execute(
        """
        SELECT w.agent_id, w.ticker, w.sector, w.added_on, w.ttl_days, w.expires_on, w.intensity_score,
               s.company_name
        FROM agent_watchlist w
        LEFT JOIN symbols s ON s.ticker = w.ticker
        WHERE w.agent_id = ? OR w.agent_id = ?
        ORDER BY w.intensity_score DESC
        """,
        (agent_id, lookup_id),
    ).fetchall()

    return [
        WatchlistItem(
            agent_id=r["agent_id"],
            ticker=r["ticker"],
            company_name=r["company_name"] or r["ticker"],
            sector=r["sector"],
            added_on=r["added_on"],
            ttl_days=r["ttl_days"],
            expires_on=r["expires_on"],
            intensity_score=round(float(r["intensity_score"]), 2) if r["intensity_score"] is not None else 0.0,
        )
        for r in rows
    ]
