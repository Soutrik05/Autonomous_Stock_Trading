"""
Jim Simons persona config only: trend/momentum hurdles, sort key and windows.
See Plan_v3 §3.1.
"""
from agents.personas.base import PersonaConfig
from agents.prompts import build_simons_system_prompt

# Technical hurdles, as a core.features.evaluate_predicate JSON predicate:
# EMA alignment, RSI 55-70, volume expansion >= 1.2x, MACD histogram positive.
SIMONS_TECHNICAL_HURDLES = {
    "all": [
        {"feature": "ema_20_above_50", "op": "==", "value": True},
        {"feature": "rsi_14", "op": ">=", "value": 55},
        {"feature": "rsi_14", "op": "<=", "value": 70},
        {"feature": "volume_surge", "op": ">=", "value": 1.2},
        {"feature": "macd_hist", "op": ">", "value": 0},
    ]
}
SIMONS_FUNDAMENTAL_HURDLES = {}

SIMONS = PersonaConfig(
    id="simons",
    name="Jim Simons",
    system_prompt=build_simons_system_prompt(SIMONS_TECHNICAL_HURDLES, SIMONS_FUNDAMENTAL_HURDLES),
    technical_hurdles=SIMONS_TECHNICAL_HURDLES,
    fundamental_hurdles=SIMONS_FUNDAMENTAL_HURDLES,
    sort_key="simons_intensity",
    ttl_days=3,
    lookback_days=14,
    eval_horizon_days=5,
    fundamentals_depth="none",
    uses_rag=False,
)
