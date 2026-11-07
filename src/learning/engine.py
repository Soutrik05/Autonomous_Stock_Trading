"""
Weekly reflection job (Sunday 10:00 IST, see Plan_v3 §5.4): reads each LLM persona's newly
closed, forensics-classified trades since its own watermark, asks an LLM to propose new
testable heuristics from that evidence, validates and inserts the valid ones into agent_memory,
then advances the watermark -- all for one agent in a single transaction, so the watermark
never moves without the heuristics it's paired with. Skips the baseline agent (no LLM).

The LLM call reuses llm/client.py's provider classes and agents/parsers.py's truncation
detection (is_truncated, step_down_reasoning_effort, strip_code_fences) but cannot call
agents.parsers.parse_with_repair_and_fallback directly -- that function is hard-coded to the
DecisionBatch schema (candidates list, HOLD fill-in, etc.). _call_llm_for_reflection below
mirrors its exact shape instead (the primary's own 2-call retry budget, then one fallback
attempt with the original prompt, 3 calls total) for the heuristics JSON shape.
See Plan_v3 §5.4-§5.5.
"""

import json
import logging

from agents.parsers import is_truncated, strip_code_fences
from agents.personas import all_personas
from core.clock import Clock
from core.config import settings
from core.database import get_connection
from evaluation.forensics_mining import extract_forensics_summary
from features.contracts import (
    FEATURE_REGISTRY,
    evaluate_predicate,
    persona_allowed_metric_names,
    predicate_feature_names,
)
from learning.forensics import LOSS_LABELS, SECONDARY_TAGS, WIN_LABELS, fetch_forward_sessions
from learning.prompts import (
    build_reflection_repair_prompt,
    build_reflection_system_prompt,
    build_reflection_user_prompt,
)
from llm.client import LLMClient, LLMConfigError, LLMResult, build_provider, require_setting, step_down_reasoning_effort

logger = logging.getLogger(__name__)

_MAX_HEURISTIC_TEXT_LEN = 200
_FEATURE_UNIT_BY_NAME = {f.name: f.unit for f in FEATURE_REGISTRY}


# ---------------------------------------------------------------------------
# Sample feature dict (for "evaluate_predicate runs on a sample dict without error")
# ---------------------------------------------------------------------------


def _sample_value_for(name: str):
    unit = _FEATURE_UNIT_BY_NAME.get(name)
    if unit == "flag":
        return True
    if unit == "-1/0/+1":
        return 1
    if unit == "label":
        return "NORMAL"
    return 50.0


def _sample_features(allowed_metrics: list[str]) -> dict:
    return {name: _sample_value_for(name) for name in allowed_metrics}


# ---------------------------------------------------------------------------
# Watermark / eligible trades / existing heuristics
# ---------------------------------------------------------------------------


def _latest_watermark(conn, agent_id: str) -> tuple[str | None, int]:
    """The watermark is keyed by (exit_date, position_id) -- see _load_eligible_trades for why.
    (None, 0) means "nothing reviewed yet" (no prior row, or a pre-migration-0007 row whose new
    columns are still NULL)."""
    row = conn.execute(
        "SELECT last_exit_date_reviewed, last_position_id_in_that_exit_order "
        "FROM reflection_runs WHERE agent_id = ? ORDER BY id DESC LIMIT 1",
        (agent_id,),
    ).fetchone()
    if row is None or row["last_exit_date_reviewed"] is None:
        return None, 0
    return row["last_exit_date_reviewed"], row["last_position_id_in_that_exit_order"]


def _load_entry_features(conn, entry_decision_id: int | None) -> dict | None:
    if entry_decision_id is None:
        return None
    row = conn.execute(
        "SELECT fs.features_json FROM decisions d JOIN feature_snapshots fs ON fs.id = d.snapshot_id WHERE d.id = ?",
        (entry_decision_id,),
    ).fetchone()
    return json.loads(row["features_json"]) if row else None


