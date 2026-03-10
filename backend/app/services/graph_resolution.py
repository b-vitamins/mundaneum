"""
Resolution helpers for graph entry centers.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Entry
from app.services.graph import GraphProvider
from app.services.s2_corpus import LocalCorpus


async def resolve_graph_center_s2_id(
    entry_id: str,
    db: AsyncSession,
    provider: GraphProvider,
    local_source: LocalCorpus | None,
) -> str | None:
    """Resolve an entry's graph center via stored S2 ID or local corpus IDs."""
    s2_id = await provider.resolve_entry_s2_id(entry_id)
    if s2_id or local_source is None:
        return s2_id

    result = await db.execute(select(Entry).where(Entry.id == entry_id))
    entry = result.scalar_one_or_none()
    if entry is None:
        return None

    doi = entry.bib_metadata.get("doi")
    if doi:
        s2_id = await local_source.resolve_id("DOI", doi)
        if s2_id:
            return s2_id

    arxiv = entry.bib_metadata.get("arxiv", "eprint")
    if arxiv:
        s2_id = await local_source.resolve_id("ArXiv", arxiv)
        if s2_id:
            return s2_id

    return None
