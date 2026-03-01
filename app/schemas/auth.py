"""Authentication and team management schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class TeamCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    token_budget_monthly: int = Field(default=1_000_000, ge=0)
    rate_limit_rpm: int = Field(default=60, ge=1, le=10_000)


class TeamUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    is_active: bool | None = None
    token_budget_monthly: int | None = Field(default=None, ge=0)
    rate_limit_rpm: int | None = Field(default=None, ge=1, le=10_000)


class TeamResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    is_active: bool
    token_budget_monthly: int
    rate_limit_rpm: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TeamListResponse(BaseModel):
    teams: list[TeamResponse]
    total: int


class ApiKeyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)


class ApiKeyResponse(BaseModel):
    id: uuid.UUID
    team_id: uuid.UUID
    key_prefix: str
    name: str
    is_active: bool
    last_used_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ApiKeyCreatedResponse(BaseModel):
    """Returned only on creation; includes the full key (shown once)."""
    id: uuid.UUID
    team_id: uuid.UUID
    key_prefix: str
    name: str
    api_key: str  # full key, only shown once
    created_at: datetime

    model_config = {"from_attributes": True}


class ApiKeyListResponse(BaseModel):
    keys: list[ApiKeyResponse]
    total: int
