# =============================================================================
# scoring/signal_extractor.py
#
# Converts raw indicator outputs (floats, bools) into signal keys
# that map to scores and phrases defined in config.py.
#
# This layer is the "interpretation" layer. It knows what values mean
# in context — e.g. RSI > 70 is overbought in a ranging market, but in
# a strong trend (confirmed by EMA + MACD), it means sustained momentum.
#
# Nothing here knows about weights or final scores — that's scorer.py's job.
# =============================================================================

import logging
from technical_agent.config import (
    RSI_OVERSOLD, RSI_OVERBOUGHT, RSI_BULLISH_ZONE, RSI_BEARISH_ZONE,
)

logger = logging.getLogger(__name__)


def extract_cdl_signal(cdl_result: dict) -> str:
    """
    Converts candlestick booleans to a signal key.
    Strict priority hierarchy: 3-candle > 2-candle > 1-candle.
    """
    if not cdl_result:
        return "cdl_neutral"

    # Priority 1: 3-Candle Reversals (Highest Conviction)
    if cdl_result.get("morning_star"):
        return "cdl_morning_star"
    if cdl_result.get("evening_star"):
        return "cdl_evening_star"
        
    # Priority 2: 2-Candle Reversals
    if cdl_result.get("bullish_engulfing"):
        return "cdl_bullish_engulfing"
    if cdl_result.get("bearish_engulfing"):
        return "cdl_bearish_engulfing"
    if cdl_result.get("bullish_harami"):
        return "cdl_bullish_harami"
        
    # Priority 3: 1-Candle Signals
    if cdl_result.get("hammer"):
        return "cdl_hammer"
    if cdl_result.get("shooting_star"):
        return "cdl_shooting_star"
    if cdl_result.get("doji"):
        return "cdl_doji"
        
    return "cdl_neutral"

def extract_rsi_signal(rsi_value: float, macd_result: dict, ema_result: dict) -> str:
    """
    Interprets RSI in the context of trend signals from MACD and EMA.

    Context-aware logic:
        RSI > 70 in a confirmed uptrend (MACD bullish + EMA bullish)
        -> read as sustained momentum, NOT overbought reversal signal.
        This addresses the well-known RSI failure mode in strong trends.

    Args:
        rsi_value:   Float RSI value (0-100).
        macd_result: Output dict from compute_macd().
        ema_result:  Output dict from compute_ema_crossover().

    Returns:
        Signal key string (maps to SIGNAL_SCORES and SIGNAL_PHRASES in config).
    """
    if rsi_value is None:
        return "rsi_neutral"

    trend_confirmed = macd_result.get("macd_bullish", False) and ema_result.get("ema_bullish", False)

    if rsi_value <= RSI_OVERSOLD:
        return "rsi_oversold"

    elif rsi_value >= RSI_OVERBOUGHT:
        if trend_confirmed:
            # Strong trend — overbought RSI means momentum, not reversal
            # Treat same as bullish zone to avoid incorrectly penalising
            return "rsi_bullish"
        return "rsi_overbought"

    elif rsi_value >= RSI_BULLISH_ZONE:
        return "rsi_bullish"

    elif rsi_value <= RSI_BEARISH_ZONE:
        return "rsi_bearish"

    else:
        return "rsi_neutral"


def extract_macd_signal(macd_result: dict, rsi_value: float = None, obv_result: dict = None) -> str:
    """
    Context-aware MACD interpretation.
    
    Key addition: if MACD is bearish but histogram is IMPROVING (getting less
    negative) AND RSI/OBV show recovery, treat as early reversal, not sell signal.
    This catches the Jan27 scenario where MACD lagged a real uptrend by 1-2 weeks.
    """
    if macd_result.get("bullish_cross"):
        return "macd_bullish_cross"
    elif macd_result.get("bearish_cross"):
        return "macd_bearish_cross"
    elif macd_result.get("macd_bullish"):
        return "macd_bullish"
    
    # MACD is bearish — check if momentum is recovering
    # histogram improving = MACD line moving toward signal line from below
    histogram = macd_result.get("histogram", 0)
    # We need histogram trend — add this to compute_macd() output (see below)
    hist_improving = macd_result.get("histogram_improving", False)
    
    rsi_recovering = rsi_value is not None and rsi_value > 45
    obv_accumulating = obv_result is not None and obv_result.get("accumulation", False)
    
    # Early reversal: MACD still bearish but showing improvement + supporting signals
    if hist_improving and (rsi_recovering or obv_accumulating):
        return "macd_neutral"   # upgrade from bearish to neutral
    
    return "macd_bearish"


def extract_ema_signal(ema_result: dict) -> str:
    """
    Interprets EMA crossover output into a signal key.
    Prioritises fresh crosses; then uses current structure.
    """
    if ema_result.get("golden_cross"):
        return "ema_golden_cross"
    elif ema_result.get("death_cross"):
        return "ema_death_cross"
    elif ema_result.get("price_above_both"):
        return "ema_bullish"
    elif ema_result.get("price_below_both"):
        return "ema_bearish"
    return "ema_neutral"


def extract_obv_signal(obv_result: dict) -> str:
    """
    Interprets OBV trend into a signal key.
    Divergence signals take priority over simple direction signals.
    """
    if obv_result.get("bullish_divergence"):
        # OBV rising while price flat/falling — strong accumulation signal
        return "obv_accumulation"
    elif obv_result.get("bearish_divergence"):
        return "obv_distribution"
    elif obv_result.get("accumulation"):
        return "obv_accumulation"
    elif obv_result.get("distribution"):
        return "obv_distribution"
    return "obv_neutral"

def extract_sr_signal(sr_result: dict) -> str:
    """
    Passes through the S&R signal directly.
    The signal is already determined in compute_support_resistance().
    This function exists for consistency with the other extractors.
    """
    return sr_result.get("signal", "sr_neutral")


def extract_all_signals(rsi_value, macd_result, ema_result, obv_result, sr_result, cdl_result) -> dict:
    return {
        "rsi":       extract_rsi_signal(rsi_value, macd_result, ema_result),
        "macd":      extract_macd_signal(macd_result, rsi_value, obv_result),
        "ema":       extract_ema_signal(ema_result),
        "obv":       extract_obv_signal(obv_result),
        "sr":        extract_sr_signal(sr_result),
        "cdl":       extract_cdl_signal(cdl_result)
    }
