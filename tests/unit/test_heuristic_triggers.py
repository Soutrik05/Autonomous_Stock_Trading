"""
Unit tests for learning/memory_manager.py: heuristic trigger evaluation, idempotency,
forward-return resolution, and lifecycle transitions. In-memory SQLite (db/schema.sql + every
migration), a FakeClock, no real API calls.
See Plan_v3 §5.5.
"""

import itertools
import json
from datetime import datetime

import learning.memory_manager as memory_manager
from core.clock import FakeClock
from core.config import settings
from learning.memory_manager import (
    evaluate_triggers_for_date,
    resolve_pending_applications,
    run_nightly,
    update_lifecycle,
)
from tests.conftest import make_portfolio_db

NOW = "2026-10-19T20:00:00+05:30"
RUN_DATE = "2026-10-19"
AGENT = "simons"
OTHER_AGENT = "baseline-simons-rules"


def clock_at(iso_datetime: str = NOW) -> FakeClock:
    return FakeClock(datetime.fromisoformat(iso_datetime))


def insert_agent(conn, agent_id: str = AGENT) -> None:
    conn.execute(
        "INSERT INTO agents (id, name, philosophy, kind, starting_cash_paise, cash_paise, created_at, updated_at) "
        "VALUES (?, ?, 'Test', 'LLM', 50000000, 50000000, ?, ?)",
        (agent_id, agent_id, NOW, NOW),
    )


def insert_feature_snapshot(conn, ticker: str, as_of_date: str, features: dict, schema_version: int = 1) -> int:
    cur = conn.execute(
        "INSERT INTO feature_snapshots (ticker, as_of_date, schema_version, features_json, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (ticker, as_of_date, schema_version, json.dumps(features), NOW),
    )
    return cur.lastrowid


def insert_decision(conn, agent_id: str, ticker: str, run_date: str, snapshot_id) -> int:
    cur = conn.execute(
        "INSERT INTO decisions (run_date, agent_id, ticker, source, action, reasoning, snapshot_id, created_at) "
        "VALUES (?, ?, ?, 'LLM', 'HOLD', 'test', ?, ?)",
        (run_date, agent_id, ticker, snapshot_id, NOW),
    )
    return cur.lastrowid


def insert_heuristic(
    conn,
    agent_id: str = AGENT,
    kind: str = "SEEK",
    trigger_json: str = "{}",
    status: str = "testing",
    last_fired_on=None,
    created_at: str = NOW,
    context: str = "ENTRY",
) -> int:
    cur = conn.execute(
        "INSERT INTO agent_memory (agent_id, kind, context, heuristic_text, trigger_json, prescribed_action, "
        "status, confidence, times_triggered, times_successful, last_fired_on, created_at, updated_at) "
        "VALUES (?, ?, ?, 'test heuristic', ?, 'test action', ?, 0.5, 0, 0, ?, ?, ?)",
        (agent_id, kind, context, trigger_json, status, last_fired_on, created_at, NOW),
    )
    return cur.lastrowid


def insert_forward_return(conn, decision_id: int, horizon_days: int, ret_pct: float) -> None:
    conn.execute(
        "INSERT INTO forward_returns (decision_id, horizon_days, ret_pct, nifty_ret_pct, computed_on) "
        "VALUES (?, ?, ?, 0.0, ?)",
        (decision_id, horizon_days, ret_pct, NOW),
    )


def resolved_rows(conn, heuristic_id: int):
    return conn.execute("SELECT * FROM heuristic_applications WHERE heuristic_id = ?", (heuristic_id,)).fetchall()


# --- 1-2: basic match / no-match ----------------------------------------------------------------


def test_a_matching_trigger_creates_one_pending_application():
    conn = make_portfolio_db()
    insert_agent(conn)
    snap = insert_feature_snapshot(conn, "TATAMOTORS", RUN_DATE, {"rsi_14": 60.0})
    insert_decision(conn, AGENT, "TATAMOTORS", RUN_DATE, snap)
    heuristic_id = insert_heuristic(conn, trigger_json=json.dumps({"feature": "rsi_14", "op": ">", "value": 55}))

    new_count = evaluate_triggers_for_date(conn, clock_at(), RUN_DATE)

    assert new_count == 1
    rows = resolved_rows(conn, heuristic_id)
    assert len(rows) == 1
    assert rows[0]["outcome"] == "PENDING"
    assert rows[0]["fired_on"] == RUN_DATE


def test_a_non_matching_trigger_creates_nothing():
    conn = make_portfolio_db()
    insert_agent(conn)
    snap = insert_feature_snapshot(conn, "TATAMOTORS", RUN_DATE, {"rsi_14": 40.0})
    insert_decision(conn, AGENT, "TATAMOTORS", RUN_DATE, snap)
    heuristic_id = insert_heuristic(conn, trigger_json=json.dumps({"feature": "rsi_14", "op": ">", "value": 55}))

    new_count = evaluate_triggers_for_date(conn, clock_at(), RUN_DATE)

    assert new_count == 0
    assert resolved_rows(conn, heuristic_id) == []


