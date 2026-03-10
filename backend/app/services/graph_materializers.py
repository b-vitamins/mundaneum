"""
Graph payload materializers and library lookup helpers.
"""

import math
from collections import Counter
from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Entry
from app.services.graph_models import AggregateEntry, GraphNode
from app.services.s2_protocol import PaperRecord


def author_names(paper: PaperRecord, limit: int = 3) -> list[str]:
    """Normalize heterogeneous author payloads to display names."""
    names: list[str] = []
    for author in (paper.authors or [])[:limit]:
        if isinstance(author, dict):
            names.append(author.get("name", "Unknown"))
        else:
            names.append(str(author))
    return names


async def load_library_map(
    session: AsyncSession,
    s2_ids: Iterable[str],
) -> dict[str, str]:
    """Map S2 IDs to library entry IDs for a batch of papers."""
    selected_ids = list(s2_ids)
    if not selected_ids:
        return {}

    library_map: dict[str, str] = {}
    chunk_size = 500
    for index in range(0, len(selected_ids), chunk_size):
        chunk = selected_ids[index : index + chunk_size]
        result = await session.execute(
            select(Entry.s2_id, Entry.id).where(
                Entry.s2_id.in_(chunk), Entry.s2_id.isnot(None)
            )
        )
        for s2_id, entry_id in result:
            library_map[s2_id] = str(entry_id)
    return library_map


def build_graph_nodes(
    selected_ids: Iterable[str],
    papers_by_id: dict[str, PaperRecord],
    library_map: dict[str, str],
) -> list[GraphNode]:
    """Build graph node payloads from canonical paper records."""
    nodes: list[GraphNode] = []
    for paper_id in selected_ids:
        paper = papers_by_id.get(paper_id)
        if paper is None:
            continue
        nodes.append(
            GraphNode(
                id=paper.s2_id or paper_id,
                title=paper.title or "Untitled",
                year=paper.year,
                venue=paper.venue,
                authors=author_names(paper),
                citation_count=paper.citation_count,
                fields_of_study=paper.fields_of_study,
                in_library=paper_id in library_map,
                entry_id=library_map.get(paper_id),
            )
        )
    return nodes


def build_aggregate_entries(
    ranked_ids: Iterable[str],
    papers_by_id: dict[str, PaperRecord],
    frequency_counter: Counter[str],
    library_map: dict[str, str],
    limit: int,
) -> list[AggregateEntry]:
    """Build and rank aggregate entry payloads."""
    entries: list[AggregateEntry] = []
    for paper_id in ranked_ids:
        paper = papers_by_id.get(paper_id)
        if paper is None:
            continue

        entries.append(
            AggregateEntry(
                id=paper.s2_id or paper_id,
                title=paper.title or "Untitled",
                year=paper.year,
                venue=paper.venue,
                authors=author_names(paper),
                citation_count=paper.citation_count,
                frequency=frequency_counter[paper_id],
                in_library=paper_id in library_map,
                entry_id=library_map.get(paper_id),
            )
        )

    entries.sort(
        key=lambda entry: entry.frequency * math.log(entry.citation_count + 1),
        reverse=True,
    )
    return entries[:limit]
