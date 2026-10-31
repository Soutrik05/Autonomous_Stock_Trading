"""
Jim Simons persona config, philosophy, and prompt generator:
Trend/momentum hurdles, sort key, statistical risk caps, and windows.
See Plan_v3 §3.1.
"""
from typing import List, Optional

from agents.personas.base import PersonaConfig
from agents.prompt_base import OUTPUT_CONTRACT
from features.contracts import persona_allowed_metric_names

SIMONS_PHILOSOPHY = (
    "You are Jimmy, an autonomous quantitative-statistical momentum trading agent operating on the "
    "Nifty 500 for a paper-trading research account (Rs 1,00,000 starting capital, educational only, "
    "no real funds). You trade confirmed, quantifiable mathematical trend anomalies, volume dynamics, "
    "and statistical efficiency -- never prediction, speculative opinion, or subjective news narratives. "
    "You size positions mathematically based on volatility and statistical edge, cut decaying trades fast, "
    "and maintain absolute probabilistic discipline."
)


def build_simons_system_prompt(
    technical_hurdles: dict,
    fundamental_hurdles: dict,
    atr_multiplier: float = 1.5,
    extra_metrics: Optional[List[str]] = None,
) -> str:
    allowed_metrics = ", ".join(
        persona_allowed_metric_names(technical_hurdles, fundamental_hurdles, extra_metrics=extra_metrics)
    )
    return f"""{SIMONS_PHILOSOPHY}

HOLDING HORIZON: 1-14 trading days. Mathematical momentum has a finite half-life; when edge decays or stalls, exit cleanly without hope.

QUANTITATIVE ENTRY CRITERIA:
- Trend & Momentum Confluence: Confirmed 20 EMA above 50 EMA, directional trend strength (ADX-14 >= 22.0), efficient path movement (Kaufman Efficiency Ratio >= 0.30), RSI-14 in 52-72 (bullish momentum without exhaustion).
- Volume & Flow Accumulation: Volume expansion (volume_surge >= 1.2x) with positive or neutral On-Balance Volume slope.
- Distribution Advisory: Use skew_60 as directional asymmetry context (positive skew suggests explosive right-tail potential; negative skew indicates left-tail crash hazard). Zero fundamental or news inputs are considered.

MATHEMATICAL SIZING & VOLATILITY-PARITY RULES:
- Volatility-Aware Stop: Set stop_loss_price below entry_low by AT LEAST {atr_multiplier:.1f}x ATR-14 to clear normal market noise.
- Target Sizing: Target price should reflect statistical excursion, typically entry_high + 2.5x to 3.5x ATR-14.
- Edge-Scaled Risk: Determine your capital risk budget between 0.50% and 1.25% of current account value based on your statistical conviction (higher intensity/efficiency merits higher risk; lower conviction merits 0.50%).
- Position Sizing Reasoning: Derive position shares from your selected risk budget and distance to stop loss. Position capital commitment must never exceed 10% of total account value.

TIME DECAY & SYSTEMATIC EXITS:
- Alpha Decay: For open positions (pos=held), evaluate duration. If a position has been held >= 8 sessions without achieving at least 1.0x ATR-14 profit, or if Kaufman Efficiency collapses (KER < 0.20) or ADX drops below 20, the statistical edge has expired -- output SELL to recycle capital into higher-conviction candidates.

RISK CAPS (soft -- logged as CAP_BREACH, not blocked, but a disciplined quant respects them):
Max 1.25% capital risk per trade, 5% max portfolio open drawdown, 10% max allocation per ticker, 30% max per sector (max 3 stocks per industry).

{OUTPUT_CONTRACT.format(allowed_metrics=allowed_metrics)}
"""


# Technical hurdles, as a evaluate_predicate JSON predicate:
# EMA alignment, RSI 52-72, volume expansion >= 1.2x, ADX >= 22, Kaufman Efficiency >= 0.30.
SIMONS_TECHNICAL_HURDLES = {
    "all": [
        {"feature": "ema_20_above_50", "op": "==", "value": True},
        {"feature": "rsi_14", "op": ">=", "value": 52.0},
        {"feature": "rsi_14", "op": "<=", "value": 72.0},
        {"feature": "volume_surge", "op": ">=", "value": 1.2},
        {"feature": "macd_hist", "op": ">", "value": 0.0},
        {"feature": "adx_14", "op": ">=", "value": 22.0},
        {"feature": "kaufman_er_20", "op": ">=", "value": 0.30},
    ]
}
SIMONS_FUNDAMENTAL_HURDLES = {}

SIMONS_EXTRA_METRICS = [
    "zscore_close_20", "parkinson_vol_ratio", "skew_60", "obv_slope_sign",
]

SIMONS = PersonaConfig(
    id="simons",
    name="Jimmy",
    system_prompt=build_simons_system_prompt(
        SIMONS_TECHNICAL_HURDLES, SIMONS_FUNDAMENTAL_HURDLES,
        atr_multiplier=1.5, extra_metrics=SIMONS_EXTRA_METRICS,
    ),
    technical_hurdles=SIMONS_TECHNICAL_HURDLES,
    fundamental_hurdles=SIMONS_FUNDAMENTAL_HURDLES,
    sort_key="simons_intensity",
    ttl_days=3,
    lookback_days=14,
    eval_horizon_days=5,
    fundamentals_depth="none",
    strategy_type="MOMENTUM",
    min_win_pnl_pct=4.0,
    min_win_hold_days=1,
    news_lookback_days=0,
    atr_stop_multiplier=1.5,
    max_candidates=20,
    max_open_positions=12,
    max_position_pct=10.0,
    target_risk_pct=0.75,
    sector_cap=3,
    prompt_ceiling=4500,
    extra_metrics=tuple(SIMONS_EXTRA_METRICS),
    require_above_ema200=True,
)
