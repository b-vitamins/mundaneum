"""
Entry router tests for Mundaneum API.
"""

from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.models import Author, Entry, EntryAuthor


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


@pytest.mark.asyncio
async def test_get_entries_supports_filters_and_total_header(
    client: AsyncClient,
    db_session,
):
    """Entry list should expose filterable browse results with a total header."""
    match_year = 300000 + (uuid4().int % 100000)
    matching_key = f"entries_filter_match_{uuid4().hex}"
    non_matching_key = f"entries_filter_other_{uuid4().hex}"

    db_session.add_all(
        [
            Entry(
                citation_key=matching_key,
                entry_type="book",
                title="Filtered Match",
                year=match_year,
                file_path="files/match.pdf",
                read=True,
                source_file="filters.bib",
            ),
            Entry(
                citation_key=non_matching_key,
                entry_type="article",
                title="Filtered Other",
                year=match_year - 1,
                file_path=None,
                read=False,
                source_file="filters.bib",
            ),
        ]
    )
    await db_session.commit()

    response = await client.get(
        "/api/entries",
        params={
            "entry_type": "book",
            "year_from": match_year,
            "year_to": match_year,
            "has_pdf": "true",
            "read": "true",
        },
    )

    assert response.status_code == 200
    assert response.headers["x-total-count"] == "1"

    data = response.json()
    assert [item["citation_key"] for item in data] == [matching_key]


@pytest.mark.asyncio
async def test_get_entry_exposes_author_refs(client: AsyncClient, db_session):
    """Entry detail payloads should provide author IDs for linkable UI."""
    suffix = uuid4().hex
    author = Author(name=f"Ada Lovelace {suffix}", normalized=f"ada lovelace {suffix}")
    entry = Entry(
        citation_key=f"entry_author_refs_{uuid4().hex}",
        entry_type="article",
        title="Author Ref Entry",
        source_file="authors.bib",
    )
    db_session.add_all([author, entry])
    await db_session.flush()
    db_session.add(
        EntryAuthor(entry_id=entry.id, author_id=author.id, position=0),
    )
    await db_session.commit()

    response = await client.get(f"/api/entries/{entry.id}")

    assert response.status_code == 200
    data = response.json()
    assert data["authors"] == [author.name]
    assert data["author_refs"] == [{"id": str(author.id), "name": author.name}]
