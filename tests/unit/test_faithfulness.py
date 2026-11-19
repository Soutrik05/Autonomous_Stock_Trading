"""
Unit tests for evaluation/faithfulness.py's underlying primitives in core/features.py:
matches() for REL, ABS, EXACT and the macd_hist ABS_PCT_CLOSE rule, and evaluate_predicate()
including None handling. Also covers evaluation/faithfulness.py's compute_faithfulness()
scoring itself: a wrong value, an unregistered name, and citing fewer than 3 metrics.
See Plan_v3 §3.3.
"""

from evaluation.faithfulness import compute_faithfulness
from features.contracts import evaluate_predicate, matches


def test_rel_rule_within_tolerance():
    assert matches("atr_14", 105.0, 100.0, {}) is True  # exactly 5% = REL(5) tolerance


def test_rel_rule_outside_tolerance():
    assert matches("atr_14", 106.0, 100.0, {}) is False


def test_abs_rule_within_tolerance():
    assert matches("rsi_14", 52.0, 50.0, {}) is True  # diff=2 <= ABS(2.0)


def test_abs_rule_outside_tolerance():
    assert matches("rsi_14", 53.0, 50.0, {}) is False


def test_exact_rule_bool():
    assert matches("ema_20_above_50", True, True, {}) is True
    assert matches("ema_20_above_50", True, False, {}) is False


def test_exact_rule_label():
    assert matches("regime", "NORMAL", "NORMAL", {}) is True
    assert matches("regime", "NORMAL", "PANIC", {}) is False


def test_macd_hist_near_zero_uses_pct_of_close_context():
    context = {"close": 1000.0}
    assert matches("macd_hist", 0.5, 0.0, context) is True  # tolerance = 0.1% * 1000 = 1.0
    assert matches("macd_hist", 2.0, 0.0, context) is False


def test_macd_hist_without_context_does_not_match():
    assert matches("macd_hist", 0.5, 0.0, {}) is False
    assert matches("macd_hist", 0.5, 0.0, None) is False


def test_unknown_feature_name_never_matches():
    assert matches("not_a_real_feature", 1.0, 1.0, {}) is False


def test_none_cited_or_actual_never_matches():
    assert matches("rsi_14", None, 50.0, {}) is False
    assert matches("rsi_14", 50.0, None, {}) is False


# --- evaluate_predicate ---


def test_evaluate_predicate_simple_condition_true_and_false():
    predicate = {"feature": "rsi_14", "op": ">=", "value": 55}
    assert evaluate_predicate({"rsi_14": 60}, predicate) is True
    assert evaluate_predicate({"rsi_14": 50}, predicate) is False


def test_evaluate_predicate_missing_feature_is_false():
    predicate = {"feature": "rsi_14", "op": ">=", "value": 55}
    assert evaluate_predicate({"rsi_14": None}, predicate) is False
    assert evaluate_predicate({}, predicate) is False


def test_evaluate_predicate_all_group():
    predicate = {
        "all": [
            {"feature": "india_vix", "op": ">", "value": 22},
            {"feature": "volume_surge", "op": ">=", "value": 1.5},
        ]
    }
    assert evaluate_predicate({"india_vix": 23, "volume_surge": 1.6}, predicate) is True
    assert evaluate_predicate({"india_vix": 23, "volume_surge": 1.0}, predicate) is False
    assert evaluate_predicate({"india_vix": 23, "volume_surge": None}, predicate) is False


def test_evaluate_predicate_any_group():
    predicate = {
        "any": [
            {"feature": "rsi_14", "op": "<", "value": 30},
            {"feature": "dist_52w_low_pct", "op": "<=", "value": 2},
        ]
    }
    assert evaluate_predicate({"rsi_14": 25, "dist_52w_low_pct": 10}, predicate) is True
    assert evaluate_predicate({"rsi_14": 50, "dist_52w_low_pct": 10}, predicate) is False


def test_evaluate_predicate_nested_groups():
    predicate = {
        "all": [
            {"feature": "regime", "op": "==", "value": "NORMAL"},
            {
                "any": [
                    {"feature": "rsi_14", "op": ">=", "value": 60},
                    {"feature": "macd_hist", "op": ">", "value": 0},
                ]
            },
        ]
    }
    assert evaluate_predicate({"regime": "NORMAL", "rsi_14": 65, "macd_hist": -1}, predicate) is True
    assert evaluate_predicate({"regime": "PANIC", "rsi_14": 65, "macd_hist": -1}, predicate) is False
    assert evaluate_predicate({"regime": "NORMAL", "rsi_14": 40, "macd_hist": -1}, predicate) is False


# --- evaluation/faithfulness.compute_faithfulness ---


def test_compute_faithfulness_wrong_value_is_a_mismatch():
    features = {"close": 1000.0, "rsi_14": 50.0, "volume_surge": 1.5, "macd_hist": 1.0}
    cited = {"rsi_14": 80.0, "volume_surge": 1.5, "macd_hist": 1.0}  # rsi_14 is wrong (diff=30 > ABS(2.0))
    score = compute_faithfulness(cited, features)
    assert score == 2 / 3


def test_compute_faithfulness_unregistered_name_is_a_mismatch():
    features = {"close": 1000.0, "rsi_14": 50.0, "volume_surge": 1.5}
    cited = {"rsi_14": 50.0, "volume_surge": 1.5, "made_up_metric": 1.0}
    score = compute_faithfulness(cited, features)
    assert score == 2 / 3


def test_compute_faithfulness_penalises_fewer_than_three_cited():
    features = {"close": 1000.0, "rsi_14": 50.0, "volume_surge": 1.5}
    cited = {"rsi_14": 50.0, "volume_surge": 1.5}  # both correct, but only 2 cited
    score = compute_faithfulness(cited, features)
    assert score == 2 / 3  # matched=2, denom=max(2,3)=3


def test_compute_faithfulness_three_correct_scores_1():
    features = {"close": 1000.0, "rsi_14": 50.0, "volume_surge": 1.5, "roce_pct": 18.0}
    cited = {"rsi_14": 50.0, "volume_surge": 1.5, "roce_pct": 18.0}
    assert compute_faithfulness(cited, features) == 1.0


def test_compute_faithfulness_empty_citation_is_zero():
    assert compute_faithfulness({}, {"close": 1000.0}) == 0.0
