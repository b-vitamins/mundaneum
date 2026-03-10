"""
Backend-specific executors compiled from the shared search query algebra.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Author, Entry, EntryAuthor
from app.schemas.search import (
    SearchHitResponse,
    SearchQuery,
    SearchResponse,
    SearchSortField,
    SearchSortOrder,
    SearchSource,
)
from app.services.entry_queries import ENTRY_SORT_COLUMNS, entry_load_options
from app.services.entry_serializers import serialize_search_hit
from app.services.sync import INDEX_NAME, SearchIndexService

SEARCH_SORT_COLUMNS = {
    SearchSortField.CREATED_AT: ENTRY_SORT_COLUMNS["created_at"],
    SearchSortField.YEAR: ENTRY_SORT_COLUMNS["year"],
    SearchSortField.TITLE: ENTRY_SORT_COLUMNS["title"],
}


def compile_meilisearch_request(query: SearchQuery) -> dict[str, object]:
    """Compile the shared search AST to Meilisearch options."""
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

    return {
        "limit": query.limit,
        "offset": query.offset,
        "filter": " AND ".join(parts) if parts else None,
        "sort": [query.sort.meilisearch_value],
    }


def compile_database_query(statement: Select, query: SearchQuery) -> Select:
    """Compile the shared search AST to a database select."""
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

    normalized_query = query.normalized_query
    if normalized_query is not None:
        pattern = f"%{normalized_query}%"
        statement = statement.where(
            or_(
                Entry.title.ilike(pattern),
                Entry.citation_key.ilike(pattern),
                Author.name.ilike(pattern),
            )
        )

    order_column = SEARCH_SORT_COLUMNS[query.sort.field]
    ordering = (
        order_column.desc().nullslast()
        if query.sort.order == SearchSortOrder.DESC
        else order_column.asc().nullsfirst()
    )
    return statement.order_by(ordering)


@dataclass(slots=True)
class MeilisearchBackend:
    """Preferred full-text backend."""

    search_index: SearchIndexService

    def execute(self, query: SearchQuery) -> SearchResponse:
        result = self.search_index.client.index(INDEX_NAME).search(
            query.normalized_query or "",
            compile_meilisearch_request(query),
        )
        hits = [SearchHitResponse.model_validate(hit) for hit in result.get("hits", [])]
        return SearchResponse.ok(
            source=SearchSource.MEILISEARCH,
            hits=hits,
            total=result.get("estimatedTotalHits", 0),
            processing_time_ms=result.get("processingTimeMs", 0),
        )


@dataclass(slots=True)
class DatabaseSearchBackend:
    """Degraded SQL fallback backend."""

    db: AsyncSession

    async def execute(self, query: SearchQuery) -> SearchResponse:
        base_ids = (
            select(Entry.id)
            .select_from(Entry)
            .outerjoin(Entry.authors)
            .outerjoin(EntryAuthor.author)
            .distinct()
        )
        filtered_ids = compile_database_query(base_ids, query)
        total = await self.db.scalar(select(func.count()).select_from(filtered_ids.subquery()))

        bounded_limit = min(query.limit, 100)
        ordered_ids_query = filtered_ids.offset(query.offset).limit(bounded_limit)

        id_rows = await self.db.execute(ordered_ids_query)
        entry_ids = list(id_rows.scalars().all())
        if not entry_ids:
            return SearchResponse.partial(
                source=SearchSource.DATABASE,
                hits=[],
                total=total or 0,
            )

        entries_result = await self.db.execute(
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