def _is_post_exit_ready(ohlcv_conn, ticker: str, exit_date: str, as_of_date: str) -> bool:
    """True once settings.POST_EXIT_SHORT_DAYS trading sessions have passed since exit_date, by
    the exact same count learning/forensics.py's enrich_post_exit uses -- so the two always
    agree on what "ready" means."""
    sessions = fetch_forward_sessions(
        ohlcv_conn,
        ticker,
        exit_date,
        as_of_date,
        limit=settings.POST_EXIT_SHORT_DAYS,
    )
    return len(sessions) >= settings.POST_EXIT_SHORT_DAYS


def _build_trade_dict(conn, r) -> dict:
    diagnosis = {}
    if r["diagnosis_json"]:
        try:
            diagnosis = json.loads(r["diagnosis_json"])
        except (json.JSONDecodeError, TypeError):
            diagnosis = {}
    return {
        "position_id": r["id"],
        "ticker": r["ticker"],
        "entry_date": r["entry_date"],
        "exit_date": r["exit_date"],
        "hold_days": r["hold_days"],
        "realized_pnl_pct": r["realized_pnl_pct"] or 0.0,
        "exit_reason": r["exit_reason"],
        "forensics_type": r["forensics_type"],
        "diagnosis_reason": diagnosis.get("reason"),
        "entry_features": _load_entry_features(conn, r["entry_decision_id"]),
        "mae_pct": diagnosis.get("mae_pct"),
        "mfe_pct": diagnosis.get("mfe_pct"),
        "profit_given_back_pct": diagnosis.get("profit_given_back_pct"),
        "run_up_before_entry_pct": diagnosis.get("run_up_before_entry_pct"),
        "largest_gap_down_pct": diagnosis.get("largest_gap_down_pct"),
        "secondary_tags": diagnosis.get("secondary_tags") or [],
        "post_exit": diagnosis.get("post_exit"),
    }


