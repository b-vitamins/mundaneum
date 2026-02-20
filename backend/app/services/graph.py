"""
Graph data provider protocol and implementations.

Architecture follows Sussman's "Design for Flexibility" — the graph
provider is a protocol (abstract interface) so any graph database
(Neo4j, TigerGraph, etc.) can be dropped in later without changing
the router or any consumer code.
"""

from __future__ import annotations

import logging
import math
from collections import Counter, deque
from dataclasses import dataclass, field
from itertools import combinations
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
class AggregateEntry:
    """A paper surfaced by aggregate analysis (prior/derivative works)."""

    id: str  # s2_id
    title: str
    year: int | None = None
    venue: str | None = None
    authors: list[str] = field(default_factory=list)
    citation_count: int = 0
    frequency: int = 0  # how many graph nodes cite/are cited by this
    in_library: bool = False
    entry_id: str | None = None


@dataclass(slots=True)
class GraphData:
    """Complete subgraph payload — the transport contract."""

    center_id: str
    nodes: list[GraphNode] = field(default_factory=list)
    edges: list[GraphEdge] = field(default_factory=list)
    similarity_edges: list["SimilarityEdge"] = field(default_factory=list)
    prior_works: list[AggregateEntry] = field(default_factory=list)
    derivative_works: list[AggregateEntry] = field(default_factory=list)


