import time

from app.utils.cache import TTLCache


def test_set_get_roundtrip():
    cache = TTLCache(maxsize=10, ttl=60)
    cache.set("a", 123)
    assert cache.get("a") == 123


def test_missing_key_returns_none():
    cache = TTLCache(maxsize=10, ttl=60)
    assert cache.get("missing") is None


def test_expiry():
    cache = TTLCache(maxsize=10, ttl=0.05)
    cache.set("a", "value")
    assert cache.get("a") == "value"
    time.sleep(0.08)
    assert cache.get("a") is None


def test_eviction_at_maxsize():
    cache = TTLCache(maxsize=2, ttl=60)
    cache.set("a", 1)
    cache.set("b", 2)
    cache.set("c", 3)  # should evict "a" (oldest)
    assert cache.get("a") is None
    assert cache.get("b") == 2
    assert cache.get("c") == 3


def test_stats_hits_and_misses():
    cache = TTLCache(maxsize=10, ttl=60)
    cache.set("a", 1)
    cache.get("a")  # hit
    cache.get("missing")  # miss
    stats = cache.stats()
    assert stats["hits"] == 1
    assert stats["misses"] == 1
    assert stats["size"] == 1
