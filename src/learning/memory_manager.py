"""
Evaluates heuristic triggers nightly, resolves PENDING applications from forward returns, and
manages the testing/active/reinforced/deprecated lifecycle. Deterministic Python only -- no LLM
calls (heuristic *generation* is learning/engine.py's job, not this module's).
See Plan_v3 §5.5.
"""

import json
import logging
import math
import sqlite3
from datetime import date

from agents.personas import get_persona
from core.clock import Clock
from core.config import settings
from features.contracts import evaluate_predicate

logger = logging.getLogger(__name__)

_DEFAULT_HORIZON_DAYS = 5  # fallback when the agent has no persona entry (e.g. the baseline).


# ---------------------------------------------------------------------------
# Shared helpers & statistics
# ---------------------------------------------------------------------------


def wilson_score_lower_bound(successes: int, total: int, z: float = 1.645) -> float:
    """Calculates the lower bound of the Wilson score confidence interval.
    For total <= 0, returns 0.0. Guards against promoting rules on small-N noise."""
    if total <= 0:
        return 0.0
    p_hat = successes / total
    z2 = z * z
    denominator = 1.0 + z2 / total
    centre = p_hat + z2 / (2.0 * total)
    spread = z * math.sqrt((p_hat * (1.0 - p_hat) + z2 / (4.0 * total)) / total)
    return max(0.0, (centre - spread) / denominator)


def _log_activity(conn, agent_id: str | None, event_type: str, description: str, metadata: dict, clock: Clock) -> None:
    conn.execute(
        "INSERT INTO activity_log (agent_id, event_type, ticker, description, metadata_json, created_at) "
        "VALUES (?, ?, NULL, ?, ?, ?)",
        (agent_id, event_type, description, json.dumps(metadata), clock.now_iso()),
    )


def _snap_to_nearest_horizon(value: int, allowed: list[int]) -> int:
    """Snaps `value` to the closest entry in `allowed` (settings.FORWARD_HORIZONS), so a
    heuristic_applications.horizon_days always matches a horizon forward_returns actually
    computes. Ties resolve to the smaller horizon."""
    if not allowed:
        return value
    return min(allowed, key=lambda h: (abs(h - value), h))


def _eval_horizon_for_agent(agent_id: str) -> int:
    """The persona's eval_horizon_days, snapped into settings.FORWARD_HORIZONS. Falls back to
    _DEFAULT_HORIZON_DAYS for an agent with no persona entry (e.g. baseline-simons-rules, which
    is a BASELINE agent, not in agents.personas' registry)."""
    try:
        horizon = get_persona(agent_id).eval_horizon_days
    except KeyError:
        horizon = _DEFAULT_HORIZON_DAYS
    return _snap_to_nearest_horizon(horizon, settings.FORWARD_HORIZONS)


def _safely_evaluate_trigger(heuristic_id, trigger_json: str, features: dict) -> bool:
    """Parses trigger_json and evaluates it against features. Any failure (invalid JSON, a
    predicate missing 'feature'/'op'/'value', an unknown operator) is treated as NOT fired and
    logged -- never raised. A missing or None feature value is already handled as NOT fired by
    features.contracts.evaluate_predicate itself."""
    try:
        trigger = json.loads(trigger_json)
    except (json.JSONDecodeError, TypeError) as exc:
        logger.warning("heuristic %s: invalid trigger_json (%s); treating as not fired", heuristic_id, exc)
        return False
    try:
        return evaluate_predicate(features, trigger)
    except Exception as exc:  # noqa: BLE001 -- a malformed predicate must never crash the nightly job
        logger.warning("heuristic %s: trigger evaluation failed (%s); treating as not fired", heuristic_id, exc)
        return False


def _load_decision_features(conn, decision_row) -> dict | None:
    """The FeatureSnapshot for one decision: the exact snapshot it was made against
    (decisions.snapshot_id) when present, else the newest schema_version for that
    ticker/run_date. Returns None if no snapshot can be found at all."""
    snapshot_id = decision_row["snapshot_id"]
    if snapshot_id is not None:
        row = conn.execute("SELECT features_json FROM feature_snapshots WHERE id = ?", (snapshot_id,)).fetchone()
        if row is not None:
            return json.loads(row["features_json"])

    row = conn.execute(
        "SELECT features_json FROM feature_snapshots WHERE ticker = ? AND as_of_date = ? "
        "ORDER BY schema_version DESC LIMIT 1",
        (decision_row["ticker"], decision_row["run_date"]),
    ).fetchone()
    return json.loads(row["features_json"]) if row is not None else None


