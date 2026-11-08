"""
Unit tests for the backtest and walk-forward module:
- Window configuration & rolling window generation
- LLM response caching
- Broker daily candle simulation (fills, stops, targets, settlement)
- Report generation with permanent BACKTEST_DERIVED labeling
"""

import sqlite3
import tempfile
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from backtest.broker_sim import simulate_market_session
from backtest.cache import LLMResponseCache
from backtest.config import (
    PERSONA_HOLDING_HORIZONS,
    get_all_trading_dates,
    get_rolling_windows,
)
from backtest.engine import SimulatedClock, inherit_prior_memory
from backtest.reports import format_markdown_report, generate_window_report

IST = ZoneInfo("Asia/Kolkata")


def test_persona_holding_horizons_defined():
    # Verify all 6 personas have defined horizons
    assert "simons" in PERSONA_HOLDING_HORIZONS
    assert "varsity" in PERSONA_HOLDING_HORIZONS
    assert "marks" in PERSONA_HOLDING_HORIZONS
    assert "lynch" in PERSONA_HOLDING_HORIZONS
    assert "jhunjhunwala" in PERSONA_HOLDING_HORIZONS
    assert "baseline-simons-rules" in PERSONA_HOLDING_HORIZONS
    assert "baseline-varsity-rules" in PERSONA_HOLDING_HORIZONS
    assert "baseline-lynch-rules" in PERSONA_HOLDING_HORIZONS

    # Check RJ maximum horizon is 180 days
    assert PERSONA_HOLDING_HORIZONS["jhunjhunwala"]["max_hold_days"] == 180


def test_rolling_windows_generation():
    # Setup mock ohlcv db with 450 simulated trade dates
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE ohlcv (trade_date TEXT, ticker TEXT, close REAL)")
    dates = [f"2025-{m:02d}-{d:02d}" for m in range(1, 13) for d in range(1, 29)]
    dates += [f"2026-{m:02d}-{d:02d}" for m in range(1, 11) for d in range(1, 29)]
    dates = sorted(list(set(dates)))[:450]

    for d in dates:
        for t in ["INFY", "TCS"]:
            conn.execute("INSERT INTO ohlcv VALUES (?, ?, 100.0)", (d, t))
    conn.commit()

    all_d = get_all_trading_dates(conn, min_tickers=2)
    assert len(all_d) == 450

    windows = get_rolling_windows(
        conn, min_warmup_sessions=200, window_len_sessions=180, step_sessions=30, min_tickers=2
    )
    # (450 - 200 - 180) / 30 = 70 / 30 = 2 increments -> 3 windows
    assert len(windows) >= 2
    assert windows[0].window_id == "rolling_w1"
    assert windows[0].sessions_count == 180
    assert windows[0].start_date == all_d[200]
    assert windows[0].end_date == all_d[200 + 180 - 1]


def test_llm_response_cache():
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "test_cache.db"
        cache = LLMResponseCache(db_path=db_path)

        agent_id = "simons"
        run_date = "2026-10-23"
        candidates = ["INFY", "TCS", "WIPRO"]
        model = "gemini-3.5-flash-lite"
        raw_resp = '{"decisions": [{"ticker": "INFY", "action": "BUY"}]}'
        decisions = [{"ticker": "INFY", "action": "BUY"}]

        # Check cache miss
        assert cache.get(agent_id, run_date, candidates, model) is None

        # Set cache
        key = cache.set(agent_id, run_date, candidates, model, raw_resp, decisions, "2026-10-23T22:00:00")
        assert len(key) == 64

        # Check cache hit
        hit = cache.get(agent_id, run_date, candidates, model)
        assert hit is not None
        assert hit["decisions"] == decisions
        assert hit["raw_response"] == raw_resp
        cache.close()


