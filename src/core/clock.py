"""
SystemClock (real IST time) and FakeClock (fixed/advanceable time for tests and replay).
See Plan_v3 Core Architectural Principles 6.
"""
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from core.interfaces import Clock
from settings import settings

IST = ZoneInfo(settings.TIMEZONE)


class SystemClock(Clock):
    """Reads the real current time in Asia/Kolkata. The only Clock used in production."""

    def now(self) -> datetime:
        return datetime.now(IST)

    def today(self) -> date:
        return self.now().date()

    def now_iso(self) -> str:
        return self.now().isoformat()


class FakeClock(Clock):
    """A settable, advanceable Clock for tests and replay runs."""

    def __init__(self, fixed_now: datetime):
        if fixed_now.tzinfo is None:
            fixed_now = fixed_now.replace(tzinfo=IST)
        self._now = fixed_now

    def now(self) -> datetime:
        return self._now

    def today(self) -> date:
        return self._now.date()

    def now_iso(self) -> str:
        return self._now.isoformat()

    def set(self, new_now: datetime) -> None:
        if new_now.tzinfo is None:
            new_now = new_now.replace(tzinfo=IST)
        self._now = new_now

    def advance(self, **timedelta_kwargs) -> None:
        self._now = self._now + timedelta(**timedelta_kwargs)
