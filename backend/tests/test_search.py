"""
Search router tests for Mundaneum API.
"""

import pytest
from meilisearch.errors import MeilisearchCommunicationError
from sqlalchemy.exc import SQLAlchemyError

from app.schemas.search import (
    SearchResponse,
    SearchSort,
    SearchSortField,
    SearchSortOrder,
    SearchSource,
    SearchStatus,
)
from app.services import search_service


@pytest.mark.asyncio
async def test_search_empty_query(client):
    """Test search with empty query."""
    response = await client.get("/api/search", params={"q": ""})

    assert response.status_code == 200
    data = response.json()
    assert data["status"] in {"ok", "partial", "unavailable"}
    assert data["source"] in {"meilisearch", "database", "none"}
    assert "hits" in data
    assert "total" in data
    assert "processing_time_ms" in data
    assert "warnings" in data


@pytest.mark.asyncio
async def test_search_with_query(client):
    """Test search with a query term."""
    response = await client.get("/api/search", params={"q": "test"})

    assert response.status_code == 200
    data = response.json()
    assert "hits" in data
    assert isinstance(data["hits"], list)
    assert data["status"] in {"ok", "partial", "unavailable"}


@pytest.mark.asyncio
async def test_search_with_filters(client):
    """Test search with filter parameters."""
    response = await client.get(
        "/api/search", params={"q": "physics", "has_pdf": "true", "read": "false"}
    )

    assert response.status_code == 200
    data = response.json()
    assert "hits" in data
    assert data["status"] in {"ok", "partial", "unavailable"}


@pytest.mark.asyncio
async def test_search_pagination(client):
    """Test search with pagination."""
    response = await client.get(
        "/api/search", params={"q": "*", "limit": 5, "offset": 0}
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["hits"]) <= 5


@pytest.mark.asyncio
async def test_search_reports_partial_when_degraded(client, monkeypatch):
    """Search should expose degraded fallback state instead of empty success."""

    def fake_meili(_query):
        raise MeilisearchCommunicationError("meili down")

    async def fake_database_search(_db, _query):
        return SearchResponse(
            status=SearchStatus.PARTIAL,
            source=SearchSource.DATABASE,
            hits=[],
            total=0,
            processing_time_ms=0,
        )

    monkeypatch.setattr(search_service, "execute_meilisearch", fake_meili)
    monkeypatch.setattr(search_service, "execute_database_search", fake_database_search)

    response = await client.get("/api/search", params={"q": "test"})

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "partial"
    assert data["source"] == "database"
    assert data["warnings"][0]["code"] == "meilisearch_unavailable"


@pytest.mark.asyncio
async def test_search_reports_unavailable_when_all_backends_fail(client, monkeypatch):
    """Search should report full unavailability explicitly."""

    def fake_meili(_query):
        raise MeilisearchCommunicationError("meili down")

    async def fake_database_search(_db, _query):
        raise SQLAlchemyError("db fallback down")

    monkeypatch.setattr(search_service, "execute_meilisearch", fake_meili)
    monkeypatch.setattr(search_service, "execute_database_search", fake_database_search)

    response = await client.get("/api/search", params={"q": "test"})

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "unavailable"
    assert data["source"] == "none"
    assert data["hits"] == []


def test_search_sort_defaults_to_created_at_desc():
    """Search sort should have a stable default policy."""
    sort = SearchSort.from_raw(None)
    assert sort.field == SearchSortField.CREATED_AT
    assert sort.order == SearchSortOrder.DESC
    assert sort.meilisearch_value == "created_at:desc"


def test_search_sort_parses_supported_field_and_order():
    """Search sort should normalize valid sort strings."""
    sort = SearchSort.from_raw("year:asc")
    assert sort.field == SearchSortField.YEAR
    assert sort.order == SearchSortOrder.ASC
    assert sort.meilisearch_value == "year:asc"


def test_search_sort_falls_back_for_unknown_values():
    """Unsupported sort parts should degrade to the default search policy."""
    sort = SearchSort.from_raw("citations:up")
    assert sort.field == SearchSortField.CREATED_AT
    assert sort.order == SearchSortOrder.DESC
