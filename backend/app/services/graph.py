"""
Graph data provider protocol and implementations.

Architecture follows Sussman's "Design for Flexibility" — the graph
provider is a protocol (abstract interface) so any graph database
(Neo4j, TigerGraph, etc.) can be dropped in later without changing
the router or any consumer code.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Entry
from app.services.graph_builder import build_similarity_subgraph
from app.services.graph_models import GraphData
from app.services.s2_protocol import S2DataSource


# ──────────────────────────────────────────────────────────
# GraphProvider protocol — the pluggable interface
# ──────────────────────────────────────────────────────────


@runtime_checkable
class GraphProvider(Protocol):
    """
    Abstract interface for graph data retrieval.

    Any graph database adapter (Neo4j, TigerGraph, JanusGraph, etc.)
    can implement this protocol and be swapped in via the factory
    function without changing a single line of router code.
    """

    async def get_subgraph(
        self,
        center_s2_id: str,
        depth: int = 1,
        max_nodes: int = 80,
    ) -> GraphData:
        """
        Return the citation neighborhood of `center_s2_id`.

        Args:
            center_s2_id: The S2 paper ID to center the graph on.
            depth: Number of hops to expand (1 or 2).
            max_nodes: Maximum nodes to return, prioritized by citation count.

        Returns:
            GraphData with nodes, edges, and center_id.
        """
        ...

    async def resolve_entry_s2_id(self, entry_id: str) -> str | None:
        """Resolve a Mundaneum entry UUID to its Semantic Scholar paper ID."""
        ...


# ──────────────────────────────────────────────────────────
# V1 implementation: SQL entry lookups + pluggable S2 source
# ──────────────────────────────────────────────────────────


class SQLAlchemyGraphProvider:
    """
    Graph provider backed by ChainedSource (DuckDB → LiveAPI) for S2 data
    and SQLAlchemy for Mundaneum entry lookups only.

    Connected Papers style similarity-first node selection:
    1. Gather 1-hop candidates via ChainedSource
    2. Fetch reference sets for candidates (instant from DuckDB)
    3. Rank candidates by co-citation + bibliographic coupling similarity
    4. Select top-N most similar papers
    5. Compute pairwise similarity edges between selected papers
    """

    def __init__(
        self,
        session: AsyncSession,
        source: S2DataSource,
    ):
        self.session = session
        self._source = source

    async def resolve_entry_s2_id(self, entry_id: str) -> str | None:
        """Resolve a Mundaneum entry UUID to its Semantic Scholar paper ID."""
        result = await self.session.execute(
            select(Entry.s2_id).where(Entry.id == entry_id)
        )
        return result.scalar_one_or_none()

    async def get_subgraph(
        self,
        center_s2_id: str,
        depth: int = 1,
        max_nodes: int = 80,
    ) -> GraphData:
        """Build a similarity-ranked graph payload for one center paper."""
        max_nodes = min(max_nodes, 200)
        return await build_similarity_subgraph(
            self.session,
            self._source,
            center_s2_id,
            depth=depth,
            max_nodes=max_nodes,
        )


# ──────────────────────────────────────────────────────────
# Factory — swap implementations via config in the future
# ──────────────────────────────────────────────────────────


def get_graph_provider(
    session: AsyncSession,
    source: S2DataSource,
) -> GraphProvider:
    """
    Factory function for obtaining a GraphProvider instance.

    Uses ChainedSource (DuckDB → LiveAPI) for all S2 data access.
    """
    return SQLAlchemyGraphProvider(session, source=source)
