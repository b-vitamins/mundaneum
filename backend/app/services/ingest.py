"""
Compatibility facade for the ingest pipeline.
"""

from app.services.ingest_entities import IngestBatchContext, build_ingest_context
from app.services.ingest_pipeline import (
    IngestResult,
    ensure_search_index_ready,
    ingest_bib_file,
    ingest_directory,
    ingest_entries_batch,
    ingest_entry,
    ingest_parsed_entries,
    sync_imported_entries,
)

__all__ = [
    "IngestBatchContext",
    "IngestResult",
    "build_ingest_context",
    "ensure_search_index_ready",
    "ingest_bib_file",
    "ingest_directory",
    "ingest_entries_batch",
    "ingest_entry",
    "ingest_parsed_entries",
    "sync_imported_entries",
]
