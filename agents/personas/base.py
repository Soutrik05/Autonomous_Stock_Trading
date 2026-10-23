"""
PersonaConfig dataclass: prompt, hurdles, sort key, TTL, windows and fundamentals depth.
See Plan_v3 §3.1.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class PersonaConfig:
    id: str
    name: str
    system_prompt: str            # philosophy, sizing guidance, risk caps, output rules
    technical_hurdles: dict       # Stage-1 boolean hurdles (reads FeatureSnapshot names)
    fundamental_hurdles: dict     # empty for Simons
    sort_key: str                 # Stage-2 intensity formula name
    ttl_days: int                 # Stage-3 watchlist lock
    lookback_days: int            # reflection window
    eval_horizon_days: int        # horizon used to score heuristics
    fundamentals_depth: str       # none | 8q | 3y | 12q | 20q
    uses_rag: bool
