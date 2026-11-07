"""
Validates the LLM's JSON decision output and performs the single allowed retry: a truncation
retry (lower reasoning effort, higher max output tokens, no repair message) when the first
attempt was cut off, or a schema-repair retry (validation error sent back to the model) when it
wasn't. At most 2 LLM calls total; a second failure always falls through to HOLD-all.

`parse_with_repair_and_fallback` wraps this with Day 5a's fallback rule: the primary gets its
own 2-call retry budget first; only if it still fails (a raised exception -- network/429-after-
backoff/5xx -- or the double parse/truncation failure) does the fallback provider get exactly
one attempt with the ORIGINAL prompt. At most 3 LLM calls total; the fallback is never consulted
when the primary succeeded.
See Plan_v3 §3.3.
"""

import json
import logging
import re
from typing import Any

from pydantic import ValidationError

from core.config import settings
from core.schemas import BuyDecision, DecisionBatch, DecisionUnion, HoldDecision
from llm.client import LLMClient, LLMResult, step_down_reasoning_effort

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


def parse_decisions(raw_text: str, candidates: list[str]) -> tuple[list[DecisionUnion], list[str]]:
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


def fill_missing_with_hold(decisions: list[DecisionUnion], candidates: list[str]) -> list[DecisionUnion]:
    """Every candidate the LLM didn't return a decision for gets a HOLD row with the exact
    reason 'no decision returned'."""
    present = {d.ticker for d in decisions}
    filled = list(decisions)
    for ticker in candidates:
        if ticker not in present:
            filled.append(HoldDecision(ticker=ticker, action="HOLD", reasoning=NO_DECISION_REASON))
    return filled


def _hold_all(candidates: list[str]) -> list[DecisionUnion]:
    return [HoldDecision(ticker=t, action="HOLD", reasoning=DOUBLE_FAILURE_REASON) for t in candidates]


def parse_with_repair(
    llm_client: LLMClient,
    system_prompt: str,
    user_prompt: str,
    first_result: LLMResult,
    candidates: list[str],
    reasoning_effort: str | None = None,
    max_output_tokens: int | None = None,
    response_schema: dict | None = None,
) -> tuple[list[DecisionUnion], str, list[str], LLMResult, list[dict]]:
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
            system_prompt,
            user_prompt,
            reasoning_effort=retry_effort,
            max_output_tokens=retry_max_tokens,
            response_schema=response_schema,
        )
        if is_truncated(second_result):
            attempts = [
                {"result": first_result, "parse_status": "FAILED"},
                {"result": second_result, "parse_status": "FAILED"},
            ]
            return _hold_all(candidates), "FAILED", [], second_result, attempts
        try:
            decisions, dropped = parse_decisions(second_result.text, candidates)
            attempts = [
                {"result": first_result, "parse_status": "FAILED"},
                {"result": second_result, "parse_status": "RETRY_SUCCESS"},
            ]
            return fill_missing_with_hold(decisions, candidates), "RETRY_SUCCESS", dropped, second_result, attempts
        except ParseFailure:
            attempts = [
                {"result": first_result, "parse_status": "FAILED"},
                {"result": second_result, "parse_status": "FAILED"},
            ]
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
            system_prompt,
            repair_user_prompt,
            reasoning_effort=reasoning_effort,
            max_output_tokens=max_output_tokens,
            response_schema=response_schema,
        )
        if is_truncated(repair_result):
            attempts = [
                {"result": first_result, "parse_status": "FAILED"},
                {"result": repair_result, "parse_status": "FAILED"},
            ]
            return _hold_all(candidates), "FAILED", [], repair_result, attempts
        try:
            decisions, dropped = parse_decisions(repair_result.text, candidates)
            attempts = [
                {"result": first_result, "parse_status": "FAILED"},
                {"result": repair_result, "parse_status": "RETRY_SUCCESS"},
            ]
            return fill_missing_with_hold(decisions, candidates), "RETRY_SUCCESS", dropped, repair_result, attempts
        except ParseFailure:
            attempts = [
                {"result": first_result, "parse_status": "FAILED"},
                {"result": repair_result, "parse_status": "FAILED"},
            ]
            return _hold_all(candidates), "FAILED", [], repair_result, attempts