def test_broker_sim_daily_order_match_and_stops():
    # Setup in-memory portfolio and ohlcv
    port_conn = sqlite3.connect(":memory:")
    port_conn.row_factory = sqlite3.Row
    from scripts.init_db import init_db

    clock = SimulatedClock(datetime(2026, 10, 23, 10, 0, tzinfo=IST))
    init_db(port_conn, clock)

    # Insert test symbols
    port_conn.execute(
        "INSERT OR REPLACE INTO symbols (ticker, instrument_key, isin, company_name, sector) VALUES ('INFY', 'NSE_EQ|INE009A01021', 'INE009A01021', 'Infosys', 'IT')"
    )
    port_conn.execute(
        "INSERT OR REPLACE INTO symbols (ticker, instrument_key, isin, company_name, sector) VALUES ('TCS', 'NSE_EQ|INE467B01029', 'INE467B01029', 'TCS', 'IT')"
    )
    port_conn.commit()

    ohlcv_conn = sqlite3.connect(":memory:")
    ohlcv_conn.row_factory = sqlite3.Row
    ohlcv_conn.executescript("""
        CREATE TABLE ohlcv (
            trade_date TEXT, ticker TEXT, open REAL, high REAL, low REAL, close REAL, volume REAL
        );
        -- INFY candle trades between 1490 and 1520 (crosses entry band 1500-1510)
        INSERT INTO ohlcv VALUES ('2026-10-23', 'INFY', 1515.0, 1520.0, 1490.0, 1505.0, 1000000);
        -- TCS candle trades between 3550 and 3600 (well above entry band 3400-3450 -> does not fill)
        INSERT INTO ohlcv VALUES ('2026-10-23', 'TCS', 3580.0, 3600.0, 3550.0, 3570.0, 500000);
    """)

    now_iso = clock.now_iso()
    # Place pending buy order for INFY (entry 1500-1510) and TCS (entry 3400-3450)
    port_conn.execute(
        """
        INSERT INTO pending_orders (
            agent_id, ticker, side, shares, entry_low_paise, entry_high_paise,
            reserved_amount_paise, decision_id, stop_paise, target_paise, status, valid_for_date,
            created_at, updated_at
        ) VALUES (
            'simons', 'INFY', 'BUY', 10, 150000, 151000, 1515000, 1, 140000, 160000, 'pending', '2026-10-23',
            ?, ?
        )
        """,
        (now_iso, now_iso),
    )
    port_conn.execute(
        """
        INSERT INTO pending_orders (
            agent_id, ticker, side, shares, entry_low_paise, entry_high_paise,
            reserved_amount_paise, decision_id, stop_paise, target_paise, status, valid_for_date,
            created_at, updated_at
        ) VALUES (
            'simons', 'TCS', 'BUY', 5, 340000, 345000, 1730000, 2, 330000, 360000, 'pending', '2026-10-23',
            ?, ?
        )
        """,
        (now_iso, now_iso),
    )
    port_conn.commit()

    clock = SimulatedClock(datetime(2026, 10, 23, 10, 0, tzinfo=IST))
    res = simulate_market_session(port_conn, ohlcv_conn, clock, "2026-10-23", nifty500_close=24200.0)

    assert res["status"] == "SUCCESS"
    assert res["fills"] == 1  # INFY filled, TCS did not

    # Verify INFY is OPEN position
    infy_pos = port_conn.execute("SELECT * FROM positions WHERE ticker = 'INFY'").fetchone()
    assert infy_pos is not None
    assert infy_pos["status"] == "OPEN"
    assert infy_pos["shares"] == 10

    # Verify daily_nav recorded
    nav = port_conn.execute("SELECT * FROM daily_nav WHERE agent_id = 'simons'").fetchone()
    assert nav is not None
    assert nav["nav_date"] == "2026-10-23"
    assert nav["nifty500_close"] == 24200.0

    # Next session: INFY drops and hits stop loss at 1400 on Monday
    ohlcv_conn.executescript("""
        INSERT INTO ohlcv VALUES ('2026-10-26', 'INFY', 1450.0, 1460.0, 1380.0, 1390.0, 800000);
    """)
    clock.set_time(datetime(2026, 10, 26, 10, 0, tzinfo=IST))
    res2 = simulate_market_session(port_conn, ohlcv_conn, clock, "2026-10-26", nifty500_close=24100.0)

    assert res2["stops"] == 1
    closed_pos = port_conn.execute("SELECT * FROM positions WHERE ticker = 'INFY'").fetchone()
    assert closed_pos["status"] == "CLOSED"
    assert closed_pos["exit_reason"] == "STOP_HIT"
    assert closed_pos["realized_pnl_pct"] < 0.0


