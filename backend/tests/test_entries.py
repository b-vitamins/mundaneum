"""
Entry router tests for Mundaneum API.
"""

from uuid import uuid4

import pytest


@pytest.mark.asyncio
async def test_get_entries_empty(client):
    """Test getting entries list (may be empty or have sample data)."""
    response = await client.get("/api/entries")

    assert response.status_code == 200
    data = response.json()

    # Should return a list
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_get_entry_not_found(client):
    """Test 404 response for non-existent entry."""
    fake_id = str(uuid4())
    response = await client.get(f"/api/entries/{fake_id}")

    assert response.status_code == 404
    data = response.json()
    assert "detail" in data
    assert fake_id in data["detail"]


@pytest.mark.asyncio
async def test_get_entry_invalid_uuid(client):
    """Test validation error for invalid UUID."""
    response = await client.get("/api/entries/not-a-uuid")

    assert response.status_code == 422
    data = response.json()
    assert "detail" in data


@pytest.mark.asyncio
async def test_get_entry_bibtex_not_found(client):
    """Test 404 for bibtex of non-existent entry."""
    fake_id = str(uuid4())
    response = await client.get(f"/api/entries/{fake_id}/bibtex")

    assert response.status_code == 404
