"""
Authors API endpoints.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Author, Entry, EntryAuthor


router = APIRouter(prefix="/authors", tags=["authors"])


# Response models
class AuthorListItem(BaseModel):
    """Response model for author list items."""

    id: str
    name: str
    entry_count: int

    model_config = {"from_attributes": True}


class AuthorDetail(BaseModel):
    """Response model for author detail view."""

    id: str
    name: str
    entry_count: int


class AuthorEntryItem(BaseModel):
    """Response model for entries by an author."""

    id: str
    citation_key: str
    entry_type: str
    title: str
    year: int | None
    venue: str | None
    read: bool

    model_config = {"from_attributes": True}


@router.get("", response_model=list[AuthorListItem])
async def list_authors(
    limit: int = 100,
    offset: int = 0,
    sort_by: str = "name",
    sort_order: str = "asc",
    db: AsyncSession = Depends(get_db),
) -> list[AuthorListItem]:
    """
    List all authors with entry counts.

    Supports sorting by name or entry_count.
    """
    # Subquery for entry counts
    entry_count_subq = (
        select(
            EntryAuthor.author_id,
            func.count(EntryAuthor.entry_id).label("entry_count"),
        )
        .group_by(EntryAuthor.author_id)
        .subquery()
    )

    # Main query with left join for counts
    query = select(
        Author.id,
        Author.name,
        func.coalesce(entry_count_subq.c.entry_count, 0).label("entry_count"),
    ).outerjoin(entry_count_subq, Author.id == entry_count_subq.c.author_id)

    # Apply sorting
    if sort_by == "entry_count":
        order_col = entry_count_subq.c.entry_count
    else:
        order_col = Author.name

    if sort_order == "desc":
        query = query.order_by(order_col.desc().nullslast())
    else:
        query = query.order_by(order_col.asc().nullsfirst())

    query = query.offset(offset).limit(limit)

    result = await db.execute(query)
    rows = result.all()

    return [
        AuthorListItem(
            id=str(row.id),
            name=row.name,
            entry_count=row.entry_count or 0,
        )
        for row in rows
    ]


@router.get("/{author_id}", response_model=AuthorDetail)
async def get_author(
    author_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> AuthorDetail:
    """Get author details by ID."""
    # Get author with entry count
    entry_count_subq = (
        select(func.count(EntryAuthor.entry_id))
        .where(EntryAuthor.author_id == author_id)
        .scalar_subquery()
    )

    query = select(
        Author.id,
        Author.name,
        entry_count_subq.label("entry_count"),
    ).where(Author.id == author_id)

    result = await db.execute(query)
    row = result.first()

    if not row:
        raise HTTPException(status_code=404, detail="Author not found")

    return AuthorDetail(
        id=str(row.id),
        name=row.name,
        entry_count=row.entry_count or 0,
    )


@router.get("/{author_id}/entries", response_model=list[AuthorEntryItem])
async def get_author_entries(
    author_id: UUID,
    limit: int = 50,
    offset: int = 0,
    sort_by: str = "year",
    sort_order: str = "desc",
    db: AsyncSession = Depends(get_db),
) -> list[AuthorEntryItem]:
    """Get all entries by a specific author."""
    # First check author exists
    author_check = await db.execute(select(Author.id).where(Author.id == author_id))
    if not author_check.first():
        raise HTTPException(status_code=404, detail="Author not found")

    # Get entries via join
    query = (
        select(Entry)
        .join(EntryAuthor, Entry.id == EntryAuthor.entry_id)
        .where(EntryAuthor.author_id == author_id)
    )

    # Apply sorting
    if sort_by == "title":
        order_col = Entry.title
    elif sort_by == "created_at":
        order_col = Entry.created_at
    else:  # default to year
        order_col = Entry.year

    if sort_order == "desc":
        query = query.order_by(order_col.desc().nullslast())
    else:
        query = query.order_by(order_col.asc().nullsfirst())

    query = query.offset(offset).limit(limit)

    result = await db.execute(query)
    entries = result.scalars().all()

    return [
        AuthorEntryItem(
            id=str(e.id),
            citation_key=e.citation_key,
            entry_type=e.entry_type.value,
            title=e.title,
            year=e.year,
            venue=e.optional_fields.get("journal")
            or e.optional_fields.get("booktitle"),
            read=e.read,
        )
        for e in entries
    ]
