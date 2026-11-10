"""Small bounded, TTL in-process cache.

Not a general-purpose caching library -- just enough to avoid re-embedding
or re-searching the same text within a single process lifetime. Explicitly
NOT shared across workers/processes; if this app is ever run with multiple
Uvicorn workers each worker gets its own cache. That's an acceptable
tradeoff for a single-instance portfolio deployment, and is documented here
so it isn't mistaken for a distributed cache later.
"""

from __future__ import annotations

import time
from collections import OrderedDict
from threading import Lock
from typing import Any, Optional


class TTLCache:
    def __init__(self, maxsize: int = 256, ttl: float = 600.0):
        self.maxsize = maxsize
        self.ttl = ttl
        self._store: "OrderedDict[str, tuple[Any, float]]" = OrderedDict()
        self._lock = Lock()
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            item = self._store.get(key)
            if item is None:
                self.misses += 1
                return None
            value, expires_at = item
            if time.time() > expires_at:
                del self._store[key]
                self.misses += 1
                return None
            # move to end (LRU-ish behavior for eviction)
            self._store.move_to_end(key)
            self.hits += 1
            return value

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            if key in self._store:
                self._store.move_to_end(key)
            self._store[key] = (value, time.time() + self.ttl)
            while len(self._store) > self.maxsize:
                self._store.popitem(last=False)

    def stats(self) -> dict:
        with self._lock:
            total = self.hits + self.misses
            return {
                "size": len(self._store),
                "maxsize": self.maxsize,
                "hits": self.hits,
                "misses": self.misses,
                "hit_rate": round(self.hits / total, 3) if total else 0.0,
            }

    def clear(self) -> None:
        with self._lock:
            self._store.clear()
