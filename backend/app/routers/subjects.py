from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Entry, EntryAuthor, Subject
from app.routers.entity_common import (
    apply_sort,
    entity_entry_payload,
    fetch_row_or_404,
    paginate,
)
from app.schemas.entities import SubjectDetail, SubjectEntryItem, SubjectListItem


router = APIRouter(prefix="/subjects", tags=["subjects"])


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

    query = apply_sort(
        query,
        sort_by=sort_by,
        sort_order=sort_order,
        sort_columns={
            "name": Subject.name,
            "entry_count": entry_count_subq.c.entry_count,
        },
    )
    query = paginate(query, limit=limit, offset=offset)

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

    row = await fetch_row_or_404(db, query, detail="Subject not found")

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

    return [SubjectEntryItem(**entity_entry_payload(entry)) for entry in entries]
