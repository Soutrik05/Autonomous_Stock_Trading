"""
Unit tests for broker/quotes.py, broker/monitor.py, broker/expiry.py and broker/settlement.py.
See Plan_v3 §4.3, §4.4.
"""

import sqlite3
from datetime import datetime

from broker.engine import Broker
from broker.expiry import expire_pending_orders
from broker.monitor import poll_once
from broker.quotes import ReplayQuoteProvider
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

    pos = conn.execute(
        "SELECT status, exit_reason, exit_price_paise FROM positions WHERE ticker = 'TATAMOTORS'"
    ).fetchone()
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

    empty_fconn = sqlite3.connect(chr(58) + 'memory' + chr(58))
    res = run_settlement(conn, clock, quote_provider=quotes, run_date_str=TRADE_DATE, fundamental_conn=empty_fconn)
    assert res["status"] == "SUCCESS"
    assert res["agents_settled"] >= 1
    assert res["nifty500_close"] == 22500.50

    nav_row = conn.execute(
        "SELECT * FROM daily_nav WHERE agent_id = 'simons' AND nav_date = ?", (TRADE_DATE,)
    ).fetchone()
    assert nav_row is not None
    assert nav_row["cash_paise"] == 10000000
    # Invested paise = 10 * 96000 = 960,000 paise
    assert nav_row["invested_paise"] == 960000
    # Total = 10,000,000 + 960,000 = 10,960,000 paise
    assert nav_row["total_paise"] == 10960000
    assert nav_row["nifty500_close"] == 22500.50


def test_monitor_fills_buy_with_price_improvement_below_entry_low():
    """Verify that BUY orders fill with price improvement when price opens below entry_low (but above stop)."""
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

    # Market price 920.00 is below entry_low (940.00) but above stop (900.00) -> should fill with price improvement
    quotes = ReplayQuoteProvider({"TATAMOTORS": 92000})
    res = poll_once(conn, clock, quotes, run_date_str=TRADE_DATE)

    assert res["status"] == "SUCCESS"
    assert res["buys_filled"] == 1

    order = conn.execute("SELECT status FROM pending_orders WHERE id = ?", (order_id,)).fetchone()
    assert order["status"] == "filled"

    fill = conn.execute("SELECT price_paise FROM fills WHERE order_id = ?", (order_id,)).fetchone()
    assert fill is not None
    # 92000 + 3bps slippage = 92028
    assert fill["price_paise"] == 92028

    pos = conn.execute("SELECT * FROM positions WHERE ticker = 'TATAMOTORS' AND status = 'OPEN'").fetchone()
    assert pos is not None
    assert pos["shares"] == 10


def test_monitor_long_horizon_stop_loss_behavior():
    """Verify long-horizon personas ignore minor midday wicks, but trigger at close or on severe crashes."""
    conn = make_portfolio_db()
    seed_db(conn)
    conn.execute(
        "INSERT OR IGNORE INTO agents (id, name, philosophy, kind, starting_cash_paise, cash_paise, created_at, updated_at) "
        "VALUES ('jhunjhunwala', 'Rakesh Jhunjhunwala', 'Value Growth', 'LLM', 10000000, 10000000, ?, ?)",
        (NOW, NOW),
    )

    # 1. Midday non-severe drop: stop=900.00, price=895.00 (> 900*0.90 = 810.00). Position should stay OPEN.
    clock_midday = FakeClock(datetime(2026, 10, 19, 11, 0, 0))
    conn.execute(
        "INSERT INTO positions (agent_id, ticker, sector, shares, avg_entry_price_paise, stop_paise, target_paise, last_price_paise, status, entry_date) "
        "VALUES ('jhunjhunwala', 'TATAMOTORS', 'Automobile', 10, 95000, 90000, 110000, 95000, 'OPEN', '2026-10-16')"
    )

    quotes_minor_drop = ReplayQuoteProvider({"TATAMOTORS": 89500})
    res1 = poll_once(conn, clock_midday, quotes_minor_drop, run_date_str=TRADE_DATE)
    assert res1["stops_hit"] == 0
    pos1 = conn.execute(
        "SELECT status FROM positions WHERE agent_id = 'jhunjhunwala' AND ticker = 'TATAMOTORS'"
    ).fetchone()
    assert pos1["status"] == "OPEN"

    # 2. Midday severe drop: price=800.00 (<= 810.00). Position should STOP_HIT immediately.
    quotes_severe_drop = ReplayQuoteProvider({"TATAMOTORS": 80000})
    res2 = poll_once(conn, clock_midday, quotes_severe_drop, run_date_str=TRADE_DATE)
    assert res2["stops_hit"] == 1
    pos2 = conn.execute(
        "SELECT status, exit_reason FROM positions WHERE agent_id = 'jhunjhunwala' AND ticker = 'TATAMOTORS'"
    ).fetchone()
    assert pos2["status"] == "CLOSED"
    assert pos2["exit_reason"] == "STOP_HIT"

    # 3. Closing window drop: price=895.00 at 15:20. Position should STOP_HIT.
    conn.execute(
        "UPDATE positions SET status = 'OPEN', exit_date = NULL, exit_price_paise = NULL, exit_reason = NULL WHERE agent_id = 'jhunjhunwala' AND ticker = 'TATAMOTORS'"
    )
    clock_close = FakeClock(datetime(2026, 10, 19, 15, 20, 0))
    res3 = poll_once(conn, clock_close, quotes_minor_drop, run_date_str=TRADE_DATE)
    assert res3["stops_hit"] == 1
    pos3 = conn.execute(
        "SELECT status, exit_reason FROM positions WHERE agent_id = 'jhunjhunwala' AND ticker = 'TATAMOTORS'"
    ).fetchone()
    assert pos3["status"] == "CLOSED"
    assert pos3["exit_reason"] == "STOP_HIT"