def test_report_formatting_permanent_label():
    mock_data = {
        "window": {
            "window_id": "test_w1",
            "name": "Test Window 1",
            "start_date": "2025-10-21",
            "end_date": "2026-07-15",
            "sessions_count": 180,
            "regime_label": "BULL_TREND",
            "description": "Bull recovery test",
        },
        "evidence_label": "BACKTEST_DERIVED",
        "is_backtest": True,
        "disclaimer": "EVIDENCE FOR QUESTION B ONLY (NOT LIVE PILOT RESULTS)",
        "performance": [
            {
                "agent_id": "simons",
                "total_return_pct": 12.5,
                "alpha_pct": 4.2,
                "sharpe_ratio": 1.45,
                "max_drawdown_pct": -6.2,
                "total_closed_trades": 15,
                "win_rate_pct": 60.0,
                "profit_factor": 1.8,
                "sample_notice": "PROVISIONAL (15/30 trades)",
            }
        ],
        "holding_stats": {
            "simons": {
                "total_trades": 15,
                "open_trades": 2,
                "min_hold_days": 2,
                "max_hold_days": 12,
                "avg_hold_days": 6.5,
            }
        },
        "comparison": {
            "deltas": {
                "excess_return_pct": 3.5,
                "excess_sharpe": 0.4,
                "excess_alpha_pct": 3.5,
                "excess_win_rate_pct": 10.0,
            },
            "llm_adds_value": True,
        },
    }

    md = format_markdown_report(mock_data)
    assert "BACKTEST_DERIVED" in md
    assert "EVIDENCE FOR QUESTION B ONLY" in md
    assert "simons" in md
    assert "180 trading sessions" in md


def test_structural_inapplicability_in_short_window():
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "test_sim.db"
        conn = sqlite3.connect(db_path)
        try:
            from core.clock import SystemClock
            from scripts.init_db import init_db

            init_db(conn, SystemClock())
            conn.commit()
        finally:
            conn.close()

        # Run report generation on 51-session supplementary window
        win_meta = {
            "window_id": "supplementary_range",
            "name": "Supplementary Window (Range-Bound Compression)",
            "start_date": "2025-11-24",
            "end_date": "2026-02-04",
            "regime_label": "RANGE_BOUND",
            "description": "Low volatility test",
            "sessions_count": 51,
        }
        rep = generate_window_report(db_path, win_meta)
        perf_map = {p["agent_id"]: p for p in rep["performance"]}

        # Simons and baseline (max_hold 14) are applicable
        assert perf_map["simons"]["is_applicable"] is True
        assert perf_map["baseline-simons-rules"]["is_applicable"] is True

        # Varsity (75), Lynch (90), Marks (120), RJ (180) are structurally inapplicable
        for aid in ["varsity", "lynch", "marks", "jhunjhunwala"]:
            assert perf_map[aid]["is_applicable"] is False
            assert "STRUCTURALLY_INAPPLICABLE" in perf_map[aid]["sample_notice"]

        md = format_markdown_report(rep)
        assert "Focal Test Scope (S1)" in md
        assert "STRUCTURALLY_INAPPLICABLE (51 sessions < 75d max_hold)" in md
        assert "STRUCTURALLY_INAPPLICABLE (51 sessions < 180d max_hold)" in md
        # Section 5 and Section 6 assembly assertions
        assert "## 5. Trade Forensics & Execution Diagnostics" in md
        assert "## 6. Persona Philosophy Adherence Audit (3-Dimensional Fidelity Engine)" in md
        assert "Selection Fid." in md
        assert "Horizon Fid." in md
        assert "Citation Fid." in md
        assert "Composite Adherence" in md


