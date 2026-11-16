"""
Unit tests for broker/engine.py validation rules (price logic, cash, no short selling, ADJUST),
reservation, averaging, atomic fills, CAP_BREACH and order_valid_date -- against an in-memory
database and FakeClock.
See Plan_v3 §4.2, §4.3.
"""

from datetime import datetime

import pytest

from broker.engine import Broker
from broker.transaction_charges import apply_slippage
from core.clock import FakeClock
from core.config import settings
from tests.conftest import make_portfolio_db

NOW = "2026-10-16T22:00:00+05:30"
RUN_DATE = "2026-10-16"  # a Friday


def clock_at(run_date=RUN_DATE, hour=22, minute=0):
    y, m, d = (int(p) for p in run_date.split("-"))
    return FakeClock(datetime(y, m, d, hour, minute))


def insert_agent(conn, agent_id="simons", cash_paise=None):
    cash_paise = cash_paise if cash_paise is not None else settings.INITIAL_CASH_PER_AGENT_PAISE
    conn.execute(
        "INSERT INTO agents (id, name, philosophy, kind, starting_cash_paise, cash_paise, created_at, updated_at) "
        "VALUES (?, 'Test', 'Test', 'LLM', ?, ?, ?, ?)",
        (agent_id, cash_paise, cash_paise, NOW, NOW),
    )


def insert_symbol(conn, ticker, sector="TestSector"):
    conn.execute(
        "INSERT INTO symbols (ticker, instrument_key, isin, company_name, sector, is_active) "
        "VALUES (?, ?, 'ISIN0000000', 'Test Co', ?, 1)",
        (ticker, f"NSE_EQ|{ticker}", sector),
    )


