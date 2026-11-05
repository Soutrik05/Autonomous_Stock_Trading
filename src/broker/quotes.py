"""
LiveQuoteProvider and ReplayQuoteProvider implementations of the QuoteProvider interface.
See Plan_v3 §4.4 and Core Architectural Principles 5.
"""
import sqlite3
from typing import Dict, Iterable, Optional

from core.interfaces import QuoteProvider
from core.money import rupees_to_paise
from ingestion.upstox_client import UpstoxClient


class ReplayQuoteProvider(QuoteProvider):
    """Returns scripted or in-memory prices {ticker: price_paise} for tests and replays."""

    def __init__(self, quotes: Optional[Dict[str, int]] = None):
        self._quotes: Dict[str, int] = dict(quotes) if quotes else {}

    def set_quote(self, ticker: str, price_paise: int) -> None:
        self._quotes[ticker] = price_paise

    def get_quotes(self, tickers: Iterable[str]) -> Dict[str, int]:
        result = {}
        for ticker in tickers:
            if ticker in self._quotes:
                result[ticker] = self._quotes[ticker]
        return result


class LiveQuoteProvider(QuoteProvider):
    """Fetches real-time market quotes from Upstox API using instrument keys from the symbols table."""

    def __init__(self, portfolio_conn: sqlite3.Connection, client: Optional[UpstoxClient] = None):
        self._conn = portfolio_conn
        self._client = client or UpstoxClient()

    def get_quotes(self, tickers: Iterable[str]) -> Dict[str, int]:
        ticker_list = list(tickers)
        if not ticker_list:
            return {}

        placeholders = ",".join("?" * len(ticker_list))
        rows = self._conn.execute(
            f"SELECT ticker, instrument_key FROM symbols WHERE ticker IN ({placeholders})",
            ticker_list,
        ).fetchall()

        ticker_to_key = {r["ticker"]: r["instrument_key"] for r in rows}
        key_to_ticker = {r["instrument_key"]: r["ticker"] for r in rows}

        instrument_keys_to_fetch = list(ticker_to_key.values())
        for t in ticker_list:
            if t in ("NIFTY_500", "NIFTY500", "NIFTY 500"):
                key = "NSE_INDEX|Nifty 500"
                instrument_keys_to_fetch.append(key)
                key_to_ticker[key] = t
            elif t not in ticker_to_key:
                key = f"NSE_EQ|{t}"
                instrument_keys_to_fetch.append(key)
                key_to_ticker[key] = t

        raw_quotes = self._client.get_quotes(instrument_keys_to_fetch)

        results: Dict[str, int] = {}
        for returned_key, quote_data in raw_quotes.items():
            last_price = quote_data.get("last_price")
            if last_price is not None:
                price_paise = rupees_to_paise(last_price)
                symbol = quote_data.get("symbol")
                if symbol and symbol in ticker_list:
                    results[symbol] = price_paise
                pipe_key = returned_key.replace(":", "|", 1)
                if pipe_key in key_to_ticker:
                    results[key_to_ticker[pipe_key]] = price_paise

        return results
