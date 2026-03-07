"""
Graph API router for citation network exploration.

Talks exclusively to the GraphProvider protocol — never to
SQLAlchemy models directly. This ensures any future graph
database backend can be swapped in without touching this file.
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.logging import get_logger
from app.services.graph import get_graph_provider
from app.services.s2 import background_sync_entry
from app.services.s2_corpus import get_local_source

logger = get_logger(__name__)

router = APIRouter(prefix="/graph", tags=["graph"])


# ──────────────────────────────────────────────────────────
# Response models — stable API contract
# ──────────────────────────────────────────────────────────


class GraphNodeResponse(BaseModel):
    """A node in the citation graph."""

    id: str
    title: str
    year: Optional[int] = None
    venue: Optional[str] = None
    authors: list[str] = []
    citation_count: int = 0
    fields_of_study: list[str] = []
    in_library: bool = False
    entry_id: Optional[str] = None


class GraphEdgeResponse(BaseModel):
    """A directed edge: source cites target."""

    source: str
    target: str
    is_influential: bool = False


class GraphResponse(BaseModel):
    """Complete subgraph payload."""

    center_id: str
    nodes: list[GraphNodeResponse] = []
    edges: list[GraphEdgeResponse] = []
    prior_works: list["AggregateEntryResponse"] = []
    derivative_works: list["AggregateEntryResponse"] = []
    similarity_edges: list["SimilarityEdgeResponse"] = []


class AggregateEntryResponse(BaseModel):
    """A paper surfaced by aggregate analysis."""

    id: str
    title: str
    year: Optional[int] = None
    venue: Optional[str] = None
    authors: list[str] = []
    citation_count: int = 0
    frequency: int = 0
    in_library: bool = False
    entry_id: Optional[str] = None


class SimilarityEdgeResponse(BaseModel):
    """An undirected similarity edge between two papers."""

    source: str
    target: str
    weight: float


# ──────────────────────────────────────────────────────────
# Endpoint
# ──────────────────────────────────────────────────────────


@router.get("/{entry_id}", response_model=GraphResponse)
async def get_graph(
    entry_id: UUID,
    background_tasks: BackgroundTasks,
    depth: int = Query(default=1, ge=1, le=2, description="Hops to expand (1 or 2)"),
    max_nodes: int = Query(
        default=80, ge=10, le=200, description="Max nodes to return"
    ),
    db: AsyncSession = Depends(get_db),
):
    """
    Get the citation subgraph centered on a library entry.

    DuckDB-first: builds graph instantly from local corpus data.
    API sync runs in the background for future benefit.
    """
    local = get_local_source()
    provider = get_graph_provider(db, source=local)
    entry_id_str = str(entry_id)

    # Fire background sync (non-blocking — enriches data for next request)
    background_tasks.add_task(background_sync_entry, entry_id_str)

    # Resolve entry to S2 ID from Postgres
    s2_id = await provider.resolve_entry_s2_id(entry_id_str)

    if not s2_id:
        # Entry has no s2_id yet — try DuckDB resolution via DOI/ArXiv
        if local:
            from sqlalchemy import select
            from app.models import Entry

            result = await db.execute(select(Entry).where(Entry.id == entry_id_str))
            entry = result.scalar_one_or_none()
            if entry:
                # Try DOI
                for fields in [
                    entry.required_fields or {},
                    entry.optional_fields or {},
                ]:
                    doi = fields.get("doi") or fields.get("DOI")
                    if doi:
                        s2_id = await local.resolve_id("DOI", doi.strip())
                        if s2_id:
                            break
                # Try ArXiv
                if not s2_id:
                    for fields in [
                        entry.required_fields or {},
                        entry.optional_fields or {},
                    ]:
                        arxiv = fields.get("arxiv") or fields.get("eprint")
                        if arxiv:
                            s2_id = await local.resolve_id("ArXiv", arxiv.strip())
                            if s2_id:
                                break

    if not s2_id:
        return GraphResponse(center_id=entry_id_str)

    # Build graph entirely from DuckDB (instant)
    graph_data = await provider.get_subgraph(
        center_s2_id=s2_id,
        depth=depth,
        max_nodes=max_nodes,
    )

    # Convert domain objects to response models
    nodes = [
        GraphNodeResponse(
            id=n.id,
            title=n.title,
            year=n.year,
            venue=n.venue,
            authors=n.authors,
            citation_count=n.citation_count,
            fields_of_study=n.fields_of_study,
            in_library=n.in_library,
            entry_id=n.entry_id,
        )
        for n in graph_data.nodes
    ]

    edges = [
        GraphEdgeResponse(
            source=e.source,
            target=e.target,
            is_influential=e.is_influential,
        )
        for e in graph_data.edges
    ]

    return GraphResponse(
        center_id=graph_data.center_id,
        nodes=nodes,
        edges=edges,
        prior_works=[
            AggregateEntryResponse(
                id=p.id,
                title=p.title,
                year=p.year,
                venue=p.venue,
                authors=p.authors,
                citation_count=p.citation_count,
                frequency=p.frequency,
                in_library=p.in_library,
                entry_id=p.entry_id,
            )
            for p in graph_data.prior_works
        ],
        derivative_works=[
            AggregateEntryResponse(
                id=p.id,
                title=p.title,
                year=p.year,
                venue=p.venue,
                authors=p.authors,
                citation_count=p.citation_count,
                frequency=p.frequency,
                in_library=p.in_library,
                entry_id=p.entry_id,
            )
            for p in graph_data.derivative_works
        ],
        similarity_edges=[
            SimilarityEdgeResponse(
                source=se.source,
                target=se.target,
                weight=round(se.weight, 4),
            )
            for se in graph_data.similarity_edges
        ],
    )
