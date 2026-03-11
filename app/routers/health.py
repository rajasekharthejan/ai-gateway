"""Health check endpoints."""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

import redis.asyncio as redis_lib

from app.cache import get_redis
from app.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    """Basic liveness probe."""
    return {"status": "ok"}


@router.get("/health/ready")
async def readiness_check(
    db: AsyncSession = Depends(get_db),
    redis_client: redis_lib.Redis | None = Depends(get_redis),
):
    """Readiness probe that checks database and Redis connectivity."""
    checks = {}

    # Database check
    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:
        checks["database"] = f"error: {exc}"
        logger.warning("Database readiness check failed: %s", exc)

    # Redis check
    try:
        if redis_client:
            await redis_client.ping()
            checks["redis"] = "ok"
        else:
            checks["redis"] = "not configured"
    except Exception as exc:
        checks["redis"] = f"error: {exc}"
        logger.warning("Redis readiness check failed: %s", exc)

    all_ok = all(v == "ok" for v in checks.values() if v != "not configured")
    status_code = 200 if all_ok else 503

    return {"status": "ready" if all_ok else "degraded", "checks": checks}