def test_window_report_section5_and_section6_with_populated_data():
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "populated_sim.db"
        conn = sqlite3.connect(db_path)
        try:
            from core.clock import SystemClock
            from scripts.init_db import init_db

            init_db(conn, SystemClock())

            # Seed NAV
            conn.execute("INSERT INTO daily_nav VALUES ('simons', '2026-10-01', 100000000, 0, 100000000, 24000.0)")
            conn.execute("INSERT INTO daily_nav VALUES ('simons', '2026-10-02', 100000000, 0, 102000000, 24100.0)")

            # Seed closed position with forensics telemetry in diagnosis_json
            import json

            diag = {
                "mae_pct": -3.2,
                "mfe_pct": 2.5,
                "profit_given_back_pct": 1.8,
                "post_exit": {"post_exit_ret_20d_pct": 14.5},
                "secondary_tags": ["EXITED_TOO_EARLY"],
            }
            conn.execute(
                """
                INSERT INTO positions (
                    agent_id, ticker, sector, shares, avg_entry_price_paise, exit_price_paise,
                    realized_pnl_paise, realized_pnl_pct, hold_days, exit_reason, forensics_type,
                    status, entry_date, exit_date, stop_paise, target_paise, last_price_paise, diagnosis_json
                ) VALUES (
                    'simons', 'INFY', 'IT', 10, 100000, 97000, -30000, -3.0, 4, 'STOP_HIT', 'FALSE_BREAKOUT',
                    'CLOSED', '2026-09-28', '2026-10-02', 95000, 110000, 97000, ?
                )
                """,
                (json.dumps(diag),),
            )

            # Seed snapshot and decision for simons
            conn.execute(
                """
                INSERT INTO feature_snapshots (id, as_of_date, ticker, schema_version, features_json, created_at)
                VALUES (1, '2026-10-01', 'INFY', 1, '{"volume_surge": 1.5, "adx_14": 26.0, "rsi_14": 60.0, "ema_20_above_50": 1, "macd_hist": 2.0, "kaufman_er_20": 0.45}', '2026-10-01T20:00:00+05:30')
                """
            )
            conn.execute(
                """
                INSERT INTO decisions (
                    id, run_date, agent_id, ticker, source, action, shares,
                    entry_high_paise, stop_paise, target_paise, cited_metrics_json, snapshot_id, created_at
                ) VALUES (
                    1, '2026-10-01', 'simons', 'INFY', 'LLM', 'BUY', 10,
                    100000, 95000, 110000, '{"volume_surge": 1.5, "adx_14": 26.0}', 1, '2026-10-01T20:00:00+05:30'
                )
                """
            )
            conn.commit()
        finally:
            conn.close()

        win_meta = {
            "window_id": "rolling_w1",
            "name": "Rolling Window 1",
            "start_date": "2026-10-01",
            "end_date": "2026-10-02",
            "regime_label": "BULL_TREND",
            "description": "Populated test",
            "sessions_count": 180,
        }
        rep = generate_window_report(db_path, win_meta)
        md = format_markdown_report(rep)

        # Assert Section 5 populated table
        assert "FALSE_BREAKOUT" in md
        assert "EXITED_TOO_EARLY" in md
        assert "+14.50%" in md  # Post-exit 20d drift
        assert "-3.20%" in md  # MAE

        # Assert Section 6 populated table
        assert "FAITHFUL" in md
        assert "100.0%" in md


