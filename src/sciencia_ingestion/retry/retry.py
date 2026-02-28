from __future__ import annotations
import random
import time
from dataclasses import dataclass
from typing import Callable, TypeVar

T = TypeVar("T")

@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 5
    base_delay: float = 1.0
    max_delay: float = 30.0
    jitter: float = 0.25  # +/- 25%

def _sleep(attempt: int, p: RetryPolicy) -> float:
    d = min(p.max_delay, p.base_delay * (2 ** (attempt - 1)))
    j = d * p.jitter
    return max(0.0, d + random.uniform(-j, j))

def call_with_retries(fn: Callable[[], T], policy: RetryPolicy, is_retryable: Callable[[Exception], bool]) -> T:
    last: Exception | None = None
    for attempt in range(1, policy.max_attempts + 1):
        try:
            return fn()
        except Exception as e:
            last = e
            if attempt >= policy.max_attempts or not is_retryable(e):
                break
            time.sleep(_sleep(attempt, policy))
    assert last is not None
    raise last
