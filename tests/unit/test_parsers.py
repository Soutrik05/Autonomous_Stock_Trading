"""
Unit tests for agents/parsers.py: clean JSON, code-fenced JSON, the truncation retry (lower
reasoning effort, higher max tokens, no repair message), the schema-repair retry, double-failure
HOLD-all, unknown-ticker dropping, and (day 5a) the primary/fallback orchestration. Uses
FakeLLMClient only (no network).
See Plan_v3 §3.3.
"""

import json

from agents.parsers import (
    DOUBLE_FAILURE_REASON,
    NO_DECISION_REASON,
    calibrate_buy_decision,
    calibrate_decisions,
    fill_missing_with_hold,
    is_truncated,
    parse_decisions,
    parse_with_repair,
    parse_with_repair_and_fallback,
    validate_arithmetic_coherence,
)
from core.schemas import BuyDecision, HoldDecision
from llm.client import FakeLLMClient, LLMClient, LLMResult

CANDIDATES = ["TATAMOTORS", "RELIANCE"]

VALID_RESPONSE = json.dumps(
    {
        "decisions": [
            {
                "ticker": "TATAMOTORS",
                "action": "BUY",
                "shares": 25,
                "entry_low": 940.0,
                "entry_high": 955.0,
                "stop_loss_price": 910.0,
                "target_price": 1020.0,
                "pre_mortem_risk": "margins compress",
                "reasoning": "breakout with volume",
                "cited_metrics": {"rsi_14": 62.4, "volume_surge": 1.82, "macd_hist": 1.8},
            }
        ]
    }
)


def _result(text: str, finish_reason: str = "stop") -> LLMResult:
    return LLMResult(
        text=text, tokens_in=10, tokens_out=10, latency_ms=1, model="fake-model", finish_reason=finish_reason
    )


def test_parses_clean_json():
    decisions, dropped = parse_decisions(VALID_RESPONSE, CANDIDATES)
    assert dropped == []
    assert len(decisions) == 1
    assert decisions[0].ticker == "TATAMOTORS"


def test_parses_code_fenced_json():
    fenced = f"```json\n{VALID_RESPONSE}\n```"
    decisions, dropped = parse_decisions(fenced, CANDIDATES)
    assert len(decisions) == 1


# --- truncation detection and retry ---


def test_is_truncated_on_empty_content():
    assert is_truncated(_result("", finish_reason="length")) is True
    assert is_truncated(_result("   ", finish_reason="stop")) is True  # whitespace-only content


def test_is_truncated_on_finish_reason_length_even_with_content():
    assert is_truncated(_result('{"decisions": [', finish_reason="length")) is True


def test_is_not_truncated_on_clean_stop():
    assert is_truncated(_result(VALID_RESPONSE, finish_reason="stop")) is False


def test_truncation_retry_uses_lower_effort_higher_tokens_and_no_repair_message():
    first = _result("", finish_reason="length")  # empty content, truncated
    llm_client = FakeLLMClient(responses=[VALID_RESPONSE])

    decisions, status, dropped, final_result, attempts = parse_with_repair(
        llm_client,
        "system",
        "the original user prompt",
        first,
        CANDIDATES,
        reasoning_effort="low",
        max_output_tokens=1000,
    )

    assert status == "RETRY_SUCCESS"
    assert len(llm_client.calls) == 1
    retry_call = llm_client.calls[0]
    assert retry_call["user"] == "the original user prompt"  # unchanged -- no repair message appended
    assert retry_call["reasoning_effort"] == "low"  # already lowest tier, stays low
    assert retry_call["max_output_tokens"] == 2000  # doubled
    assert len(attempts) == 2
    assert attempts[0]["parse_status"] == "FAILED"
    assert attempts[1]["parse_status"] == "RETRY_SUCCESS"


def test_truncation_retry_steps_down_from_medium_to_low():
    first = _result("", finish_reason="length")
    llm_client = FakeLLMClient(responses=[VALID_RESPONSE])
    parse_with_repair(
        llm_client,
        "system",
        "user",
        first,
        CANDIDATES,
        reasoning_effort="medium",
        max_output_tokens=1000,
    )
    assert llm_client.calls[0]["reasoning_effort"] == "low"


