import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_venues(client: AsyncClient):
    response = await client.get("/api/venues")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_list_subjects(client: AsyncClient):
    response = await client.get("/api/subjects")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_list_topics(client: AsyncClient):
    response = await client.get("/api/topics")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
