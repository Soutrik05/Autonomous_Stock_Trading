"""
StockMinds Features Package:
Unified quantitative indicators, FinBERT sentiment scoring, and feature contracts.
"""

from features.contracts import (
    FEATURE_REGISTRY,
    FEATURE_SCHEMA_VERSION,
    FeatureDef,
    FeatureSnapshot,
    allowed_metric_names,
    evaluate_predicate,
    matches,
    persona_allowed_metric_names,
    predicate_feature_names,
)
from features.indicators import (
    add_indicators,
    adx_wilder,
    atr_wilder,
    dist_from_52w_high_pct,
    dist_from_52w_low_pct,
    ema,
    kaufman_er_20,
    macd_histogram,
    obv,
    obv_slope_sign,
    parkinson_vol_ratio,
    rsi_wilder,
    skew_60,
    true_range,
    volume_surge,
    zscore_close_20,
)
from features.sentiment import (
    FinBertScorer,
    get_finbert_scorer,
    set_finbert_scorer,
)

__all__ = [
    # Indicators
    "add_indicators",
    "adx_wilder",
    "atr_wilder",
    "dist_from_52w_high_pct",
    "dist_from_52w_low_pct",
    "ema",
    "kaufman_er_20",
    "macd_histogram",
    "obv",
    "obv_slope_sign",
    "parkinson_vol_ratio",
    "rsi_wilder",
    "skew_60",
    "true_range",
    "volume_surge",
    "zscore_close_20",
    # Sentiment
    "FinBertScorer",
    "get_finbert_scorer",
    "set_finbert_scorer",
    # Contracts
    "FeatureDef",
    "FEATURE_REGISTRY",
    "FEATURE_SCHEMA_VERSION",
    "FeatureSnapshot",
    "allowed_metric_names",
    "evaluate_predicate",
    "matches",
    "persona_allowed_metric_names",
    "predicate_feature_names",
]