def test_truncation_retry_failing_again_gives_hold_all():
    first = _result("", finish_reason="length")
    llm_client = FakeLLMClient(responses=[{"text": "", "finish_reason": "length"}])

    decisions, status, dropped, final_result, attempts = parse_with_repair(
        llm_client,
        "system",
        "user",
        first,
        CANDIDATES,
    )
    assert status == "FAILED"
    assert len(llm_client.calls) == 1  # at most 2 total calls (first + this one retry)
    assert all(isinstance(d, HoldDecision) for d in decisions)
    assert all(d.reasoning == DOUBLE_FAILURE_REASON for d in decisions)


# --- schema-repair retry (not truncated, just invalid) ---


def test_repair_retry_sends_validation_error_and_succeeds():
    bad_first = _result("not valid json at all")
    llm_client = FakeLLMClient(responses=[VALID_RESPONSE])

    decisions, status, dropped, final_result, attempts = parse_with_repair(
        llm_client, "system", "user", bad_first, CANDIDATES
    )

    assert status == "RETRY_SUCCESS"
    assert len(llm_client.calls) == 1  # exactly one repair call, not more
    assert "failed validation" in llm_client.calls[0]["user"]  # the repair message IS sent here
    tickers = {d.ticker for d in decisions}
    assert "TATAMOTORS" in tickers
    assert "RELIANCE" in tickers  # filled in with HOLD, no decision returned


def test_double_failure_gives_hold_all_with_failed_status():
    bad_first = _result("still not json")
    llm_client = FakeLLMClient(responses=["also not json"])

    decisions, status, dropped, final_result, attempts = parse_with_repair(
        llm_client, "system", "user", bad_first, CANDIDATES
    )

    assert status == "FAILED"
    assert len(decisions) == len(CANDIDATES)
    assert all(isinstance(d, HoldDecision) for d in decisions)
    assert all(d.reasoning == DOUBLE_FAILURE_REASON for d in decisions)


def test_at_most_two_calls_total_across_all_paths():
    bad_first = _result("not json")
    llm_client = FakeLLMClient(responses=["still not json"])
    parse_with_repair(llm_client, "system", "user", bad_first, CANDIDATES)
    assert len(llm_client.calls) == 1  # 1 (caller's first) + 1 (this retry) = 2 total, never 3


def test_unknown_ticker_is_dropped_and_logged():
    response = json.dumps({"decisions": [{"ticker": "NOTACANDIDATE", "action": "HOLD", "reasoning": "n/a"}]})
    decisions, dropped = parse_decisions(response, CANDIDATES)
    assert decisions == []
    assert dropped == ["NOTACANDIDATE"]


def test_fill_missing_with_hold_uses_exact_reason():
    filled = fill_missing_with_hold([], CANDIDATES)
    assert len(filled) == len(CANDIDATES)
    assert all(d.reasoning == NO_DECISION_REASON for d in filled)


# --- day 5a: primary/fallback orchestration ---


class _RaisingLLMClient(LLMClient):
    """Simulates a primary whose own HTTP-level retries are already exhausted (a network error,
    429-after-backoff, or 5xx that escaped _retry_with_backoff)."""

    def __init__(self, exc: Exception):
        self._exc = exc
        self.calls = 0

    def complete(self, system, user, reasoning_effort=None, max_output_tokens=None, response_schema=None):
        self.calls += 1
        raise self._exc


def test_fallback_is_never_called_when_primary_succeeds():
    primary = FakeLLMClient(responses=[VALID_RESPONSE], provider="groq")
    fallback = FakeLLMClient(responses=[VALID_RESPONSE], provider="gemini")

    decisions, status, dropped, final_result, attempts = parse_with_repair_and_fallback(
        primary,
        "system",
        "user",
        CANDIDATES,
        fallback=fallback,
    )

    assert status == "SUCCESS"
    assert len(primary.calls) == 1
    assert len(fallback.calls) == 0  # never touched
    assert len(attempts) == 1
    assert attempts[0]["fallback_used"] is False


