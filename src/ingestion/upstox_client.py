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

import requests

from core.config import settings
from core.rate_limiter import UpstoxRateLimiter

RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


class UpstoxAPIError(Exception):
    """Raised when a request fails after exhausting all retries, or on a non-retryable error.
    Never includes the Authorization header or token value."""


class UpstoxClient:
    def __init__(
        self,
        token: str | None = None,
        rate_limiter: UpstoxRateLimiter | None = None,
        base_url: str = None,
        max_retries: int = None,
        backoff_base_sec: float = 1.0,
        session: requests.Session | None = None,
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
            self._sleep(self._backoff_base_sec * (2**attempt))
            attempt += 1

    def get_daily_candles(self, instrument_key: str, from_date: str, to_date: str) -> list[list]:
        """Returns the raw candle rows: [timestamp, open, high, low, close, volume, open_interest]."""
        path = f"/v3/historical-candle/{quote(instrument_key, safe='')}/days/1/{to_date}/{from_date}"
        body = self._request("GET", path)
        return (body.get("data") or {}).get("candles") or []

    def get_intraday_candles(
        self, instrument_key: str, interval_minutes: int, from_date: str, to_date: str
    ) -> list[list]:
        """Returns raw intraday candle rows: [timestamp, open, high, low, close, volume, open_interest].
        Upstox API supports interval_minutes=1, 30, etc. Chunking is handled by caller."""
        path = (
            f"/v3/historical-candle/{quote(instrument_key, safe='')}/minutes/{interval_minutes}/{to_date}/{from_date}"
        )
        body = self._request("GET", path)
        return (body.get("data") or {}).get("candles") or []

    def get_intraday_daily_candle(self, instrument_key: str) -> list[list]:
        """Returns current-day daily candle rows from V3 intraday: [[timestamp, open, high, low, close, volume, open_interest]]."""
        path = f"/v3/historical-candle/intraday/{quote(instrument_key, safe='')}/days/1"
        body = self._request("GET", path)
        return (body.get("data") or {}).get("candles") or []

    def get_quotes(self, instrument_keys: list[str], batch_size: int = None) -> dict[str, dict]:
        """Returns {instrument key (as 'EXCHANGE:SYMBOL'): quote dict}, batching instrument_key
        into groups of `batch_size` (default settings.MARKET_QUOTE_BATCH_SIZE) per call via V3 quotes."""
        batch_size = batch_size or settings.MARKET_QUOTE_BATCH_SIZE
        merged: dict[str, dict] = {}
        for start in range(0, len(instrument_keys), batch_size):
            batch = instrument_keys[start : start + batch_size]
            body = self._request("GET", "/v3/market-quote/quotes", params={"instrument_key": ",".join(batch)})
            merged.update(body.get("data", {}))
        return merged

    def get_holidays(self) -> list[dict]:
        """Returns the exchange holiday list: [{date, description, holiday_type,
        closed_exchanges, open_exchanges}, ...]."""
        body = self._request("GET", "/v2/market/holidays")
        return body.get("data", [])

    def get_india_vix(self) -> dict | None:
        """Returns the India VIX quote dict (same shape as an equity quote), or None if missing."""
        quotes = self.get_quotes(["NSE_INDEX|India VIX"])
        return quotes.get("NSE_INDEX:India VIX")

    def get_key_ratios(self, isin: str) -> list[dict]:
        """Returns list of key ratios: [{name, company_value, sector_value}, ...] for ISIN."""
        path = f"/v2/fundamentals/{quote(isin, safe='')}/key-ratios"
        body = self._request("GET", path)
        return body.get("data", [])

    def get_income_statement(self, isin: str, time_period: str = "yearly") -> dict:
        """Returns income statement dict: {income_statement: [...], full_statement: [...]}.
        time_period can be 'yearly' or 'quarterly'."""
        path = f"/v2/fundamentals/{quote(isin, safe='')}/income-statement"
        params = {"type": "consolidated", "time_period": time_period, "fs": "true"}
        body = self._request("GET", path, params=params)
        return body.get("data", {})

    def get_balance_sheet(self, isin: str) -> dict:
        """Returns consolidated annual balance sheet dict: {history: [...], full_statement: [...]}.
        Note: Upstox does not offer quarterly balance sheets."""
        path = f"/v2/fundamentals/{quote(isin, safe='')}/balance-sheet"
        params = {"type": "consolidated", "fs": "true"}
        body = self._request("GET", path, params=params)
        return body.get("data", {})

    def get_cash_flow(self, isin: str) -> dict:
        """Returns consolidated annual cash flow dict: {cash_flow: [...], full_statement: [...]}.
        Note: Upstox does not offer quarterly cash flow statements."""
        path = f"/v2/fundamentals/{quote(isin, safe='')}/cash-flow"
        params = {"type": "consolidated", "fs": "true"}
        body = self._request("GET", path, params=params)
        return body.get("data", {})

    def get_share_holdings(self, isin: str) -> list[dict]:
        """Returns quarterly shareholding breakdown list: [{category, history: [...]}, ...]."""
        path = f"/v2/fundamentals/{quote(isin, safe='')}/share-holdings"
        body = self._request("GET", path)
        return body.get("data", [])

    def get_corporate_actions(self, isin: str) -> list[dict]:
        """Returns list of corporate action events: [{name, expiry_date, amount, ratio, event_details}, ...]."""
        path = f"/v2/fundamentals/{quote(isin, safe='')}/corporate-actions"
        body = self._request("GET", path)
        return body.get("data", []) or []

    def get_fii_data(self, data_type: str = "NSE_EQ|CASH", interval: str = "1D") -> list[dict]:
        """Returns list of FII activity records: [{time_stamp, buy_amount, sell_amount, ...}]."""
        params = {"data_type": data_type, "interval": interval}
        body = self._request("GET", "/v2/market/fii", params=params)
        return (body.get("data") or {}).get(data_type, [])

    def get_dii_data(self, data_type: str = "NSE_EQ|CASH", interval: str = "1D") -> list[dict]:
        """Returns list of DII activity records: [{time_stamp, buy_amount, sell_amount, ...}]."""
        params = {"data_type": data_type, "interval": interval}
        body = self._request("GET", "/v2/market/dii", params=params)
        return (body.get("data") or {}).get(data_type, [])

    def get_news(self, instrument_keys: list[str]) -> dict:
        """Returns news articles mapped by instrument key:
        {instrument_key: [{heading, summary, article_link, thumbnail, published_time}, ...]}.
        Upstox supports up to 30 instrument keys per call.
        """
        if not instrument_keys:
            return {}
        keys_param = ",".join(instrument_keys)
        params = {"category": "instrument_keys", "instrument_keys": keys_param}
        body = self._request("GET", "/v2/news", params=params)
        return body.get("data") or {}
