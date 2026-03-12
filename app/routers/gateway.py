"""Main gateway route: OpenAI-compatible chat completions proxy."""

import logging
import time
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

import redis.asyncio as redis_lib

from app.cache import get_redis
from app.database import get_db
from app.models.user import ApiKey, Team
from app.schemas.gateway import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    GatewayMetadata,
    make_error_response,
)
from app.services.audit import log_request
from app.services.cache import get_cached_response, set_cached_response
from app.services.cost_tracker import calculate_cost, update_usage_summary
from app.services.policy_engine import evaluate_policies
from app.services.rate_limiter import check_rate_limit
from app.services.router import provider_router

logger = logging.getLogger(__name__)

router = APIRouter(tags=["gateway"])


async def _authenticate(
    authorization: str | None,
    db: AsyncSession,
) -> tuple[Team, ApiKey]:
    """Validate the Bearer token and return the associated team and API key.

    Raises HTTPException 401 if the key is invalid or inactive.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Empty API key")

    # Hash the token to look it up
    import hashlib
    key_hash = hashlib.sha256(token.encode()).hexdigest()

    stmt = select(ApiKey).where(ApiKey.key_hash == key_hash, ApiKey.is_active.is_(True))
    result = await db.execute(stmt)
    api_key = result.scalar_one_or_none()

    if api_key is None:
        raise HTTPException(status_code=401, detail="Invalid API key")

    # Fetch the team
    team_stmt = select(Team).where(Team.id == api_key.team_id, Team.is_active.is_(True))
    team_result = await db.execute(team_stmt)
    team = team_result.scalar_one_or_none()

    if team is None:
        raise HTTPException(status_code=403, detail="Team is inactive")

    # Update last_used_at
    from datetime import datetime, timezone
    await db.execute(
        update(ApiKey)
        .where(ApiKey.id == api_key.id)
        .values(last_used_at=datetime.now(timezone.utc))
    )

    return team, api_key


@router.post("/v1/chat/completions", response_model=ChatCompletionResponse)
async def chat_completions(
    request_body: ChatCompletionRequest,
    request: Request,
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
    redis_client: redis_lib.Redis | None = Depends(get_redis),
):
    """OpenAI-compatible chat completions endpoint.

    Pipeline:
    1. Authenticate API key
    2. Check rate limit
    3. Evaluate access policies
    4. Check prompt cache
    5. Route to provider
    6. Calculate cost
    7. Log audit entry
    8. Update usage counters
    9. Return response with gateway metadata
    """
    request_id = str(uuid.uuid4())
    start_time = time.monotonic()
    ip_address = request.client.host if request.client else None

    # 1. Authenticate
    team, api_key = await _authenticate(authorization, db)

    # 2. Rate limit
    rate_result = await check_rate_limit(
        redis_client, str(team.id), team.rate_limit_rpm
    )
    if not rate_result:
        latency_ms = int((time.monotonic() - start_time) * 1000)
        await log_request(
            db=db,
            team_id=str(team.id),
            api_key_id=str(api_key.id),
            request_id=request_id,
            model=request_body.model,
            provider="none",
            latency_ms=latency_ms,
            status="rate_limited",
            error_message="Rate limit exceeded",
            request_body=request_body.model_dump(),
            ip_address=ip_address,
        )
        raise HTTPException(
            status_code=429,
            detail=make_error_response(
                f"Rate limit exceeded. Limit: {rate_result.limit} RPM. "
                f"Retry after: {int(rate_result.reset_at - time.time())}s",
                error_type="rate_limit_error",
                code="rate_limit_exceeded",
            ),
            headers={
                "X-RateLimit-Limit": str(rate_result.limit),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(int(rate_result.reset_at)),
                "Retry-After": str(max(1, int(rate_result.reset_at - time.time()))),
            },
        )

    # 3. Evaluate policies
    policy_decision = await evaluate_policies(db, str(team.id), request_body)
    if not policy_decision:
        latency_ms = int((time.monotonic() - start_time) * 1000)
        await log_request(
            db=db,
            team_id=str(team.id),
            api_key_id=str(api_key.id),
            request_id=request_id,
            model=request_body.model,
            provider="none",
            latency_ms=latency_ms,
            status="policy_denied",
            error_message=policy_decision.reason,
            request_body=request_body.model_dump(),
            ip_address=ip_address,
        )
        raise HTTPException(
            status_code=403,
            detail=make_error_response(
                policy_decision.reason,
                error_type="policy_error",
                code="policy_denied",
            ),
        )

    # 4. Check prompt cache
    cached = await get_cached_response(redis_client, request_body)
    if cached is not None:
        latency_ms = int((time.monotonic() - start_time) * 1000)
        response = ChatCompletionResponse(**cached)
        response.gateway_metadata = GatewayMetadata(
            cost_usd=0.0,
            cache_hit=True,
            provider=cached.get("gateway_metadata", {}).get("provider", "cache"),
            latency_ms=latency_ms,
            request_id=request_id,
        )

        await log_request(
            db=db,
            team_id=str(team.id),
            api_key_id=str(api_key.id),
            request_id=request_id,
            model=request_body.model,
            provider="cache",
            latency_ms=latency_ms,
            status="success",
            ip_address=ip_address,
        )
        await update_usage_summary(
            db=db,
            team_id=str(team.id),
            model=request_body.model,
            provider="cache",
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            cost_usd=0.0,
            cache_hit=True,
        )
        return response

    # 5. Route to provider
    try:
        response = await provider_router.route_request(request_body)
    except RuntimeError as exc:
        latency_ms = int((time.monotonic() - start_time) * 1000)
        await log_request(
            db=db,
            team_id=str(team.id),
            api_key_id=str(api_key.id),
            request_id=request_id,
            model=request_body.model,
            provider="none",
            latency_ms=latency_ms,
            status="error",
            error_message=str(exc),
            request_body=request_body.model_dump(),
            ip_address=ip_address,
        )
        raise HTTPException(status_code=502, detail=make_error_response(str(exc), "provider_error"))
    except Exception as exc:
        latency_ms = int((time.monotonic() - start_time) * 1000)
        await log_request(
            db=db,
            team_id=str(team.id),
            api_key_id=str(api_key.id),
            request_id=request_id,
            model=request_body.model,
            provider="none",
            latency_ms=latency_ms,
            status="error",
            error_message=str(exc),
            request_body=request_body.model_dump(),
            ip_address=ip_address,
        )
        logger.exception("Provider error for model=%s", request_body.model)
        raise HTTPException(status_code=500, detail=make_error_response(str(exc), "internal_error"))

    # 6. Calculate cost
    prompt_tokens = response.usage.prompt_tokens
    completion_tokens = response.usage.completion_tokens
    total_tokens = response.usage.total_tokens
    cost_usd = calculate_cost(request_body.model, prompt_tokens, completion_tokens)

    provider_name = response.gateway_metadata.provider if response.gateway_metadata else "unknown"
    provider_latency = response.gateway_metadata.latency_ms if response.gateway_metadata else 0

    total_latency_ms = int((time.monotonic() - start_time) * 1000)

    # Set gateway metadata on response
    response.gateway_metadata = GatewayMetadata(
        cost_usd=cost_usd,
        cache_hit=False,
        provider=provider_name,
        latency_ms=total_latency_ms,
        request_id=request_id,
    )

    # 7. Log audit entry
    await log_request(
        db=db,
        team_id=str(team.id),
        api_key_id=str(api_key.id),
        request_id=request_id,
        model=request_body.model,
        provider=provider_name,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        cost_usd=cost_usd,
        latency_ms=total_latency_ms,
        status="success",
        request_body=request_body.model_dump(),
        response_body=response.model_dump(),
        ip_address=ip_address,
    )

    # 8. Update usage counters
    await update_usage_summary(
        db=db,
        team_id=str(team.id),
        model=request_body.model,
        provider=provider_name,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        cost_usd=cost_usd,
    )

    # 9. Cache the response (async, best-effort)
    try:
        await set_cached_response(redis_client, request_body, response.model_dump())
    except Exception as exc:
        logger.warning("Failed to cache response: %s", exc)

    return response
