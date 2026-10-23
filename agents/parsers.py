"""
Validates the LLM's JSON decision output and performs the single allowed repair retry.
See Plan_v3 §3.3.
"""
import json
import logging
import re
from typing import List, Tuple

from pydantic import ValidationError

from core.schemas import DecisionBatch, DecisionUnion, HoldDecision
from llm.client import LLMClient, LLMResult

logger = logging.getLogger(__name__)

_CODE_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE | re.MULTILINE)

NO_DECISION_REASON = "no decision returned"
DOUBLE_FAILURE_REASON = "LLM response failed validation twice; defaulting to HOLD"


class ParseFailure(Exception):
    """Raw text was not valid JSON, or failed DecisionBatch validation."""


def strip_code_fences(text: str) -> str:
    """Removes a leading/trailing ``` or ```json fence, if present."""
    return _CODE_FENCE_RE.sub("", text.strip()).strip()


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


def parse_with_repair(
    llm_client: LLMClient, system_prompt: str, user_prompt: str, first_result: LLMResult,
    candidates: List[str],
) -> Tuple[List[DecisionUnion], str, List[str], LLMResult]:
    """Parses `first_result.text`. On failure, sends the validation error back to the model for
    one repair retry. If that also fails, every candidate gets a HOLD decision.
    Returns (decisions, parse_status, dropped_unknown_tickers, final_llm_result)."""
    try:
        decisions, dropped = parse_decisions(first_result.text, candidates)
        return fill_missing_with_hold(decisions, candidates), "SUCCESS", dropped, first_result
    except ParseFailure as first_error:
        repair_user_prompt = (
            f"{user_prompt}\n\n"
            "Your previous response failed validation with this error:\n"
            f"{first_error}\n\n"
            "Return ONLY corrected JSON matching the exact schema, with no extra commentary "
            "and no code fences."
        )
        repair_result = llm_client.complete(system_prompt, repair_user_prompt)
        try:
            decisions, dropped = parse_decisions(repair_result.text, candidates)
            return fill_missing_with_hold(decisions, candidates), "RETRY_SUCCESS", dropped, repair_result
        except ParseFailure:
            hold_all = [HoldDecision(ticker=t, action="HOLD", reasoning=DOUBLE_FAILURE_REASON) for t in candidates]
            return hold_all, "FAILED", [], repair_result
