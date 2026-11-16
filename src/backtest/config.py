"""
Backtest window configuration and rolling window generator.
Pure data specification: window boundaries, regime labels, warmup sessions,
and declarative persona cadence tables.
See Plan_v3 §5.6.
"""

import sqlite3
from dataclasses import dataclass
from typing import Any

WARMUP_SESSIONS: int = 300


@dataclass(frozen=True)
class CadenceRule:
    persona_id: str
    base_interval_sessions: int  # Base cadence in trading sessions (1=daily, 2=semi-weekly, 5=weekly, 10=bi-weekly)
    secondary_trigger: str | None  # e.g., "REGIME_CHANGE" for Marks
    cooldown_sessions: int  # Minimum sessions between runs (debounce guard)
    max_hold_days: int  # Maximum holding period used for analysis and window gates
    min_hold_days: int = 1  # Minimum holding horizon required to open a position before window end (tail cutoff)


CADENCE_TABLE: dict[str, CadenceRule] = {
    "simons": CadenceRule(
        persona_id="simons",
        base_interval_sessions=1,
        secondary_trigger=None,
        cooldown_sessions=0,
        max_hold_days=14,
        min_hold_days=1,
    ),
    "baseline-simons-rules": CadenceRule(
        persona_id="baseline-simons-rules",
        base_interval_sessions=1,
        secondary_trigger=None,
        cooldown_sessions=0,
        max_hold_days=14,
        min_hold_days=1,
    ),
    "varsity": CadenceRule(
        persona_id="varsity",
        base_interval_sessions=1,
        secondary_trigger=None,
        cooldown_sessions=0,
        max_hold_days=75,
        min_hold_days=1,
    ),
    "baseline-varsity-rules": CadenceRule(
        persona_id="baseline-varsity-rules",
        base_interval_sessions=1,
        secondary_trigger=None,
        cooldown_sessions=0,
        max_hold_days=75,
        min_hold_days=1,
    ),
    "marks": CadenceRule(
        persona_id="marks",
        base_interval_sessions=1,
        secondary_trigger="REGIME_CHANGE",
        cooldown_sessions=0,
        max_hold_days=120,
        min_hold_days=1,
    ),
    "baseline-marks-rules": CadenceRule(
        persona_id="baseline-marks-rules",
        base_interval_sessions=1,
        secondary_trigger="REGIME_CHANGE",
        cooldown_sessions=0,
        max_hold_days=120,
        min_hold_days=1,
    ),
    "lynch": CadenceRule(
        persona_id="lynch",
        base_interval_sessions=1,
        secondary_trigger=None,
        cooldown_sessions=0,
        max_hold_days=90,
        min_hold_days=1,
    ),
    "baseline-lynch-rules": CadenceRule(
        persona_id="baseline-lynch-rules",
        base_interval_sessions=1,
        secondary_trigger=None,
        cooldown_sessions=0,
        max_hold_days=90,
        min_hold_days=1,
    ),
    "jhunjhunwala": CadenceRule(
        persona_id="jhunjhunwala",
        base_interval_sessions=1,
        secondary_trigger=None,
        cooldown_sessions=0,
        max_hold_days=180,
        min_hold_days=1,
    ),
    "baseline-rj-rules": CadenceRule(
        persona_id="baseline-rj-rules",
        base_interval_sessions=1,
        secondary_trigger=None,
        cooldown_sessions=0,
        max_hold_days=180,
        min_hold_days=1,
    ),
}


@dataclass(frozen=True)
class BacktestWindowConfig:
    window_id: str
    name: str
    start_date: str
    end_date: str
    regime_label: str
    description: str
    sessions_count: int


# Data-Derived Empirical Walk-Forward Windows for Backtesting
BACKTEST_WINDOWS: dict[str, BacktestWindowConfig] = {
    "rolling_w1": BacktestWindowConfig(
        window_id="rolling_w1",
        name="Rolling Window 1 (Bull Trend)",
        start_date="2025-02-28",
        end_date="2025-11-21",
        regime_label="BULL_TREND",
        description="Expansion and sustained momentum recovery (+19.7% Nifty, 13.4 avg VIX)",
        sessions_count=180,
    ),
    "rolling_w2": BacktestWindowConfig(
        window_id="rolling_w2",
        name="Rolling Window 2 (High Volatility Correction & Recovery)",
        start_date="2026-02-05",
        end_date="2026-10-29",
        regime_label="HIGH_VOL_CORRECTION",
        description="Elevated India VIX regime and correction drawdown testing (-13.7% max DD, 27.9 peak VIX)",
        sessions_count=180,
    ),
    "supplementary_range": BacktestWindowConfig(
        window_id="supplementary_range",
        name="Supplementary Window (Range-Bound Compression)",
        start_date="2025-11-24",
        end_date="2026-02-04",
        regime_label="RANGE_BOUND",
        description="Low volatility sideways consolidation (-0.6% return, 11.3 avg VIX, zero days VIX>=18)",
        sessions_count=51,
    ),
}