def test_historical_data_provider_point_in_time_layering():
    ohlcv_conn = sqlite3.connect(":memory:")
    ohlcv_conn.row_factory = sqlite3.Row
    ohlcv_conn.execute(
        "CREATE TABLE ohlcv (trade_date TEXT, ticker TEXT, open REAL, high REAL, low REAL, close REAL, volume REAL)"
    )
    ohlcv_conn.execute("INSERT INTO ohlcv VALUES ('2025-06-15', 'TEST', 100, 105, 99, 102, 1000)")
    ohlcv_conn.execute("INSERT INTO ohlcv VALUES ('2025-09-01', 'TEST', 102, 108, 101, 106, 1200)")

    fund_conn = sqlite3.connect(":memory:")
    fund_conn.row_factory = sqlite3.Row
    from scripts.parse_screener_sheets import init_quarterly_history_table

    init_quarterly_history_table(fund_conn)

    # Q1 FY26: end 2025-06-30 -> filing date 2025-08-14 (45 days)
    fund_conn.execute(
        """
        INSERT INTO fundamental_quarterly_history
        (ticker, period_end_date, filing_date, sales, operating_profit, net_profit, eps, roce_pct, created_at)
        VALUES ('TEST', '2025-06-30', '2025-08-14', 500, 100, 75, 15.0, 22.5, '2025-08-14')
        """
    )
    # Frozen current snapshot
    fund_conn.execute("CREATE TABLE fundamental_ratios (ticker TEXT PRIMARY KEY, roce_pct REAL, raw_json TEXT)")
    fund_conn.execute("INSERT INTO fundamental_ratios VALUES ('TEST', 18.0, '{}')")
    fund_conn.commit()

    from backtest.data_provider import HistoricalDataProvider

    provider = HistoricalDataProvider(ohlcv_conn=ohlcv_conn, fundamental_conn=fund_conn)

    # Query BEFORE filing date (e.g. 2025-07-15) -> Layer 2 hidden, fallback to Layer 3
    row_before = provider.get_fundamental_row("TEST", "2025-07-15")
    assert row_before is not None
    assert row_before["fundamentals_source"] == "FROZEN_CURRENT"
    assert row_before["roce_pct"] == 18.0

    # Query ON OR AFTER filing date (e.g. 2025-08-20) -> Layer 2 visible
    row_after = provider.get_fundamental_row("TEST", "2025-08-20")
    assert row_after is not None
    assert row_after["fundamentals_source"] == "POINT_IN_TIME"
    assert row_after["roce_pct"] == 22.5


def test_persona_cadence_and_debounce_rules():
    from backtest.engine import is_persona_due_today

    last_run = {"simons": 10, "varsity": 10, "marks": 10, "jhunjhunwala": 10}

    # All personas have intrinsic cadence and evaluate every trading session
    assert is_persona_due_today("simons", 11, last_run, "NORMAL", "NORMAL", remaining_sessions=100) is True
    assert is_persona_due_today("varsity", 11, last_run, "NORMAL", "NORMAL", remaining_sessions=100) is True
    assert is_persona_due_today("marks", 11, last_run, "NORMAL", "NORMAL", remaining_sessions=150) is True
    assert is_persona_due_today("jhunjhunwala", 11, last_run, "NORMAL", "NORMAL", remaining_sessions=100) is True

    # High priority event trigger (TARGET_REACHED) always returns True
    assert (
        is_persona_due_today(
            "simons", 11, last_run, "NORMAL", "NORMAL", remaining_sessions=0, has_target_reached_event=True
        )
        is True
    )

    # Tail entry cutoff: min_hold_days=1 -> if remaining_sessions < 1 (0 remaining), cannot open new positions
    assert is_persona_due_today("simons", 11, last_run, "NORMAL", "NORMAL", remaining_sessions=0) is False
    assert is_persona_due_today("jhunjhunwala", 11, last_run, "NORMAL", "NORMAL", remaining_sessions=0) is False