# ---------------------------------------------------------------------------
# 1. Trigger evaluation
# ---------------------------------------------------------------------------


def evaluate_triggers_for_date(conn, clock: Clock, as_of_date: str) -> int:
    """Checks every testing/active/reinforced heuristic against:
      1. That agent's decisions for as_of_date (ENTRY context), tracking compliance.
      2. That agent's OPEN positions as of as_of_date against today's snapshot (EXIT context).
    Inserts a PENDING heuristic_applications row for each new fire.
    Returns the number of new applications created."""
    heuristics = conn.execute(
        "SELECT id, agent_id, kind, context, trigger_json FROM agent_memory "
        "WHERE status IN ('testing', 'active', 'reinforced')"
    ).fetchall()
    if not heuristics:
        return 0

    heuristics_by_agent: dict = {}
    for h in heuristics:
        heuristics_by_agent.setdefault(h["agent_id"], []).append(h)

    new_applications = 0

    # 1. Entry decisions pass
    decisions = conn.execute(
        "SELECT id, agent_id, ticker, action, run_date, snapshot_id FROM decisions WHERE run_date = ?",
        (as_of_date,),
    ).fetchall()

    for decision in decisions:
        agent_heuristics = heuristics_by_agent.get(decision["agent_id"])
        if not agent_heuristics:
            continue

        features = _load_decision_features(conn, decision)
        if features is None:
            continue

        for heuristic in agent_heuristics:
            h_ctx = heuristic["context"] if "context" in heuristic.keys() else "ENTRY"
            if h_ctx not in ("ENTRY", "ANY", None):
                continue

            already_fired = conn.execute(
                "SELECT 1 FROM heuristic_applications WHERE heuristic_id = ? AND decision_id = ?",
                (heuristic["id"], decision["id"]),
            ).fetchone()
            if already_fired:
                continue

            if not _safely_evaluate_trigger(heuristic["id"], heuristic["trigger_json"], features):
                continue

            horizon_days = _eval_horizon_for_agent(decision["agent_id"])
            now_iso = clock.now_iso()

            # Compliance: SEEK complied if BUY; AVOID complied if action != BUY (i.e. HOLD/skipped)
            if heuristic["kind"] == "SEEK":
                complied = 1 if decision["action"] == "BUY" else 0
            else:
                complied = 1 if decision["action"] != "BUY" else 0

            conn.execute(
                "INSERT INTO heuristic_applications "
                "(heuristic_id, decision_id, position_id, context, fired_on, horizon_days, outcome, complied) "
                "VALUES (?, ?, NULL, 'ENTRY', ?, ?, 'PENDING', ?)",
                (heuristic["id"], decision["id"], as_of_date, horizon_days, complied),
            )
            conn.execute(
                "UPDATE agent_memory SET times_triggered = times_triggered + 1, "
                "last_fired_on = ?, updated_at = ? WHERE id = ?",
                (as_of_date, now_iso, heuristic["id"]),
            )
            new_applications += 1

    # 2. Exit-side open positions pass
    open_positions = conn.execute(
        "SELECT id, agent_id, ticker FROM positions WHERE status = 'OPEN'",
    ).fetchall()

    for pos in open_positions:
        agent_heuristics = heuristics_by_agent.get(pos["agent_id"])
        if not agent_heuristics:
            continue

        # Pull today's FeatureSnapshot for this ticker (not the historical entry snapshot)
        snap_row = conn.execute(
            "SELECT features_json FROM feature_snapshots WHERE ticker = ? AND as_of_date = ? "
            "ORDER BY schema_version DESC LIMIT 1",
            (pos["ticker"], as_of_date),
        ).fetchone()
        if snap_row is None:
            continue
        try:
            pos_features = json.loads(snap_row["features_json"])
        except Exception:
            continue

        for heuristic in agent_heuristics:
            h_ctx = heuristic["context"] if "context" in heuristic.keys() else "ENTRY"
            if h_ctx not in ("EXIT", "ANY"):
                continue

            already_fired = conn.execute(
                "SELECT 1 FROM heuristic_applications WHERE heuristic_id = ? AND position_id = ? AND fired_on = ?",
                (heuristic["id"], pos["id"], as_of_date),
            ).fetchone()
            if already_fired:
                continue

            if not _safely_evaluate_trigger(heuristic["id"], heuristic["trigger_json"], pos_features):
                continue

            horizon_days = _eval_horizon_for_agent(pos["agent_id"])
            now_iso = clock.now_iso()

            # Check compliance if the agent made a decision on this ticker tonight
            dec_row = conn.execute(
                "SELECT action FROM decisions WHERE agent_id = ? AND ticker = ? AND run_date = ?",
                (pos["agent_id"], pos["ticker"], as_of_date),
            ).fetchone()
            complied = None
            if dec_row is not None:
                agent_action = dec_row["action"]
                if heuristic["kind"] == "SEEK":
                    # Exit SEEK = sell signal. Complied if agent decided SELL
                    complied = 1 if agent_action == "SELL" else 0
                else:
                    # Exit AVOID = hold signal. Complied if agent decided HOLD (or did not sell)
                    complied = 1 if agent_action != "SELL" else 0

            conn.execute(
                "INSERT INTO heuristic_applications "
                "(heuristic_id, decision_id, position_id, context, fired_on, horizon_days, outcome, complied) "
                "VALUES (?, NULL, ?, 'EXIT', ?, ?, 'PENDING', ?)",
                (heuristic["id"], pos["id"], as_of_date, horizon_days, complied),
            )
            conn.execute(
                "UPDATE agent_memory SET times_triggered = times_triggered + 1, "
                "last_fired_on = ?, updated_at = ? WHERE id = ?",
                (as_of_date, now_iso, heuristic["id"]),
            )
            new_applications += 1

    return new_applications


