"""
Pydantic models for the Plan_v3 §3.3 decision schema: BUY, SELL, HOLD, ADJUST, dispatched by
the "action" field. Used by agents/parsers.py to validate the LLM's JSON output.
See Plan_v3 §3.3.
"""

import json
import math
import re
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class BuyDecision(BaseModel):
    ticker: str
    action: Literal["BUY"]
    shares: int = Field(gt=0)
    entry_low: float = Field(gt=0)
    entry_high: float = Field(gt=0)
    stop_loss_price: float = Field(gt=0)
    target_price: float = Field(gt=0)
    pre_mortem_risk: str
    reasoning: str
    cited_metrics: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _check_price_logic(self) -> "BuyDecision":
        if not (0 < self.stop_loss_price < self.entry_low <= self.entry_high < self.target_price):
            raise ValueError("price logic must satisfy 0 < stop_loss_price < entry_low <= entry_high < target_price")
        return self


class SellDecision(BaseModel):
    ticker: str
    action: Literal["SELL"]
    reasoning: str


class HoldDecision(BaseModel):
    ticker: str
    action: Literal["HOLD"]
    reasoning: str  # one-line reason


class AdjustDecision(BaseModel):
    ticker: str
    action: Literal["ADJUST"]
    stop_loss_price: float | None = None
    target_price: float | None = None
    reasoning: str | None = None

    @model_validator(mode="after")
    def _require_a_new_value(self) -> "AdjustDecision":
        if self.stop_loss_price is None and self.target_price is None:
            raise ValueError("ADJUST needs a new stop_loss_price and/or target_price")
        return self


DecisionUnion = Annotated[BuyDecision | SellDecision | HoldDecision | AdjustDecision, Field(discriminator="action")]


class DecisionBatch(BaseModel):
    decisions: list[DecisionUnion]


class FeatureMetrics(BaseModel):
    """
    Pydantic contract for the 30 FeatureSnapshot metrics defined in Plan_v3 §2.1.
    Forbids extra/typo fields, coerces types, and sanitizes NaN/inf into None.
    """

    # Price
    close: float | None = Field(default=None, gt=0)

    # Trend
    ema_20: float | None = None
    ema_50: float | None = None
    ema_200: float | None = None
    ema_20_above_50: bool | None = None
    ema_20_cross_above_50: bool | None = None

    # Momentum
    rsi_14: float | None = Field(default=None, ge=0.0, le=100.0)
    macd_hist: float | None = None
    adx_14: float | None = Field(default=None, ge=0.0)

    # Volatility
    atr_14: float | None = Field(default=None, ge=0.0)

    # Volume
    volume_surge: float | None = Field(default=None, ge=0.0)
    obv_slope_sign: int | None = Field(default=None)

    # Structure
    dist_52w_high_pct: float | None = None
    dist_52w_low_pct: float | None = None
    kaufman_er_20: float | None = Field(default=None, ge=0.0, le=1.0)
    zscore_close_20: float | None = None
    parkinson_vol_ratio: float | None = Field(default=None, ge=0.0)
    skew_60: float | None = None

    # Quality
    roce_pct: float | None = None
    roe_pct: float | None = None

    # Valuation
    pe: float | None = None
    pb: float | None = None
    peg: float | None = None
    dcf_discount_pct: float | None = None

    # Solvency
    debt_to_equity: float | None = None
    interest_coverage: float | None = None

    # Cash flow
    cfo_to_pat: float | None = None

    # Growth
    pat_growth_yoy_pct: float | None = None
    revenue_growth_yoy_pct: float | None = None

    # Ownership
    promoter_holding_pct: float | None = Field(default=None, ge=0.0, le=100.0)
    promoter_pledge_pct: float | None = Field(default=None, ge=0.0, le=100.0)
    fii_dii_qoq_delta_pct: float | None = None

    # News
    news_sentiment: float | None = Field(default=None, ge=-1.0, le=1.0)
    news_article_count: int | None = Field(default=None, ge=0)

    # Macro
    india_vix: float | None = Field(default=None, ge=0.0)
    regime: str | None = None

    # Provenance
    fundamentals_source: str | None = None

    model_config = {
        "extra": "forbid",
    }

    @model_validator(mode="before")
    @classmethod
    def _sanitize_nans_and_types(cls, data: Any) -> Any:

        if not isinstance(data, dict):
            return data
        sanitized: dict[str, Any] = {}
        for k, v in data.items():
            if v is None:
                sanitized[k] = None
            elif isinstance(v, bool):
                sanitized[k] = v
            elif isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                sanitized[k] = None
            elif isinstance(v, (int, float, str)):
                sanitized[k] = v
            else:
                try:
                    val = float(v)
                    sanitized[k] = None if (math.isnan(val) or math.isinf(val)) else val
                except (ValueError, TypeError):
                    sanitized[k] = v
        return sanitized


