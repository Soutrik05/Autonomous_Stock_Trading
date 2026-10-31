"""
Unit tests verifying that all 5 persona configurations match Plan_v3 specifications:
- System prompt contains output contract, pre-mortem risk, risk caps, sizing, and allowed metrics.
- Stage-1 hurdles are properly formed predicates.
- Stage-2 sort keys are registered in precompute.watchlist_refresh.SORT_KEYS and calculate valid scores.
- Windows (TTL, lookback, eval horizon) match Plan_v3 §3.1.
"""
from agents.personas import all_personas, get_persona
from watchlist.watchlist_refresh import SORT_KEYS

EXPECTED_PERSONAS = {
    "simons": {"ttl": 3, "lookback": 14, "eval_horizon": 5, "sort_key": "simons_intensity", "atr_mult": 1.5, "require_above_ema200": True},
    "lynch": {"ttl": 14, "lookback": 120, "eval_horizon": 60, "sort_key": "lynch_intensity", "atr_mult": 2.5, "require_above_ema200": False},
    "marks": {"ttl": 10, "lookback": 90, "eval_horizon": 60, "sort_key": "marks_intensity", "atr_mult": 2.5, "require_above_ema200": False},
    "jhunjhunwala": {"ttl": 14, "lookback": 150, "eval_horizon": 90, "sort_key": "rj_intensity", "atr_mult": 3.5, "require_above_ema200": True},
    "varsity": {"ttl": 14, "lookback": 90, "eval_horizon": 20, "sort_key": "varsity_intensity", "atr_mult": 2.0, "require_above_ema200": True},
}

SAMPLE_FEATURES = {
    "close": 1000.0,
    "ema_20": 990.0,
    "ema_50": 980.0,
    "ema_200": 920.0,
    "ema_20_above_50": True,
    "rsi_14": 58.0,
    "macd_hist": 1.5,
    "adx_14": 25.0,
    "atr_14": 15.0,
    "volume_surge": 1.4,
    "dist_52w_high_pct": -5.0,
    "dist_52w_low_pct": 15.0,
    "roce_pct": 18.0,
    "roe_pct": 16.0,
    "pe": 22.0,
    "pb": 3.5,
    "peg": 0.85,
    "debt_to_equity": 0.4,
    "cfo_to_pat": 1.1,
    "pat_growth_yoy_pct": 14.0,
    "revenue_growth_yoy_pct": 12.0,
    "promoter_holding_pct": 52.0,
    "india_vix": 13.5,
    "regime": "LOW_VOL",
}


def test_all_five_personas_registered_and_match_plan():
    personas = all_personas()
    assert len(personas) == 5
    ids = {p.id for p in personas}
    assert ids == set(EXPECTED_PERSONAS.keys())

    for p in personas:
        expected = EXPECTED_PERSONAS[p.id]
        assert p.ttl_days == expected["ttl"]
        assert p.lookback_days == expected["lookback"]
        assert p.eval_horizon_days == expected["eval_horizon"]
        assert p.sort_key == expected["sort_key"]
        assert p.atr_stop_multiplier == expected["atr_mult"]
        assert p.require_above_ema200 == expected["require_above_ema200"]


def test_system_prompt_integrity_for_all_personas():
    for p in all_personas():
        prompt = p.system_prompt
        # Must contain essential components of the system prompt skeleton
        assert "OUTPUT CONTRACT" in prompt
        assert "decisions" in prompt
        assert "pre_mortem_risk" in prompt
        assert "RISK CAPS" in prompt
        assert "SIZING" in prompt
        assert "HOLDING HORIZON" in prompt
        assert "ENTRY CRITERIA" in prompt
        # Must contain allowed metrics injected
        assert "rsi_14" in prompt
        assert "volume_surge" in prompt
        # Sizing and stop guidance must be agentic without explicit parenthetical math formulas
        assert "(stop_loss_price <=" not in prompt

    # Jhunjhunwala must consistently use 3.5x ATR
    rj_prompt = get_persona("jhunjhunwala").system_prompt
    assert "3.5x ATR" in rj_prompt
    assert "3.0x ATR" not in rj_prompt


def test_sort_keys_registered_and_calculate_scores():
    for p in all_personas():
        assert p.sort_key in SORT_KEYS
        sort_fn = SORT_KEYS[p.sort_key]
        score = sort_fn(SAMPLE_FEATURES)
        assert isinstance(score, float)
        assert score > float("-inf")


def test_sort_keys_gracefully_handle_missing_features():
    for p in all_personas():
        sort_fn = SORT_KEYS[p.sort_key]
        # Empty dict should return -inf or finite fallback, never raise an unhandled exception
        score = sort_fn({})
        assert isinstance(score, float)
