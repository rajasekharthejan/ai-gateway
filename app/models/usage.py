"""Usage summary model for aggregated daily statistics."""

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, Float, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class UsageSummary(Base):
    __tablename__ = "usage_summaries"
    __table_args__ = (
        UniqueConstraint("team_id", "model", "provider", "date", name="uq_usage_daily"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    team_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    model: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    total_requests: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_prompt_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_completion_tokens: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    total_cost_usd: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    cache_hits: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