def insert_decision(
    conn,
    agent_id,
    ticker,
    action,
    run_date=RUN_DATE,
    shares=None,
    entry_low=None,
    entry_high=None,
    stop=None,
    target=None,
    reasoning="test",
):
    cur = conn.execute(
        """
        INSERT INTO decisions
            (run_date, agent_id, ticker, source, action, shares, entry_low_paise, entry_high_paise,
             stop_paise, target_paise, reasoning, created_at)
        VALUES (?, ?, ?, 'LLM', ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (run_date, agent_id, ticker, action, shares, entry_low, entry_high, stop, target, reasoning, NOW),
    )
    return cur.lastrowid


def insert_watchlist(conn, agent_id, ticker, sector, intensity_score):
    conn.execute(
        "INSERT INTO agent_watchlist (agent_id, ticker, sector, added_on, ttl_days, expires_on, intensity_score) "
        "VALUES (?, ?, ?, ?, 3, '2026-10-30', ?)",
        (agent_id, ticker, sector, RUN_DATE, intensity_score),
    )


def insert_open_position(
    conn,
    agent_id,
    ticker,
    sector="TestSector",
    shares=10,
    avg_entry=100000,
    stop=90000,
    target=120000,
    last_price=100000,
    entry_date="2026-10-01",
    entry_decision_id=None,
):
    cur = conn.execute(
        """
        INSERT INTO positions
            (agent_id, ticker, sector, shares, avg_entry_price_paise, stop_paise, target_paise,
             last_price_paise, status, entry_date, entry_decision_id, entry_reasoning)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'OPEN', ?, ?, 'test entry')
        """,
        (agent_id, ticker, sector, shares, avg_entry, stop, target, last_price, entry_date, entry_decision_id),
    )
    return cur.lastrowid


# --- reservation --------------------------------------------------------------------------------------


def test_reservation_equals_sum_of_pending_buys():
    conn = make_portfolio_db()
    insert_agent(conn)
    insert_symbol(conn, "A")
    insert_symbol(conn, "B")
    insert_decision(conn, "simons", "A", "BUY", shares=10, entry_low=9400, entry_high=9500, stop=9100, target=10200)
    insert_decision(conn, "simons", "B", "BUY", shares=5, entry_low=19400, entry_high=19500, stop=19100, target=20200)
    broker = Broker(conn, clock_at())

    broker.place_orders_for_run("simons", RUN_DATE)

    independent_sum = conn.execute(
        "SELECT COALESCE(SUM(reserved_amount_paise),0) AS t FROM pending_orders WHERE agent_id='simons' AND status='pending'"
    ).fetchone()["t"]
    assert broker.reserved_cash_paise("simons") == independent_sum
    assert independent_sum > 0


def test_reservation_is_never_a_stored_counter():
    # agents table has no reserved_cash column at all -- reserved_cash_paise must be computed.
    conn = make_portfolio_db()
    cols = [r["name"] for r in conn.execute("PRAGMA table_info(agents)")]
    assert "reserved_cash_paise" not in cols
    assert "reserved_cash" not in cols


def test_reservation_drops_when_order_is_filled():
    conn = make_portfolio_db()
    insert_agent(conn)
    insert_symbol(conn, "A")
    insert_decision(conn, "simons", "A", "BUY", shares=10, entry_low=9400, entry_high=9500, stop=9100, target=10200)
    broker = Broker(conn, clock_at())
    broker.place_orders_for_run("simons", RUN_DATE)
    assert broker.reserved_cash_paise("simons") > 0

    order_id = conn.execute("SELECT id FROM pending_orders WHERE ticker='A'").fetchone()["id"]
    assert broker.fill_buy(order_id, 9450) is True
    assert broker.reserved_cash_paise("simons") == 0


def test_reservation_drops_when_order_is_cancelled_or_expired():
    conn = make_portfolio_db()
    insert_agent(conn)
    insert_symbol(conn, "A")
    insert_decision(conn, "simons", "A", "BUY", shares=10, entry_low=9400, entry_high=9500, stop=9100, target=10200)
    broker = Broker(conn, clock_at())
    broker.place_orders_for_run("simons", RUN_DATE)
    order_id = conn.execute("SELECT id FROM pending_orders WHERE ticker='A'").fetchone()["id"]

    assert broker.cancel_order(order_id, "EXPIRED") is True
    assert broker.reserved_cash_paise("simons") == 0


# --- cash rejection is deterministic -------------------------------------------------------------------


def test_cash_rejection_is_deterministic_by_intensity_not_decision_order():
    conn = make_portfolio_db()
    # Cash enough for exactly one ~Rs 95,000 order, not both.
    insert_agent(conn, cash_paise=10_000_000)
    insert_symbol(conn, "LOWINT", "SectorA")
    insert_symbol(conn, "HIGHINT", "SectorB")
    # Insert the LOW-intensity decision FIRST in the table, to prove insertion order doesn't matter.
    insert_decision(
        conn, "simons", "LOWINT", "BUY", shares=100, entry_low=94000, entry_high=95000, stop=91000, target=102000
    )
    insert_decision(
        conn, "simons", "HIGHINT", "BUY", shares=100, entry_low=94000, entry_high=95000, stop=91000, target=102000
    )
    insert_watchlist(conn, "simons", "LOWINT", "SectorA", 1.0)
    insert_watchlist(conn, "simons", "HIGHINT", "SectorB", 9.0)  # higher intensity

    broker = Broker(conn, clock_at())
    broker.place_orders_for_run("simons", RUN_DATE)

    high = conn.execute("SELECT status FROM pending_orders WHERE ticker='HIGHINT'").fetchone()
    low = conn.execute("SELECT status FROM pending_orders WHERE ticker='LOWINT'").fetchone()
    assert high["status"] == "pending"
    assert low["status"] == "rejected"


# --- price logic / no-short / ADJUST -------------------------------------------------------------------


def test_buy_price_logic_rejection():
    conn = make_portfolio_db()
    insert_agent(conn)
    insert_symbol(conn, "A")
    # stop > entry_low violates 0 < stop < entry_low <= entry_high < target
    insert_decision(conn, "simons", "A", "BUY", shares=10, entry_low=9000, entry_high=9500, stop=9200, target=10200)
    broker = Broker(conn, clock_at())
    broker.place_orders_for_run("simons", RUN_DATE)

    order = conn.execute("SELECT status, rejection_reason FROM pending_orders WHERE ticker='A'").fetchone()
    assert order["status"] == "rejected"
    assert order["rejection_reason"] == "INVALID_PRICES"


def test_sell_without_open_position_is_rejected_no_open_position():
    conn = make_portfolio_db()
    insert_agent(conn)
    insert_symbol(conn, "A")
    insert_decision(conn, "simons", "A", "SELL", reasoning="exit")
    broker = Broker(conn, clock_at())
    broker.place_orders_for_run("simons", RUN_DATE)

    order = conn.execute("SELECT status, rejection_reason FROM pending_orders WHERE ticker='A'").fetchone()
    assert order["status"] == "rejected"
    assert order["rejection_reason"] == "NO_OPEN_POSITION"


def test_adjust_rejects_a_lower_stop():
    conn = make_portfolio_db()
    insert_agent(conn)
    insert_symbol(conn, "A")
    insert_open_position(conn, "simons", "A", stop=90000, target=120000, last_price=100000)
    insert_decision(conn, "simons", "A", "ADJUST", stop=80000)  # lower than existing 90000
    broker = Broker(conn, clock_at())
    broker.place_orders_for_run("simons", RUN_DATE)

    position = conn.execute("SELECT stop_paise FROM positions WHERE ticker='A'").fetchone()
    assert position["stop_paise"] == 90000  # unchanged
    log = conn.execute("SELECT description FROM activity_log WHERE event_type='VALIDATION_FAILED'").fetchone()
    assert "stop may only rise" in log["description"]


def test_adjust_requires_stop_below_and_target_above_last_price():
    conn = make_portfolio_db()
    insert_agent(conn)
    insert_symbol(conn, "A")
    insert_open_position(conn, "simons", "A", stop=90000, target=120000, last_price=100000)
    # new stop (105000) is above last_price (100000) -> invalid
    insert_decision(conn, "simons", "A", "ADJUST", stop=105000, target=130000)
    broker = Broker(conn, clock_at())
    broker.place_orders_for_run("simons", RUN_DATE)

    position = conn.execute("SELECT stop_paise FROM positions WHERE ticker='A'").fetchone()
    assert position["stop_paise"] == 90000  # unchanged


def test_adjust_accepts_a_valid_change():
    conn = make_portfolio_db()
    insert_agent(conn)
    insert_symbol(conn, "A")
    insert_open_position(conn, "simons", "A", stop=90000, target=120000, last_price=100000)
    insert_decision(conn, "simons", "A", "ADJUST", stop=95000, target=125000)
    broker = Broker(conn, clock_at())
    broker.place_orders_for_run("simons", RUN_DATE)

    position = conn.execute("SELECT stop_paise, target_paise FROM positions WHERE ticker='A'").fetchone()
    assert position["stop_paise"] == 95000
    assert position["target_paise"] == 125000
    log = conn.execute("SELECT description FROM activity_log WHERE event_type='ADJUSTED'").fetchone()
    assert log is not None


# --- averaging -----------------------------------------------------------------------------------------


def test_averaging_two_buy_fills_gives_exact_weighted_average_and_one_open_row():
    conn = make_portfolio_db()
    insert_agent(conn, cash_paise=100_000_000)
    insert_symbol(conn, "A")

    d1 = insert_decision(
        conn, "simons", "A", "BUY", shares=10, entry_low=9900, entry_high=10000, stop=9500, target=11000
    )
    broker = Broker(conn, clock_at())
    broker.place_orders_for_run("simons", RUN_DATE)
    order1 = conn.execute("SELECT id FROM pending_orders WHERE decision_id=?", (d1,)).fetchone()["id"]
    assert broker.fill_buy(order1, 10000) is True  # fill price with slippage = 10010

    # Second BUY on the same ticker (averaging in) -- different decision, different run_date.
    d2 = insert_decision(
        conn,
        "simons",
        "A",
        "BUY",
        run_date="2026-10-19",
        shares=20,
        entry_low=10900,
        entry_high=11000,
        stop=10500,
        target=12000,
    )
    broker.place_orders_for_run("simons", "2026-10-19")
    order2 = conn.execute("SELECT id FROM pending_orders WHERE decision_id=?", (d2,)).fetchone()["id"]
    assert broker.fill_buy(order2, 11000) is True  # fill price with slippage = 11011

    positions = conn.execute("SELECT * FROM positions WHERE agent_id='simons' AND ticker='A'").fetchall()
    assert len(positions) == 1
    pos = positions[0]
    assert pos["status"] == "OPEN"
    assert pos["shares"] == 30

    fill1_price = apply_slippage(10000, "BUY")
    fill2_price = apply_slippage(11000, "BUY")
    expected_avg = round((10 * fill1_price + 20 * fill2_price) / 30)
    assert pos["avg_entry_price_paise"] == expected_avg
    assert pos["stop_paise"] == 10500  # latest order's values
    assert pos["target_paise"] == 12000


# --- atomic fill -----------------------------------------------------------------------------------------


def test_fill_buy_twice_on_the_same_order_fills_only_once():
    conn = make_portfolio_db()
    insert_agent(conn)
    insert_symbol(conn, "A")
    insert_decision(conn, "simons", "A", "BUY", shares=10, entry_low=9400, entry_high=9500, stop=9100, target=10200)
    broker = Broker(conn, clock_at())
    broker.place_orders_for_run("simons", RUN_DATE)
    order_id = conn.execute("SELECT id FROM pending_orders WHERE ticker='A'").fetchone()["id"]

    assert broker.fill_buy(order_id, 9450) is True
    cash_after_first = conn.execute("SELECT cash_paise FROM agents WHERE id='simons'").fetchone()["cash_paise"]

    assert broker.fill_buy(order_id, 9450) is False  # second call: no-op
    cash_after_second = conn.execute("SELECT cash_paise FROM agents WHERE id='simons'").fetchone()["cash_paise"]
    assert cash_after_second == cash_after_first

    fills = conn.execute("SELECT COUNT(*) AS n FROM fills WHERE order_id=?", (order_id,)).fetchone()["n"]
    assert fills == 1


# --- exact-paisa fill math -----------------------------------------------------------------------------------


def test_buy_fill_cash_math_exact_paisa():
    conn = make_portfolio_db()
    insert_agent(conn, cash_paise=20_000_000)
    insert_symbol(conn, "A")
    insert_decision(
        conn, "simons", "A", "BUY", shares=100, entry_low=99000, entry_high=100000, stop=95000, target=110000
    )
    broker = Broker(conn, clock_at())
    broker.place_orders_for_run("simons", RUN_DATE)
    order_id = conn.execute("SELECT id FROM pending_orders WHERE ticker='A'").fetchone()["id"]

    assert broker.fill_buy(order_id, 100000) is True  # Rs 1000 market price_paise

    from broker.transaction_charges import apply_slippage, compute_transaction_charges_paise

    fill_price = apply_slippage(100000, "BUY")
    charges = compute_transaction_charges_paise(fill_price, 100, "BUY")
    expected_cost = 100 * fill_price + charges

    cash = conn.execute("SELECT cash_paise FROM agents WHERE id='simons'").fetchone()["cash_paise"]
    assert cash == 20_000_000 - expected_cost

    fill = conn.execute("SELECT price_paise, charges_paise FROM fills WHERE order_id=?", (order_id,)).fetchone()
    assert fill["price_paise"] == fill_price
    assert fill["charges_paise"] == charges


def test_sell_fill_pnl_exact_paisa_including_buy_side_charges():
    conn = make_portfolio_db()
    insert_agent(conn, cash_paise=10_000_000)
    insert_symbol(conn, "A")

    from broker.transaction_charges import apply_slippage, compute_transaction_charges_paise

    buy_fill_price = apply_slippage(100000, "BUY")
    buy_charges = compute_transaction_charges_paise(buy_fill_price, 100, "BUY")
    position_id = insert_open_position(
        conn, "simons", "A", shares=100, avg_entry=buy_fill_price, stop=90000, target=120000, last_price=buy_fill_price
    )
    conn.execute(
        "INSERT INTO fills (order_id, position_id, agent_id, ticker, side, shares, price_paise, charges_paise, executed_at) "
        "VALUES (NULL, ?, 'simons', 'A', 'BUY', 100, ?, ?, ?)",
        (position_id, buy_fill_price, buy_charges, NOW),
    )

    decision_id = insert_decision(conn, "simons", "A", "SELL", reasoning="exit")
    broker = Broker(conn, clock_at())
    broker.place_orders_for_run("simons", RUN_DATE)
    order_id = conn.execute("SELECT id FROM pending_orders WHERE decision_id=?", (decision_id,)).fetchone()["id"]

    assert broker.fill_sell(order_id, 110000) is True

    sell_fill_price = apply_slippage(110000, "SELL")
    sell_charges = compute_transaction_charges_paise(sell_fill_price, 100, "SELL")
    proceeds = 100 * sell_fill_price - sell_charges
    cost_basis = buy_fill_price * 100 + buy_charges
    expected_pnl = proceeds - cost_basis

    position = conn.execute("SELECT * FROM positions WHERE id=?", (position_id,)).fetchone()
    assert position["status"] == "CLOSED"
    assert position["realized_pnl_paise"] == expected_pnl
    assert position["realized_pnl_pct"] == pytest.approx(expected_pnl / cost_basis * 100)

    cash = conn.execute("SELECT cash_paise FROM agents WHERE id='simons'").fetchone()["cash_paise"]
    assert cash == 10_000_000 + proceeds


# --- idempotent place_orders_for_run -----------------------------------------------------------------------------


def test_second_place_orders_for_run_call_creates_no_new_rows():
    conn = make_portfolio_db()
    insert_agent(conn)
    insert_symbol(conn, "A")
    insert_decision(conn, "simons", "A", "BUY", shares=10, entry_low=9400, entry_high=9500, stop=9100, target=10200)
    broker = Broker(conn, clock_at())
    broker.place_orders_for_run("simons", RUN_DATE)
    count_after_first = conn.execute("SELECT COUNT(*) AS n FROM pending_orders").fetchone()["n"]

    broker.place_orders_for_run("simons", RUN_DATE)
    count_after_second = conn.execute("SELECT COUNT(*) AS n FROM pending_orders").fetchone()["n"]
    assert count_after_second == count_after_first == 1


# --- CAP_BREACH is logged but never blocks --------------------------------------------------------------------------


def test_cap_breach_logged_but_order_still_accepted():
    conn = make_portfolio_db()
    # Small account so a single big order breaches risk/position/sector caps easily.
    insert_agent(conn, cash_paise=1_000_000)  # Rs 10,000
    insert_symbol(conn, "A", "SectorA")
    # position value ~ entry_high*shares = 9500*50 = 475000 paise = Rs4750, 47.5% of Rs10000 account
    insert_decision(conn, "simons", "A", "BUY", shares=50, entry_low=9400, entry_high=9500, stop=9000, target=11000)
    broker = Broker(conn, clock_at())
    broker.place_orders_for_run("simons", RUN_DATE)

    order = conn.execute("SELECT status FROM pending_orders WHERE ticker='A'").fetchone()
    assert order["status"] == "pending"  # accepted despite breaching caps

    breaches = conn.execute("SELECT * FROM activity_log WHERE event_type='CAP_BREACH'").fetchall()
    assert len(breaches) > 0
    caps_breached = {__import__("json").loads(b["metadata_json"])["cap"] for b in breaches}
    assert "POSITION_PCT" in caps_breached


def test_persona_specific_soft_caps_breach():
    conn = make_portfolio_db()
    # Rs 100,000 account
    insert_agent(conn, cash_paise=10_000_000)
    insert_symbol(conn, "A", "IT")
    insert_symbol(conn, "B", "IT")
    insert_symbol(conn, "C", "IT")

    # Simons has max_position_pct = 10.0% (global is 20.0%)
    # Submit 15% position: 150 shares @ Rs 100 (10,000 paise) = Rs 15,000 (15% of Rs 100,000 account)
    insert_decision(conn, "simons", "A", "BUY", shares=150, entry_low=9500, entry_high=10000, stop=9000, target=11000)
    broker = Broker(conn, clock_at())
    broker.place_orders_for_run("simons", RUN_DATE)

    breaches = conn.execute("SELECT * FROM activity_log WHERE event_type='CAP_BREACH' AND ticker='A'").fetchall()
    import json

    breach_map = {json.loads(b["metadata_json"])["cap"]: json.loads(b["metadata_json"]) for b in breaches}
    assert "POSITION_PCT" in breach_map
    assert breach_map["POSITION_PCT"]["limit"] == 10.0
    assert breach_map["POSITION_PCT"]["measured"] == 15.0

    # Sector cap test: Varsity has sector_cap = 2
    insert_agent(conn, agent_id="varsity", cash_paise=10_000_000)
    # Pre-populate 2 open positions in IT for varsity
    conn.execute(
        "INSERT INTO positions (agent_id, ticker, sector, shares, avg_entry_price_paise, stop_paise, target_paise, last_price_paise, status, entry_date) "
        "VALUES ('varsity', 'A', 'IT', 10, 10000, 9000, 12000, 10000, 'OPEN', '2026-10-15')"
    )
    conn.execute(
        "INSERT INTO positions (agent_id, ticker, sector, shares, avg_entry_price_paise, stop_paise, target_paise, last_price_paise, status, entry_date) "
        "VALUES ('varsity', 'B', 'IT', 10, 10000, 9000, 12000, 10000, 'OPEN', '2026-10-15')"
    )
    # Buy a 3rd IT stock (C)
    insert_decision(conn, "varsity", "C", "BUY", shares=10, entry_low=9500, entry_high=10000, stop=9000, target=11000)
    broker.place_orders_for_run("varsity", RUN_DATE)

    varsity_breaches = conn.execute(
        "SELECT * FROM activity_log WHERE event_type='CAP_BREACH' AND agent_id='varsity' AND ticker='C'"
    ).fetchall()
    v_map = {json.loads(b["metadata_json"])["cap"]: json.loads(b["metadata_json"]) for b in varsity_breaches}
    assert "SECTOR_CAP" in v_map
    assert v_map["SECTOR_CAP"]["limit"] == 2
    assert v_map["SECTOR_CAP"]["measured"] == 3


# --- order_valid_date -----------------------------------------------------------------------------------------------


def test_order_valid_date_next_trading_day_mode_skips_weekend():
    conn = make_portfolio_db()
    broker = Broker(conn, clock_at())  # ORDER_VALIDITY_MODE default: NEXT_TRADING_DAY
    from datetime import date

    friday = date(2026, 10, 16)
    assert broker.order_valid_date(friday) == date(2026, 10, 19)  # Monday, skips Sat/Sun


def test_order_valid_date_next_trading_day_mode_skips_a_holiday():
    conn = make_portfolio_db()
    conn.execute(
        "INSERT INTO market_calendar (trade_date, is_trading_day, session_type, note) "
        "VALUES ('2026-10-19', 0, 'CLOSED', 'Test holiday')"
    )
    broker = Broker(conn, clock_at())
    from datetime import date

    friday = date(2026, 10, 16)
    assert broker.order_valid_date(friday) == date(2026, 10, 20)  # Mon is a holiday -> Tuesday


def test_order_valid_date_same_day_if_before_open_mode():
    from datetime import date

    conn = make_portfolio_db()

    import core.config as settings_module

    original_mode = settings_module.settings.ORDER_VALIDITY_MODE
    object.__setattr__(settings_module.settings, "ORDER_VALIDITY_MODE", "SAME_DAY_IF_BEFORE_OPEN")
    try:
        friday = date(2026, 10, 16)
        before_open = Broker(conn, clock_at(hour=9, minute=0))
        assert before_open.order_valid_date(friday) == friday  # before 09:15, trading day -> same day

        after_open = Broker(conn, clock_at(hour=9, minute=30))
        assert after_open.order_valid_date(friday) == date(2026, 10, 19)  # after 09:15 -> next trading day

        saturday = date(2026, 10, 17)
        on_weekend = Broker(conn, clock_at(hour=9, minute=0))
        assert on_weekend.order_valid_date(saturday) == date(2026, 10, 19)  # run_date not a trading day
    finally:
        object.__setattr__(settings_module.settings, "ORDER_VALIDITY_MODE", original_mode)
