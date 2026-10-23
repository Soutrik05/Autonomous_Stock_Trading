"""
FeatureSnapshot definition: the single list of allowed metric names, units and faithfulness match rules.
See Plan_v3 §2.1.
"""
import json
import operator
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

FEATURE_SCHEMA_VERSION = 1

_EPSILON = 1e-9


@dataclass(frozen=True)
class FeatureDef:
    name: str
    group: str
    unit: str
    match_rule: str  # "REL(x)" | "ABS(x)" | "ABS_PCT_CLOSE(x)" | "EXACT"


# The only place a metric name is defined. Order matches Plan_v3 §2.1.
FEATURE_REGISTRY: List[FeatureDef] = [
    FeatureDef("close", "Price", "₹", "REL(0.5)"),
    FeatureDef("ema_20", "Trend", "₹", "REL(0.5)"),
    FeatureDef("ema_50", "Trend", "₹", "REL(0.5)"),
    FeatureDef("ema_200", "Trend", "₹", "REL(0.5)"),
    FeatureDef("ema_20_above_50", "Trend", "flag", "EXACT"),
    FeatureDef("rsi_14", "Momentum", "0-100", "ABS(2.0)"),
    FeatureDef("macd_hist", "Momentum", "₹", "ABS_PCT_CLOSE(0.1)"),
    FeatureDef("adx_14", "Momentum", "0-100", "ABS(2.0)"),
    FeatureDef("atr_14", "Volatility", "₹", "REL(5)"),
    FeatureDef("volume_surge", "Volume", "x", "REL(5)"),
    FeatureDef("obv_slope_sign", "Volume", "-1/0/+1", "EXACT"),
    FeatureDef("dist_52w_high_pct", "Structure", "%", "ABS(1.0)"),
    FeatureDef("dist_52w_low_pct", "Structure", "%", "ABS(1.0)"),
    FeatureDef("roce_pct", "Quality", "%", "ABS(1.0)"),
    FeatureDef("roe_pct", "Quality", "%", "ABS(1.0)"),
    FeatureDef("pe", "Valuation", "x", "REL(5)"),
    FeatureDef("pb", "Valuation", "x", "REL(5)"),
    FeatureDef("peg", "Valuation", "x", "REL(5)"),
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
]

_BY_NAME: Dict[str, FeatureDef] = {f.name: f for f in FEATURE_REGISTRY}
_RULE_RE = re.compile(r"^(REL|ABS|ABS_PCT_CLOSE)\(([0-9.]+)\)$")


def allowed_metric_names() -> List[str]:
    """Returns every allowed FeatureSnapshot/cited_metrics name, in registry order."""
    return [f.name for f in FEATURE_REGISTRY]


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def matches(name: str, cited: Any, actual: Any, context: Optional[dict] = None) -> bool:
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


def evaluate_predicate(features: Dict[str, Any], predicate: Dict[str, Any]) -> bool:
    """Evaluates a JSON predicate like {"all": [{"feature": "rsi_14", "op": ">=", "value": 55}]}
    against a features dict (ops: > >= < <= == !=; groups: "all"/"any", nestable). A missing
    (None, or absent) feature makes that leaf condition False. An empty predicate ({}) is
    vacuously True (e.g. a persona's unused fundamental_hurdles). Used for both persona hurdles
    and heuristic triggers."""
    if not predicate:
        return True
    if "all" in predicate:
        return all(evaluate_predicate(features, child) for child in predicate["all"])
    if "any" in predicate:
        return any(evaluate_predicate(features, child) for child in predicate["any"])

    actual = features.get(predicate["feature"])
    if actual is None:
        return False
    op_func = _OPS[predicate["op"]]
    return bool(op_func(actual, predicate["value"]))


@dataclass
class FeatureSnapshot:
    ticker: str
    as_of_date: str
    schema_version: int
    features: Dict[str, Any] = field(default_factory=dict)

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
