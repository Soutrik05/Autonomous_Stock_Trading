"""
Abstract base classes for Clock and QuoteProvider, so live, replay and test code share one contract.
See Plan_v3 Core Architectural Principles 5.
"""

from abc import ABC, abstractmethod
from collections.abc import Iterable
from datetime import date, datetime


class Clock(ABC):
    """Supplies the current IST business date and timestamp. Nothing reads system time directly."""

    @abstractmethod
    def now(self) -> datetime:
        """Returns the current IST timestamp."""
        raise NotImplementedError

    @abstractmethod
    def today(self) -> date:
        """Returns the current IST business date."""
        raise NotImplementedError

    @abstractmethod
    def now_iso(self) -> str:
        """Returns the current IST timestamp as ISO-8601 text, for storage in TEXT columns."""
        raise NotImplementedError


class QuoteProvider(ABC):
    """Supplies quotes for a batch of tickers. Implemented by LiveQuoteProvider and ReplayQuoteProvider."""

    @abstractmethod
    def get_quotes(self, tickers: Iterable[str]) -> dict[str, int]:
        """Returns {ticker: last_traded_price_paise} for the given tickers."""
        raise NotImplementedError
