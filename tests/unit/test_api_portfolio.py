"""
Tests for GET /api/agents/{id}/positions, /orders and /decisions.
See docs/backend_implementation_guide_week5.md §3.2-3.4.
"""

import json
import sqlite3

import pytest

from ._api_test_helpers import NOW, build_file_db, clear_overrides, make_client, seed_agent, seed_symbol


@pytest.fixture(autouse=True)
def _reset_overrides():
    yield
    clear_overrides()


def test_unknown_agent_returns_404(tmp_path):
    db_path = str(tmp_path / "portfolio.db")
    build_file_db(db_path)
    client = make_client(db_path)

    for path in ("positions", "orders", "decisions"):
        resp = client.get(f"/api/agents/nobody/{path}")
        assert resp.status_code == 404


def test_known_agent_zero_rows_returns_200_with_empty_list(tmp_path):
    db_path = str(tmp_path / "portfolio.db")
    build_file_db(db_path)
    seed_agent(db_path, "simons", "Jim Simons", "Quant Momentum")
    client = make_client(db_path)

    for path in ("positions", "orders", "decisions"):
        resp = client.get(f"/api/agents/simons/{path}")
        assert resp.status_code == 200
        assert resp.json() == []


def test_open_position_computes_unrealized_pnl_and_exposes_forensic_tag(tmp_path):
    db_path = str(tmp_path / "portfolio.db")
    build_file_db(db_path)
    seed_agent(db_path, "simons", "Jim Simons", "Quant Momentum")
    seed_symbol(db_path, "TATAMOTORS", "Tata Motors Ltd", "Automobiles")
    conn = sqlite3.connect(db_path, isolation_level=None)
    conn.execute(
        "INSERT INTO positions (agent_id, ticker, sector, shares, avg_entry_price_paise, stop_paise, "
        "target_paise, last_price_paise, status, entry_date, entry_reasoning) "
        "VALUES ('simons', 'TATAMOTORS', 'Automobiles', 10, 100000, 90000, 120000, 110000, 'OPEN', "
        "'2026-11-01', 'Momentum breakout above 20-day high.')"
    )
    conn.close()
    client = make_client(db_path)

    resp = client.get("/api/agents/simons/positions")

    assert resp.status_code == 200
    pos = resp.json()[0]
    assert pos["symbol"] == "TATAMOTORS"
    assert pos["company_name"] == "Tata Motors Ltd"
    assert pos["quantity"] == 10
    assert pos["unrealized_pnl_paise"] == 100000  # (110000-100000)*10
    assert pos["unrealized_pnl_pct"] == 10.0
    assert pos["realized_pnl_paise"] is None
    assert pos["is_frozen"] is False
    assert pos["thesis_summary"] == "Momentum breakout above 20-day high."


def test_closed_position_exposes_realized_pnl_and_forensic_tag(tmp_path):
    db_path = str(tmp_path / "portfolio.db")
    build_file_db(db_path)
    seed_agent(db_path, "simons", "Jim Simons", "Quant Momentum")
    conn = sqlite3.connect(db_path, isolation_level=None)
    conn.execute(
        "INSERT INTO positions (agent_id, ticker, sector, shares, avg_entry_price_paise, stop_paise, "
        "target_paise, last_price_paise, status, entry_date, exit_date, exit_price_paise, exit_reason, "
        "hold_days, realized_pnl_paise, realized_pnl_pct, forensics_type) "
        "VALUES ('simons', 'TATAMOTORS', 'Automobiles', 10, 100000, 90000, 120000, 115000, 'CLOSED', "
        "'2026-10-20', '2026-10-28', 115000, 'AGENT_SELL', 8, 150000, 15.0, 'TREND_CONTINUATION')"
    )
    conn.close()
    client = make_client(db_path)

    resp = client.get("/api/agents/simons/positions?status=CLOSED")

    pos = resp.json()[0]
    assert pos["status"] == "CLOSED"
    assert pos["realized_pnl_paise"] == 150000
    assert pos["realized_pnl_pct"] == 15.0
    assert pos["unrealized_pnl_paise"] == 0
    assert pos["forensic_tag"] == "TREND_CONTINUATION"
    assert pos["closed_at"] == "2026-10-28"


def test_frozen_position_is_flagged(tmp_path):
    db_path = str(tmp_path / "portfolio.db")
    build_file_db(db_path)
    seed_agent(db_path, "simons", "Jim Simons", "Quant Momentum")
    conn = sqlite3.connect(db_path, isolation_level=None)
    conn.execute(
        "INSERT INTO positions (agent_id, ticker, sector, shares, avg_entry_price_paise, stop_paise, "
        "target_paise, last_price_paise, status, entry_date, frozen_reason) "
        "VALUES ('simons', 'TATAMOTORS', 'Automobiles', 10, 100000, 90000, 120000, 100000, 'OPEN', "
        "'2026-11-01', 'CORP_ACTION')"
    )
    conn.close()
    client = make_client(db_path)

    pos = client.get("/api/agents/simons/positions").json()[0]
    assert pos["is_frozen"] is True


