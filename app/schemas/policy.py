"""Policy CRUD schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class PolicyCreate(BaseModel):
    team_id: uuid.UUID | None = None
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    policy_type: str = Field(..., pattern=r"^(allow|deny)$")
    resource: str = Field(..., min_length=1, max_length=255)
    conditions: dict[str, Any] | None = None
    priority: int = Field(default=0, ge=0, le=1000)
    is_active: bool = True


class PolicyUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    policy_type: str | None = Field(default=None, pattern=r"^(allow|deny)$")
    resource: str | None = Field(default=None, min_length=1, max_length=255)
    conditions: dict[str, Any] | None = None
    priority: int | None = Field(default=None, ge=0, le=1000)
    is_active: bool | None = None


class PolicyResponse(BaseModel):
    id: uuid.UUID
    team_id: uuid.UUID | None
    name: str
    description: str | None
    policy_type: str
    resource: str
    conditions: dict[str, Any] | None
    priority: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PolicyListResponse(BaseModel):
    policies: list[PolicyResponse]
    total: int
