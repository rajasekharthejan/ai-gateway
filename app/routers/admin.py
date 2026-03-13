"""Admin endpoints for team and API key management."""

import hashlib
import logging
import secrets
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models.user import ApiKey, Team
from app.schemas.auth import (
    ApiKeyCreate,
    ApiKeyCreatedResponse,
    ApiKeyListResponse,
    ApiKeyResponse,
    TeamCreate,
    TeamListResponse,
    TeamResponse,
    TeamUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/teams", tags=["admin"])


def _require_admin(authorization: str | None) -> None:
    settings = get_settings()
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    token = authorization.removeprefix("Bearer ").strip()
    if token != settings.ADMIN_API_KEY:
        raise HTTPException(status_code=403, detail="Admin access required")


def _generate_api_key() -> str:
    """Generate a secure random API key with a recognizable prefix."""
    random_part = secrets.token_hex(32)
    return f"gw-{random_part}"


@router.post("", response_model=TeamResponse, status_code=201)
async def create_team(
    body: TeamCreate,
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Create a new team."""
    _require_admin(authorization)

    # Check for duplicate name
    existing = await db.execute(select(Team).where(Team.name == body.name))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Team '{body.name}' already exists")

    team = Team(
        id=uuid.uuid4(),
        name=body.name,
        description=body.description,
        token_budget_monthly=body.token_budget_monthly,
        rate_limit_rpm=body.rate_limit_rpm,
    )
    db.add(team)
    await db.flush()
    await db.refresh(team)

    logger.info("Created team id=%s name='%s'", team.id, team.name)
    return TeamResponse.model_validate(team)


@router.get("", response_model=TeamListResponse)
async def list_teams(
    is_active: bool | None = None,
    limit: int = 50,
    offset: int = 0,
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    """List all teams."""
    _require_admin(authorization)

    query = select(Team)
    count_query = select(func.count(Team.id))

    if is_active is not None:
        query = query.where(Team.is_active == is_active)
        count_query = count_query.where(Team.is_active == is_active)

    query = query.order_by(Team.created_at.desc()).offset(offset).limit(limit)

    result = await db.execute(query)
    teams = result.scalars().all()

    count_result = await db.execute(count_query)
    total = count_result.scalar_one()

    return TeamListResponse(
        teams=[TeamResponse.model_validate(t) for t in teams],
        total=total,
    )


@router.get("/{team_id}", response_model=TeamResponse)
async def get_team(
    team_id: uuid.UUID,
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Get a single team by ID."""
    _require_admin(authorization)

    result = await db.execute(select(Team).where(Team.id == team_id))
    team = result.scalar_one_or_none()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    return TeamResponse.model_validate(team)


@router.put("/{team_id}", response_model=TeamResponse)
async def update_team(
    team_id: uuid.UUID,
    body: TeamUpdate,
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Update a team."""
    _require_admin(authorization)

    result = await db.execute(select(Team).where(Team.id == team_id))
    team = result.scalar_one_or_none()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(team, field, value)

    await db.flush()
    await db.refresh(team)

    logger.info("Updated team id=%s", team_id)
    return TeamResponse.model_validate(team)


# --- API Key Management ---

@router.post("/{team_id}/keys", response_model=ApiKeyCreatedResponse, status_code=201)
async def create_api_key(
    team_id: uuid.UUID,
    body: ApiKeyCreate,
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Generate a new API key for a team.

    The full API key is returned only once in this response.
    """
    _require_admin(authorization)

    # Verify team exists
    team_result = await db.execute(select(Team).where(Team.id == team_id))
    if not team_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Team not found")

    raw_key = _generate_api_key()
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    key_prefix = raw_key[:11]  # "gw-" + first 8 hex chars

    api_key = ApiKey(
        id=uuid.uuid4(),
        team_id=team_id,
        key_hash=key_hash,
        key_prefix=key_prefix,
        name=body.name,
    )
    db.add(api_key)
    await db.flush()
    await db.refresh(api_key)

    logger.info(
        "Created API key id=%s prefix=%s for team=%s",
        api_key.id,
        key_prefix,
        team_id,
    )
    return ApiKeyCreatedResponse(
        id=api_key.id,
        team_id=api_key.team_id,
        key_prefix=api_key.key_prefix,
        name=api_key.name,
        api_key=raw_key,
        created_at=api_key.created_at,
    )


@router.get("/{team_id}/keys", response_model=ApiKeyListResponse)
async def list_api_keys(
    team_id: uuid.UUID,
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    """List all API keys for a team (without the full key)."""
    _require_admin(authorization)

    result = await db.execute(
        select(ApiKey)
        .where(ApiKey.team_id == team_id)
        .order_by(ApiKey.created_at.desc())
    )
    keys = result.scalars().all()

    count_result = await db.execute(
        select(func.count(ApiKey.id)).where(ApiKey.team_id == team_id)
    )
    total = count_result.scalar_one()

    return ApiKeyListResponse(
        keys=[ApiKeyResponse.model_validate(k) for k in keys],
        total=total,
    )


@router.delete("/{team_id}/keys/{key_id}", status_code=204)
async def revoke_api_key(
    team_id: uuid.UUID,
    key_id: uuid.UUID,
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Revoke (deactivate) an API key."""
    _require_admin(authorization)

    result = await db.execute(
        select(ApiKey).where(ApiKey.id == key_id, ApiKey.team_id == team_id)
    )
    api_key = result.scalar_one_or_none()

    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")

    api_key.is_active = False
    await db.flush()

    logger.info("Revoked API key id=%s for team=%s", key_id, team_id)
