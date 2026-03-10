"""
Graph API router for citation network exploration.

Talks exclusively to the GraphProvider protocol — never to
SQLAlchemy models directly. This ensures any future graph
database backend can be swapped in without touching this file.
"""

from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.logging import get_logger
from app.schemas.graph import GraphResponse, graph_response_from_data
from app.services.graph import get_graph_provider
from app.services.graph_resolution import resolve_graph_center_s2_id
from app.services.s2 import background_sync_entry

logger = get_logger(__name__)

router = APIRouter(prefix="/graph", tags=["graph"])


# ──────────────────────────────────────────────────────────
# Endpoint
# ──────────────────────────────────────────────────────────


@router.get("/{entry_id}", response_model=GraphResponse)
async def get_graph(
    entry_id: UUID,
    request: Request,
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
    s2_runtime = request.app.state.context.services.s2_runtime
    local = s2_runtime.local_source
    provider = get_graph_provider(db, source=s2_runtime.data_source)
    entry_id_str = str(entry_id)

    # Fire background sync (non-blocking — enriches data for next request)
    background_tasks.add_task(background_sync_entry, s2_runtime.orchestrator, entry_id_str)

    s2_id = await resolve_graph_center_s2_id(entry_id_str, db, provider, local)

    if not s2_id:
        return GraphResponse(center_id=entry_id_str)

    # Build graph entirely from DuckDB (instant)
    graph_data = await provider.get_subgraph(
        center_s2_id=s2_id,
        depth=depth,
        max_nodes=max_nodes,
    )

    return graph_response_from_data(graph_data)
