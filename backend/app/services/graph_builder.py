"""
Graph assembly orchestration.
"""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.graph_aggregates import compute_aggregate_entries
from app.services.graph_algorithms import (
    build_neighborhoods,
    compute_similarity_edges,
    similarity_to_center,
)
from app.services.graph_fetch import (
    candidate_ids_from_edges,
    fetch_reference_enrichment,
    fetch_touching_edges,
    load_papers,
    merge_edges,
    rank_candidates_by_citations,
)
from app.services.graph_materializers import build_graph_nodes, load_library_map
from app.services.graph_models import GraphData, GraphEdge
from app.services.s2_protocol import PaperRecord, S2DataSource

logger = logging.getLogger(__name__)


async def build_similarity_subgraph(
    session: AsyncSession,
    source: S2DataSource,
    center_s2_id: str,
    *,
    depth: int,
    max_nodes: int,
) -> GraphData:
    """Build a graph payload centered on one S2 paper."""
    hop1_edges = await fetch_touching_edges(source, [center_s2_id])
    candidate_ids = candidate_ids_from_edges(hop1_edges, exclude_id=center_s2_id)
    if not candidate_ids:
        logger.info("No candidates found for %s", center_s2_id)
        return GraphData(center_id=center_s2_id)

    logger.info("Graph %s: %d 1-hop candidates found", center_s2_id, len(candidate_ids))

    all_papers = await load_papers(source, candidate_ids | {center_s2_id})
    ranked_candidates = rank_candidates_by_citations(candidate_ids, all_papers)
    enrich_candidates = ranked_candidates[:100]

    reference_edges = await fetch_reference_enrichment(source, enrich_candidates)
    expansion_edges: list[tuple[str, str, bool]] = []
    if depth > 1:
        expansion_edges = await fetch_touching_edges(
            source,
            enrich_candidates[:20],
            max_citations=200,
        )

    all_edges = merge_edges(hop1_edges, reference_edges, expansion_edges)
    candidate_ids = candidate_ids_from_edges(all_edges, exclude_id=center_s2_id)

    logger.info("Graph %s: %d total edges", center_s2_id, len(all_edges))

    citers_of, refs_of = build_neighborhoods(all_edges)
    selected_ids = select_graph_nodes(
        center_s2_id,
        candidate_ids,
        citers_of,
        refs_of,
        max_nodes=max_nodes,
    )

    logger.info(
        "Graph %s: %d nodes selected (of %d candidates with sim > 0)",
        center_s2_id,
        len(selected_ids),
        sum(
            1
            for candidate_id in candidate_ids
            if similarity_to_center(center_s2_id, candidate_id, citers_of, refs_of) > 0
        ),
    )

    papers_by_id = await hydrate_selected_papers(
        source,
        selected_ids,
        cached_papers=all_papers,
    )
    library_map = await load_library_map(session, selected_ids)
    nodes = build_graph_nodes(selected_ids, papers_by_id, library_map)
    edges = build_citation_edges(selected_ids, all_edges)
    similarity_edges = compute_similarity_edges(selected_ids, all_edges)
    prior_works = await compute_aggregate_entries(
        session,
        source,
        selected_ids,
        direction="prior",
    )
    derivative_works = await compute_aggregate_entries(
        session,
        source,
        selected_ids,
        direction="derivative",
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


def select_graph_nodes(
    center_s2_id: str,
    candidate_ids: set[str],
    citers_of: dict[str, set[str]],
    refs_of: dict[str, set[str]],
    *,
    max_nodes: int,
) -> set[str]:
    """Select the most similar nodes for the graph payload."""
    scored = [
        (
            candidate_id,
            similarity_to_center(center_s2_id, candidate_id, citers_of, refs_of),
        )
        for candidate_id in candidate_ids
    ]
    scored.sort(key=lambda item: item[1], reverse=True)

    selected_ids = {center_s2_id}
    for candidate_id, score in scored[: max_nodes - 1]:
        if score > 0:
            selected_ids.add(candidate_id)
    return selected_ids


async def hydrate_selected_papers(
    source: S2DataSource,
    selected_ids: set[str],
    *,
    cached_papers: dict[str, PaperRecord],
) -> dict[str, PaperRecord]:
    """Ensure selected graph nodes have paper metadata available."""
    papers_by_id = {
        paper_id: paper
        for paper_id, paper in cached_papers.items()
        if paper_id in selected_ids
    }
    missing_ids = [paper_id for paper_id in selected_ids if paper_id not in papers_by_id]
    if missing_ids:
        papers_by_id.update(await load_papers(source, missing_ids))
    return papers_by_id


def build_citation_edges(
    selected_ids: set[str],
    all_edges: list[tuple[str, str, bool]],
) -> list[GraphEdge]:
    """Build directed citation edges confined to the selected graph nodes."""
    edges: list[GraphEdge] = []
    seen_edges: set[tuple[str, str]] = set()

    for source, target, influential in all_edges:
        if source not in selected_ids or target not in selected_ids:
            continue
        edge_key = (source, target)
        if edge_key in seen_edges:
            continue
        seen_edges.add(edge_key)
        edges.append(
            GraphEdge(
                source=source,
                target=target,
                is_influential=influential,
            )
        )

    return edges
