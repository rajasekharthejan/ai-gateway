"""Cost calculation and usage summary tracking."""

import logging
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.usage import UsageSummary

logger = logging.getLogger(__name__)

# Pricing per 1M tokens (input, output) in USD
# Updated pricing as of 2024
MODEL_PRICING: dict[str, tuple[float, float]] = {
    # OpenAI models
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4-turbo": (10.00, 30.00),
    "gpt-4-0125-preview": (10.00, 30.00),
    "gpt-4-1106-preview": (10.00, 30.00),
    "gpt-4": (30.00, 60.00),
    "gpt-3.5-turbo": (0.50, 1.50),
    "gpt-3.5-turbo-0125": (0.50, 1.50),
    "gpt-3.5-turbo-1106": (1.00, 2.00),
    "o1": (15.00, 60.00),
    "o1-mini": (3.00, 12.00),
    "o1-preview": (15.00, 60.00),
    "o3-mini": (1.10, 4.40),
    # Anthropic Claude models (Bedrock pricing)
    "claude-3-5-sonnet": (3.00, 15.00),
    "claude-3-5-haiku": (0.80, 4.00),
    "claude-3-opus": (15.00, 75.00),
    "claude-3-sonnet": (3.00, 15.00),
    "claude-3-haiku": (0.25, 1.25),
}

# Default pricing for unknown models
DEFAULT_PRICING: tuple[float, float] = (10.00, 30.00)


def calculate_cost(
    model: str, prompt_tokens: int, completion_tokens: int
) -> float:
    """Calculate the cost in USD for a given model and token counts.

    Looks up the model in the pricing table, falling back to prefix matching
    and then the default pricing.

    Returns:
        Cost in USD (float).
    """
    pricing = _get_pricing(model)
    input_price_per_token = pricing[0] / 1_000_000
    output_price_per_token = pricing[1] / 1_000_000

    input_cost = prompt_tokens * input_price_per_token
    output_cost = completion_tokens * output_price_per_token
    total = round(input_cost + output_cost, 8)

    return total


def _get_pricing(model: str) -> tuple[float, float]:
    """Resolve pricing for a model name, with prefix-based fallback."""
    if model in MODEL_PRICING:
        return MODEL_PRICING[model]

    # Try prefix matching (e.g., "gpt-4o-2024-08-06" -> "gpt-4o")
    for known_model, pricing in MODEL_PRICING.items():
        if model.startswith(known_model):
            return pricing

    logger.warning("No pricing found for model '%s', using default", model)
    return DEFAULT_PRICING


def get_model_pricing_table() -> dict[str, dict[str, float]]:
    """Return the full pricing table for API consumers."""
    return {
        model: {"input_per_1m": p[0], "output_per_1m": p[1]}
        for model, p in MODEL_PRICING.items()
    }


async def update_usage_summary(
    db: AsyncSession,
    team_id: str,
    model: str,
    provider: str,
    prompt_tokens: int,
    completion_tokens: int,
    total_tokens: int,
    cost_usd: float,
    cache_hit: bool = False,
) -> None:
    """Upsert a daily usage summary row for the team/model/provider."""
    today = date.today()

    stmt = select(UsageSummary).where(
        UsageSummary.team_id == team_id,
        UsageSummary.model == model,
        UsageSummary.provider == provider,
        UsageSummary.date == today,
    )
    result = await db.execute(stmt)
    summary = result.scalar_one_or_none()

    if summary is None:
        summary = UsageSummary(
            id=uuid.uuid4(),
            team_id=team_id,
            model=model,
            provider=provider,
            date=today,
            total_requests=1,
            total_tokens=total_tokens,
            total_prompt_tokens=prompt_tokens,
            total_completion_tokens=completion_tokens,
            total_cost_usd=cost_usd,
            cache_hits=1 if cache_hit else 0,
        )
        db.add(summary)
    else:
        summary.total_requests += 1
        summary.total_tokens += total_tokens
        summary.total_prompt_tokens += prompt_tokens
        summary.total_completion_tokens += completion_tokens
        summary.total_cost_usd = round(summary.total_cost_usd + cost_usd, 8)
        if cache_hit:
            summary.cache_hits += 1
        summary.updated_at = datetime.now(timezone.utc)

    await db.flush()