def parse_with_repair_and_fallback(
    primary: LLMClient,
    system_prompt: str,
    user_prompt: str,
    candidates: list[str],
    fallback: LLMClient | None = None,
    reasoning_effort: str | None = None,
    max_output_tokens: int | None = None,
    response_schema: dict | None = None,
) -> tuple[list[DecisionUnion], str, list[str], LLMResult | None, list[dict]]:
    """Makes the primary's first call, runs its own retry via `parse_with_repair`, and -- only if
    the primary raised (after its own HTTP-level backoff) or still failed after its retry -- gives
    `fallback` exactly one attempt with the original, unmodified prompt. Never touches `fallback`
    when the primary succeeds, and never gives the primary a third call. Each returned `attempts`
    entry gains a "fallback_used" key for llm_calls logging."""
    reasoning_effort = reasoning_effort or settings.LLM_REASONING_EFFORT
    max_output_tokens = max_output_tokens or settings.LLM_MAX_OUTPUT_TOKENS

    primary_exc = None
    decisions: list[DecisionUnion] = _hold_all(candidates)
    status: str = "FAILED"
    dropped: list[str] = []
    final_result: LLMResult | None = None
    attempts: list[dict] = []
    try:
        first_result = primary.complete(
            system_prompt,
            user_prompt,
            reasoning_effort=reasoning_effort,
            max_output_tokens=max_output_tokens,
            response_schema=response_schema,
        )
        decisions, status, dropped, final_result, attempts = parse_with_repair(
            primary,
            system_prompt,
            user_prompt,
            first_result,
            candidates,
            reasoning_effort=reasoning_effort,
            max_output_tokens=max_output_tokens,
            response_schema=response_schema,
        )
    except Exception as exc:
        primary_exc = exc

    for attempt in attempts:
        attempt["fallback_used"] = False

    if primary_exc is None and status != "FAILED":
        return decisions, status, dropped, final_result, attempts

    if fallback is None:
        if primary_exc is not None:
            raise primary_exc
        return decisions, status, dropped, final_result, attempts

    try:
        fallback_result = fallback.complete(
            system_prompt,
            user_prompt,
            reasoning_effort=reasoning_effort,
            max_output_tokens=max_output_tokens,
            response_schema=response_schema,
        )
    except Exception as fallback_exc:
        if primary_exc is not None:
            raise fallback_exc from primary_exc
        return decisions, status, dropped, final_result, attempts  # primary's own HOLD-all stands

    if not is_truncated(fallback_result):
        try:
            fb_decisions, fb_dropped = parse_decisions(fallback_result.text, candidates)
            attempts.append({"result": fallback_result, "parse_status": "FALLBACK_SUCCESS", "fallback_used": True})
            return (
                fill_missing_with_hold(fb_decisions, candidates),
                "FALLBACK_SUCCESS",
                fb_dropped,
                fallback_result,
                attempts,
            )
        except ParseFailure:
            pass

    attempts.append({"result": fallback_result, "parse_status": "FAILED", "fallback_used": True})
    if primary_exc is not None:
        decisions, status, dropped = _hold_all(candidates), "FAILED", []
    return decisions, status, dropped, fallback_result, attempts


