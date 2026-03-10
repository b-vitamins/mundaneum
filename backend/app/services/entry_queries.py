"""
Entry query helpers.
"""

from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.exceptions import NotFoundError
from app.models import Entry, EntryAuthor
from app.routers.entity_common import apply_sort, paginate

ENTRY_SORT_COLUMNS = {
    "title": Entry.title,
    "year": Entry.year,
    "created_at": Entry.created_at,
    "updated_at": Entry.updated_at,
}


def entry_load_options(statement: Select) -> Select:
    """Attach the eager-loading required by entry serializers."""
    return statement.options(
        selectinload(Entry.authors).selectinload(EntryAuthor.author),
        selectinload(Entry.venue),
    )


async def list_entries(
    db: AsyncSession,
    *,
    limit: int,
    offset: int,
    sort_by: str,
    sort_order: str,
) -> list[Entry]:
    """Fetch a paginated entry list with serializer-friendly relationships."""
    query = entry_load_options(select(Entry))
    query = apply_sort(
        query,
        sort_by=sort_by,
        sort_order=sort_order,
        sort_columns=ENTRY_SORT_COLUMNS,
    )
    query = paginate(query, limit=limit, offset=offset)
    result = await db.execute(query)
    return result.scalars().all()


async def get_entry(
    db: AsyncSession,
    entry_id: UUID,
    *,
    include_relationships: bool = True,
) -> Entry:
    """Load a single entry or raise a typed 404."""
    query = select(Entry).where(Entry.id == entry_id)
    if include_relationships:
        query = entry_load_options(query)

    result = await db.execute(query)
    entry = result.scalar_one_or_none()
    if not entry:
        raise NotFoundError("Entry", str(entry_id))
    return entry
