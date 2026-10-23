"""
Unit tests for agents/parsers.py: clean JSON, code-fenced JSON, the truncation retry (lower
reasoning effort, higher max tokens, no repair message), the schema-repair retry, double-failure
HOLD-all, and unknown-ticker dropping. Uses FakeLLMClient only (no network).
See Plan_v3 §3.3.
"""
import json

from agents.parsers import (
    DOUBLE_FAILURE_REASON,
    NO_DECISION_REASON,
    fill_missing_with_hold,
    is_truncated,
    parse_decisions,
    parse_with_repair,
)
from core.schemas import HoldDecision
from llm.client import FakeLLMClient, LLMResult

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
    return LLMResult(text=text, tokens_in=10, tokens_out=10, latency_ms=1, model="fake-model", finish_reason=finish_reason)


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
        llm_client, "system", "the original user prompt", first, CANDIDATES,
        reasoning_effort="low", max_output_tokens=1000,
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
        llm_client, "system", "user", first, CANDIDATES, reasoning_effort="medium", max_output_tokens=1000,
    )
    assert llm_client.calls[0]["reasoning_effort"] == "low"


def test_truncation_retry_failing_again_gives_hold_all():
    first = _result("", finish_reason="length")
    llm_client = FakeLLMClient(responses=[{"text": "", "finish_reason": "length"}])

    decisions, status, dropped, final_result, attempts = parse_with_repair(
        llm_client, "system", "user", first, CANDIDATES,
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
    response = json.dumps(
        {"decisions": [{"ticker": "NOTACANDIDATE", "action": "HOLD", "reasoning": "n/a"}]}
    )
    decisions, dropped = parse_decisions(response, CANDIDATES)
    assert decisions == []
    assert dropped == ["NOTACANDIDATE"]


def test_fill_missing_with_hold_uses_exact_reason():
    filled = fill_missing_with_hold([], CANDIDATES)
    assert len(filled) == len(CANDIDATES)
    assert all(d.reasoning == NO_DECISION_REASON for d in filled)
