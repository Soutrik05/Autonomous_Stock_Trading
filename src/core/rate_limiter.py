"""
Thread-safe multi-tier sliding-window rate limiter for Upstox calls (per second/minute/30 minutes).
See Plan_v3 §1.3.
"""

import threading
import time
from collections import deque

from core.config import settings


class UpstoxRateLimiter:
    """Blocks `acquire()` until a call is allowed under all three sliding windows at once.
    `time_func`/`sleep_func` are injectable so tests can verify blocking behaviour without
    actually sleeping (a fake sleep_func just advances the fake clock instead of waiting)."""

    def __init__(
        self,
        per_sec: int = None,
        per_min: int = None,
        per_30min: int = None,
        time_func=time.time,
        sleep_func=time.sleep,
    ):
        self._time = time_func
        self._sleep = sleep_func
        self._lock = threading.Lock()
        self._windows = [
            (deque(), 1.0, per_sec if per_sec is not None else settings.RATE_LIMIT_PER_SEC),
            (deque(), 60.0, per_min if per_min is not None else settings.RATE_LIMIT_PER_MIN),
            (deque(), 1800.0, per_30min if per_30min is not None else settings.RATE_LIMIT_PER_30MIN),
        ]

    def acquire(self) -> None:
        with self._lock:
            while True:
                now = self._time()
                wait = 0.0
                for q, span, cap in self._windows:
                    while q and q[0] <= now - span:
                        q.popleft()
                    if len(q) >= cap:
                        wait = max(wait, span - (now - q[0]))
                if wait <= 0:
                    for q, _, _ in self._windows:
                        q.append(now)
                    return
                self._sleep(max(0.01, wait))