def test_screener_parser_quarter_calculation():
    from scripts.parse_screener_sheets import compute_lodr_filing_date, parse_period_string

    q_june = parse_period_string("Jun 2025")
    assert q_june == date(2025, 6, 30)
    # Q1: 45 days LODR floor
    assert compute_lodr_filing_date(q_june) == date(2025, 8, 14)

    q_march = parse_period_string("Mar 2026")
    assert q_march == date(2026, 3, 31)
    # Q4 / Annual: 60 days LODR floor
    assert compute_lodr_filing_date(q_march) == date(2026, 5, 30)


def test_broker_sim_breakeven_ratchet_and_time_stops():
    from backtest.broker_sim import resolve_day
    from backtest.engine import SimulatedClock, inherit_prior_memory
    from broker.engine import Broker
    from scripts.init_db import init_db

    port_conn = sqlite3.connect(":memory:")
    port_conn.row_factory = sqlite3.Row
    init_db(port_conn)

    ohlcv_conn = sqlite3.connect(":memory:")
    ohlcv_conn.row_factory = sqlite3.Row
    ohlcv_conn.executescript("""
        CREATE TABLE ohlcv (
            trade_date TEXT, ticker TEXT, open REAL, high REAL, low REAL, close REAL, volume REAL
        );
        -- Candle 1: High reaches 1065.0, breaching target @ 1060.0 (106000 paise)
        INSERT INTO ohlcv VALUES ('2026-10-02', 'INFY', 1020.0, 1065.0, 1010.0, 1050.0, 100000);
        -- Candle 2: Drops back to 990.0, hitting the agent-ratcheted stop
        INSERT INTO ohlcv VALUES ('2026-10-05', 'INFY', 995.0, 1005.0, 990.0, 992.0, 100000);
    """)

    # Seed calendar for trading days
    port_conn.executescript("""
        INSERT INTO market_calendar (trade_date, is_trading_day) VALUES
        ('2026-10-01', 1), ('2026-10-02', 1), ('2026-10-05', 1), ('2026-10-06', 1);
    """)

    # Open position for Simons: bought @ 1000 with stop @ 940, target @ 1060 (106000 paise)
    port_conn.execute("""
        INSERT INTO positions (
            id, agent_id, ticker, sector, shares, avg_entry_price_paise,
            stop_paise, target_paise, last_price_paise, status, entry_date
        ) VALUES (
            1, 'simons', 'INFY', 'IT', 10, 100000, 94000, 106000, 100000, 'OPEN', '2026-10-01'
        )
    """)
    port_conn.commit()

    clock = SimulatedClock(datetime(2026, 10, 2, 10, 0, tzinfo=IST))
    res1 = resolve_day(port_conn, ohlcv_conn, clock, "2026-10-02", nifty500_close=24000.0)
    assert res1["status"] == "SUCCESS"
    assert res1["targets"] == 1

    # Broker logs TARGET_REACHED and enforces broker-level graduated trailing stop (breakeven ratchet at +1.08R)
    pos = port_conn.execute("SELECT * FROM positions WHERE id = 1").fetchone()
    assert pos["status"] == "OPEN"
    assert pos["stop_paise"] == 100000  # Auto-ratcheted to breakeven (entry price) at >= +1.0R peak

    act = port_conn.execute("SELECT * FROM activity_log WHERE event_type = 'TARGET_REACHED'").fetchone()
    assert act is not None
    assert act["ticker"] == "INFY"

    # Agent party executes ADJUST decision to ratchet stop and trail target
    broker = Broker(port_conn, clock)
    adjust_decision = {
        "id": 101,
        "agent_id": "simons",
        "ticker": "INFY",
        "stop_paise": 103000,  # locked 50% profit (1000 + (1060 - 1000)*0.5)
        "target_paise": 115000,
    }
    assert broker._process_adjust(adjust_decision) is True

    ratcheted_pos = port_conn.execute("SELECT * FROM positions WHERE id = 1").fetchone()
    assert ratcheted_pos["stop_paise"] == 103000
    assert ratcheted_pos["target_paise"] == 115000

    # On next day, candle low dips to 990.0 -> broker executes automatic STOP_HIT at ratcheted stop
    clock.set_time(datetime(2026, 10, 5, 10, 0, tzinfo=IST))
    res2 = resolve_day(port_conn, ohlcv_conn, clock, "2026-10-05", nifty500_close=24000.0)
    assert res2["stops"] == 1

    closed_pos = port_conn.execute("SELECT * FROM positions WHERE id = 1").fetchone()
    assert closed_pos["status"] == "CLOSED"
    assert closed_pos["exit_reason"] == "STOP_HIT"
    # Exited near open (99500 with ~10 bps slippage = 99401 paise), saving from full -6% loss
    assert 99000 <= closed_pos["exit_price_paise"] <= 99500
    assert closed_pos["realized_pnl_pct"] > -1.5  # Dramatically better than -6.0%

    # --- Test 2: Mechanical Max Hold Time Stop (14 sessions for Simons) ---
    port_conn.execute("""
        INSERT INTO positions (
            id, agent_id, ticker, sector, shares, avg_entry_price_paise,
            stop_paise, target_paise, last_price_paise, status, entry_date
        ) VALUES (
            2, 'simons', 'TCS', 'IT', 5, 300000, 270000, 360000, 300000, 'OPEN', '2026-09-01'
        )
    """)
    ohlcv_conn.executescript("""
        INSERT INTO ohlcv VALUES ('2026-10-06', 'TCS', 3050.0, 3100.0, 3020.0, 3080.0, 50000);
    """)
    port_conn.commit()

    # Run on 2026-10-06 (way past 14 sessions from 2026-09-01)
    clock.set_time(datetime(2026, 10, 6, 10, 0, tzinfo=IST))
    res3 = resolve_day(port_conn, ohlcv_conn, clock, "2026-10-06", nifty500_close=24000.0)
    assert res3["stops"] == 1

    time_pos = port_conn.execute("SELECT * FROM positions WHERE id = 2").fetchone()
    assert time_pos["status"] == "CLOSED"
    assert time_pos["exit_reason"] == "TIME_STOP_HIT"


