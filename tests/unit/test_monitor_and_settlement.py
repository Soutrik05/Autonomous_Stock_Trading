"""
Unit tests for broker/quotes.py, broker/monitor.py, broker/expiry.py and broker/settlement.py.
See Plan_v3 §4.3, §4.4.
"""
from datetime import datetime
import json
import sqlite3

from broker.engine import Broker
from broker.expiry import expire_pending_orders
from broker.monitor import poll_once
from broker.quotes import LiveQuoteProvider, ReplayQuoteProvider
from broker.settlement import run_settlement
from core.clock import FakeClock
from core.money import rupees_to_paise
from tests.conftest import make_portfolio_db

NOW = "2026-10-19T09:30:00+05:30"
TRADE_DATE = "2026-10-19"  # Monday


def seed_db(conn: sqlite3.Connection):
    conn.execute(
        "INSERT OR IGNORE INTO agents (id, name, philosophy, kind, starting_cash_paise, cash_paise, created_at, updated_at) "
        "VALUES ('simons', 'Jim Simons', 'Quant', 'LLM', 10000000, 10000000, ?, ?)",
        (NOW, NOW),
    )
    conn.execute(
        "INSERT OR IGNORE INTO symbols (ticker, instrument_key, isin, company_name, sector, is_active) "
        "VALUES ('TATAMOTORS', 'NSE_EQ|INE155A01022', 'INE155A01022', 'Tata Motors Ltd', 'Automobile', 1)"
    )
    conn.execute(
        "INSERT OR IGNORE INTO symbols (ticker, instrument_key, isin, company_name, sector, is_active) "
        "VALUES ('RELIANCE', 'NSE_EQ|INE002A01018', 'INE002A01018', 'Reliance Industries', 'Energy', 1)"
    )


def test_replay_quote_provider():
    provider = ReplayQuoteProvider({"TATAMOTORS": 95000})
    provider.set_quote("RELIANCE", 250000)

    quotes = provider.get_quotes(["TATAMOTORS", "RELIANCE", "UNKNOWN"])
    assert quotes["TATAMOTORS"] == 95000
    assert quotes["RELIANCE"] == 250000
    assert "UNKNOWN" not in quotes


def test_monitor_fills_buy_within_range():
    conn = make_portfolio_db()
    seed_db(conn)
    clock = FakeClock(datetime(2026, 10, 19, 10, 0, 0))

    # Insert a decision and a pending BUY order
    cur = conn.execute(
        "INSERT INTO decisions (run_date, agent_id, ticker, source, action, shares, entry_low_paise, entry_high_paise, stop_paise, target_paise, created_at) "
        "VALUES (?, 'simons', 'TATAMOTORS', 'LLM', 'BUY', 10, 94000, 96000, 90000, 102000, ?)",
        (TRADE_DATE, NOW),
    )
    decision_id = cur.lastrowid
    broker = Broker(conn, clock)
    outlay = broker.worst_case_buy_outlay_paise(10, 96000)
    cur = conn.execute(
        "INSERT INTO pending_orders (agent_id, ticker, side, shares, entry_low_paise, entry_high_paise, stop_paise, target_paise, reserved_amount_paise, decision_id, status, valid_for_date, created_at, updated_at) "
        "VALUES ('simons', 'TATAMOTORS', 'BUY', 10, 94000, 96000, 90000, 102000, ?, ?, 'pending', ?, ?, ?)",
        (outlay, decision_id, TRADE_DATE, NOW, NOW),
    )
    order_id = cur.lastrowid

    # Market price 950.00 is between 940.00 and 960.00 -> should fill
    quotes = ReplayQuoteProvider({"TATAMOTORS": 95000})
    res = poll_once(conn, clock, quotes, run_date_str=TRADE_DATE)

    assert res["status"] == "SUCCESS"
    assert res["buys_filled"] == 1

    order = conn.execute("SELECT status FROM pending_orders WHERE id = ?", (order_id,)).fetchone()
    assert order["status"] == "filled"

    pos = conn.execute("SELECT * FROM positions WHERE ticker = 'TATAMOTORS' AND status = 'OPEN'").fetchone()
    assert pos is not None
    assert pos["shares"] == 10


def test_monitor_crash_cancels_buy_when_price_below_stop():
    conn = make_portfolio_db()
    seed_db(conn)
    clock = FakeClock(datetime(2026, 10, 19, 10, 0, 0))

    cur = conn.execute(
        "INSERT INTO decisions (run_date, agent_id, ticker, source, action, shares, entry_low_paise, entry_high_paise, stop_paise, target_paise, created_at) "
        "VALUES (?, 'simons', 'TATAMOTORS', 'LLM', 'BUY', 10, 94000, 96000, 90000, 102000, ?)",
        (TRADE_DATE, NOW),
    )
    decision_id = cur.lastrowid
    broker = Broker(conn, clock)
    outlay = broker.worst_case_buy_outlay_paise(10, 96000)
    cur = conn.execute(
        "INSERT INTO pending_orders (agent_id, ticker, side, shares, entry_low_paise, entry_high_paise, stop_paise, target_paise, reserved_amount_paise, decision_id, status, valid_for_date, created_at, updated_at) "
        "VALUES ('simons', 'TATAMOTORS', 'BUY', 10, 94000, 96000, 90000, 102000, ?, ?, 'pending', ?, ?, ?)",
        (outlay, decision_id, TRADE_DATE, NOW, NOW),
    )
    order_id = cur.lastrowid

    # Market price 890.00 <= stop_paise (90000) -> crash cancelled
    quotes = ReplayQuoteProvider({"TATAMOTORS": 89000})
    res = poll_once(conn, clock, quotes, run_date_str=TRADE_DATE)

    assert res["status"] == "SUCCESS"
    assert res["crashes_cancelled"] == 1

    order = conn.execute("SELECT status, rejection_reason FROM pending_orders WHERE id = ?", (order_id,)).fetchone()
    assert order["status"] == "cancelled"
    assert order["rejection_reason"] == "CRASH_CANCELLED"