def test_orders_left_joins_fills_and_exposes_charges(tmp_path):
    db_path = str(tmp_path / "portfolio.db")
    build_file_db(db_path)
    seed_agent(db_path, "simons", "Jim Simons", "Quant Momentum")
    conn = sqlite3.connect(db_path, isolation_level=None)
    cur = conn.execute(
        "INSERT INTO pending_orders (agent_id, ticker, side, shares, entry_low_paise, entry_high_paise, "
        "status, valid_for_date, created_at, updated_at) "
        "VALUES ('simons', 'TATAMOTORS', 'BUY', 10, 100000, 102000, 'filled', '2026-11-01', ?, ?)",
        (NOW, NOW),
    )
    order_id = cur.lastrowid
    conn.execute(
        "INSERT INTO positions (agent_id, ticker, sector, shares, avg_entry_price_paise, stop_paise, "
        "target_paise, last_price_paise, status, entry_date) "
        "VALUES ('simons', 'TATAMOTORS', 'Automobiles', 10, 101000, 90000, 120000, 101000, 'OPEN', '2026-11-01')"
    )
    position_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.execute(
        "INSERT INTO fills (order_id, position_id, agent_id, ticker, side, shares, price_paise, "
        "charges_paise, executed_at) VALUES (?, ?, 'simons', 'TATAMOTORS', 'BUY', 10, 101000, 238, ?)",
        (order_id, position_id, NOW),
    )
    conn.close()
    client = make_client(db_path)

    resp = client.get("/api/agents/simons/orders")

    order = resp.json()[0]
    assert order["status"] == "FILLED"
    assert order["filled_price_paise"] == 101000
    assert order["statutory_charges_paise"] == 238
    assert order["entry_low_paise"] == 100000
    assert order["entry_high_paise"] == 102000


def test_rejected_order_exposes_rejection_reason_and_no_fill(tmp_path):
    db_path = str(tmp_path / "portfolio.db")
    build_file_db(db_path)
    seed_agent(db_path, "simons", "Jim Simons", "Quant Momentum")
    conn = sqlite3.connect(db_path, isolation_level=None)
    conn.execute(
        "INSERT INTO pending_orders (agent_id, ticker, side, shares, entry_low_paise, entry_high_paise, "
        "status, rejection_reason, valid_for_date, created_at, updated_at) "
        "VALUES ('simons', 'GESHIP', 'BUY', 20, 161000, 162500, 'rejected', 'INSUFFICIENT_CASH', "
        "'2026-11-01', ?, ?)",
        (NOW, NOW),
    )
    conn.close()
    client = make_client(db_path)

    order = client.get("/api/agents/simons/orders").json()[0]
    assert order["status"] == "REJECTED"
    assert order["rejection_reason"] == "INSUFFICIENT_CASH"
    assert order["filled_price_paise"] is None


def test_decisions_parse_cited_metrics_from_json(tmp_path):
    db_path = str(tmp_path / "portfolio.db")
    build_file_db(db_path)
    seed_agent(db_path, "simons", "Jim Simons", "Quant Momentum")
    conn = sqlite3.connect(db_path, isolation_level=None)
    conn.execute(
        "INSERT INTO decisions (run_date, agent_id, ticker, source, action, reasoning, "
        "faithfulness_score, sizing_fidelity_score, cited_metrics_json, created_at) "
        "VALUES ('2026-11-04', 'simons', 'TATAMOTORS', 'LLM', 'BUY', 'Momentum breakout.', "
        "1.0, 0.95, ?, ?)",
        (json.dumps({"rsi_14": 65.3, "adx_14": 32.4}), NOW),
    )
    conn.close()
    client = make_client(db_path)

    resp = client.get("/api/agents/simons/decisions")

    decision = resp.json()[0]
    assert decision["action"] == "BUY"
    assert decision["faithfulness_score"] == 1.0
    assert decision["sizing_fidelity_score"] == 0.95
    assert decision["candidate_rank"] is None
    assert decision["allocated_paise"] is None
    cited = {m["name"]: m["cited_value"] for m in decision["cited_metrics"]}
    assert cited == {"rsi_14": 65.3, "adx_14": 32.4}


def test_decisions_cited_metrics_is_null_when_column_is_really_empty(tmp_path):
    db_path = str(tmp_path / "portfolio.db")
    build_file_db(db_path)
    seed_agent(db_path, "simons", "Jim Simons", "Quant Momentum")
    conn = sqlite3.connect(db_path, isolation_level=None)
    # Three ways the column can be "really empty": NULL, '', and '{}' (a HOLD decision cites
    # nothing). None of these should produce an empty list -- they must all be null.
    conn.execute(
        "INSERT INTO decisions (run_date, agent_id, ticker, source, action, cited_metrics_json, created_at) "
        "VALUES ('2026-11-04', 'simons', 'A', 'LLM', 'HOLD', NULL, ?)", (NOW,),
    )
    conn.execute(
        "INSERT INTO decisions (run_date, agent_id, ticker, source, action, cited_metrics_json, created_at) "
        "VALUES ('2026-11-04', 'simons', 'B', 'LLM', 'HOLD', '{}', ?)", (NOW,),
    )
    conn.close()
    client = make_client(db_path)

    resp = client.get("/api/agents/simons/decisions")

    for decision in resp.json():
        assert decision["cited_metrics"] is None