def make_fundamental_db_with_actions():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE corporate_actions (
            ticker         TEXT NOT NULL,
            isin           TEXT NOT NULL,
            action_type    TEXT NOT NULL,
            expiry_date    TEXT,
            amount         REAL,
            ratio          TEXT,
            raw_details    TEXT,
            updated_at     TEXT NOT NULL,
            PRIMARY KEY (ticker, action_type, expiry_date)
        )
        """
    )
    return conn


def test_settlement_credits_dividend_to_held_positions():
    portfolio_conn = make_portfolio_db()
    seed_db(portfolio_conn)
    fundamental_conn = make_fundamental_db_with_actions()
    clock = FakeClock(datetime(2026, 10, 19, 15, 35, 0))

    # Add dividend for TATAMOTORS on 2026-10-19: Rs 8.50 per share
    fundamental_conn.execute(
        "INSERT INTO corporate_actions (ticker, isin, action_type, expiry_date, amount, updated_at) "
        "VALUES ('TATAMOTORS', 'INE155A01022', 'Dividend', '2026-10-19', 8.5, '2026-10-19T00:00:00')"
    )

    # 1. Open position entered before ex-date (2026-10-16): 100 shares -> Should receive Rs 850 (85,000 paise)
    portfolio_conn.execute(
        "INSERT INTO positions (agent_id, ticker, sector, shares, avg_entry_price_paise, stop_paise, target_paise, last_price_paise, status, entry_date) "
        "VALUES ('simons', 'TATAMOTORS', 'Automobile', 100, 95000, 90000, 105000, 95000, 'OPEN', '2026-10-16')"
    )

    initial_cash = 10000000  # 10,000,000 paise
    quotes = ReplayQuoteProvider({"TATAMOTORS": 94000, "NIFTY_500": rupees_to_paise(22500.0)})

    res = run_settlement(
        portfolio_conn,
        clock,
        quote_provider=quotes,
        run_date_str="2026-10-19",
        fundamental_conn=fundamental_conn,
    )

    assert res["status"] == "SUCCESS"
    assert res["dividends_credited"] == 1
    assert res["dividend_payout_paise"] == 85000  # 100 * 8.5 * 100

    # Agent cash should be initial + 85,000
    agent = portfolio_conn.execute("SELECT cash_paise FROM agents WHERE id = 'simons'").fetchone()
    assert agent["cash_paise"] == initial_cash + 85000

    # dividend_payouts table audit record
    payout = portfolio_conn.execute("SELECT * FROM dividend_payouts WHERE agent_id = 'simons'").fetchone()
    assert payout is not None
    assert payout["ticker"] == "TATAMOTORS"
    assert payout["amount_per_share"] == 8.5
    assert payout["shares"] == 100
    assert payout["payout_paise"] == 85000
    assert payout["ex_date"] == "2026-10-19"

    # activity_log record
    log_row = portfolio_conn.execute(
        "SELECT * FROM activity_log WHERE event_type = 'DIVIDEND_CREDITED'"
    ).fetchone()
    assert log_row is not None
    assert "850.00" in log_row["description"]
    assert log_row["ticker"] == "TATAMOTORS"

    # Daily NAV total should include the credited dividend cash
    nav = portfolio_conn.execute("SELECT * FROM daily_nav WHERE agent_id = 'simons'").fetchone()
    # invested: 100 * 94000 = 9,400,000; cash: 10,085,000; total: 19,485,000
    assert nav["cash_paise"] == 10085000
    assert nav["invested_paise"] == 9400000
    assert nav["total_paise"] == 19485000


def test_settlement_dividend_eligibility_and_idempotence():
    portfolio_conn = make_portfolio_db()
    seed_db(portfolio_conn)
    fundamental_conn = make_fundamental_db_with_actions()
    clock = FakeClock(datetime(2026, 10, 19, 15, 35, 0))

    # Dividend Rs 5.00 on 2026-10-19 for TATAMOTORS
    fundamental_conn.execute(
        "INSERT INTO corporate_actions (ticker, isin, action_type, expiry_date, amount, updated_at) "
        "VALUES ('TATAMOTORS', 'INE155A01022', 'Dividend', '2026-10-19', 5.0, '2026-10-19T00:00:00')"
    )

    # Position A: Bought on ex-date 2026-10-19 -> NOT eligible
    portfolio_conn.execute(
        "INSERT INTO positions (agent_id, ticker, sector, shares, avg_entry_price_paise, stop_paise, target_paise, last_price_paise, status, entry_date) "
        "VALUES ('simons', 'TATAMOTORS', 'Automobile', 50, 95000, 90000, 105000, 95000, 'OPEN', '2026-10-19')"
    )

    quotes = ReplayQuoteProvider({"TATAMOTORS": 95000})
    res1 = run_settlement(
        portfolio_conn, clock, quote_provider=quotes, run_date_str="2026-10-19", fundamental_conn=fundamental_conn
    )
    assert res1["dividends_credited"] == 0
    assert res1["dividend_payout_paise"] == 0

    # Position B: Bought on 2026-10-15, closed BEFORE ex-date on 2026-10-18 -> NOT eligible
    portfolio_conn.execute("DELETE FROM positions")
    portfolio_conn.execute(
        "INSERT INTO positions (agent_id, ticker, sector, shares, avg_entry_price_paise, stop_paise, target_paise, last_price_paise, status, entry_date, exit_date) "
        "VALUES ('simons', 'TATAMOTORS', 'Automobile', 50, 95000, 90000, 105000, 95000, 'CLOSED', '2026-10-15', '2026-10-18')"
    )
    res2 = run_settlement(
        portfolio_conn, clock, quote_provider=quotes, run_date_str="2026-10-19", fundamental_conn=fundamental_conn
    )
    assert res2["dividends_credited"] == 0

    # Position C: Bought on 2026-10-15, sold ON ex-date (2026-10-19) -> IS eligible (held cum-date overnight)
    portfolio_conn.execute("DELETE FROM positions")
    portfolio_conn.execute(
        "INSERT INTO positions (agent_id, ticker, sector, shares, avg_entry_price_paise, stop_paise, target_paise, last_price_paise, status, entry_date, exit_date) "
        "VALUES ('simons', 'TATAMOTORS', 'Automobile', 40, 95000, 90000, 105000, 95000, 'CLOSED', '2026-10-15', '2026-10-19')"
    )
    res3 = run_settlement(
        portfolio_conn, clock, quote_provider=quotes, run_date_str="2026-10-19", fundamental_conn=fundamental_conn
    )
    assert res3["dividends_credited"] == 1
    assert res3["dividend_payout_paise"] == 20000  # 40 * 5.0 * 100

    # Idempotence: re-running settlement on the same date does not credit again
    res4 = run_settlement(
        portfolio_conn, clock, quote_provider=quotes, run_date_str="2026-10-19", fundamental_conn=fundamental_conn
    )
    assert res4["dividends_credited"] == 0
    assert res4["dividend_payout_paise"] == 0



def test_settlement_dividend_upstox_date_format():
    portfolio_conn = make_portfolio_db()
    seed_db(portfolio_conn)
    fundamental_conn = make_fundamental_db_with_actions()
    clock = FakeClock(datetime(2026, 10, 19, 15, 35, 0))

    # Upstox returns expiry_date as '19 Oct 2026'
    fundamental_conn.execute(
        "INSERT INTO corporate_actions (ticker, isin, action_type, expiry_date, amount, updated_at) "
        "VALUES ('TATAMOTORS', 'INE155A01022', 'Dividend', '19 Oct 2026', 12.0, '2026-10-19T00:00:00')"
    )

    portfolio_conn.execute(
        "INSERT INTO positions (agent_id, ticker, sector, shares, avg_entry_price_paise, stop_paise, target_paise, last_price_paise, status, entry_date) "
        "VALUES ('simons', 'TATAMOTORS', 'Automobile', 50, 95000, 90000, 105000, 95000, 'OPEN', '2026-10-16')"
    )

    quotes = ReplayQuoteProvider({"TATAMOTORS": 95000})
    res = run_settlement(
        portfolio_conn, clock, quote_provider=quotes, run_date_str="2026-10-19", fundamental_conn=fundamental_conn
    )
    assert res["status"] == "SUCCESS"
    assert res["dividends_credited"] == 1
    assert res["dividend_payout_paise"] == 60000  # 50 * 12.0 * 100

    payout = portfolio_conn.execute("SELECT * FROM dividend_payouts WHERE agent_id = 'simons'").fetchone()
    assert payout["ex_date"] == "2026-10-19"  # normalized to ISO
