"""
Tests for GET /api/baseline/comparison.
See docs/backend_implementation_guide_week5.md §3.6.
"""

import sqlite3

import pytest

from ._api_test_helpers import NOW, build_file_db, clear_overrides, make_client, seed_agent


@pytest.fixture(autouse=True)
def _reset_overrides():
    yield
    clear_overrides()


def test_unknown_persona_returns_422_with_clear_message(tmp_path):
    db_path = str(tmp_path / "portfolio.db")
    build_file_db(db_path)
    client = make_client(db_path)

    resp = client.get("/api/baseline/comparison?persona=buffett")

    assert resp.status_code == 422
    assert "buffett" in resp.json()["detail"]


def test_zero_trades_returns_200_with_provisional_and_null_horizons(tmp_path):
    db_path = str(tmp_path / "portfolio.db")
    build_file_db(db_path)
    seed_agent(db_path, "simons", "Jim Simons", "Quant Momentum", "LLM")
    seed_agent(db_path, "baseline-simons-rules", "Baseline Simons Rules", "Rules-only momentum baseline", "BASELINE")
    client = make_client(db_path)

    resp = client.get("/api/baseline/comparison?persona=simons")

    assert resp.status_code == 200
    body = resp.json()
    assert body["is_provisional"] is True
    assert len(body["horizon_returns"]) == 5
    for hr in body["horizon_returns"]:
        assert hr["llm_buy_avg_pct"] is None
        assert hr["selection_alpha_pct"] is None
        assert hr["llm_buy_count"] is None


def test_each_persona_resolves_to_its_own_pair(tmp_path):
    db_path = str(tmp_path / "portfolio.db")
    build_file_db(db_path)
    for llm_id, rules_id in (
        ("lynch", "baseline-lynch-rules"),
        ("marks", "baseline-marks-rules"),
        ("jhunjhunwala", "baseline-rj-rules"),
        ("varsity", "baseline-varsity-rules"),
    ):
        seed_agent(db_path, llm_id, llm_id, "Growth")
        seed_agent(db_path, rules_id, rules_id, "Rules", "BASELINE")
    client = make_client(db_path)

    for persona in ("lynch", "marks", "jhunjhunwala", "varsity"):
        resp = client.get(f"/api/baseline/comparison?persona={persona}")
        assert resp.status_code == 200
        assert resp.json()["persona_id"] == persona


def test_selection_alpha_computed_with_real_forward_returns(tmp_path):
    db_path = str(tmp_path / "portfolio.db")
    build_file_db(db_path)
    seed_agent(db_path, "simons", "Jim Simons", "Quant Momentum", "LLM")
    seed_agent(db_path, "baseline-simons-rules", "Baseline Simons Rules", "Rules-only momentum baseline", "BASELINE")
    conn = sqlite3.connect(db_path, isolation_level=None)
    cur = conn.execute(
        "INSERT INTO decisions (run_date, agent_id, ticker, source, action, created_at) "
        "VALUES ('2026-10-01', 'simons', 'TATAMOTORS', 'LLM', 'BUY', ?)", (NOW,),
    )
    buy_id = cur.lastrowid
    cur = conn.execute(
        "INSERT INTO decisions (run_date, agent_id, ticker, source, action, created_at) "
        "VALUES ('2026-10-01', 'simons', 'INFY', 'LLM', 'HOLD', ?)", (NOW,),
    )
    hold_id = cur.lastrowid
    conn.execute(
        "INSERT INTO forward_returns (decision_id, horizon_days, ret_pct, nifty_ret_pct, computed_on) "
        "VALUES (?, 5, 3.0, 1.0, ?)", (buy_id, NOW),
    )
    conn.execute(
        "INSERT INTO forward_returns (decision_id, horizon_days, ret_pct, nifty_ret_pct, computed_on) "
        "VALUES (?, 5, -1.0, 1.0, ?)", (hold_id, NOW),
    )
    conn.close()
    client = make_client(db_path)

    resp = client.get("/api/baseline/comparison?persona=simons")

    horizon_5 = next(hr for hr in resp.json()["horizon_returns"] if hr["horizon_days"] == 5)
    assert horizon_5["llm_buy_avg_pct"] == 3.0
    assert horizon_5["llm_hold_avg_pct"] == -1.0
    assert horizon_5["nifty500_avg_pct"] == 1.0
    assert horizon_5["selection_alpha_pct"] == 4.0
    assert horizon_5["llm_buy_count"] == 1
