"""Usage and cost reporting endpoints."""

import logging
import uuid
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models.usage import UsageSummary
from app.models.user import Team
from app.schemas.usage import (
    BudgetStatus,
    BudgetStatusResponse,
    CostBreakdown,
    CostBreakdownResponse,
    TopModel,
    TopModelsResponse,
    UsageSummaryResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/usage", tags=["usage"])


def _require_admin(authorization: str | None) -> None:
    settings = get_settings()
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    token = authorization.removeprefix("Bearer ").strip()
    if token != settings.ADMIN_API_KEY:
        raise HTTPException(status_code=403, detail="Admin access required")


@router.get("", response_model=list[UsageSummaryResponse])
async def get_usage(
    team_id: uuid.UUID | None = None,
    model: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    limit: int = Query(default=100, le=1000),
    offset: int = Query(default=0, ge=0),
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Get usage summaries with optional filters."""
    _require_admin(authorization)

    query = select(UsageSummary)

    if team_id is not None:
        query = query.where(UsageSummary.team_id == team_id)
    if model is not None:
        query = query.where(UsageSummary.model == model)
    if start_date is not None:
        query = query.where(UsageSummary.date >= start_date)
    if end_date is not None:
        query = query.where(UsageSummary.date <= end_date)

    query = query.order_by(UsageSummary.date.desc()).offset(offset).limit(limit)

    result = await db.execute(query)
    rows = result.scalars().all()

    return [UsageSummaryResponse.model_validate(r) for r in rows]


@router.get("/costs", response_model=CostBreakdownResponse)
async def get_cost_breakdown(
    start_date: date | None = None,
    end_date: date | None = None,
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Get cost breakdown by team and model."""
    _require_admin(authorization)

    query = (
        select(
            UsageSummary.team_id,
            UsageSummary.model,
            func.sum(UsageSummary.total_cost_usd).label("total_cost_usd"),
            func.sum(UsageSummary.total_tokens).label("total_tokens"),
            func.sum(UsageSummary.total_requests).label("total_requests"),
        )
        .group_by(UsageSummary.team_id, UsageSummary.model)
    )

    if start_date:
        query = query.where(UsageSummary.date >= start_date)
    if end_date:
        query = query.where(UsageSummary.date <= end_date)

    query = query.order_by(func.sum(UsageSummary.total_cost_usd).desc())

    result = await db.execute(query)
    rows = result.all()

    # Resolve team names
    team_ids = {r.team_id for r in rows}
    team_names = {}
    if team_ids:
        team_result = await db.execute(
            select(Team.id, Team.name).where(Team.id.in_(team_ids))
        )
        team_names = {t.id: t.name for t in team_result.all()}

    costs = []
    total_cost = 0.0
    for r in rows:
        cost = CostBreakdown(
            team_id=r.team_id,
            team_name=team_names.get(r.team_id, "Unknown"),
            model=r.model,
            total_cost_usd=round(r.total_cost_usd, 6),
            total_tokens=r.total_tokens,
            total_requests=r.total_requests,
        )
        costs.append(cost)
        total_cost += r.total_cost_usd

    return CostBreakdownResponse(costs=costs, total_cost_usd=round(total_cost, 6))


@router.get("/top-models", response_model=TopModelsResponse)
async def get_top_models(
    start_date: date | None = None,
    end_date: date | None = None,
    limit: int = Query(default=10, le=50),
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Get the most-used models by request count."""
    _require_admin(authorization)

    query = (
        select(
            UsageSummary.model,
            func.sum(UsageSummary.total_requests).label("total_requests"),
            func.sum(UsageSummary.total_tokens).label("total_tokens"),
            func.sum(UsageSummary.total_cost_usd).label("total_cost_usd"),
        )
        .group_by(UsageSummary.model)
    )

    if start_date:
        query = query.where(UsageSummary.date >= start_date)
    if end_date:
        query = query.where(UsageSummary.date <= end_date)

    query = query.order_by(func.sum(UsageSummary.total_requests).desc()).limit(limit)

    result = await db.execute(query)
    rows = result.all()

    return TopModelsResponse(
        models=[
            TopModel(
                model=r.model,
                total_requests=r.total_requests,
                total_tokens=r.total_tokens,
                total_cost_usd=round(r.total_cost_usd, 6),
            )
            for r in rows
        ]
    )


@router.get("/budget-status", response_model=BudgetStatusResponse)
async def get_budget_status(
    team_id: uuid.UUID | None = None,
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Get budget status for all teams or a specific team."""
    _require_admin(authorization)

    # Get current month boundaries
    now = datetime.now(timezone.utc)
    month_start = date(now.year, now.month, 1)

    # Get teams
    team_query = select(Team).where(Team.is_active.is_(True))
    if team_id:
        team_query = team_query.where(Team.id == team_id)

    team_result = await db.execute(team_query)
    teams = team_result.scalars().all()

    budgets = []
    for team in teams:
        # Aggregate this month's usage for the team
        usage_query = (
            select(
                func.coalesce(func.sum(UsageSummary.total_tokens), 0).label("tokens_used"),
                func.coalesce(func.sum(UsageSummary.total_cost_usd), 0.0).label("cost"),
            )
            .where(
                UsageSummary.team_id == team.id,
                UsageSummary.date >= month_start,
            )
        )
        usage_result = await db.execute(usage_query)
        usage_row = usage_result.one()
        tokens_used = int(usage_row.tokens_used)
        cost = float(usage_row.cost)

        tokens_remaining = max(0, team.token_budget_monthly - tokens_used)
        utilization = (tokens_used / team.token_budget_monthly * 100) if team.token_budget_monthly > 0 else 0.0

        budgets.append(
            BudgetStatus(
                team_id=team.id,
                team_name=team.name,
                token_budget_monthly=team.token_budget_monthly,
                tokens_used=tokens_used,
                tokens_remaining=tokens_remaining,
                budget_utilization_pct=round(utilization, 2),
                cost_this_month_usd=round(cost, 6),
            )
        )

    return BudgetStatusResponse(budgets=budgets)
