"""
Unit tests for evaluation/performance.py and evaluation/comparison.py.
Verifies Sharpe ratio, maximum drawdown, win rate, profit factor,
small-sample flags, and Simons vs baseline paired comparisons.
"""

import sqlite3

import pytest

from evaluation.comparison import compare_simons_vs_baseline
from evaluation.performance import (
    calculate_agent_performance,
    calculate_max_drawdown,
    calculate_sharpe_ratio,
    calculate_sortino_ratio,
)


def test_calculate_sharpe_ratio_deterministic():
    # Constant return = 0 variance -> Sharpe = 0
    assert calculate_sharpe_ratio([0.01, 0.01, 0.01, 0.01, 0.01]) == 0.0

    # Short history (<5) -> 0.0
    assert calculate_sharpe_ratio([0.02, 0.01]) == 0.0

    # Strong positive series
    returns = [0.01, 0.015, -0.005, 0.02, 0.012, 0.008, 0.015, -0.002, 0.018, 0.022]
    sharpe = calculate_sharpe_ratio(returns, risk_free_annual_rate=0.06)
    assert sharpe > 1.0


def test_calculate_sortino_ratio():
    # Short history (<5) -> 0.0
    assert calculate_sortino_ratio([0.01, 0.02]) == 0.0

    # Series with positive returns and one minor dip
    returns = [0.01, 0.015, -0.005, 0.02, 0.012, 0.008, 0.015, -0.002, 0.018, 0.022]
    sortino = calculate_sortino_ratio(returns, risk_free_annual_rate=0.06)
    assert sortino > 1.0


def test_calculate_max_drawdown_calculation():
    assert calculate_max_drawdown([]) == 0.0
    assert calculate_max_drawdown([100]) == 0.0

    # Peak 100 -> drop to 80 -> -20.0%
    nav_series = [100, 105, 110, 99, 88, 100, 115]
    # Peak is 110, trough is 88: (88 - 110)/110 = -22/110 = -20.0%
    dd = calculate_max_drawdown(nav_series)
    assert dd == -20.0


