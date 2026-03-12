"""
Entry-specific S2 projection helpers.
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Entry
from app.schemas.entries import S2MetaResponse, S2PaperResponse
from app.services.entry_queries import get_entry
from app.services.s2 import SyncStatus, sync_entry
from app.services.s2_protocol import EdgeRecord, PaperRecord
from app.services.s2_sync import SyncOrchestrator


def serialize_s2_paper(
    paper: PaperRecord, edge: EdgeRecord | None = None
) -> S2PaperResponse:
    """Project a canonical paper record into the entry API shape."""
    return S2PaperResponse(
        s2_id=paper.s2_id or "",
        title=paper.title,
        year=paper.year,
        venue=paper.venue,
        authors=paper.authors,
        abstract=paper.abstract,
        tldr={"text": paper.tldr} if paper.tldr else None,
        citation_count=paper.citation_count,
        is_influential=edge.is_influential if edge else False,
        contexts=[],
        intents=[],
    )


def serialize_s2_meta(paper: PaperRecord) -> S2MetaResponse:
    """Project canonical paper data into the progressive metadata response."""
    return S2MetaResponse(
        sync_status="synced",
        s2_id=paper.s2_id,
        title=paper.title,
        abstract=paper.abstract,
        tldr=paper.tldr,
        citation_count=paper.citation_count,
        reference_count=paper.reference_count,
        influential_citation_count=paper.influential_citation_count,
        fields_of_study=paper.fields_of_study,
        publication_types=paper.publication_types,
        is_open_access=paper.is_open_access,
        open_access_pdf_url=paper.open_access_pdf_url,
        external_ids=paper.external_ids,
        s2_url=f"https://www.semanticscholar.org/paper/{paper.s2_id}",
    )


async def get_entry_s2_meta(
    db: AsyncSession,
    entry_id: UUID,
    *,
    source,
    orchestrator: SyncOrchestrator,
) -> S2MetaResponse:
    """Load S2 metadata for an entry from corpus and sync fallback."""
    entry = await get_entry(db, entry_id, include_relationships=False)

    if entry.s2_id:
        paper = await source.get_paper(entry.s2_id)
        if paper is not None:
            return serialize_s2_meta(paper)

    status = await sync_entry(orchestrator, str(entry_id))
    if status == SyncStatus.SYNCING:
        return S2MetaResponse(sync_status="syncing")
    if status == SyncStatus.NO_MATCH:
        return S2MetaResponse(sync_status="no_match")

    await db.refresh(entry)
    if not entry.s2_id:
        return S2MetaResponse(sync_status="pending")

    paper = await source.get_paper(entry.s2_id)
    if paper is None:
        return S2MetaResponse(sync_status="pending", s2_id=entry.s2_id)

    return serialize_s2_meta(paper)


async def get_related_s2_papers(
    db: AsyncSession,
    entry_id: UUID,
    *,
    source,
    relation: str,
    limit: int = 100,
) -> list[S2PaperResponse]:
    """Load projected citation/reference papers for an entry."""
    result = await db.execute(select(Entry.s2_id).where(Entry.id == entry_id))
    s2_id = result.scalar_one_or_none()
    if not s2_id:
        return []

    edge_loader = (
        source.get_citations if relation == "citations" else source.get_references
    )
    edges = await edge_loader(s2_id)
    if not edges:
        return []

    projected: list[S2PaperResponse] = []
    for edge in edges[:limit]:
        related_id = edge.citing_s2_id if relation == "citations" else edge.cited_s2_id
        if not related_id:
            continue
        paper = await source.get_paper(related_id)
        if paper is not None:
            projected.append(serialize_s2_paper(paper, edge=edge))

    return projected
