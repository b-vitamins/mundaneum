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
from typing import Protocol, runtime_checkable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Entry
from app.services.s2_corpus import get_data_source
from app.services.s2_protocol import PaperRecord, S2DataSource

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
    Graph provider backed by ChainedSource (DuckDB → LiveAPI) for S2 data
    and SQLAlchemy for Folio entry lookups only.

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
        source: S2DataSource | None = None,
    ):
        self.session = session
        self._source = source or get_data_source()

    async def resolve_entry_s2_id(self, entry_id: str) -> str | None:
        """Resolve a Folio entry UUID to its Semantic Scholar paper ID."""
        result = await self.session.execute(
            select(Entry.s2_id).where(Entry.id == entry_id)
        )
        return result.scalar_one_or_none()

    async def _fetch_edges(
        self, paper_ids: list[str], max_citations: int = 500
    ) -> list[tuple[str, str, bool]]:
        """Fetch citation edges touching the given paper IDs.

        Parallelized: all DuckDB queries run concurrently via the thread pool.
        """

        async def _edges_for(pid: str) -> list[tuple[str, str, bool]]:
            result: list[tuple[str, str, bool]] = []
            refs = await self._source.get_references(pid)
            if refs:
                for e in refs:
                    if e.cited_s2_id:
                        result.append((pid, e.cited_s2_id, e.is_influential))
            cits = await self._source.get_citations(pid, limit=max_citations)
            if cits:
                for e in cits:
                    if e.citing_s2_id:
                        result.append((e.citing_s2_id, pid, e.is_influential))
            return result

        results = await asyncio.gather(*[_edges_for(pid) for pid in paper_ids])
        edges: list[tuple[str, str, bool]] = []
        for r in results:
            edges.extend(r)
        return edges

    async def _enrich_references(
        self,
        paper_ids: list[str],
        max_papers: int = 30,
    ) -> list[tuple[str, str, bool]]:
        """Fetch references for candidate papers (parallelized)."""
        ids_to_fetch = paper_ids[:max_papers]

        async def _refs_for(pid: str) -> list[tuple[str, str, bool]]:
            result: list[tuple[str, str, bool]] = []
            refs = await self._source.get_references(pid)
            if refs:
                for e in refs:
                    if e.cited_s2_id:
                        result.append((pid, e.cited_s2_id, e.is_influential))
            return result

        results = await asyncio.gather(*[_refs_for(pid) for pid in ids_to_fetch])
        edges: list[tuple[str, str, bool]] = []
        for r in results:
            edges.extend(r)

        logger.info(
            "Reference enrichment: %d edges for %d papers",
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

        # ── Step 1: Gather 1-hop candidates via ChainedSource ──
        hop1_edges = await self._fetch_edges([center_s2_id])

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
        all_papers: dict[str, PaperRecord] = {}
        cand_list = list(candidate_ids | {center_s2_id})

        # Fetch paper metadata for ranking via ChainedSource
        fetch_tasks = [self._source.get_paper(pid) for pid in cand_list]
        fetch_results = await asyncio.gather(*fetch_tasks)
        for pid, paper in zip(cand_list, fetch_results):
            if paper:
                all_papers[pid] = paper

        # Sort candidates by citation count, take top 100 for enrichment
        ranked_candidates = sorted(
            candidate_ids,
            key=lambda pid: all_papers[pid].citation_count if pid in all_papers else 0,
            reverse=True,
        )
        enrich_candidates = ranked_candidates[:100]

        # ── Step 3: Enrich via ChainedSource (instant from DuckDB) ──
        enrichment_edges = await self._enrich_references(enrich_candidates)

        # Merge 1-hop edges + enrichment edges
        edge_set: set[tuple[str, str, bool]] = set()
        for e in hop1_edges:
            edge_set.add(e)
        for e in enrichment_edges:
            edge_set.add(e)
        all_edges = list(edge_set)

        logger.info(
            "Graph %s: %d total edges",
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
        papers_by_id: dict[str, PaperRecord] = {}
        for pid in selected_ids:
            if pid in all_papers:
                papers_by_id[pid] = all_papers[pid]

        # Fetch any missing papers
        missing = [pid for pid in selected_ids if pid not in papers_by_id]
        if missing:
            missing_tasks = [self._source.get_paper(pid) for pid in missing]
            missing_results = await asyncio.gather(*missing_tasks)
            for pid, paper in zip(missing, missing_results):
                if paper:
                    papers_by_id[pid] = paper

        # ── In-library detection ──
        selected_id_list = list(selected_ids)
        library_map: dict[str, str] = {}
        chunk_size = 500
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
                    id=paper.s2_id or pid,
                    title=paper.title or "Untitled",
                    year=paper.year,
                    venue=paper.venue,
                    authors=authors,
                    citation_count=paper.citation_count,
                    fields_of_study=paper.fields_of_study,
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
        """
        counter: Counter[str] = Counter()

        async def _count_for(pid: str) -> list[str]:
            ids: list[str] = []
            if direction == "prior":
                refs = await self._source.get_references(pid)
                if refs:
                    for e in refs:
                        if e.cited_s2_id and e.cited_s2_id not in graph_ids:
                            ids.append(e.cited_s2_id)
            else:
                cits = await self._source.get_citations(pid, limit=500)
                if cits:
                    for e in cits:
                        if e.citing_s2_id and e.citing_s2_id not in graph_ids:
                            ids.append(e.citing_s2_id)
            return ids

        results = await asyncio.gather(*[_count_for(pid) for pid in graph_ids])
        for ids in results:
            for s2_id in ids:
                counter[s2_id] += 1

        if not counter:
            return []

        # Take top candidates by raw frequency, then re-rank
        top_ids = [pid for pid, _ in counter.most_common(limit * 3)]

        # Fetch paper metadata via ChainedSource
        fetch_tasks = [self._source.get_paper(pid) for pid in top_ids]
        fetch_results = await asyncio.gather(*fetch_tasks)
        papers_by_id: dict[str, PaperRecord] = {}
        for pid, paper in zip(top_ids, fetch_results):
            if paper:
                papers_by_id[pid] = paper

        # In-library detection
        library_map: dict[str, str] = {}
        chunk_size = 500
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

            authors = []
            if paper.authors:
                for a in paper.authors[:3]:
                    if isinstance(a, dict):
                        authors.append(a.get("name", "Unknown"))
                    else:
                        authors.append(str(a))

            entries.append(
                AggregateEntry(
                    id=paper.s2_id or pid,
                    title=paper.title or "Untitled",
                    year=paper.year,
                    venue=paper.venue,
                    authors=authors,
                    citation_count=paper.citation_count,
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
    source: S2DataSource | None = None,
) -> GraphProvider:
    """
    Factory function for obtaining a GraphProvider instance.

    Uses ChainedSource (DuckDB → LiveAPI) for all S2 data access.
    """
    return SQLAlchemyGraphProvider(session, source=source)
