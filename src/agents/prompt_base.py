"""
Shared prompt infrastructure and output schema contract for all trading agents.
"""

from features.contracts import persona_allowed_metric_names

OUTPUT_CONTRACT = """OUTPUT CONTRACT
Return ONLY one JSON object, no commentary, no code fences:
{{
  "decisions": [
    {{
      "ticker": "TATAMOTORS", "action": "BUY", "shares": 25,
      "entry_low": 940.0, "entry_high": 955.0,
      "stop_loss_price": 910.0, "target_price": 1020.0,
      "pre_mortem_risk": "one sentence: the single most likely way this trade fails",
      "reasoning": "one or two sentences citing the metrics that justify this decision",
      "cited_metrics": {{"rsi_14": 62.4, "volume_surge": 1.82, "macd_hist": 1.8}}
    }}
  ]
}}
- action: BUY, SELL, HOLD or ADJUST.
- BUY needs shares, entry_low, entry_high, stop_loss_price, target_price, pre_mortem_risk,
  reasoning, cited_metrics. Price logic: 0 < stop_loss_price < entry_low <= entry_high < target_price.
- SELL needs only ticker and reasoning (sells the whole position).
- HOLD needs only ticker and a one-line reasoning.
- ADJUST needs ticker plus a new stop_loss_price and/or target_price (a stop may only rise).
- Return exactly one decision per candidate given, and no others.
- Before every BUY, state the single most likely way it loses money in pre_mortem_risk.
- cited_metrics must name at least 3 metrics, every name from this exact list (any other name
  is unverifiable and counts against you): {allowed_metrics}
  Cite only values you actually saw in the candidate data. If your decision reasoning explicitly relies on news events, corporate developments, or sentiment as a justification, you must include news_sentiment in cited_metrics."""

_OUTPUT_CONTRACT = OUTPUT_CONTRACT


def build_generic_system_prompt(
    philosophy: str,
    holding_horizon: str,
    hurdle_summary: str,
    technical_hurdles: dict,
    fundamental_hurdles: dict,
    atr_multiplier: float = 2.0,
    news_guidance: str | None = None,
    extra_metrics: list[str] | None = None,
) -> str:
    allowed_metrics = ", ".join(
        persona_allowed_metric_names(technical_hurdles, fundamental_hurdles, extra_metrics=extra_metrics)
    )
    news_section = f"\n\nNEWS GUIDANCE & CATALYSTS:\n{news_guidance}" if news_guidance else ""
    return f"""{philosophy}

HOLDING HORIZON: {holding_horizon}.

ENTRY CRITERIA: {hurdle_summary}{news_section}

STOP LOSS & SIZING:
- Volatility-aware stop: Set stop_loss_price below entry_low by AT LEAST {atr_multiplier:.1f}x ATR-14 to avoid market noise shakeouts.
- Sizing: Determine position size such that your capital at risk if the stop is hit does not exceed 1% to 2% of total account capital, and total capital committed to the position does not exceed 20% of account equity.

RISK CAPS (soft -- logged as a breach, not blocked, but a disciplined trader respects them):
at most 2% capital risk per trade, 5% max open-position drawdown, 25% max per sector.

{OUTPUT_CONTRACT.format(allowed_metrics=allowed_metrics)}
"""
