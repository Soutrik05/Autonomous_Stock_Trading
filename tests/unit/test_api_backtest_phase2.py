"""
Phase-2 tests for src/api/routes/backtest.py: pairing heuristics ON/OFF runs in /runs, and the
new Question B holding-duration endpoint.
"""

import sqlite3

import pytest
from fastapi.testclient import TestClient

from ._api_test_helpers import build_file_db, clear_overrides, seed_agent


@pytest.fixture(autouse=True)
def _reset_overrides():
    yield
    clear_overrides()


def _seed_window(backtest_dir, window_id: str, hold_days_by_agent: dict) -> str:
    db_path = str(backtest_dir / f"{window_id}.db")
    build_file_db(db_path)
    seed_agent(db_path, "simons", "Jim Simons", "Quant Momentum")
    conn = sqlite3.connect(db_path, isolation_level=None)
    conn.execute(
        "INSERT INTO daily_nav (agent_id, nav_date, cash_paise, invested_paise, total_paise, nifty500_close) "
        "VALUES ('simons', '2026-10-10', 90000000, 11500000, 101500000, 23460.0)"
    )
    for agent_id, durations in hold_days_by_agent.items():
        for d in durations:
            conn.execute(
                "INSERT INTO positions (agent_id, ticker, sector, shares, avg_entry_price_paise, stop_paise, "
                "target_paise, last_price_paise, status, entry_date, exit_date, hold_days, realized_pnl_paise, "
                "realized_pnl_pct) VALUES (?, 'TATAMOTORS', 'Automobiles', 10, 100000, 90000, 120000, 115000, "
                "'CLOSED', '2026-10-01', '2026-10-10', ?, 10000, 10.0)",
                (agent_id, d),
            )
    conn.close()
    return db_path


def test_runs_pairs_heuristics_on_and_off(tmp_path, monkeypatch):
    from api.main import app
    import api.routes.backtest as backtest_module

    backtest_dir = tmp_path / "storage_backtest"
    backtest_dir.mkdir()
    _seed_window(backtest_dir, "rolling_w9_heuristics_on", {"simons": [5, 10]})
    _seed_window(backtest_dir, "rolling_w9_heuristics_off", {"simons": [5, 10]})
    monkeypatch.setattr(backtest_module, "BACKTEST_DIR", backtest_dir, raising=False)
    client = TestClient(app)

    resp = client.get("/api/backtest/runs")

    pairs = {p["pair_id"]: p for p in resp.json()["runs"]}
    assert "rolling_w9" in pairs
    pair = pairs["rolling_w9"]
    assert pair["heuristics_on"]["window_id"] == "rolling_w9_heuristics_on"
    assert pair["heuristics_off"]["window_id"] == "rolling_w9_heuristics_off"


def test_runs_pair_with_missing_counterpart_is_null(tmp_path, monkeypatch):
    from api.main import app
    import api.routes.backtest as backtest_module

    backtest_dir = tmp_path / "storage_backtest"
    backtest_dir.mkdir()
    _seed_window(backtest_dir, "rolling_w10_heuristics_on", {"simons": [5]})
    monkeypatch.setattr(backtest_module, "BACKTEST_DIR", backtest_dir, raising=False)
    client = TestClient(app)

    resp = client.get("/api/backtest/runs")

    pairs = {p["pair_id"]: p for p in resp.json()["runs"]}
    assert pairs["rolling_w10"]["heuristics_on"] is not None
    assert pairs["rolling_w10"]["heuristics_off"] is None


def test_holding_duration_computes_avg_and_median_per_persona(tmp_path, monkeypatch):
    from api.main import app
    import api.routes.backtest as backtest_module

    backtest_dir = tmp_path / "storage_backtest"
    backtest_dir.mkdir()
    _seed_window(backtest_dir, "rolling_w11_heuristics_on", {"simons": [4, 6, 8, 10]})
    monkeypatch.setattr(backtest_module, "BACKTEST_DIR", backtest_dir, raising=False)
    client = TestClient(app)

    resp = client.get("/api/backtest/runs/rolling_w11_heuristics_on/holding-duration")

    assert resp.status_code == 200
    body = resp.json()
    assert body["evidence_label"] == "BACKTEST_DERIVED"
    persona = body["personas"][0]
    assert persona["agent_id"] == "simons"
    assert persona["closed_trades"] == 4
    assert persona["avg_hold_days"] == 7.0  # (4+6+8+10)/4
    assert persona["median_hold_days"] == 7.0  # (6+8)/2


def test_holding_duration_rejects_path_traversal(tmp_path, monkeypatch):
    from api.main import app
    import api.routes.backtest as backtest_module

    backtest_dir = tmp_path / "storage_backtest"
    backtest_dir.mkdir()
    monkeypatch.setattr(backtest_module, "BACKTEST_DIR", backtest_dir, raising=False)
    client = TestClient(app)

    resp = client.get("/api/backtest/runs/%2e%2e/holding-duration")

    assert resp.status_code == 400