# --- 3-4: missing metric / bad JSON, never crash --------------------------------------------------


def test_a_missing_metric_is_treated_as_not_fired_without_crashing():
    conn = make_portfolio_db()
    insert_agent(conn)
    # rsi_14 absent entirely from this candidate's features.
    snap = insert_feature_snapshot(conn, "TATAMOTORS", RUN_DATE, {"close": 1000.0})
    insert_decision(conn, AGENT, "TATAMOTORS", RUN_DATE, snap)
    heuristic_id = insert_heuristic(conn, trigger_json=json.dumps({"feature": "rsi_14", "op": ">", "value": 55}))

    new_count = evaluate_triggers_for_date(conn, clock_at(), RUN_DATE)

    assert new_count == 0
    assert resolved_rows(conn, heuristic_id) == []


def test_bad_trigger_json_is_treated_as_not_fired_without_crashing():
    conn = make_portfolio_db()
    insert_agent(conn)
    snap = insert_feature_snapshot(conn, "TATAMOTORS", RUN_DATE, {"rsi_14": 60.0})
    insert_decision(conn, AGENT, "TATAMOTORS", RUN_DATE, snap)
    heuristic_id = insert_heuristic(conn, trigger_json="not valid json {{{")

    new_count = evaluate_triggers_for_date(conn, clock_at(), RUN_DATE)

    assert new_count == 0
    assert resolved_rows(conn, heuristic_id) == []


# --- 5: idempotent rerun --------------------------------------------------------------------------


def test_running_evaluation_twice_does_not_create_duplicates():
    conn = make_portfolio_db()
    insert_agent(conn)
    snap = insert_feature_snapshot(conn, "TATAMOTORS", RUN_DATE, {"rsi_14": 60.0})
    insert_decision(conn, AGENT, "TATAMOTORS", RUN_DATE, snap)
    heuristic_id = insert_heuristic(conn, trigger_json=json.dumps({"feature": "rsi_14", "op": ">", "value": 55}))

    first = evaluate_triggers_for_date(conn, clock_at(), RUN_DATE)
    second = evaluate_triggers_for_date(conn, clock_at(), RUN_DATE)

    assert first == 1
    assert second == 0
    assert len(resolved_rows(conn, heuristic_id)) == 1


# --- 6: agent isolation -----------------------------------------------------------------------


def test_a_heuristic_only_fires_on_its_own_agents_decisions():
    conn = make_portfolio_db()
    insert_agent(conn, AGENT)
    insert_agent(conn, OTHER_AGENT)
    snap = insert_feature_snapshot(conn, "TATAMOTORS", RUN_DATE, {"rsi_14": 60.0})
    insert_decision(conn, OTHER_AGENT, "TATAMOTORS", RUN_DATE, snap)
    heuristic_id = insert_heuristic(
        conn, agent_id=AGENT, trigger_json=json.dumps({"feature": "rsi_14", "op": ">", "value": 55})
    )

    new_count = evaluate_triggers_for_date(conn, clock_at(), RUN_DATE)

    assert new_count == 0
    assert resolved_rows(conn, heuristic_id) == []


# --- 7-8: SEEK/AVOID resolution ------------------------------------------------------------------


def test_seek_success_and_failure():
    conn = make_portfolio_db()
    insert_agent(conn)
    snap = insert_feature_snapshot(conn, "A", RUN_DATE, {"rsi_14": 60.0})
    win_decision = insert_decision(conn, AGENT, "A", RUN_DATE, snap)
    lose_decision = insert_decision(conn, AGENT, "B", RUN_DATE, snap)
    heuristic_id = insert_heuristic(conn, kind="SEEK")
    conn.execute(
        "INSERT INTO heuristic_applications (heuristic_id, decision_id, fired_on, horizon_days, outcome) "
        "VALUES (?, ?, ?, 5, 'PENDING')",
        (heuristic_id, win_decision, RUN_DATE),
    )
    conn.execute(
        "INSERT INTO heuristic_applications (heuristic_id, decision_id, fired_on, horizon_days, outcome) "
        "VALUES (?, ?, ?, 5, 'PENDING')",
        (heuristic_id, lose_decision, RUN_DATE),
    )
    insert_forward_return(conn, win_decision, 5, 2.0)
    insert_forward_return(conn, lose_decision, 5, -1.0)

    resolved_count = resolve_pending_applications(conn, clock_at())

    assert resolved_count == 2
    rows = {r["decision_id"]: r["outcome"] for r in resolved_rows(conn, heuristic_id)}
    assert rows[win_decision] == "SUCCESS"
    assert rows[lose_decision] == "FAILURE"


