"""
FeatureSnapshot definition: the single list of allowed metric names, units and faithfulness match rules.
"""

import json
import operator
import re
from dataclasses import dataclass, field
from typing import Any

FEATURE_SCHEMA_VERSION = 1

_EPSILON = 1e-9


@dataclass(frozen=True)
class FeatureDef:
    name: str
    group: str
    unit: str
    match_rule: str  # "REL(x)" | "ABS(x)" | "ABS_PCT_CLOSE(x)" | "EXACT"


# The only place a metric name is defined. Order matches Plan_v3 §2.1.
FEATURE_REGISTRY: list[FeatureDef] = [
    FeatureDef("close", "Price", "₹", "REL(0.5)"),
    FeatureDef("ema_20", "Trend", "₹", "REL(0.5)"),
    FeatureDef("ema_50", "Trend", "₹", "REL(0.5)"),
    FeatureDef("ema_200", "Trend", "₹", "REL(0.5)"),
    FeatureDef("ema_20_above_50", "Trend", "flag", "EXACT"),
    FeatureDef("ema_20_cross_above_50", "Trend", "flag", "EXACT"),
    FeatureDef("rsi_14", "Momentum", "0-100", "ABS(2.0)"),
    FeatureDef("macd_hist", "Momentum", "₹", "ABS_PCT_CLOSE(0.1)"),
    FeatureDef("adx_14", "Momentum", "0-100", "ABS(2.0)"),
    FeatureDef("atr_14", "Volatility", "₹", "REL(5)"),
    FeatureDef("volume_surge", "Volume", "x", "REL(5)"),
    FeatureDef("obv_slope_sign", "Volume", "-1/0/+1", "EXACT"),
    FeatureDef("dist_52w_high_pct", "Structure", "%", "ABS(1.0)"),
    FeatureDef("dist_52w_low_pct", "Structure", "%", "ABS(1.0)"),
    FeatureDef("kaufman_er_20", "Momentum", "0-1", "ABS(0.05)"),
    FeatureDef("zscore_close_20", "Structure", "z", "ABS(0.2)"),
    FeatureDef("parkinson_vol_ratio", "Volatility", "%", "REL(5)"),
    FeatureDef("skew_60", "Structure", "ratio", "ABS(0.1)"),
    FeatureDef("roce_pct", "Quality", "%", "ABS(1.0)"),
    FeatureDef("roe_pct", "Quality", "%", "ABS(1.0)"),
    FeatureDef("pe", "Valuation", "x", "REL(5)"),
    FeatureDef("pb", "Valuation", "x", "REL(5)"),
    FeatureDef("peg", "Valuation", "x", "REL(5)"),
    FeatureDef("dcf_discount_pct", "Valuation", "%", "ABS(2.0)"),
    FeatureDef("debt_to_equity", "Solvency", "x", "ABS(0.05)"),
    FeatureDef("interest_coverage", "Solvency", "x", "REL(5)"),
    FeatureDef("cfo_to_pat", "Cash flow", "x", "ABS(0.05)"),
    FeatureDef("pat_growth_yoy_pct", "Growth", "%", "ABS(1.0)"),
    FeatureDef("revenue_growth_yoy_pct", "Growth", "%", "ABS(1.0)"),
    FeatureDef("promoter_holding_pct", "Ownership", "%", "ABS(0.5)"),
    FeatureDef("promoter_pledge_pct", "Ownership", "%", "ABS(0.5)"),
    FeatureDef("fii_dii_qoq_delta_pct", "Ownership", "%", "ABS(0.5)"),
    FeatureDef("news_sentiment", "News", "-1..1", "ABS(0.05)"),
    FeatureDef("news_article_count", "News", "count", "EXACT"),
    FeatureDef("india_vix", "Macro", "value", "ABS(0.5)"),
    FeatureDef("regime", "Macro", "label", "EXACT"),
    FeatureDef("fundamentals_source", "Provenance", "label", "EXACT"),
]

_BY_NAME: dict[str, FeatureDef] = {f.name: f for f in FEATURE_REGISTRY}
_RULE_RE = re.compile(r"^(REL|ABS|ABS_PCT_CLOSE)\(([0-9.]+)\)$")


def allowed_metric_names() -> list[str]:
    """Returns every allowed FeatureSnapshot/cited_metrics name, in registry order."""
    return [f.name for f in FEATURE_REGISTRY]


CORE_TECHNICAL_FIELDS = [
    "close",
    "ema_20",
    "ema_50",
    "ema_200",
    "rsi_14",
    "macd_hist",
    "volume_surge",
    "adx_14",
    "atr_14",
    "dist_52w_high_pct",
    "dist_52w_low_pct",
]
CONDITIONAL_TECHNICAL_FIELDS = [
    "obv_slope_sign",
    "ema_20_above_50",
    "ema_20_cross_above_50",
    "kaufman_er_20",
    "zscore_close_20",
    "parkinson_vol_ratio",
    "skew_60",
]


