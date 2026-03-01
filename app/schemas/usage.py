"""Usage and cost reporting schemas."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel


class UsageSummaryResponse(BaseModel):
    id: uuid.UUID
    team_id: uuid.UUID
    model: str
    provider: str
    date: date
    total_requests: int
    total_tokens: int
    total_prompt_tokens: int
    total_completion_tokens: int
    total_cost_usd: float
    cache_hits: int

    model_config = {"from_attributes": True}


class UsageQueryParams(BaseModel):
    team_id: uuid.UUID | None = None
    model: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    limit: int = 100
    offset: int = 0


class CostBreakdown(BaseModel):
    team_id: uuid.UUID
    team_name: str
    model: str
    total_cost_usd: float
    total_tokens: int
    total_requests: int


class CostBreakdownResponse(BaseModel):
    costs: list[CostBreakdown]
    total_cost_usd: float


class TopModel(BaseModel):
    model: str
    total_requests: int
    total_tokens: int
    total_cost_usd: float


class TopModelsResponse(BaseModel):
    models: list[TopModel]


class BudgetStatus(BaseModel):
    team_id: uuid.UUID
    team_name: str
    token_budget_monthly: int
    tokens_used: int
    tokens_remaining: int
    budget_utilization_pct: float
    cost_this_month_usd: float


class BudgetStatusResponse(BaseModel):
    budgets: list[BudgetStatus]
