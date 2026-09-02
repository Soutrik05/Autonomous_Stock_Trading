# =============================================================================
# indicators/ema.py
#
# EMA crossover signals — separate from MACD.
#
# MACD measures momentum (distance between EMAs, rate of change).
# EMA crossover measures trend structure (is short-term average above
# or below long-term average right now?).
# They can disagree — early trend reversals show MACD turning before
# the EMA crossover fires. That disagreement is useful information.
#
# Pairs used (from config.EMA_PAIRS):
#   Swing:      9  / 21  EMA
#   Medium:     25 / 50  EMA
#   Positional: 50 / 100 EMA
# =============================================================================

import logging
import pandas as pd
from technical_agent.config import EMA_PAIRS

logger = logging.getLogger(__name__)


def _ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, min_periods=period, adjust=False).mean()


def compute_ema_crossover(df: pd.DataFrame, trade_type: str) -> dict:
    """
    Computes EMA crossover signals for the given trade type.

    Args:
        df:         OHLCV DataFrame with a 'close' column.
        trade_type: "swing", "medium", or "positional" -- selects EMA pair.

    Returns:
        dict with keys:
            ema_short        (float) current short EMA value
            ema_long         (float) current long EMA value
            golden_cross     (bool)  short crossed above long on latest candle
            death_cross      (bool)  short crossed below long on latest candle
            ema_bullish      (bool)  short EMA currently above long EMA
            price_above_both (bool)  close > short EMA > long EMA (ideal bull)
            price_below_both (bool)  close < short EMA < long EMA (bear structure)
            short_period     (int)   for logging/display
            long_period      (int)   for logging/display
    """
    if "close" not in df.columns:
        raise KeyError("DataFrame must have a 'close' column.")

    pair       = EMA_PAIRS[trade_type]
    short_p    = pair["short"]
    long_p     = pair["long"]
    close      = df["close"]

    ema_short  = _ema(close, short_p)
    ema_long   = _ema(close, long_p)

    short_now  = ema_short.iloc[-1]
    long_now   = ema_long.iloc[-1]
    short_prev = ema_short.iloc[-2]
    long_prev  = ema_long.iloc[-2]
    price_now  = close.iloc[-1]

    golden_cross = (short_prev <= long_prev) and (short_now > long_now)
    death_cross  = (short_prev >= long_prev) and (short_now < long_now)

    return {
        "ema_short":        round(short_now, 2),
        "ema_long":         round(long_now, 2),
        "golden_cross":     golden_cross,
        "death_cross":      death_cross,
        "ema_bullish":      bool(short_now > long_now),
        "price_above_both": bool(price_now > short_now > long_now),
        "price_below_both": bool(price_now < short_now < long_now),
        "short_period":     short_p,
        "long_period":      long_p,
    }
