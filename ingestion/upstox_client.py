"""
Authenticated Upstox client wrapping the candle, quote, VIX and holiday endpoints confirmed
working in docs/upstox_findings.md. Every request goes through the injected rate limiter and
retries on 429/5xx with exponential backoff. The access token is read from the
UPSTOX_ANALYTICS_TOKEN environment variable and is never printed, logged or returned.
See Plan_v3 §1.1.
"""
import os
import time
from urllib.parse import quote
from typing import Dict, List, Optional

import requests

from core.rate_limiter import UpstoxRateLimiter
from settings import settings

RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


class UpstoxAPIError(Exception):
    """Raised when a request fails after exhausting all retries, or on a non-retryable error.
    Never includes the Authorization header or token value."""


class UpstoxClient:
    def __init__(
        self,
        token: Optional[str] = None,
        rate_limiter: Optional[UpstoxRateLimiter] = None,
        base_url: str = None,
        max_retries: int = None,
        backoff_base_sec: float = 1.0,
        session: Optional[requests.Session] = None,
        sleep_func=time.sleep,
    ):
        self._token = token if token is not None else os.environ.get("UPSTOX_ANALYTICS_TOKEN", "")
        self._rate_limiter = rate_limiter or UpstoxRateLimiter()
        self._base_url = base_url or settings.UPSTOX_BASE_URL
        self._max_retries = max_retries if max_retries is not None else settings.INGESTION_RETRY_COUNT
        self._backoff_base_sec = backoff_base_sec
        self._session = session or requests.Session()
        self._sleep = sleep_func

    def _request(self, method: str, path: str, params: dict = None) -> dict:
        """Makes one logical request, retrying on 429/5xx up to `max_retries` times with
        exponential backoff. Raises UpstoxAPIError on a non-retryable error or after the last
        retry is exhausted."""
        url = f"{self._base_url}{path}"
        headers = {"Authorization": f"Bearer {self._token}", "Accept": "application/json"}
        attempt = 0
        while True:
            self._rate_limiter.acquire()
            resp = self._session.request(method, url, headers=headers, params=params, timeout=20)
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code not in RETRYABLE_STATUS_CODES or attempt >= self._max_retries:
                raise UpstoxAPIError(f"{method} {path} failed with status {resp.status_code}")
            self._sleep(self._backoff_base_sec * (2 ** attempt))
            attempt += 1

    def get_daily_candles(self, instrument_key: str, from_date: str, to_date: str) -> List[list]:
        """Returns the raw candle rows: [timestamp, open, high, low, close, volume, open_interest]."""
        path = f"/v2/historical-candle/{quote(instrument_key, safe='')}/day/{to_date}/{from_date}"
        body = self._request("GET", path)
        return body.get("data", {}).get("candles", [])

    def get_quotes(self, instrument_keys: List[str], batch_size: int = None) -> Dict[str, dict]:
        """Returns {instrument key (as 'EXCHANGE:SYMBOL'): quote dict}, batching instrument_key
        into groups of `batch_size` (default settings.MARKET_QUOTE_BATCH_SIZE) per call."""
        batch_size = batch_size or settings.MARKET_QUOTE_BATCH_SIZE
        merged: Dict[str, dict] = {}
        for start in range(0, len(instrument_keys), batch_size):
            batch = instrument_keys[start : start + batch_size]
            body = self._request(
                "GET", "/v2/market-quote/quotes", params={"instrument_key": ",".join(batch)}
            )
            merged.update(body.get("data", {}))
        return merged

    def get_holidays(self) -> List[dict]:
        """Returns the exchange holiday list: [{date, description, holiday_type,
        closed_exchanges, open_exchanges}, ...]."""
        body = self._request("GET", "/v2/market/holidays")
        return body.get("data", [])

    def get_india_vix(self) -> Optional[dict]:
        """Returns the India VIX quote dict (same shape as an equity quote), or None if missing."""
        quotes = self.get_quotes(["NSE_INDEX|India VIX"])
        return quotes.get("NSE_INDEX:India VIX")
