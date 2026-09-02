# =============================================================================
# indicators/rsi.py
#
# Manual RSI using Wilder's smoothing (EWM alpha=1/period).
#
# Formula:
#   delta    = close.diff()
#   gain     = delta where delta > 0, else 0
#   loss     = abs(delta) where delta < 0, else 0
#   avg_gain = Wilder EWM of gain
#   avg_loss = Wilder EWM of loss
#   RS       = avg_gain / avg_loss
#   RSI      = 100 - (100 / (1 + RS))
#
# Why Wilder's EWM and not simple rolling mean?
#   Wilder's smoothing (alpha=1/n, adjust=False) weights recent data slightly
#   more. TradingView uses this same method -- so our values match, which
#   makes manual validation against charts straightforward.
# =============================================================================
import logging
import pandas as pd
from technical_agent.config import RSI_PERIOD

logger = logging.getLogger(__name__)


def compute_rsi(df: pd.DataFrame, period: int = RSI_PERIOD) -> pd.Series:
    """
    Computes RSI for the full price series.

    Args:
        df:     OHLCV DataFrame with a 'close' column.
        period: Lookback period. Default 14 (Wilder's original).

    Returns:
        pd.Series of RSI values (0-100). First ~period values are NaN.
    """
    if "close" not in df.columns:
        raise KeyError("DataFrame must have a 'close' column.")

    close = df["close"]
    delta = close.diff()

    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)

    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()

    rs  = avg_gain / avg_loss.replace(0, float("nan"))
    rsi = 100 - (100 / (1 + rs))
    rsi.name = "rsi"
    return rsi


def get_latest_rsi(df: pd.DataFrame) -> float:
    """Returns the most recent RSI value. Used by signal_extractor."""
    try:
        return round(float(compute_rsi(df).iloc[-1]), 2)
    except Exception as e:
        logger.warning(f"RSI computation failed: {e}")
        return None