@pytest.fixture
def test_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE agents (
            id TEXT PRIMARY KEY,
            kind TEXT NOT NULL
        );
        CREATE TABLE daily_nav (
            agent_id         TEXT NOT NULL,
            nav_date         TEXT NOT NULL,
            cash_paise       INTEGER NOT NULL,
            invested_paise   INTEGER NOT NULL,
            total_paise      INTEGER NOT NULL,
            nifty500_close   REAL NOT NULL,
            PRIMARY KEY (agent_id, nav_date)
        );
        CREATE TABLE positions (
            id                     INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_id               TEXT NOT NULL,
            ticker                 TEXT NOT NULL,
            shares                 INTEGER NOT NULL,
            avg_entry_price_paise  INTEGER NOT NULL,
            realized_pnl_paise     INTEGER,
            realized_pnl_pct       REAL,
            hold_days              INTEGER,
            exit_reason            TEXT,
            status                 TEXT NOT NULL,
            closed_at              TEXT
        );
        CREATE TABLE decisions (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_id            TEXT NOT NULL,
            run_date            TEXT NOT NULL,
            ticker              TEXT NOT NULL,
            action              TEXT NOT NULL,
            faithfulness_score  REAL
        );
        CREATE TABLE forward_returns (
            id                    INTEGER PRIMARY KEY AUTOINCREMENT,
            decision_id           INTEGER NOT NULL,
            horizon_days          INTEGER NOT NULL,
            return_pct            REAL NOT NULL,
            benchmark_return_pct  REAL NOT NULL,
            excess_return_pct     REAL NOT NULL
        );
        INSERT INTO agents (id, kind) VALUES ('simons', 'LLM');
        INSERT INTO agents (id, kind) VALUES ('baseline-simons-rules', 'BASELINE');
    """)
    yield conn
    conn.close()


def test_agent_performance_provisional_and_metrics(test_db):
    # Seed NAV series for simons (starting 10L paise, ending 10.5L paise)
    test_db.execute("INSERT INTO daily_nav VALUES ('simons', '2026-10-01', 100000000, 0, 100000000, 24000.0)")
    test_db.execute("INSERT INTO daily_nav VALUES ('simons', '2026-10-02', 80000000, 20500000, 100500000, 24100.0)")
    test_db.execute("INSERT INTO daily_nav VALUES ('simons', '2026-10-03', 75000000, 26000000, 101000000, 24050.0)")
    test_db.execute("INSERT INTO daily_nav VALUES ('simons', '2026-10-04', 70000000, 31500000, 101500000, 24150.0)")
    test_db.execute("INSERT INTO daily_nav VALUES ('simons', '2026-10-05', 65000000, 37000000, 102000000, 24200.0)")
    test_db.execute("INSERT INTO daily_nav VALUES ('simons', '2026-10-06', 60000000, 45000000, 105000000, 24240.0)")

    # Seed closed positions (2 wins, 1 loss)
    test_db.execute(
        "INSERT INTO positions (agent_id, ticker, shares, avg_entry_price_paise, realized_pnl_paise, realized_pnl_pct, hold_days, status, closed_at) VALUES ('simons', 'INFY', 10, 150000, 15000, 10.0, 5, 'CLOSED', '2026-10-06')"
    )
    test_db.execute(
        "INSERT INTO positions (agent_id, ticker, shares, avg_entry_price_paise, realized_pnl_paise, realized_pnl_pct, hold_days, status, closed_at) VALUES ('simons', 'TCS', 10, 350000, 20000, 5.7, 7, 'CLOSED', '2026-10-06')"
    )
    test_db.execute(
        "INSERT INTO positions (agent_id, ticker, shares, avg_entry_price_paise, realized_pnl_paise, realized_pnl_pct, hold_days, status, closed_at) VALUES ('simons', 'WIPRO', 10, 45000, -5000, -11.1, 4, 'CLOSED', '2026-10-06')"
    )

    perf = calculate_agent_performance(test_db, "simons", is_backtest=True)

    assert perf["agent_id"] == "simons"
    assert perf["is_backtest"] is True
    assert perf["evidence_label"] == "BACKTEST_DERIVED"
    assert perf["total_return_pct"] == 5.0  # (105000000 - 100000000)/100000000 = +5%
    assert perf["total_closed_trades"] == 3
    assert perf["winning_trades"] == 2
    assert perf["losing_trades"] == 1
    assert perf["win_rate_pct"] == 66.7
    assert perf["profit_factor"] == 7.0  # (15000 + 20000) / 5000 = 7.0
    assert perf["sortino_ratio"] > 0.0
    assert perf["avg_invested_pct"] > 0.0
    assert perf["cash_drag_pct"] < 100.0
    assert perf["payoff_ratio"] > 0.0
    assert "expectancy_pct" in perf
    assert perf["philosophy_adherence_pct"] == 100.0
    assert perf["is_provisional"] is True
    assert "PROVISIONAL" in perf["sample_notice"]


def test_comparison_simons_vs_baseline(test_db):
    test_db.execute("INSERT INTO daily_nav VALUES ('simons', '2026-10-01', 100000000, 0, 100000000, 24000.0)")
    test_db.execute("INSERT INTO daily_nav VALUES ('simons', '2026-10-06', 100000000, 0, 105000000, 24000.0)")
    test_db.execute(
        "INSERT INTO daily_nav VALUES ('baseline-simons-rules', '2026-10-01', 100000000, 0, 100000000, 24000.0)"
    )
    test_db.execute(
        "INSERT INTO daily_nav VALUES ('baseline-simons-rules', '2026-10-06', 100000000, 0, 101000000, 24000.0)"
    )

    cmp = compare_simons_vs_baseline(test_db, is_backtest=True)
    assert cmp["is_backtest"] is True
    assert cmp["deltas"]["excess_return_pct"] == 4.0  # 5.0 - 1.0 = +4.0%
    assert cmp["llm_adds_value"] is True


def test_performance_zero_trades_graceful_boundary(test_db):
    # Agent with zero trades, zero daily NAV rows
    test_db.execute("INSERT INTO agents (id, kind) VALUES ('new_agent', 'LLM')")
    perf = calculate_agent_performance(test_db, "new_agent", is_backtest=True)

    assert perf["agent_id"] == "new_agent"
    assert perf["total_closed_trades"] == 0
    assert perf["winning_trades"] == 0
    assert perf["losing_trades"] == 0
    assert perf["win_rate_pct"] == 0.0
    assert perf["profit_factor"] == 0.0
    assert perf["payoff_ratio"] == 0.0
    assert perf["expectancy_pct"] == 0.0
    assert perf["sortino_ratio"] == 0.0
    assert perf["calmar_ratio"] == 0.0
    assert perf["max_drawdown_pct"] == 0.0


def test_performance_100_pct_wins_no_division_by_zero(test_db):
    test_db.execute("INSERT INTO agents (id, kind) VALUES ('perfect_agent', 'LLM')")
    test_db.execute("INSERT INTO daily_nav VALUES ('perfect_agent', '2026-10-01', 100000000, 0, 100000000, 24000.0)")
    test_db.execute("INSERT INTO daily_nav VALUES ('perfect_agent', '2026-10-02', 100000000, 0, 110000000, 24000.0)")

    # 3 winning trades, 0 losses
    for i, pnl in enumerate([5.0, 8.0, 12.0]):
        test_db.execute(
            f"INSERT INTO positions (agent_id, ticker, shares, avg_entry_price_paise, realized_pnl_paise, realized_pnl_pct, hold_days, status, closed_at) "
            f"VALUES ('perfect_agent', 'WIN{i}', 10, 100000, 10000, {pnl}, 5, 'CLOSED', '2026-10-02')"
        )

    perf = calculate_agent_performance(test_db, "perfect_agent", is_backtest=True)
    assert perf["total_closed_trades"] == 3
    assert perf["winning_trades"] == 3
    assert perf["losing_trades"] == 0
    assert perf["win_rate_pct"] == 100.0
    assert perf["profit_factor"] == 999.0  # Clean fallback cap for 0 losses
    assert perf["payoff_ratio"] == 999.0  # Clean fallback cap for 0 losses
    assert perf["avg_loss_pct"] == 0.0
    assert perf["avg_win_pct"] == pytest.approx(8.33, abs=0.01)


def test_performance_100_pct_losses_no_division_by_zero(test_db):
    test_db.execute("INSERT INTO agents (id, kind) VALUES ('loss_agent', 'LLM')")
    test_db.execute("INSERT INTO daily_nav VALUES ('loss_agent', '2026-10-01', 100000000, 0, 100000000, 24000.0)")
    test_db.execute("INSERT INTO daily_nav VALUES ('loss_agent', '2026-10-02', 100000000, 0, 90000000, 24000.0)")

    # 2 losing trades, 0 wins
    for i, pnl in enumerate([-4.0, -6.0]):
        test_db.execute(
            f"INSERT INTO positions (agent_id, ticker, shares, avg_entry_price_paise, realized_pnl_paise, realized_pnl_pct, hold_days, status, closed_at) "
            f"VALUES ('loss_agent', 'LOSS{i}', 10, 100000, -5000, {pnl}, 5, 'CLOSED', '2026-10-02')"
        )

    perf = calculate_agent_performance(test_db, "loss_agent", is_backtest=True)
    assert perf["total_closed_trades"] == 2
    assert perf["winning_trades"] == 0
    assert perf["losing_trades"] == 2
    assert perf["win_rate_pct"] == 0.0
    assert perf["profit_factor"] == 0.0
    assert perf["payoff_ratio"] == 0.0
    assert perf["avg_win_pct"] == 0.0
    assert perf["avg_loss_pct"] == -5.0


def test_performance_zero_drawdown_calmar_handling(test_db):
    test_db.execute("INSERT INTO agents (id, kind) VALUES ('steady_agent', 'LLM')")
    # Strictly monotonically increasing NAV (0.0% drawdown)
    test_db.execute("INSERT INTO daily_nav VALUES ('steady_agent', '2026-10-01', 100000000, 0, 100000000, 24000.0)")
    test_db.execute("INSERT INTO daily_nav VALUES ('steady_agent', '2026-10-02', 100000000, 0, 101000000, 24000.0)")
    test_db.execute("INSERT INTO daily_nav VALUES ('steady_agent', '2026-10-03', 100000000, 0, 102000000, 24000.0)")

    perf = calculate_agent_performance(test_db, "steady_agent", is_backtest=True)
    assert perf["max_drawdown_pct"] == 0.0
    # Calmar ratio is safely 0.0 when drawdown is 0
    assert perf["calmar_ratio"] == 0.0