def test_avoid_success_and_failure():
    conn = make_portfolio_db()
    insert_agent(conn)
    snap = insert_feature_snapshot(conn, "A", RUN_DATE, {"rsi_14": 60.0})
    win_decision = insert_decision(conn, AGENT, "A", RUN_DATE, snap)  # AVOID wins when ret <= 0
    lose_decision = insert_decision(conn, AGENT, "B", RUN_DATE, snap)
    heuristic_id = insert_heuristic(conn, kind="AVOID")
    conn.execute(
        "INSERT INTO heuristic_applications (heuristic_id, decision_id, fired_on, horizon_days, outcome) "
        "VALUES (?, ?, ?, 5, 'PENDING')",
        (heuristic_id, win_decision, RUN_DATE),
    )
    conn.execute(
        "INSERT INTO heuristic_applications (heuristic_id, decision_id, fired_on, horizon_days, outcome) "
        "VALUES (?, ?, ?, 5, 'PENDING')",
        (heuristic_id, lose_decision, RUN_DATE),
    )
    insert_forward_return(conn, win_decision, 5, -1.0)
    insert_forward_return(conn, lose_decision, 5, 2.0)

    resolved_count = resolve_pending_applications(conn, clock_at())

    assert resolved_count == 2
    rows = {r["decision_id"]: r["outcome"] for r in resolved_rows(conn, heuristic_id)}
    assert rows[win_decision] == "SUCCESS"
    assert rows[lose_decision] == "FAILURE"


# --- 9-10: horizon not yet resolved -------------------------------------------------------------


def test_pending_application_stays_pending_when_only_a_different_horizon_exists():
    conn = make_portfolio_db()
    insert_agent(conn)
    snap = insert_feature_snapshot(conn, "A", RUN_DATE, {"rsi_14": 60.0})
    decision_id = insert_decision(conn, AGENT, "A", RUN_DATE, snap)
    heuristic_id = insert_heuristic(conn, kind="SEEK")
    conn.execute(
        "INSERT INTO heuristic_applications (heuristic_id, decision_id, fired_on, horizon_days, outcome) "
        "VALUES (?, ?, ?, 5, 'PENDING')",
        (heuristic_id, decision_id, RUN_DATE),
    )
    insert_forward_return(conn, decision_id, 10, 2.0)  # wrong horizon -- the 5-day one hasn't resolved

    resolved_count = resolve_pending_applications(conn, clock_at())

    assert resolved_count == 0
    assert resolved_rows(conn, heuristic_id)[0]["outcome"] == "PENDING"


def test_pending_application_stays_pending_with_no_forward_returns_row_at_all():
    conn = make_portfolio_db()
    insert_agent(conn)
    snap = insert_feature_snapshot(conn, "A", RUN_DATE, {"rsi_14": 60.0})
    decision_id = insert_decision(conn, AGENT, "A", RUN_DATE, snap)
    heuristic_id = insert_heuristic(conn, kind="SEEK")
    conn.execute(
        "INSERT INTO heuristic_applications (heuristic_id, decision_id, fired_on, horizon_days, outcome) "
        "VALUES (?, ?, ?, 5, 'PENDING')",
        (heuristic_id, decision_id, RUN_DATE),
    )

    resolved_count = resolve_pending_applications(conn, clock_at())

    assert resolved_count == 0
    assert resolved_rows(conn, heuristic_id)[0]["outcome"] == "PENDING"


# --- 11-15: lifecycle transitions -----------------------------------------------------------------


def _set_resolved_applications(conn, heuristic_id, successes: int, failures: int):
    """Inserts `successes` + `failures` already-resolved applications for `heuristic_id`, each
    against its OWN decision (the unique index on (heuristic_id, decision_id) forbids reusing
    one decision for several applications of the same heuristic)."""
    agent_id = conn.execute("SELECT agent_id FROM agent_memory WHERE id = ?", (heuristic_id,)).fetchone()["agent_id"]
    snap = insert_feature_snapshot(
        conn, f"SYN{heuristic_id}", RUN_DATE, {"rsi_14": 60.0}, schema_version=heuristic_id * 1000
    )
    outcomes = ["SUCCESS"] * successes + ["FAILURE"] * failures
    for i, outcome in enumerate(outcomes):
        decision_id = insert_decision(conn, agent_id, f"SYN{heuristic_id}_{i}", RUN_DATE, snap)
        conn.execute(
            "INSERT INTO heuristic_applications (heuristic_id, decision_id, fired_on, horizon_days, outcome, resolved_on) "
            "VALUES (?, ?, ?, 5, ?, ?)",
            (heuristic_id, decision_id, RUN_DATE, outcome, RUN_DATE),
        )


_since_counter = itertools.count()


def _insert_resolved_since(conn, heuristic_id, outcomes: list, resolved_on: str):
    """Like _set_resolved_applications, but with an explicit resolved_on per batch (so epoch/
    rolling-window filtering by date can be exercised), and an explicit outcome sequence."""
    agent_id = conn.execute("SELECT agent_id FROM agent_memory WHERE id = ?", (heuristic_id,)).fetchone()["agent_id"]
    for outcome in outcomes:
        n = next(_since_counter)
        ticker = f"SYN{heuristic_id}_{n}"
        snap = insert_feature_snapshot(conn, ticker, RUN_DATE, {"rsi_14": 60.0}, schema_version=n + 1)
        decision_id = insert_decision(conn, agent_id, ticker, RUN_DATE, snap)
        conn.execute(
            "INSERT INTO heuristic_applications (heuristic_id, decision_id, fired_on, horizon_days, outcome, resolved_on) "
            "VALUES (?, ?, ?, 5, ?, ?)",
            (heuristic_id, decision_id, RUN_DATE, outcome, resolved_on),
        )


