# =============================================================================
# config.py
# Single source of truth for all constants, thresholds, and parameters.
# No logic lives here — only data. Tune this file during backtesting.
# =============================================================================

# -----------------------------------------------------------------------------
# TRADE TYPE DATA CONFIG
# Drives data_fetcher.py — interval and lookback per trade type.
# NSE trades ~6.25 hrs/day but we use daily candles for all types (simpler,
# consistent, and EMA crossovers are more meaningful on daily candles).
# -----------------------------------------------------------------------------

import os

TRADE_TYPE_DATA_CONFIG = {
    "swing": {
        "interval_in_minutes": 1440,  # daily candles
        "lookback_days": 50,   
    },
    "short": {
        "interval_in_minutes": 1440,
        "lookback_days": 100,
    },
    "medium": {
        "interval_in_minutes": 1440,
        "lookback_days": 365,
    },
}

# Minimum trading day candles required before trusting any indicator.
# Set per trade type based on the longest EMA period used.
# Buffer added on top of the EMA period to ensure stable values.
MIN_DATA_POINTS = {
    "swing":      30,   # 21 EMA + 9 buffer
    "short":     60,   # 50 EMA + 10 buffer
    "medium": 230,  # 200 EMA + 30 buffer
}

# Path to Nifty 500 CSV from niftyindices.com
# Column used: 'Symbol' — NSE tickers, directly compatible with Groww API
NIFTY500_CSV_PATH = os.path.join(os.path.dirname(__file__), "data", "nifty500_constituents.csv")

# -----------------------------------------------------------------------------
# INDICATOR PARAMETERS — per trade type where they differ
# -----------------------------------------------------------------------------

# RSI — same period across all trade types (Wilder's original)
RSI_PERIOD = 14

# MACD — scaled up for positional to avoid excessive crossovers on long holds
MACD_PARAMS = {
    "swing":      {"fast": 12, "slow": 26, "signal": 9},
    "short":     {"fast": 12, "slow": 26, "signal": 9},
    "medium": {"fast": 19, "slow": 39, "signal": 9},
}

# EMA crossover pairs — timeframe-appropriate for each trade type
# Swing:      9/21   — catches short-term momentum shifts (1-2 weeks)
# Short:     25/50  — medium-term trend changes (4-8 weeks)
# Medium: 50/100 — structural long-term trend (6+ months)
EMA_PAIRS = {
    "swing":      {"short": 9,  "long": 21},
    "short":     {"short": 25, "long": 50},
    "medium": {"short": 50, "long": 200},
}


# OBV trend lookback — how many candles to measure OBV direction over
OBV_TREND_LOOKBACK = 10

# Support & Resistance
SR_SWING_WINDOW  = 5      # candles on each side to qualify as swing point
                           # 5 means a swing low must be lowest in 11-candle window
SR_CLUSTER_PCT   = 1.5    # levels within 1.5% of each other → same zone
SR_PROXIMITY_PCT = 2.0    # price within 2% of a level → "near" signal
SR_MIN_TOUCHES_SUPPORT    = 2   # support must be tested twice — proven floor
SR_MIN_TOUCHES_RESISTANCE = 1   # resistance can be single-touch — unvisited highs are valid

# -----------------------------------------------------------------------------
# SIGNAL THRESHOLDS
# Used by signal_extractor.py to convert raw values → categorical signals.
# -----------------------------------------------------------------------------

# RSI thresholds
RSI_OVERSOLD     = 30   # below → bullish (oversold, potential bounce)
RSI_OVERBOUGHT   = 70   # above → bearish (overbought, potential reversal)
RSI_BULLISH_ZONE = 55   # 55–70 → mild bullish momentum
RSI_BEARISH_ZONE = 45   # 30–45 → mild bearish momentum


# -----------------------------------------------------------------------------
# SCORING WEIGHTS
# 5 indicators, must sum to 1.0 per trade type.
# Updated 3 tier weight logic
# -----------------------------------------------------------------------------
WEIGHT_PROFILES = {
    "swing": {
        # Tier 1 — Setup (40%): Is there a valid level here?
        "cdl":   0.20,
        "sr":    0.20,

        # Tier 2 — Trend (35%): Is the direction supporting it?
        "ema":   0.20,
        "obv":   0.15,

        # Tier 3 — Momentum (25%): Is now the right moment?
        "macd":  0.15,
        "rsi":   0.10,
    },
    "short": {
        "cdl" :  0.15,
        "sr":    0.20,
        "ema":   0.25,
        "obv":   0.15,
        "macd":  0.15,
        "rsi":   0.10,
    },
    "medium": {
        "cdl":   0.10,   
        "sr":    0.20,
        "ema":   0.30,   # trend matters more over longer holds
        "obv":   0.20,
        "macd":  0.15,
        "rsi":   0.05,   # RSI less relevant over 3-6 month holds
    },
}

# Sanity check — fails loudly at import if weights don't sum to 1.0
for _profile, _weights in WEIGHT_PROFILES.items():
    _total = sum(_weights.values())
    assert abs(_total - 1.0) < 1e-9, (
        f"Weights for '{_profile}' sum to {_total:.4f} — must be exactly 1.0"
    )

