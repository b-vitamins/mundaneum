"""
Tests for admin router (backup/restore functionality).
"""

import uuid

import pytest
from httpx import AsyncClient

from app.models import Collection, CollectionEntry, Entry


def unique_id() -> str:
    """Generate unique ID for test isolation."""
    return str(uuid.uuid4())[:8]


@pytest.mark.asyncio
async def test_health_endpoint(client: AsyncClient):
    """Test detailed health endpoint."""
    response = await client.get("/api/admin/health")
    assert response.status_code == 200

    data = response.json()
    assert "status" in data
    assert "database" in data
    assert "search" in data
    assert "bib_directory" in data
    assert "bib_files_count" in data


@pytest.mark.asyncio
async def test_export_empty_state(client: AsyncClient):
    """Test export returns valid structure."""
    response = await client.get("/api/admin/export")
    assert response.status_code == 200

    data = response.json()
    assert data["version"] == "1.0"
    assert "exported_at" in data
    assert isinstance(data["entries"], list)
    assert isinstance(data["collections"], list)


@pytest.mark.asyncio
async def test_export_with_entries(client: AsyncClient, db_session):
    """Test export includes entries with user state."""
    key = f"export_test_{unique_id()}"

    # Create entry with notes
    entry = Entry(
        citation_key=key,
        entry_type="article",
        title="Export Test Paper",
        source_file="test.bib",
        notes="Important paper",
        read=True,
    )
    db_session.add(entry)
    await db_session.commit()

    response = await client.get("/api/admin/export")
    assert response.status_code == 200

    data = response.json()
    assert len(data["entries"]) >= 1

    exported = next((e for e in data["entries"] if e["citation_key"] == key), None)
    assert exported is not None
    assert exported["notes"] == "Important paper"
    assert exported["read"] is True


@pytest.mark.asyncio
async def test_export_with_collections(client: AsyncClient, db_session):
    """Test export includes collections."""
    key = f"coll_test_{unique_id()}"
    coll_name = f"Test Collection {unique_id()}"

    # Create entry
    entry = Entry(
        citation_key=key,
        entry_type="article",
        title="Collection Test Paper",
        source_file="test.bib",
    )
    db_session.add(entry)
    await db_session.flush()

    # Create collection
    collection = Collection(name=coll_name)
    db_session.add(collection)
    await db_session.flush()

    # Add entry to collection
    ce = CollectionEntry(collection_id=collection.id, entry_id=entry.id, sort_order=0)
    db_session.add(ce)
    await db_session.commit()

    response = await client.get("/api/admin/export")
    assert response.status_code == 200

    data = response.json()
    exported_coll = next(
        (c for c in data["collections"] if c["name"] == coll_name), None
    )
    assert exported_coll is not None
    assert key in exported_coll["entry_keys"]


@pytest.mark.asyncio
async def test_import_empty_data(client: AsyncClient):
    """Test import with empty data."""
    import_data = {
        "version": "1.0",
        "exported_at": "2024-01-01T00:00:00+00:00",
        "entries": [],
        "collections": [],
    }

    response = await client.post("/api/admin/import", json=import_data)
    assert response.status_code == 200

    data = response.json()
    assert data["entries_updated"] == 0
    assert data["collections_created"] == 0


@pytest.mark.asyncio
async def test_import_restores_entry_state(client: AsyncClient, db_session):
    """Test import restores entry notes and read status."""
    key = f"restore_test_{unique_id()}"

    # Create entry
    entry = Entry(
        citation_key=key,
        entry_type="article",
        title="Test Paper",
        source_file="test.bib",
        notes=None,
        read=False,
    )
    db_session.add(entry)
    await db_session.commit()

    import_data = {
        "version": "1.0",
        "exported_at": "2024-01-01T00:00:00+00:00",
        "entries": [{"citation_key": key, "notes": "Restored notes", "read": True}],
        "collections": [],
    }

    response = await client.post("/api/admin/import", json=import_data)
    assert response.status_code == 200

    data = response.json()
    assert data["entries_updated"] == 1

    # Verify entry was updated
    await db_session.refresh(entry)
    assert entry.notes == "Restored notes"
    assert entry.read is True


@pytest.mark.asyncio
async def test_import_creates_collection(client: AsyncClient, db_session):
    """Test import creates collections."""
    key = f"coll_import_{unique_id()}"
    coll_name = f"Imported Coll {unique_id()}"

    # Create matching entry
    entry = Entry(
        citation_key=key,
        entry_type="article",
        title="Test Paper",
        source_file="test.bib",
    )
    db_session.add(entry)
    await db_session.commit()

    import_data = {
        "version": "1.0",
        "exported_at": "2024-01-01T00:00:00+00:00",
        "entries": [],
        "collections": [
            {
                "name": coll_name,
                "description": "A collection from import",
                "sort_order": 0,
                "entry_keys": [key],
            }
        ],
    }

    response = await client.post("/api/admin/import", json=import_data)
    assert response.status_code == 200

    data = response.json()
    assert data["collections_created"] == 1


@pytest.mark.asyncio
async def test_import_handles_missing_entries(client: AsyncClient):
    """Test import handles references to non-existent entries."""
    key = f"nonexistent_{unique_id()}"

    import_data = {
        "version": "1.0",
        "exported_at": "2024-01-01T00:00:00+00:00",
        "entries": [{"citation_key": key, "notes": "Test", "read": True}],
        "collections": [],
    }

    response = await client.post("/api/admin/import", json=import_data)
    assert response.status_code == 200

    data = response.json()
    assert data["entries_skipped"] == 1
    assert any(key in err for err in data["errors"])
