"""Prompt-level response caching using Redis."""

import hashlib
import json
import logging

import redis.asyncio as redis_lib

from app.config import get_settings
from app.schemas.gateway import ChatCompletionRequest

logger = logging.getLogger(__name__)


def _build_cache_key(request: ChatCompletionRequest) -> str:
    """Create a deterministic cache key from the request.

    Hashes model + messages + temperature + top_p + max_tokens to produce
    a stable key. This means identical prompts with the same parameters
    will share a cached response.
    """
    key_parts = {
        "model": request.model,
        "messages": [m.model_dump(exclude_none=True) for m in request.messages],
        "temperature": request.temperature,
        "top_p": request.top_p,
        "max_tokens": request.max_tokens,
        "n": request.n,
    }
    key_json = json.dumps(key_parts, sort_keys=True, separators=(",", ":"))
    key_hash = hashlib.sha256(key_json.encode()).hexdigest()
    return f"cache:chat:{key_hash}"


async def get_cached_response(
    redis_client: redis_lib.Redis | None,
    request: ChatCompletionRequest,
) -> dict | None:
    """Look up a cached response for the given request.

    Returns the parsed JSON response dict if found, else None.
    """
    settings = get_settings()
    if not settings.CACHE_ENABLED or redis_client is None:
        return None

    key = _build_cache_key(request)
    try:
        cached = await redis_client.get(key)
        if cached:
            logger.debug("Cache HIT for key=%s", key[:32])
            return json.loads(cached)
    except Exception as exc:
        logger.warning("Cache read error: %s", exc)

    return None


async def set_cached_response(
    redis_client: redis_lib.Redis | None,
    request: ChatCompletionRequest,
    response_dict: dict,
) -> None:
    """Store a response in the cache with TTL.

    Only caches if:
    - Caching is enabled
    - Temperature is 0 (deterministic output) OR explicitly enabled
    - The response was successful
    """
    settings = get_settings()
    if not settings.CACHE_ENABLED or redis_client is None:
        return

    # Only cache deterministic (temperature=0) responses by default
    if request.temperature > 0:
        return

    key = _build_cache_key(request)
    try:
        payload = json.dumps(response_dict, separators=(",", ":"))
        await redis_client.setex(key, settings.CACHE_TTL_SECONDS, payload)
        logger.debug("Cache SET for key=%s (ttl=%ds)", key[:32], settings.CACHE_TTL_SECONDS)
    except Exception as exc:
        logger.warning("Cache write error: %s", exc)


async def invalidate_cache(
    redis_client: redis_lib.Redis | None,
    pattern: str = "cache:chat:*",
) -> int:
    """Delete cache entries matching a pattern. Returns count of deleted keys."""
    if redis_client is None:
        return 0

    deleted = 0
    try:
        cursor = "0"
        while cursor:
            cursor, keys = await redis_client.scan(
                cursor=cursor, match=pattern, count=100
            )
            if keys:
                deleted += await redis_client.delete(*keys)
            if cursor == 0 or cursor == "0":
                break
    except Exception as exc:
        logger.warning("Cache invalidation error: %s", exc)

    logger.info("Invalidated %d cache entries matching '%s'", deleted, pattern)
    return deleted


async def get_cache_stats(redis_client: redis_lib.Redis | None) -> dict:
    """Return basic cache statistics."""
    if redis_client is None:
        return {"enabled": False, "keys": 0}

    try:
        cursor = "0"
        total_keys = 0
        while True:
            cursor, keys = await redis_client.scan(
                cursor=cursor, match="cache:chat:*", count=100
            )
            total_keys += len(keys)
            if cursor == 0 or cursor == "0":
                break
        return {"enabled": True, "keys": total_keys}
    except Exception as exc:
        return {"enabled": True, "keys": 0, "error": str(exc)}
