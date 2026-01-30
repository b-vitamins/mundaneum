"""
Collections router tests for Folio API.
"""

from uuid import uuid4

import pytest


@pytest.mark.asyncio
async def test_list_collections(client):
    """Test listing collections."""
    response = await client.get("/api/collections")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_create_collection(client):
    """Test creating a new collection."""
    collection_name = f"Test Collection {uuid4().hex[:8]}"
    response = await client.post("/api/collections", json={"name": collection_name})

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == collection_name
    assert "id" in data
    assert data["entry_count"] == 0


@pytest.mark.asyncio
async def test_create_duplicate_collection(client):
    """Test that duplicate collection names are rejected."""
    collection_name = f"Duplicate Test {uuid4().hex[:8]}"

    # Create first collection
    response1 = await client.post("/api/collections", json={"name": collection_name})
    assert response1.status_code == 201

    # Try to create duplicate
    response2 = await client.post("/api/collections", json={"name": collection_name})
    assert response2.status_code == 409  # Conflict


@pytest.mark.asyncio
async def test_get_collection_not_found(client):
    """Test 404 for non-existent collection."""
    fake_id = str(uuid4())
    response = await client.get(f"/api/collections/{fake_id}")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_collection(client):
    """Test deleting a collection."""
    # Create a collection to delete
    collection_name = f"To Delete {uuid4().hex[:8]}"
    create_response = await client.post(
        "/api/collections", json={"name": collection_name}
    )
    assert create_response.status_code == 201
    collection_id = create_response.json()["id"]

    # Delete it
    delete_response = await client.delete(f"/api/collections/{collection_id}")
    assert delete_response.status_code == 200

    # Verify it's gone
    get_response = await client.get(f"/api/collections/{collection_id}")
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_add_entry_to_collection_not_found(client):
    """Test adding non-existent entry to collection fails."""
    # Create a collection
    collection_name = f"Test Collection {uuid4().hex[:8]}"
    create_response = await client.post(
        "/api/collections", json={"name": collection_name}
    )
    collection_id = create_response.json()["id"]

    # Try to add non-existent entry
    fake_entry_id = str(uuid4())
    response = await client.post(
        f"/api/collections/{collection_id}/entries/{fake_entry_id}"
    )
    assert response.status_code == 404
