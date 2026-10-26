"""
Integration tests covering the full trading day order and position lifecycle:
placement -> monitor poll fill -> crash cancel -> stop loss -> target notification -> expiry -> settlement.
See Plan_v3 §4.3, §4.4.
"""
from datetime import datetime

from broker.check import check_invariants
from broker.engine import Broker
from broker.expiry import expire_pending_orders
from broker.monitor import poll_once
from broker.quotes import ReplayQuoteProvider
from broker.settlement import run_settlement
from core.clock import FakeClock
from core.money import rupees_to_paise

RUN_DATE = "2026-10-19"
NEXT_TRADING_DAY = "2026-10-20"


def _insert_decision(
    conn,
    agent_id="simons",
    ticker="TATAMOTORS",
    action="BUY",
    shares=10,
    entry_low_rs=995.0,
    entry_high_rs=1005.0,
    stop_rs=960.0,
    target_rs=1080.0,
    run_date=RUN_DATE,
):
    now = f"{run_date}T22:00:00+05:30"
    cur = conn.execute(
        """
        INSERT INTO decisions
            (run_date, agent_id, ticker, source, action, shares, entry_low_paise,
             entry_high_paise, stop_paise, target_paise, reasoning, created_at)
        VALUES (?, ?, ?, 'LLM', ?, ?, ?, ?, ?, ?, 'Order lifecycle test', ?)
        """,
        (
            run_date,
            agent_id,
            ticker,
            action,
            shares,
            rupees_to_paise(entry_low_rs) if entry_low_rs else None,
            rupees_to_paise(entry_high_rs) if entry_high_rs else None,
            rupees_to_paise(stop_rs) if stop_rs else None,
            rupees_to_paise(target_rs) if target_rs else None,
            now,
        ),
    )
    return cur.lastrowid


def test_order_placement_and_buy_fill(seeded_portfolio):
    conn = seeded_portfolio
    clock_night = FakeClock(datetime(2026, 10, 19, 22, 0, 0))

    # 1. 22:00 IST Night before: Place BUY decision & generate pending order
    _insert_decision(conn, "simons", "TATAMOTORS", "BUY", shares=10, entry_low_rs=995.0, entry_high_rs=1005.0)
    broker = Broker(conn, clock_night)
    summary = broker.place_orders_for_run("simons", RUN_DATE)
    assert summary["orders_created"] == 1

    order = conn.execute("SELECT * FROM pending_orders WHERE ticker = 'TATAMOTORS'").fetchone()
    assert order["status"] == "pending"
    assert order["valid_for_date"] == NEXT_TRADING_DAY
    assert order["reserved_amount_paise"] == broker.worst_case_buy_outlay_paise(10, rupees_to_paise(1005.0))

    # 2. 09:30 IST Next trading morning: Monitor poll finds quote within [entry_low, entry_high]
    clock_morning = FakeClock(datetime(2026, 10, 20, 9, 30, 0))
    quotes = ReplayQuoteProvider({"TATAMOTORS": rupees_to_paise(1000.0)})
    poll_summary = poll_once(conn, clock_morning, quotes, run_date_str=NEXT_TRADING_DAY)

    assert poll_summary["buys_filled"] == 1
    assert poll_summary["crashes_cancelled"] == 0

    # 3. Verify order is filled and position is opened
    order_after = conn.execute("SELECT * FROM pending_orders WHERE id = ?", (order["id"],)).fetchone()
    assert order_after["status"] == "filled"

    position = conn.execute(
        "SELECT * FROM positions WHERE agent_id = 'simons' AND ticker = 'TATAMOTORS' AND status = 'OPEN'"
    ).fetchone()
    assert position is not None
    assert position["shares"] == 10
    assert position["status"] == "OPEN"

    # Reserved cash is freed upon fill
    assert broker.reserved_cash_paise("simons") == 0
    assert check_invariants(conn) == []


def test_crash_cancellation_when_price_gaps_below_stop(seeded_portfolio):
    conn = seeded_portfolio
    clock_night = FakeClock(datetime(2026, 10, 19, 22, 0, 0))

    # Pending BUY with entry [995, 1005], stop at 960
    _insert_decision(
        conn, "simons", "TATAMOTORS", "BUY", shares=10,
        entry_low_rs=995.0, entry_high_rs=1005.0, stop_rs=960.0
    )
    broker = Broker(conn, clock_night)
    broker.place_orders_for_run("simons", RUN_DATE)

    # Market opens next morning gapped down to 950 (below stop_paise 96000)
    clock_morning = FakeClock(datetime(2026, 10, 20, 9, 30, 0))
    quotes = ReplayQuoteProvider({"TATAMOTORS": rupees_to_paise(950.0)})
    poll_summary = poll_once(conn, clock_morning, quotes, run_date_str=NEXT_TRADING_DAY)

    assert poll_summary["crashes_cancelled"] == 1
    assert poll_summary["buys_filled"] == 0

    order = conn.execute("SELECT * FROM pending_orders WHERE ticker = 'TATAMOTORS'").fetchone()
    assert order["status"] == "cancelled"
    assert order["rejection_reason"] == "CRASH_CANCELLED"
    assert broker.reserved_cash_paise("simons") == 0
    assert check_invariants(conn) == []


