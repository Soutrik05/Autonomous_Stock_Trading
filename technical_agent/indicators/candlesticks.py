# =============================================================================
# technical_agent/candlesticks.py
# =============================================================================
import pandas as pd

def get_latest_candlestick_patterns(df: pd.DataFrame) -> dict:
    """
    Scans the latest data for Varsity high-probability candlestick patterns.
    Uses dynamic volatility (10-day average body) and short-term trend context 
    to filter out fake signals.
    """

    # SAFETY NET 1: Ensure enough data exists for a 10-day rolling average
    if df is None or len(df) < 15:
        return {} 
        
    # SAFETY NET 2: Drop random missing data from the API
    df = df.dropna(subset=['open', 'high', 'low', 'close', 'volume'])
    
    # SAFETY NET 3: Prevent Zero-Division errors on mathematically flat days
    # If a stock is halted or has zero volume, average body could be exactly 0.0
    bodies = abs(df['close'] - df['open'])
    avg_body = bodies.rolling(10).mean().iloc[-1]
    
    if avg_body == 0.0:
        avg_body = 0.01
    if len(df) < 15:
        return {}
    
    # 1. Grab the last 3 candles for pattern matching
    c1 = df.iloc[-3] # 2 days ago
    c2 = df.iloc[-2] # Yesterday
    c3 = df.iloc[-1] # Today
    
    # 2. Calculate Dynamic Volatility (Average body size over 10 days)
    # This prevents flagging tiny, meaningless candles in low-volume markets
    bodies = abs(df['close'] - df['open'])
    avg_body = bodies.rolling(10).mean().iloc[-1]

    avg_volume = df['volume'].rolling(10).mean().iloc[-1]

    # Current candle metrics
    c3_vol = c3['volume']

    # Define what constitutes a "Volume Surge" (e.g., 20% above the 10-day average)
    high_volume_surge = c3_vol > (1.2 * avg_volume)

    # Current candle metrics
    c3_body = abs(c3['close'] - c3['open'])
    c3_range = c3['high'] - c3['low']
    c3_lower_wick = min(c3['open'], c3['close']) - c3['low']
    c3_upper_wick = c3['high'] - max(c3['open'], c3['close'])
    
    # 3. Short-Term Trend Context (Looking back 4 days)
    # A reversal pattern is only valid if it's reversing something!
    is_short_term_downtrend = c3['close'] < df.iloc[-5]['close']
    is_short_term_uptrend   = c3['close'] > df.iloc[-5]['close']

    # =========================================================================
    # SINGLE CANDLE PATTERNS
    # =========================================================================
    
    # Doji: Opening and closing prices are virtually identical (indecision)
    is_doji = c3_body <= (0.1 * avg_body)

    # Hammer: Must be in a downtrend. Long lower wick, small body.
    hammer = (
        is_short_term_downtrend and 
        (c3_range > 0) and 
        (c3_lower_wick >= 2 * c3_body) and 
        (c3_upper_wick <= 0.2 * c3_body) # Stricter wick rule
    )
    
    # Shooting Star: Must be in an uptrend. Long upper wick, small body.
    shooting_star = (
        is_short_term_uptrend and 
        (c3_range > 0) and 
        (c3_upper_wick >= 2 * c3_body) and 
        (c3_lower_wick <= 0.2 * c3_body)
    )

    # =========================================================================
    # TWO-CANDLE PATTERNS
    # =========================================================================
    
    c2_body = abs(c2['close'] - c2['open'])

    # Bullish Engulfing: Must be in downtrend. Big green body covers small red body.
    bullish_engulfing = (
        is_short_term_downtrend and
        (c2['close'] < c2['open']) and
        (c3['close'] > c3['open']) and
        (c3_body > avg_body) and
        (c3['open'] <= c2['close']) and 
        (c3['close'] >= c2['open']) and
        high_volume_surge
    )

    # Bearish Engulfing: Must be in uptrend. Big red covers small green.
    bearish_engulfing = (
        is_short_term_uptrend and
        (c2['close'] > c2['open']) and # Yesterday Green
        (c3['close'] < c3['open']) and # Today Red
        (c3_body > avg_body) and
        (c3['open'] >= c2['close']) and 
        (c3['close'] <= c2['open'])
    )

    # Bullish Harami (Inside Bar): Breakout contraction. 
    # Yesterday big red, today small green perfectly inside yesterday's body.
    bullish_harami = (
        is_short_term_downtrend and
        (c2['close'] < c2['open']) and
        (c3['close'] > c3['open']) and
        (c3['open'] > c2['close']) and 
        (c3['close'] < c2['open'])
    )

    # =========================================================================
    # THREE-CANDLE PATTERNS (The strongest Varsity signals)
    # =========================================================================
    
    # Morning Star: Big Red -> Gap Down Doji/Small -> Big Green pushing into Red's body
    morning_star = (
        is_short_term_downtrend and
        (c1['close'] < c1['open']) and (abs(c1['close']-c1['open']) > avg_body) and # Day 1: Strong Red
        (c2_body < 0.3 * avg_body) and # Day 2: Indecision/Doji
        (c3['close'] > c3['open']) and (c3_body > avg_body) and # Day 3: Strong Green
        (c3['close'] > (c1['open'] + c1['close']) / 2) # Must close above 50% of Day 1's red body
    )

    # Evening Star: Big Green -> Gap Up Doji/Small -> Big Red pushing into Green's body
    evening_star = (
        is_short_term_uptrend and
        (c1['close'] > c1['open']) and (abs(c1['close']-c1['open']) > avg_body) and # Day 1: Strong Green
        (c2_body < 0.3 * avg_body) and # Day 2: Indecision
        (c3['close'] < c3['open']) and (c3_body > avg_body) and # Day 3: Strong Red
        (c3['close'] < (c1['open'] + c1['close']) / 2) # Must close below 50% of Day 1's green body
    )

    return {
        "morning_star": bool(morning_star),
        "evening_star": bool(evening_star),
        "bullish_engulfing": bool(bullish_engulfing),
        "bearish_engulfing": bool(bearish_engulfing),
        "bullish_harami": bool(bullish_harami),
        "hammer": bool(hammer),
        "shooting_star": bool(shooting_star),
        "doji": bool(is_doji)
    }