# -----------------------------------------------------------------------------
# SIGNAL SCORES
# Each indicator returns a signal key. These map signal keys → sub-scores (0–100).
# The scorer multiplies each sub-score by its weight to get the final score.
#
# Design principle: neutral = 50, bullish > 50, bearish < 50.
# Strong signals push toward 0 or 100.
# -----------------------------------------------------------------------------
SIGNAL_SCORES = {
    # RSI
    "rsi_oversold":    85,   # strong bullish — oversold bounce likely
    "rsi_bullish":     65,   # mild bullish — momentum building
    "rsi_neutral":     50,   # no edge
    "rsi_bearish":     35,   # mild bearish
    "rsi_overbought":  15,   # strong bearish — but note: in strong trends, treat carefully

    # MACD
    "macd_bullish_cross": 90,  # crossover just happened — strongest signal
    "macd_bullish":       65,  # MACD above signal, no fresh cross
    "macd_neutral":       50,
    "macd_bearish":       35,
    "macd_bearish_cross": 10,  # crossunder just happened

    # EMA crossover
    "ema_golden_cross":    90,  # 50 crossed above 200 — very strong
    "ema_bullish":         65,  # short EMA above long EMA
    "ema_neutral":         50,
    "ema_bearish":         35,
    "ema_death_cross":     10,

    # Support & Resistance
    "sr_near_support":    80,   # price at support, hasn't moved yet — early entry
    "sr_near_resistance": 30,   # price at resistance — limited upside, caution
    "sr_breakout":        90,   # price just closed above resistance — strong signal
    "sr_breakdown":       10,   # price just closed below support — avoid
    "sr_neutral":         50,   # between levels — no S&R edge

    # Candle Stick Patterns
    # (3-Candle Patterns - Highest Conviction)
    "cdl_morning_star":      95,  # Textbook bullish reversal at support
    "cdl_evening_star":      15,  # Textbook bearish reversal at resistance

    # (2-Candle Patterns - High Conviction)
    "cdl_bullish_engulfing": 85,  # Strong buyer takeover
    "cdl_bearish_engulfing": 25,  # Strong seller takeover
    "cdl_bullish_harami":    75,  # Volatility contraction, potential upside breakout

    # (1-Candle Patterns - Medium Conviction)
    "cdl_hammer":            70,  # Intraday rejection of lower prices
    "cdl_shooting_star":     30,  # Intraday rejection of higher prices
    "cdl_doji":              50,  # Indecision
    "cdl_neutral":           50,  # No clear pattern
}

# -----------------------------------------------------------------------------
# REASONING PHRASES
# Human-readable strings for each signal. Used in final JSON output.
# -----------------------------------------------------------------------------
SIGNAL_PHRASES = {
    "rsi_oversold":       "RSI oversold — potential reversal upward",
    "rsi_bullish":        "RSI in bullish momentum zone",
    "rsi_neutral":        "RSI neutral — no momentum signal",
    "rsi_bearish":        "RSI in bearish momentum zone",
    "rsi_overbought":     "RSI overbought — monitor for reversal or sustained trend",

    "macd_bullish_cross": "MACD bullish crossover — strong entry signal",
    "macd_bullish":       "MACD above signal line — upward momentum",
    "macd_neutral":       "MACD flat — no momentum signal",
    "macd_bearish":       "MACD below signal line — downward momentum",
    "macd_bearish_cross": "MACD bearish crossover — exit signal",

    "ema_golden_cross":   "Golden Cross — short EMA crossed above long EMA",
    "ema_bullish":        "Short EMA above long EMA — bullish trend structure",
    "ema_neutral":        "EMAs converging — no clear trend",
    "ema_bearish":        "Short EMA below long EMA — bearish trend structure",
    "ema_death_cross":    "Death Cross — short EMA crossed below long EMA",

    "obv_accumulation":   "OBV rising — volume confirms upward move",
    "obv_neutral":        "OBV flat — no volume conviction",
    "obv_distribution":   "OBV falling — volume confirms downward pressure",

    "sr_near_support":    "Price at support zone — potential bounce entry",
    "sr_near_resistance": "Price approaching resistance — limited upside",
    "sr_breakout":        "Breakout above resistance — trend continuation signal",
    "sr_breakdown":       "Breakdown below support — high risk, avoid",
    "sr_neutral":         "Price between S&R levels — no level signal",

    "cdl_morning_star":      "Morning Star formed — high-conviction 3-day bullish reversal",
    "cdl_evening_star":      "Evening Star formed — high-conviction 3-day bearish reversal",
    "cdl_bullish_engulfing": "Bullish Engulfing — buyers overwhelmed sellers on high relative volatility",
    "cdl_bearish_engulfing": "Bearish Engulfing — sellers overwhelmed buyers on high relative volatility",
    "cdl_bullish_harami":    "Bullish Harami (Inside Bar) — downward momentum halting, potential reversal",
    "cdl_hammer":            "Hammer candle — strong intraday rejection of lower prices",
    "cdl_shooting_star":     "Shooting Star — strong intraday rejection of higher prices",
    "cdl_doji":              "Doji candle — market indecision, waiting for trend confirmation",
    "cdl_neutral":           "Normal price action — no distinct candlestick pattern",
}

# -----------------------------------------------------------------------------
# SCORE BANDS — label attached to final 0–100 score in JSON output
# -----------------------------------------------------------------------------
SCORE_BANDS = [
    (80, 100, "Strong Buy"),
    (60,  79, "Buy"),
    (40,  59, "Watch"),
    (20,  39, "Avoid"),
    (0,   19, "Strong Avoid"),
]

# Market Regime Filter Strong Buy Threshold 
STRONG_BUY_THRESHOLD = 0.70

# Market Regime EMA periods per trade type
REGIME_EMA = {
    "swing":      {"fast": 9,  "slow": 21},
    "short":      {"fast": 20, "slow": 50},
    "medium":     {"fast": 50, "slow": 100},
}
REGIME_LOOKBACK_DAYS = 120

# Minimum Score required out of 1.0 for each Risk Profile to pass technical analysis.
RISK_PROFILE_THRESHOLDS = {
    "low":      0.70,
    "medium":   0.60,
    "high":     0.50
}

