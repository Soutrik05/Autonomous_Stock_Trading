"""
Unit tests for agents/parsers.py: clean JSON, code-fenced JSON, the single repair retry,
double-failure HOLD-all, and unknown-ticker dropping. Uses FakeLLMClient only (no network).
See Plan_v3 §3.3.
"""
import json

from agents.parsers import (
    DOUBLE_FAILURE_REASON,
    NO_DECISION_REASON,
    fill_missing_with_hold,
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


def _result(text: str) -> LLMResult:
    return LLMResult(text=text, tokens_in=10, tokens_out=10, latency_ms=1, model="fake-model")


def test_parses_clean_json():
    decisions, dropped = parse_decisions(VALID_RESPONSE, CANDIDATES)
    assert dropped == []
    assert len(decisions) == 1
    assert decisions[0].ticker == "TATAMOTORS"


def test_parses_code_fenced_json():
    fenced = f"```json\n{VALID_RESPONSE}\n```"
    decisions, dropped = parse_decisions(fenced, CANDIDATES)
    assert len(decisions) == 1


def test_repair_retry_succeeds_after_invalid_json():
    bad_first = _result("not valid json at all")
    llm_client = FakeLLMClient(responses=[VALID_RESPONSE])

    decisions, status, dropped, final_result = parse_with_repair(
        llm_client, "system", "user", bad_first, CANDIDATES
    )

    assert status == "RETRY_SUCCESS"
    assert len(llm_client.calls) == 1  # exactly one repair call, not more
    tickers = {d.ticker for d in decisions}
    assert "TATAMOTORS" in tickers
    assert "RELIANCE" in tickers  # filled in with HOLD, no decision returned


def test_double_failure_gives_hold_all_with_failed_status():
    bad_first = _result("still not json")
    llm_client = FakeLLMClient(responses=["also not json"])

    decisions, status, dropped, final_result = parse_with_repair(
        llm_client, "system", "user", bad_first, CANDIDATES
    )

    assert status == "FAILED"
    assert len(decisions) == len(CANDIDATES)
    assert all(isinstance(d, HoldDecision) for d in decisions)
    assert all(d.reasoning == DOUBLE_FAILURE_REASON for d in decisions)


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
