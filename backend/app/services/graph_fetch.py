"""
Graph traversal and paper-loading helpers.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterable

from app.services.s2_protocol import PaperRecord, S2DataSource

logger = logging.getLogger(__name__)

EdgeTuple = tuple[str, str, bool]


async def fetch_touching_edges(
    source: S2DataSource,
    paper_ids: Iterable[str],
    *,
    max_citations: int = 500,
) -> list[EdgeTuple]:
    """Fetch citation edges touching the given paper IDs."""

    async def _edges_for(paper_id: str) -> list[EdgeTuple]:
        result: list[EdgeTuple] = []
        refs = await source.get_references(paper_id)
        if refs:
            for edge in refs:
                if edge.cited_s2_id:
                    result.append((paper_id, edge.cited_s2_id, edge.is_influential))

        citations = await source.get_citations(paper_id, limit=max_citations)
        if citations:
            for edge in citations:
                if edge.citing_s2_id:
                    result.append((edge.citing_s2_id, paper_id, edge.is_influential))

        return result

    results = await asyncio.gather(*[_edges_for(paper_id) for paper_id in paper_ids])
    return flatten_edges(results)


async def fetch_reference_enrichment(
    source: S2DataSource,
    paper_ids: list[str],
    *,
    max_papers: int = 30,
) -> list[EdgeTuple]:
    """Fetch references for a bounded candidate set to enrich neighborhoods."""
    ids_to_fetch = paper_ids[:max_papers]

    async def _refs_for(paper_id: str) -> list[EdgeTuple]:
        result: list[EdgeTuple] = []
        refs = await source.get_references(paper_id)
        if refs:
            for edge in refs:
                if edge.cited_s2_id:
                    result.append((paper_id, edge.cited_s2_id, edge.is_influential))
        return result

    results = await asyncio.gather(*[_refs_for(paper_id) for paper_id in ids_to_fetch])
    edges = flatten_edges(results)
    logger.info(
        "Reference enrichment: %d edges for %d papers",
        len(edges),
        len(ids_to_fetch),
    )
    return edges


async def load_papers(
    source: S2DataSource,
    paper_ids: Iterable[str],
) -> dict[str, PaperRecord]:
    """Load paper metadata for a batch of S2 IDs."""
    ids = list(dict.fromkeys(paper_ids))
    if not ids:
        return {}

    results = await asyncio.gather(*[source.get_paper(paper_id) for paper_id in ids])
    papers: dict[str, PaperRecord] = {}
    for paper_id, paper in zip(ids, results):
        if paper is not None:
            papers[paper_id] = paper
    return papers


def flatten_edges(edge_groups: Iterable[list[EdgeTuple]]) -> list[EdgeTuple]:
    """Flatten nested edge batches into a single list."""
    edges: list[EdgeTuple] = []
    for group in edge_groups:
        edges.extend(group)
    return edges


def merge_edges(*edge_groups: Iterable[EdgeTuple]) -> list[EdgeTuple]:
    """Merge and deduplicate edge tuples while preserving insertion order."""
    return list(dict.fromkeys(edge for group in edge_groups for edge in group))


def candidate_ids_from_edges(
    edges: Iterable[EdgeTuple],
    *,
    exclude_id: str,
) -> set[str]:
    """Collect candidate IDs from edge endpoints."""
    candidate_ids: set[str] = set()
    for source, target, _ in edges:
        candidate_ids.add(source)
        candidate_ids.add(target)
    candidate_ids.discard(exclude_id)
    return candidate_ids


def rank_candidates_by_citations(
    candidate_ids: Iterable[str],
    papers_by_id: dict[str, PaperRecord],
) -> list[str]:
    """Rank candidate IDs by citation count using already-loaded paper metadata."""
    return sorted(
        candidate_ids,
        key=lambda paper_id: papers_by_id[paper_id].citation_count
        if paper_id in papers_by_id
        else 0,
        reverse=True,
    )