# ---------------------------------------------------------------------------
# 2. Resolution from forward returns
# ---------------------------------------------------------------------------


def resolve_pending_applications(conn, clock: Clock, ohlcv_conn: sqlite3.Connection | None = None) -> int:
    """Resolves every PENDING heuristic_applications row whose forward returns are available.
    - For ENTRY applications: checks forward_returns (SEEK: ret > hurdle, AVOID: ret <= hurdle).
    - For EXIT applications: checks OHLCV forward price drift from fired_on with the sign flipped
      (SEEK: ret <= hurdle [price fell, exiting was right]; AVOID: ret > hurdle [price rose, holding was right]).
    Cost-aware via settings.HEURISTIC_SUCCESS_COST_HURDLE_PCT. Returns resolved count."""
    pending = conn.execute(
        """
        SELECT ha.id AS application_id, ha.heuristic_id, ha.decision_id, ha.position_id,
               ha.context, ha.fired_on, ha.horizon_days, am.kind, pos.ticker AS pos_ticker
        FROM heuristic_applications ha
        JOIN agent_memory am ON am.id = ha.heuristic_id
        LEFT JOIN positions pos ON pos.id = ha.position_id
        WHERE ha.outcome = 'PENDING'
        """
    ).fetchall()
    if not pending:
        return 0

    resolved_count = 0
    resolved_on = clock.today().isoformat()
    hurdle = settings.HEURISTIC_SUCCESS_COST_HURDLE_PCT
    owns_ohlcv = False
    if ohlcv_conn is None:
        try:
            from core.database import get_connection

            ohlcv_conn = get_connection(settings.OHLCV_DB_PATH)
            owns_ohlcv = True
        except Exception:
            ohlcv_conn = None

    try:
        for app in pending:
            context = app["context"] or "ENTRY"
            ret_pct = None

            if context == "ENTRY":
                if app["decision_id"] is None:
                    continue
                fr = conn.execute(
                    "SELECT ret_pct FROM forward_returns WHERE decision_id = ? AND horizon_days = ?",
                    (app["decision_id"], app["horizon_days"]),
                ).fetchone()
                if fr is None:
                    continue
                ret_pct = fr["ret_pct"]
                success = (ret_pct > hurdle) if app["kind"] == "SEEK" else (ret_pct <= hurdle)

            else:  # EXIT context (open position evaluation)
                ticker = app["pos_ticker"]
                if not ticker or ohlcv_conn is None:
                    continue

                candles = ohlcv_conn.execute(
                    "SELECT trade_date, close FROM ohlcv WHERE ticker = ? AND trade_date >= ? "
                    "ORDER BY trade_date ASC LIMIT ?",
                    (ticker, app["fired_on"], app["horizon_days"] + 1),
                ).fetchall()
                if len(candles) < app["horizon_days"] + 1:
                    continue  # horizon hasn't elapsed yet

                base_close = candles[0]["close"]
                fwd_close = candles[-1]["close"]
                if not base_close or base_close <= 0:
                    continue
                ret_pct = ((fwd_close - base_close) / base_close) * 100.0

                # Exit-side sign flip:
                # SEEK (exit signal) -> success if price fell (ret_pct <= hurdle)
                # AVOID (hold signal) -> success if price rose (ret_pct > hurdle)
                success = (ret_pct <= hurdle) if app["kind"] == "SEEK" else (ret_pct > hurdle)

            outcome = "SUCCESS" if success else "FAILURE"
            conn.execute(
                "UPDATE heuristic_applications SET outcome = ?, resolved_on = ? WHERE id = ?",
                (outcome, resolved_on, app["application_id"]),
            )
            if success:
                conn.execute(
                    "UPDATE agent_memory SET times_successful = times_successful + 1, updated_at = ? WHERE id = ?",
                    (clock.now_iso(), app["heuristic_id"]),
                )
            resolved_count += 1
    finally:
        if owns_ohlcv and ohlcv_conn is not None:
            ohlcv_conn.close()

    return resolved_count


