"""
Admin router for Mundaneum API.

Provides backup/restore, ingest, and health endpoints for administration.
"""

from datetime import UTC, datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database import check_db_health, get_db
from app.logging import get_logger
from app.models import Collection, CollectionEntry, Entry
from app.services.sync import is_available as meili_available

logger = get_logger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


# ============================================================================
# Export/Import Schemas
# ============================================================================


class ExportedEntry(BaseModel):
    """Exported entry user state."""

    citation_key: str
    notes: Optional[str] = None
    read: bool = False


class ExportedCollection(BaseModel):
    """Exported collection with entries."""

    name: str
    description: Optional[str] = None
    sort_order: int = 0
    entry_keys: list[str]  # citation keys


class ExportData(BaseModel):
    """Complete backup data structure."""

    version: str = "1.0"
    exported_at: str
    entries: list[ExportedEntry]
    collections: list[ExportedCollection]


class ImportResult(BaseModel):
    """Result of import operation."""

    entries_updated: int
    entries_skipped: int
    collections_created: int
    collections_updated: int
    errors: list[str]


class IngestRequest(BaseModel):
    """Request for triggering ingest."""

    directory: Optional[str] = None


class IngestResponse(BaseModel):
    """Response from ingest operation."""

    imported: int
    errors: int
    total_parsed: int


class HealthResponse(BaseModel):
    """Detailed health status."""

    status: str
    database: str
    search: str
    bib_directory: str
    bib_files_count: int


# ============================================================================
# Export Endpoint
# ============================================================================


@router.get("/export", response_model=ExportData)
async def export_user_state(db: AsyncSession = Depends(get_db)):
    """
    Export all user state (notes, read status, collections).

    This data can be restored after a fresh ingest to recover user work.
    """
    # Export entry user state
    result = await db.execute(
        select(Entry).where((Entry.notes.isnot(None)) | (Entry.read == True))  # noqa
    )
    entries_with_state = result.scalars().all()

    exported_entries = [
        ExportedEntry(
            citation_key=e.citation_key,
            notes=e.notes,
            read=e.read,
        )
        for e in entries_with_state
    ]

    # Export collections with entry references
    result = await db.execute(
        select(Collection).options(
            selectinload(Collection.entries).selectinload(CollectionEntry.entry)
        )
    )
    collections = result.scalars().all()

    exported_collections = [
        ExportedCollection(
            name=c.name,
            description=c.description,
            sort_order=c.sort_order,
            entry_keys=[ce.entry.citation_key for ce in c.entries if ce.entry],
        )
        for c in collections
    ]

    logger.info(
        "Exported %d entries and %d collections",
        len(exported_entries),
        len(exported_collections),
    )

    return ExportData(
        exported_at=datetime.now(UTC).isoformat(),
        entries=exported_entries,
        collections=exported_collections,
    )


# ============================================================================
# Import Endpoint
# ============================================================================


@router.post("/import", response_model=ImportResult)
async def import_user_state(
    data: ExportData,
    db: AsyncSession = Depends(get_db),
):
    """
    Import user state from a backup.

    Updates notes, read status, and recreates collections.
    Entries must already exist (from ingest) - this only restores user state.
    """
    errors: list[str] = []
    entries_updated = 0
    entries_skipped = 0
    collections_created = 0
    collections_updated = 0

    # Build citation_key -> entry lookup
    result = await db.execute(select(Entry))
    all_entries = {e.citation_key: e for e in result.scalars().all()}

    # Restore entry user state
    for exp_entry in data.entries:
        entry = all_entries.get(exp_entry.citation_key)
        if entry:
            entry.notes = exp_entry.notes
            entry.read = exp_entry.read
            entries_updated += 1
        else:
            entries_skipped += 1
            errors.append(f"Entry not found: {exp_entry.citation_key}")

    # Restore collections
    for exp_coll in data.collections:
        # Check if collection exists
        result = await db.execute(
            select(Collection).where(Collection.name == exp_coll.name)
        )
        collection = result.scalar_one_or_none()

        if collection:
            # Update existing
            collection.description = exp_coll.description
            collection.sort_order = exp_coll.sort_order
            # Clear existing entries
            await db.execute(
                CollectionEntry.__table__.delete().where(
                    CollectionEntry.collection_id == collection.id
                )
            )
            collections_updated += 1
        else:
            # Create new
            collection = Collection(
                name=exp_coll.name,
                description=exp_coll.description,
                sort_order=exp_coll.sort_order,
            )
            db.add(collection)
            await db.flush()  # Get ID
            collections_created += 1

        # Add entries to collection
        for i, key in enumerate(exp_coll.entry_keys):
            entry = all_entries.get(key)
            if entry:
                ce = CollectionEntry(
                    collection_id=collection.id,
                    entry_id=entry.id,
                    sort_order=i,
                )
                db.add(ce)
            else:
                errors.append(f"Collection '{exp_coll.name}': entry not found: {key}")

    await db.commit()

    logger.info(
        "Imported: %d entries updated, %d collections created/updated",
        entries_updated,
        collections_created + collections_updated,
    )

    return ImportResult(
        entries_updated=entries_updated,
        entries_skipped=entries_skipped,
        collections_created=collections_created,
        collections_updated=collections_updated,
        errors=errors,
    )


# ============================================================================
# Ingest Endpoints (Background Worker)
# ============================================================================


@router.get("/ingest/status")
async def get_ingest_status():
    """
    Get current ingestion worker status.

    Returns progress information for background ingestion.
    """
    from app.services.worker import worker

    return worker.get_status()


@router.post("/ingest/start")
async def start_ingest(
    request: IngestRequest,
):
    """
    Manually trigger background ingestion.

    If already running, returns current status without restarting.
    """
    from app.services.worker import worker

    if worker.is_running:
        return {"message": "Ingestion already running", **worker.get_status()}

    directory = request.directory or "/bibliography"
    path = Path(directory)

    if not path.exists() or not path.is_dir():
        return JSONResponse(
            status_code=400,
            content={"detail": f"Directory not found: {directory}"},
        )

    # Start background ingestion
    await worker.start(path)

    return {"message": "Ingestion started", **worker.get_status()}


# ============================================================================
# Health Endpoint
# ============================================================================


@router.get("/health", response_model=HealthResponse)
async def detailed_health():
    """
    Detailed health check for admin dashboard.
    """
    db_ok = await check_db_health()
    meili_ok = meili_available()

    # Check BibTeX directory (optional - not having one doesn't affect core functionality)
    bib_dir = Path(settings.bib_directory)
    bib_exists = bib_dir.exists() and bib_dir.is_dir()
    bib_count = len(list(bib_dir.glob("**/*.bib"))) if bib_exists else 0

    # Status based on core services only (db and search)
    if db_ok and meili_ok:
        status = "healthy"
    elif db_ok:
        status = "degraded"
    else:
        status = "unhealthy"

    return HealthResponse(
        status=status,
        database="ok" if db_ok else "unavailable",
        search="ok" if meili_ok else "unavailable",
        bib_directory="ok" if bib_exists else "not configured",
        bib_files_count=bib_count,
    )
