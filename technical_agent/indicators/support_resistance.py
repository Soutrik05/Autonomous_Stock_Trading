# =============================================================================
# indicators/support_resistance.py
#
# Support and Resistance detection using swing high/low method.
#
# APPROACH — Varsity swing high/low (Module 2, Chapter 11):
#   A swing low  = candle whose LOW  is lower than N candles on each side
#   A swing high = candle whose HIGH is higher than N candles on each side
#   Nearby levels (within CLUSTER_PCT%) are merged into a single zone.
#   Each zone is scored by how many times price tested it (strength).
#
# WHY THIS APPROACH:
#   - Pure price history, no ML, no prediction
#   - Levels are proven by actual price reactions, not formulas
#   - Naturally produces a stack of levels, not just one
#   - A broken support becomes resistance (and vice versa) — we handle this
#
# SIGNAL LOGIC:
#   near_support     → price within PROXIMITY_PCT% above nearest support
#                      stock hasn't moved yet, early entry opportunity
#   near_resistance  → price within PROXIMITY_PCT% below nearest resistance
#                      upside limited, caution on new entries
#   breakout         → price closed above resistance on this candle
#                      strong bullish — trend continuation likely
#   breakdown        → price closed below support on this candle
#                      bearish — next support level becomes the target
#   neutral          → price between levels, no strong S&R signal
#
# INTEGRATION:
#   - Called from agent.py alongside other indicators
#   - Returns dict consumed by signal_extractor.extract_sr_signal()
#   - Scores defined in config.SIGNAL_SCORES under sr_* keys
#   - Weight defined in config.WEIGHT_PROFILES under "sr" key
# =============================================================================

import logging
import numpy as np
import pandas as pd
from technical_agent.config import SR_SWING_WINDOW, SR_CLUSTER_PCT, SR_PROXIMITY_PCT, SR_MIN_TOUCHES_SUPPORT, SR_MIN_TOUCHES_RESISTANCE

logger = logging.getLogger(__name__)


def _find_swing_lows(df: pd.DataFrame, window: int) -> pd.Series:
    """
    Identifies swing lows — candles whose LOW is the lowest
    within `window` candles on each side.

    Uses pandas rolling min comparison for efficiency.
    Returns boolean Series — True where a swing low occurs.
    """
    low = df["low"]
    # A candle is a swing low if its low equals the rolling min
    # over [i-window .. i+window]
    rolling_min = low.rolling(window=2 * window + 1, center=True).min()
    return low == rolling_min


def _find_swing_highs(df: pd.DataFrame, window: int) -> pd.Series:
    """
    Identifies swing highs — candles whose HIGH is the highest
    within `window` candles on each side.
    """
    high = df["high"]
    rolling_max = high.rolling(window=2 * window + 1, center=True).max()
    return high == rolling_max


def _cluster_levels(levels: list, cluster_pct: float) -> list:
    """
    Merges price levels that are within cluster_pct% of each other
    into a single zone, weighted by touch count.

    Example: levels at 100, 101.2, 98.5 with cluster_pct=2.0
    → 100 and 101.2 are within 2% → merged to average 100.6
    → 98.5 is outside → kept separate

    Returns list of dicts:
        {"level": float, "touches": int, "type": "support"|"resistance"}
    """
    if not levels:
        return []

    # Sort by price
    levels = sorted(levels, key=lambda x: x["level"])
    clusters = []
    current = levels[0].copy()

    for lvl in levels[1:]:
        # Check if this level is within cluster_pct% of current cluster
        pct_diff = abs(lvl["level"] - current["level"]) / current["level"] * 100
        if pct_diff <= cluster_pct:
            # Merge — weighted average by touches
            total_touches = current["touches"] + lvl["touches"]
            current["level"] = (
                (current["level"] * current["touches"] +
                 lvl["level"] * lvl["touches"]) / total_touches
            )
            current["touches"] = total_touches
        else:
            clusters.append(current)
            current = lvl.copy()

    clusters.append(current)
    return clusters


