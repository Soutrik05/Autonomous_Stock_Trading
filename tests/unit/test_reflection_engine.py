"""
Unit tests for learning/engine.py: the weekly reflection job. FakeLLMClient only, no real API
calls. In-memory SQLite (db/schema.sql + every migration) for the portfolio, an in-memory
ohlcv table (for post-exit readiness -- see _is_post_exit_ready) and a FakeClock.

Dates: every trade closes on EXIT_DATE ("2026-11-01"). settings.POST_EXIT_SHORT_DAYS (5)
trading sessions after that are seeded in the ohlcv table at "2026-11-02".."2026-11-06", so
AS_OF_READY ("2026-11-06") makes a trade eligible and AS_OF_NOT_READY ("2026-11-03") does not
(only 2 of the 5 sessions exist yet).
See Plan_v3 §5.4.
"""

import json
from datetime import datetime

import learning.engine as engine
from core.clock import FakeClock
from ingestion.sync_ohlcv import ensure_schema as ensure_ohlcv_schema
from llm.client import FakeLLMClient
from tests.conftest import make_portfolio_db

EXIT_DATE = "2026-11-01"  # a Sunday -- every trade in these tests closes on this date
AS_OF_READY_ISO = "2026-11-06T20:00:00+05:30"  # 5 forward sessions exist -- post-exit ready
AS_OF_NOT_READY_ISO = "2026-11-03T20:00:00+05:30"  # only 2 forward sessions exist -- not ready yet
NOW_ISO = AS_OF_READY_ISO  # kept for the agent-row timestamp; any value is fine there
AGENT = "simons"
OTHER_AGENT = "lynch"
BASELINE_AGENT = "baseline-simons-rules"

GOOD_HEURISTIC = {
    "kind": "SEEK",
    "heuristic_text": "RSI momentum entries above 55 tend to work.",
    "trigger": {"feature": "rsi_14", "op": ">", "value": 55},
    "prescribed_action": "size normally",
    "rationale": "Three winning RSI>55 entries in a row.",
}


def good_response(heuristics=None) -> str:
    return json.dumps({"heuristics": heuristics if heuristics is not None else [GOOD_HEURISTIC]})


def clock_at(iso_datetime: str = AS_OF_READY_ISO) -> FakeClock:
    return FakeClock(datetime.fromisoformat(iso_datetime))


def make_ohlcv_conn():
    import sqlite3

    conn = sqlite3.connect(":memory:", isolation_level=None)
    conn.row_factory = sqlite3.Row
    ensure_ohlcv_schema(conn)
    return conn


def seed_forward_sessions(ohlcv_conn, ticker: str, exit_date: str = EXIT_DATE, sessions: int = 5) -> None:
    """Inserts `sessions` consecutive daily OHLCV rows the day after exit_date, matching
    settings.POST_EXIT_SHORT_DAYS's own counting (learning/forensics.py::fetch_forward_sessions:
    trade_date > exit_date, ascending)."""
    from datetime import date, timedelta

    d = date.fromisoformat(exit_date) + timedelta(days=1)
    for _ in range(sessions):
        ohlcv_conn.execute(
            "INSERT OR REPLACE INTO ohlcv (ticker, trade_date, open, high, low, close, volume) "
            "VALUES (?, ?, 100.0, 101.0, 99.0, 100.0, 100000)",
            (ticker, d.isoformat()),
        )
        d += timedelta(days=1)


def insert_agent(conn, agent_id: str) -> None:
    conn.execute(
        "INSERT INTO agents (id, name, philosophy, kind, starting_cash_paise, cash_paise, created_at, updated_at) "
        "VALUES (?, ?, 'Test', 'LLM', 50000000, 50000000, ?, ?)",
        (agent_id, agent_id, NOW_ISO, NOW_ISO),
    )


def insert_closed_position(
    conn,
    agent_id: str,
    ticker: str = "A",
    exit_date: str = EXIT_DATE,
    hold_days: int = 5,
    realized_pnl_pct: float = 5.0,
    exit_reason: str = "AGENT_SELL",
    forensics_type: str = "TREND_CONTINUATION",
    diagnosis_reason: str = "test reason",
    entry_date: str = "2026-10-01",
    status: str = "CLOSED",
) -> int:
    cur = conn.execute(
        """
        INSERT INTO positions
            (agent_id, ticker, sector, shares, avg_entry_price_paise, stop_paise, target_paise,
             last_price_paise, status, entry_date, exit_date, exit_price_paise, exit_reason,
             hold_days, realized_pnl_paise, realized_pnl_pct, forensics_type, regime_at_exit, diagnosis_json)
        VALUES (?, ?, 'IT', 10, 100000, 90000, 120000, 100000, ?, ?, ?, 105000, ?, ?, 50000, ?, ?, 'NORMAL', ?)
        """,
        (
            agent_id,
            ticker,
            status,
            entry_date,
            exit_date,
            exit_reason,
            hold_days,
            realized_pnl_pct,
            forensics_type if status == "CLOSED" else None,
            json.dumps({"reason": diagnosis_reason}) if status == "CLOSED" else None,
        ),
    )
    return cur.lastrowid


