"""
Unit tests for scheduler.py's build_scheduler(): confirms the two new Week-3 jobs
(heuristic_nightly, weekly_reflection) are registered with the right schedule, and that every
pre-existing job's own schedule is unchanged. Also covers job_heuristic_nightly's two
independently-isolated steps (heuristic evaluation, then forensics post-exit enrichment). No
scheduler is started; no network calls.
See Plan_v3 §1.4, §5.4-§5.5.
"""

import scheduler
from scheduler import build_scheduler, job_heuristic_nightly

# (job_id, day_of_week, hour, minute) for every job that existed before this task.
_PRE_EXISTING_JOBS = [
    ("intraday_monitor_morning", "mon-fri", "9", "20,30,40,50"),
    ("intraday_monitor_midday", "mon-fri", "10-14", "*/10"),
    ("intraday_monitor_afternoon", "mon-fri", "15", "0,10,20"),
    ("order_expiry", "mon-fri", "15", "30"),
    ("settlement", "mon-fri", "15", "35"),
    ("nightly_ingestion", "mon-fri", "20", "0"),
    ("nightly_pipeline_retry_2030", "mon-fri", "20", "30"),
    ("nightly_pipeline_retry_2100", "mon-fri", "21", "0"),
    ("nightly_backup", "*", "21", "45"),  # no day_of_week filter -- runs daily
    ("agent_runner", "mon-fri", "22", "0"),
]


def _jobs_by_id(scheduler):
    return {job.id: job for job in scheduler.get_jobs()}


def _field_value(trigger, field_name: str) -> str:
    for field in trigger.fields:
        if field.name == field_name:
            return str(field)
    raise AssertionError(f"CronTrigger has no field named {field_name!r}")


def test_pre_existing_jobs_are_unchanged():
    jobs = _jobs_by_id(build_scheduler())
    for job_id, day_of_week, hour, minute in _PRE_EXISTING_JOBS:
        assert job_id in jobs, f"missing pre-existing job {job_id!r}"
        trigger = jobs[job_id].trigger
        if day_of_week != "*":
            assert _field_value(trigger, "day_of_week") == day_of_week, job_id
        assert _field_value(trigger, "hour") == hour, job_id
        assert _field_value(trigger, "minute") == minute, job_id


def test_heuristic_nightly_job_is_registered_at_2230_after_agent_runner():
    jobs = _jobs_by_id(build_scheduler())
    assert "heuristic_nightly" in jobs
    trigger = jobs["heuristic_nightly"].trigger
    assert _field_value(trigger, "day_of_week") == "mon-fri"
    assert _field_value(trigger, "hour") == "22"
    assert _field_value(trigger, "minute") == "30"


def test_weekly_reflection_job_is_registered_sunday_1000():
    jobs = _jobs_by_id(build_scheduler())
    assert "weekly_reflection" in jobs
    trigger = jobs["weekly_reflection"].trigger
    assert _field_value(trigger, "day_of_week") == "sun"
    assert _field_value(trigger, "hour") == "10"
    assert _field_value(trigger, "minute") == "0"


def test_build_scheduler_has_exactly_the_expected_job_count():
    jobs = _jobs_by_id(build_scheduler())
    expected_ids = {job_id for job_id, *_ in _PRE_EXISTING_JOBS} | {"heuristic_nightly", "weekly_reflection"}
    assert set(jobs.keys()) == expected_ids


# --- job_heuristic_nightly's two isolated steps --------------------------------------------------


class _StubConn:
    def close(self):
        pass


def _patch_common(monkeypatch, run_nightly_fn, enrich_fn, record_failure_fn=None):
    monkeypatch.setattr(scheduler, "_is_agent_runner_complete", lambda conn, run_date: True)
    monkeypatch.setattr(scheduler, "get_connection", lambda path: _StubConn())
    import learning.forensics
    import learning.memory_manager

    monkeypatch.setattr(learning.memory_manager, "run_nightly", run_nightly_fn)
    monkeypatch.setattr(learning.forensics, "enrich_post_exit", enrich_fn)
    if record_failure_fn is not None:
        import notifications.alerts

        monkeypatch.setattr(notifications.alerts, "record_pipeline_failure", record_failure_fn)


def test_job_heuristic_nightly_runs_both_steps(monkeypatch):
    calls = []
    _patch_common(
        monkeypatch,
        run_nightly_fn=lambda conn, clock, run_date: calls.append("heuristics") or {"errors": {}},
        enrich_fn=lambda conn, clock, run_date: calls.append("post_exit") or 0,
    )
    job_heuristic_nightly()
    assert calls == ["heuristics", "post_exit"]


def test_post_exit_enrichment_failure_does_not_stop_heuristic_evaluation(monkeypatch):
    calls = []
    failures = []
    _patch_common(
        monkeypatch,
        run_nightly_fn=lambda conn, clock, run_date: calls.append("heuristics") or {"errors": {}},
        enrich_fn=lambda conn, clock, run_date: (_ for _ in ()).throw(RuntimeError("boom")),
        record_failure_fn=lambda conn, job, run_date, detail, clock: failures.append((job, detail)),
    )
    job_heuristic_nightly()  # must not raise
    assert calls == ["heuristics"]  # heuristic step ran fine
    assert failures == [("post_exit_enrichment", "boom")]


def test_heuristic_evaluation_failure_does_not_stop_post_exit_enrichment(monkeypatch):
    calls = []
    failures = []
    _patch_common(
        monkeypatch,
        run_nightly_fn=lambda conn, clock, run_date: (_ for _ in ()).throw(RuntimeError("kaboom")),
        enrich_fn=lambda conn, clock, run_date: calls.append("post_exit") or 0,
        record_failure_fn=lambda conn, job, run_date, detail, clock: failures.append((job, detail)),
    )
    job_heuristic_nightly()  # must not raise
    assert calls == ["post_exit"]  # post-exit step still ran
    assert failures == [("heuristic_nightly", "kaboom")]
