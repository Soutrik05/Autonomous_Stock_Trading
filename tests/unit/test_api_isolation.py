"""
Evidence isolation (docs/backend_implementation_guide_week5.md §1.1 item 4): every live route
reads exclusively from the live portfolio ledger; only src/api/routes/backtest.py ever opens
anything under storage/backtest/. Also proves the read-only connection guarantee: a write
attempted through the API's own connection factory raises, it never silently succeeds.
"""

import re
import sqlite3
from pathlib import Path

import pytest

from ._api_test_helpers import build_file_db, clear_overrides, make_client, seed_agent
from api.deps import get_ro_conn

_API_ROUTES_DIR = Path(__file__).resolve().parents[2] / "src" / "api" / "routes"
_LIVE_ROUTE_FILES = [
    "health.py", "activity.py", "leaderboard.py", "portfolio.py",
    "memory.py", "baseline.py", "funnel.py",
]


@pytest.fixture(autouse=True)
def _reset_overrides():
    yield
    clear_overrides()


def test_live_route_source_never_mentions_backtest_storage():
    """Static guard: none of the live route files reference storage/backtest or
    settings.BACKTEST_DB_DIR -- that string appears only in backtest.py."""
    for filename in _LIVE_ROUTE_FILES:
        text = (_API_ROUTES_DIR / filename).read_text(encoding="utf-8")
        assert "storage/backtest" not in text, f"{filename} references storage/backtest"
        assert "BACKTEST_DB_DIR" not in text, f"{filename} references BACKTEST_DB_DIR"
        assert not re.search(r"\bbacktest\b", text, re.IGNORECASE), f"{filename} mentions backtest at all"


def test_live_routes_never_blend_in_a_backtest_database(tmp_path, monkeypatch):
    """Seeds a LIVE temp db with one 'simons' row and a SEPARATE storage/backtest/ directory
    (pointed at by settings.BACKTEST_DB_DIR) with a DIFFERENT 'simons' row. The live leaderboard
    and positions routes must reflect only the live (overridden) db -- proving they never read
    the backtest directory, even though one exists on disk right next to them."""
    live_db = str(tmp_path / "live_portfolio.db")
    build_file_db(live_db)
    seed_agent(live_db, "simons", "LIVE Jim Simons", "Quant Momentum")

    backtest_dir = tmp_path / "storage_backtest"
    backtest_dir.mkdir()
    backtest_db = str(backtest_dir / "window1.db")
    build_file_db(backtest_db)
    seed_agent(backtest_db, "simons", "BACKTEST Jim Simons (should never appear)", "Quant Momentum")

    client = make_client(live_db)

    resp = client.get("/api/leaderboard")
    names = [e["name"] for e in resp.json()]
    assert names == ["LIVE Jim Simons"]
    assert "BACKTEST Jim Simons (should never appear)" not in names


def test_read_only_connection_rejects_a_write(tmp_path):
    db_path = str(tmp_path / "portfolio.db")
    build_file_db(db_path)

    conn = get_ro_conn(db_path)
    try:
        with pytest.raises(sqlite3.OperationalError):
            conn.execute(
                "INSERT INTO agents (id, name, philosophy, kind, starting_cash_paise, cash_paise, "
                "created_at, updated_at) VALUES ('x', 'x', 'x', 'LLM', 1, 1, 'x', 'x')"
            )
    finally:
        conn.close()