def insert_three_eligible_trades(conn, ohlcv_conn, agent_id: str = AGENT) -> None:
    for i in range(3):
        ticker = f"T{i}"
        insert_closed_position(conn, agent_id, ticker=ticker)
        seed_forward_sessions(ohlcv_conn, ticker)


def insert_open_position(conn, agent_id: str, ticker: str = "OPENPOS", entry_date: str = "2026-09-01") -> int:
    """A still-OPEN position: no exit_date, no forensics_type. Never a reflection candidate."""
    cur = conn.execute(
        "INSERT INTO positions (agent_id, ticker, sector, shares, avg_entry_price_paise, "
        "stop_paise, target_paise, last_price_paise, status, entry_date) "
        "VALUES (?, ?, 'IT', 10, 100000, 90000, 120000, 100000, 'OPEN', ?)",
        (agent_id, ticker, entry_date),
    )
    return cur.lastrowid


def close_position(
    conn,
    position_id: int,
    exit_date: str,
    hold_days: int = 5,
    realized_pnl_pct: float = 5.0,
    exit_reason: str = "AGENT_SELL",
    forensics_type: str | None = "TREND_CONTINUATION",
    diagnosis_reason: str = "closed later",
) -> None:
    conn.execute(
        "UPDATE positions SET status = 'CLOSED', exit_date = ?, exit_price_paise = 105000, "
        "exit_reason = ?, hold_days = ?, realized_pnl_paise = 50000, realized_pnl_pct = ?, "
        "forensics_type = ?, regime_at_exit = 'NORMAL', diagnosis_json = ? WHERE id = ?",
        (
            exit_date,
            exit_reason,
            hold_days,
            realized_pnl_pct,
            forensics_type,
            json.dumps({"reason": diagnosis_reason}) if forensics_type else None,
            position_id,
        ),
    )


def existing_heuristics_for(conn, agent_id: str):
    return conn.execute("SELECT * FROM agent_memory WHERE agent_id = ?", (agent_id,)).fetchall()


def reflection_runs_for(conn, agent_id: str):
    return conn.execute("SELECT * FROM reflection_runs WHERE agent_id = ? ORDER BY id DESC", (agent_id,)).fetchall()


# --- 1-2: sample gate / happy path ----------------------------------------------------------


def test_fewer_than_three_eligible_trades_is_skipped_with_no_llm_call():
    conn = make_portfolio_db()
    ohlcv = make_ohlcv_conn()
    insert_agent(conn, AGENT)
    insert_closed_position(conn, AGENT)
    seed_forward_sessions(ohlcv, "A")
    insert_closed_position(conn, AGENT, ticker="B")
    seed_forward_sessions(ohlcv, "B")
    fake_llm = FakeLLMClient(responses=[good_response()])

    summary = engine.run(conn, clock_at(), llm_client=fake_llm, agent_ids=[AGENT], ohlcv_conn=ohlcv)

    assert summary["agents"][AGENT]["status"] == "SKIPPED_TOO_FEW_TRADES"
    assert len(fake_llm.calls) == 0
    runs = reflection_runs_for(conn, AGENT)
    assert len(runs) == 1
    assert runs[0]["status"] == "SKIPPED_TOO_FEW_TRADES"
    assert runs[0]["last_position_id_reviewed"] == 0  # watermark NOT moved


def test_three_or_more_trades_creates_heuristics_and_moves_watermark():
    conn = make_portfolio_db()
    ohlcv = make_ohlcv_conn()
    insert_agent(conn, AGENT)
    insert_three_eligible_trades(conn, ohlcv)
    fake_llm = FakeLLMClient(responses=[good_response()])

    summary = engine.run(conn, clock_at(), llm_client=fake_llm, agent_ids=[AGENT], ohlcv_conn=ohlcv)

    assert summary["agents"][AGENT]["status"] == "DONE"
    assert summary["agents"][AGENT]["heuristics_created"] == 1
    heuristics = existing_heuristics_for(conn, AGENT)
    assert len(heuristics) == 1
    assert heuristics[0]["status"] == "testing"
    assert heuristics[0]["confidence"] == 0.5
    runs = reflection_runs_for(conn, AGENT)
    assert runs[0]["status"] == "DONE"
    assert runs[0]["trades_reviewed"] == 3
    max_position_id = conn.execute("SELECT MAX(id) AS m FROM positions WHERE agent_id = ?", (AGENT,)).fetchone()["m"]
    assert runs[0]["last_position_id_reviewed"] == max_position_id


# --- 3-4: watermark behaviour -----------------------------------------------------------------


def test_a_second_run_right_after_does_not_reread_the_same_trades():
    conn = make_portfolio_db()
    ohlcv = make_ohlcv_conn()
    insert_agent(conn, AGENT)
    insert_three_eligible_trades(conn, ohlcv)
    fake_llm = FakeLLMClient(responses=[good_response(), good_response()])

    first = engine.run(conn, clock_at(), llm_client=fake_llm, agent_ids=[AGENT], ohlcv_conn=ohlcv)
    calls_after_first = len(fake_llm.calls)
    second = engine.run(conn, clock_at(), llm_client=fake_llm, agent_ids=[AGENT], ohlcv_conn=ohlcv)

    assert first["agents"][AGENT]["status"] == "DONE"
    assert second["agents"][AGENT]["status"] == "SKIPPED_TOO_FEW_TRADES"
    assert len(fake_llm.calls) == calls_after_first  # no new LLM call on the second run
    assert len(existing_heuristics_for(conn, AGENT)) == 1  # no duplicate insert