def test_promotion_testing_to_active_at_threshold_and_not_below_it():
    conn = make_portfolio_db()
    insert_agent(conn)
    snap = insert_feature_snapshot(conn, "A", RUN_DATE, {"rsi_14": 60.0})
    insert_decision(conn, AGENT, "A", RUN_DATE, snap)

    # With Wilson score lower bound (z=1.645, threshold >= 0.50):
    # At n=10: 8/10 gives Wilson LB = 0.541 >= 0.50 -> promotes
    #          7/10 gives Wilson LB = 0.441 < 0.50  -> stays testing
    at_threshold = insert_heuristic(conn, status="testing")
    _set_resolved_applications(conn, at_threshold, successes=8, failures=2)

    below_threshold = insert_heuristic(conn, status="testing")
    _set_resolved_applications(conn, below_threshold, successes=7, failures=3)

    update_lifecycle(conn, clock_at())

    assert (
        conn.execute("SELECT status FROM agent_memory WHERE id = ?", (at_threshold,)).fetchone()["status"] == "active"
    )
    assert (
        conn.execute("SELECT status FROM agent_memory WHERE id = ?", (below_threshold,)).fetchone()["status"]
        == "testing"
    )


def test_promotion_active_to_reinforced():
    conn = make_portfolio_db()
    insert_agent(conn)
    snap = insert_feature_snapshot(conn, "A", RUN_DATE, {"rsi_14": 60.0})
    insert_decision(conn, AGENT, "A", RUN_DATE, snap)

    # With Wilson score lower bound (z=1.645, threshold >= 0.55, min_applications=10):
    # At n=10: 9/10 gives Wilson LB = 0.652 >= 0.55 -> promotes
    heuristic_id = insert_heuristic(conn, status="active")
    _set_resolved_applications(conn, heuristic_id, successes=9, failures=1)

    changes = update_lifecycle(conn, clock_at())

    row = conn.execute("SELECT status FROM agent_memory WHERE id = ?", (heuristic_id,)).fetchone()
    assert row["status"] == "reinforced"
    assert (heuristic_id, "active", "reinforced") in changes


def test_deprecation_by_low_success_rate():
    conn = make_portfolio_db()
    insert_agent(conn)
    snap = insert_feature_snapshot(conn, "A", RUN_DATE, {"rsi_14": 60.0})
    insert_decision(conn, AGENT, "A", RUN_DATE, snap)

    heuristic_id = insert_heuristic(conn, status="active")
    _set_resolved_applications(conn, heuristic_id, successes=1, failures=4)  # 1/5 = 0.2 < 0.4

    update_lifecycle(conn, clock_at())

    assert (
        conn.execute("SELECT status FROM agent_memory WHERE id = ?", (heuristic_id,)).fetchone()["status"]
        == "deprecated"
    )


def test_deprecation_by_30_days_with_no_firing():
    conn = make_portfolio_db()
    insert_agent(conn)
    heuristic_id = insert_heuristic(conn, status="testing", last_fired_on=None, created_at="2026-09-01T00:00:00+05:30")

    update_lifecycle(conn, clock_at("2026-11-03T20:00:00+05:30"))  # 63 days later

    assert (
        conn.execute("SELECT status FROM agent_memory WHERE id = ?", (heuristic_id,)).fetchone()["status"]
        == "deprecated"
    )


def test_a_deprecated_heuristic_is_never_promoted_again():
    conn = make_portfolio_db()
    insert_agent(conn)
    snap = insert_feature_snapshot(conn, "A", RUN_DATE, {"rsi_14": 60.0})
    insert_decision(conn, AGENT, "A", RUN_DATE, snap)

    heuristic_id = insert_heuristic(conn, status="deprecated")
    _set_resolved_applications(conn, heuristic_id, successes=10, failures=0)  # would be reinforced-worthy

    changes = update_lifecycle(conn, clock_at())

    assert (
        conn.execute("SELECT status FROM agent_memory WHERE id = ?", (heuristic_id,)).fetchone()["status"]
        == "deprecated"
    )
    assert all(c[0] != heuristic_id for c in changes)


# --- 16: activity_log ------------------------------------------------------------------------------


def test_status_changes_are_written_to_activity_log():
    conn = make_portfolio_db()
    insert_agent(conn)
    snap = insert_feature_snapshot(conn, "A", RUN_DATE, {"rsi_14": 60.0})
    insert_decision(conn, AGENT, "A", RUN_DATE, snap)

    heuristic_id = insert_heuristic(conn, status="testing")
    _set_resolved_applications(
        conn, heuristic_id, successes=5, failures=0
    )  # promotes to active (Wilson LB = 0.649 >= 0.50)

    update_lifecycle(conn, clock_at())

    rows = conn.execute("SELECT * FROM activity_log WHERE event_type = 'HEURISTIC_STATUS_CHANGED'").fetchall()
    assert len(rows) == 1
    metadata = json.loads(rows[0]["metadata_json"])
    assert metadata["heuristic_id"] == heuristic_id
    assert metadata["old_status"] == "testing"
    assert metadata["new_status"] == "active"
    assert metadata["wilson_lb"] >= 0.50


