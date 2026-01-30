"""
Entries router for Folio API.
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.exceptions import NotFoundError
from app.logging import get_logger
from app.models import Entry, EntryAuthor, S2Citation, S2Paper
from app.services.s2 import S2Service

logger = get_logger(__name__)

router = APIRouter(prefix="/entries", tags=["entries"])


class EntryResponse(BaseModel):
    """Response model for entry list items."""

    id: str
    citation_key: str
    entry_type: str
    title: str
    year: Optional[int] = None
    authors: list[str]
    venue: Optional[str] = None
    abstract: Optional[str] = None
    file_path: Optional[str] = None
    read: bool = False

    model_config = {"from_attributes": True}


class EntryDetailResponse(EntryResponse):
    """Response model for entry detail view."""

    required_fields: dict
    optional_fields: dict
    notes: Optional[str] = None
    source_file: str


class NotesRequest(BaseModel):
    """Request model for updating notes."""

    notes: str


class ReadRequest(BaseModel):
    """Request model for updating read status."""

    read: bool


@router.get("/{entry_id}", response_model=EntryDetailResponse)
async def get_entry(
    entry_id: UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Get a single entry by ID."""
    result = await db.execute(
        select(Entry)
        .options(selectinload(Entry.authors).selectinload(EntryAuthor.author))
        .where(Entry.id == entry_id)
    )
    entry = result.scalar_one_or_none()

    if not entry:
        raise NotFoundError("Entry", str(entry_id))

    # Build response
    authors = [ea.author.name for ea in sorted(entry.authors, key=lambda x: x.position)]

    required = entry.required_fields or {}
    optional = entry.optional_fields or {}

    venue = (
        required.get("journal")
        or required.get("booktitle")
        or optional.get("journal")
        or optional.get("booktitle")
    )
    abstract = optional.get("abstract")

    # Trigger background sync (S2 integration)
    background_tasks.add_task(S2Service().sync_paper, str(entry_id))

    return EntryDetailResponse(
        id=str(entry.id),
        citation_key=entry.citation_key,
        entry_type=entry.entry_type.value,
        title=entry.title,
        year=entry.year,
        authors=authors,
        venue=venue,
        abstract=abstract,
        file_path=entry.file_path,
        read=entry.read or False,
        required_fields=required,
        optional_fields=optional,
        notes=entry.notes,
        source_file=entry.source_file,
    )


class ReadResponse(BaseModel):
    """Response for read status update."""

    id: str
    read: bool


class NotesResponse(BaseModel):
    """Response for notes update."""

    id: str
    notes: str


@router.patch("/{entry_id}/read", response_model=ReadResponse)
async def toggle_read(
    entry_id: UUID,
    request: ReadRequest,
    db: AsyncSession = Depends(get_db),
):
    """Toggle read status of an entry."""
    result = await db.execute(select(Entry).where(Entry.id == entry_id))
    entry = result.scalar_one_or_none()

    if not entry:
        raise NotFoundError("Entry", str(entry_id))

    entry.read = request.read
    await db.commit()

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
):
    """Update notes for an entry."""
    result = await db.execute(select(Entry).where(Entry.id == entry_id))
    entry = result.scalar_one_or_none()

    if not entry:
        raise NotFoundError("Entry", str(entry_id))

    entry.notes = request.notes
    await db.commit()

    logger.debug("Updated notes for %s", entry.citation_key)
    return NotesResponse(id=str(entry_id), notes=request.notes)


@router.get("/{entry_id}/bibtex", response_class=PlainTextResponse)
async def get_bibtex(
    entry_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Export entry as BibTeX."""
    result = await db.execute(
        select(Entry)
        .options(selectinload(Entry.authors).selectinload(EntryAuthor.author))
        .where(Entry.id == entry_id)
    )
    entry = result.scalar_one_or_none()

    if not entry:
        raise NotFoundError("Entry", str(entry_id))

    # Build BibTeX string
    authors = [ea.author.name for ea in sorted(entry.authors, key=lambda x: x.position)]

    lines = [f"@{entry.entry_type.value}{{{entry.citation_key},"]
    lines.append(f"  title = {{{entry.title}}},")

    if authors:
        lines.append(f"  author = {{{' and '.join(authors)}}},")

    if entry.year:
        lines.append(f"  year = {{{entry.year}}},")

    # Add required fields
    for key, value in (entry.required_fields or {}).items():
        if key not in {"title", "author", "year"}:
            lines.append(f"  {key} = {{{value}}},")

    # Add optional fields
    for key, value in (entry.optional_fields or {}).items():
        lines.append(f"  {key} = {{{value}}},")

    if entry.file_path:
        lines.append(f"  file = {{{entry.file_path}}},")

    lines.append("}")

    return "\n".join(lines)


class S2PaperResponse(BaseModel):
    s2_id: str
    title: str
    year: Optional[int]
    venue: Optional[str]
    authors: list[dict]
    tldr: Optional[dict]
    citation_count: int
    is_influential: bool = False
    contexts: list[str] = []
    intents: list[str] = []

    model_config = {"from_attributes": True}


@router.get("/{entry_id}/citations", response_model=list[S2PaperResponse])
async def get_citations(
    entry_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get citations (incoming edges) for this entry."""
    # 1. Get Entry to find s2_id
    res = await db.execute(select(Entry.s2_id).where(Entry.id == entry_id))
    s2_id = res.scalar_one_or_none()

    if not s2_id:
        # If no S2 ID, return empty list (sync might be pending)
        return []

    # 2. Query S2Citations joined with S2Paper (source)
    # We want papers that CITE this paper.
    # So citation.target_id == s2_id. We fetch citation.source.

    stmt = (
        select(S2Citation, S2Paper)
        .join(S2Paper, S2Citation.source_id == S2Paper.s2_id)
        .where(S2Citation.target_id == s2_id)
        .order_by(desc(S2Citation.is_influential), desc(S2Paper.citation_count))
        .limit(100)
    )

    result = await db.execute(stmt)
    rows = result.all()

    response = []
    for citation, paper in rows:
        response.append(
            S2PaperResponse(
                s2_id=paper.s2_id,
                title=paper.title,
                year=paper.year,
                venue=paper.venue,
                authors=paper.authors,
                tldr=paper.tldr,
                citation_count=paper.citation_count,
                is_influential=citation.is_influential,
                contexts=citation.contexts,
                intents=citation.intents,
            )
        )

    return response


@router.get("/{entry_id}/references", response_model=list[S2PaperResponse])
async def get_references(
    entry_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get references (outgoing edges) for this entry."""
    res = await db.execute(select(Entry.s2_id).where(Entry.id == entry_id))
    s2_id = res.scalar_one_or_none()

    if not s2_id:
        return []

    # 2. Query S2Citations joined with S2Paper (target)
    # This paper CITES target.
    # So citation.source_id == s2_id. We fetch citation.target.

    stmt = (
        select(S2Citation, S2Paper)
        .join(S2Paper, S2Citation.target_id == S2Paper.s2_id)
        .where(S2Citation.source_id == s2_id)
        .order_by(desc(S2Citation.is_influential), desc(S2Paper.citation_count))
        .limit(100)
    )

    result = await db.execute(stmt)
    rows = result.all()

    response = []
    for citation, paper in rows:
        response.append(
            S2PaperResponse(
                s2_id=paper.s2_id,
                title=paper.title,
                year=paper.year,
                venue=paper.venue,
                authors=paper.authors,
                tldr=paper.tldr,
                citation_count=paper.citation_count,
                is_influential=citation.is_influential,
                contexts=citation.contexts,
                intents=citation.intents,
            )
        )

    return response