def test_trades_before_the_watermark_are_never_sent_to_the_llm():
    conn = make_portfolio_db()
    ohlcv = make_ohlcv_conn()
    insert_agent(conn, AGENT)
    old_position_id = insert_closed_position(conn, AGENT, ticker="OLDTICKER")
    seed_forward_sessions(ohlcv, "OLDTICKER")
    conn.execute(
        "INSERT INTO reflection_runs (agent_id, run_date, last_exit_date_reviewed, "
        "last_position_id_in_that_exit_order, last_position_id_reviewed, trades_reviewed, status) "
        "VALUES (?, '2026-10-25', ?, ?, ?, 1, 'DONE')",
        (AGENT, EXIT_DATE, old_position_id, old_position_id),
    )
    insert_three_eligible_trades(conn, ohlcv)  # all have id > old_position_id
    fake_llm = FakeLLMClient(responses=[good_response()])

    summary = engine.run(conn, clock_at(), llm_client=fake_llm, agent_ids=[AGENT], ohlcv_conn=ohlcv)

    assert summary["agents"][AGENT]["status"] == "DONE"
    assert summary["agents"][AGENT]["trades_reviewed"] == 3  # not 4
    assert all("OLDTICKER" not in call["user"] for call in fake_llm.calls)


# --- 5-8: validation ---------------------------------------------------------------------------


def test_an_unknown_metric_name_is_dropped_valid_ones_kept():
    conn = make_portfolio_db()
    ohlcv = make_ohlcv_conn()
    insert_agent(conn, AGENT)
    insert_three_eligible_trades(conn, ohlcv)
    bad = {
        "kind": "SEEK",
        "heuristic_text": "Nonsense trigger.",
        "trigger": {"feature": "totally_unknown_metric_xyz", "op": ">", "value": 1},
        "prescribed_action": "x",
        "rationale": "y",
    }
    fake_llm = FakeLLMClient(responses=[good_response([bad, GOOD_HEURISTIC])])

    summary = engine.run(conn, clock_at(), llm_client=fake_llm, agent_ids=[AGENT], ohlcv_conn=ohlcv)

    assert summary["agents"][AGENT]["heuristics_created"] == 1
    kept = existing_heuristics_for(conn, AGENT)
    assert len(kept) == 1
    assert json.loads(kept[0]["trigger_json"])["feature"] == "rsi_14"


def test_a_metric_not_allowed_for_this_persona_is_dropped():
    conn = make_portfolio_db()
    ohlcv = make_ohlcv_conn()
    insert_agent(conn, AGENT)  # simons has no fundamental hurdles -- "peg" is not allowed for it
    insert_three_eligible_trades(conn, ohlcv)
    disallowed = {
        "kind": "AVOID",
        "heuristic_text": "High PEG avoid.",
        "trigger": {"feature": "peg", "op": ">", "value": 3},
        "prescribed_action": "x",
        "rationale": "y",
    }
    fake_llm = FakeLLMClient(responses=[good_response([disallowed, GOOD_HEURISTIC])])

    summary = engine.run(conn, clock_at(), llm_client=fake_llm, agent_ids=[AGENT], ohlcv_conn=ohlcv)

    assert summary["agents"][AGENT]["heuristics_created"] == 1
    kept = existing_heuristics_for(conn, AGENT)
    assert all(json.loads(h["trigger_json"]).get("feature") != "peg" for h in kept)


def test_a_duplicate_of_an_existing_heuristic_is_dropped():
    conn = make_portfolio_db()
    ohlcv = make_ohlcv_conn()
    insert_agent(conn, AGENT)
    insert_three_eligible_trades(conn, ohlcv)
    now = NOW_ISO
    conn.execute(
        "INSERT INTO agent_memory (agent_id, kind, heuristic_text, trigger_json, prescribed_action, "
        "status, confidence, times_triggered, times_successful, created_at, updated_at) "
        "VALUES (?, 'SEEK', 'existing dup', ?, 'x', 'testing', 0.5, 0, 0, ?, ?)",
        (AGENT, json.dumps(GOOD_HEURISTIC["trigger"]), now, now),
    )
    fake_llm = FakeLLMClient(responses=[good_response([GOOD_HEURISTIC])])

    summary = engine.run(conn, clock_at(), llm_client=fake_llm, agent_ids=[AGENT], ohlcv_conn=ohlcv)

    assert summary["agents"][AGENT]["heuristics_created"] == 0
    assert len(existing_heuristics_for(conn, AGENT)) == 1  # only the pre-existing one
    rejected = conn.execute("SELECT * FROM activity_log WHERE event_type = 'HEURISTIC_REJECTED'").fetchall()
    assert any("duplicate" in r["description"] for r in rejected)


