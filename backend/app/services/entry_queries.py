"""
Entry query helpers.
"""

from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.exceptions import NotFoundError
from app.models import Entry, EntryAuthor
from app.routers.entity_common import apply_sort, paginate
from app.schemas.search import SearchFilters

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


def apply_entry_filters(statement: Select, *, filters: SearchFilters) -> Select:
    """Apply browse/list filters to an entry query."""
    if filters.entry_type is not None:
        statement = statement.where(Entry.entry_type == filters.entry_type)
    if filters.year_from is not None:
        statement = statement.where(Entry.year >= filters.year_from)
    if filters.year_to is not None:
        statement = statement.where(Entry.year <= filters.year_to)
    if filters.has_pdf is True:
        statement = statement.where(Entry.file_path.is_not(None))
    elif filters.has_pdf is False:
        statement = statement.where(Entry.file_path.is_(None))
    if filters.read is not None:
        statement = statement.where(Entry.read == filters.read)

    return statement


async def list_entries(
    db: AsyncSession,
    *,
    limit: int,
    offset: int,
    sort_by: str,
    sort_order: str,
    filters: SearchFilters | None = None,
) -> tuple[list[Entry], int]:
    """Fetch a paginated entry list with serializer-friendly relationships."""
    filters = filters or SearchFilters()

    total_query = apply_entry_filters(select(Entry.id), filters=filters)
    total = await db.scalar(select(func.count()).select_from(total_query.subquery()))

    query = entry_load_options(apply_entry_filters(select(Entry), filters=filters))
    query = apply_sort(
        query,
        sort_by=sort_by,
        sort_order=sort_order,
        sort_columns=ENTRY_SORT_COLUMNS,
    )
    query = paginate(query, limit=limit, offset=offset)
    result = await db.execute(query)
    return result.scalars().all(), total or 0


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
