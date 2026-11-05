"""
Unit tests for features.contracts.persona_allowed_metric_names() -- the per-persona allowed list
that agents/context_assembler.py (candidate row keys) and agents/prompts.py (the cited-metrics
list) both generate from, so they can never drift apart.
See Plan_v3 §3.2, §3.3.
"""
from agents.personas.simons import SIMONS_FUNDAMENTAL_HURDLES, SIMONS_TECHNICAL_HURDLES
from features.contracts import CORE_TECHNICAL_FIELDS, persona_allowed_metric_names, predicate_feature_names


def test_predicate_feature_names_collects_nested_all_any():
    predicate = {
        "all": [
            {"feature": "rsi_14", "op": ">=", "value": 55},
            {"any": [{"feature": "macd_hist", "op": ">", "value": 0}, {"feature": "adx_14", "op": ">", "value": 20}]},
        ]
    }
    assert predicate_feature_names(predicate) == {"rsi_14", "macd_hist", "adx_14"}


def test_predicate_feature_names_empty_for_empty_predicate():
    assert predicate_feature_names({}) == set()
    assert predicate_feature_names(None) == set()


def test_simons_allowed_names_include_core_set_and_ema_20_above_50_not_obv():
    names = persona_allowed_metric_names(SIMONS_TECHNICAL_HURDLES, SIMONS_FUNDAMENTAL_HURDLES)
    for core_name in CORE_TECHNICAL_FIELDS:
        assert core_name in names
    assert "ema_20_above_50" in names  # referenced by Simons' hurdles
    assert "obv_slope_sign" not in names  # not referenced by Simons' hurdles
    assert "india_vix" in names
    assert "regime" in names


def test_allowed_names_include_fundamental_hurdle_references():
    technical = {"feature": "rsi_14", "op": ">=", "value": 55}
    fundamental = {"feature": "roce_pct", "op": ">=", "value": 15}
    names = persona_allowed_metric_names(technical, fundamental)
    assert "roce_pct" in names


def test_allowed_names_ignore_unregistered_feature_names():
    technical = {"feature": "not_a_real_metric", "op": ">", "value": 0}
    names = persona_allowed_metric_names(technical, {})
    assert "not_a_real_metric" not in names


def test_allowed_names_include_extra_metrics():
    names = persona_allowed_metric_names({}, {}, extra_metrics=["news_sentiment"])
    assert "news_sentiment" in names
