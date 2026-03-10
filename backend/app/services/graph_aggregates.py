"""
Aggregate graph entry computation.
"""

from __future__ import annotations

import asyncio
from collections import Counter

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.graph_fetch import load_papers
from app.services.graph_materializers import build_aggregate_entries, load_library_map
from app.services.graph_models import AggregateEntry
from app.services.s2_protocol import S2DataSource


async def compute_aggregate_entries(
    session: AsyncSession,
    source: S2DataSource,
    graph_ids: set[str],
    *,
    direction: str,
    limit: int = 20,
) -> list[AggregateEntry]:
    """Compute prior or derivative works for a selected subgraph."""
    counter = await count_aggregate_ids(source, graph_ids, direction=direction)
    if not counter:
        return []

    top_ids = [paper_id for paper_id, _ in counter.most_common(limit * 3)]
    papers_by_id = await load_papers(source, top_ids)
    library_map = await load_library_map(session, top_ids)
    return build_aggregate_entries(
        top_ids,
        papers_by_id,
        counter,
        library_map,
        limit=limit,
    )


async def count_aggregate_ids(
    source: S2DataSource,
    graph_ids: set[str],
    *,
    direction: str,
) -> Counter[str]:
    """Count candidate aggregate papers outside the selected graph."""
    counter: Counter[str] = Counter()

    async def _count_for(paper_id: str) -> list[str]:
        ids: list[str] = []
        if direction == "prior":
            refs = await source.get_references(paper_id)
            if refs:
                for edge in refs:
                    if edge.cited_s2_id and edge.cited_s2_id not in graph_ids:
                        ids.append(edge.cited_s2_id)
        else:
            citations = await source.get_citations(paper_id, limit=500)
            if citations:
                for edge in citations:
                    if edge.citing_s2_id and edge.citing_s2_id not in graph_ids:
                        ids.append(edge.citing_s2_id)
        return ids

    results = await asyncio.gather(*[_count_for(paper_id) for paper_id in graph_ids])
    for ids in results:
        for paper_id in ids:
            counter[paper_id] += 1

    return counter
