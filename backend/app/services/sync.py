"""
Meilisearch sync service for Folio.

Handles syncing entries to Meilisearch for full-text search.
"""

from functools import lru_cache, wraps
from typing import TYPE_CHECKING

import meilisearch
from meilisearch.errors import MeilisearchApiError, MeilisearchCommunicationError

from app.config import settings
from app.logging import get_logger

if TYPE_CHECKING:
    from app.models import Entry

logger = get_logger(__name__)

INDEX_NAME = "entries"

# Searchable attributes for full-text search
SEARCHABLE_ATTRS = [
    "title",
    "authors",
    "abstract",
    "venue",
    "citation_key",
]

# Filterable attributes for faceted search
FILTERABLE_ATTRS = [
    "entry_type",
    "year",
    "authors",
    "has_pdf",
    "read",
]

# Sortable attributes
SORTABLE_ATTRS = [
    "year",
    "title",
    "created_at",
]


class MeilisearchUnavailableError(Exception):
    """Raised when Meilisearch is unavailable."""

    pass


@lru_cache(maxsize=1)
def get_client() -> meilisearch.Client:
    """Get cached Meilisearch client."""
    return meilisearch.Client(
        settings.meili_url,
        settings.meili_api_key,
        timeout=settings.meili_timeout,
    )


def _handle_meili_error(func):
    """Decorator to handle Meilisearch errors gracefully."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except MeilisearchCommunicationError as e:
            logger.warning("Meilisearch unavailable: %s", e)
            raise MeilisearchUnavailableError("Meilisearch is not available") from e
        except MeilisearchApiError as e:
            logger.error("Meilisearch API error: %s", e)
            raise

    return wrapper


@_handle_meili_error
def ensure_index() -> None:
    """Create index if it doesn't exist and configure settings."""
    client = get_client()

    try:
        client.get_index(INDEX_NAME)
        logger.debug("Index '%s' already exists", INDEX_NAME)
    except MeilisearchApiError:
        logger.info("Creating index '%s'", INDEX_NAME)
        client.create_index(INDEX_NAME, {"primaryKey": "id"})

    index = client.index(INDEX_NAME)

    # Configure searchable attributes
    index.update_searchable_attributes(SEARCHABLE_ATTRS)
    index.update_filterable_attributes(FILTERABLE_ATTRS)
    index.update_sortable_attributes(SORTABLE_ATTRS)

    logger.info("Index '%s' configured", INDEX_NAME)


def entry_to_document(entry: "Entry") -> dict:
    """Convert database entry to Meilisearch document."""
    # Get authors as list of names
    author_names = [ea.author.name for ea in entry.authors] if entry.authors else []

    # Extract common fields from JSONB (handle None values)
    optional = entry.optional_fields or {}
    required = entry.required_fields or {}

    abstract = optional.get("abstract", "")
    venue = (
        required.get("journal")
        or required.get("booktitle")
        or optional.get("journal")
        or optional.get("booktitle")
        or ""
    )

    return {
        "id": str(entry.id),
        "citation_key": entry.citation_key,
        "entry_type": entry.entry_type.value if entry.entry_type else "misc",
        "title": entry.title or "",
        "year": entry.year,
        "authors": author_names,
        "abstract": abstract,
        "venue": venue,
        "has_pdf": bool(entry.file_path),
        "read": entry.read or False,
        "created_at": entry.created_at.timestamp() if entry.created_at else 0,
    }


@_handle_meili_error
def sync_entry(entry: "Entry") -> None:
    """Sync a single entry to Meilisearch."""
    client = get_client()
    index = client.index(INDEX_NAME)
    doc = entry_to_document(entry)
    index.add_documents([doc])
    logger.debug("Synced entry %s", entry.citation_key)


@_handle_meili_error
def sync_entries(entries: list["Entry"]) -> None:
    """Sync multiple entries to Meilisearch."""
    if not entries:
        return

    client = get_client()
    index = client.index(INDEX_NAME)
    docs = [entry_to_document(e) for e in entries]

    # Batch in chunks of 1000
    batch_size = 1000
    for i in range(0, len(docs), batch_size):
        batch = docs[i : i + batch_size]
        index.add_documents(batch)
        logger.debug("Synced batch %d-%d", i, i + len(batch))

    logger.info("Synced %d entries to Meilisearch", len(entries))


@_handle_meili_error
def delete_entry(entry_id: str) -> None:
    """Delete an entry from Meilisearch."""
    client = get_client()
    index = client.index(INDEX_NAME)
    index.delete_document(entry_id)
    logger.debug("Deleted entry %s from index", entry_id)


def search(
    query: str | None,
    filters: dict | None = None,
    limit: int = 20,
    offset: int = 0,
    sort: str | None = None,
) -> dict:
    """
    Search entries in Meilisearch.

    Returns dict with hits, total count, and processing time.
    Falls back to empty results if Meilisearch is unavailable.
    """
    try:
        client = get_client()
        index = client.index(INDEX_NAME)

        # Build filter string
        filter_parts = []
        if filters:
            for key, value in filters.items():
                if value is None:
                    continue
                if isinstance(value, bool):
                    filter_parts.append(f"{key} = {str(value).lower()}")
                elif isinstance(value, list) and len(value) == 2:
                    # Range filter for year
                    if key == "year":
                        filter_parts.append(
                            f"{key} >= {value[0]} AND {key} <= {value[1]}"
                        )
                elif isinstance(value, (int, float)):
                    filter_parts.append(f"{key} = {value}")
                else:
                    filter_parts.append(f"{key} = '{value}'")

        filter_str = " AND ".join(filter_parts) if filter_parts else None

        # Prepare search params
        search_params = {
            "limit": limit,
            "offset": offset,
            "filter": filter_str,
        }
        if sort:
            search_params["sort"] = [sort]

        # Handle explicit None query for "match all"
        q = query if query is not None else ""

        result = index.search(q, search_params)

        return {
            "hits": result.get("hits", []),
            "total": result.get("estimatedTotalHits", 0),
            "processing_time_ms": result.get("processingTimeMs", 0),
        }

    except (MeilisearchCommunicationError, MeilisearchApiError) as e:
        logger.warning("Search failed, returning empty results: %s", e)
        return {
            "hits": [],
            "total": 0,
            "processing_time_ms": 0,
        }


def is_available() -> bool:
    """Check if Meilisearch is reachable."""
    try:
        client = get_client()
        client.health()
        return True
    except Exception:
        return False
