"""
Meilisearch sync service for Mundaneum.

Handles syncing entries to Meilisearch for full-text search.
"""

from functools import wraps
from typing import TYPE_CHECKING

import meilisearch
from meilisearch.errors import MeilisearchApiError, MeilisearchCommunicationError

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


def get_client() -> meilisearch.Client:
    """Get the process-owned Meilisearch client."""
    from app.services.service_container import get_service_container

    return get_service_container().search.client


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
    metadata = entry.bib_metadata

    return {
        "id": str(entry.id),
        "citation_key": entry.citation_key,
        "entry_type": entry.entry_type.value if entry.entry_type else "misc",
        "title": entry.title or "",
        "year": entry.year,
        "authors": author_names,
        "abstract": metadata.abstract or "",
        "venue": metadata.venue_name or "",
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


def is_available() -> bool:
    """Check if Meilisearch is reachable."""
    try:
        client = get_client()
        client.health()
        return True
    except Exception:
        return False
