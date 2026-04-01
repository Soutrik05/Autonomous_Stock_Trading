# =============================================================================
# indicators/macd.py
#
# Manual MACD implementation.
#
# MACD Line   = EMA(close, fast) - EMA(close, slow)
# Signal Line = EMA(MACD Line, signal_period)
# Histogram   = MACD Line - Signal Line
#
# Crossover detection:
#   Bullish cross: MACD was below signal yesterday, crossed above today
#   Bearish cross: MACD was above signal yesterday, crossed below today
#   Comparing two consecutive candles is more reliable than checking
#   histogram sign alone, which can flip on tiny moves.
# =============================================================================

import logging
import pandas as pd
from technical_agent.config import MACD_PARAMS

logger = logging.getLogger(__name__)


def _ema(series: pd.Series, period: int) -> pd.Series:
    """Standard EMA. adjust=False matches TradingView's implementation."""
    return series.ewm(span=period, min_periods=period, adjust=False).mean()


def compute_macd(df: pd.DataFrame, trade_type: str) -> dict:
    """
    Computes MACD and extracts key signals.

    Args:
        df:         OHLCV DataFrame with a 'close' column.
        trade_type: "swing", "medium", or "positional" -- selects MACD params.

    Returns:
        dict with keys:
            macd_line       (float)  current MACD line value
            signal_line     (float)  current signal line value
            histogram       (float)  current histogram value
            bullish_cross   (bool)   crossover happened on latest candle
            bearish_cross   (bool)   crossunder happened on latest candle
            macd_bullish    (bool)   MACD currently above signal (no fresh cross)
    """
    if "close" not in df.columns:
        raise KeyError("DataFrame must have a 'close' column.")

    params      = MACD_PARAMS[trade_type]
    close       = df["close"]
    macd_line   = _ema(close, params["fast"]) - _ema(close, params["slow"])
    signal_line = _ema(macd_line, params["signal"])
    histogram   = macd_line - signal_line

    # Current and previous values for crossover detection
    macd_now    = macd_line.iloc[-1]
    signal_now  = signal_line.iloc[-1]
    macd_prev   = macd_line.iloc[-2]
    signal_prev = signal_line.iloc[-2]

    bullish_cross = (macd_prev <= signal_prev) and (macd_now > signal_now)
    bearish_cross = (macd_prev >= signal_prev) and (macd_now < signal_now)

    hist_now  = float(histogram.iloc[-1])
    hist_prev = float(histogram.iloc[-2])
    histogram_improving = hist_now > hist_prev

    return {
        "macd_line":     round(macd_now, 4),
        "signal_line":   round(signal_now, 4),
        "histogram":     round(float(histogram.iloc[-1]), 4),
        "bullish_cross": bullish_cross,
        "bearish_cross": bearish_cross,
        "macd_bullish":  bool(macd_now > signal_now),
        "histogram_improving": histogram_improving
    }
