"""
Core entry endpoints.
"""

from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends
from fastapi.responses import FileResponse, PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.logging import get_logger
from app.schemas.entries import (
    EntryDetailResponse,
    EntryResponse,
    NotesRequest,
    NotesResponse,
    ReadRequest,
    ReadResponse,
)
from app.services.entry_exports import render_bibtex, resolve_pdf_path
from app.services.entry_mutations import update_entry_notes, update_entry_read
from app.services.entry_queries import get_entry, list_entries
from app.services.entry_serializers import (
    serialize_entry,
    serialize_entry_detail,
)
from app.services.s2 import background_sync_entry

logger = get_logger(__name__)

router = APIRouter()


@router.get("", response_model=list[EntryResponse])
async def list_entry_rows(
    limit: int = 50,
    offset: int = 0,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    db: AsyncSession = Depends(get_db),
) -> list[EntryResponse]:
    """List entries with pagination and consistent serializer rules."""
    entries = await list_entries(
        db,
        limit=limit,
        offset=offset,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return [serialize_entry(entry) for entry in entries]


@router.get("/{entry_id}", response_model=EntryDetailResponse)
async def get_entry_detail(
    entry_id: UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> EntryDetailResponse:
    """Get a single entry and schedule background S2 hydration."""
    entry = await get_entry(db, entry_id)
    background_tasks.add_task(background_sync_entry, str(entry_id))
    return serialize_entry_detail(entry)


@router.patch("/{entry_id}/read", response_model=ReadResponse)
async def toggle_read(
    entry_id: UUID,
    request: ReadRequest,
    db: AsyncSession = Depends(get_db),
) -> ReadResponse:
    """Toggle read status of an entry."""
    entry = await update_entry_read(db, entry_id, read=request.read)
    logger.info(
        "Entry %s marked as %s",
        entry.citation_key,
        "read" if request.read else "unread",
    )
    return ReadResponse(id=str(entry_id), read=request.read)


@router.patch("/{entry_id}/notes", response_model=NotesResponse)
async def update_notes(
    entry_id: UUID,
    request: NotesRequest,
    db: AsyncSession = Depends(get_db),
) -> NotesResponse:
    """Update notes for an entry."""
    entry = await update_entry_notes(db, entry_id, notes=request.notes)
    logger.debug("Updated notes for %s", entry.citation_key)
    return NotesResponse(id=str(entry_id), notes=request.notes)


@router.get("/{entry_id}/bibtex", response_class=PlainTextResponse)
async def get_bibtex(
    entry_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> str:
    """Export entry as BibTeX."""
    entry = await get_entry(db, entry_id)
    return render_bibtex(entry)


@router.get("/{entry_id}/pdf")
async def get_pdf(
    entry_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    """Serve the PDF associated with an entry."""
    entry = await get_entry(db, entry_id, include_relationships=False)
    pdf_path = resolve_pdf_path(entry)
    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=pdf_path.name,
        headers={"Content-Disposition": f'inline; filename="{pdf_path.name}"'},
    )