def test_more_than_the_maximum_is_trimmed():
    conn = make_portfolio_db()
    ohlcv = make_ohlcv_conn()
    insert_agent(conn, AGENT)
    insert_three_eligible_trades(conn, ohlcv)
    four_heuristics = [
        {
            "kind": "SEEK",
            "heuristic_text": f"Rule {i}",
            "trigger": {"feature": "rsi_14", "op": ">", "value": 50 + i},
            "prescribed_action": "x",
            "rationale": "y",
        }
        for i in range(4)
    ]
    fake_llm = FakeLLMClient(responses=[good_response(four_heuristics)])

    summary = engine.run(conn, clock_at(), llm_client=fake_llm, agent_ids=[AGENT], ohlcv_conn=ohlcv)

    assert summary["agents"][AGENT]["heuristics_proposed"] == 4
    assert summary["agents"][AGENT]["heuristics_created"] == 3  # settings.MAX_NEW_HEURISTICS_PER_REFLECTION
    assert len(existing_heuristics_for(conn, AGENT)) == 3


# --- 9: repair retry and total failure ---------------------------------------------------------


def test_malformed_json_then_a_good_repair_works():
    conn = make_portfolio_db()
    ohlcv = make_ohlcv_conn()
    insert_agent(conn, AGENT)
    insert_three_eligible_trades(conn, ohlcv)
    fake_llm = FakeLLMClient(responses=["not valid json {{{", good_response()])

    summary = engine.run(conn, clock_at(), llm_client=fake_llm, agent_ids=[AGENT], ohlcv_conn=ohlcv)

    assert summary["agents"][AGENT]["status"] == "DONE"
    assert len(fake_llm.calls) == 2  # first + repair, no fallback needed
    assert len(existing_heuristics_for(conn, AGENT)) == 1


def test_llm_failure_after_retries_writes_nothing_and_leaves_watermark_unchanged():
    conn = make_portfolio_db()
    ohlcv = make_ohlcv_conn()
    insert_agent(conn, AGENT)
    insert_three_eligible_trades(conn, ohlcv)
    fake_llm = FakeLLMClient(responses=["still not json", "still not json"])

    summary = engine.run(
        conn,
        clock_at(),
        llm_client=fake_llm,
        agent_ids=[AGENT],
        fallback_client=None,
        ohlcv_conn=ohlcv,
    )

    assert summary["agents"][AGENT]["status"] == "LLM_FAILED"
    assert reflection_runs_for(conn, AGENT) == []  # nothing written at all
    assert existing_heuristics_for(conn, AGENT) == []


# --- 10-11: isolation ---------------------------------------------------------------------------


def test_one_agents_failure_does_not_stop_the_next_agent(monkeypatch):
    conn = make_portfolio_db()
    ohlcv = make_ohlcv_conn()
    insert_agent(conn, AGENT)
    insert_agent(conn, OTHER_AGENT)
    insert_three_eligible_trades(conn, ohlcv, AGENT)
    insert_three_eligible_trades(conn, ohlcv, OTHER_AGENT)
    fake_llm = FakeLLMClient(responses=[good_response()])

    original = engine._load_eligible_trades

    def _boom(conn_, ohlcv_, agent_id, *a, **kw):
        if agent_id == AGENT:
            raise RuntimeError("boom")
        return original(conn_, ohlcv_, agent_id, *a, **kw)

    monkeypatch.setattr(engine, "_load_eligible_trades", _boom)

    summary = engine.run(conn, clock_at(), llm_client=fake_llm, agent_ids=[AGENT, OTHER_AGENT], ohlcv_conn=ohlcv)

    assert summary["agents"][AGENT]["status"] == "ERROR"
    assert summary["agents"][OTHER_AGENT]["status"] == "DONE"


def test_the_baseline_agent_is_skipped():
    conn = make_portfolio_db()
    ohlcv = make_ohlcv_conn()
    insert_agent(conn, BASELINE_AGENT)
    insert_three_eligible_trades(conn, ohlcv, BASELINE_AGENT)
    fake_llm = FakeLLMClient(responses=[good_response()])

    summary = engine.run(conn, clock_at(), llm_client=fake_llm, agent_ids=[BASELINE_AGENT], ohlcv_conn=ohlcv)

    assert BASELINE_AGENT not in summary["agents"]
    assert len(fake_llm.calls) == 0


# --- 12: prompt content -----------------------------------------------------------------------


def test_prompt_contains_allowed_metrics_and_forensics_labels():
    conn = make_portfolio_db()
    ohlcv = make_ohlcv_conn()
    insert_agent(conn, AGENT)
    insert_three_eligible_trades(conn, ohlcv)
    fake_llm = FakeLLMClient(responses=[good_response()])

    engine.run(conn, clock_at(), llm_client=fake_llm, agent_ids=[AGENT], ohlcv_conn=ohlcv)

    system_prompt = fake_llm.calls[0]["system"]
    assert "rsi_14" in system_prompt  # an allowed metric for simons
    assert "TREND_CONTINUATION" in system_prompt  # a real forensics.py label
    assert "CORP_ACTION_ARTIFACT" in system_prompt


# --- Task 2: post-exit readiness gates eligibility, and the watermark never skips ----------------


