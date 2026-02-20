"""
Graph API router for citation network exploration.

Talks exclusively to the GraphProvider protocol — never to
SQLAlchemy models directly. This ensures any future graph
database backend can be swapped in without touching this file.
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.exceptions import NotFoundError
from app.logging import get_logger
from app.services.graph import get_graph_provider

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


# ──────────────────────────────────────────────────────────
# Endpoint
# ──────────────────────────────────────────────────────────


@router.get("/{entry_id}", response_model=GraphResponse)
async def get_graph(
    entry_id: UUID,
    depth: int = Query(default=1, ge=1, le=2, description="Hops to expand (1 or 2)"),
    max_nodes: int = Query(
        default=80, ge=10, le=200, description="Max nodes to return"
    ),
    db: AsyncSession = Depends(get_db),
):
    """
    Get the citation subgraph centered on a library entry.

    Returns nodes (papers) and edges (citation links) for
    interactive graph visualization.
    """
    provider = get_graph_provider(db)

    # Resolve entry to S2 ID
    s2_id = await provider.resolve_entry_s2_id(str(entry_id))
    if not s2_id:
        raise NotFoundError(
            "Graph data",
            f"Entry {entry_id} has no Semantic Scholar ID (S2 sync may be pending)",
        )

    # Fetch subgraph
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
    )