def compute_support_resistance(df: pd.DataFrame) -> dict:
    """
    Detects support and resistance levels and generates a trading signal.

    Args:
        df: OHLCV DataFrame. Should have at least 100 candles for
            reliable level detection. 200 is ideal.

    Returns:
        dict with keys:
            signal          (str)   one of: sr_near_support, sr_near_resistance,
                                    sr_breakout, sr_breakdown, sr_neutral
            current_price   (float) latest close
            nearest_support (float|None) strongest support below current price
            nearest_resistance (float|None) strongest resistance above current price
            support_strength   (int)  number of times nearest support was tested
            resistance_strength (int) number of times nearest resistance was tested
            all_levels      (list)  all detected levels for debugging/display
            proximity_pct   (float) how close price is to nearest level (%)
    """
    if len(df) < SR_SWING_WINDOW * 2 + 5:
        logger.debug("S&R: insufficient data for detection")
        return _neutral_result(df)

    current_price = float(df["close"].iloc[-1])
    prev_close    = float(df["close"].iloc[-2])

    # ── Detect swing points ───────────────────────────────────────────
    swing_low_mask  = _find_swing_lows(df, SR_SWING_WINDOW)
    swing_high_mask = _find_swing_highs(df, SR_SWING_WINDOW)

    # Collect raw levels with touch count = 1 initially
    raw_levels = []

    for idx in df[swing_low_mask].index:
        raw_levels.append({
            "level":   float(df.loc[idx, "low"]),
            "touches": 1,
            "type":    "support",
        })

    for idx in df[swing_high_mask].index:
        raw_levels.append({
            "level":   float(df.loc[idx, "high"]),
            "touches": 1,
            "type":    "resistance",
        })

    if not raw_levels:
        return _neutral_result(df)

    # ── Cluster nearby levels ─────────────────────────────────────────
    # Cluster support and resistance separately to avoid mixing types
    support_raw    = [l for l in raw_levels if l["type"] == "support"]
    resistance_raw = [l for l in raw_levels if l["type"] == "resistance"]

    supports    = _cluster_levels(support_raw,    SR_CLUSTER_PCT)
    resistances = _cluster_levels(resistance_raw, SR_CLUSTER_PCT)

    # Filter by minimum touches — weak levels are noise
    supports    = [l for l in supports    if l["touches"] >= SR_MIN_TOUCHES_SUPPORT]
    resistances = [l for l in resistances if l["touches"] >= SR_MIN_TOUCHES_RESISTANCE]

    all_levels = supports + resistances

    # ── Find nearest levels to current price ─────────────────────────
    # Support  = strongest level BELOW current price
    # Resistance = strongest level ABOVE current price
    supports_below    = [l for l in supports    if l["level"] < current_price]
    resistances_above = [l for l in resistances if l["level"] > current_price]

    # Nearest = closest in price; if tie, prefer more touches (stronger)
    nearest_support = (
        max(supports_below, key=lambda x: (x["level"], x["touches"]))
        if supports_below else None
    )
    nearest_resistance = (
        min(resistances_above, key=lambda x: (-x["level"], -x["touches"]))
        if resistances_above else None
    )

    # ── Determine signal ─────────────────────────────────────────────
    signal          = "sr_neutral"
    proximity_pct   = None

    # Check for breakout: previous close was below resistance,
    # current close is above it — confirmed breakout
    if nearest_resistance is None and resistances_above == []:
        # Price is above ALL resistance levels — very strong breakout
        # Find the highest resistance that price just broke through
        all_resistance_below = [l for l in resistances if l["level"] < current_price]
        if all_resistance_below:
            just_broken = max(all_resistance_below, key=lambda x: x["level"])
            if prev_close < just_broken["level"] <= current_price:
                signal = "sr_breakout"
                proximity_pct = round(
                    (current_price - just_broken["level"]) / just_broken["level"] * 100, 2
                )

    # Check for breakdown: previous close was above support,
    # current close is below it — confirmed breakdown
    if signal == "sr_neutral" and nearest_support is None and supports_below == []:
        all_support_above = [l for l in supports if l["level"] > current_price]
        if all_support_above:
            just_broken = min(all_support_above, key=lambda x: x["level"])
            if prev_close > just_broken["level"] >= current_price:
                signal = "sr_breakdown"
                proximity_pct = round(
                    (just_broken["level"] - current_price) / current_price * 100, 2
                )

    # Check proximity to nearest resistance (above)
    if signal == "sr_neutral" and nearest_resistance:
        dist_pct = (nearest_resistance["level"] - current_price) / current_price * 100
        if dist_pct <= SR_PROXIMITY_PCT:
            signal        = "sr_near_resistance"
            proximity_pct = round(dist_pct, 2)

    # Check proximity to nearest support (below) — takes priority over resistance
    # because near_support is an entry signal, near_resistance is a caution signal
    if nearest_support:
        dist_pct = (current_price - nearest_support["level"]) / nearest_support["level"] * 100
        if dist_pct <= SR_PROXIMITY_PCT:
            signal        = "sr_near_support"
            proximity_pct = round(dist_pct, 2)

    return {
        "signal":               signal,
        "current_price":        round(current_price, 2),
        "nearest_support":      round(nearest_support["level"], 2)    if nearest_support    else None,
        "nearest_resistance":   round(nearest_resistance["level"], 2) if nearest_resistance else None,
        "support_strength":     nearest_support["touches"]    if nearest_support    else 0,
        "resistance_strength":  nearest_resistance["touches"] if nearest_resistance else 0,
        "all_levels":           all_levels,
        "proximity_pct":        proximity_pct,
    }


def _neutral_result(df: pd.DataFrame) -> dict:
    """Returns a safe neutral result when detection is not possible."""
    return {
        "signal":               "sr_neutral",
        "current_price":        round(float(df["close"].iloc[-1]), 2) if not df.empty else None,
        "nearest_support":      None,
        "nearest_resistance":   None,
        "support_strength":     0,
        "resistance_strength":  0,
        "all_levels":           [],
        "proximity_pct":        None,
    }
