"""Redis-based sliding window rate limiter."""

import logging
import time

import redis.asyncio as redis_lib

logger = logging.getLogger(__name__)


class RateLimitResult:
    """Outcome of a rate limit check."""

    def __init__(self, allowed: bool, remaining: int, reset_at: float, limit: int):
        self.allowed = allowed
        self.remaining = remaining
        self.reset_at = reset_at
        self.limit = limit

    def __bool__(self) -> bool:
        return self.allowed


async def check_rate_limit(
    redis_client: redis_lib.Redis | None,
    team_id: str,
    limit_rpm: int,
) -> RateLimitResult:
    """Sliding-window rate limiter using a Redis sorted set.

    Each request is recorded as a member with the current timestamp as the score.
    Old entries (older than 60 seconds) are pruned on each check.

    Returns a RateLimitResult indicating whether the request is allowed.
    """
    if redis_client is None:
        # If Redis is unavailable, allow all requests (fail open)
        return RateLimitResult(allowed=True, remaining=limit_rpm, reset_at=0, limit=limit_rpm)

    key = f"rate_limit:{team_id}"
    now = time.time()
    window_start = now - 60.0  # 60-second sliding window

    pipe = redis_client.pipeline(transaction=True)
    try:
        # Remove entries older than the window
        pipe.zremrangebyscore(key, "-inf", window_start)
        # Count current entries in the window
        pipe.zcard(key)
        # Add the current request
        pipe.zadd(key, {f"{now}:{id(pipe)}": now})
        # Set TTL on the key so it auto-expires
        pipe.expire(key, 120)
        results = await pipe.execute()
    except Exception as exc:
        logger.warning("Rate limiter Redis error: %s; failing open", exc)
        return RateLimitResult(allowed=True, remaining=limit_rpm, reset_at=0, limit=limit_rpm)

    current_count = results[1]  # zcard result before the new addition

    if current_count >= limit_rpm:
        # Over limit; remove the entry we just added
        try:
            await redis_client.zremrangebyscore(key, now, now + 1)
        except Exception:
            pass

        # Find the oldest entry to calculate reset time
        try:
            oldest = await redis_client.zrangebyscore(key, "-inf", "+inf", start=0, num=1, withscores=True)
            reset_at = oldest[0][1] + 60.0 if oldest else now + 60.0
        except Exception:
            reset_at = now + 60.0

        return RateLimitResult(
            allowed=False,
            remaining=0,
            reset_at=reset_at,
            limit=limit_rpm,
        )

    remaining = max(0, limit_rpm - current_count - 1)
    reset_at = now + 60.0

    return RateLimitResult(
        allowed=True,
        remaining=remaining,
        reset_at=reset_at,
        limit=limit_rpm,
    )


async def get_rate_limit_status(
    redis_client: redis_lib.Redis | None,
    team_id: str,
    limit_rpm: int,
) -> dict:
    """Get current rate limit status without consuming a request."""
    if redis_client is None:
        return {"limit": limit_rpm, "remaining": limit_rpm, "used": 0}

    key = f"rate_limit:{team_id}"
    now = time.time()
    window_start = now - 60.0

    try:
        await redis_client.zremrangebyscore(key, "-inf", window_start)
        current_count = await redis_client.zcard(key)
    except Exception:
        current_count = 0

    return {
        "limit": limit_rpm,
        "remaining": max(0, limit_rpm - current_count),
        "used": current_count,
    }