def test_position_stop_loss_trigger(seeded_portfolio):
    conn = seeded_portfolio
    clock = FakeClock(datetime(2026, 10, 20, 11, 0, 0))
    broker = Broker(conn, clock)

    # Directly seed an open position
    conn.execute(
        """
        INSERT INTO positions
            (agent_id, ticker, sector, shares, avg_entry_price_paise, stop_paise,
             target_paise, last_price_paise, status, entry_date)
        VALUES ('simons', 'TATAMOTORS', 'Automobiles', 10, 100000, 96000, 108000, 100000, 'OPEN', '2026-10-19')
        """
    )

    # Price drops to 955 (<= stop 960)
    quotes = ReplayQuoteProvider({"TATAMOTORS": rupees_to_paise(955.0)})
    poll_summary = poll_once(conn, clock, quotes, run_date_str=NEXT_TRADING_DAY)

    assert poll_summary["stops_hit"] == 1
    closed_pos = conn.execute("SELECT * FROM positions WHERE ticker = 'TATAMOTORS'").fetchone()
    assert closed_pos["status"] == "CLOSED"
    assert closed_pos["exit_reason"] == "STOP_HIT"
    assert check_invariants(conn) == []


def test_position_target_reached_notification(seeded_portfolio):
    conn = seeded_portfolio
    clock = FakeClock(datetime(2026, 10, 20, 13, 0, 0))

    # Directly seed an open position
    conn.execute(
        """
        INSERT INTO positions
            (agent_id, ticker, sector, shares, avg_entry_price_paise, stop_paise,
             target_paise, last_price_paise, status, entry_date)
        VALUES ('simons', 'TATAMOTORS', 'Automobiles', 10, 100000, 96000, 108000, 100000, 'OPEN', '2026-10-19')
        """
    )

    # Price rises to 1090 (>= target 1080)
    quotes = ReplayQuoteProvider({"TATAMOTORS": rupees_to_paise(1090.0)})
    poll_summary = poll_once(conn, clock, quotes, run_date_str=NEXT_TRADING_DAY)

    assert poll_summary["targets_reached"] == 1
    # Target reached is a soft notification; position remains OPEN
    pos = conn.execute("SELECT * FROM positions WHERE ticker = 'TATAMOTORS'").fetchone()
    assert pos["status"] == "OPEN"

    log_entry = conn.execute(
        "SELECT * FROM activity_log WHERE event_type = 'TARGET_REACHED' AND ticker = 'TATAMOTORS'"
    ).fetchone()
    assert log_entry is not None
    assert check_invariants(conn) == []


def test_order_expiry_at_day_end(seeded_portfolio):
    conn = seeded_portfolio
    clock_night = FakeClock(datetime(2026, 10, 19, 22, 0, 0))

    # Place order that remains pending all day
    _insert_decision(conn, "simons", "TATAMOTORS", "BUY", shares=10, entry_low_rs=995.0, entry_high_rs=1005.0)
    broker = Broker(conn, clock_night)
    broker.place_orders_for_run("simons", RUN_DATE)

    # 15:30 IST: Expiry job runs
    clock_1530 = FakeClock(datetime(2026, 10, 20, 15, 30, 0))
    expiry_res = expire_pending_orders(conn, clock_1530, run_date_str=NEXT_TRADING_DAY)

    assert expiry_res["status"] == "SUCCESS"
    assert expiry_res["expired_count"] == 1

    order = conn.execute("SELECT * FROM pending_orders WHERE ticker = 'TATAMOTORS'").fetchone()
    assert order["status"] == "cancelled"
    assert order["rejection_reason"] == "EXPIRED"
    assert broker.reserved_cash_paise("simons") == 0

    pipe_run = conn.execute(
        "SELECT status FROM pipeline_runs WHERE job = 'expiry' AND run_date = ?", (NEXT_TRADING_DAY,)
    ).fetchone()
    assert pipe_run is not None
    assert pipe_run["status"] == "SUCCESS"
    assert check_invariants(conn) == []


def test_settlement_and_daily_nav(seeded_portfolio):
    conn = seeded_portfolio
    clock_1535 = FakeClock(datetime(2026, 10, 20, 15, 35, 0))

    # Simons holds an open position
    conn.execute(
        """
        INSERT INTO positions
            (agent_id, ticker, sector, shares, avg_entry_price_paise, stop_paise,
             target_paise, last_price_paise, status, entry_date)
        VALUES ('simons', 'TATAMOTORS', 'Automobiles', 10, 100000, 96000, 108000, 100000, 'OPEN', '2026-10-19')
        """
    )

    quotes = ReplayQuoteProvider({
        "TATAMOTORS": rupees_to_paise(1050.0),
        "NIFTY_500": rupees_to_paise(22500.0),
    })

    settle_res = run_settlement(conn, clock_1535, quote_provider=quotes, run_date_str=NEXT_TRADING_DAY)
    assert settle_res["status"] == "SUCCESS"
    assert settle_res["agents_settled"] >= 2

    # Verify daily_nav entry for simons
    nav_simons = conn.execute(
        "SELECT * FROM daily_nav WHERE agent_id = 'simons' AND nav_date = ?", (NEXT_TRADING_DAY,)
    ).fetchone()
    assert nav_simons is not None
    assert nav_simons["invested_paise"] == 10 * rupees_to_paise(1050.0)
    assert nav_simons["total_paise"] == nav_simons["cash_paise"] + nav_simons["invested_paise"]
    assert nav_simons["nifty500_close"] == 22500.0

    # Verify pipeline_runs recorded
    pipe_run = conn.execute(
        "SELECT status FROM pipeline_runs WHERE job = 'settlement' AND run_date = ?", (NEXT_TRADING_DAY,)
    ).fetchone()
    assert pipe_run is not None
    assert pipe_run["status"] == "SUCCESS"
    assert check_invariants(conn) == []
