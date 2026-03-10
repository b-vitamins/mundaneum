from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Entry, EntryAuthor, Venue, VenueCategory
from app.routers.entity_common import (
    apply_sort,
    fetch_row_or_404,
    paginate,
    venue_entry_payload,
)
from app.schemas.entities import VenueDetail, VenueEntryItem, VenueListItem

router = APIRouter(prefix="/venues", tags=["venues"])


@router.get("", response_model=list[VenueListItem])
async def list_venues(
    limit: int = 100,
    offset: int = 0,
    sort_by: str = "name",
    sort_order: str = "asc",
    category: VenueCategory | None = None,
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

    query = apply_sort(
        query,
        sort_by=sort_by,
        sort_order=sort_order,
        sort_columns={
            "name": Venue.name,
            "entry_count": entry_count_subq.c.entry_count,
        },
    )
    query = paginate(query, limit=limit, offset=offset)

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

    row = await fetch_row_or_404(db, query, detail="Venue not found")

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
    query = paginate(query, limit=limit, offset=offset).options(
        selectinload(Entry.authors).selectinload(EntryAuthor.author)
    )

    result = await db.execute(query)
    entries = result.scalars().all()

    return [VenueEntryItem(**venue_entry_payload(entry)) for entry in entries]
