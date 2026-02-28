from __future__ import annotations
import time

class RateLimiter:
    def __init__(self, min_interval_seconds: float) -> None:
        self.min_interval = float(min_interval_seconds)
        self._last = 0.0

    def wait(self) -> None:
        now = time.time()
        sleep_s = (self._last + self.min_interval) - now
        if sleep_s > 0:
            time.sleep(sleep_s)
        self._last = time.time()
