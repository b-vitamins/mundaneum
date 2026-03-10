"""
Search application service with explicit degradation states.
"""

from __future__ import annotations

from typing import Final

from meilisearch.errors import MeilisearchApiError, MeilisearchCommunicationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.logging import get_logger
from app.schemas.search import (
    SearchQuery,
    SearchResponse,
    SearchWarning,
    SearchWarningCode,
)
from app.services.search_backends import DatabaseSearchBackend, MeilisearchBackend
from app.services.sync import SearchIndexService

logger = get_logger(__name__)

MEILI_WARNING: Final[SearchWarning] = SearchWarning(
    code=SearchWarningCode.MEILISEARCH_UNAVAILABLE,
    message="Full-text search is unavailable. Showing degraded database results.",
)
UNAVAILABLE_WARNING: Final[SearchWarning] = SearchWarning(
    code=SearchWarningCode.SEARCH_UNAVAILABLE,
    message="Search is temporarily unavailable.",
)


def execute_meilisearch(
    query: SearchQuery,
    search_index: SearchIndexService,
) -> SearchResponse:
    """Execute the preferred Meilisearch query."""
    return MeilisearchBackend(search_index).execute(query)


async def execute_database_search(
    db: AsyncSession,
    query: SearchQuery,
) -> SearchResponse:
    """Execute degraded search directly against the database."""
    return await DatabaseSearchBackend(db).execute(query)


async def search_entries(
    db: AsyncSession,
    query: SearchQuery,
    search_index: SearchIndexService,
) -> SearchResponse:
    """Search with explicit degradation handling."""
    try:
        return execute_meilisearch(query, search_index)
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