def test_a_recent_trade_is_not_sent_to_the_llm():
    """A trade that closed too recently (post-exit data not ready) must not appear in the
    prompt, and must not even count toward the sample gate."""
    conn = make_portfolio_db()
    ohlcv = make_ohlcv_conn()
    insert_agent(conn, AGENT)
    insert_three_eligible_trades(conn, ohlcv)  # 3 ready trades
    recent_id = insert_closed_position(conn, AGENT, ticker="RECENT")
    seed_forward_sessions(ohlcv, "RECENT", sessions=2)  # only 2 of 5 sessions exist
    fake_llm = FakeLLMClient(responses=[good_response()])

    summary = engine.run(conn, clock_at(AS_OF_NOT_READY_ISO), llm_client=fake_llm, agent_ids=[AGENT], ohlcv_conn=ohlcv)

    # At AS_OF_NOT_READY_ISO, none of the 3 "eligible" trades have 5 forward sessions either
    # (they were seeded relative to EXIT_DATE, same as RECENT) -- the whole agent should be
    # blocked at the very first position, matching the id>watermark ascending scan.
    assert summary["agents"][AGENT]["status"] == "SKIPPED_TOO_FEW_TRADES"
    assert summary["agents"][AGENT]["trades_reviewed"] == 0
    assert len(fake_llm.calls) == 0


def test_watermark_does_not_skip_over_a_recent_trade_blocking_a_later_one():
    """Position 10 (recent, not ready) must block the watermark even though position 11
    (later id, already ready) would otherwise qualify -- the exact scenario the task warned
    about: id order is entry order, not exit order."""
    conn = make_portfolio_db()
    ohlcv = make_ohlcv_conn()
    insert_agent(conn, AGENT)

    recent_id = insert_closed_position(conn, AGENT, ticker="RECENT", exit_date="2026-11-05")
    seed_forward_sessions(ohlcv, "RECENT", exit_date="2026-11-05", sessions=1)  # not ready by 11-06

    ready_id = insert_closed_position(conn, AGENT, ticker="READY", exit_date="2026-10-20")
    seed_forward_sessions(ohlcv, "READY", exit_date="2026-10-20", sessions=5)  # long since ready
    assert ready_id > recent_id

    fake_llm = FakeLLMClient(responses=[good_response()])
    summary = engine.run(conn, clock_at(AS_OF_READY_ISO), llm_client=fake_llm, agent_ids=[AGENT], ohlcv_conn=ohlcv)

    # Blocked at RECENT (the first position after the watermark) -- READY is never reviewed
    # this run, and the watermark must NOT have jumped past RECENT to READY's id.
    assert summary["agents"][AGENT]["status"] == "SKIPPED_TOO_FEW_TRADES"
    assert summary["agents"][AGENT]["trades_reviewed"] == 0
    runs = reflection_runs_for(conn, AGENT)
    assert runs[0]["last_position_id_reviewed"] == 0  # unchanged -- never advanced past RECENT
    assert len(fake_llm.calls) == 0


def test_a_recent_trade_is_picked_up_once_it_becomes_old_enough():
    """The same RECENT/READY setup, but run a second time once RECENT's post-exit data has
    matured -- both trades (plus one more to hit the sample gate) must now be reviewed, and the
    watermark must advance all the way to the newest one."""
    conn = make_portfolio_db()
    ohlcv = make_ohlcv_conn()
    insert_agent(conn, AGENT)

    # simons' lookback_days is 14 -- keep READY/THIRD's exit_date within that window of the
    # SECOND run's as_of_date (2026-11-11) too, so they don't fall out of the reflection
    # window by the time RECENT finally matures.
    recent_id = insert_closed_position(conn, AGENT, ticker="RECENT", exit_date="2026-11-05")
    seed_forward_sessions(ohlcv, "RECENT", exit_date="2026-11-05", sessions=1)

    ready_id = insert_closed_position(conn, AGENT, ticker="READY", exit_date="2026-10-29")
    seed_forward_sessions(ohlcv, "READY", exit_date="2026-10-29", sessions=5)

    third_id = insert_closed_position(conn, AGENT, ticker="THIRD", exit_date="2026-10-29")
    seed_forward_sessions(ohlcv, "THIRD", exit_date="2026-10-29", sessions=5)

    fake_llm = FakeLLMClient(responses=[good_response()])

    # First run (not ready): nothing reviewed, as in the test above.
    first = engine.run(conn, clock_at(AS_OF_READY_ISO), llm_client=fake_llm, agent_ids=[AGENT], ohlcv_conn=ohlcv)
    assert first["agents"][AGENT]["status"] == "SKIPPED_TOO_FEW_TRADES"

    # RECENT matures: 5 forward sessions now exist.
    seed_forward_sessions(ohlcv, "RECENT", exit_date="2026-11-05", sessions=5)
    later = engine.run(
        conn, clock_at("2026-11-11T20:00:00+05:30"), llm_client=fake_llm, agent_ids=[AGENT], ohlcv_conn=ohlcv
    )

    assert later["agents"][AGENT]["status"] == "DONE"
    assert later["agents"][AGENT]["trades_reviewed"] == 3
    runs = reflection_runs_for(conn, AGENT)
    # Exit order, not id order: RECENT has the lowest id but the LATEST exit_date (2026-11-05,
    # vs READY/THIRD's 2026-10-29), so it's last in the walk -- the watermark lands on its id,
    # even though that id is numerically the smallest of the three.
    assert runs[0]["last_exit_date_reviewed"] == "2026-11-05"
    assert runs[0]["last_position_id_in_that_exit_order"] == recent_id
    assert runs[0]["last_position_id_reviewed"] == recent_id