def test_monitor_triggers_stop_loss_on_open_position():
    conn = make_portfolio_db()
    seed_db(conn)
    clock = FakeClock(datetime(2026, 10, 19, 11, 0, 0))

    # Create an OPEN position with stop at 900.00
    conn.execute(
        "INSERT INTO positions (agent_id, ticker, sector, shares, avg_entry_price_paise, stop_paise, target_paise, last_price_paise, status, entry_date) "
        "VALUES ('simons', 'TATAMOTORS', 'Automobile', 10, 95000, 90000, 105000, 95000, 'OPEN', '2026-10-16')"
    )

    # Price drops to 895.00 <= stop (90000) -> should trigger stop loss
    quotes = ReplayQuoteProvider({"TATAMOTORS": 89500})
    res = poll_once(conn, clock, quotes, run_date_str=TRADE_DATE)

    assert res["status"] == "SUCCESS"
    assert res["stops_hit"] == 1

    pos = conn.execute("SELECT status, exit_reason, exit_price_paise FROM positions WHERE ticker = 'TATAMOTORS'").fetchone()
    assert pos["status"] == "CLOSED"
    assert pos["exit_reason"] == "STOP_HIT"


def test_monitor_logs_target_reached_once():
    conn = make_portfolio_db()
    seed_db(conn)
    clock = FakeClock(datetime(2026, 10, 19, 11, 0, 0))

    conn.execute(
        "INSERT INTO positions (agent_id, ticker, sector, shares, avg_entry_price_paise, stop_paise, target_paise, last_price_paise, status, entry_date) "
        "VALUES ('simons', 'TATAMOTORS', 'Automobile', 10, 95000, 90000, 100000, 95000, 'OPEN', '2026-10-16')"
    )

    # Price hits target 1010.00 >= 1000.00
    quotes = ReplayQuoteProvider({"TATAMOTORS": 101000})
    res1 = poll_once(conn, clock, quotes, run_date_str=TRADE_DATE)
    assert res1["targets_reached"] == 1

    # Position remains OPEN
    pos = conn.execute("SELECT status FROM positions WHERE ticker = 'TATAMOTORS'").fetchone()
    assert pos["status"] == "OPEN"

    # Second poll on same day does not duplicate target_reached log
    res2 = poll_once(conn, clock, quotes, run_date_str=TRADE_DATE)
    assert res2["targets_reached"] == 0


def test_expiry_cancels_remaining_pending_orders():
    conn = make_portfolio_db()
    seed_db(conn)
    clock = FakeClock(datetime(2026, 10, 19, 15, 30, 0))

    conn.execute(
        "INSERT INTO pending_orders (agent_id, ticker, side, shares, entry_low_paise, entry_high_paise, stop_paise, target_paise, reserved_amount_paise, status, valid_for_date, created_at, updated_at) "
        "VALUES ('simons', 'TATAMOTORS', 'BUY', 10, 94000, 96000, 90000, 102000, 1000000, 'pending', ?, ?, ?)",
        (TRADE_DATE, NOW, NOW),
    )

    res = expire_pending_orders(conn, clock, run_date_str=TRADE_DATE)
    assert res["status"] == "SUCCESS"
    assert res["expired_count"] == 1

    order = conn.execute("SELECT status, rejection_reason FROM pending_orders WHERE ticker = 'TATAMOTORS'").fetchone()
    assert order["status"] == "cancelled"
    assert order["rejection_reason"] == "EXPIRED"

    # Reserved cash is now 0
    broker = Broker(conn, clock)
    assert broker.reserved_cash_paise("simons") == 0


def test_settlement_computes_daily_nav_correctly():
    conn = make_portfolio_db()
    seed_db(conn)
    clock = FakeClock(datetime(2026, 10, 19, 15, 35, 0))

    # Agent cash: 10,000,000 paise (Rs 1,00,000). Add an open position: 10 shares of TATAMOTORS at 950.00
    conn.execute(
        "INSERT INTO positions (agent_id, ticker, sector, shares, avg_entry_price_paise, stop_paise, target_paise, last_price_paise, status, entry_date) "
        "VALUES ('simons', 'TATAMOTORS', 'Automobile', 10, 95000, 90000, 105000, 95000, 'OPEN', '2026-10-16')"
    )

    # Latest quote brings TATAMOTORS to 960.00 paise (96000), and Nifty 500 close is 22500.50
    quotes = ReplayQuoteProvider({"TATAMOTORS": 96000, "NIFTY_500": rupees_to_paise(22500.50)})

    res = run_settlement(conn, clock, quote_provider=quotes, run_date_str=TRADE_DATE)
    assert res["status"] == "SUCCESS"
    assert res["agents_settled"] >= 1
    assert res["nifty500_close"] == 22500.50

    nav_row = conn.execute("SELECT * FROM daily_nav WHERE agent_id = 'simons' AND nav_date = ?", (TRADE_DATE,)).fetchone()
    assert nav_row is not None
    assert nav_row["cash_paise"] == 10000000
    # Invested paise = 10 * 96000 = 960,000 paise
    assert nav_row["invested_paise"] == 960000
    # Total = 10,000,000 + 960,000 = 10,960,000 paise
    assert nav_row["total_paise"] == 10960000
    assert nav_row["nifty500_close"] == 22500.50
