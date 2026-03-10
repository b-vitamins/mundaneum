"""
Explicit Meilisearch indexing service for Mundaneum.
"""

from __future__ import annotations

from functools import wraps
from typing import TYPE_CHECKING

import meilisearch
from meilisearch.errors import MeilisearchApiError, MeilisearchCommunicationError

from app.logging import get_logger

if TYPE_CHECKING:
    from app.models import Entry

logger = get_logger(__name__)

INDEX_NAME = "entries"
SEARCHABLE_ATTRS = ["title", "authors", "abstract", "venue", "citation_key"]
FILTERABLE_ATTRS = ["entry_type", "year", "authors", "has_pdf", "read"]
SORTABLE_ATTRS = ["year", "title", "created_at"]


class MeilisearchUnavailableError(Exception):
    """Raised when Meilisearch is unavailable."""

    pass


def _handle_meili_error(func):
    """Decorator to handle Meilisearch errors gracefully."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except MeilisearchCommunicationError as exc:
            logger.warning("Meilisearch unavailable: %s", exc)
            raise MeilisearchUnavailableError("Meilisearch is not available") from exc
        except MeilisearchApiError as exc:
            logger.error("Meilisearch API error: %s", exc)
            raise

    return wrapper


def entry_to_document(entry: "Entry") -> dict:
    """Convert a hydrated entry to its Meilisearch document."""
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


class SearchIndexService:
    """Own Meilisearch indexing policy and connectivity."""

    def __init__(self, client: meilisearch.Client):
        self.client = client

    @_handle_meili_error
    def ensure_index(self) -> None:
        try:
            self.client.get_index(INDEX_NAME)
            logger.debug("Index '%s' already exists", INDEX_NAME)
        except MeilisearchApiError:
            logger.info("Creating index '%s'", INDEX_NAME)
            self.client.create_index(INDEX_NAME, {"primaryKey": "id"})

        index = self.client.index(INDEX_NAME)
        index.update_searchable_attributes(SEARCHABLE_ATTRS)
        index.update_filterable_attributes(FILTERABLE_ATTRS)
        index.update_sortable_attributes(SORTABLE_ATTRS)
        logger.info("Index '%s' configured", INDEX_NAME)

    @_handle_meili_error
    def sync_entry(self, entry: "Entry") -> None:
        index = self.client.index(INDEX_NAME)
        index.add_documents([entry_to_document(entry)])
        logger.debug("Synced entry %s", entry.citation_key)

    @_handle_meili_error
    def sync_entries(self, entries: list["Entry"]) -> None:
        if not entries:
            return

        index = self.client.index(INDEX_NAME)
        docs = [entry_to_document(entry) for entry in entries]
        batch_size = 1000
        for offset in range(0, len(docs), batch_size):
            batch = docs[offset : offset + batch_size]
            index.add_documents(batch)
            logger.debug("Synced batch %d-%d", offset, offset + len(batch))
        logger.info("Synced %d entries to Meilisearch", len(entries))

    @_handle_meili_error
    def delete_entry(self, entry_id: str) -> None:
        self.client.index(INDEX_NAME).delete_document(entry_id)
        logger.debug("Deleted entry %s from index", entry_id)

    def is_available(self) -> bool:
        try:
            self.client.health()
            return True
        except Exception:
            return False
