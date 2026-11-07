"""
StockMinds Backtesting and Walk-Forward Simulation Subsystem.
Provides multi-regime historical simulation, persistent LLM decision caching,
daily candle matching, order expiry, and Question B evaluation reporting.
"""

from backtest.config import BacktestWindowConfig, get_curated_regime_windows, get_rolling_windows
from backtest.engine import BacktestEngine
from backtest.reports import format_markdown_report, generate_window_report

__all__ = [
    "BacktestWindowConfig",
    "get_rolling_windows",
    "get_curated_regime_windows",
    "BacktestEngine",
    "generate_window_report",
    "format_markdown_report",
]
