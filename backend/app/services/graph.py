"""
Graph data provider protocol and implementations.

Architecture follows Sussman's "Design for Flexibility" — the graph
provider is a protocol (abstract interface) so any graph database
(Neo4j, TigerGraph, etc.) can be dropped in later without changing
the router or any consumer code.
"""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Entry, S2Citation, S2Paper

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────
# Domain types — stable contract between layers
# ──────────────────────────────────────────────────────────


@dataclass(slots=True)
class GraphNode:
    """A node in the citation graph."""

    id: str  # s2_id
    title: str
    year: int | None = None
    venue: str | None = None
    authors: list[str] = field(default_factory=list)
    citation_count: int = 0
    fields_of_study: list[str] = field(default_factory=list)
    in_library: bool = False
    entry_id: str | None = None  # Folio UUID if in library


@dataclass(slots=True)
class GraphEdge:
    """A directed edge: source cites target."""

    source: str  # s2_id
    target: str  # s2_id
    is_influential: bool = False


@dataclass(slots=True)
class GraphData:
    """Complete subgraph payload — the transport contract."""

    center_id: str
    nodes: list[GraphNode] = field(default_factory=list)
    edges: list[GraphEdge] = field(default_factory=list)


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
        """Resolve a Folio entry UUID to its Semantic Scholar paper ID."""
        ...


# ──────────────────────────────────────────────────────────
# V1 implementation: SQL over S2Paper / S2Citation tables
# ──────────────────────────────────────────────────────────


class SQLAlchemyGraphProvider:
    """
    Graph provider backed by the existing S2Paper and S2Citation
    tables via SQLAlchemy async queries.

    BFS expansion, in-library detection, citation-count ranking.
    Efficient for subgraphs up to a few hundred nodes.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def resolve_entry_s2_id(self, entry_id: str) -> str | None:
        """Resolve a Folio entry UUID to its Semantic Scholar paper ID."""
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
        """
        BFS expansion over S2Citation edges.

        1. Start from center_s2_id.
        2. At each depth level, fetch all citation edges (both directions).
        3. Collect unique paper IDs.
        4. Fetch paper metadata for all discovered IDs.
        5. Cross-reference against Entry.s2_id for in-library detection.
        6. Cap at max_nodes by citation count (center always included).
        """
        depth = min(depth, 2)  # Hard cap at 2 hops
        max_nodes = min(max_nodes, 200)  # Hard cap at 200

        # ── BFS to discover paper IDs and edges ──
        visited: set[str] = {center_s2_id}
        frontier: deque[str] = deque([center_s2_id])
        all_edges: list[tuple[str, str, bool]] = []  # (source, target, influential)
        current_depth = 0

        while frontier and current_depth < depth:
            level_size = len(frontier)
            next_ids: set[str] = set()

            # Process in batches (the frontier for this depth level)
            level_ids = [frontier.popleft() for _ in range(level_size)]

            # Fetch outgoing edges (this paper cites others)
            outgoing = await self.session.execute(
                select(
                    S2Citation.source_id,
                    S2Citation.target_id,
                    S2Citation.is_influential,
                ).where(S2Citation.source_id.in_(level_ids))
            )
            for src, tgt, influential in outgoing:
                all_edges.append((src, tgt, influential))
                if tgt not in visited:
                    next_ids.add(tgt)

            # Fetch incoming edges (others cite this paper)
            incoming = await self.session.execute(
                select(
                    S2Citation.source_id,
                    S2Citation.target_id,
                    S2Citation.is_influential,
                ).where(S2Citation.target_id.in_(level_ids))
            )
            for src, tgt, influential in incoming:
                all_edges.append((src, tgt, influential))
                if src not in visited:
                    next_ids.add(src)

            # Add discovered IDs to visited and frontier
            visited.update(next_ids)
            frontier.extend(next_ids)
            current_depth += 1

        # ── Fetch paper metadata for all discovered IDs ──
        all_paper_ids = list(visited)
        papers_by_id: dict[str, S2Paper] = {}

        # Batch fetch in chunks of 500 to avoid overly large IN clauses
        chunk_size = 500
        for i in range(0, len(all_paper_ids), chunk_size):
            chunk = all_paper_ids[i : i + chunk_size]
            result = await self.session.execute(
                select(S2Paper).where(S2Paper.s2_id.in_(chunk))
            )
            for paper in result.scalars():
                papers_by_id[paper.s2_id] = paper

        # ── Rank and cap nodes ──
        # Center always included; others ranked by citation count
        ranked_ids = sorted(
            [pid for pid in papers_by_id if pid != center_s2_id],
            key=lambda pid: papers_by_id[pid].citation_count or 0,
            reverse=True,
        )
        # Keep center + top (max_nodes - 1)
        selected_ids = {center_s2_id} | set(ranked_ids[: max_nodes - 1])

        # ── In-library detection ──
        # Cross-reference selected s2_ids against Entry.s2_id
        library_map: dict[str, str] = {}  # s2_id -> entry_id
        selected_id_list = list(selected_ids)
        for i in range(0, len(selected_id_list), chunk_size):
            chunk = selected_id_list[i : i + chunk_size]
            result = await self.session.execute(
                select(Entry.s2_id, Entry.id).where(
                    Entry.s2_id.in_(chunk), Entry.s2_id.isnot(None)
                )
            )
            for s2_id, entry_id in result:
                library_map[s2_id] = str(entry_id)

        # ── Build response ──
        nodes: list[GraphNode] = []
        for pid in selected_ids:
            paper = papers_by_id.get(pid)
            if not paper:
                continue

            # Extract first 3 author names
            authors = []
            if paper.authors:
                for a in paper.authors[:3]:
                    if isinstance(a, dict):
                        authors.append(a.get("name", "Unknown"))
                    else:
                        authors.append(str(a))

            nodes.append(
                GraphNode(
                    id=paper.s2_id,
                    title=paper.title or "Untitled",
                    year=paper.year,
                    venue=paper.venue,
                    authors=authors,
                    citation_count=paper.citation_count or 0,
                    fields_of_study=paper.fields_of_study or [],
                    in_library=pid in library_map,
                    entry_id=library_map.get(pid),
                )
            )

        # Filter edges to only include selected nodes
        edges: list[GraphEdge] = []
        seen_edges: set[tuple[str, str]] = set()
        for src, tgt, influential in all_edges:
            if src in selected_ids and tgt in selected_ids:
                edge_key = (src, tgt)
                if edge_key not in seen_edges:
                    seen_edges.add(edge_key)
                    edges.append(
                        GraphEdge(
                            source=src,
                            target=tgt,
                            is_influential=influential,
                        )
                    )

        logger.info(
            "Graph for %s: %d nodes, %d edges (depth=%d, max=%d)",
            center_s2_id,
            len(nodes),
            len(edges),
            depth,
            max_nodes,
        )

        return GraphData(center_id=center_s2_id, nodes=nodes, edges=edges)


# ──────────────────────────────────────────────────────────
# Factory — swap implementations via config in the future
# ──────────────────────────────────────────────────────────


def get_graph_provider(session: AsyncSession) -> GraphProvider:
    """
    Factory function for obtaining a GraphProvider instance.

    Currently returns SQLAlchemyGraphProvider. To integrate a graph
    database, add a config setting and return the appropriate provider.
    """
    return SQLAlchemyGraphProvider(session)
