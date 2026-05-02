"""
Rate limiting using Redis atomic operations.

BUG FIX: Original implementation had a race condition:
    count = cache.get(key, 0)      # read
    cache.set(key, count + 1, ...) # write

Two concurrent calls can both read count=9 (below limit=10), both write 10,
and both return False — so the limit is not enforced under concurrency.

Fixed by using Redis INCR (atomic) + EXPIRE via the raw Redis client.
INCR returns the new value atomically, so only one caller gets value 11.

ADDED: get_remaining() — useful for returning rate-limit headers.
ADDED: Per-action rate limiting (e.g. tighter limits for email sends).
"""

import logging
from django.core.cache import cache

logger = logging.getLogger(__name__)

# Default limits per action
LIMITS = {
    "default":     {"limit": 60,  "window": 60},   # 60 events/minute
    "email":       {"limit": 5,   "window": 3600},  # 5 emails/hour
    "push":        {"limit": 30,  "window": 60},    # 30 pushes/minute
    "websocket":   {"limit": 20,  "window": 60},    # 20 WS msgs/minute
}


def _redis_client():
    """Return the raw redis-py client from django-redis."""
    return cache.client.get_client()


def is_rate_limited(user_id: str, action: str = "default", limit: int = None, window: int = None) -> bool:
    """
    Return True if the user has exceeded the rate limit for `action`.

    Uses Redis INCR for atomicity — no race conditions.
    Falls back to cache.get/set if the raw client is unavailable (e.g. LocMemCache in tests).
    """
    cfg = LIMITS.get(action, LIMITS["default"])
    effective_limit = limit if limit is not None else cfg["limit"]
    effective_window = window if window is not None else cfg["window"]
    key = f"rate:{action}:{user_id}"

    try:
        client = _redis_client()
        current = client.incr(key)
        if current == 1:
            # First increment — set the expiry
            client.expire(key, effective_window)
        return current > effective_limit
    except Exception:
        # Fallback for non-Redis backends (dev/test)
        logger.debug("Redis client unavailable, using cache fallback for rate limiting")
        count = cache.get(key, 0)
        if count >= effective_limit:
            return True
        cache.set(key, count + 1, timeout=effective_window)
        return False


def get_remaining(user_id: str, action: str = "default") -> int:
    """Return how many requests the user has left in the current window."""
    cfg = LIMITS.get(action, LIMITS["default"])
    key = f"rate:{action}:{user_id}"
    try:
        current = int(_redis_client().get(key) or 0)
        return max(0, cfg["limit"] - current)
    except Exception:
        return cfg["limit"]


def reset_rate_limit(user_id: str, action: str = "default") -> None:
    """Clear the rate limit for a user (useful in tests or admin overrides)."""
    key = f"rate:{action}:{user_id}"
    try:
        _redis_client().delete(key)
    except Exception:
        cache.delete(key)