def predicate_feature_names(predicate: dict | None) -> set:
    """Recursively collects every 'feature' name referenced anywhere in an evaluate_predicate-style
    JSON predicate (including nested all/any groups)."""
    names = set()
    if not predicate:
        return names
    if "all" in predicate:
        for child in predicate["all"]:
            names |= predicate_feature_names(child)
    elif "any" in predicate:
        for child in predicate["any"]:
            names |= predicate_feature_names(child)
    elif "feature" in predicate:
        names.add(predicate["feature"])
    return names


def persona_allowed_metric_names(
    technical_hurdles: dict, fundamental_hurdles: dict, extra_metrics: list[str] | None = None
) -> list[str]:
    """The exact FeatureSnapshot names a persona's candidate rows and cited_metrics list may
    use: the core technical set, conditional fields only if the persona's hurdles reference them,
    any other registry name its hurdles or extra_metrics reference, and always india_vix/regime."""
    referenced = predicate_feature_names(technical_hurdles) | predicate_feature_names(fundamental_hurdles)
    if extra_metrics:
        referenced |= set(extra_metrics)
    names = list(CORE_TECHNICAL_FIELDS)
    for name in CONDITIONAL_TECHNICAL_FIELDS:
        if name in referenced:
            names.append(name)
    registry_names = set(allowed_metric_names())
    for name in sorted(referenced):
        if name not in names and name in registry_names:
            names.append(name)
    for name in ("india_vix", "regime"):
        if name not in names:
            names.append(name)
    return names


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def matches(name: str, cited: Any, actual: Any, context: dict | None = None) -> bool:
    """Compares a cited value against the FeatureSnapshot's actual value using that feature's
    match rule. A name outside the registry, or a None cited/actual value, never matches."""
    feature = _BY_NAME.get(name)
    if feature is None or cited is None or actual is None:
        return False

    rule = feature.match_rule
    if rule == "EXACT":
        if _is_number(cited) and _is_number(actual):
            return float(cited) == float(actual)
        return cited == actual

    match = _RULE_RE.match(rule)
    if not match:
        return False
    kind, raw_tolerance = match.group(1), float(match.group(2))
    if not (_is_number(cited) and _is_number(actual)):
        return False
    cited_f, actual_f = float(cited), float(actual)

    if kind == "ABS":
        return abs(cited_f - actual_f) <= raw_tolerance
    if kind == "REL":
        denom = abs(actual_f) if abs(actual_f) > _EPSILON else _EPSILON
        return abs(cited_f - actual_f) / denom <= raw_tolerance / 100.0
    if kind == "ABS_PCT_CLOSE":
        context = context or {}
        close = context.get("close")
        if close is None:
            return False
        tolerance = raw_tolerance / 100.0 * abs(float(close))
        return abs(cited_f - actual_f) <= tolerance
    return False


_OPS = {
    ">": operator.gt,
    ">=": operator.ge,
    "<": operator.lt,
    "<=": operator.le,
    "==": operator.eq,
    "!=": operator.ne,
}


def evaluate_predicate(features: dict[str, Any], predicate: dict[str, Any]) -> bool:
    """Evaluates a JSON predicate against a features dict with robust type coercion."""
    if not predicate:
        return True
    if "all" in predicate:
        return all(evaluate_predicate(features, child) for child in predicate["all"])
    if "any" in predicate:
        return any(evaluate_predicate(features, child) for child in predicate["any"])

    actual = features.get(predicate.get("feature"))
    if actual is None:
        return False
    op_func = _OPS.get(predicate.get("op"))
    if not op_func:
        return False

    target_val = predicate.get("value")

    # Attempt numeric coercion if one side is numeric and the other is a numeric string
    try:
        if isinstance(actual, (int, float)) and not isinstance(actual, bool) and not isinstance(target_val, bool):
            target_val = float(target_val)
        elif isinstance(target_val, (int, float)) and not isinstance(target_val, bool) and not isinstance(actual, bool):
            actual = float(actual)
    except (ValueError, TypeError):
        pass

    try:
        return bool(op_func(actual, target_val))
    except TypeError:
        return False


@dataclass
class FeatureSnapshot:
    ticker: str
    as_of_date: str
    schema_version: int
    features: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if isinstance(self.features, dict):
            from core.schemas import FeatureMetrics

            validated = FeatureMetrics.model_validate(self.features)
            self.features = validated.model_dump(exclude_unset=False)

    def to_json(self) -> str:
        return json.dumps(
            {
                "ticker": self.ticker,
                "as_of_date": self.as_of_date,
                "schema_version": self.schema_version,
                "features": self.features,
            }
        )

    @classmethod
    def from_json(cls, raw: str) -> "FeatureSnapshot":
        data = json.loads(raw)
        return cls(data["ticker"], data["as_of_date"], data["schema_version"], data["features"])
