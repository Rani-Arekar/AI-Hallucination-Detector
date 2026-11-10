"""In-process, per-client sliding-window rate limiter.

Deliberately not backed by Redis or any external service -- for a
single-instance portfolio deployment this is a reasonable tradeoff (see
app/config.py). It will NOT correctly rate-limit across multiple Uvicorn
workers or multiple deployed instances, since each process has its own
in-memory state; that's a known, documented limitation, not an oversight.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from threading import Lock


class SlidingWindowRateLimiter:
    def __init__(self, max_requests: int, window_seconds: float):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: dict[str, deque] = defaultdict(deque)
        self._lock = Lock()

    def check(self, key: str) -> tuple[bool, float]:
        """Returns (allowed, retry_after_seconds). Records the hit if
        allowed.
        """
        now = time.monotonic()
        with self._lock:
            q = self._hits[key]
            cutoff = now - self.window_seconds
            while q and q[0] < cutoff:
                q.popleft()

            if len(q) >= self.max_requests:
                retry_after = self.window_seconds - (now - q[0])
                return False, max(retry_after, 0.0)

            q.append(now)
            return True, 0.0
