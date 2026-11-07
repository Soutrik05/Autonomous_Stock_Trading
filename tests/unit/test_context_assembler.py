"""
Unit tests for agents/context_assembler.py: candidate rows keyed by exact FeatureSnapshot names
(omitting None fields), and the trim order (RAG, then episodic memory, then lowest-intensity
watchlist candidates) -- held positions are never trimmed.
See Plan_v3 §3.2.
"""

from agents.context_assembler import assemble_prompt, build_candidate_row, estimate_tokens
from features.contracts import persona_allowed_metric_names

SIMONS_HURDLES = {
    "all": [
        {"feature": "ema_20_above_50", "op": "==", "value": True},
        {"feature": "rsi_14", "op": ">=", "value": 55},
        {"feature": "volume_surge", "op": ">=", "value": 1.2},
        {"feature": "macd_hist", "op": ">", "value": 0},
    ]
}
ALLOWED_NAMES = persona_allowed_metric_names(SIMONS_HURDLES, {})


def make_candidate(ticker, is_held, intensity=0.0, close=100.0):
    return {
        "ticker": ticker,
        "sector": "TestSector",
        "features": {"close": close, "ema_20": 101.0, "ema_50": 99.0, "ema_200": 95.0, "rsi_14": 60.0},
        "is_held": is_held,
        "intensity_score": intensity,
    }


def test_candidate_row_uses_exact_metric_names_and_omits_none():
    features = {"close": 948.2, "rsi_14": 62.4, "ema_20": None}  # ema_20 None -> omitted
    row = build_candidate_row("TATAMOTORS", "Automobiles", features, is_held=False, allowed_names=ALLOWED_NAMES)
    assert row.startswith("TATAMOTORS|AUT|")
    assert "close=948.20" in row
    assert "rsi_14=62.4" in row
    assert "ema_20=" not in row  # None -> omitted, not shown as NA
    assert "pos=none" in row


def test_candidate_row_adds_ema_20_above_50_only_when_persona_uses_it():
    features = {"close": 100.0, "ema_20_above_50": True, "obv_slope_sign": 1}
    row = build_candidate_row("X", "Sector", features, is_held=False, allowed_names=ALLOWED_NAMES)
    assert "ema_20_above_50=true" in row  # Simons hurdles reference it
    assert "obv_slope_sign" not in row  # Simons hurdles do not reference it


def test_persona_allowed_names_excludes_regime_level_names_from_rows():
    features = {"close": 100.0, "india_vix": 14.0, "regime": "NORMAL"}
    row = build_candidate_row("X", "Sector", features, is_held=False, allowed_names=ALLOWED_NAMES)
    assert "india_vix" not in row
    assert "regime=" not in row


def test_estimate_tokens_is_chars_over_2_7():
    text = "a" * 27
    assert estimate_tokens(text) == 10


def test_no_trim_needed_when_under_ceiling():
    candidates = [make_candidate("HELD1", True), make_candidate("WL1", False, intensity=5.0)]
    text, trimmed = assemble_prompt(
        system_prompt="short system prompt",
        regime_line="REGIME: NORMAL (India VIX: 14.00).",
        heuristics_block="ACTIVE HEURISTICS: none yet.",
        episodic_block="RECENT CLOSED TRADES: none yet.",
        portfolio_block="PORTFOLIO: cash=Rs100,000, no open positions.",
        candidates=candidates,
        allowed_names=ALLOWED_NAMES,
        ceiling=100_000,
    )
    assert trimmed == {"episodic": False, "headlines": False, "dropped_candidates": []}
    assert "HELD1" in text
    assert "WL1" in text


def test_trim_order_episodic_then_headlines_then_lowest_intensity_never_held():
    # Two held positions (must survive no matter what) and several watchlist names with
    # distinct intensity so we can verify the lowest-intensity ones go first.
    candidates = [
        make_candidate("HELD1", True),
        make_candidate("HELD2", True),
        make_candidate("WLHIGH", False, intensity=9.0),
        make_candidate("WLMID", False, intensity=5.0),
        make_candidate("WLLOW", False, intensity=1.0),
    ]
    big_episodic = "RECENT CLOSED TRADES (most recent first):\n" + "\n".join(f"- TICK{i} closed" for i in range(50))

    # Ceiling chosen so that: with everything, over budget; drop episodic -> still over;
    # must then drop WLLOW, then WLMID, but never HELD1/HELD2.
    text, trimmed = assemble_prompt(
        system_prompt="short",
        regime_line="REGIME: NORMAL (India VIX: 14.00).",
        heuristics_block="ACTIVE HEURISTICS: none yet.",
        episodic_block=big_episodic,
        portfolio_block="PORTFOLIO: cash=Rs100,000, no open positions.",
        candidates=candidates,
        allowed_names=ALLOWED_NAMES,
        ceiling=120,
    )

    assert trimmed["episodic"] is True
    assert "WLLOW" in trimmed["dropped_candidates"]
    assert "HELD1" not in trimmed["dropped_candidates"]
    assert "HELD2" not in trimmed["dropped_candidates"]
    assert "HELD1" in text
    assert "HELD2" in text


def test_held_candidates_survive_even_at_an_impossibly_small_ceiling():
    candidates = [make_candidate("HELD1", True), make_candidate("WL1", False, intensity=5.0)]
    text, trimmed = assemble_prompt(
        system_prompt="short",
        regime_line="REGIME: NORMAL (India VIX: 14.00).",
        heuristics_block="ACTIVE HEURISTICS: none yet.",
        episodic_block="RECENT CLOSED TRADES: none yet.",
        portfolio_block="PORTFOLIO: cash=Rs100,000, no open positions.",
        candidates=candidates,
        allowed_names=ALLOWED_NAMES,
        ceiling=1,
    )
    assert "WL1" in trimmed["dropped_candidates"]
    assert "HELD1" in text


def test_headlines_block_rendering_and_trimming():
    candidate_with_news = make_candidate("TATA", False)
    candidate_with_news["headlines"] = [
        {"relative_age": "today", "sentiment_score": 0.85, "heading": "Quarterly revenue jumps 20%"},
        {"relative_age": "3d ago", "sentiment_score": -0.40, "heading": "Raw material costs rise"},
    ]

    text, trimmed = assemble_prompt(
        system_prompt="short",
        regime_line="REGIME: NORMAL (India VIX: 14.00).",
        heuristics_block="ACTIVE HEURISTICS: none yet.",
        episodic_block="RECENT CLOSED TRADES: none yet.",
        portfolio_block="PORTFOLIO: cash=Rs100,000, no open positions.",
        candidates=[candidate_with_news],
        allowed_names=ALLOWED_NAMES,
        ceiling=10_000,
    )

    assert "RECENT HEADLINES:" in text
    assert "• [today | score: +0.85] Quarterly revenue jumps 20%" in text
    assert "• [3d ago | score: -0.40] Raw material costs rise" in text
    assert trimmed.get("headlines", False) is False

    # When ceiling is tight, headlines are trimmed before dropping candidates
    text_tight, trimmed_tight = assemble_prompt(
        system_prompt="short",
        regime_line="REGIME: NORMAL (India VIX: 14.00).",
        heuristics_block="ACTIVE HEURISTICS: none yet.",
        episodic_block="RECENT CLOSED TRADES: none yet.",
        portfolio_block="PORTFOLIO: cash=Rs100,000, no open positions.",
        candidates=[candidate_with_news],
        allowed_names=ALLOWED_NAMES,
        ceiling=75,
    )
    assert trimmed_tight.get("headlines") is True
    assert "RECENT HEADLINES:" not in text_tight