# --- Follow-up task: exit-order watermark (fixes the open-position-blocks-everything bug) ------


def test_an_open_position_with_a_low_id_does_not_block_later_closed_trades():
    conn = make_portfolio_db()
    ohlcv = make_ohlcv_conn()
    insert_agent(conn, AGENT)
    insert_open_position(conn, AGENT, ticker="SLOWOPEN")  # low id, still open -- never a candidate
    insert_three_eligible_trades(conn, ohlcv)  # higher ids, closed and ready
    fake_llm = FakeLLMClient(responses=[good_response()])

    summary = engine.run(conn, clock_at(), llm_client=fake_llm, agent_ids=[AGENT], ohlcv_conn=ohlcv)

    assert summary["agents"][AGENT]["status"] == "DONE"
    assert summary["agents"][AGENT]["trades_reviewed"] == 3
    assert all("SLOWOPEN" not in call["user"] for call in fake_llm.calls)


def test_an_open_position_is_picked_up_once_it_closes_with_a_later_exit_date():
    """Once SLOWOPEN finally closes, it becomes a normal CLOSED candidate and is reviewed in a
    later run, as long as its exit_date is later than the watermark recorded while it was still
    open -- true for any real (monotonic) Clock, since a position can only close at or after
    "now", and the watermark's exit_date can never be later than "now" either.

    If a position's exit_date were somehow EARLIER than an already-recorded watermark -- not
    possible with sequential time, since nothing can exit in the past relative to when an
    earlier run observed "now" -- _load_eligible_trades' `(exit_date, id) > watermark` filter
    would exclude it forever, silently. There is no code guard against this because it cannot
    happen with core.clock.SystemClock (or a FakeClock a test only ever advances forward); it is
    documented here rather than defended against in code.
    """
    conn = make_portfolio_db()
    ohlcv = make_ohlcv_conn()
    insert_agent(conn, AGENT)
    open_id = insert_open_position(conn, AGENT, ticker="SLOWOPEN")
    insert_three_eligible_trades(conn, ohlcv)
    fake_llm = FakeLLMClient(responses=[good_response(), good_response()])

    first = engine.run(conn, clock_at(), llm_client=fake_llm, agent_ids=[AGENT], ohlcv_conn=ohlcv)
    assert first["agents"][AGENT]["status"] == "DONE"
    assert all("SLOWOPEN" not in call["user"] for call in fake_llm.calls)

    later_exit = "2026-11-08"  # after the first run's watermark (EXIT_DATE = 2026-11-01)
    close_position(conn, open_id, exit_date=later_exit)
    seed_forward_sessions(ohlcv, "SLOWOPEN", exit_date=later_exit, sessions=5)
    insert_closed_position(conn, AGENT, ticker="X1", exit_date=later_exit)
    seed_forward_sessions(ohlcv, "X1", exit_date=later_exit, sessions=5)
    insert_closed_position(conn, AGENT, ticker="X2", exit_date=later_exit)
    seed_forward_sessions(ohlcv, "X2", exit_date=later_exit, sessions=5)

    second = engine.run(
        conn, clock_at("2026-11-13T20:00:00+05:30"), llm_client=fake_llm, agent_ids=[AGENT], ohlcv_conn=ohlcv
    )

    assert second["agents"][AGENT]["status"] == "DONE"
    assert second["agents"][AGENT]["trades_reviewed"] == 3
    assert any("SLOWOPEN" in call["user"] for call in fake_llm.calls)


def test_a_too_recent_trade_blocks_only_trades_that_closed_after_it():
    conn = make_portfolio_db()
    ohlcv = make_ohlcv_conn()
    insert_agent(conn, AGENT)

    # C, C2, C3: earliest exit_dates, long since post-exit ready -- must be reviewed.
    for i, exit_date in enumerate(["2026-10-25", "2026-10-26", "2026-10-27"]):
        ticker = f"C{i}"
        insert_closed_position(conn, AGENT, ticker=ticker, exit_date=exit_date)
        seed_forward_sessions(ohlcv, ticker, exit_date=exit_date, sessions=5)

    # A: too recent (only 1 of 5 sessions exists) -- must block the scan here.
    insert_closed_position(conn, AGENT, ticker="RECENT_A", exit_date="2026-11-05")
    seed_forward_sessions(ohlcv, "RECENT_A", exit_date="2026-11-05", sessions=1)
    # B: closed AFTER A -- must be blocked too, even though B's own data might otherwise be ready.
    insert_closed_position(conn, AGENT, ticker="RECENT_B", exit_date="2026-11-06")
    seed_forward_sessions(ohlcv, "RECENT_B", exit_date="2026-11-06", sessions=5)

    fake_llm = FakeLLMClient(responses=[good_response()])
    summary = engine.run(conn, clock_at(AS_OF_READY_ISO), llm_client=fake_llm, agent_ids=[AGENT], ohlcv_conn=ohlcv)

    assert summary["agents"][AGENT]["status"] == "DONE"
    assert summary["agents"][AGENT]["trades_reviewed"] == 3  # C0, C1, C2 only
    calls_text = " ".join(c["user"] for c in fake_llm.calls)
    assert "C0: entered" in calls_text
    assert "RECENT_A: entered" not in calls_text
    assert "RECENT_B: entered" not in calls_text


