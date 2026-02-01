"""
Venue API endpoints.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Entry, Venue, VenueCategory


router = APIRouter(prefix="/venues", tags=["venues"])


# Response models
class VenueListItem(BaseModel):
    """Response model for venue list items."""

    id: str
    slug: str
    name: str
    category: str
    entry_count: int

    model_config = {"from_attributes": True}


class VenueDetail(BaseModel):
    """Response model for venue detail view."""

    id: str
    slug: str
    name: str
    category: str
    aliases: list[str]
    url: Optional[str]
    entry_count: int


class VenueEntryItem(BaseModel):
    """Response model for entries in a venue."""

    id: str
    citation_key: str
    entry_type: str
    title: str
    year: int | None
    authors: list[str]
    read: bool

    model_config = {"from_attributes": True}


@router.get("", response_model=list[VenueListItem])
async def list_venues(
    limit: int = 100,
    offset: int = 0,
    sort_by: str = "name",
    sort_order: str = "asc",
    category: Optional[VenueCategory] = None,
    db: AsyncSession = Depends(get_db),
) -> list[VenueListItem]:
    """
    List all venues with entry counts.
    """
    # Subquery for entry counts
    entry_count_subq = (
        select(
            Venue.id,
            func.count(Entry.id).label("entry_count"),
        )
        .join(Entry, Venue.id == Entry.venue_id)
        .group_by(Venue.id)
        .subquery()
    )

    # Main query
    query = select(
        Venue,
        func.coalesce(entry_count_subq.c.entry_count, 0).label("entry_count"),
    ).outerjoin(entry_count_subq, Venue.id == entry_count_subq.c.id)

    # Filter by category
    if category:
        query = query.where(Venue.category == category)

    # Apply sorting
    if sort_by == "entry_count":
        order_col = entry_count_subq.c.entry_count
    else:
        order_col = Venue.name

    if sort_order == "desc":
        query = query.order_by(order_col.desc().nullslast())
    else:
        query = query.order_by(order_col.asc().nullsfirst())

    query = query.offset(offset).limit(limit)

    result = await db.execute(query)
    rows = result.all()

    return [
        VenueListItem(
            id=str(row.Venue.id),
            slug=row.Venue.slug,
            name=row.Venue.name,
            category=row.Venue.category.value,
            entry_count=row.entry_count,
        )
        for row in rows
    ]


@router.get("/{slug}", response_model=VenueDetail)
async def get_venue(
    slug: str,
    db: AsyncSession = Depends(get_db),
) -> VenueDetail:
    """Get venue details by slug."""
    # Get venue with entry count
    entry_count_subq = (
        select(func.count(Entry.id)).where(Entry.venue_id == Venue.id).scalar_subquery()
    )

    query = select(
        Venue,
        entry_count_subq.label("entry_count"),
    ).where(Venue.slug == slug)

    result = await db.execute(query)
    row = result.first()

    if not row:
        raise HTTPException(status_code=404, detail="Venue not found")

    venue = row.Venue
    return VenueDetail(
        id=str(venue.id),
        slug=venue.slug,
        name=venue.name,
        category=venue.category.value,
        aliases=venue.aliases,
        url=venue.url,
        entry_count=row.entry_count,
    )


@router.get("/{slug}/entries", response_model=list[VenueEntryItem])
async def get_venue_entries(
    slug: str,
    limit: int = 50,
    offset: int = 0,
    sort_by: str = "year",
    sort_order: str = "desc",
    db: AsyncSession = Depends(get_db),
) -> list[VenueEntryItem]:
    """Get all entries in a specific venue."""
    # First check venue exists
    venue_check = await db.execute(select(Venue.id).where(Venue.slug == slug))
    venue_id = venue_check.scalar_one_or_none()
    if not venue_id:
        raise HTTPException(status_code=404, detail="Venue not found")

    # Get entries
    query = select(Entry).where(Entry.venue_id == venue_id)

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

    # Eager load authors
    from app.models import EntryAuthor
    from sqlalchemy.orm import selectinload, joinedload

    query = query.options(selectinload(Entry.authors).joinedload(EntryAuthor.author))

    result = await db.execute(query)
    entries = result.scalars().all()

    return [
        VenueEntryItem(
            id=str(e.id),
            citation_key=e.citation_key,
            entry_type=e.entry_type.value,
            title=e.title,
            year=e.year,
            authors=[a.author.name for a in e.authors],  # Assumes authors loaded
            read=e.read,
        )
        for e in entries
    ]
