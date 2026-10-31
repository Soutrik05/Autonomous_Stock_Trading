"""
Unit tests for ingestion/upstox_client.py retry/backoff behaviour, using a fake HTTP session
so no real network call is made and nothing sleeps.
See Plan_v3 §1.1, §1.5.
"""
import pytest

from core.rate_limiter import UpstoxRateLimiter
from ingestion.upstox_client import UpstoxAPIError, UpstoxClient


class FakeResponse:
    def __init__(self, status_code, body):
        self.status_code = status_code
        self._body = body

    def json(self):
        return self._body


class FakeSession:
    """Returns the next canned response on each call; records every call's URL/params."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def request(self, method, url, headers=None, params=None, timeout=None):
        self.calls.append({"method": method, "url": url, "params": params, "headers": headers})
        return self._responses.pop(0)


def make_client(responses, max_retries=3):
    sleeps = []
    session = FakeSession(responses)
    client = UpstoxClient(
        token="fake-token",
        rate_limiter=UpstoxRateLimiter(per_sec=1000, per_min=1000, per_30min=1000),
        session=session,
        max_retries=max_retries,
        backoff_base_sec=1.0,
        sleep_func=sleeps.append,
    )
    return client, session, sleeps


def test_succeeds_on_first_try():
    client, session, sleeps = make_client([FakeResponse(200, {"status": "success", "data": {"candles": []}})])
    result = client.get_daily_candles("NSE_EQ|INE002A01018", "2026-10-01", "2026-10-15")
    assert result == []
    assert len(session.calls) == 1
    assert sleeps == []


def test_retries_on_429_then_succeeds():
    client, session, sleeps = make_client(
        [
            FakeResponse(429, {"status": "error"}),
            FakeResponse(503, {"status": "error"}),
            FakeResponse(200, {"status": "success", "data": {"candles": [["2026-10-15", 1, 2, 3, 4, 5, 0]]}}),
        ]
    )
    result = client.get_daily_candles("NSE_EQ|INE002A01018", "2026-10-01", "2026-10-15")
    assert len(result) == 1
    assert len(session.calls) == 3
    assert sleeps == [1.0, 2.0]  # exponential backoff: base * 2**0, base * 2**1


def test_exhausts_retries_and_raises():
    client, session, sleeps = make_client(
        [FakeResponse(503, {"status": "error"})] * 4,  # 1 initial attempt + 3 retries
        max_retries=3,
    )
    with pytest.raises(UpstoxAPIError):
        client.get_daily_candles("NSE_EQ|INE002A01018", "2026-10-01", "2026-10-15")
    assert len(session.calls) == 4
    assert sleeps == [1.0, 2.0, 4.0]


def test_does_not_retry_on_404():
    client, session, sleeps = make_client([FakeResponse(404, {"status": "error"})])
    with pytest.raises(UpstoxAPIError):
        client.get_daily_candles("NSE_EQ|INE002A01018", "2026-10-01", "2026-10-15")
    assert len(session.calls) == 1
    assert sleeps == []


def test_never_logs_or_returns_the_token():
    client, session, _ = make_client([FakeResponse(200, {"status": "success", "data": {"candles": []}})])
    client.get_daily_candles("NSE_EQ|INE002A01018", "2026-10-01", "2026-10-15")
    call = session.calls[0]
    assert call["headers"]["Authorization"] == "Bearer fake-token"
    assert repr(client).count("fake-token") == 0
    assert str(client).count("fake-token") == 0


def test_v3_historical_candles_url():
    client, session, _ = make_client([FakeResponse(200, {"status": "success", "data": {"candles": [["2026-10-15T00:00:00+05:30", 1, 2, 3, 4, 5, 0]]}})])
    result = client.get_daily_candles("NSE_EQ|INE002A01018", "2026-10-01", "2026-10-15")
    assert len(result) == 1
    call = session.calls[0]
    assert "/v3/historical-candle/NSE_EQ%7CINE002A01018/days/1/2026-10-15/2026-10-01" in call["url"]


def test_v3_intraday_daily_candle_url():
    client, session, _ = make_client([FakeResponse(200, {"status": "success", "data": {"candles": [["2026-10-26T00:00:00+05:30", 10, 20, 5, 15, 500, 0]]}})])
    result = client.get_intraday_daily_candle("NSE_EQ|INE002A01018")
    assert len(result) == 1
    assert result[0][0] == "2026-10-26T00:00:00+05:30"
    call = session.calls[0]
    assert "/v3/historical-candle/intraday/NSE_EQ%7CINE002A01018/days/1" in call["url"]


def test_v3_quotes_url():
    client, session, _ = make_client([FakeResponse(200, {"status": "success", "data": {"NSE_EQ:RELIANCE": {"last_price": 1200.0}}})])
    result = client.get_quotes(["NSE_EQ|INE002A01018"])
    assert "NSE_EQ:RELIANCE" in result
    call = session.calls[0]
    assert "/v3/market-quote/quotes" in call["url"]


def test_corporate_actions_url():
    client, session, _ = make_client([FakeResponse(200, {"status": "success", "data": [{"name": "Dividend", "amount": 5.0}]})])
    result = client.get_corporate_actions("INE002A01018")
    assert len(result) == 1
    assert result[0]["name"] == "Dividend"
    call = session.calls[0]
    assert "/v2/fundamentals/INE002A01018/corporate-actions" in call["url"]


def test_fii_and_dii_urls():
    client, session, _ = make_client([
        FakeResponse(200, {"status": "success", "data": {"NSE_EQ|CASH": [{"time_stamp": 1792953000000, "buy_amount": 100, "sell_amount": 80}]}}),
        FakeResponse(200, {"status": "success", "data": {"NSE_EQ|CASH": [{"time_stamp": 1792953000000, "buy_amount": 200, "sell_amount": 150}]}}),
    ])
    fii = client.get_fii_data()
    dii = client.get_dii_data()
    assert len(fii) == 1
    assert len(dii) == 1
    assert "/v2/market/fii" in session.calls[0]["url"]
    assert "/v2/market/dii" in session.calls[1]["url"]