def test_broker_sim_crash_cancelled_on_gap_down():
    from backtest.broker_sim import resolve_day
    from backtest.engine import SimulatedClock, inherit_prior_memory
    from scripts.init_db import init_db

    port_conn = sqlite3.connect(":memory:")
    port_conn.row_factory = sqlite3.Row
    init_db(port_conn)

    ohlcv_conn = sqlite3.connect(":memory:")
    ohlcv_conn.row_factory = sqlite3.Row
    ohlcv_conn.executescript("""
        CREATE TABLE ohlcv (
            trade_date TEXT, ticker TEXT, open REAL, high REAL, low REAL, close REAL, volume REAL
        );
        -- Gap-down crash candle: opens at 890.0, below stop @ 900.0 (90000 paise)
        INSERT INTO ohlcv VALUES ('2026-10-02', 'TATAMOTORS', 890.0, 950.0, 880.0, 940.0, 100000);
    """)

    port_conn.executescript("""
        INSERT INTO market_calendar (trade_date, is_trading_day) VALUES ('2026-10-02', 1);
    """)

    # Pending BUY order with entry [940.0, 960.0] and stop 900.0 (90000 paise)
    now_iso = "2026-10-02T09:00:00+05:30"
    port_conn.execute(
        """
        INSERT INTO pending_orders (
            id, agent_id, ticker, side, shares, entry_low_paise, entry_high_paise,
            stop_paise, target_paise, reserved_amount_paise, status, valid_for_date, created_at, updated_at
        ) VALUES (
            1, 'simons', 'TATAMOTORS', 'BUY', 10, 94000, 96000, 90000, 102000, 1000000, 'pending', '2026-10-02', ?, ?
        )
    """,
        (now_iso, now_iso),
    )
    port_conn.commit()

    clock = SimulatedClock(datetime(2026, 10, 2, 10, 0, tzinfo=IST))
    res = resolve_day(port_conn, ohlcv_conn, clock, "2026-10-02", nifty500_close=24000.0)
    assert res["status"] == "SUCCESS"
    assert res["fills"] == 0

    order = port_conn.execute("SELECT status, rejection_reason FROM pending_orders WHERE id = 1").fetchone()
    assert order["status"] == "cancelled"
    assert order["rejection_reason"] == "CRASH_CANCELLED"


