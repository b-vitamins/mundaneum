"""
Search router tests for Mundaneum API.
"""

import pytest


@pytest.mark.asyncio
async def test_search_empty_query(client):
    """Test search with empty query."""
    response = await client.get("/api/search", params={"q": ""})

    assert response.status_code == 200
    data = response.json()
    assert "hits" in data
    assert "total" in data
    assert "processing_time_ms" in data


@pytest.mark.asyncio
async def test_search_with_query(client):
    """Test search with a query term."""
    response = await client.get("/api/search", params={"q": "test"})

    assert response.status_code == 200
    data = response.json()
    assert "hits" in data
    assert isinstance(data["hits"], list)


@pytest.mark.asyncio
async def test_search_with_filters(client):
    """Test search with filter parameters."""
    response = await client.get(
        "/api/search", params={"q": "physics", "has_pdf": "true", "read": "false"}
    )

    assert response.status_code == 200
    data = response.json()
    assert "hits" in data


@pytest.mark.asyncio
async def test_search_pagination(client):
    """Test search with pagination."""
    response = await client.get(
        "/api/search", params={"q": "*", "limit": 5, "offset": 0}
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["hits"]) <= 5
