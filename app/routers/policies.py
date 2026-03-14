"""CRUD endpoints for access policies."""

import logging
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models.policy import Policy
from app.schemas.policy import (
    PolicyCreate,
    PolicyListResponse,
    PolicyResponse,
    PolicyUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/policies", tags=["policies"])


def _require_admin(authorization: str | None) -> None:
    """Simple admin-key check for policy management endpoints."""
    settings = get_settings()
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    token = authorization.removeprefix("Bearer ").strip()
    if token != settings.ADMIN_API_KEY:
        raise HTTPException(status_code=403, detail="Admin access required")


@router.post("", response_model=PolicyResponse, status_code=201)
async def create_policy(
    body: PolicyCreate,
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Create a new access policy."""
    _require_admin(authorization)

    policy = Policy(
        id=uuid.uuid4(),
        team_id=body.team_id,
        name=body.name,
        description=body.description,
        policy_type=body.policy_type,
        resource=body.resource,
        conditions=body.conditions,
        priority=body.priority,
        is_active=body.is_active,
    )
    db.add(policy)
    await db.flush()
    await db.refresh(policy)

    logger.info("Created policy id=%s name='%s'", policy.id, policy.name)
    return PolicyResponse.model_validate(policy)


@router.get("", response_model=PolicyListResponse)
async def list_policies(
    team_id: uuid.UUID | None = None,
    is_active: bool | None = None,
    limit: int = 50,
    offset: int = 0,
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    """List policies with optional filters."""
    _require_admin(authorization)

    query = select(Policy)
    count_query = select(func.count(Policy.id))

    if team_id is not None:
        query = query.where(Policy.team_id == team_id)
        count_query = count_query.where(Policy.team_id == team_id)
    if is_active is not None:
        query = query.where(Policy.is_active == is_active)
        count_query = count_query.where(Policy.is_active == is_active)

    query = query.order_by(Policy.priority.desc()).offset(offset).limit(limit)

    result = await db.execute(query)
    policies = result.scalars().all()

    count_result = await db.execute(count_query)
    total = count_result.scalar_one()

    return PolicyListResponse(
        policies=[PolicyResponse.model_validate(p) for p in policies],
        total=total,
    )


@router.get("/{policy_id}", response_model=PolicyResponse)
async def get_policy(
    policy_id: uuid.UUID,
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Get a single policy by ID."""
    _require_admin(authorization)

    result = await db.execute(select(Policy).where(Policy.id == policy_id))
    policy = result.scalar_one_or_none()

    if policy is None:
        raise HTTPException(status_code=404, detail="Policy not found")

    return PolicyResponse.model_validate(policy)


@router.put("/{policy_id}", response_model=PolicyResponse)
async def update_policy(
    policy_id: uuid.UUID,
    body: PolicyUpdate,
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Update an existing policy."""
    _require_admin(authorization)

    result = await db.execute(select(Policy).where(Policy.id == policy_id))
    policy = result.scalar_one_or_none()

    if policy is None:
        raise HTTPException(status_code=404, detail="Policy not found")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(policy, field, value)

    await db.flush()
    await db.refresh(policy)

    logger.info("Updated policy id=%s", policy_id)
    return PolicyResponse.model_validate(policy)


@router.delete("/{policy_id}", status_code=204)
async def delete_policy(
    policy_id: uuid.UUID,
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Delete a policy."""
    _require_admin(authorization)

    result = await db.execute(select(Policy).where(Policy.id == policy_id))
    policy = result.scalar_one_or_none()

    if policy is None:
        raise HTTPException(status_code=404, detail="Policy not found")

    await db.delete(policy)
    await db.flush()

    logger.info("Deleted policy id=%s", policy_id)
