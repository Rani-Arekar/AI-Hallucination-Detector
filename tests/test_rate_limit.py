import time

from app.utils.rate_limit import SlidingWindowRateLimiter


def test_allows_up_to_max_requests():
    limiter = SlidingWindowRateLimiter(max_requests=3, window_seconds=60)
    for _ in range(3):
        allowed, _ = limiter.check("client-a")
        assert allowed


def test_blocks_after_max_requests():
    limiter = SlidingWindowRateLimiter(max_requests=2, window_seconds=60)
    limiter.check("client-a")
    limiter.check("client-a")
    allowed, retry_after = limiter.check("client-a")
    assert not allowed
    assert retry_after > 0


def test_clients_are_tracked_independently():
    limiter = SlidingWindowRateLimiter(max_requests=1, window_seconds=60)
    allowed_a, _ = limiter.check("client-a")
    allowed_b, _ = limiter.check("client-b")
    assert allowed_a
    assert allowed_b


def test_window_expiry_allows_requests_again():
    limiter = SlidingWindowRateLimiter(max_requests=1, window_seconds=0.05)
    allowed_1, _ = limiter.check("client-a")
    allowed_2, _ = limiter.check("client-a")
    time.sleep(0.08)
    allowed_3, _ = limiter.check("client-a")
    assert allowed_1
    assert not allowed_2
    assert allowed_3