def test_a_trade_with_no_forensics_type_does_not_block_earlier_trades_and_is_picked_up_later():
    conn = make_portfolio_db()
    ohlcv = make_ohlcv_conn()
    insert_agent(conn, AGENT)

    for i, exit_date in enumerate(["2026-10-25", "2026-10-26", "2026-10-27"]):
        ticker = f"EARLY{i}"
        insert_closed_position(conn, AGENT, ticker=ticker, exit_date=exit_date)
        seed_forward_sessions(ohlcv, ticker, exit_date=exit_date, sessions=5)

    # Closed, but forensics hasn't run (forensics_type NULL) -- exit_date after the EARLY three.
    pending_id = insert_closed_position(conn, AGENT, ticker="PENDING", exit_date="2026-10-29", forensics_type=None)
    seed_forward_sessions(ohlcv, "PENDING", exit_date="2026-10-29", sessions=5)

    fake_llm = FakeLLMClient(responses=[good_response(), good_response()])
    first = engine.run(conn, clock_at(AS_OF_READY_ISO), llm_client=fake_llm, agent_ids=[AGENT], ohlcv_conn=ohlcv)

    assert first["agents"][AGENT]["status"] == "DONE"
    assert first["agents"][AGENT]["trades_reviewed"] == 3  # the three EARLY trades only
    calls_text = " ".join(c["user"] for c in fake_llm.calls)
    assert "PENDING: entered" not in calls_text

    # Forensics completes for PENDING; two more trades to hit the sample gate on the next run.
    conn.execute(
        "UPDATE positions SET forensics_type = 'TREND_CONTINUATION' WHERE id = ?",
        (pending_id,),
    )
    insert_closed_position(conn, AGENT, ticker="LATER1", exit_date="2026-10-30")
    seed_forward_sessions(ohlcv, "LATER1", exit_date="2026-10-30", sessions=5)
    insert_closed_position(conn, AGENT, ticker="LATER2", exit_date="2026-10-31")
    seed_forward_sessions(ohlcv, "LATER2", exit_date="2026-10-31", sessions=5)

    second = engine.run(conn, clock_at(AS_OF_READY_ISO), llm_client=fake_llm, agent_ids=[AGENT], ohlcv_conn=ohlcv)

    assert second["agents"][AGENT]["status"] == "DONE"
    assert second["agents"][AGENT]["trades_reviewed"] == 3  # PENDING, LATER1, LATER2
    second_calls_text = fake_llm.calls[-1]["user"]
    assert "PENDING: entered" in second_calls_text


def test_watermark_does_not_move_when_the_llm_call_fails():
    conn = make_portfolio_db()
    ohlcv = make_ohlcv_conn()
    insert_agent(conn, AGENT)
    insert_three_eligible_trades(conn, ohlcv)
    fake_llm = FakeLLMClient(responses=["still not json", "still not json"])

    summary = engine.run(
        conn,
        clock_at(),
        llm_client=fake_llm,
        agent_ids=[AGENT],
        fallback_client=None,
        ohlcv_conn=ohlcv,
    )
    assert summary["agents"][AGENT]["status"] == "LLM_FAILED"
    assert reflection_runs_for(conn, AGENT) == []

    # Nothing was consumed by the failed attempt -- a later run with a working LLM must still
    # see the exact same 3 trades.
    fake_llm2 = FakeLLMClient(responses=[good_response()])
    second = engine.run(conn, clock_at(), llm_client=fake_llm2, agent_ids=[AGENT], ohlcv_conn=ohlcv)
    assert second["agents"][AGENT]["status"] == "DONE"
    assert second["agents"][AGENT]["trades_reviewed"] == 3


def test_two_consecutive_runs_never_review_the_same_trade_twice():
    conn = make_portfolio_db()
    ohlcv = make_ohlcv_conn()
    insert_agent(conn, AGENT)
    insert_three_eligible_trades(conn, ohlcv)
    fake_llm = FakeLLMClient(responses=[good_response(), good_response()])

    first = engine.run(conn, clock_at(), llm_client=fake_llm, agent_ids=[AGENT], ohlcv_conn=ohlcv)
    first_calls = len(fake_llm.calls)
    assert first["agents"][AGENT]["status"] == "DONE"

    second = engine.run(conn, clock_at(), llm_client=fake_llm, agent_ids=[AGENT], ohlcv_conn=ohlcv)

    assert second["agents"][AGENT]["status"] == "SKIPPED_TOO_FEW_TRADES"
    assert second["agents"][AGENT]["trades_reviewed"] == 0
    assert len(fake_llm.calls) == first_calls  # no new LLM call -- nothing re-reviewed


# --- Phase 0: Dedup key fixes & forensics base rates -----------------------------------------