# ---------------------------------------------------------------------------
# 3. Lifecycle transitions
# ---------------------------------------------------------------------------


def _parse_date_prefix(value: str) -> date:
    """Both last_fired_on/created_at ('YYYY-MM-DD'...) and full ISO datetimes share this
    10-character date prefix."""
    return date.fromisoformat(value[:10])


def _days_since(clock: Clock, reference: str) -> int:
    return (clock.today() - _parse_date_prefix(reference)).days


def _resolved_stats(conn, heuristic_id: int, since: str | None = None) -> tuple[int, int]:
    """(resolved_count, successes) over resolved (SUCCESS/FAILURE) applications, optionally only
    those resolved_on >= `since` (None means no lower bound -- the lifetime/epoch-since-the-
    beginning case)."""
    if since is None:
        row = conn.execute(
            "SELECT SUM(CASE WHEN outcome = 'SUCCESS' THEN 1 ELSE 0 END) AS successes, "
            "SUM(CASE WHEN outcome IN ('SUCCESS', 'FAILURE') THEN 1 ELSE 0 END) AS resolved "
            "FROM heuristic_applications WHERE heuristic_id = ?",
            (heuristic_id,),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT SUM(CASE WHEN outcome = 'SUCCESS' THEN 1 ELSE 0 END) AS successes, "
            "SUM(CASE WHEN outcome IN ('SUCCESS', 'FAILURE') THEN 1 ELSE 0 END) AS resolved "
            "FROM heuristic_applications WHERE heuristic_id = ? AND resolved_on >= ?",
            (heuristic_id, since),
        ).fetchone()
    return row["resolved"] or 0, row["successes"] or 0


def _rolling_stats(conn, heuristic_id: int, since: str | None, window: int) -> tuple[int, int] | None:
    """(window_count, successes) over the most recent `window` resolved applications since
    `since` (None = since the beginning), ordered by resolved_on then id. Returns None if fewer
    than `window` such applications exist yet -- the rolling check is skipped entirely then."""
    if since is None:
        rows = conn.execute(
            "SELECT outcome FROM heuristic_applications WHERE heuristic_id = ? "
            "AND outcome IN ('SUCCESS', 'FAILURE') ORDER BY resolved_on DESC, id DESC LIMIT ?",
            (heuristic_id, window),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT outcome FROM heuristic_applications WHERE heuristic_id = ? AND resolved_on >= ? "
            "AND outcome IN ('SUCCESS', 'FAILURE') ORDER BY resolved_on DESC, id DESC LIMIT ?",
            (heuristic_id, since, window),
        ).fetchall()
    if len(rows) < window:
        return None
    successes = sum(1 for r in rows if r["outcome"] == "SUCCESS")
    return len(rows), successes