def test_fallback_answers_after_primary_raises_and_is_logged_as_fallback():
    primary = _RaisingLLMClient(ConnectionError("network error"))
    fallback = FakeLLMClient(responses=[VALID_RESPONSE], provider="gemini")

    decisions, status, dropped, final_result, attempts = parse_with_repair_and_fallback(
        primary,
        "system",
        "the original user prompt",
        CANDIDATES,
        fallback=fallback,
    )

    assert status == "FALLBACK_SUCCESS"
    assert primary.calls == 1
    assert len(fallback.calls) == 1
    assert fallback.calls[0]["user"] == "the original user prompt"  # unmodified prompt
    assert len(attempts) == 1
    assert attempts[0]["fallback_used"] is True
    assert attempts[0]["result"].provider == "gemini"
    tickers = {d.ticker for d in decisions}
    assert "TATAMOTORS" in tickers


def test_fallback_answers_after_primary_double_parse_failure_and_is_logged_as_fallback():
    primary = FakeLLMClient(responses=["still not json", "still not json"], provider="groq")  # first + retry both bad
    fallback = FakeLLMClient(responses=[VALID_RESPONSE], provider="gemini")

    decisions, status, dropped, final_result, attempts = parse_with_repair_and_fallback(
        primary,
        "system",
        "user",
        CANDIDATES,
        fallback=fallback,
    )

    assert status == "FALLBACK_SUCCESS"
    assert len(primary.calls) == 2  # primary used its own full 2-call retry budget first
    assert len(fallback.calls) == 1  # exactly one fallback attempt
    assert attempts[-1]["fallback_used"] is True
    assert attempts[-1]["parse_status"] == "FALLBACK_SUCCESS"


def test_both_primary_and_fallback_failing_gives_hold_all():
    primary = FakeLLMClient(responses=["still not json", "still not json"], provider="groq")
    fallback = FakeLLMClient(responses=["also not json"], provider="gemini")

    decisions, status, dropped, final_result, attempts = parse_with_repair_and_fallback(
        primary,
        "system",
        "user",
        CANDIDATES,
        fallback=fallback,
    )

    assert status == "FAILED"
    assert len(decisions) == len(CANDIDATES)
    assert all(isinstance(d, HoldDecision) for d in decisions)
    assert attempts[-1]["fallback_used"] is True
    assert attempts[-1]["parse_status"] == "FAILED"


def test_no_fallback_configured_keeps_primary_only_hold_all():
    primary = FakeLLMClient(responses=["still not json", "still not json"], provider="groq")

    decisions, status, dropped, final_result, attempts = parse_with_repair_and_fallback(
        primary,
        "system",
        "user",
        CANDIDATES,
        fallback=None,
    )

    assert status == "FAILED"
    assert all(isinstance(d, HoldDecision) for d in decisions)
    assert all(not a["fallback_used"] for a in attempts)


def test_both_primary_and_fallback_raising_chains_the_exception():
    primary = _RaisingLLMClient(ConnectionError("primary down"))
    fallback = _RaisingLLMClient(ConnectionError("fallback down"))

    try:
        parse_with_repair_and_fallback(primary, "system", "user", CANDIDATES, fallback=fallback)
        assert False, "expected an exception"
    except ConnectionError as exc:
        assert str(exc) == "fallback down"
        assert isinstance(exc.__cause__, ConnectionError)
        assert str(exc.__cause__) == "primary down"


def test_at_most_three_calls_total_across_all_paths():
    primary = FakeLLMClient(responses=["still not json", "still not json"], provider="groq")
    fallback = FakeLLMClient(responses=["also not json"], provider="gemini")
    parse_with_repair_and_fallback(primary, "system", "user", CANDIDATES, fallback=fallback)
    assert len(primary.calls) + len(fallback.calls) == 3  # 1 + 1 retry + 1 fallback, never more


