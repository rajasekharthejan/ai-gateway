"""Tests for admin team and API key management endpoints."""

import pytest
import pytest_asyncio
from httpx import AsyncClient

from tests.conftest import ADMIN_KEY


@pytest.mark.asyncio
async def test_create_team(client: AsyncClient):
    response = await client.post(
        "/v1/teams",
        json={"name": "Engineering", "description": "Core eng team"},
        headers={"X-Admin-Key": ADMIN_KEY},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Engineering"
    assert data["is_active"] is True
    assert "id" in data


@pytest.mark.asyncio
async def test_create_team_duplicate_name(client: AsyncClient):
    headers = {"X-Admin-Key": ADMIN_KEY}
    await client.post("/v1/teams", json={"name": "Duplicate"}, headers=headers)
    response = await client.post("/v1/teams", json={"name": "Duplicate"}, headers=headers)
    assert response.status_code in (400, 409, 500)


@pytest.mark.asyncio
async def test_list_teams(client: AsyncClient):
    headers = {"X-Admin-Key": ADMIN_KEY}
    await client.post("/v1/teams", json={"name": "Team A"}, headers=headers)
    await client.post("/v1/teams", json={"name": "Team B"}, headers=headers)

    response = await client.get("/v1/teams", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 2


@pytest.mark.asyncio
async def test_create_api_key(client: AsyncClient, test_team):
    headers = {"X-Admin-Key": ADMIN_KEY}
    response = await client.post(
        f"/v1/teams/{test_team.id}/keys",
        json={"name": "Production Key"},
        headers=headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert "key" in data  # Full key returned on creation
    assert data["key"].startswith("gw-")


@pytest.mark.asyncio
async def test_admin_requires_key(client: AsyncClient):
    response = await client.get("/v1/teams")
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_admin_rejects_bad_key(client: AsyncClient):
    response = await client.get(
        "/v1/teams",
        headers={"X-Admin-Key": "wrong-key"},
    )
    assert response.status_code in (401, 403)
