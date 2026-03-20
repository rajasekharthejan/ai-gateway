"""Shared test fixtures."""

import asyncio
import hashlib
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import Settings, get_settings
from app.database import Base, get_db
from app.cache import get_redis
from app.main import app
from app.models.user import ApiKey, Team


# Use SQLite for tests (in-memory)
TEST_DATABASE_URL = "sqlite+aiosqlite:///./test.db"


def get_test_settings() -> Settings:
    return Settings(
        DATABASE_URL=TEST_DATABASE_URL,
        REDIS_URL="redis://localhost:6379/15",
        OPENAI_API_KEY="test-key",
        ADMIN_API_KEY="test-admin-key",
        CACHE_ENABLED=False,
        LOG_LEVEL="WARNING",
    )


test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionLocal = async_sessionmaker(
    test_engine, class_=AsyncSession, expire_on_commit=False
)


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a clean database session for each test."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestSessionLocal() as session:
        yield session

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create a test HTTP client with overridden dependencies."""

    async def override_get_db():
        try:
            yield db_session
            await db_session.commit()
        except Exception:
            await db_session.rollback()
            raise

    async def override_get_redis():
        yield None  # No Redis in tests

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = override_get_redis
    app.dependency_overrides[get_settings] = get_test_settings

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def test_team(db_session: AsyncSession) -> Team:
    """Create a test team."""
    team = Team(
        id=uuid.uuid4(),
        name="Test Team",
        description="A team for testing",
        token_budget_monthly=1_000_000,
        rate_limit_rpm=60,
    )
    db_session.add(team)
    await db_session.flush()
    return team


@pytest_asyncio.fixture
async def test_api_key(db_session: AsyncSession, test_team: Team) -> tuple[str, ApiKey]:
    """Create a test API key, returning (raw_key, ApiKey model)."""
    raw_key = "gw-test1234567890abcdef1234567890abcdef1234567890abcdef1234567890ab"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

    api_key = ApiKey(
        id=uuid.uuid4(),
        team_id=test_team.id,
        key_hash=key_hash,
        key_prefix=raw_key[:11],
        name="Test Key",
    )
    db_session.add(api_key)
    await db_session.flush()
    return raw_key, api_key


ADMIN_KEY = "test-admin-key"
