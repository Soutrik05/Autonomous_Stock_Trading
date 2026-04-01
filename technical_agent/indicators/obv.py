# =============================================================================
# indicators/obv.py
#
# On-Balance Volume — manual implementation.
#
# OBV is a running cumulative total:
#   If close > prev_close: OBV += volume  (up day — buyers in control)
#   If close < prev_close: OBV -= volume  (down day — sellers in control)
#   If close == prev_close: OBV unchanged
#
# Raw OBV value is meaningless on its own — the magnitude depends on share
# float and volume scale. What matters is the DIRECTION of OBV vs price:
#
#   OBV rising + price rising  -> volume confirms the move (strong)
#   OBV rising + price flat    -> accumulation (bullish divergence, price likely follows)
#   OBV falling + price rising -> distribution (bearish divergence, price likely drops)
#   OBV falling + price falling-> volume confirms downtrend (strong)
#
# We measure OBV trend over OBV_TREND_LOOKBACK candles using linear regression
# slope (more robust than just comparing first vs last value).
# =============================================================================

import logging
import numpy as np
import pandas as pd
from technical_agent.config import OBV_TREND_LOOKBACK

logger = logging.getLogger(__name__)


def _slope(series: pd.Series) -> float:
    """
    Returns the linear regression slope of a series.
    Normalised by mean to make it comparable across stocks with different
    volume scales (e.g. large-cap vs small-cap).
    """
    y    = series.values
    x    = np.arange(len(y))
    mean = np.mean(y)
    if mean == 0:
        return 0.0
    slope = np.polyfit(x, y, 1)[0]
    return slope / abs(mean)  # normalised slope


def compute_obv(df: pd.DataFrame) -> dict:
    """
    Computes OBV and extracts trend signals.

    Args:
        df: OHLCV DataFrame with 'close' and 'volume' columns.

    Returns:
        dict with keys:
            obv_latest       (float)  most recent OBV value
            obv_slope        (float)  normalised slope of OBV over lookback period
            price_slope      (float)  normalised slope of price over same period
            accumulation     (bool)   OBV trending up (regardless of price)
            distribution     (bool)   OBV trending down (regardless of price)
            bullish_divergence (bool) OBV rising while price flat/falling
            bearish_divergence (bool) OBV falling while price flat/rising
    """
    if "close" not in df.columns or "volume" not in df.columns:
        raise KeyError("DataFrame must have 'close' and 'volume' columns.")

    close  = df["close"]
    volume = df["volume"]

    # Build OBV series
    obv    = [0]
    for i in range(1, len(close)):
        if close.iloc[i] > close.iloc[i - 1]:
            obv.append(obv[-1] + volume.iloc[i])
        elif close.iloc[i] < close.iloc[i - 1]:
            obv.append(obv[-1] - volume.iloc[i])
        else:
            obv.append(obv[-1])

    obv_series = pd.Series(obv, index=df.index, name="obv")

    # Measure trend over lookback window
    lookback     = OBV_TREND_LOOKBACK
    obv_window   = obv_series.iloc[-lookback:]
    price_window = close.iloc[-lookback:]

    obv_slope   = _slope(obv_window)
    price_slope = _slope(price_window)

    accumulation = obv_slope > 0
    distribution = obv_slope < 0

    # Divergence: OBV and price moving in meaningfully opposite directions
    # Threshold of 0.001 filters out noise (flat slopes near zero)
    bullish_divergence = (obv_slope > 0.001) and (price_slope < -0.001)
    bearish_divergence = (obv_slope < -0.001) and (price_slope > 0.001)

    return {
        "obv_latest":          float(obv_series.iloc[-1]),
        "obv_slope":           round(obv_slope, 6),
        "price_slope":         round(price_slope, 6),
        "accumulation":        accumulation,
        "distribution":        distribution,
        "bullish_divergence":  bullish_divergence,
        "bearish_divergence":  bearish_divergence,
    }
