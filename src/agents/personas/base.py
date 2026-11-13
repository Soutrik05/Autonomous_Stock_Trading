"""
PersonaConfig dataclass: prompt, hurdles, sort key, TTL, windows and fundamentals depth.
See Plan_v3 §3.1.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class PersonaConfig:
    id: str
    name: str
    system_prompt: str  # philosophy, sizing guidance, risk caps, output rules
    technical_hurdles: dict  # Stage-1 boolean hurdles (reads FeatureSnapshot names)
    fundamental_hurdles: dict  # empty for Simons
    sort_key: str  # Stage-2 intensity formula name
    ttl_days: int  # Stage-3 watchlist lock
    lookback_days: int  # reflection window
    eval_horizon_days: int  # horizon used to score heuristics
    fundamentals_depth: str  # none | 8q | 3y | 4y | 12q | 20q
    strategy_type: str = "QUANT_MOMENTUM"  # QUANT_MOMENTUM | GARP | VALUE_CONTRARIAN | GROWTH_COMPOUNDER | HYBRID
    min_win_pnl_pct: float = 4.0  # Minimum gain % to qualify as a strategic win
    min_win_hold_days: int = 3  # Minimum holding days to qualify as a strategic win
    news_lookback_days: int = 7  # Horizon for news headline and narrative context
    atr_stop_multiplier: float = 2.0  # Minimum distance (in ATR_14) below entry for stop loss
    max_candidates: int = 10  # Review pool size (defaults to settings.MAX_CANDIDATES_PER_RUN)
    max_open_positions: int = 5  # Maximum concurrent open positions (defaults to settings.MAX_OPEN_POSITIONS_PER_AGENT)
    max_position_pct: float = 20.0  # Maximum allocation to a single position as % of capital
    target_risk_pct: float = 1.0  # Target capital risk per trade as % of capital
    sector_cap: int = 2  # Maximum positions / watchlist candidates per sector
    prompt_ceiling: int = 3800  # Persona-specific token ceiling (defaults to settings.PROMPT_TOKEN_CEILING)
    extra_metrics: tuple = ()  # Additional metrics for candidate rows and prompt cited_metrics
    require_above_ema200: bool = True  # Whether Stage 3 retention requires price > 200 EMA
    min_closed_trades_for_reflection: int = (
        3  # Minimum closed trades since last watermark required to trigger reflection
    )
