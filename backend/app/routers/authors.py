from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Author, Entry, EntryAuthor
from app.routers.entity_common import (
    apply_sort,
    author_entry_payload,
    fetch_row_or_404,
    paginate,
)
from app.schemas.entities import AuthorDetail, AuthorEntryItem, AuthorListItem

router = APIRouter(prefix="/authors", tags=["authors"])


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

    query = apply_sort(
        query,
        sort_by=sort_by,
        sort_order=sort_order,
        sort_columns={
            "name": Author.name,
            "entry_count": entry_count_subq.c.entry_count,
        },
    )
    query = paginate(query, limit=limit, offset=offset)

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

    row = await fetch_row_or_404(db, query, detail="Author not found")

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
    result = await db.execute(select(Author.id).where(Author.id == author_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Author not found")

    # Get entries via join
    query = (
        select(Entry)
        .join(EntryAuthor, Entry.id == EntryAuthor.entry_id)
        .where(EntryAuthor.author_id == author_id)
    )

    query = apply_sort(
        query,
        sort_by=sort_by,
        sort_order=sort_order,
        sort_columns={
            "title": Entry.title,
            "created_at": Entry.created_at,
            "year": Entry.year,
        },
    )
    query = paginate(query, limit=limit, offset=offset)

    result = await db.execute(query)
    entries = result.scalars().all()

    return [AuthorEntryItem(**author_entry_payload(entry)) for entry in entries]