# --- 17: run_nightly isolates failures -------------------------------------------------------------


def test_run_nightly_keeps_going_when_one_step_raises(monkeypatch):
    conn = make_portfolio_db()
    insert_agent(conn)

    def _boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(memory_manager, "evaluate_triggers_for_date", _boom)

    summary = run_nightly(conn, clock_at(), RUN_DATE)

    assert summary["new_applications"] is None
    assert summary["errors"]["evaluate_triggers_for_date"] == "boom"
    assert summary["resolved_applications"] == 0  # still ran
    assert summary["status_changes"] == []  # still ran


# --- Lifecycle fixes: rolling demotion, no flip-flop, cost-aware success, 5-application gate ---


def test_migration_0008_adds_a_nullable_epoch_column():
    conn = make_portfolio_db()
    insert_agent(conn)
    heuristic_id = insert_heuristic(conn)
    row = conn.execute("SELECT lifecycle_epoch_start FROM agent_memory WHERE id = ?", (heuristic_id,)).fetchone()
    assert row["lifecycle_epoch_start"] is None  # "since the beginning"


def test_rolling_demotion_reinforced_to_active_and_active_to_testing_below_045():
    conn = make_portfolio_db()
    insert_agent(conn)

    # 5/12 = 0.4167: below the 0.45 rolling floor, but NOT below the 0.4 deprecation floor, so
    # only the rolling-demotion path can explain the change.
    outcomes = ["SUCCESS"] * 5 + ["FAILURE"] * 7

    reinforced_id = insert_heuristic(conn, status="reinforced")
    _insert_resolved_since(conn, reinforced_id, outcomes, RUN_DATE)

    active_id = insert_heuristic(conn, status="active")
    _insert_resolved_since(conn, active_id, outcomes, RUN_DATE)

    changes = update_lifecycle(conn, clock_at())

    today = clock_at().today().isoformat()
    r1 = conn.execute(
        "SELECT status, lifecycle_epoch_start FROM agent_memory WHERE id = ?", (reinforced_id,)
    ).fetchone()
    r2 = conn.execute("SELECT status, lifecycle_epoch_start FROM agent_memory WHERE id = ?", (active_id,)).fetchone()
    assert r1["status"] == "active"
    assert r1["lifecycle_epoch_start"] == today
    assert r2["status"] == "testing"
    assert r2["lifecycle_epoch_start"] == today
    assert (reinforced_id, "reinforced", "active") in changes
    assert (active_id, "active", "testing") in changes


def test_rolling_demotion_skipped_with_only_11_resolved_since_epoch():
    conn = make_portfolio_db()
    insert_agent(conn)
    heuristic_id = insert_heuristic(conn, status="active")

    # Safe lifetime history (so lifetime stats alone never trigger deprecation)...
    _insert_resolved_since(conn, heuristic_id, ["SUCCESS"] * 10, "2026-09-01")
    # ...then an epoch reset, with only 11 (not 12) resolved since it, at a bad rate.
    conn.execute("UPDATE agent_memory SET lifecycle_epoch_start = ? WHERE id = ?", ("2026-10-01", heuristic_id))
    _insert_resolved_since(conn, heuristic_id, ["SUCCESS"] * 4 + ["FAILURE"] * 7, "2026-10-05")  # 11 since epoch

    update_lifecycle(conn, clock_at())

    row = conn.execute("SELECT status FROM agent_memory WHERE id = ?", (heuristic_id,)).fetchone()
    assert row["status"] == "active"  # unchanged -- rolling check needs >= 12 since the epoch


def test_rolling_demotion_not_triggered_at_exactly_045():
    conn = make_portfolio_db()
    insert_agent(conn)
    heuristic_id = insert_heuristic(conn, status="active")

    # 12 doesn't divide evenly into an exact 0.45 -- widen the window just for this test so
    # 9/20 = 0.45 exactly is representable. settings is a frozen dataclass; object.__setattr__
    # bypasses that for the duration of the test only.
    original_window = settings.HEURISTIC_ROLLING_WINDOW
    object.__setattr__(settings, "HEURISTIC_ROLLING_WINDOW", 20)
    try:
        outcomes = ["SUCCESS"] * 9 + ["FAILURE"] * 11  # 9/20 = 0.45 exactly
        _insert_resolved_since(conn, heuristic_id, outcomes, RUN_DATE)
        update_lifecycle(conn, clock_at())
    finally:
        object.__setattr__(settings, "HEURISTIC_ROLLING_WINDOW", original_window)

    row = conn.execute("SELECT status FROM agent_memory WHERE id = ?", (heuristic_id,)).fetchone()
    assert row["status"] == "active"  # exactly 0.45 is NOT "< 0.45" -- not demoted


