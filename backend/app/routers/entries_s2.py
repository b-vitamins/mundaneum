"""
Entry endpoints backed by Semantic Scholar data.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.entries import S2MetaResponse, S2PaperResponse
from app.services.entry_s2 import get_entry_s2_meta, get_related_s2_papers

router = APIRouter()


@router.get("/{entry_id}/s2", response_model=S2MetaResponse)
async def get_entry_s2(
    entry_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> S2MetaResponse:
    """Get S2 metadata and sync status for an entry."""
    s2_runtime = request.app.state.context.services.s2_runtime
    return await get_entry_s2_meta(
        db,
        entry_id,
        source=s2_runtime.data_source,
        orchestrator=s2_runtime.orchestrator,
    )


@router.get("/{entry_id}/citations", response_model=list[S2PaperResponse])
async def get_citations(
    entry_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> list[S2PaperResponse]:
    """Get citations (incoming edges) for an entry."""
    s2_runtime = request.app.state.context.services.s2_runtime
    return await get_related_s2_papers(
        db,
        entry_id,
        source=s2_runtime.data_source,
        relation="citations",
    )


@router.get("/{entry_id}/references", response_model=list[S2PaperResponse])
async def get_references(
    entry_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> list[S2PaperResponse]:
    """Get references (outgoing edges) for an entry."""
    s2_runtime = request.app.state.context.services.s2_runtime
    return await get_related_s2_papers(
        db,
        entry_id,
        source=s2_runtime.data_source,
        relation="references",
    )
