# =============================================================================
# scoring/scorer.py
#
# Takes signal keys + trade type, applies weights, returns final score.
#
# Flow:
#   signal keys (strings)
#       -> SIGNAL_SCORES (config) maps each key to a sub-score (0-100)
#       -> WEIGHT_PROFILES (config) assigns weight per indicator per trade type
#       -> final_score = sum(sub_score * weight) for all indicators
#       -> normalise to 0-1 for output
#       -> attach label from SCORE_BANDS
#       -> build reasoning string from SIGNAL_PHRASES
# =============================================================================

import logging
from technical_agent.config import (
    SIGNAL_SCORES,
    WEIGHT_PROFILES,
    SCORE_BANDS,
    SIGNAL_PHRASES,
    STRONG_BUY_THRESHOLD
)

logger = logging.getLogger(__name__)


def compute_score(signals: dict, trade_type: str) -> dict:
    """
    Computes the final weighted technical score for one stock.

    Args:
        signals:    Dict of signal keys from signal_extractor.extract_all_signals().
                    Format: {"rsi": "rsi_bullish", "macd": "macd_bullish_cross", ...}
        trade_type: "swing", "short", or "medium" — selects weight profile.

    Returns:
        dict with keys:
            score_100   (float) raw weighted score 0-100
            score       (float) normalised score 0.0-1.0 (2 decimal places)
            label       (str)   "Strong Buy", "Buy", "Watch", "Avoid", "Strong Avoid"
            reasoning   (str)   human-readable summary of signals that fired
            signals     (dict)  the input signal keys (for transparency/debugging)
    """
    weights     = WEIGHT_PROFILES[trade_type]
    score_100   = 0.0
    
    # Safely get the signal key, defaulting to neutral if missing
    cdl_signal_key = signals.get("cdl", "cdl_neutral")
    
    # Grab the human-readable phrase using the signal_key (not the indicator name!)
    cdl_reasoning_raw = SIGNAL_PHRASES.get(cdl_signal_key, "No pattern")

    if trade_type == "medium":
        cdl_output = "N/A (Daily candlesticks ignored for medium-term horizons)"
    elif cdl_signal_key in ["cdl_neutral", "cdl_doji"]:
        cdl_output = "No actionable candlestick pattern present today."
    else:
        cdl_output = cdl_reasoning_raw

    # MATHEMATICAL CONFLUENCE CHECK
    # Only award candlestick points if price is actually at a key level
    sr_signal_key = signals.get("sr", "sr_neutral")
    
    # If we have a bullish candlestick, but we are NOT at support, erase the points
    if cdl_signal_key in ["cdl_morning_star", "cdl_bullish_engulfing", "cdl_hammer"]:
        if sr_signal_key != "sr_near_support":
            signals["cdl"] = "cdl_neutral" # Downgrade the signal
            cdl_output = "Bullish pattern detected, but ignored because price is in 'No Man's Land' (not at support)."
            
    # Do the same for bearish patterns at resistance
    elif cdl_signal_key in ["cdl_evening_star", "cdl_bearish_engulfing", "cdl_shooting_star"]:
        if sr_signal_key != "sr_near_resistance":
            signals["cdl"] = "cdl_neutral"
            cdl_output = "Bearish pattern detected, but ignored because price is not at resistance."

    for indicator, signal_key in signals.items():
        weight    = weights.get(indicator, 0)
        sub_score = SIGNAL_SCORES.get(signal_key, 50)  # default 50 (neutral) if key missing
        score_100 += sub_score * weight

    score_100 = round(score_100, 2)
    score     = round(score_100 / 100, 2)
    label     = _get_label(score_100)
    reasoning = _build_reasoning(signals)

    return {
        "score_100": score_100,
        "score":     score,
        "label":     label,
        "reasoning": reasoning,
        "cdl_reasoning": cdl_output,
        "signals":   signals,
    }


def _get_label(score_100: float) -> str:
    """Maps a 0-100 score to a human-readable label using SCORE_BANDS."""
    for low, high, label in SCORE_BANDS:
        if low <= score_100 <= high:
            return label
    return "Watch"


def _build_reasoning(signals: dict) -> str:
    """
    Builds a concise reasoning string from the signals that fired.
    Only includes non-neutral signals to keep the output clean.
    """
    neutral_signals = {
        "rsi_neutral", "macd_neutral", "ema_neutral", "obv_neutral", "sr_neutral", "cdl_neutral"
    }

    phrases = []
    for signal_key in signals.values():
        if signal_key not in neutral_signals:
            phrase = SIGNAL_PHRASES.get(signal_key)
            if phrase:
                phrases.append(phrase)

    if not phrases:
        return "No strong signals — neutral technical picture"

    return " | ".join(phrases)


def apply_regime_filter(score_res: dict, regime: str) -> dict:
    """
    Adjusts scores and labels based on market regime.

    Bullish / Neutral → no changes, trust all signals

    Bearish →
        score 0.70+  (strong Buy) → keep Buy, append regime note
        score 0.60-0.69 (weak Buy) → downgrade to Watch
        Watch / Avoid → unchanged
    """
    if regime != "bearish":
        return score_res

    score     = score_res["score"]
    label     = score_res["label"]
    reasoning = score_res["reasoning"]


    if label in ("Strong Buy", "Buy"):
        if label == "Strong Buy":
            # Always keep — highest conviction, keep in any market
            reasoning = reasoning + " | ⚠ Bearish market — strong setup retained"
        
        elif score >= STRONG_BUY_THRESHOLD:
            # score 0.70-0.79 → Buy but near Strong Buy territory — keep
            reasoning = reasoning + " | ⚠ Bearish market — high-conviction Buy retained"
        
        else:
            # score 0.60-0.69 → marginal Buy — downgrade to Watch
            label     = "Watch"
            reasoning = reasoning + " | ⚠ Bearish market — marginal Buy downgraded to Watch"

    return {
        **score_res,
        "score":     score,
        "score_100": round(score * 100, 1),
        "label":     label,
        "reasoning": reasoning,
    }