def test_promotion_moves_only_one_step_even_with_overwhelming_evidence():
    conn = make_portfolio_db()
    insert_agent(conn)
    heuristic_id = insert_heuristic(conn, status="testing")
    _set_resolved_applications(conn, heuristic_id, successes=10, failures=0)  # clears the reinforced bar too

    update_lifecycle(conn, clock_at())

    row = conn.execute("SELECT status FROM agent_memory WHERE id = ?", (heuristic_id,)).fetchone()
    assert row["status"] == "active"  # not "reinforced" -- one step per call


def test_no_flip_flop_after_demotion_needs_fresh_epoch_evidence_to_repromote():
    conn = make_portfolio_db()
    insert_agent(conn)
    heuristic_id = insert_heuristic(conn, status="active")

    _insert_resolved_since(conn, heuristic_id, ["SUCCESS"] * 20, "2026-09-01")
    _insert_resolved_since(conn, heuristic_id, ["FAILURE"] * 7 + ["SUCCESS"] * 5, "2026-10-01")  # 5/12 = 0.4167

    update_lifecycle(conn, clock_at())  # demotes active -> testing, resets the epoch to today
    row1 = conn.execute(
        "SELECT status, lifecycle_epoch_start FROM agent_memory WHERE id = ?", (heuristic_id,)
    ).fetchone()
    assert row1["status"] == "testing"
    epoch_after_demotion = row1["lifecycle_epoch_start"]
    assert epoch_after_demotion == clock_at().today().isoformat()

    # Lifetime rate is (20+5)/(20+12) = 0.78, well above 60% -- but nothing new has resolved
    # since the epoch yet, so a second call must NOT re-promote it off the stale lifetime record.
    update_lifecycle(conn, clock_at())
    row2 = conn.execute("SELECT status FROM agent_memory WHERE id = ?", (heuristic_id,)).fetchone()
    assert row2["status"] == "testing"

    # Genuinely fresh evidence resolved on/after the epoch: 5 new applications at 100% (Wilson LB = 0.649 >= 0.50).
    _insert_resolved_since(conn, heuristic_id, ["SUCCESS"] * 5, epoch_after_demotion)
    update_lifecycle(conn, clock_at())
    row3 = conn.execute("SELECT status FROM agent_memory WHERE id = ?", (heuristic_id,)).fetchone()
    assert row3["status"] == "active"  # promoted, on epoch stats alone


def test_promotion_needs_five_applications_not_three():
    conn = make_portfolio_db()
    insert_agent(conn)

    three_of_three = insert_heuristic(conn, status="testing")
    _set_resolved_applications(conn, three_of_three, successes=3, failures=0)  # resolved=3, rate=1.0

    five_of_five = insert_heuristic(conn, status="testing")
    _set_resolved_applications(
        conn, five_of_five, successes=5, failures=0
    )  # resolved=5, rate=1.0 (Wilson LB = 0.649 >= 0.50)

    update_lifecycle(conn, clock_at())

    assert (
        conn.execute("SELECT status FROM agent_memory WHERE id = ?", (three_of_three,)).fetchone()["status"]
        == "testing"
    )  # only 3 resolved -- below the new minimum of 5
    assert (
        conn.execute("SELECT status FROM agent_memory WHERE id = ?", (five_of_five,)).fetchone()["status"] == "active"
    )


def test_demotion_logs_rolling_rate_and_sample_sizes_to_activity_log():
    conn = make_portfolio_db()
    insert_agent(conn)
    heuristic_id = insert_heuristic(conn, status="active")
    _insert_resolved_since(conn, heuristic_id, ["SUCCESS"] * 5 + ["FAILURE"] * 7, RUN_DATE)

    update_lifecycle(conn, clock_at())

    row = conn.execute(
        "SELECT metadata_json FROM activity_log WHERE event_type = 'HEURISTIC_STATUS_CHANGED' ORDER BY id DESC LIMIT 1"
    ).fetchone()
    meta = json.loads(row["metadata_json"])
    assert meta["reason"] == "rolling_demotion"
    assert meta["rolling_n"] == 12
    assert abs(meta["rolling_rate"] - 5 / 12) < 1e-3  # metadata rounds rolling_rate to 4 decimals
    assert meta["lifetime_resolved"] == 12
    assert "lifetime_rate" in meta