def test_calibrate_buy_decision_widens_tight_stop_and_resizes_shares():
    buy = BuyDecision(
        ticker="TATAMOTORS",
        action="BUY",
        shares=100,
        entry_low=200.0,
        entry_high=205.0,
        stop_loss_price=198.0,
        target_price=230.0,  # distance = 2.0
        pre_mortem_risk="slowdown",
        reasoning="uptrend",
    )
    # ATR = 5.0. Min mult = 2.0 -> min stop dist = 10.0. Clamped stop = 190.0.
    # Risk per share = 205.0 - 190.0 = 15.0.
    # Account = 100,000:
    # 1% risk = 1,000 -> max shares by risk = 1000 // 15 = 66.
    # 20% position = 20,000 -> max shares by position = 20000 // 205 = 97.
    # Expected shares = min(100, 66, 97) = 66.
    calibrated = calibrate_buy_decision(
        buy,
        atr_14=5.0,
        min_atr_multiplier=2.0,
        account_value_rupees=100000.0,
        max_risk_pct=1.0,
    )
    assert calibrated.stop_loss_price == 190.0
    assert calibrated.shares == 66


def test_calibrate_buy_decision_leaves_adequate_stop():
    buy = BuyDecision(
        ticker="TATAMOTORS",
        action="BUY",
        shares=20,
        entry_low=200.0,
        entry_high=205.0,
        stop_loss_price=185.0,
        target_price=230.0,  # distance = 15.0
        pre_mortem_risk="slowdown",
        reasoning="uptrend",
    )
    # ATR = 5.0. Min mult = 2.0 -> min stop dist = 10.0. 15.0 >= 10.0 -> no stop change (remains 185.0).
    # Risk per share = 205.0 - 185.0 = 20.0.
    # Max shares by risk = 1000 // 20 = 50. Position cap = 20000 // 205 = 97.
    # Since original shares (20) <= 50 and <= 97, shares remain 20.
    calibrated = calibrate_buy_decision(
        buy,
        atr_14=5.0,
        min_atr_multiplier=2.0,
        account_value_rupees=100000.0,
        max_risk_pct=1.0,
    )
    assert calibrated.stop_loss_price == 185.0
    assert calibrated.shares == 20


def test_calibrate_buy_decision_handles_missing_atr():
    buy = BuyDecision(
        ticker="TATAMOTORS",
        action="BUY",
        shares=15,
        entry_low=1000.0,
        entry_high=1010.0,
        stop_loss_price=980.0,
        target_price=1100.0,
        pre_mortem_risk="slowdown",
        reasoning="uptrend",
    )
    calibrated = calibrate_buy_decision(buy, atr_14=None, min_atr_multiplier=2.0, account_value_rupees=100000.0)
    assert calibrated.stop_loss_price == 980.0
    assert calibrated.shares == 15


def test_calibrate_decisions_batch():
    buy1 = BuyDecision(
        ticker="TATAMOTORS",
        action="BUY",
        shares=50,
        entry_low=1000.0,
        entry_high=1010.0,
        stop_loss_price=990.0,
        target_price=1100.0,
        pre_mortem_risk="risk1",
        reasoning="reason1",
    )
    hold = HoldDecision(ticker="INFY", action="HOLD", reasoning="sideways")
    features = {
        "TATAMOTORS": {"atr_14": 20.0},
        "INFY": {"atr_14": 15.0},
    }
    calibrated = calibrate_decisions([buy1, hold], features, min_atr_multiplier=1.5, account_value_rupees=100000.0)
    assert len(calibrated) == 2
    # 1.5 * 20 = 30.0 -> stop = 1000 - 30 = 970.0.
    assert calibrated[0].stop_loss_price == 970.0
    assert isinstance(calibrated[1], HoldDecision)


