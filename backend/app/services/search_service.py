"""
Search application service with explicit degradation states.
"""

from __future__ import annotations

from typing import Final

from meilisearch.errors import MeilisearchApiError, MeilisearchCommunicationError
from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError

from app.logging import get_logger
from app.models import Author, Entry, EntryAuthor
from app.schemas.search import (
    SearchHitResponse,
    SearchQuery,
    SearchResponse,
    SearchSort,
    SearchSortField,
    SearchSortOrder,
    SearchSource,
    SearchWarning,
    SearchWarningCode,
)
from app.services.entry_queries import ENTRY_SORT_COLUMNS, entry_load_options
from app.services.entry_serializers import serialize_search_hit
from app.services.sync import INDEX_NAME, get_client

logger = get_logger(__name__)

MEILI_WARNING: Final[SearchWarning] = SearchWarning(
    code=SearchWarningCode.MEILISEARCH_UNAVAILABLE,
    message="Full-text search is unavailable. Showing degraded database results.",
)
UNAVAILABLE_WARNING: Final[SearchWarning] = SearchWarning(
    code=SearchWarningCode.SEARCH_UNAVAILABLE,
    message="Search is temporarily unavailable.",
)
SEARCH_SORT_COLUMNS: Final = {
    SearchSortField.CREATED_AT: ENTRY_SORT_COLUMNS["created_at"],
    SearchSortField.YEAR: ENTRY_SORT_COLUMNS["year"],
    SearchSortField.TITLE: ENTRY_SORT_COLUMNS["title"],
}


def _build_meili_filter(query: SearchQuery) -> str | None:
    parts: list[str] = []
    filters = query.filters
    if filters.entry_type is not None:
        parts.append(f"entry_type = '{filters.entry_type.value}'")
    if filters.year_from is not None:
        parts.append(f"year >= {filters.year_from}")
    if filters.year_to is not None:
        parts.append(f"year <= {filters.year_to}")
    if filters.has_pdf is not None:
        parts.append(f"has_pdf = {str(filters.has_pdf).lower()}")
    if filters.read is not None:
        parts.append(f"read = {str(filters.read).lower()}")
    return " AND ".join(parts) if parts else None


def execute_meilisearch(query: SearchQuery) -> SearchResponse:
    """Execute the preferred Meilisearch query."""
    client = get_client()
    index = client.index(INDEX_NAME)
    result = index.search(
        query.normalized_query or "",
        {
            "limit": query.limit,
            "offset": query.offset,
            "filter": _build_meili_filter(query),
            "sort": [query.sort.meilisearch_value],
        },
    )
    hits = [
        SearchHitResponse.model_validate(hit)
        for hit in result.get("hits", [])
    ]
    return SearchResponse.ok(
        source=SearchSource.MEILISEARCH,
        hits=hits,
        total=result.get("estimatedTotalHits", 0),
        processing_time_ms=result.get("processingTimeMs", 0),
    )


def _apply_database_filters(statement: Select, query: SearchQuery) -> Select:
    filters = query.filters
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


def _apply_database_query(statement: Select, query: SearchQuery) -> Select:
    normalized_query = query.normalized_query
    if normalized_query is None:
        return statement

    pattern = f"%{normalized_query}%"
    return statement.where(
        or_(
            Entry.title.ilike(pattern),
            Entry.citation_key.ilike(pattern),
            Author.name.ilike(pattern),
        )
    )


def _apply_database_sort(statement: Select, sort: SearchSort) -> Select:
    order_column = SEARCH_SORT_COLUMNS[sort.field]
    ordering = (
        order_column.desc().nullslast()
        if sort.order == SearchSortOrder.DESC
        else order_column.asc().nullsfirst()
    )
    return statement.order_by(ordering)


def _paginate(statement: Select, query: SearchQuery) -> Select:
    bounded_limit = min(query.limit, 100)
    return statement.offset(query.offset).limit(bounded_limit)


async def execute_database_search(
    db: AsyncSession,
    query: SearchQuery,
) -> SearchResponse:
    """Execute degraded search directly against the database."""
    base_ids = (
        select(Entry.id)
        .select_from(Entry)
        .outerjoin(Entry.authors)
        .outerjoin(EntryAuthor.author)
        .distinct()
    )
    base_ids = _apply_database_filters(base_ids, query)
    base_ids = _apply_database_query(base_ids, query)

    total = await db.scalar(select(func.count()).select_from(base_ids.subquery()))
    ordered_ids_query = _apply_database_sort(base_ids, query.sort)
    ordered_ids_query = _paginate(ordered_ids_query, query)

    id_rows = await db.execute(ordered_ids_query)
    entry_ids = list(id_rows.scalars().all())
    if not entry_ids:
        return SearchResponse.partial(
            source=SearchSource.DATABASE,
            hits=[],
            total=total or 0,
        )

    entries_result = await db.execute(
        entry_load_options(select(Entry).where(Entry.id.in_(entry_ids)))
    )
    entries_by_id = {entry.id: entry for entry in entries_result.scalars().all()}
    ordered_entries = [
        entries_by_id[entry_id]
        for entry_id in entry_ids
        if entry_id in entries_by_id
    ]
    return SearchResponse.partial(
        source=SearchSource.DATABASE,
        hits=[serialize_search_hit(entry) for entry in ordered_entries],
        total=total or 0,
    )


async def search_entries(db: AsyncSession, query: SearchQuery) -> SearchResponse:
    """Search with explicit degradation handling."""
    try:
        return execute_meilisearch(query)
    except (MeilisearchCommunicationError, MeilisearchApiError) as exc:
        logger.warning("Meilisearch search failed, degrading to database: %s", exc)

    try:
        degraded = await execute_database_search(db, query)
        return degraded.model_copy(update={"warnings": [MEILI_WARNING]})
    except SQLAlchemyError as exc:
        logger.exception("Database fallback search failed: %s", exc)
        return SearchResponse.unavailable(
            warnings=[
                MEILI_WARNING,
                UNAVAILABLE_WARNING,
            ],
        )