def test_seek_and_avoid_success_relative_to_the_cost_hurdle():
    conn = make_portfolio_db()
    insert_agent(conn)
    snap = insert_feature_snapshot(conn, "A", RUN_DATE, {"rsi_14": 60.0})
    hurdle = settings.HEURISTIC_SUCCESS_COST_HURDLE_PCT

    seek_id = insert_heuristic(conn, kind="SEEK")
    avoid_id = insert_heuristic(conn, kind="AVOID")

    def pending(heuristic_id, ticker):
        d = insert_decision(conn, AGENT, ticker, RUN_DATE, snap)
        conn.execute(
            "INSERT INTO heuristic_applications (heuristic_id, decision_id, fired_on, horizon_days, outcome) "
            "VALUES (?, ?, ?, 5, 'PENDING')",
            (heuristic_id, d, RUN_DATE),
        )
        return d

    seek_above, seek_at, seek_below = pending(seek_id, "SA"), pending(seek_id, "SAT"), pending(seek_id, "SB")
    avoid_above, avoid_at, avoid_below = pending(avoid_id, "AA"), pending(avoid_id, "AAT"), pending(avoid_id, "AB")

    for d in (seek_above, avoid_above):
        insert_forward_return(conn, d, 5, hurdle + 0.5)
    for d in (seek_at, avoid_at):
        insert_forward_return(conn, d, 5, hurdle)
    for d in (seek_below, avoid_below):
        insert_forward_return(conn, d, 5, hurdle - 0.5)

    resolved = resolve_pending_applications(conn, clock_at())
    assert resolved == 6

    def outcome(decision_id):
        return conn.execute(
            "SELECT outcome FROM heuristic_applications WHERE decision_id = ?", (decision_id,)
        ).fetchone()["outcome"]

    assert outcome(seek_above) == "SUCCESS"
    assert outcome(seek_at) == "FAILURE"  # SEEK needs strictly > hurdle
    assert outcome(seek_below) == "FAILURE"
    assert outcome(avoid_above) == "FAILURE"
    assert outcome(avoid_at) == "SUCCESS"  # AVOID succeeds at <= hurdle
    assert outcome(avoid_below) == "SUCCESS"


def test_already_resolved_applications_are_never_re_resolved_by_the_new_rule():
    conn = make_portfolio_db()
    insert_agent(conn)
    snap = insert_feature_snapshot(conn, "A", RUN_DATE, {"rsi_14": 60.0})
    heuristic_id = insert_heuristic(conn, kind="SEEK")
    d = insert_decision(conn, AGENT, "X", RUN_DATE, snap)
    conn.execute(
        "INSERT INTO heuristic_applications (heuristic_id, decision_id, fired_on, horizon_days, outcome, resolved_on) "
        "VALUES (?, ?, ?, 5, 'SUCCESS', ?)",
        (heuristic_id, d, RUN_DATE, RUN_DATE),
    )
    # No forward_returns row at all for this decision -- if the already-resolved row were
    # re-evaluated it would have nothing to resolve against; it must simply be left alone.
    resolved = resolve_pending_applications(conn, clock_at())
    assert resolved == 0
    assert (
        conn.execute("SELECT outcome FROM heuristic_applications WHERE decision_id = ?", (d,)).fetchone()["outcome"]
        == "SUCCESS"
    )


def test_run_nightly_twice_in_a_row_changes_nothing_the_second_time():
    conn = make_portfolio_db()
    insert_agent(conn)
    snap = insert_feature_snapshot(conn, "A", RUN_DATE, {"rsi_14": 60.0})
    insert_decision(conn, AGENT, "A", RUN_DATE, snap)
    insert_heuristic(conn, trigger_json=json.dumps({"feature": "rsi_14", "op": ">", "value": 55}))

    first = run_nightly(conn, clock_at(), RUN_DATE)
    assert first["new_applications"] == 1

    second = run_nightly(conn, clock_at(), RUN_DATE)
    assert second["new_applications"] == 0
    assert second["resolved_applications"] == 0
    assert second["status_changes"] == []


# --- Phase 1: Compliance tracking & exit-side heuristics --------------------------------------


def test_compliance_tracking_on_entry_decisions():
    conn = make_portfolio_db()
    insert_agent(conn)
    snap = insert_feature_snapshot(conn, "A", RUN_DATE, {"rsi_14": 60.0})
    # Decision 1: Agent bought -> complies with SEEK, defies AVOID
    cur1 = conn.execute(
        "INSERT INTO decisions (run_date, agent_id, ticker, source, action, reasoning, snapshot_id, created_at) "
        "VALUES (?, ?, 'A', 'LLM', 'BUY', 'test', ?, ?)",
        (RUN_DATE, AGENT, snap, NOW),
    )
    did_buy = cur1.lastrowid
    # Decision 2: Agent held -> defies SEEK, complies with AVOID
    cur2 = conn.execute(
        "INSERT INTO decisions (run_date, agent_id, ticker, source, action, reasoning, snapshot_id, created_at) "
        "VALUES (?, ?, 'B', 'LLM', 'HOLD', 'test', ?, ?)",
        (RUN_DATE, AGENT, snap, NOW),
    )
    did_hold = cur2.lastrowid

    h_seek = insert_heuristic(conn, kind="SEEK", trigger_json=json.dumps({"feature": "rsi_14", "op": ">", "value": 55}))
    h_avoid = insert_heuristic(
        conn, kind="AVOID", trigger_json=json.dumps({"feature": "rsi_14", "op": ">", "value": 55})
    )

    new_apps = evaluate_triggers_for_date(conn, clock_at(), RUN_DATE)
    assert new_apps == 4

    # Check compliance values
    row_seek_buy = conn.execute(
        "SELECT complied FROM heuristic_applications WHERE heuristic_id = ? AND decision_id = ?", (h_seek, did_buy)
    ).fetchone()
    assert row_seek_buy["complied"] == 1

    row_seek_hold = conn.execute(
        "SELECT complied FROM heuristic_applications WHERE heuristic_id = ? AND decision_id = ?", (h_seek, did_hold)
    ).fetchone()
    assert row_seek_hold["complied"] == 0

    row_avoid_buy = conn.execute(
        "SELECT complied FROM heuristic_applications WHERE heuristic_id = ? AND decision_id = ?", (h_avoid, did_buy)
    ).fetchone()
    assert row_avoid_buy["complied"] == 0

    row_avoid_hold = conn.execute(
        "SELECT complied FROM heuristic_applications WHERE heuristic_id = ? AND decision_id = ?", (h_avoid, did_hold)
    ).fetchone()
    assert row_avoid_hold["complied"] == 1


