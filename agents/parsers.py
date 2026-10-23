"""
Validates the LLM's JSON decision output and performs the single allowed retry: a truncation
retry (lower reasoning effort, higher max output tokens, no repair message) when the first
attempt was cut off, or a schema-repair retry (validation error sent back to the model) when it
wasn't. At most 2 LLM calls total; a second failure always falls through to HOLD-all.
See Plan_v3 §3.3.
"""
import json
import logging
import re
from typing import List, Optional, Tuple

from pydantic import ValidationError

from core.schemas import DecisionBatch, DecisionUnion, HoldDecision
from llm.client import LLMClient, LLMResult, step_down_reasoning_effort
from settings import settings

logger = logging.getLogger(__name__)

_CODE_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE | re.MULTILINE)

NO_DECISION_REASON = "no decision returned"
DOUBLE_FAILURE_REASON = "LLM response failed validation twice; defaulting to HOLD"
TRUNCATION_RETRY_MAX_OUTPUT_TOKENS_MULTIPLIER = 2


class ParseFailure(Exception):
    """Raw text was not valid JSON, or failed DecisionBatch validation."""


def strip_code_fences(text: str) -> str:
    """Removes a leading/trailing ``` or ```json fence, if present."""
    return _CODE_FENCE_RE.sub("", text.strip()).strip()


def is_truncated(result: LLMResult) -> bool:
    """A failed attempt due to truncation: empty content, or finish_reason == 'length'
    (confirmed against the real Groq API: a cut-off reasoning-heavy response can report either,
    or both)."""
    return not (result.text or "").strip() or result.finish_reason == "length"


def parse_decisions(raw_text: str, candidates: List[str]) -> Tuple[List[DecisionUnion], List[str]]:
    """Parses and validates one LLM response. Returns (decisions, dropped_unknown_tickers).
    Raises ParseFailure on invalid JSON or a schema validation error."""
    cleaned = strip_code_fences(raw_text)
    try:
        data = json.loads(cleaned)
        batch = DecisionBatch.model_validate(data)
    except (json.JSONDecodeError, ValidationError) as exc:
        raise ParseFailure(str(exc)) from exc

    valid_set = set(candidates)
    decisions, dropped = [], []
    for d in batch.decisions:
        if d.ticker not in valid_set:
            dropped.append(d.ticker)
            logger.warning("Dropping decision for unknown ticker %r (not in candidate pool)", d.ticker)
            continue
        decisions.append(d)
    return decisions, dropped


def fill_missing_with_hold(decisions: List[DecisionUnion], candidates: List[str]) -> List[DecisionUnion]:
    """Every candidate the LLM didn't return a decision for gets a HOLD row with the exact
    reason 'no decision returned'."""
    present = {d.ticker for d in decisions}
    filled = list(decisions)
    for ticker in candidates:
        if ticker not in present:
            filled.append(HoldDecision(ticker=ticker, action="HOLD", reasoning=NO_DECISION_REASON))
    return filled


def _hold_all(candidates: List[str]) -> List[HoldDecision]:
    return [HoldDecision(ticker=t, action="HOLD", reasoning=DOUBLE_FAILURE_REASON) for t in candidates]


def parse_with_repair(
    llm_client: LLMClient, system_prompt: str, user_prompt: str, first_result: LLMResult,
    candidates: List[str], reasoning_effort: Optional[str] = None,
    max_output_tokens: Optional[int] = None, response_schema: Optional[dict] = None,
) -> Tuple[List[DecisionUnion], str, List[str], LLMResult, List[dict]]:
    """Classifies `first_result` and, if it failed, makes at most one more call (2 total):
    - Truncated (empty content or finish_reason == 'length'): retries with a lower reasoning
      effort and `TRUNCATION_RETRY_MAX_OUTPUT_TOKENS_MULTIPLIER`x max_output_tokens, re-sending
      the ORIGINAL prompt unchanged -- no repair message for a truncation failure.
    - Invalid JSON / schema error (not truncated): retries with the validation error appended
      to the prompt (the repair-message behaviour).
    A second failure of either kind always falls through to HOLD-all with parse_status FAILED;
    there is never a third call.
    Returns (decisions, overall_parse_status, dropped_unknown_tickers, final_result, attempts),
    where `attempts` is a log entry per actual LLM call made:
    [{"result": LLMResult, "parse_status": "SUCCESS"|"RETRY_SUCCESS"|"FAILED"}, ...] -- the
    caller logs each one to llm_calls."""
    reasoning_effort = reasoning_effort or settings.LLM_REASONING_EFFORT
    max_output_tokens = max_output_tokens or settings.LLM_MAX_OUTPUT_TOKENS

    if is_truncated(first_result):
        retry_effort = step_down_reasoning_effort(reasoning_effort)
        retry_max_tokens = max_output_tokens * TRUNCATION_RETRY_MAX_OUTPUT_TOKENS_MULTIPLIER
        second_result = llm_client.complete(
            system_prompt, user_prompt, reasoning_effort=retry_effort,
            max_output_tokens=retry_max_tokens, response_schema=response_schema,
        )
        if is_truncated(second_result):
            attempts = [{"result": first_result, "parse_status": "FAILED"}, {"result": second_result, "parse_status": "FAILED"}]
            return _hold_all(candidates), "FAILED", [], second_result, attempts
        try:
            decisions, dropped = parse_decisions(second_result.text, candidates)
            attempts = [{"result": first_result, "parse_status": "FAILED"}, {"result": second_result, "parse_status": "RETRY_SUCCESS"}]
            return fill_missing_with_hold(decisions, candidates), "RETRY_SUCCESS", dropped, second_result, attempts
        except ParseFailure:
            attempts = [{"result": first_result, "parse_status": "FAILED"}, {"result": second_result, "parse_status": "FAILED"}]
            return _hold_all(candidates), "FAILED", [], second_result, attempts

    try:
        decisions, dropped = parse_decisions(first_result.text, candidates)
        attempts = [{"result": first_result, "parse_status": "SUCCESS"}]
        return fill_missing_with_hold(decisions, candidates), "SUCCESS", dropped, first_result, attempts
    except ParseFailure as first_error:
        repair_user_prompt = (
            f"{user_prompt}\n\n"
            "Your previous response failed validation with this error:\n"
            f"{first_error}\n\n"
            "Return ONLY corrected JSON matching the exact schema, with no extra commentary "
            "and no code fences."
        )
        repair_result = llm_client.complete(
            system_prompt, repair_user_prompt, reasoning_effort=reasoning_effort,
            max_output_tokens=max_output_tokens, response_schema=response_schema,
        )
        if is_truncated(repair_result):
            attempts = [{"result": first_result, "parse_status": "FAILED"}, {"result": repair_result, "parse_status": "FAILED"}]
            return _hold_all(candidates), "FAILED", [], repair_result, attempts
        try:
            decisions, dropped = parse_decisions(repair_result.text, candidates)
            attempts = [{"result": first_result, "parse_status": "FAILED"}, {"result": repair_result, "parse_status": "RETRY_SUCCESS"}]
            return fill_missing_with_hold(decisions, candidates), "RETRY_SUCCESS", dropped, repair_result, attempts
        except ParseFailure:
            attempts = [{"result": first_result, "parse_status": "FAILED"}, {"result": repair_result, "parse_status": "FAILED"}]
            return _hold_all(candidates), "FAILED", [], repair_result, attempts
