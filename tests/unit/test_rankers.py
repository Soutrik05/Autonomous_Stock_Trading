"""
Unit tests for precompute/rankers.py:
Verifies single-stock heuristic scorers and cross-sectional factor rankers for all 5 personas.
"""

from watchlist.rankers import (
    SORT_KEYS,
    get_strategy_ranker,
    rank_lynch_intensity,
    rank_marks_intensity,
    rank_rj_intensity,
    rank_simons_intensity,
    rank_varsity_intensity,
)


def test_heuristic_scorers_registered_and_handle_empty():
    assert len(SORT_KEYS) == 5
    for key, scorer in SORT_KEYS.items():
        score = scorer({})
        assert isinstance(score, float)
        assert score == float("-inf") or score >= 0.0


def test_rankers_handle_empty_candidates():
    rankers = [
        rank_simons_intensity,
        rank_lynch_intensity,
        rank_marks_intensity,
        rank_rj_intensity,
        rank_varsity_intensity,
    ]
    for ranker in rankers:
        assert ranker([], {}, {}) == []


def test_simons_ranker_ordering_and_obv_penalty():
    candidates = ["HIGH_MOM", "LOW_MOM", "PENALIZED"]
    features = {
        "HIGH_MOM": {"volume_surge": 2.5, "kaufman_er_20": 0.8, "adx_14": 40.0, "obv_slope_sign": 1},
        "LOW_MOM": {"volume_surge": 1.0, "kaufman_er_20": 0.2, "adx_14": 15.0, "obv_slope_sign": 1},
        "PENALIZED": {"volume_surge": 2.4, "kaufman_er_20": 0.79, "adx_14": 39.0, "obv_slope_sign": -1},
    }
    sectors = {t: "Tech" for t in candidates}
    ranked = rank_simons_intensity(candidates, features, sectors)
    assert len(ranked) == 3
    assert ranked[0]["ticker"] == "HIGH_MOM"
    # PENALIZED receives 20% discount due to obv_slope_sign == -1
    penalized_row = next(r for r in ranked if r["ticker"] == "PENALIZED")
    high_mom_row = next(r for r in ranked if r["ticker"] == "HIGH_MOM")
    assert penalized_row["intensity_score"] < high_mom_row["intensity_score"]


def test_lynch_ranker_ordering_and_growth_bonus():
    candidates = ["HIGH_GROWTH", "MOD_GROWTH"]
    features = {
        "HIGH_GROWTH": {"peg": 0.5, "roce_pct": 25.0, "cfo_to_pat": 1.2, "pat_growth_yoy_pct": 20.0},
        "MOD_GROWTH": {"peg": 0.5, "roce_pct": 25.0, "cfo_to_pat": 1.2, "pat_growth_yoy_pct": 10.0},
    }
    sectors = {t: "FMCG" for t in candidates}
    ranked = rank_lynch_intensity(candidates, features, sectors)
    assert len(ranked) == 2
    assert ranked[0]["ticker"] == "HIGH_GROWTH"
    assert ranked[0]["intensity_score"] > ranked[1]["intensity_score"]


def test_marks_ranker_panic_regime_multiplier():
    candidates = ["PANIC_STOCK", "NORMAL_STOCK"]
    features = {
        "PANIC_STOCK": {
            "rsi_14": 25.0,
            "dist_52w_low_pct": 5.0,
            "roce_pct": 18.0,
            "cfo_to_pat": 1.0,
            "debt_to_equity": 0.3,
            "regime": "PANIC",
        },
        "NORMAL_STOCK": {
            "rsi_14": 25.0,
            "dist_52w_low_pct": 5.0,
            "roce_pct": 18.0,
            "cfo_to_pat": 1.0,
            "debt_to_equity": 0.3,
            "regime": "NORMAL",
        },
    }
    sectors = {t: "Metals" for t in candidates}
    ranked = rank_marks_intensity(candidates, features, sectors)
    assert ranked[0]["ticker"] == "PANIC_STOCK"
    assert ranked[0]["intensity_score"] > ranked[1]["intensity_score"]


def test_rj_ranker_promoter_bonus():
    candidates = ["HIGH_PROM", "LOW_PROM"]
    features = {
        "HIGH_PROM": {
            "pat_growth_yoy_pct": 25.0,
            "fii_dii_qoq_delta_pct": 1.0,
            "volume_surge": 1.5,
            "roce_pct": 20.0,
            "promoter_holding_pct": 55.0,
        },
        "LOW_PROM": {
            "pat_growth_yoy_pct": 25.0,
            "fii_dii_qoq_delta_pct": 1.0,
            "volume_surge": 1.5,
            "roce_pct": 20.0,
            "promoter_holding_pct": 40.0,
        },
    }
    sectors = {t: "Auto" for t in candidates}
    ranked = rank_rj_intensity(candidates, features, sectors)
    assert ranked[0]["ticker"] == "HIGH_PROM"
    assert ranked[0]["intensity_score"] > ranked[1]["intensity_score"]


def test_varsity_ranker_dcf_and_news_sentiment():
    candidates = ["STRONG_VARSITY", "NEUTRAL_VARSITY"]
    features = {
        "STRONG_VARSITY": {
            "volume_surge": 1.8,
            "rsi_14": 58.0,
            "roce_pct": 20.0,
            "debt_to_equity": 0.4,
            "dcf_discount_pct": 20.0,
            "news_sentiment": 0.25,
        },
        "NEUTRAL_VARSITY": {
            "volume_surge": 1.2,
            "rsi_14": 50.0,
            "roce_pct": 14.0,
            "debt_to_equity": 0.7,
            "dcf_discount_pct": None,
            "news_sentiment": 0.0,
        },
    }
    sectors = {t: "Diversified" for t in candidates}
    ranked = rank_varsity_intensity(candidates, features, sectors)
    assert ranked[0]["ticker"] == "STRONG_VARSITY"
    assert ranked[0]["intensity_score"] > ranked[1]["intensity_score"]


def test_get_strategy_ranker_fallback():
    custom_ranker = get_strategy_ranker("unknown_sort_key")
    candidates = ["T1"]
    features = {"T1": {"kaufman_er_20": 0.5, "adx_14": 30.0, "volume_surge": 1.2}}
    sectors = {"T1": "Tech"}
    ranked = custom_ranker(candidates, features, sectors)
    assert len(ranked) == 1
    assert ranked[0]["ticker"] == "T1"