def calibrate_buy_decision(
    decision: BuyDecision,
    atr_14: float | None,
    min_atr_multiplier: float = 2.0,
    account_value_rupees: float | None = None,
    max_risk_pct: float = 1.0,
    max_position_pct: float = 20.0,
    parkinson_vol_ratio: float | None = None,
) -> BuyDecision:
    """
    Calibrates a BUY decision's stop_loss_price and shares against volatility (ATR-14 / Parkinson extreme-value)
    and risk parameters:
    1. If atr_14 is present and positive, ensures:
       (entry_low - stop_loss_price) >= min_atr_multiplier * atr_14.
       If parkinson_vol_ratio is elevated (> 3.0%), buffers stop distance by 0.75x extreme-value volatility.
       If tighter than this floor, clamps stop_loss_price to (entry_low - min_stop_distance).
    2. Recalculates/caps shares so total risk does not exceed max_risk_pct (default 1%)
       and max_position_pct (default 20%) of account_value_rupees.
    """
    if not isinstance(decision, BuyDecision):
        return decision

    stop_loss = decision.stop_loss_price
    shares = decision.shares

    # 1. Volatility ATR and Parkinson extreme-value floor check
    if atr_14 is not None and atr_14 > 0:
        min_stop_distance = round(min_atr_multiplier * float(atr_14), 2)
        if parkinson_vol_ratio is not None and parkinson_vol_ratio > 3.0:
            parkinson_distance = round(decision.entry_low * (parkinson_vol_ratio / 100.0) * 0.75, 2)
            min_stop_distance = max(min_stop_distance, parkinson_distance)

        current_distance = decision.entry_low - stop_loss
        if current_distance < (min_stop_distance - 0.10):
            calibrated_stop = round(decision.entry_low - min_stop_distance, 2)
            if calibrated_stop <= 0:
                calibrated_stop = round(decision.entry_low * 0.90, 2)
            if 0 < calibrated_stop < decision.entry_low and abs(calibrated_stop - stop_loss) >= 0.10:
                logger.info(
                    "Calibrating stop for %s: widened from %.2f to %.2f (%.1fx ATR-14 floor %.2f, parkinson_vol=%.2f%%)",
                    decision.ticker,
                    stop_loss,
                    calibrated_stop,
                    min_atr_multiplier,
                    min_stop_distance,
                    parkinson_vol_ratio or 0.0,
                )
                stop_loss = calibrated_stop

    # 2. Risk sizing check (1% capital risk, 20% position cap)
    if account_value_rupees is not None and account_value_rupees > 0:
        risk_per_share = max(0.01, decision.entry_high - stop_loss)
        max_risk_rupees = account_value_rupees * (max_risk_pct / 100.0)
        shares_by_risk = int(max_risk_rupees // risk_per_share)

        max_position_rupees = account_value_rupees * (max_position_pct / 100.0)
        shares_by_cap = int(max_position_rupees // decision.entry_high)

        max_allowed_shares = min(shares_by_risk, shares_by_cap)
        shares_tolerance_ceiling = int(max_allowed_shares * 1.10)
        if max_allowed_shares >= 1 and shares > shares_tolerance_ceiling:
            logger.info(
                "Calibrating shares for %s: reduced from %d to %d (risk cap %.1f%% / max pos %.1f%%)",
                decision.ticker,
                shares,
                max_allowed_shares,
                max_risk_pct,
                max_position_pct,
            )
            shares = max_allowed_shares

    if stop_loss != decision.stop_loss_price or shares != decision.shares:
        return decision.model_copy(update={"stop_loss_price": stop_loss, "shares": shares})

    return decision


def validate_arithmetic_coherence(decision: BuyDecision) -> dict[str, Any]:
    """
    Validates internal mathematical and directional coherence of a BUY decision:
    1. Bounds coherence: entry_high >= entry_low > 0
    2. Long direction coherence: stop_loss_price < entry_low and target_price > entry_high
    3. Implied Risk-Reward Ratio (RRR): (target_price - entry_high) / max(0.01, entry_high - stop_loss_price)
    4. Sizing coherence: shares > 0
    Returns a telemetry dictionary with flags and the computed RRR.
    """
    flags: list[str] = []
    entry_low = decision.entry_low
    entry_high = decision.entry_high
    stop = decision.stop_loss_price
    target = decision.target_price
    shares = decision.shares

    if entry_low <= 0 or entry_high < entry_low:
        flags.append("INVALID_ENTRY_RANGE")

    if stop >= entry_low:
        flags.append("INVERTED_STOP_ABOVE_ENTRY")

    if target <= entry_high:
        flags.append("INVERTED_TARGET_BELOW_ENTRY")

    risk = max(0.01, entry_high - stop)
    reward = max(0.0, target - entry_high)
    implied_rrr = round(reward / risk, 2) if risk > 0 else 0.0

    if implied_rrr < 1.0 and "INVERTED_TARGET_BELOW_ENTRY" not in flags:
        flags.append("NEGATIVE_ASYMMETRY_RRR_SUB_1")

    if shares <= 0:
        flags.append("ZERO_OR_NEGATIVE_SHARES")

    is_coherent = len(flags) == 0
    if not is_coherent:
        logger.warning(
            "Arithmetic coherence anomaly in decision for %s: flags=%s, entry=[%.2f, %.2f], stop=%.2f, target=%.2f, rrr=%.2f",
            decision.ticker,
            flags,
            entry_low,
            entry_high,
            stop,
            target,
            implied_rrr,
        )

    return {
        "is_coherent": is_coherent,
        "flags": flags,
        "implied_rrr": implied_rrr,
        "risk_per_share": round(risk, 2),
        "reward_per_share": round(reward, 2),
    }


def calibrate_decisions(
    decisions: list[DecisionUnion],
    features_by_ticker: dict[str, dict],
    min_atr_multiplier: float = 2.0,
    account_value_rupees: float | None = None,
    max_risk_pct: float = 1.0,
    max_position_pct: float = 20.0,
) -> list[DecisionUnion]:
    """Applies calibrate_buy_decision to all BuyDecision items in decisions."""
    calibrated = []
    for d in decisions:
        if isinstance(d, BuyDecision):
            validate_arithmetic_coherence(d)
            feat = features_by_ticker.get(d.ticker, {})
            atr_14 = feat.get("atr_14")
            parkinson_vol = feat.get("parkinson_vol_ratio")
            d = calibrate_buy_decision(
                d,
                atr_14=atr_14,
                min_atr_multiplier=min_atr_multiplier,
                account_value_rupees=account_value_rupees,
                max_risk_pct=max_risk_pct,
                max_position_pct=max_position_pct,
                parkinson_vol_ratio=parkinson_vol,
            )
        calibrated.append(d)
    return calibrated


def calculate_counterfactual_buy(
    decision: BuyDecision,
    atr_14: float | None,
    account_value_rupees: float,
    min_atr_multiplier: float = 1.5,
    target_risk_pct: float = 0.75,
    max_position_pct: float = 10.0,
) -> tuple[int, int, int]:
    """
    Computes strict formulaic shadow sizing for a given BuyDecision:
    - stop: entry_low - min_atr_multiplier * atr_14
    - shares: floor(min(risk_shares, cap_shares))
    - target: entry_high + 3.0 * atr_14
    Returns (shares, stop_paise, target_paise).
    """
    from core.money import rupees_to_paise

    stop_price = decision.stop_loss_price
    if atr_14 is not None and atr_14 > 0:
        stop_dist = min_atr_multiplier * float(atr_14)
        stop_price = round(decision.entry_low - stop_dist, 2)
        if stop_price <= 0:
            stop_price = round(decision.entry_low * 0.90, 2)

    risk_per_share = max(0.01, decision.entry_high - stop_price)
    max_risk_rupees = account_value_rupees * (target_risk_pct / 100.0)
    shares_by_risk = int(max_risk_rupees // risk_per_share)

    max_position_rupees = account_value_rupees * (max_position_pct / 100.0)
    shares_by_cap = int(max_position_rupees // decision.entry_high)

    shares = max(1, min(shares_by_risk, shares_by_cap))
    target_price = decision.target_price
    if atr_14 is not None and atr_14 > 0:
        target_price = round(decision.entry_high + 3.0 * float(atr_14), 2)

    return shares, rupees_to_paise(stop_price), rupees_to_paise(target_price)


def compute_sizing_fidelity_score(actual_shares: int | None, expected_shares: int | None) -> float | None:
    """
    Measures arithmetic self-consistency between actual LLM shares and expected formulaic shares.
    Score = 1.0 - min(1.0, abs(actual - expected) / expected).
    Returns score in [0.0, 1.0].
    """
    if actual_shares is None or expected_shares is None or expected_shares <= 0 or actual_shares <= 0:
        return 0.0
    diff = abs(actual_shares - expected_shares)
    return round(max(0.0, 1.0 - (diff / expected_shares)), 4)
