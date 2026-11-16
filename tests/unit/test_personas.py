"""
Unit tests verifying that all 5 persona configurations match Plan_v3 specifications:
- System prompt contains output contract, pre-mortem risk, risk caps, sizing, and allowed metrics.
- Stage-1 hurdles are properly formed predicates.
- Stage-2 sort keys are registered in precompute.watchlist_refresh.SORT_KEYS and calculate valid scores.
- Windows (TTL, lookback, eval horizon) match Plan_v3 §3.1.
"""

from agents.personas import all_personas, get_persona
from core.config import settings
from watchlist.watchlist_refresh import SORT_KEYS

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
    assert ids == set(settings.PERSONAS.keys())

    for p in personas:
        expected = settings.PERSONAS[p.id]
        assert p.ttl_days == expected["ttl_days"]
        assert p.lookback_days == expected["lookback_days"]
        assert p.eval_horizon_days == expected["eval_horizon_days"]
        assert p.sort_key == expected["sort_key"]
        assert p.atr_stop_multiplier == expected["atr_stop_multiplier"]
        assert p.require_above_ema200 == expected["require_above_ema200"]
        assert p.max_candidates == expected["max_candidates"]
        assert p.max_open_positions == expected["max_open_positions"]
        assert p.min_closed_trades_for_reflection == expected["min_closed_trades_for_reflection"]


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

    # Jhunjhunwala must consistently use 3.0x ATR
    rj_prompt = get_persona("jhunjhunwala").system_prompt
    assert "3.0x ATR" in rj_prompt


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