def update_lifecycle(conn, clock: Clock) -> list[tuple[int, str, str]]:
    """Promotes, demotes, or deprecates every non-deprecated heuristic. Deprecated is final --
    such heuristics are skipped entirely and never reconsidered. A heuristic moves AT MOST ONE
    step per call, checked in this order:

      (a) Deprecation, exactly as before -- on LIFETIME stats (all resolved applications ever):
          below the deprecation success-rate floor with the minimum sample, or stale (no fire in
          HEURISTIC_DEPRECATED_STALE_DAYS). Final; nothing below runs if this fires.
      (b) Rolling demotion -- on the ROLLING stats (the last HEURISTIC_ROLLING_WINDOW resolved
          applications since the heuristic's current lifecycle_epoch_start), only once that many
          exist since the epoch (otherwise skipped, not failed). reinforced -> active, or
          active -> testing, when the rolling rate is below HEURISTIC_ROLLING_DEMOTE_BELOW. The
          epoch resets to today on a demotion, so promotion afterwards needs fresh evidence.
      (c) Promotion -- on EPOCH stats (resolved applications since lifecycle_epoch_start; equal
          to lifetime stats when the epoch is NULL, i.e. never demoted), and gated by the
          CURRENT status so a heuristic can only move up one tier even if its epoch stats would
          already clear a higher tier's bar: testing -> active, or active -> reinforced. A
          heuristic already 'reinforced' stays there (checked in (b) for demotion only) and a
          heuristic already 'active' is only ever considered for 'reinforced' here, never
          straight from 'testing'.

    Confidence (Laplace-smoothed, from LIFETIME stats, unchanged from before) is recomputed for
    every live heuristic every call, status change or not. Returns a list of
    (heuristic_id, old_status, new_status) for every heuristic that actually changed status."""
    heuristics = conn.execute(
        "SELECT id, agent_id, status, last_fired_on, created_at, lifecycle_epoch_start "
        "FROM agent_memory WHERE status != 'deprecated'"
    ).fetchall()

    changes: list[tuple[int, str, str]] = []
    now_iso = clock.now_iso()
    today_iso = clock.today().isoformat()

    for h in heuristics:
        lifetime_resolved, lifetime_successes = _resolved_stats(conn, h["id"], since=None)
        lifetime_rate = (lifetime_successes / lifetime_resolved) if lifetime_resolved else 0.0
        # Laplace smoothing so a tiny sample (e.g. 1/1) never reads as unconditional confidence.
        confidence = (lifetime_successes + 1) / (lifetime_resolved + 2)
        wilson_lb = wilson_score_lower_bound(lifetime_successes, lifetime_resolved, z=settings.HEURISTIC_WILSON_Z)

        stale_reference = h["last_fired_on"] or h["created_at"]
        is_stale = _days_since(clock, stale_reference) >= settings.HEURISTIC_DEPRECATED_STALE_DAYS

        epoch_start = h["lifecycle_epoch_start"]
        new_status = h["status"]
        new_epoch_start = epoch_start
        reason = "no_change"
        rolling_info: tuple[int, int] | None = None

        # (a) Deprecation -- lifetime stats, final.
        rate_below_floor = (
            lifetime_resolved >= settings.HEURISTIC_DEPRECATED_MIN_APPLICATIONS
            and lifetime_rate < settings.HEURISTIC_DEPRECATED_MAX_SUCCESS_RATE
        )
        if rate_below_floor or is_stale:
            new_status = "deprecated"
            if rate_below_floor and is_stale:
                reason = "lifetime_rate_below_floor_and_stale"
            elif rate_below_floor:
                reason = "lifetime_rate_below_floor"
            else:
                reason = "stale"
        else:
            # (b) Rolling demotion -- only reinforced or active can be demoted, and only once
            # HEURISTIC_ROLLING_WINDOW resolved applications exist since the current epoch.
            rolling_info = _rolling_stats(conn, h["id"], epoch_start, settings.HEURISTIC_ROLLING_WINDOW)
            if rolling_info is not None and h["status"] in ("active", "reinforced"):
                rolling_count, rolling_successes = rolling_info
                rolling_rate = rolling_successes / rolling_count
                if rolling_rate < settings.HEURISTIC_ROLLING_DEMOTE_BELOW:
                    new_status = "active" if h["status"] == "reinforced" else "testing"
                    new_epoch_start = today_iso
                    reason = "rolling_demotion"

            # (c) Promotion -- on Wilson score lower bound computed from EPOCH stats,
            # gated by CURRENT status so a heuristic moves up at most one tier per call.
            # Only considered when (b) did not just demote this heuristic.
            if reason == "no_change":
                epoch_resolved, epoch_successes = _resolved_stats(conn, h["id"], since=epoch_start)
                (epoch_successes / epoch_resolved) if epoch_resolved else 0.0
                wilson_lb = wilson_score_lower_bound(epoch_successes, epoch_resolved, z=settings.HEURISTIC_WILSON_Z)
                if (
                    h["status"] == "active"
                    and epoch_resolved >= settings.HEURISTIC_REINFORCED_MIN_APPLICATIONS
                    and wilson_lb >= settings.HEURISTIC_REINFORCED_MIN_WILSON_SCORE
                ):
                    new_status = "reinforced"
                    reason = "promotion_epoch"
                elif (
                    h["status"] == "testing"
                    and epoch_resolved >= settings.HEURISTIC_ACTIVE_MIN_APPLICATIONS
                    and wilson_lb >= settings.HEURISTIC_ACTIVE_MIN_WILSON_SCORE
                ):
                    new_status = "active"
                    reason = "promotion_epoch"

        conn.execute(
            "UPDATE agent_memory SET confidence = ?, status = ?, lifecycle_epoch_start = ?, "
            "updated_at = ? WHERE id = ?",
            (round(confidence, 4), new_status, new_epoch_start, now_iso, h["id"]),
        )

        if new_status != h["status"]:
            metadata = {
                "heuristic_id": h["id"],
                "old_status": h["status"],
                "new_status": new_status,
                "reason": reason,
                "lifetime_resolved": lifetime_resolved,
                "lifetime_successes": lifetime_successes,
                "lifetime_rate": round(lifetime_rate, 4),
                "confidence": round(confidence, 4),
                "wilson_lb": round(wilson_lb, 4),
            }
            description = (
                f"heuristic {h['id']}: {h['status']} -> {new_status} ({reason}; "
                f"wilson_lb={wilson_lb:.2f} lifetime_rate={lifetime_rate:.2f} n={lifetime_resolved}"
            )
            if rolling_info is not None:
                rolling_count, rolling_successes = rolling_info
                rolling_rate = rolling_successes / rolling_count
                metadata["rolling_rate"] = round(rolling_rate, 4)
                metadata["rolling_n"] = rolling_count
                description += f"; rolling_rate={rolling_rate:.2f} n={rolling_count}"
            description += ")"

            _log_activity(conn, h["agent_id"], "HEURISTIC_STATUS_CHANGED", description, metadata, clock)
            changes.append((h["id"], h["status"], new_status))

    return changes


