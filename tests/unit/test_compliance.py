"""
Unit tests for learning/compliance.py telemetry and escalation.
"""

from datetime import datetime

from core.clock import FakeClock
from learning.compliance import audit_compliance_and_escalate, compute_compliance_summary
from tests.conftest import make_portfolio_db

NOW = "2026-10-20T20:00:00+05:30"
AGENT = "simons"


def clock_at(iso_datetime: str = NOW) -> FakeClock:
    return FakeClock(datetime.fromisoformat(iso_datetime))


def setup_test_data(conn):
    conn.execute(
        "INSERT INTO agents (id, name, philosophy, kind, starting_cash_paise, cash_paise, created_at, updated_at) "
        "VALUES (?, ?, 'Test', 'LLM', 50000000, 50000000, ?, ?)",
        (AGENT, AGENT, NOW, NOW),
    )
    conn.execute(
        "INSERT INTO positions (id, agent_id, ticker, sector, shares, avg_entry_price_paise, stop_paise, target_paise, last_price_paise, status, entry_date, entry_reasoning) "
        "VALUES (1, ?, 'INFY', 'IT', 10, 100000, 90000, 120000, 100000, 'OPEN', '2026-10-10', 'test')",
        (AGENT,),
    )


def insert_rule(conn, kind="AVOID", status="active", confidence=0.75, context="ENTRY") -> int:
    cur = conn.execute(
        "INSERT INTO agent_memory (agent_id, kind, context, heuristic_text, trigger_json, prescribed_action, "
        "status, confidence, times_triggered, times_successful, last_fired_on, created_at, updated_at) "
        "VALUES (?, ?, ?, 'test rule', '{}', 'test action', ?, ?, 0, 0, '2026-10-20', ?, ?)",
        (AGENT, kind, context, status, confidence, NOW, NOW),
    )
    return cur.lastrowid


import itertools

_app_counter = itertools.count()


def insert_app(conn, heuristic_id, complied, outcome="SUCCESS", fired_on=None):
    n = next(_app_counter)
    date_str = fired_on or f"2026-09-{(n % 28) + 1:02d}"
    conn.execute(
        "INSERT INTO heuristic_applications (heuristic_id, decision_id, position_id, context, fired_on, horizon_days, outcome, complied) "
        "VALUES (?, NULL, 1, 'EXIT', ?, 5, ?, ?)",
        (heuristic_id, date_str, outcome, complied),
    )


def test_compliance_insufficient_sample():
    conn = make_portfolio_db()
    setup_test_data(conn)
    h_id = insert_rule(conn)
    # Only 3 applications (< 5)
    for _ in range(3):
        insert_app(conn, h_id, complied=1, outcome="SUCCESS")

    summaries = compute_compliance_summary(conn, agent_id=AGENT)
    assert len(summaries) == 1
    assert summaries[0]["classification"] == "INSUFFICIENT_SAMPLE"
    assert summaries[0]["compliance_rate"] == 1.0


def test_compliance_compliant_performing():
    conn = make_portfolio_db()
    setup_test_data(conn)
    h_id = insert_rule(conn)
    # 8 applications: 7 complied (87.5%), 6 success (75%)
    for _ in range(6):
        insert_app(conn, h_id, complied=1, outcome="SUCCESS")
    insert_app(conn, h_id, complied=1, outcome="FAILURE")
    insert_app(conn, h_id, complied=0, outcome="SUCCESS")

    summaries = compute_compliance_summary(conn, agent_id=AGENT)
    assert len(summaries) == 1
    assert summaries[0]["classification"] == "COMPLIANT_PERFORMING"
    assert summaries[0]["compliance_rate"] == 0.875
    assert summaries[0]["success_rate"] == 0.875


def test_compliance_compliant_underperforming():
    conn = make_portfolio_db()
    setup_test_data(conn)
    h_id = insert_rule(conn)
    # 10 applications: 9 complied (90%), but only 2 successes (20% < 45%)
    for _ in range(2):
        insert_app(conn, h_id, complied=1, outcome="SUCCESS")
    for _ in range(7):
        insert_app(conn, h_id, complied=1, outcome="FAILURE")
    insert_app(conn, h_id, complied=0, outcome="FAILURE")

    summaries = compute_compliance_summary(conn, agent_id=AGENT)
    assert len(summaries) == 1
    assert summaries[0]["classification"] == "COMPLIANT_UNDERPERFORMING"


def test_compliance_defied_valid_and_escalation():
    conn = make_portfolio_db()
    setup_test_data(conn)
    h_id = insert_rule(conn, kind="AVOID", status="active", confidence=0.8)
    # 10 applications: LLM complied only 2 times (20% < 50%), but heuristic was right 8 times (80% >= 60%)
    for _ in range(2):
        insert_app(conn, h_id, complied=1, outcome="SUCCESS")
    for _ in range(6):
        insert_app(conn, h_id, complied=0, outcome="SUCCESS")
    for _ in range(2):
        insert_app(conn, h_id, complied=0, outcome="FAILURE")

    clock = clock_at()
    summaries = compute_compliance_summary(conn, agent_id=AGENT)
    assert len(summaries) == 1
    assert summaries[0]["classification"] == "DEFIED_VALID"

    # Run audit and verify HEURISTIC_COMPLIANCE_BREACH logged
    escalations = audit_compliance_and_escalate(conn, clock)
    assert len(escalations) == 1
    assert escalations[0]["heuristic_id"] == h_id
    assert escalations[0]["classification"] == "DEFIED_VALID"

    logs = conn.execute("SELECT * FROM activity_log WHERE event_type = 'HEURISTIC_COMPLIANCE_BREACH'").fetchall()
    assert len(logs) == 1
    assert f"Agent {AGENT} defied valid rule #{h_id}" in logs[0]["description"]

    # Calling again on the same day should not duplicate the activity log
    escalations_second = audit_compliance_and_escalate(conn, clock)
    assert len(escalations_second) == 1
    logs_second = conn.execute("SELECT * FROM activity_log WHERE event_type = 'HEURISTIC_COMPLIANCE_BREACH'").fetchall()
    assert len(logs_second) == 1
