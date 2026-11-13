"""
Tests for GET /api/leaderboard and GET /api/agents/nav.
See docs/backend_implementation_guide_week5.md §3.1, §3.5.
"""

import sqlite3

import pytest

from ._api_test_helpers import NOW, build_file_db, clear_overrides, make_client, seed_agent


@pytest.fixture(autouse=True)
def _reset_overrides():
    yield
    clear_overrides()


def test_empty_db_returns_200_with_no_entries(tmp_path):
    db_path = str(tmp_path / "portfolio.db")
    build_file_db(db_path)
    client = make_client(db_path)

    resp = client.get("/api/leaderboard")

    assert resp.status_code == 200
    assert resp.json() == []


def test_agent_with_zero_trades_is_provisional_and_paise_are_integers(tmp_path):
    db_path = str(tmp_path / "portfolio.db")
    build_file_db(db_path)
    seed_agent(db_path, "simons", "Jim Simons", "Quant Momentum", "LLM")
    client = make_client(db_path)

    resp = client.get("/api/leaderboard")

    assert resp.status_code == 200
    entries = resp.json()
    assert len(entries) == 1
    entry = entries[0]
    assert entry["id"] == "simons"
    assert entry["badge"] == "LLM"
    assert entry["strategy_family"] == "Quant Momentum"
    assert entry["is_provisional"] is True
    assert entry["closed_trades"] == 0
    assert isinstance(entry["nav_paise"], int)
    assert isinstance(entry["starting_capital_paise"], int)


def test_baseline_agent_gets_rules_badge_and_null_foundation_model(tmp_path):
    db_path = str(tmp_path / "portfolio.db")
    build_file_db(db_path)
    seed_agent(db_path, "baseline-simons-rules", "Baseline Simons Rules", "Rules-only momentum baseline", "BASELINE")
    client = make_client(db_path)

    resp = client.get("/api/leaderboard")

    entry = resp.json()[0]
    assert entry["badge"] == "RULES"
    assert entry["foundation_model"] is None


def test_llm_agent_foundation_model_comes_from_latest_llm_call(tmp_path):
    db_path = str(tmp_path / "portfolio.db")
    build_file_db(db_path)
    seed_agent(db_path, "simons", "Jim Simons", "Quant Momentum", "LLM")
    conn = sqlite3.connect(db_path, isolation_level=None)
    conn.execute(
        "INSERT INTO llm_calls (agent_id, run_date, model, prompt, response, tokens_in, tokens_out, "
        "latency_ms, parse_status, created_at) VALUES ('simons', '2026-11-04', 'gemini-3.5-flash-lite', "
        "'p', 'r', 10, 10, 100, 'SUCCESS', ?)",
        (NOW,),
    )
    conn.close()
    client = make_client(db_path)

    resp = client.get("/api/leaderboard")

    assert resp.json()[0]["foundation_model"] == "gemini-3.5-flash-lite"


def test_nav_endpoint_empty_db_returns_200_with_empty_list(tmp_path):
    db_path = str(tmp_path / "portfolio.db")
    build_file_db(db_path)
    client = make_client(db_path)

    resp = client.get("/api/agents/nav")

    assert resp.status_code == 200
    assert resp.json() == []


def test_nav_endpoint_rebases_nifty_to_starting_capital_in_paise(tmp_path):
    db_path = str(tmp_path / "portfolio.db")
    build_file_db(db_path)
    seed_agent(db_path, "simons", "Jim Simons", "Quant Momentum", "LLM")
    conn = sqlite3.connect(db_path, isolation_level=None)
    conn.execute(
        "INSERT INTO daily_nav (agent_id, nav_date, cash_paise, invested_paise, total_paise, nifty500_close) "
        "VALUES ('simons', '2026-11-03', 100000000, 0, 100000000, 23000.0)"
    )
    conn.execute(
        "INSERT INTO daily_nav (agent_id, nav_date, cash_paise, invested_paise, total_paise, nifty500_close) "
        "VALUES ('simons', '2026-11-04', 90000000, 11000000, 101000000, 23460.0)"
    )
    conn.close()
    client = make_client(db_path)

    resp = client.get("/api/agents/nav")

    series = resp.json()
    assert len(series) == 2
    day1 = series[0]["values"]
    assert day1["simons"] == 100000000
    assert day1["nifty500"] == 100000000  # first day always rebases to itself
    day2 = series[1]["values"]
    assert day2["simons"] == 101000000
    assert isinstance(day2["nifty500"], int)
    assert day2["nifty500"] == round(100000000 * (23460.0 / 23000.0))
