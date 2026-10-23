"""
Technical indicator package. Public API: add_indicators(df) -> DataFrame with every
FeatureSnapshot technical column appended. See Plan_v3 §2.2.
"""
from technical.indicators.snapshot import (
    add_indicators,
    adx_wilder,
    atr_wilder,
    dist_from_52w_high_pct,
    dist_from_52w_low_pct,
    ema,
    macd_histogram,
    obv,
    obv_slope_sign,
    rsi_wilder,
    true_range,
    volume_surge,
)

__all__ = [
    "add_indicators",
    "adx_wilder",
    "atr_wilder",
    "dist_from_52w_high_pct",
    "dist_from_52w_low_pct",
    "ema",
    "macd_histogram",
    "obv",
    "obv_slope_sign",
    "rsi_wilder",
    "true_range",
    "volume_surge",
]
