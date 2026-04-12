# =============================================================================
# data/data_fetcher.py
#
# Single responsibility: fetch OHLCV data, return a clean DataFrame.
# Nothing outside this file needs to know about Groww, HTTP, or auth.
# To swap data source later — only this file changes.
# =============================================================================

import os
import logging
from datetime import datetime, timedelta

import pandas as pd
from growwapi import GrowwAPI

import time
from collections import deque

from technical_agent.config import (
    TRADE_TYPE_DATA_CONFIG,
    MIN_DATA_POINTS,
    NIFTY500_CSV_PATH,
    REGIME_EMA,
    REGIME_LOOKBACK_DAYS
)

import yfinance as yf

logger = logging.getLogger(__name__)

def get_market_regime(end_date: str = None, trade_type: str = "swing") -> str:
    try:
        if end_date:
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        else:
            end_dt = datetime.now()

        lookback_days = REGIME_LOOKBACK_DAYS
        start_dt = end_dt - timedelta(days=lookback_days)

        df = yf.download(
            "^CRSLDX",
            start=start_dt.strftime("%Y-%m-%d"),
            end=(end_dt + timedelta(days=1)).strftime("%Y-%m-%d"),
            interval="1d",
            progress=False
        )

        if df is None or df.empty or len(df) < 30:
            return "neutral"

        df.columns = [col[0].lower() for col in df.columns]
        df = df[df["volume"] > 0].copy()

        close = df["close"]

        # Fast signal: 5-day rate of change — catches reversals early
        roc5 = (close.iloc[-1] - close.iloc[-5]) / close.iloc[-5] * 100

        # Medium signal: price vs 20-day SMA — where are we structurally?
        sma20 = close.rolling(20).mean()
        above_sma20 = close.iloc[-1] > sma20.iloc[-1]

        # Slow signal: original EMA crossover (kept for confirmation)
        ema_cfg = REGIME_EMA.get(trade_type, REGIME_EMA["swing"])
        fast, slow = ema_cfg["fast"], ema_cfg["slow"]
        ema_fast = close.ewm(span=fast, adjust=False).mean()
        ema_slow = close.ewm(span=slow, adjust=False).mean()
        ema_bullish = ema_fast.iloc[-1] > ema_slow.iloc[-1]

        # Vote: 2 out of 3 signals decide regime
        bull_votes = sum([roc5 > 1.0, above_sma20, ema_bullish])
        bear_votes = sum([roc5 < -1.0, not above_sma20, not ema_bullish])

        if bull_votes >= 2:
            regime = "bullish"
        elif bear_votes >= 2:
            regime = "bearish"
        else:
            regime = "neutral"

        logger.info(
            f"Market regime: {regime.upper()} "
            f"[ROC5={roc5:.1f}%  above_sma20={above_sma20}  ema_cross={ema_bullish}]"
        )
        return regime

    except Exception as e:
        logger.warning(f"get_market_regime failed: {e} — defaulting to neutral")
        return "neutral"

    
class _RateLimiter:

    """
    Sliding Window rate limiter.
    Tracks timesstamps of the last N calls and sleeps if we are about to
    exceed the per-minute limit of Groww (300/min)

    """
    def __init__(self, max_calls: int = 250, period: int = 60):
        self.max_calls = max_calls
        self.period = period
        self._calls = deque()
    
    def wait(self):
        now = time.monotonic()

        #Drop timestamps older than the window
        while self._calls and now - self._calls[0] > self.period:
            self._calls.popleft()
        
        if len(self._calls) >= self.max_calls:
            # We've hit the limit -- sleep untill the oldeest call falls out
            sleep_for = self.period - (now - self._calls[0]) + 0.1
            logger.info(f"Rate limiter: Sleeping {sleep_for:.1f}s to stay under limit...")
            time.sleep(sleep_for)
        
        self._calls.append(time.monotonic())


