"""
Unit tests for core/rate_limiter.py sliding-window limits, using a fake clock so nothing sleeps.
See Plan_v3 §1.3.
"""

from core.rate_limiter import UpstoxRateLimiter


class FakeTime:
    """A controllable clock: acquire() reads `now`, and the injected sleep_func advances it
    by the requested amount instead of actually blocking."""

    def __init__(self):
        self.now = 0.0
        self.sleep_calls = 0

    def time(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleep_calls += 1
        self.now += seconds


def test_per_second_limit_blocks_without_sleeping():
    clock = FakeTime()
    limiter = UpstoxRateLimiter(per_sec=2, per_min=1000, per_30min=10000, time_func=clock.time, sleep_func=clock.sleep)

    limiter.acquire()
    limiter.acquire()
    assert clock.sleep_calls == 0  # first two calls are free

    limiter.acquire()  # third call within the same second must wait
    assert clock.sleep_calls > 0
    assert clock.now >= 1.0  # the fake clock advanced by (at least) the per-second window


def test_per_minute_limit_blocks():
    clock = FakeTime()
    limiter = UpstoxRateLimiter(per_sec=1000, per_min=2, per_30min=10000, time_func=clock.time, sleep_func=clock.sleep)

    limiter.acquire()
    limiter.acquire()
    assert clock.sleep_calls == 0

    limiter.acquire()
    assert clock.sleep_calls > 0
    assert clock.now >= 60.0


def test_per_30min_limit_blocks():
    clock = FakeTime()
    limiter = UpstoxRateLimiter(per_sec=1000, per_min=1000, per_30min=2, time_func=clock.time, sleep_func=clock.sleep)

    limiter.acquire()
    limiter.acquire()
    assert clock.sleep_calls == 0

    limiter.acquire()
    assert clock.sleep_calls > 0
    assert clock.now >= 1800.0


def test_window_frees_up_after_expiry():
    clock = FakeTime()
    limiter = UpstoxRateLimiter(per_sec=1, per_min=1000, per_30min=10000, time_func=clock.time, sleep_func=clock.sleep)

    limiter.acquire()
    clock.now += 1.1  # past the 1-second window
    limiter.acquire()  # must not block: the first call has expired out of the window
    assert clock.sleep_calls == 0
