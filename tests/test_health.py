"""Tests for health check endpoints."""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_health_liveness(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_health_ready(client: AsyncClient):
    response = await client.get("/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert "database" in data
    assert "redis" in data