class GrowwDataFetcher:
    """
    Wraps the Groww API to deliver a normalised OHLCV DataFrame.

    Contract for callers — get_ohlcv() always returns:
        columns : [open, high, low, close, volume]
        index   : DatetimeIndex, Asia/Kolkata tz-naive, oldest -> newest
        dtypes  : float64
    """

    _EXCHANGE = GrowwAPI.EXCHANGE_NSE
    _SEGMENT  = GrowwAPI.SEGMENT_CASH
    _rate_limiter = _RateLimiter(max_calls = 280, period = 60)

    def __init__(self, api_key: str, secret: str):
        access_token = GrowwAPI.get_access_token(api_key=api_key, secret=secret)
        self._client = GrowwAPI(access_token)
        logger.info("GrowwDataFetcher: authenticated successfully.")

    def get_ohlcv(self, ticker: str, trade_type: str, end_date: str = None) -> pd.DataFrame:
        """
        Fetches historical OHLCV data for a single NSE ticker.

        Args:
            ticker:     NSE symbol e.g. "RELIANCE", "TCS"
            trade_type: "swing", "short", or "medium"

        Returns:
            Normalised DataFrame, or empty DataFrame on failure.
            Always check with is_valid_df() before passing to indicators.
        """
        if trade_type not in TRADE_TYPE_DATA_CONFIG:
            raise ValueError(
                f"Unknown trade_type '{trade_type}'. "
                f"Must be one of: {list(TRADE_TYPE_DATA_CONFIG.keys())}"
            )

        cfg        = TRADE_TYPE_DATA_CONFIG[trade_type]
        end_dt = datetime.strptime(end_date, "%Y-%m-%d") if end_date else datetime.now()
        start_dt   = end_dt - timedelta(days=cfg["lookback_days"])

        # Groww API expects "YYYY-MM-DD HH:MM:SS" with market hours
        start_time = start_dt.strftime("%Y-%m-%d") + " 09:15:00"
        end_time   = end_dt.strftime("%Y-%m-%d")   + " 15:30:00"

        logger.debug(f"Fetching {ticker} | {trade_type} | {start_time} -> {end_time}")

        MAX_RETRIES = 3
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                self._rate_limiter.wait()           # <- throttle before every call
                raw = self._client.get_historical_candle_data(
                    trading_symbol      = ticker,
                    exchange            = self._EXCHANGE,
                    segment             = self._SEGMENT,
                    start_time          = start_time,
                    end_time            = end_time,
                    interval_in_minutes = cfg["interval_in_minutes"],
                )
                return self._parse(raw, ticker)

            except Exception as e:
                msg = str(e)
                if "Rate limit" in msg or "rate limit" in msg:
                    wait = 60 * attempt   # back off: 60s, 120s, 180s
                    logger.warning(
                        f"{ticker}: rate limit on attempt {attempt}/{MAX_RETRIES}."
                        f" Waiting {wait}s before retry..."
                    )
                    time.sleep(wait)
                else:
                    logger.warning(f"{ticker}: fetch failed --{msg}")
                    return pd.DataFrame()
            
        logger.warning(f"{ticker}: failed after {MAX_RETRIES} retries --skipping.")
        return pd.DataFrame() 
    
    def get_ohlcv_daterange(self, ticker, start_dt, end_dt):
        MAX_RETRIES = 3

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                self._rate_limiter.wait()
                raw = self._client.get_historical_candle_data(
                    trading_symbol      = ticker,
                    exchange            = self._EXCHANGE,
                    segment             = self._SEGMENT,
                    interval_in_minutes = 1440,
                    start_time          = start_dt.strftime("%Y-%m-%d") + " 09:15:00",
                    end_time            = end_dt.strftime("%Y-%m-%d")   + " 15:30:00",
                )
                return self._parse(raw, ticker)

            except Exception as e:
                msg = str(e)
                if "Rate limit" in msg or "rate limit" in msg:
                    wait = 60 * attempt    # 60s, 120s, 180s
                    logger.warning(
                        f"{ticker}: rate limited on attempt {attempt}/{MAX_RETRIES}."
                        f" Waiting {wait}s before retry."
                    )
                    time.sleep(wait)
                else:
                    logger.warning(f"{ticker}: backtest fetch failed -- {msg}")
                    return pd.DataFrame()   # non-rate-limit error — don't retry

        logger.warning(f"{ticker}: failed after {MAX_RETRIES} retries -- skipping.")
        return pd.DataFrame()

    def _parse(self, raw: dict, ticker: str) -> pd.DataFrame:
        """
        Converts raw Groww JSON to normalised DataFrame.
        Handles both list-of-lists and list-of-dicts candle formats.
        """
        try:
            candles = raw.get("candles") or raw.get("data") or raw

            if not candles:
                logger.warning(f"{ticker}: empty candles in response.")
                return pd.DataFrame()

            if isinstance(candles[0], (list, tuple)):
                df = pd.DataFrame(
                    candles,
                    columns=["timestamp", "open", "high", "low", "close", "volume"]
                )
            elif isinstance(candles[0], dict):
                df = pd.DataFrame(candles)
                df.columns = [c.lower() for c in df.columns]
                df.rename(columns={
                    "ts": "timestamp", "time": "timestamp", "t": "timestamp",
                    "o": "open", "h": "high", "l": "low",
                    "c": "close", "v": "volume",
                }, inplace=True)
            else:
                logger.warning(f"{ticker}: unrecognised candle format.")
                return pd.DataFrame()

            # Normalise timestamp — Groww returns epoch ms or ISO string
            if pd.api.types.is_numeric_dtype(df["timestamp"]):
                df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
            else:
                df["timestamp"] = pd.to_datetime(df["timestamp"])

            df["timestamp"] = (
                df["timestamp"]
                .dt.tz_localize("UTC", ambiguous="infer", nonexistent="shift_forward")
                .dt.tz_convert("Asia/Kolkata")
                .dt.tz_localize(None)
            )

            df.set_index("timestamp", inplace=True)
            df.sort_index(inplace=True)

            for col in ["open", "high", "low", "close", "volume"]:
                df[col] = pd.to_numeric(df[col], errors="coerce")

            df.dropna(subset=["open", "high", "low", "close", "volume"], inplace=True)

            logger.debug(f"{ticker}: {len(df)} clean candles.")
            return df

        except Exception as e:
            logger.warning(f"{ticker}: parse failed -- {e}")
            return pd.DataFrame()


