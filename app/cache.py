"""Redis async client for caching and rate limiting."""

import logging
from collections.abc import AsyncGenerator

import redis.asyncio as redis

from app.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

_redis_pool: redis.Redis | None = None


async def init_redis() -> redis.Redis:
    """Initialize the Redis connection pool."""
    global _redis_pool
    _redis_pool = redis.from_url(
        settings.REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
        max_connections=50,
    )
    try:
        await _redis_pool.ping()
        logger.info("Redis connection established")
    except redis.ConnectionError:
        logger.warning("Redis not available; caching and rate limiting disabled")
        _redis_pool = None
    return _redis_pool


async def close_redis() -> None:
    """Close the Redis connection pool."""
    global _redis_pool
    if _redis_pool:
        await _redis_pool.close()
        _redis_pool = None
        logger.info("Redis connection closed")


async def get_redis() -> AsyncGenerator[redis.Redis | None, None]:
    """FastAPI dependency that yields the Redis client."""
    yield _redis_pool


def get_redis_client() -> redis.Redis | None:
    """Direct access to the Redis client (non-dependency)."""
    return _redis_pool