def test_exit_side_heuristic_fires_on_open_positions():
    conn = make_portfolio_db()
    insert_agent(conn)
    # Insert an OPEN position
    cur = conn.execute(
        "INSERT INTO positions (agent_id, ticker, sector, shares, avg_entry_price_paise, stop_paise, target_paise, "
        "last_price_paise, status, entry_date, entry_reasoning) "
        "VALUES (?, 'INFY', 'Technology', 10, 150000, 140000, 170000, 155000, 'OPEN', '2026-10-10', 'entered')",
        (AGENT,),
    )
    pos_id = cur.lastrowid

    # Snapshot for today (RUN_DATE)
    insert_feature_snapshot(conn, "INFY", RUN_DATE, {"rsi_14": 75.0})
    h_exit = insert_heuristic(
        conn, kind="SEEK", trigger_json=json.dumps({"feature": "rsi_14", "op": ">", "value": 70}), context="EXIT"
    )
    # An ENTRY heuristic on the same trigger must NOT fire on open positions
    h_entry = insert_heuristic(
        conn, kind="SEEK", trigger_json=json.dumps({"feature": "rsi_14", "op": ">", "value": 70}), context="ENTRY"
    )

    new_apps = evaluate_triggers_for_date(conn, clock_at(), RUN_DATE)
    assert new_apps == 1

    app = conn.execute("SELECT * FROM heuristic_applications WHERE position_id = ?", (pos_id,)).fetchone()
    assert app is not None
    assert app["context"] == "EXIT"
    assert app["heuristic_id"] == h_exit
    assert app["outcome"] == "PENDING"
    assert app["decision_id"] is None


def test_exit_side_resolution_sign_flip():
    conn = make_portfolio_db()
    insert_agent(conn)
    cur = conn.execute(
        "INSERT INTO positions (agent_id, ticker, sector, shares, avg_entry_price_paise, stop_paise, target_paise, "
        "last_price_paise, status, entry_date, entry_reasoning) "
        "VALUES (?, 'INFY', 'Technology', 10, 150000, 140000, 170000, 155000, 'OPEN', '2026-10-10', 'entered')",
        (AGENT,),
    )
    pos_id = cur.lastrowid

    h_seek = insert_heuristic(conn, kind="SEEK", trigger_json="{}")
    h_avoid = insert_heuristic(conn, kind="AVOID", trigger_json="{}")

    # Manually insert pending exit applications
    conn.execute(
        "INSERT INTO heuristic_applications (heuristic_id, decision_id, position_id, context, fired_on, horizon_days, outcome) "
        "VALUES (?, NULL, ?, 'EXIT', ?, 5, 'PENDING')",
        (h_seek, pos_id, RUN_DATE),
    )
    conn.execute(
        "INSERT INTO heuristic_applications (heuristic_id, decision_id, position_id, context, fired_on, horizon_days, outcome) "
        "VALUES (?, NULL, ?, 'EXIT', ?, 5, 'PENDING')",
        (h_avoid, pos_id, RUN_DATE),
    )

    # Mock OHLCV connection with 6 candles (day 0 to day 5)
    import sqlite3

    ohlcv = sqlite3.connect(":memory:")
    ohlcv.row_factory = sqlite3.Row
    ohlcv.execute("CREATE TABLE ohlcv (ticker TEXT, trade_date TEXT, close REAL)")
    # Scenario: Price fell from 100 to 90 (negative return: -10%)
    for i, p in enumerate([100.0, 98.0, 96.0, 94.0, 92.0, 90.0]):
        d_str = f"2026-10-{19 + i}"
        ohlcv.execute("INSERT INTO ohlcv VALUES ('INFY', ?, ?)", (d_str, p))

    resolved = resolve_pending_applications(conn, clock_at(), ohlcv_conn=ohlcv)
    assert resolved == 2

    # Exit SEEK: price fell (-10% <= hurdle) -> exiting was right -> SUCCESS
    app_seek = conn.execute("SELECT outcome FROM heuristic_applications WHERE heuristic_id = ?", (h_seek,)).fetchone()
    assert app_seek["outcome"] == "SUCCESS"

    # Exit AVOID: price fell (-10% <= hurdle) -> holding was wrong -> FAILURE
    app_avoid = conn.execute("SELECT outcome FROM heuristic_applications WHERE heuristic_id = ?", (h_avoid,)).fetchone()
    assert app_avoid["outcome"] == "FAILURE"