@dataclass(slots=True)
class SimilarityEdge:
    """An undirected similarity edge between two papers."""

    source: str  # s2_id
    target: str  # s2_id
    weight: float  # 0–1 similarity score


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

        # ── Compute similarity edges ──
        similarity_edges = self._compute_similarity(selected_ids, all_edges)

        # ── Compute Prior & Derivative Works ──
        prior_works = await self._compute_aggregate(selected_ids, direction="prior")
        derivative_works = await self._compute_aggregate(
            selected_ids, direction="derivative"
        )

        logger.info(
            "Graph for %s: %d nodes, %d edges, %d prior, %d derivative (depth=%d, max=%d)",
            center_s2_id,
            len(nodes),
            len(edges),
            len(prior_works),
            len(derivative_works),
            depth,
            max_nodes,
        )

        return GraphData(
            center_id=center_s2_id,
            nodes=nodes,
            edges=edges,
            similarity_edges=similarity_edges,
            prior_works=prior_works,
            derivative_works=derivative_works,
        )

    def _compute_similarity(
        self,
        selected_ids: set[str],
        all_edges: list[tuple[str, str, bool]],
        min_weight: float = 0.05,
    ) -> list[SimilarityEdge]:
        """
        Compute similarity edges via co-citation + bibliographic coupling.

        Co-citation:  How many papers cite BOTH A and B?
        Bib coupling: How many papers are cited by BOTH A and B?
        Combined:     max(jaccard_cocitation, jaccard_coupling)

        This is an alternative "lens" on the same graph data —
        one of many possible views, not privileged above others.
        """
        # Build per-paper neighborhoods from ALL edges (not just selected)
        citers_of: dict[str, set[str]] = {}  # paper -> set of papers that cite it
        refs_of: dict[str, set[str]] = {}  # paper -> set of papers it cites

        for src, tgt, _ in all_edges:
            citers_of.setdefault(tgt, set()).add(src)
            refs_of.setdefault(src, set()).add(tgt)

        # Compute pairwise Jaccard for selected nodes
        selected_list = list(selected_ids)
        sim_edges: list[SimilarityEdge] = []

        for a, b in combinations(selected_list, 2):
            # Co-citation Jaccard
            ca = citers_of.get(a, set())
            cb = citers_of.get(b, set())
            cc_union = len(ca | cb)
            jc_cocite = len(ca & cb) / cc_union if cc_union > 0 else 0.0

            # Bibliographic coupling Jaccard
            ra = refs_of.get(a, set())
            rb = refs_of.get(b, set())
            bc_union = len(ra | rb)
            jc_bibcoup = len(ra & rb) / bc_union if bc_union > 0 else 0.0

            # Combined: max of both signals
            weight = max(jc_cocite, jc_bibcoup)

            if weight >= min_weight:
                sim_edges.append(SimilarityEdge(source=a, target=b, weight=weight))

        # Sort by weight descending, cap at reasonable number
        sim_edges.sort(key=lambda e: e.weight, reverse=True)
        return sim_edges[:500]

    async def _compute_aggregate(
        self,
        graph_ids: set[str],
        direction: str,
        limit: int = 15,
    ) -> list[AggregateEntry]:
        """
        Compute prior or derivative works for the subgraph.

        Prior works: papers cited by many graph nodes (seminal foundations).
        Derivative works: papers that cite many graph nodes (surveys/recent).
        """
        graph_id_list = list(graph_ids)
        chunk_size = 500
        counter: Counter[str] = Counter()

        if direction == "prior":
            # Find papers cited BY graph nodes (graph_node -> target)
            # We want targets NOT in the graph
            for i in range(0, len(graph_id_list), chunk_size):
                chunk = graph_id_list[i : i + chunk_size]
                result = await self.session.execute(
                    select(S2Citation.target_id).where(S2Citation.source_id.in_(chunk))
                )
                for (target_id,) in result:
                    if target_id not in graph_ids:
                        counter[target_id] += 1
        else:
            # Find papers that CITE graph nodes (source -> graph_node)
            # We want sources NOT in the graph
            for i in range(0, len(graph_id_list), chunk_size):
                chunk = graph_id_list[i : i + chunk_size]
                result = await self.session.execute(
                    select(S2Citation.source_id).where(S2Citation.target_id.in_(chunk))
                )
                for (source_id,) in result:
                    if source_id not in graph_ids:
                        counter[source_id] += 1

        if not counter:
            return []

        # Get top candidates (by frequency first, then we'll re-rank)
        # Take more than limit so we can rank by frequency * citation_count
        top_ids = [pid for pid, _ in counter.most_common(limit * 3)]

        # Fetch paper metadata
        papers_by_id: dict[str, S2Paper] = {}
        for i in range(0, len(top_ids), chunk_size):
            chunk = top_ids[i : i + chunk_size]
            result = await self.session.execute(
                select(S2Paper).where(S2Paper.s2_id.in_(chunk))
            )
            for paper in result.scalars():
                papers_by_id[paper.s2_id] = paper

        # In-library detection
        library_map: dict[str, str] = {}
        for i in range(0, len(top_ids), chunk_size):
            chunk = top_ids[i : i + chunk_size]
            result = await self.session.execute(
                select(Entry.s2_id, Entry.id).where(
                    Entry.s2_id.in_(chunk), Entry.s2_id.isnot(None)
                )
            )
            for s2_id, entry_id in result:
                library_map[s2_id] = str(entry_id)

        # Build entries, rank by frequency * log(citation_count + 1)

        entries: list[AggregateEntry] = []
        for pid in top_ids:
            paper = papers_by_id.get(pid)
            if not paper:
                continue

            freq = counter[pid]
            if freq < 2:
                continue  # Must be cited/citing at least 2 graph nodes

            authors = []
            if paper.authors:
                for a in paper.authors[:3]:
                    if isinstance(a, dict):
                        authors.append(a.get("name", "Unknown"))
                    else:
                        authors.append(str(a))

            entries.append(
                AggregateEntry(
                    id=paper.s2_id,
                    title=paper.title or "Untitled",
                    year=paper.year,
                    venue=paper.venue,
                    authors=authors,
                    citation_count=paper.citation_count or 0,
                    frequency=freq,
                    in_library=pid in library_map,
                    entry_id=library_map.get(pid),
                )
            )

        # Sort by frequency * log(citations+1), descending
        entries.sort(
            key=lambda e: e.frequency * math.log(e.citation_count + 1),
            reverse=True,
        )

        return entries[:limit]


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