def _load_eligible_trades(
    conn,
    ohlcv_conn,
    agent_id: str,
    watermark: tuple[str | None, int],
    lookback_days: int,
    as_of_date: str,
) -> tuple[list[dict], str | None, int]:
    """Positions closed after the watermark, within lookback_days (calendar days, counted back
    from as_of_date) of their exit_date, AND whose post-exit data is ready (see
    _is_post_exit_ready).

    Walks CLOSED positions ordered by (exit_date, id) -- EXIT order, not entry/id order, so one
    slow persona's long-held OPEN position (which could have a low id but close months later)
    never blocks anything: open positions are simply never candidates at all (excluded by the
    `status = 'CLOSED'` filter itself, not by scanning past them).

    Stops advancing the moment it hits a CLOSED position that isn't reviewable YET:
      - too recent for post-exit data (see _is_post_exit_ready). Because the walk is ordered by
        exit_date, every later position closed on the same day or later, so it has had the same
        or less time to mature -- it is ALSO not ready. Nothing after this point can be skipped
        by mistake; stopping here is exactly as complete as scanning further would be.
      - forensics_type IS NULL (forensics hasn't run yet, or failed to write anything -- in
        practice forensics.run() always falls back to UNCLASSIFIED on error, so this should be
        rare/transient). This does NOT share the above monotonicity argument -- a later-exit
        trade could easily have forensics done while an earlier one doesn't. Chosen behaviour
        (documented, not just coded): still STOP here rather than skip-and-continue. The
        alternative -- filtering it out of the candidate query entirely like an open position --
        would let a LATER trade's successful review advance the watermark past this one's
        exit_date, after which it could never become eligible again even once forensics
        appears. Stopping costs a short delay (this trade and anything exit-dated after it wait
        one more run) but never loses it -- and since forensics runs synchronously at close,
        that delay is normally zero. A logged warning marks this case so it's visible if it
        ever isn't transient.

    Returns (eligible_trades, last_exit_date_reviewed, last_position_id_reviewed) -- the
    watermark to persist on a successful run. A position merely too OLD for the lookback window
    is a separate, PERMANENT exclusion (age only increases with a real clock), so it's left out
    of `eligible` but does not stop the watermark from advancing past it.
    """
    wm_exit_date, wm_position_id = watermark
    rows = conn.execute(
        """
        SELECT id, ticker, entry_date, exit_date, hold_days, realized_pnl_pct, exit_reason,
               forensics_type, diagnosis_json, entry_decision_id,
               (julianday(?) - julianday(exit_date)) AS age_days
        FROM positions
        WHERE agent_id = ? AND status = 'CLOSED' AND exit_date IS NOT NULL
          AND (exit_date > ? OR (exit_date = ? AND id > ?))
        ORDER BY exit_date ASC, id ASC
        """,
        (as_of_date, agent_id, wm_exit_date or "0000-00-00", wm_exit_date or "0000-00-00", wm_position_id),
    ).fetchall()

    trades: list[dict] = []
    last_exit_date, last_position_id = wm_exit_date, wm_position_id
    for r in rows:
        if r["forensics_type"] is None:
            logger.warning(
                "learning.engine: position %s (ticker=%s, exit_date=%s) closed but has no "
                "forensics_type yet; stopping the exit-order scan here so nothing after it is "
                "skipped. Will retry from the same point next run.",
                r["id"],
                r["ticker"],
                r["exit_date"],
            )
            break

        if not _is_post_exit_ready(ohlcv_conn, r["ticker"], r["exit_date"], as_of_date):
            break  # too recent -- everything after it (by exit_date) is too recent as well

        last_exit_date, last_position_id = r["exit_date"], r["id"]  # safe to advance at least this far

        if r["age_days"] is not None and r["age_days"] > lookback_days:
            continue  # permanently too old for this agent's reflection window -- skip, don't block

        trades.append(_build_trade_dict(conn, r))

    return trades, last_exit_date, last_position_id