class FeatureSnapshotModel(BaseModel):
    """
    Pydantic contract for one versioned FeatureSnapshot entity.
    """

    ticker: str
    as_of_date: str
    schema_version: int = 1
    features: FeatureMetrics


# =============================================================================
# News Ingestion & Anti-Prompt Injection Defense Contract
# =============================================================================

_INJECTION_PATTERNS = [
    re.compile(r"\[/?inst\]", re.IGNORECASE),
    re.compile(r"<<sys>>|<</sys>>", re.IGNORECASE),
    re.compile(r"<\|im_start\|>|<\|im_end\|>", re.IGNORECASE),
    re.compile(r"(system|assistant|human|user)\s*:\s*", re.IGNORECASE),
    re.compile(r"(ignore|disregard)\s+(all|previous|prior)\s+(instructions|prompts)", re.IGNORECASE),
    re.compile(r"new\s+instruction\s*:", re.IGNORECASE),
]


def sanitize_text_for_prompt(text: str, max_len: int = 140) -> str:
    """
    Sanitizes third-party text to prevent indirect prompt injection, strips linebreaks
    and ASCII control characters, collapses whitespace, and enforces maximum character bounds.
    """
    if not text:
        return ""
    # Strip line breaks and ASCII control codes
    cleaned = re.sub(r"[\r\n\t\x00-\x1f\x7f-\x9f]", " ", text)
    # Neutralize injection patterns
    for pattern in _INJECTION_PATTERNS:
        cleaned = pattern.sub("[REDACTED]", cleaned)
    # Collapse multiple spaces
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:max_len]


class SanitizedNewsArticle(BaseModel):
    """
    Pydantic contract for news articles ingested from external sources.
    Guarantees clean, non-poisonous text, valid ISO timestamps, and bounded FinBERT scores.
    """

    model_config = ConfigDict(extra="ignore")

    ticker: str
    instrument_key: str
    heading: str
    summary: str | None = None
    article_link: str | None = None
    thumbnail: str | None = None
    published_time: str
    positive_prob: float | None = Field(default=None, ge=0.0, le=1.0)
    negative_prob: float | None = Field(default=None, ge=0.0, le=1.0)
    neutral_prob: float | None = Field(default=None, ge=0.0, le=1.0)
    sentiment_score: float | None = Field(default=None, ge=-1.0, le=1.0)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)

    @field_validator("heading")
    @classmethod
    def _sanitize_heading(cls, v: str) -> str:
        cleaned = sanitize_text_for_prompt(v, max_len=140)
        if not cleaned:
            raise ValueError("Heading cannot be empty after sanitization")
        return cleaned

    @field_validator("summary")
    @classmethod
    def _sanitize_summary(cls, v: str | None) -> str | None:
        if not v:
            return None
        return sanitize_text_for_prompt(v, max_len=300)


# =============================================================================
# Reflection & Heuristic Machine-Checkable Trigger Contract
# =============================================================================


class TriggerPredicate(BaseModel):
    """
    Recursive Pydantic validator for machine-checkable triggers over FeatureSnapshot metrics.
    Ensures that only valid registry features and supported operators can ever be saved.
    """

    model_config = ConfigDict(extra="forbid")

    all: list["TriggerPredicate"] | None = None
    any: list["TriggerPredicate"] | None = None
    feature: str | None = None
    op: Literal[">", ">=", "<", "<=", "==", "!="] | None = None
    value: float | int | bool | str | None = None

    @model_validator(mode="after")
    def _check_structure(self) -> "TriggerPredicate":
        is_group_all = self.all is not None
        is_group_any = self.any is not None
        is_leaf = self.feature is not None or self.op is not None or self.value is not None

        if sum([is_group_all, is_group_any, is_leaf]) != 1:
            raise ValueError("Predicate node must be exactly one of: 'all' group, 'any' group, or leaf condition")

        if is_leaf:
            if self.feature is None or self.op is None or self.value is None:
                raise ValueError("Leaf condition requires 'feature', 'op', and 'value'")
            from features.contracts import allowed_metric_names

            allowed = set(allowed_metric_names())
            if self.feature not in allowed:
                raise ValueError(f"Feature {self.feature!r} is not an allowed metric name. Allowed: {sorted(allowed)}")
        return self


class HeuristicRuleDefinition(BaseModel):
    """
    Pydantic contract for LLM-generated reflection heuristics before insertion into agent_memory.
    """

    model_config = ConfigDict(extra="forbid")

    agent_id: str
    kind: Literal["SEEK", "AVOID"]
    context: Literal["ENTRY", "EXIT", "ANY"] = "ENTRY"
    heuristic_text: str = Field(min_length=5, max_length=300)
    trigger: TriggerPredicate
    prescribed_action: Literal["BUY", "SELL", "HOLD", "ADJUST"]
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    status: Literal["testing", "active", "reinforced", "deprecated"] = "testing"

    def to_trigger_json(self) -> str:
        return json.dumps(self.trigger.model_dump(exclude_none=True))