# ---------------------------------------------------------------------------
# 4. Orchestrator
# ---------------------------------------------------------------------------


def run_nightly(conn, clock: Clock, as_of_date: str) -> dict:
    """Runs evaluate_triggers_for_date -> resolve_pending_applications -> update_lifecycle in
    order. Each step is isolated: a failure in one is logged and does not stop the others. Not
    wired into the scheduler by this task."""
    summary: dict = {"as_of_date": as_of_date, "errors": {}}

    try:
        summary["new_applications"] = evaluate_triggers_for_date(conn, clock, as_of_date)
    except Exception as exc:  # noqa: BLE001 -- one step's failure must not block the others
        logger.exception("run_nightly: evaluate_triggers_for_date failed for %s", as_of_date)
        summary["new_applications"] = None
        summary["errors"]["evaluate_triggers_for_date"] = str(exc)

    try:
        summary["resolved_applications"] = resolve_pending_applications(conn, clock)
    except Exception as exc:  # noqa: BLE001
        logger.exception("run_nightly: resolve_pending_applications failed for %s", as_of_date)
        summary["resolved_applications"] = None
        summary["errors"]["resolve_pending_applications"] = str(exc)

    try:
        summary["status_changes"] = update_lifecycle(conn, clock)
    except Exception as exc:  # noqa: BLE001
        logger.exception("run_nightly: update_lifecycle failed for %s", as_of_date)
        summary["status_changes"] = None
        summary["errors"]["update_lifecycle"] = str(exc)

    try:
        from learning.compliance import audit_compliance_and_escalate

        summary["compliance_escalations"] = audit_compliance_and_escalate(conn, clock)
    except Exception as exc:  # noqa: BLE001
        logger.exception("run_nightly: audit_compliance_and_escalate failed for %s", as_of_date)
        summary["compliance_escalations"] = None
        summary["errors"]["audit_compliance_and_escalate"] = str(exc)

    return summary
