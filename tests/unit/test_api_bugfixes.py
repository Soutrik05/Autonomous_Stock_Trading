"""
Regression tests for the three bugs fixed in this phase:
  (a) evaluation/comparison.py::compare_selection_alpha queried forward_returns columns that
      don't exist (return_pct/benchmark_return_pct/excess_return_pct); real columns are
      ret_pct/nifty_ret_pct, and excess is now computed in Python.
  (b) src/api/routes/backtest.py's positions query selected opened_at/closed_at, which don't
      exist on positions; the real columns are entry_date/exit_date.
  (c) backtest.py used settings.SIMULATION_DB_PATH, which doesn't exist; it now uses
      settings.BACKTEST_DB_DIR (default storage/backtest) and rejects a window_id containing a
      path separator or "..".
  (d) backtest.py now reads with the same read-only connection as the live routes, and returns
      paise (not rupee floats) from the NAV endpoint.
"""

import sqlite3

import pytest
from fastapi.testclient import TestClient

from ._api_test_helpers import NOW, build_file_db, clear_overrides, seed_agent

pytestmark = pytest.mark.filterwarnings("ignore")


@pytest.fixture(autouse=True)
def _reset_overrides():
    yield
    clear_overrides()


def test_compare_selection_alpha_uses_real_columns(portfolio_conn):
    from evaluation.comparison import compare_selection_alpha

    agent_id = "simons"
    portfolio_conn.execute(
        "INSERT INTO agents (id, name, philosophy, kind, starting_cash_paise, cash_paise, created_at, updated_at) "
        "VALUES (?, ?, 'Quant Momentum', 'LLM', 100000000, 100000000, ?, ?)",
        (agent_id, "Jim Simons", NOW, NOW),
    )
    cur = portfolio_conn.execute(
        "INSERT INTO decisions (run_date, agent_id, ticker, source, action, created_at) "
        "VALUES ('2026-11-01', ?, 'TATAMOTORS', 'LLM', 'BUY', ?)",
        (agent_id, NOW),
    )
    buy_id = cur.lastrowid
    cur = portfolio_conn.execute(
        "INSERT INTO decisions (run_date, agent_id, ticker, source, action, created_at) "
        "VALUES ('2026-11-01', ?, 'INFY', 'LLM', 'HOLD', ?)",
        (agent_id, NOW),
    )
    hold_id = cur.lastrowid
    portfolio_conn.execute(
        "INSERT INTO forward_returns (decision_id, horizon_days, ret_pct, nifty_ret_pct, computed_on) "
        "VALUES (?, 5, 4.0, 1.0, ?)",
        (buy_id, NOW),
    )
    portfolio_conn.execute(
        "INSERT INTO forward_returns (decision_id, horizon_days, ret_pct, nifty_ret_pct, computed_on) "
        "VALUES (?, 5, 0.5, 1.0, ?)",
        (hold_id, NOW),
    )

    # Must not raise sqlite3.OperationalError (the original bug), and must compute real numbers.
    result = compare_selection_alpha(portfolio_conn, horizon_days=5)

    assert result["buy_decisions"]["count"] == 1
    assert result["buy_decisions"]["avg_return_pct"] == 4.0
    assert result["buy_decisions"]["avg_excess_pct"] == 3.0  # 4.0 - 1.0
    assert result["hold_decisions"]["avg_return_pct"] == 0.5
    assert result["selection_alpha_pct"] == 3.5  # 4.0 - 0.5


def _seed_backtest_window(backtest_dir, window_id: str) -> str:
    db_path = str(backtest_dir / f"{window_id}.db")
    build_file_db(db_path)
    seed_agent(db_path, "simons", "Jim Simons", "Quant Momentum")
    seed_agent(db_path, "baseline-simons-rules", "Baseline Simons Rules", "Rules-only momentum baseline", "BASELINE")
    conn = sqlite3.connect(db_path, isolation_level=None)
    conn.execute(
        "INSERT INTO positions (agent_id, ticker, sector, shares, avg_entry_price_paise, stop_paise, "
        "target_paise, last_price_paise, status, entry_date, exit_date, exit_price_paise, exit_reason, "
        "hold_days, realized_pnl_paise, realized_pnl_pct, forensics_type) "
        "VALUES ('simons', 'TATAMOTORS', 'Automobiles', 10, 100000, 90000, 120000, 115000, 'CLOSED', "
        "'2026-10-01', '2026-10-10', 115000, 'AGENT_SELL', 9, 150000, 15.0, 'TREND_CONTINUATION')"
    )
    conn.execute(
        "INSERT INTO daily_nav (agent_id, nav_date, cash_paise, invested_paise, total_paise, nifty500_close) "
        "VALUES ('simons', '2026-10-10', 90000000, 11500000, 101500000, 23460.0)"
    )
    conn.close()
    return db_path


def test_backtest_positions_uses_entry_exit_date_not_opened_closed_at(tmp_path, monkeypatch):
    from api.main import app

    backtest_dir = tmp_path / "storage_backtest"
    backtest_dir.mkdir()
    _seed_backtest_window(backtest_dir, "window1")
    import api.routes.backtest as backtest_module

    monkeypatch.setattr(backtest_module, "BACKTEST_DIR", backtest_dir, raising=False)
    client = TestClient(app)

    resp = client.get("/api/backtest/runs/window1/positions")

    assert resp.status_code == 200  # the original bug raised sqlite3.OperationalError here
    pos = resp.json()["positions"][0]
    assert pos["opened_at"] == "2026-10-01"
    assert pos["closed_at"] == "2026-10-10"
    assert pos["avg_entry_price_paise"] == 100000  # integer paise, not a rupee float


def test_backtest_db_dir_setting_replaces_removed_simulation_db_path(tmp_path, monkeypatch):
    from core.config import settings

    assert hasattr(settings, "BACKTEST_DB_DIR")
    assert not hasattr(settings, "SIMULATION_DB_PATH")


def test_backtest_window_id_rejects_path_traversal(tmp_path, monkeypatch):
    from api.main import app

    backtest_dir = tmp_path / "storage_backtest"
    backtest_dir.mkdir()
    import api.routes.backtest as backtest_module

    monkeypatch.setattr(backtest_module, "BACKTEST_DIR", backtest_dir, raising=False)
    client = TestClient(app)

    for bad_id in ("../../etc/passwd", "..%2Fsecret", "a/b"):
        resp = client.get(f"/api/backtest/runs/{bad_id}/positions")
        assert resp.status_code in (400, 404)  # never a raw file-path escape


def test_backtest_nav_series_is_integer_paise(tmp_path, monkeypatch):
    from api.main import app

    backtest_dir = tmp_path / "storage_backtest"
    backtest_dir.mkdir()
    _seed_backtest_window(backtest_dir, "window1")
    import api.routes.backtest as backtest_module

    monkeypatch.setattr(backtest_module, "BACKTEST_DIR", backtest_dir, raising=False)
    client = TestClient(app)

    resp = client.get("/api/backtest/runs/window1/nav")

    series = resp.json()["nav_series"]
    assert series[0]["simons"] == 101500000
    assert isinstance(series[0]["simons"], int)
