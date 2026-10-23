"""
Prompt templates shared by the runner: system prompt skeleton, decision schema, output contract.
The cited-metrics list is generated from core.features.persona_allowed_metric_names() -- the
same function agents/context_assembler.py uses to decide which keys appear in candidate rows --
so the prompt and the data it describes can never drift apart. Parameterized by each persona's
hurdle dicts (not imported from agents.personas) to avoid a prompts<->personas import cycle.
See Plan_v3 §3.1.
"""
from core.features import persona_allowed_metric_names

_OUTPUT_CONTRACT = """OUTPUT CONTRACT
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
  Cite only values you actually saw in the candidate data."""


def _build_system_prompt(philosophy: str, holding_horizon: str, hurdle_summary: str,
                          technical_hurdles: dict, fundamental_hurdles: dict) -> str:
    allowed_metrics = ", ".join(persona_allowed_metric_names(technical_hurdles, fundamental_hurdles))
    return f"""{philosophy}

HOLDING HORIZON: {holding_horizon}.

ENTRY CRITERIA: {hurdle_summary}

SIZING: risk about 2% of account capital if the stop is hit
(shares = 0.02 x account_value / (entry - stop_loss)); never commit more than ~20% to one position.

RISK CAPS (soft -- logged as a breach, not blocked, but a disciplined trader respects them):
at most 2% capital risk per trade, 5% max open-position drawdown, 25% max per sector.

{_OUTPUT_CONTRACT.format(allowed_metrics=allowed_metrics)}
"""


SIMONS_PHILOSOPHY = (
    "You are Jim Simons, running a quantitative momentum strategy on the Nifty 500 for a "
    "paper-trading research account (Rs 1,00,000 starting capital, educational only, no real "
    "funds). You trade confirmed, quantifiable trend structure -- never prediction -- and cut "
    "losses fast when it breaks down."
)


def build_simons_system_prompt(technical_hurdles: dict, fundamental_hurdles: dict) -> str:
    return _build_system_prompt(
        philosophy=SIMONS_PHILOSOPHY,
        holding_horizon="3-14 trading days; exit if a position hasn't worked by then, don't hope",
        hurdle_summary=(
            "20 EMA above the 50 EMA, volume >=1.2x its 20-session average, RSI 55-70 "
            "(strong but not overbought), and a positive MACD histogram."
        ),
        technical_hurdles=technical_hurdles,
        fundamental_hurdles=fundamental_hurdles,
    )