def test_inherit_prior_memory():
    with tempfile.TemporaryDirectory() as tmpdir:
        src_db = Path(tmpdir) / "source.db"
        src_conn = sqlite3.connect(src_db)
        src_conn.execute("""
            CREATE TABLE agent_memory (
                id INTEGER PRIMARY KEY,
                agent_id TEXT,
                kind TEXT,
                context TEXT,
                heuristic_text TEXT,
                trigger_json TEXT,
                prescribed_action TEXT,
                status TEXT,
                confidence REAL,
                created_at TEXT,
                updated_at TEXT
            )
        """)
        src_conn.execute("""
            INSERT INTO agent_memory (agent_id, kind, context, heuristic_text, trigger_json, prescribed_action, status, confidence, created_at, updated_at)
            VALUES ('varsity', 'AVOID', 'ENTRY', 'Avoid high RSI', '{\"feature\":\"rsi_14\",\"op\":\">\",\"value\":65}', 'HOLD', 'reinforced', 0.85, '2025-05-01', '2025-05-01')
        """)
        src_conn.execute("""
            INSERT INTO agent_memory (agent_id, kind, context, heuristic_text, trigger_json, prescribed_action, status, confidence, created_at, updated_at)
            VALUES ('simons', 'SEEK', 'EXIT', 'Exit on momentum decay', '{\"feature\":\"macd_hist\",\"op\":\"<\",\"value\":0}', 'SELL', 'active', 0.75, '2025-05-01', '2025-05-01')
        """)
        src_conn.execute("""
            INSERT INTO agent_memory (agent_id, kind, context, heuristic_text, trigger_json, prescribed_action, status, confidence, created_at, updated_at)
            VALUES ('lynch', 'AVOID', 'ENTRY', 'Testing rule', '{\"feature\":\"peg\",\"op\":\">\",\"value\":1.5}', 'HOLD', 'testing', 0.5, '2025-05-01', '2025-05-01')
        """)
        src_conn.commit()
        src_conn.close()

        target_conn = sqlite3.connect(":memory:")
        target_conn.row_factory = sqlite3.Row
        target_conn.execute("""
            CREATE TABLE agent_memory (
                id INTEGER PRIMARY KEY,
                agent_id TEXT,
                kind TEXT,
                context TEXT,
                heuristic_text TEXT,
                trigger_json TEXT,
                prescribed_action TEXT,
                status TEXT,
                confidence REAL,
                created_at TEXT,
                updated_at TEXT
            )
        """)
        clock = SimulatedClock(datetime(2025, 6, 1, 9, 0, tzinfo=IST))
        count = inherit_prior_memory(target_conn, src_db, clock)

        # Should only copy active and reinforced (2 out of 3, ignoring testing)
        assert count == 2
        rows = target_conn.execute("SELECT agent_id, status FROM agent_memory ORDER BY agent_id").fetchall()
        assert len(rows) == 2
        assert rows[0]["agent_id"] == "simons" and rows[0]["status"] == "active"
        assert rows[1]["agent_id"] == "varsity" and rows[1]["status"] == "reinforced"
