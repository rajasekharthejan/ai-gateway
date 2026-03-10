"""Audit logging service for gateway requests."""

import json
import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.audit import AuditLog

logger = logging.getLogger(__name__)


def _truncate(obj: dict | None, max_chars: int) -> dict | None:
    """Truncate a dict's JSON representation to max_chars."""
    if obj is None:
        return None
    try:
        text = json.dumps(obj, separators=(",", ":"))
        if len(text) <= max_chars:
            return obj
        truncated_text = text[:max_chars]
        return {"_truncated": True, "data": truncated_text}
    except (TypeError, ValueError):
        return {"_error": "Could not serialize for audit"}


async def log_request(
    db: AsyncSession,
    team_id: str | None,
    api_key_id: str | None,
    request_id: str,
    model: str,
    provider: str,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    total_tokens: int = 0,
    cost_usd: float = 0.0,
    latency_ms: int = 0,
    status: str = "success",
    error_message: str | None = None,
    request_body: dict | None = None,
    response_body: dict | None = None,
    ip_address: str | None = None,
) -> AuditLog:
    """Write an audit log entry for a gateway request.

    Bodies are truncated to the configured maximum to prevent oversized rows.
    """
    settings = get_settings()
    max_chars = settings.AUDIT_BODY_TRUNCATE_CHARS

    truncated_request = None
    if settings.AUDIT_LOG_REQUEST_BODY and request_body:
        truncated_request = _truncate(request_body, max_chars)

    truncated_response = None
    if settings.AUDIT_LOG_RESPONSE_BODY and response_body:
        truncated_response = _truncate(response_body, max_chars)

    audit_entry = AuditLog(
        id=uuid.uuid4(),
        team_id=team_id,
        api_key_id=api_key_id,
        request_id=request_id,
        model=model,
        provider=provider,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        cost_usd=cost_usd,
        latency_ms=latency_ms,
        status=status,
        error_message=error_message,
        request_body=truncated_request,
        response_body=truncated_response,
        ip_address=ip_address,
    )

    db.add(audit_entry)
    await db.flush()

    logger.info(
        "Audit log: request_id=%s model=%s provider=%s status=%s tokens=%d cost=%.6f latency=%dms",
        request_id,
        model,
        provider,
        status,
        total_tokens,
        cost_usd,
        latency_ms,
    )

    return audit_entry