def test_counterfactual_buy_and_fidelity_score():
    from agents.parsers import calculate_counterfactual_buy, compute_sizing_fidelity_score

    buy = BuyDecision(
        ticker="TATAMOTORS",
        action="BUY",
        shares=25,
        entry_low=1000.0,
        entry_high=1005.0,
        stop_loss_price=980.0,
        target_price=1080.0,
        pre_mortem_risk="risk",
        reasoning="reason",
    )
    # atr=20.0, min_atr_multiplier=1.5 -> stop=1000 - 30 = 970.0 (stop_dist = 1005 - 970 = 35.0)
    # account_value=100,000, target_risk_pct=0.75% -> risk_budget=750 Rs
    # shares_by_risk = 750 // 35 = 21 shares
    # position_cap = 10% of 100,000 = 10,000 Rs // 1005 = 9 shares
    # shares = min(21, 9) = 9 shares
    cf_shares, cf_stop_p, cf_target_p = calculate_counterfactual_buy(
        buy,
        atr_14=20.0,
        account_value_rupees=100000.0,
        min_atr_multiplier=1.5,
        target_risk_pct=0.75,
        max_position_pct=10.0,
    )
    assert cf_shares == 9
    assert cf_stop_p == 97000
    assert cf_target_p == 106500  # 1005 + 3*20 = 1065.0 -> 106500 paise

    # Exact match -> fidelity 1.0
    assert compute_sizing_fidelity_score(9, 9) == 1.0
    # LLM output 12 shares vs 9 expected -> diff = 3 -> 1 - (3/9) = 0.6667
    assert compute_sizing_fidelity_score(12, 9) == 0.6667
    # 0 or negative -> 0.0
    assert compute_sizing_fidelity_score(0, 9) == 0.0


def test_calibrate_buy_decision_parkinson_volatility():
    buy = BuyDecision(
        ticker="TATAMOTORS",
        action="BUY",
        shares=20,
        entry_low=1000.0,
        entry_high=1005.0,
        stop_loss_price=970.0,
        target_price=1100.0,
        pre_mortem_risk="slowdown",
        reasoning="uptrend",
    )
    # atr_14 = 10.0, min_atr_multiplier = 2.0 -> ATR stop distance = 20.0
    # Current stop is 970.0 (distance 30.0).
    # With elevated parkinson_vol_ratio = 5.0%:
    # parkinson_stop_distance = 1000.0 * (5.0 / 100.0) * 0.75 = 37.5
    # Wider buffer 37.5 > 30.0 -> calibrated stop = 1000.0 - 37.5 = 962.5
    calibrated = calibrate_buy_decision(
        buy,
        atr_14=10.0,
        min_atr_multiplier=2.0,
        account_value_rupees=100000.0,
        parkinson_vol_ratio=5.0,
    )
    assert calibrated.stop_loss_price == 962.5


def test_validate_arithmetic_coherence():
    # Coherent decision
    valid_buy = BuyDecision(
        ticker="INFY",
        action="BUY",
        shares=10,
        entry_low=1000.0,
        entry_high=1020.0,
        stop_loss_price=950.0,  # risk = 1020 - 950 = 70
        target_price=1160.0,  # reward = 1160 - 1020 = 140 (RRR = 2.0)
        pre_mortem_risk="slowdown",
        reasoning="uptrend",
    )
    coh = validate_arithmetic_coherence(valid_buy)
    assert coh["is_coherent"] is True
    assert coh["flags"] == []
    assert coh["implied_rrr"] == 2.0

    # Inverted bounds (stop above entry bypassed via model_copy)
    inverted_buy = valid_buy.model_copy(update={"stop_loss_price": 1050.0})
    coh_inv = validate_arithmetic_coherence(inverted_buy)
    assert coh_inv["is_coherent"] is False
    assert "INVERTED_STOP_ABOVE_ENTRY" in coh_inv["flags"]

    # Sub-1 RRR (reward < risk)
    poor_rrr_buy = BuyDecision(
        ticker="INFY",
        action="BUY",
        shares=10,
        entry_low=1000.0,
        entry_high=1020.0,
        stop_loss_price=920.0,  # risk = 100
        target_price=1050.0,  # reward = 30 (RRR = 0.3)
        pre_mortem_risk="slowdown",
        reasoning="uptrend",
    )
    coh_rrr = validate_arithmetic_coherence(poor_rrr_buy)
    assert coh_rrr["is_coherent"] is False
    assert "NEGATIVE_ASYMMETRY_RRR_SUB_1" in coh_rrr["flags"]