def test_deprecated_heuristic_is_not_reinserted():
    conn = make_portfolio_db()
    ohlcv = make_ohlcv_conn()
    insert_agent(conn, AGENT)
    insert_three_eligible_trades(conn, ohlcv)
    now = NOW_ISO
    # Insert a deprecated heuristic with the same trigger and kind
    conn.execute(
        "INSERT INTO agent_memory (agent_id, kind, heuristic_text, trigger_json, prescribed_action, "
        "status, confidence, times_triggered, times_successful, created_at, updated_at) "
        "VALUES (?, 'SEEK', 'old deprecated rule', ?, 'x', 'deprecated', 0.2, 5, 1, ?, ?)",
        (AGENT, json.dumps(GOOD_HEURISTIC["trigger"]), now, now),
    )
    fake_llm = FakeLLMClient(responses=[good_response([GOOD_HEURISTIC])])

    summary = engine.run(conn, clock_at(), llm_client=fake_llm, agent_ids=[AGENT], ohlcv_conn=ohlcv)

    assert summary["agents"][AGENT]["heuristics_created"] == 0
    rejected = conn.execute("SELECT * FROM activity_log WHERE event_type = 'HEURISTIC_REJECTED'").fetchall()
    assert any("duplicate of a deprecated heuristic" in r["description"] for r in rejected)


def test_seek_and_avoid_on_same_trigger_do_not_collide():
    conn = make_portfolio_db()
    ohlcv = make_ohlcv_conn()
    insert_agent(conn, AGENT)
    insert_three_eligible_trades(conn, ohlcv)
    now = NOW_ISO
    # Existing active heuristic is AVOID on rsi_14 > 55
    conn.execute(
        "INSERT INTO agent_memory (agent_id, kind, heuristic_text, trigger_json, prescribed_action, "
        "status, confidence, times_triggered, times_successful, created_at, updated_at) "
        "VALUES (?, 'AVOID', 'avoid high rsi', ?, 'x', 'active', 0.8, 4, 3, ?, ?)",
        (AGENT, json.dumps(GOOD_HEURISTIC["trigger"]), now, now),
    )
    # Propose SEEK on rsi_14 > 55 -- different kind, must NOT be rejected as duplicate
    fake_llm = FakeLLMClient(responses=[good_response([GOOD_HEURISTIC])])

    summary = engine.run(conn, clock_at(), llm_client=fake_llm, agent_ids=[AGENT], ohlcv_conn=ohlcv)

    assert summary["agents"][AGENT]["heuristics_created"] == 1
    heuristics = existing_heuristics_for(conn, AGENT)
    assert len(heuristics) == 2
    kinds = {h["kind"] for h in heuristics}
    assert kinds == {"AVOID", "SEEK"}


def test_forensics_summary_wired_into_reflection_prompt():
    conn = make_portfolio_db()
    ohlcv = make_ohlcv_conn()
    insert_agent(conn, AGENT)
    insert_three_eligible_trades(conn, ohlcv)
    fake_llm = FakeLLMClient(responses=[good_response()])

    summary = engine.run(conn, clock_at(), llm_client=fake_llm, agent_ids=[AGENT], ohlcv_conn=ohlcv)

    assert summary["agents"][AGENT]["status"] == "DONE"
    # Inspect the prompt passed to the fake LLM
    assert len(fake_llm.calls) == 1
    user_prompt = fake_llm.calls[0]["user"]
    assert "AGGREGATE FORENSICS & BASE RATES:" in user_prompt
    assert "Sample Base Rate:" in user_prompt
    assert "Excursions Profile:" in user_prompt


def test_reflection_accepts_exit_context_and_infers_from_action():
    conn = make_portfolio_db()
    ohlcv = make_ohlcv_conn()
    insert_agent(conn, AGENT)
    insert_three_eligible_trades(conn, ohlcv)

    # 1. Explicit context: "EXIT"
    explicit_exit_heuristic = {
        "context": "EXIT",
        "kind": "SEEK",
        "heuristic_text": "Exit when RSI > 70 and momentum fades",
        "trigger": {"feature": "rsi_14", "op": ">", "value": 70},
        "prescribed_action": "SELL to lock in profit",
        "rationale": "Closed trades gave back profits after RSI peaked above 70",
    }
    # 2. Inferred context: "EXIT" from prescribed_action containing "SELL"
    inferred_exit_heuristic = {
        "kind": "SEEK",
        "heuristic_text": "Sell when dist 52w high falls",
        "trigger": {"feature": "dist_52w_high_pct", "op": "<", "value": -10.0},
        "prescribed_action": "SELL immediately",
        "rationale": "Protect capital on trend break",
    }

    fake_llm = FakeLLMClient(responses=[good_response([explicit_exit_heuristic, inferred_exit_heuristic])])

    summary = engine.run(conn, clock_at(), llm_client=fake_llm, agent_ids=[AGENT], ohlcv_conn=ohlcv)

    assert summary["agents"][AGENT]["heuristics_created"] == 2
    rows = conn.execute("SELECT context, prescribed_action FROM agent_memory WHERE agent_id = ?", (AGENT,)).fetchall()
    contexts = [r["context"] for r in rows]
    assert contexts == ["EXIT", "EXIT"]
