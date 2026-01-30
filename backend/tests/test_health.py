"""
Health endpoint tests for Folio API.
"""

import pytest


@pytest.mark.asyncio
async def test_health_endpoint_returns_status(client):
    """Test that /health endpoint returns expected structure."""
    response = await client.get("/health")

    assert response.status_code == 200
    data = response.json()

    assert "status" in data
    assert "version" in data
    assert "services" in data
    assert data["status"] in ("ok", "degraded", "unhealthy")


@pytest.mark.asyncio
async def test_stats_endpoint(client):
    """Test that /api/stats endpoint returns counts."""
    response = await client.get("/api/stats")

    assert response.status_code == 200
    data = response.json()

    # Should return numeric counts (may be 0 without DB)
    assert "entries" in data
    assert "authors" in data
    assert "collections" in data