def load_nifty500_tickers(csv_path: str = NIFTY500_CSV_PATH) -> list:
    """
    Loads NSE tickers from Nifty 500 CSV from niftyindices.com.
    Download: https://www.niftyindices.com/IndexConstituents/ind_nifty500list.csv
    """
    if not os.path.exists(csv_path):
        raise FileNotFoundError(
            f"Nifty 500 CSV not found at '{csv_path}'.\n"
            f"Download from: https://www.niftyindices.com/IndexConstituents/ind_nifty500list.csv"
        )

    df = pd.read_csv(csv_path)

    if "Symbol" not in df.columns:
        raise KeyError(f"Expected 'Symbol' column. Found: {list(df.columns)}")

    tickers = df["Symbol"].dropna().str.strip().str.upper().tolist()
    logger.info(f"Loaded {len(tickers)} tickers from Nifty 500 CSV.")
    return tickers


def is_valid_df(df: pd.DataFrame, ticker: str, trade_type: str) -> bool:
    """
    Returns True only if df has enough candles for reliable indicators.
    Call this before passing any DataFrame to the indicator layer.
    """
    if df.empty:
        logger.warning(f"{ticker}: DataFrame is empty -- skipping.")
        return False

    required = MIN_DATA_POINTS[trade_type]
    if len(df) < required:
        logger.warning(
            f"{ticker}: only {len(df)} candles, need {required} for '{trade_type}' -- skipping."
        )
        return False

    return True
