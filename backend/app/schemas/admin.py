"""
Schemas for admin API surfaces.
"""

from pydantic import BaseModel


class ExportedEntry(BaseModel):
    """Exported entry user state."""

    citation_key: str
    notes: str | None = None
    read: bool = False


class ExportedCollection(BaseModel):
    """Exported collection with entry citation keys."""

    name: str
    description: str | None = None
    sort_order: int = 0
    entry_keys: list[str]


class ExportData(BaseModel):
    """Complete backup structure."""

    version: str = "1.0"
    exported_at: str
    entries: list[ExportedEntry]
    collections: list[ExportedCollection]


class ImportResult(BaseModel):
    """Result of importing user state."""

    entries_updated: int
    entries_skipped: int
    collections_created: int
    collections_updated: int
    errors: list[str]


class IngestRequest(BaseModel):
    """Request for triggering ingest."""

    directory: str | None = None


class IngestResponse(BaseModel):
    """Response from ingest operations."""

    imported: int
    errors: int
    total_parsed: int


class HealthResponse(BaseModel):
    """Detailed health status for admin views."""

    status: str
    database: str
    search: str
    bibliography: str
    bibliography_repo_url: str
    bibliography_checkout_path: str
    bib_files_count: int
