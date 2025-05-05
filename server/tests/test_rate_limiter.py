from services.rate_limiter import RateLimiter
import time


def test_rate_limiter_allows_and_bans():
    rl = RateLimiter()
    key = "test"

    # Send MAX_MSG_PER_WIN messages quickly
    for _ in range(60):
        assert rl.allow(key) is True

    # Next one should trigger a temporary ban
    assert rl.allow(key) is False
    assert rl.is_banned(key) is True

    # After BAN_SECONDS, it should clear
    time.sleep(31)
    assert rl.allow(key) is True
