"""
Subject API endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Entry, EntryAuthor, Subject


router = APIRouter(prefix="/subjects", tags=["subjects"])


# Response models
class SubjectListItem(BaseModel):
    """Response model for subject list items."""

    id: str
    slug: str
    name: str
    parent_slug: str | None = None
    display_name: str | None = None
    entry_count: int

    model_config = {"from_attributes": True}


class SubjectDetail(BaseModel):
    """Response model for subject detail view."""

    id: str
    slug: str
    name: str
    entry_count: int


class SubjectEntryItem(BaseModel):
    """Response model for entries in a subject."""

    id: str
    citation_key: str
    entry_type: str
    title: str
    year: int | None
    authors: list[str]
    venue: str | None
    read: bool

    model_config = {"from_attributes": True}


@router.get("", response_model=list[SubjectListItem])
async def list_subjects(
    limit: int = 100,
    offset: int = 0,
    sort_by: str = "name",
    sort_order: str = "asc",
    db: AsyncSession = Depends(get_db),
) -> list[SubjectListItem]:
    """
    List all subjects with entry counts.
    """
    # Subquery for entry counts
    entry_count_subq = (
        select(
            Subject.id,
            func.count(Entry.id).label("entry_count"),
        )
        .join(Entry, Subject.id == Entry.subject_id)
        .group_by(Subject.id)
        .subquery()
    )

    # Main query
    query = select(
        Subject,
        func.coalesce(entry_count_subq.c.entry_count, 0).label("entry_count"),
    ).outerjoin(entry_count_subq, Subject.id == entry_count_subq.c.id)

    # Apply sorting
    if sort_by == "entry_count":
        order_col = entry_count_subq.c.entry_count
    else:
        order_col = Subject.name

    if sort_order == "desc":
        query = query.order_by(order_col.desc().nullslast())
    else:
        query = query.order_by(order_col.asc().nullsfirst())

    query = query.offset(offset).limit(limit)

    result = await db.execute(query)
    rows = result.all()

    return [
        SubjectListItem(
            id=str(row.Subject.id),
            slug=row.Subject.slug,
            name=row.Subject.name,
            parent_slug=row.Subject.parent_slug,
            display_name=row.Subject.display_name,
            entry_count=row.entry_count,
        )
        for row in rows
    ]


@router.get("/{slug}", response_model=SubjectDetail)
async def get_subject(
    slug: str,
    db: AsyncSession = Depends(get_db),
) -> SubjectDetail:
    """Get subject details by slug."""
    # Get subject with entry count
    entry_count_subq = (
        select(func.count(Entry.id))
        .where(Entry.subject_id == Subject.id)
        .scalar_subquery()
    )

    query = select(
        Subject,
        entry_count_subq.label("entry_count"),
    ).where(Subject.slug == slug)

    result = await db.execute(query)
    row = result.first()

    if not row:
        raise HTTPException(status_code=404, detail="Subject not found")

    subject = row.Subject
    return SubjectDetail(
        id=str(subject.id),
        slug=subject.slug,
        name=subject.name,
        entry_count=row.entry_count,
    )


@router.get("/{slug}/entries", response_model=list[SubjectEntryItem])
async def get_subject_entries(
    slug: str,
    limit: int = 50,
    offset: int = 0,
    sort_by: str = "year",
    sort_order: str = "desc",
    db: AsyncSession = Depends(get_db),
) -> list[SubjectEntryItem]:
    """Get all entries in a specific subject."""
    # First check subject exists
    subject_check = await db.execute(select(Subject.id).where(Subject.slug == slug))
    subject_id = subject_check.scalar_one_or_none()
    if not subject_id:
        raise HTTPException(status_code=404, detail="Subject not found")

    # Get entries with eager loaded authors and venues
    # Note: Using selectinload for authors and venue to populate response model
    query = (
        select(Entry)
        .where(Entry.subject_id == subject_id)
        .options(
            selectinload(Entry.authors).selectinload(EntryAuthor.author),
            selectinload(Entry.venue),
        )
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
        SubjectEntryItem(
            id=str(e.id),
            citation_key=e.citation_key,
            entry_type=e.entry_type.value,
            title=e.title,
            year=e.year,
            authors=[a.author.name for a in e.authors],
            venue=e.venue.name
            if e.venue
            else (
                e.optional_fields.get("journal") or e.optional_fields.get("booktitle")
            ),
            read=e.read,
        )
        for e in entries
    ]
