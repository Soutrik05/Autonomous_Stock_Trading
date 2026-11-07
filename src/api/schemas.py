"""
Pydantic response models for the live (non-backtest) API routes. Field names follow
docs/backend_implementation_guide_week5.md where a real data source exists; a field with no
real source is kept (so the frontend contract doesn't break) but is always null -- see
docs/api.md "Deviations from the Week 5 guide" for the full list and why.
"""

from typing import Any, Optional

from pydantic import BaseModel


class HealthJob(BaseModel):
    job_name: str
    cadence: Optional[str] = None
    status: str
    last_run_at: Optional[str] = None
    duration_sec: Optional[int] = None
    records_processed: Optional[int] = None
    error_message: Optional[str] = None


class HealthResponse(BaseModel):
    database_reachable: bool
    jobs: list[HealthJob]


class ActivityEvent(BaseModel):
    id: str
    timestamp: str
    event_type: str
    agent_id: Optional[str] = None
    symbol: Optional[str] = None
    message: str
    severity: str
    details: Optional[dict[str, Any]] = None


class ActivityResponse(BaseModel):
    total: int
    limit: int
    offset: int
    events: list[ActivityEvent]


class LeaderboardEntry(BaseModel):
    id: str
    name: str
    badge: str
    strategy_family: str
    nav_paise: int
    starting_capital_paise: int
    return_pct: float
    alpha_vs_benchmark_pct: float
    sharpe_ratio: float
    max_drawdown_pct: float
    win_rate_pct: float
    faithfulness_rate_pct: float
    total_trades: int
    closed_trades: int
    active_positions_count: int
    is_provisional: bool
    sample_notice: str
    foundation_model: Optional[str] = None
    evidence_label: str


class NavPoint(BaseModel):
    date: str
    values: dict[str, int]  # agent_id (incl. "nifty500") -> paise


class CitedMetric(BaseModel):
    name: str
    cited_value: Any
    actual_snapshot_value: Optional[Any] = None
    tolerance: Optional[str] = None
    is_faithful: Optional[bool] = None


class Position(BaseModel):
    id: int
    agent_id: str
    symbol: str
    company_name: Optional[str] = None
    sector: str
    quantity: int
    entry_price_paise: int
    current_price_paise: int
    exit_price_paise: Optional[int] = None
    stop_loss_paise: int
    target_price_paise: int
    status: str
    unrealized_pnl_paise: int
    unrealized_pnl_pct: float
    realized_pnl_paise: Optional[int] = None
    realized_pnl_pct: Optional[float] = None
    opened_at: Optional[str] = None
    closed_at: Optional[str] = None
    hold_days: Optional[int] = None
    forensic_tag: Optional[str] = None
    is_frozen: bool
    thesis_summary: Optional[str] = None


class Order(BaseModel):
    id: int
    agent_id: str
    symbol: str
    side: str
    order_type: Optional[str] = None
    quantity: int
    limit_price_paise: Optional[int] = None
    entry_low_paise: Optional[int] = None
    entry_high_paise: Optional[int] = None
    filled_price_paise: Optional[int] = None
    status: str
    rejection_reason: Optional[str] = None
    submitted_at: Optional[str] = None
    filled_at: Optional[str] = None
    statutory_charges_paise: Optional[int] = None
    slippage_paise: Optional[int] = None


class Decision(BaseModel):
    id: int
    agent_id: str
    symbol: str
    decision_date: str
    action: str
    rationale: Optional[str] = None
    faithfulness_score: Optional[float] = None
    sizing_fidelity_score: Optional[float] = None
    candidate_rank: Optional[int] = None
    stage_reached: Optional[str] = None
    allocated_paise: Optional[int] = None
    cited_metrics: list[CitedMetric] = []
