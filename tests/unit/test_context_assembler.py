"""
Unit tests for agents/context_assembler.py: candidate row formatting and the trim order
(RAG, then episodic memory, then lowest-intensity watchlist candidates) -- held positions are
never trimmed.
See Plan_v3 §3.2.
"""
from agents.context_assembler import assemble_prompt, build_candidate_row, estimate_tokens


def make_candidate(ticker, is_held, intensity=0.0, close=100.0):
    return {
        "ticker": ticker,
        "sector": "TestSector",
        "features": {"close": close, "ema_20": 101.0, "ema_50": 99.0, "ema_200": 95.0, "rsi_14": 60.0},
        "is_held": is_held,
        "intensity_score": intensity,
    }


def test_candidate_row_handles_missing_fundamentals_as_na():
    row = build_candidate_row("TATAMOTORS", "Automobiles", {"close": 948.2, "rsi_14": 62.4}, is_held=False)
    assert row.startswith("TATAMOTORS|AUT|")
    assert "roce=NA" in row
    assert "pos=none" in row


def test_estimate_tokens_is_chars_over_3_5():
    text = "a" * 35
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
        rag_block="Some RAG snippet.",
        ceiling=100_000,
    )
    assert trimmed == {"rag": False, "episodic": False, "dropped_candidates": []}
    assert "HELD1" in text
    assert "WL1" in text
    assert "Some RAG snippet." in text


def test_trim_order_rag_then_episodic_then_lowest_intensity_never_held():
    # Two held positions (must survive no matter what) and several watchlist names with
    # distinct intensity so we can verify the lowest-intensity ones go first.
    candidates = [
        make_candidate("HELD1", True),
        make_candidate("HELD2", True),
        make_candidate("WLHIGH", False, intensity=9.0),
        make_candidate("WLMID", False, intensity=5.0),
        make_candidate("WLLOW", False, intensity=1.0),
    ]
    big_rag = "RAG: " + ("x" * 2000)
    big_episodic = "RECENT CLOSED TRADES (most recent first):\n" + "\n".join(f"- TICK{i} closed" for i in range(50))

    # Ceiling chosen so that: with everything, over budget; drop RAG -> still maybe over;
    # drop episodic -> still over; must then drop WLLOW, then WLMID, but never HELD1/HELD2.
    text, trimmed = assemble_prompt(
        system_prompt="short",
        regime_line="REGIME: NORMAL (India VIX: 14.00).",
        heuristics_block="ACTIVE HEURISTICS: none yet.",
        episodic_block=big_episodic,
        portfolio_block="PORTFOLIO: cash=Rs100,000, no open positions.",
        candidates=candidates,
        rag_block=big_rag,
        ceiling=120,
    )

    assert trimmed["rag"] is True
    assert trimmed["episodic"] is True
    assert "WLLOW" in trimmed["dropped_candidates"]
    assert "HELD1" not in trimmed["dropped_candidates"]
    assert "HELD2" not in trimmed["dropped_candidates"]
    assert "HELD1" in text
    assert "HELD2" in text
    assert "x" * 2000 not in text  # RAG block gone


def test_held_candidates_survive_even_at_an_impossibly_small_ceiling():
    candidates = [make_candidate("HELD1", True), make_candidate("WL1", False, intensity=5.0)]
    text, trimmed = assemble_prompt(
        system_prompt="short",
        regime_line="REGIME: NORMAL (India VIX: 14.00).",
        heuristics_block="ACTIVE HEURISTICS: none yet.",
        episodic_block="RECENT CLOSED TRADES: none yet.",
        portfolio_block="PORTFOLIO: cash=Rs100,000, no open positions.",
        candidates=candidates,
        ceiling=1,
    )
    assert "WL1" in trimmed["dropped_candidates"]
    assert "HELD1" in text
