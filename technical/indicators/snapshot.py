"""
Vectorized pandas/numpy indicator functions for the FeatureSnapshot technical group
(ema_20/50/200, rsi_14, macd_hist, adx_14, atr_14, volume_surge, obv_slope_sign,
dist_52w_high_pct/low_pct, ema_20_above_50). No network, no database.
See Plan_v3 §2.1, §2.2.
"""
import numpy as np
import pandas as pd

_EPSILON = 1e-9
_FLAT_ATR_PCT_THRESHOLD = 0.001  # 0.1% of price


def ema(series: pd.Series, period: int) -> pd.Series:
    """Standard EMA (adjust=False), matching TradingView's convention."""
    return series.ewm(span=period, min_periods=period, adjust=False).mean()


def rsi_wilder(close: pd.Series, period: int = 14) -> pd.Series:
    """Wilder-smoothed RSI (alpha = 1/period on the gain/loss series). When a session has
    neither gains nor losses (a perfectly flat price run), RS is 0/0 and is defined here as
    neutral RSI = 50, rather than the epsilon-skewed 0 that the raw formula would give."""
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / (avg_loss + _EPSILON)
    rsi = 100 - (100 / (1 + rs))
    flat = (avg_gain.abs() < _EPSILON) & (avg_loss.abs() < _EPSILON)
    return rsi.where(~flat, 50.0)


def macd_histogram(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.Series:
    """MACD histogram = (EMA(fast) - EMA(slow)) - EMA(signal) of that difference."""
    macd_line = ema(close, fast) - ema(close, slow)
    signal_line = ema(macd_line, signal)
    return macd_line - signal_line


def true_range(df: pd.DataFrame) -> pd.Series:
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    return pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)


def atr_wilder(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Wilder-smoothed Average True Range."""
    return true_range(df).ewm(alpha=1 / period, min_periods=period, adjust=False).mean()


def adx_wilder(df: pd.DataFrame, period: int = 14, atr: pd.Series = None) -> pd.Series:
    """Wilder ADX. +DI/-DI are normalised by ATR (epsilon-guarded against a near-zero ATR)."""
    high, low = df["high"], df["low"]
    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = up_move.where((up_move > down_move) & (up_move > 0), 0.0)
    minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0.0)

    atr_series = atr if atr is not None else atr_wilder(df, period)
    smoothed_plus_dm = plus_dm.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    smoothed_minus_dm = minus_dm.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()

    denom = atr_series.abs() + _EPSILON
    plus_di = 100 * smoothed_plus_dm / denom
    minus_di = 100 * smoothed_minus_dm / denom

    dx_denom = (plus_di + minus_di).abs() + _EPSILON
    dx = 100 * (plus_di - minus_di).abs() / dx_denom
    return dx.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()


def volume_surge(volume: pd.Series, window: int = 20) -> pd.Series:
    """Today's volume divided by the `window`-session average volume INCLUDING today
    (pandas' trailing rolling window ends at, and so includes, the current row)."""
    avg_volume = volume.rolling(window=window, min_periods=window).mean()
    return volume / (avg_volume + _EPSILON)


def obv(df: pd.DataFrame) -> pd.Series:
    """On-Balance Volume: cumulative sum of signed volume (sign of the day's close change)."""
    direction = np.sign(df["close"].diff()).fillna(0)
    return (direction * df["volume"]).cumsum()


def _rolling_slope(series: pd.Series, window: int) -> pd.Series:
    """Closed-form OLS slope of `series` against 0..window-1, per rolling window."""
    x = np.arange(window, dtype=float)
    x_demeaned = x - x.mean()
    denom = (x_demeaned ** 2).sum()

    def _slope(y: np.ndarray) -> float:
        return float((x_demeaned * (y - y.mean())).sum() / denom)

    return series.rolling(window=window).apply(_slope, raw=True)


def obv_slope_sign(obv_series: pd.Series, window: int = 10) -> pd.Series:
    """Sign (-1, 0, +1) of the `window`-session linear slope of OBV."""
    return np.sign(_rolling_slope(obv_series, window))


def dist_from_52w_high_pct(close: pd.Series, window: int = 252) -> pd.Series:
    """Percent distance of close from the `window`-session high; always <= 0, since the
    rolling max includes today's close."""
    rolling_high = close.rolling(window=window, min_periods=window).max()
    return (close - rolling_high) / (rolling_high + _EPSILON) * 100


def dist_from_52w_low_pct(close: pd.Series, window: int = 252) -> pd.Series:
    """Percent distance of close from the `window`-session low; always >= 0."""
    rolling_low = close.rolling(window=window, min_periods=window).min()
    return (close - rolling_low) / (rolling_low + _EPSILON) * 100


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Returns a copy of `df` (expects columns open, high, low, close, volume, sorted ascending
    by date) with every FeatureSnapshot technical column appended.

    Flat-price guard: every ratio above already has an epsilon added to its divisor. On top of
    that, when ATR is below 0.1% of price (a near-flat run), adx_14 and volume_surge are
    overridden to a neutral value (0.0 and 1.0 respectively) rather than trusting a ratio whose
    denominator is close to zero.
    """
    out = df.copy()
    close = out["close"]

    out["ema_20"] = ema(close, 20)
    out["ema_50"] = ema(close, 50)
    out["ema_200"] = ema(close, 200)
    out["ema_20_above_50"] = out["ema_20"] > out["ema_50"]

    out["rsi_14"] = rsi_wilder(close, 14)
    out["macd_hist"] = macd_histogram(close, 12, 26, 9)

    out["atr_14"] = atr_wilder(out, 14)
    out["adx_14"] = adx_wilder(out, 14, atr=out["atr_14"])

    out["volume_surge"] = volume_surge(out["volume"], 20)

    out["obv"] = obv(out)
    out["obv_slope_sign"] = obv_slope_sign(out["obv"], 10)

    out["dist_52w_high_pct"] = dist_from_52w_high_pct(close, 252)
    out["dist_52w_low_pct"] = dist_from_52w_low_pct(close, 252)

    atr_pct = out["atr_14"] / (close.abs() + _EPSILON)
    flat = atr_pct < _FLAT_ATR_PCT_THRESHOLD
    out.loc[flat, "adx_14"] = 0.0
    out.loc[flat, "volume_surge"] = 1.0

    return out
