"""
Shared helpers for entity-style routers.
"""

from collections.abc import Mapping
from typing import Any

from fastapi import HTTPException
from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Entry


def apply_sort(
    query: Select,
    *,
    sort_by: str,
    sort_order: str,
    sort_columns: Mapping[str, Any],
) -> Select:
    """Apply consistent null-aware ordering to a query."""
    default_column = next(iter(sort_columns.values()))
    order_column = sort_columns.get(sort_by, default_column)

    ordering = (
        order_column.desc().nullslast()
        if sort_order == "desc"
        else order_column.asc().nullsfirst()
    )
    return query.order_by(ordering)


def paginate(query: Select, *, limit: int, offset: int, max_limit: int = 200) -> Select:
    """Apply bounded pagination to a query."""
    bounded_limit = min(limit, max_limit)
    return query.offset(offset).limit(bounded_limit)


async def fetch_scalar_or_404(
    db: AsyncSession,
    statement: Select,
    *,
    detail: str,
):
    """Fetch a scalar result or raise a 404."""
    result = await db.execute(statement)
    value = result.scalar_one_or_none()
    if value is None:
        raise HTTPException(status_code=404, detail=detail)
    return value


async def fetch_row_or_404(
    db: AsyncSession,
    statement: Select,
    *,
    detail: str,
):
    """Fetch the first row result or raise a 404."""
    result = await db.execute(statement)
    row = result.first()
    if row is None:
        raise HTTPException(status_code=404, detail=detail)
    return row


def entry_authors(entry: Entry) -> list[str]:
    """Return author names in stored position order."""
    return [
        relation.author.name
        for relation in sorted(entry.authors, key=lambda relation: relation.position)
    ]


def entry_venue(entry: Entry) -> str | None:
    """Resolve the best available venue label for an entry."""
    if entry.venue:
        return entry.venue.name

    required = entry.required_fields or {}
    optional = entry.optional_fields or {}
    return (
        required.get("journal")
        or required.get("booktitle")
        or optional.get("journal")
        or optional.get("booktitle")
    )


def author_entry_payload(entry: Entry) -> dict[str, Any]:
    """Serialize an author-owned entry row."""
    return {
        "id": str(entry.id),
        "citation_key": entry.citation_key,
        "entry_type": entry.entry_type.value,
        "title": entry.title,
        "year": entry.year,
        "venue": entry_venue(entry),
        "read": entry.read,
    }


def entity_entry_payload(entry: Entry) -> dict[str, Any]:
    """Serialize a venue/subject/topic entry row."""
    return {
        "id": str(entry.id),
        "citation_key": entry.citation_key,
        "entry_type": entry.entry_type.value,
        "title": entry.title,
        "year": entry.year,
        "authors": entry_authors(entry),
        "venue": entry_venue(entry),
        "read": entry.read,
    }


def venue_entry_payload(entry: Entry) -> dict[str, Any]:
    """Serialize a venue entry row."""
    return {
        "id": str(entry.id),
        "citation_key": entry.citation_key,
        "entry_type": entry.entry_type.value,
        "title": entry.title,
        "year": entry.year,
        "authors": entry_authors(entry),
        "read": entry.read,
    }
