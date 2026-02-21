"""
Graph data provider protocol and implementations.

Architecture follows Sussman's "Design for Flexibility" — the graph
provider is a protocol (abstract interface) so any graph database
(Neo4j, TigerGraph, etc.) can be dropped in later without changing
the router or any consumer code.
"""

from __future__ import annotations

import asyncio
import logging
import math
from collections import Counter
from dataclasses import dataclass, field
from itertools import combinations
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Entry, S2Citation, S2Paper

if TYPE_CHECKING:
    from app.services.s2 import S2Transport

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
    tables via SQLAlchemy async queries + live S2 API enrichment.

    Connected Papers style similarity-first node selection:
    1. Gather 1-hop candidates from local DB
    2. Enrich top candidates via S2 API (fetch their references)
    3. Rank candidates by co-citation + bibliographic coupling similarity
    4. Select top-N most similar papers
    5. Compute pairwise similarity edges between selected papers
    """

    def __init__(
        self,
        session: AsyncSession,
        transport: S2Transport | None = None,
    ):
        self.session = session
        self._transport = transport

    async def resolve_entry_s2_id(self, entry_id: str) -> str | None:
        """Resolve a Folio entry UUID to its Semantic Scholar paper ID."""
        result = await self.session.execute(
            select(Entry.s2_id).where(Entry.id == entry_id)
        )
        return result.scalar_one_or_none()

    async def _fetch_edges_db(
        self, paper_ids: list[str], chunk_size: int = 500
    ) -> list[tuple[str, str, bool]]:
        """Fetch all citation edges from local DB touching the given paper IDs."""
        edges: list[tuple[str, str, bool]] = []

        for i in range(0, len(paper_ids), chunk_size):
            chunk = paper_ids[i : i + chunk_size]

            outgoing = await self.session.execute(
                select(
                    S2Citation.source_id,
                    S2Citation.target_id,
                    S2Citation.is_influential,
                ).where(S2Citation.source_id.in_(chunk))
            )
            for src, tgt, inf in outgoing:
                edges.append((src, tgt, inf))

            incoming = await self.session.execute(
                select(
                    S2Citation.source_id,
                    S2Citation.target_id,
                    S2Citation.is_influential,
                ).where(S2Citation.target_id.in_(chunk))
            )
            for src, tgt, inf in incoming:
                edges.append((src, tgt, inf))

        return edges

    async def _enrich_from_api(
        self,
        paper_ids: list[str],
        max_papers: int = 30,
    ) -> list[tuple[str, str, bool]]:
        """
        Fetch references for candidate papers via the S2 API.

        Only fetches references (what each candidate cites) — this provides
        the bibliographic coupling signal. Co-citation data already comes
        from the local DB's 1-hop edges for the center paper.

        Rate-limited: 3 concurrent requests at a time to stay under S2's
        unauthenticated rate limit of ~1 req/sec.
        """
        if not self._transport:
            return []

        ids_to_fetch = paper_ids[:max_papers]
        edges: list[tuple[str, str, bool]] = []

        # Fetch references in small batches to avoid 429s
        batch_size = 3
        for batch_start in range(0, len(ids_to_fetch), batch_size):
            batch = ids_to_fetch[batch_start : batch_start + batch_size]

            tasks = [
                self._transport.get(
                    f"paper/{pid}/references",
                    params={
                        "fields": "citedPaper.paperId,isInfluential",
                        "limit": "100",
                    },
                )
                for pid in batch
            ]
            results = await asyncio.gather(*tasks)

            for pid, result in zip(batch, results):
                if not result or not result.get("data"):
                    continue
                for item in result["data"]:
                    cited = item.get("citedPaper") or {}
                    cited_id = cited.get("paperId")
                    if not cited_id:
                        continue
                    is_inf = item.get("isInfluential", False)
                    edges.append((pid, cited_id, is_inf))

        logger.info(
            "API enrichment: fetched %d reference edges for %d papers",
            len(edges),
            len(ids_to_fetch),
        )
        return edges

    def _build_neighborhoods(
        self, edges: list[tuple[str, str, bool]]
    ) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
        """Build citers-of and refs-of maps from edge list."""
        citers_of: dict[str, set[str]] = {}
        refs_of: dict[str, set[str]] = {}

        for src, tgt, _ in edges:
            citers_of.setdefault(tgt, set()).add(src)
            refs_of.setdefault(src, set()).add(tgt)

        return citers_of, refs_of

    def _similarity_to_center(
        self,
        center_id: str,
        candidate_id: str,
        citers_of: dict[str, set[str]],
        refs_of: dict[str, set[str]],
    ) -> float:
        """
        Compute similarity between a candidate paper and the center paper.

        Uses max(co-citation Jaccard, bibliographic coupling Jaccard).
        Connected Papers uses a similar metric.
        """
        cc = citers_of.get(center_id, set())
        ca = citers_of.get(candidate_id, set())
        cc_union = len(cc | ca)
        jc_cocite = len(cc & ca) / cc_union if cc_union > 0 else 0.0

        rc = refs_of.get(center_id, set())
        ra = refs_of.get(candidate_id, set())
        bc_union = len(rc | ra)
        jc_bibcoup = len(rc & ra) / bc_union if bc_union > 0 else 0.0

        return max(jc_cocite, jc_bibcoup)

    async def get_subgraph(
        self,
        center_s2_id: str,
        depth: int = 1,
        max_nodes: int = 80,
    ) -> GraphData:
        """
        Similarity-first graph construction (Connected Papers style).

        1. Gather 1-hop candidates from local DB.
        2. Pre-filter top candidates by citation count.
        3. Enrich via S2 API: fetch references + citations for candidates.
        4. Build neighborhoods from combined local + API data.
        5. Rank each candidate by Jaccard similarity to center.
        6. Select top max_nodes most similar papers.
        """
        max_nodes = min(max_nodes, 200)

        # ── Step 1: Gather 1-hop candidates from local DB ──
        hop1_edges = await self._fetch_edges_db([center_s2_id])

        candidate_ids: set[str] = set()
        for src, tgt, _ in hop1_edges:
            candidate_ids.add(src)
            candidate_ids.add(tgt)
        candidate_ids.discard(center_s2_id)

        if not candidate_ids:
            logger.info("No candidates found for %s", center_s2_id)
            return GraphData(center_id=center_s2_id)

        logger.info(
            "Graph %s: %d 1-hop candidates found",
            center_s2_id,
            len(candidate_ids),
        )

        # ── Step 2: Pre-filter top candidates by citation count ──
        # Fetch metadata for ranking (we need citation counts)
        chunk_size = 500
        all_papers: dict[str, S2Paper] = {}
        cand_list = list(candidate_ids | {center_s2_id})
        for i in range(0, len(cand_list), chunk_size):
            chunk = cand_list[i : i + chunk_size]
            result = await self.session.execute(
                select(S2Paper).where(S2Paper.s2_id.in_(chunk))
            )
            for paper in result.scalars():
                all_papers[paper.s2_id] = paper

        # Sort candidates by citation count, take top 100 for API enrichment
        ranked_candidates = sorted(
            candidate_ids,
            key=lambda pid: (all_papers[pid].citation_count or 0)
            if pid in all_papers
            else 0,
            reverse=True,
        )
        api_candidates = ranked_candidates[:100]

        # ── Step 3: Enrich via S2 API ──
        api_edges = await self._enrich_from_api(api_candidates)

        # Merge local DB edges + API edges
        edge_set: set[tuple[str, str, bool]] = set()
        for e in hop1_edges:
            edge_set.add(e)
        for e in api_edges:
            edge_set.add(e)
        all_edges = list(edge_set)

        logger.info(
            "Graph %s: %d total edges (local + API)",
            center_s2_id,
            len(all_edges),
        )

        # ── Step 4: Build neighborhoods and rank by similarity ──
        citers_of, refs_of = self._build_neighborhoods(all_edges)

        scored: list[tuple[str, float]] = []
        for cid in candidate_ids:
            sim = self._similarity_to_center(center_s2_id, cid, citers_of, refs_of)
            scored.append((cid, sim))

        scored.sort(key=lambda x: x[1], reverse=True)

        # ── Step 5: Select top max_nodes ──
        selected_ids = {center_s2_id}
        for cid, sim in scored[: max_nodes - 1]:
            if sim > 0:
                selected_ids.add(cid)

        logger.info(
            "Graph %s: %d nodes selected (of %d candidates with sim > 0)",
            center_s2_id,
            len(selected_ids),
            sum(1 for _, s in scored if s > 0),
        )

        # ── Fetch paper metadata for selected nodes ──
        # Use already-fetched papers + any new ones from API data
        papers_by_id: dict[str, S2Paper] = {}
        for pid in selected_ids:
            if pid in all_papers:
                papers_by_id[pid] = all_papers[pid]

        # Fetch any missing papers
        missing = [pid for pid in selected_ids if pid not in papers_by_id]
        for i in range(0, len(missing), chunk_size):
            chunk = missing[i : i + chunk_size]
            result = await self.session.execute(
                select(S2Paper).where(S2Paper.s2_id.in_(chunk))
            )
            for paper in result.scalars():
                papers_by_id[paper.s2_id] = paper

        selected_id_list = list(selected_ids)
        for i in range(0, len(selected_id_list), chunk_size):
            chunk = selected_id_list[i : i + chunk_size]
            result = await self.session.execute(
                select(S2Paper).where(S2Paper.s2_id.in_(chunk))
            )
            for paper in result.scalars():
                papers_by_id[paper.s2_id] = paper

        # ── In-library detection ──
        library_map: dict[str, str] = {}
        for i in range(0, len(selected_id_list), chunk_size):
            chunk = selected_id_list[i : i + chunk_size]
            result = await self.session.execute(
                select(Entry.s2_id, Entry.id).where(
                    Entry.s2_id.in_(chunk), Entry.s2_id.isnot(None)
                )
            )
            for s2_id, entry_id in result:
                library_map[s2_id] = str(entry_id)

        # ── Build GraphNode list ──
        nodes: list[GraphNode] = []
        for pid in selected_ids:
            paper = papers_by_id.get(pid)
            if not paper:
                continue

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

        # ── Citation edges (for citation view) ──
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

        # ── Similarity edges (for similarity view — primary) ──
        similarity_edges = self._compute_similarity(selected_ids, all_edges)

        # ── Prior & Derivative Works ──
        prior_works = await self._compute_aggregate(selected_ids, direction="prior")
        derivative_works = await self._compute_aggregate(
            selected_ids, direction="derivative"
        )

        logger.info(
            "Graph for %s: %d nodes, %d citation edges, %d similarity edges, "
            "%d prior, %d derivative",
            center_s2_id,
            len(nodes),
            len(edges),
            len(similarity_edges),
            len(prior_works),
            len(derivative_works),
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
        min_weight: float = 0.03,
    ) -> list[SimilarityEdge]:
        """
        Compute pairwise similarity edges via co-citation + bibliographic coupling.

        Co-citation:  How many papers cite BOTH A and B?
        Bib coupling: How many papers are cited by BOTH A and B?
        Combined:     max(jaccard_cocitation, jaccard_coupling)

        Lower threshold (0.03) than before to produce denser edges for
        the force-directed layout — proximity should encode similarity.
        """
        citers_of, refs_of = self._build_neighborhoods(all_edges)

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

            weight = max(jc_cocite, jc_bibcoup)

            if weight >= min_weight:
                sim_edges.append(SimilarityEdge(source=a, target=b, weight=weight))

        sim_edges.sort(key=lambda e: e.weight, reverse=True)
        return sim_edges[:800]

    async def _compute_aggregate(
        self,
        graph_ids: set[str],
        direction: str,
        limit: int = 20,
    ) -> list[AggregateEntry]:
        """
        Compute prior or derivative works for the subgraph.

        Prior works: papers cited by many graph nodes (seminal foundations).
        Derivative works: papers that cite many graph nodes (surveys/recent).

        No minimum frequency threshold — show all relevant papers ranked
        by frequency × log(citation_count + 1).
        """
        graph_id_list = list(graph_ids)
        chunk_size = 500
        counter: Counter[str] = Counter()

        if direction == "prior":
            for i in range(0, len(graph_id_list), chunk_size):
                chunk = graph_id_list[i : i + chunk_size]
                result = await self.session.execute(
                    select(S2Citation.target_id).where(S2Citation.source_id.in_(chunk))
                )
                for (target_id,) in result:
                    if target_id not in graph_ids:
                        counter[target_id] += 1
        else:
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

        # Take top candidates by raw frequency, then re-rank
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

        entries: list[AggregateEntry] = []
        for pid in top_ids:
            paper = papers_by_id.get(pid)
            if not paper:
                continue

            freq = counter[pid]
            # No minimum frequency threshold — show all, ranked by score

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

        # Sort by frequency × log(citations+1), descending
        entries.sort(
            key=lambda e: e.frequency * math.log(e.citation_count + 1),
            reverse=True,
        )

        return entries[:limit]


# ──────────────────────────────────────────────────────────
# Factory — swap implementations via config in the future
# ──────────────────────────────────────────────────────────


def get_graph_provider(
    session: AsyncSession,
    transport: S2Transport | None = None,
) -> GraphProvider:
    """
    Factory function for obtaining a GraphProvider instance.

    Pass transport to enable live S2 API enrichment for richer
    similarity graphs (Connected Papers style).
    """
    return SQLAlchemyGraphProvider(session, transport=transport)