# Persona holding horizons for verification against backtest windows
PERSONA_HOLDING_HORIZONS: dict[str, dict[str, Any]] = {
    "simons": {"min_hold_days": 1, "max_hold_days": 14, "name": "Quant Momentum"},
    "baseline-simons-rules": {"min_hold_days": 1, "max_hold_days": 14, "name": "Rules Momentum Baseline"},
    "varsity": {"min_hold_days": 20, "max_hold_days": 75, "name": "Zerodha Varsity Balanced"},
    "baseline-varsity-rules": {"min_hold_days": 20, "max_hold_days": 75, "name": "Rules Varsity Baseline"},
    "marks": {"min_hold_days": 21, "max_hold_days": 120, "name": "Contrarian Value"},
    "baseline-marks-rules": {"min_hold_days": 21, "max_hold_days": 120, "name": "Rules Contrarian Baseline"},
    "lynch": {"min_hold_days": 30, "max_hold_days": 90, "name": "GARP Compounder"},
    "baseline-lynch-rules": {"min_hold_days": 30, "max_hold_days": 90, "name": "Rules GARP Baseline"},
    "jhunjhunwala": {"min_hold_days": 90, "max_hold_days": 180, "name": "Growth Compounder"},
    "baseline-rj-rules": {"min_hold_days": 90, "max_hold_days": 180, "name": "Rules Compounder Baseline"},
}


def get_all_trading_dates(ohlcv_conn: sqlite3.Connection, min_tickers: int = 200) -> list[str]:
    """Returns sorted unique trading dates from ohlcv.db with sufficient ticker coverage."""
    rows = ohlcv_conn.execute(
        """
        SELECT trade_date FROM ohlcv
        GROUP BY trade_date
        HAVING count(*) >= ?
        ORDER BY trade_date ASC
        """,
        (min_tickers,),
    ).fetchall()
    return [r[0] if isinstance(r, (tuple, list)) else r["trade_date"] for r in rows]


def get_rolling_windows(
    ohlcv_conn: sqlite3.Connection,
    min_warmup_sessions: int = 200,
    window_len_sessions: int = 180,
    step_sessions: int = 30,
    min_tickers: int = 200,
) -> list[BacktestWindowConfig]:
    """
    Generates rolling 180-trading-day walk-forward windows shifted by 30 trading days.
    Guarantees sufficient lookback history prior to start_date for 200 EMA & indicators.
    """
    all_dates = get_all_trading_dates(ohlcv_conn, min_tickers=min_tickers)
    total_dates = len(all_dates)

    if total_dates < min_warmup_sessions + window_len_sessions:
        start_idx = max(0, total_dates - window_len_sessions)
        return [
            BacktestWindowConfig(
                window_id="window_full_history",
                name="Full History Test Window",
                start_date=all_dates[start_idx] if all_dates else "2026-01-01",
                end_date=all_dates[-1] if all_dates else "2026-10-29",
                regime_label="MIXED",
                description="Entire available historical range",
                sessions_count=len(all_dates) - start_idx,
            )
        ]

    windows: list[BacktestWindowConfig] = []
    current_start_idx = min_warmup_sessions
    window_idx = 1

    while current_start_idx + window_len_sessions <= total_dates:
        end_idx = current_start_idx + window_len_sessions - 1
        start_dt = all_dates[current_start_idx]
        end_dt = all_dates[end_idx]

        if window_idx == 1:
            regime = "BULL_TREND"
            desc = "Uptrend & Expansion with strong momentum"
        elif window_idx == 2:
            regime = "RANGE_BOUND"
            desc = "Sector rotation, low directional trend"
        elif window_idx == 3:
            regime = "HIGH_VOLATILITY"
            desc = "Correction period with elevated India VIX"
        else:
            regime = f"ROLLING_CYCLE_{window_idx}"
            desc = f"Walk-forward shifted window #{window_idx}"

        windows.append(
            BacktestWindowConfig(
                window_id=f"rolling_w{window_idx}",
                name=f"Rolling Window {window_idx} ({regime})",
                start_date=start_dt,
                end_date=end_dt,
                regime_label=regime,
                description=desc,
                sessions_count=window_len_sessions,
            )
        )

        current_start_idx += step_sessions
        window_idx += 1

    return windows


def get_curated_regime_windows(ohlcv_conn: sqlite3.Connection | None = None) -> list[BacktestWindowConfig]:
    """Returns the curated representative walk-forward windows (rolling_w1, rolling_w2, rolling_w3)."""
    return list(BACKTEST_WINDOWS.values())