def _load_existing_heuristics(conn, agent_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT id, kind, context, heuristic_text, status, trigger_json FROM agent_memory WHERE agent_id = ?",
        (agent_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def _write_reflection_run(
    conn,
    agent_id: str,
    as_of_date: str,
    clock: Clock,
    last_exit_date_reviewed: str | None,
    last_position_id_reviewed: int,
    trades_reviewed: int,
    status: str,
) -> None:
    """last_position_id_reviewed is kept populated (equal to last_position_id_reviewed, now
    paired with last_exit_date_reviewed as the real watermark key) so anything that reads only
    the old column still sees a sensible value."""
    conn.execute(
        "INSERT INTO reflection_runs (agent_id, run_date, last_exit_date_reviewed, "
        "last_position_id_in_that_exit_order, last_position_id_reviewed, trades_reviewed, status) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            agent_id,
            as_of_date,
            last_exit_date_reviewed,
            last_position_id_reviewed,
            last_position_id_reviewed,
            trades_reviewed,
            status,
        ),
    )


# ---------------------------------------------------------------------------
# LLM call: mirrors parse_with_repair_and_fallback's shape for a different JSON schema
# ---------------------------------------------------------------------------


def _is_valid_json_object(text: str) -> dict | None:
    try:
        data = json.loads(strip_code_fences(text))
    except (json.JSONDecodeError, TypeError):
        return None
    return data if isinstance(data, dict) and isinstance(data.get("heuristics"), list) else None


def _primary_attempt(
    client: LLMClient,
    system_prompt: str,
    user_prompt: str,
    reasoning_effort: str,
    max_output_tokens: int,
) -> tuple[dict | None, list[LLMResult]]:
    attempts: list[LLMResult] = []
    first = client.complete(
        system_prompt, user_prompt, reasoning_effort=reasoning_effort, max_output_tokens=max_output_tokens
    )
    attempts.append(first)

    if is_truncated(first):
        retry_effort = step_down_reasoning_effort(reasoning_effort)
        retry = client.complete(
            system_prompt,
            user_prompt,
            reasoning_effort=retry_effort,
            max_output_tokens=max_output_tokens * 2,
        )
        attempts.append(retry)
        data = None if is_truncated(retry) else _is_valid_json_object(retry.text)
        return data, attempts

    data = _is_valid_json_object(first.text)
    if data is not None:
        return data, attempts

    repair_prompt = build_reflection_repair_prompt(
        user_prompt,
        "response was not a JSON object with a top-level 'heuristics' array",
    )
    repair = client.complete(
        system_prompt, repair_prompt, reasoning_effort=reasoning_effort, max_output_tokens=max_output_tokens
    )
    attempts.append(repair)
    data = None if is_truncated(repair) else _is_valid_json_object(repair.text)
    return data, attempts


def _call_llm_for_reflection(
    primary: LLMClient,
    fallback: LLMClient | None,
    system_prompt: str,
    user_prompt: str,
) -> tuple[dict | None, list[LLMResult], bool]:
    """Returns (parsed_data_or_None, attempts_made, fallback_used). At most 3 LLM calls total
    (primary's first call, its own one retry, one fallback attempt) -- same budget as the
    nightly decision calls."""
    reasoning_effort = settings.LLM_REASONING_EFFORT
    max_output_tokens = settings.REFLECTION_MAX_TOKENS

    primary_exc = None
    data: dict | None = None
    attempts: list[LLMResult] = []
    try:
        data, attempts = _primary_attempt(primary, system_prompt, user_prompt, reasoning_effort, max_output_tokens)
    except Exception as exc:  # noqa: BLE001 -- network/429-after-backoff/5xx must still try the fallback
        primary_exc = exc

    if primary_exc is None and data is not None:
        return data, attempts, False

    if fallback is None:
        if primary_exc is not None:
            raise primary_exc
        return None, attempts, False

    try:
        fb_result = fallback.complete(
            system_prompt,
            user_prompt,
            reasoning_effort=reasoning_effort,
            max_output_tokens=max_output_tokens,
        )
    except Exception as fb_exc:  # noqa: BLE001
        if primary_exc is not None:
            raise fb_exc from primary_exc
        return None, attempts, True

    attempts.append(fb_result)
    data = None if is_truncated(fb_result) else _is_valid_json_object(fb_result.text)
    return data, attempts, True


def _insert_llm_call(
    conn,
    agent_id: str,
    run_date: str,
    user_prompt: str,
    result: LLMResult,
    parse_status: str,
    fallback_used: bool,
    clock: Clock,
) -> int:
    cur = conn.execute(
        """
        INSERT INTO llm_calls (agent_id, run_date, model, prompt, response, tokens_in, tokens_out,
                                latency_ms, parse_status, finish_reason, reasoning_tokens, created_at,
                                provider, thinking_tokens, fallback_used, purpose)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'reflection')
        """,
        (
            agent_id,
            run_date,
            result.model,
            user_prompt,
            result.text,
            result.tokens_in,
            result.tokens_out,
            result.latency_ms,
            parse_status,
            result.finish_reason,
            result.reasoning_tokens,
            clock.now_iso(),
            result.provider,
            result.thinking_tokens,
            int(fallback_used),
        ),
    )
    return cur.lastrowid


# ---------------------------------------------------------------------------
# Heuristic validation
# ---------------------------------------------------------------------------


def _validate_heuristic(item: dict, allowed_metrics: set) -> tuple[bool, str, str | None]:
    """Returns (is_valid, reason_if_invalid, normalized_trigger_json_if_valid)."""
    if not isinstance(item, dict):
        return False, "item is not an object", None
    kind = item.get("kind")
    if kind not in ("SEEK", "AVOID"):
        return False, f"invalid kind {kind!r}", None
    prescribed_action = item.get("prescribed_action")
    if not isinstance(prescribed_action, str) or not prescribed_action.strip():
        return False, "prescribed_action missing or empty", None
    context = item.get("context")
    if context is None:
        action_upper = prescribed_action.upper()
        if any(w in action_upper for w in ("SELL", "EXIT", "CLOSE", "TRIM")):
            context = "EXIT"
        else:
            context = "ENTRY"
        item["context"] = context
    elif context not in ("ENTRY", "EXIT", "ANY"):
        return False, f"invalid context {context!r}; expected 'ENTRY', 'EXIT', or 'ANY'", None
    text = item.get("heuristic_text")
    if not isinstance(text, str) or not text.strip() or len(text) > _MAX_HEURISTIC_TEXT_LEN:
        return False, "heuristic_text missing, empty, or over 200 characters", None
    trigger = item.get("trigger")
    if not isinstance(trigger, dict) or not trigger:
        return False, "trigger missing or not an object", None

    used_names = predicate_feature_names(trigger)
    if not used_names:
        return False, "trigger references no feature", None
    disallowed = used_names - allowed_metrics
    if disallowed:
        return False, f"trigger uses metric(s) not allowed for this persona: {sorted(disallowed)}", None

    try:
        evaluate_predicate(_sample_features(list(allowed_metrics)), trigger)
    except Exception as exc:  # noqa: BLE001 -- any crash here means the trigger itself is invalid
        return False, f"trigger failed sample evaluation: {exc}", None

    return True, "", json.dumps(trigger, sort_keys=True)


def _log_activity(conn, agent_id: str | None, event_type: str, description: str, metadata: dict, clock: Clock) -> None:
    conn.execute(
        "INSERT INTO activity_log (agent_id, event_type, ticker, description, metadata_json, created_at) "
        "VALUES (?, ?, NULL, ?, ?, ?)",
        (agent_id, event_type, description, json.dumps(metadata), clock.now_iso()),
    )


def _insert_heuristic(conn, agent_id: str, item: dict, clock: Clock) -> int:
    now_iso = clock.now_iso()
    context = item.get("context", "ENTRY")
    cur = conn.execute(
        """
        INSERT INTO agent_memory (agent_id, kind, context, heuristic_text, trigger_json, prescribed_action,
                                   status, confidence, times_triggered, times_successful, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, 'testing', 0.5, 0, 0, ?, ?)
        """,
        (
            agent_id,
            item["kind"],
            context,
            item["heuristic_text"],
            json.dumps(item["trigger"]),
            item["prescribed_action"],
            now_iso,
            now_iso,
        ),
    )
    return cur.lastrowid


# ---------------------------------------------------------------------------
# Per-agent and top-level orchestration
# ---------------------------------------------------------------------------


def _default_providers() -> tuple[LLMClient, LLMClient | None]:
    """Builds the reflection-specific primary/fallback pair from settings.REFLECTION_LLM_* when
    the caller doesn't inject its own clients (e.g. production use outside the scheduler, which
    builds and passes its own). See the Day-5a-style pattern in agents/runner.py::run()."""
    primary_kwargs = {}
    if settings.REFLECTION_LLM_PROVIDER == "gemini":
        primary_kwargs["thinking_budget"] = settings.REFLECTION_GEMINI_THINKING_BUDGET
    primary = build_provider(
        settings.REFLECTION_LLM_PROVIDER,
        model=require_setting(settings.REFLECTION_LLM_MODEL, "REFLECTION_LLM_MODEL"),
        **primary_kwargs,
    )
    fallback = None
    try:
        fallback_kwargs = {}
        if settings.REFLECTION_LLM_FALLBACK_PROVIDER == "gemini":
            fallback_kwargs["thinking_budget"] = settings.REFLECTION_GEMINI_THINKING_BUDGET
        fallback = build_provider(
            settings.REFLECTION_LLM_FALLBACK_PROVIDER,
            model=require_setting(settings.REFLECTION_LLM_FALLBACK_MODEL, "REFLECTION_LLM_FALLBACK_MODEL"),
            **fallback_kwargs,
        )
    except LLMConfigError as exc:
        logger.warning("Reflection fallback provider unavailable (%s); continuing with primary only.", exc)
    return primary, fallback


def _run_one_agent(
    conn, ohlcv_conn, clock: Clock, persona, as_of_date: str, primary: LLMClient, fallback: LLMClient | None
) -> dict:
    agent_id = persona.id
    watermark = _latest_watermark(conn, agent_id)
    wm_exit_date, wm_position_id = watermark
    eligible, last_exit_date, last_position_id = _load_eligible_trades(
        conn,
        ohlcv_conn,
        agent_id,
        watermark,
        persona.lookback_days,
        as_of_date,
    )

    if len(eligible) < settings.MIN_CLOSED_TRADES_FOR_REFLECTION:
        # The sample gate never moves the watermark, exactly as before -- write back the OLD
        # (exit_date, position_id), not whatever _load_eligible_trades scanned up to.
        _write_reflection_run(
            conn,
            agent_id,
            as_of_date,
            clock,
            wm_exit_date,
            wm_position_id,
            len(eligible),
            "SKIPPED_TOO_FEW_TRADES",
        )
        return {
            "status": "SKIPPED_TOO_FEW_TRADES",
            "trades_reviewed": len(eligible),
            "watermark": (wm_exit_date, wm_position_id),
        }

    allowed_metrics = persona_allowed_metric_names(persona.technical_hurdles, persona.fundamental_hurdles)
    allowed_metrics_set = set(allowed_metrics)
    existing = _load_existing_heuristics(conn, agent_id)
    # Dedup key is (kind, context, normalized_trigger) and includes deprecated heuristics:
    # 1. A SEEK and AVOID on the same trigger predicate do NOT collide.
    # 2. ENTRY and EXIT rules on the same trigger do NOT collide.
    # 3. A previously deprecated heuristic cannot be re-inserted verbatim.
    existing_keys = {
        (h["kind"], h.get("context") or "ENTRY", json.dumps(json.loads(h["trigger_json"]), sort_keys=True))
        for h in existing
    }
    deprecated_keys = {
        (h["kind"], h.get("context") or "ENTRY", json.dumps(json.loads(h["trigger_json"]), sort_keys=True))
        for h in existing
        if h["status"] == "deprecated"
    }

    system_prompt = build_reflection_system_prompt(
        persona.name,
        persona.system_prompt,
        allowed_metrics,
        LOSS_LABELS,
        WIN_LABELS,
        SECONDARY_TAGS,
        settings.MAX_NEW_HEURISTICS_PER_REFLECTION,
    )
    forensics_summaries = extract_forensics_summary(conn)
    agent_forensics = forensics_summaries.get(agent_id)
    user_prompt = build_reflection_user_prompt(eligible, existing, forensics_summary=agent_forensics)

    data, attempts, fallback_used = _call_llm_for_reflection(primary, fallback, system_prompt, user_prompt)

    parse_status = "SUCCESS" if data is not None else "FAILED"
    for result in attempts:
        _insert_llm_call(conn, agent_id, as_of_date, user_prompt, result, parse_status, fallback_used, clock)

    if data is None:
        logger.error("learning.engine: reflection LLM call failed for agent %s; watermark left unchanged.", agent_id)
        return {
            "status": "LLM_FAILED",
            "trades_reviewed": len(eligible),
            "watermark": (wm_exit_date, wm_position_id),
        }

    proposed = data.get("heuristics", [])
    accepted: list[dict] = []
    for item in proposed:
        if len(accepted) >= settings.MAX_NEW_HEURISTICS_PER_REFLECTION:
            _log_activity(
                conn,
                agent_id,
                "HEURISTIC_REJECTED",
                f"dropped (beyond the max of {settings.MAX_NEW_HEURISTICS_PER_REFLECTION})",
                {"item": item},
                clock,
            )
            continue

        is_valid, reason, normalized_trigger = _validate_heuristic(item, allowed_metrics_set)
        if not is_valid:
            logger.warning("learning.engine: dropping invalid heuristic for agent %s: %s", agent_id, reason)
            _log_activity(conn, agent_id, "HEURISTIC_REJECTED", reason, {"item": item}, clock)
            continue

        dedup_key = (item["kind"], item.get("context", "ENTRY"), normalized_trigger)
        if dedup_key in existing_keys:
            is_dep = dedup_key in deprecated_keys
            msg = "duplicate of a deprecated heuristic" if is_dep else "duplicate of an existing heuristic"
            logger.warning("learning.engine: dropping duplicate heuristic for agent %s: %s", agent_id, msg)
            _log_activity(conn, agent_id, "HEURISTIC_REJECTED", msg, {"item": item}, clock)
            continue

        existing_keys.add(dedup_key)
        accepted.append(item)

    conn.execute("BEGIN IMMEDIATE")
    try:
        for item in accepted:
            heuristic_id = _insert_heuristic(conn, agent_id, item, clock)
            _log_activity(
                conn,
                agent_id,
                "HEURISTIC_CREATED",
                f"new {item['kind']} heuristic: {item['heuristic_text']}",
                {"heuristic_id": heuristic_id, "kind": item["kind"], "rationale": item.get("rationale", "")},
                clock,
            )
        _write_reflection_run(
            conn, agent_id, as_of_date, clock, last_exit_date, last_position_id, len(eligible), "DONE"
        )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise

    return {
        "status": "DONE",
        "trades_reviewed": len(eligible),
        "watermark": (last_exit_date, last_position_id),
        "heuristics_created": len(accepted),
        "heuristics_proposed": len(proposed),
    }


def run(
    conn,
    clock: Clock,
    llm_client: LLMClient | None = None,
    fallback_client: LLMClient | None = None,
    agent_ids: list[str] | None = None,
    ohlcv_conn=None,
) -> dict:
    """Runs weekly reflection for every LLM persona (never the baseline -- all_personas()
    already excludes it). `llm_client`/`fallback_client` let callers (tests, the scheduler)
    inject their own clients; if `llm_client` is None, a default pair is built from
    settings.REFLECTION_LLM_*. `ohlcv_conn` is used to check each trade's post-exit readiness
    (see _load_eligible_trades); if not supplied, one is opened against settings.OHLCV_DB_PATH
    and closed again before returning. One agent's failure is caught and logged, never stopping
    the others."""
    as_of_date = clock.today().isoformat()
    personas = all_personas()
    if agent_ids is not None:
        personas = [p for p in personas if p.id in agent_ids]

    if llm_client is not None:
        primary, fallback = llm_client, fallback_client
    else:
        primary, fallback = _default_providers()

    owns_ohlcv = ohlcv_conn is None
    if owns_ohlcv:
        ohlcv_conn = get_connection(settings.OHLCV_DB_PATH)

    summary: dict = {"as_of_date": as_of_date, "agents": {}}
    try:
        for persona in personas:
            try:
                summary["agents"][persona.id] = _run_one_agent(
                    conn,
                    ohlcv_conn,
                    clock,
                    persona,
                    as_of_date,
                    primary,
                    fallback,
                )
            except Exception as exc:  # noqa: BLE001 -- one agent's failure must never stop the others
                logger.exception("learning.engine.run: agent %s failed", persona.id)
                summary["agents"][persona.id] = {"status": "ERROR", "detail": str(exc)}
    finally:
        if owns_ohlcv:
            ohlcv_conn.close()

    return summary
