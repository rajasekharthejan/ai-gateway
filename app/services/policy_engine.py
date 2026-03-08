"""Policy evaluation engine for access control."""

import fnmatch
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.policy import Policy
from app.schemas.gateway import ChatCompletionRequest

logger = logging.getLogger(__name__)


class PolicyDecision:
    """Result of policy evaluation."""

    def __init__(self, allowed: bool, reason: str = "", policy_name: str = ""):
        self.allowed = allowed
        self.reason = reason
        self.policy_name = policy_name

    def __bool__(self) -> bool:
        return self.allowed


async def evaluate_policies(
    db: AsyncSession,
    team_id: str,
    request: ChatCompletionRequest,
) -> PolicyDecision:
    """Evaluate all active policies for a team and return allow/deny decision.

    Policy resolution:
    1. Fetch all active policies for the team + global policies (team_id IS NULL).
    2. Filter to policies whose resource pattern matches the requested model.
    3. Sort by priority descending (highest priority wins).
    4. First matching policy determines the outcome.
    5. If no policies match, default to ALLOW.
    """
    stmt = (
        select(Policy)
        .where(Policy.is_active.is_(True))
        .where(
            (Policy.team_id == team_id) | (Policy.team_id.is_(None))
        )
        .order_by(Policy.priority.desc())
    )

    result = await db.execute(stmt)
    policies = result.scalars().all()

    if not policies:
        return PolicyDecision(allowed=True, reason="No policies configured")

    model = request.model

    for policy in policies:
        # Check if the resource pattern matches the requested model
        if not _resource_matches(policy.resource, model):
            continue

        # Evaluate any additional conditions
        if not _evaluate_conditions(policy.conditions, request):
            continue

        if policy.policy_type == "deny":
            logger.info(
                "Policy '%s' DENIED model=%s for team=%s",
                policy.name,
                model,
                team_id,
            )
            return PolicyDecision(
                allowed=False,
                reason=f"Denied by policy: {policy.name}",
                policy_name=policy.name,
            )

        if policy.policy_type == "allow":
            logger.info(
                "Policy '%s' ALLOWED model=%s for team=%s",
                policy.name,
                model,
                team_id,
            )
            return PolicyDecision(
                allowed=True,
                reason=f"Allowed by policy: {policy.name}",
                policy_name=policy.name,
            )

    # Default: allow when no matching policy is found
    return PolicyDecision(allowed=True, reason="No matching policy; default allow")


def _resource_matches(pattern: str, model: str) -> bool:
    """Check if a resource pattern matches a model name using glob-style matching."""
    if pattern == "*":
        return True
    return fnmatch.fnmatch(model, pattern)


def _evaluate_conditions(
    conditions: dict | None,
    request: ChatCompletionRequest,
) -> bool:
    """Evaluate optional JSON conditions against the request.

    Supported conditions:
    - max_tokens: int - deny if request max_tokens exceeds this value
    - time_window: {"start_hour": int, "end_hour": int} - only applies during these UTC hours
    - allowed_models: list[str] - explicit list of allowed model names
    - denied_models: list[str] - explicit list of denied model names
    """
    if not conditions:
        return True

    # max_tokens condition
    max_tokens_limit = conditions.get("max_tokens")
    if max_tokens_limit is not None and request.max_tokens is not None:
        if request.max_tokens > max_tokens_limit:
            return True  # condition matches (will apply the policy)

    # time_window condition
    time_window = conditions.get("time_window")
    if time_window:
        now_hour = datetime.now(timezone.utc).hour
        start_hour = time_window.get("start_hour", 0)
        end_hour = time_window.get("end_hour", 24)
        if start_hour <= end_hour:
            if not (start_hour <= now_hour < end_hour):
                return False  # outside time window, condition doesn't match
        else:
            # Handles wrap-around (e.g., 22:00 to 06:00)
            if not (now_hour >= start_hour or now_hour < end_hour):
                return False

    # allowed_models / denied_models
    allowed_models = conditions.get("allowed_models")
    if allowed_models and request.model not in allowed_models:
        return True  # model not in allowlist, condition matches

    denied_models = conditions.get("denied_models")
    if denied_models and request.model in denied_models:
        return True  # model in denylist, condition matches

    return True
