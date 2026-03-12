"""
Persistence layer for Semantic Scholar records.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Protocol, runtime_checkable

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Entry, S2Citation, S2Paper
from app.schemas.s2 import S2Paper as S2PaperSchema

FULL_PAPER_FIELDS = [
    "paperId",
    "title",
    "year",
    "venue",
    "authors",
    "abstract",
    "tldr",
    "embedding",
    "citationCount",
    "referenceCount",
    "influentialCitationCount",
    "isOpenAccess",
    "openAccessPdf",
    "fieldsOfStudy",
    "publicationTypes",
    "externalIds",
]


@runtime_checkable
class PaperStore(Protocol):
    """Persistence layer for S2 data."""

    async def get_paper(self, s2_id: str) -> S2Paper | None:
        ...

    async def upsert_paper(self, data: dict) -> None:
        ...

    async def upsert_papers_batch(self, records: list[dict]) -> None:
        ...

    async def upsert_edges(self, edges: list[dict]) -> None:
        ...

    async def is_stale(self, s2_id: str, ttl_days: int) -> bool:
        ...

    async def set_entry_s2_id(self, entry_id: str, s2_id: str) -> None:
        ...

    async def unresolved_entries(self, limit: int) -> list[Entry]:
        ...

    async def get_entry(self, entry_id: str) -> Entry | None:
        ...

    async def commit(self) -> None:
        ...


class SQLAlchemyPaperStore:
    """PaperStore backed by PostgreSQL via SQLAlchemy async sessions."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_entry(self, entry_id: str) -> Entry | None:
        result = await self._session.execute(select(Entry).where(Entry.id == entry_id))
        return result.scalar_one_or_none()

    async def get_paper(self, s2_id: str) -> S2Paper | None:
        result = await self._session.execute(
            select(S2Paper).where(S2Paper.s2_id == s2_id)
        )
        return result.scalar_one_or_none()

    async def is_stale(self, s2_id: str, ttl_days: int) -> bool:
        paper = await self.get_paper(s2_id)
        if not paper or not paper.updated_at:
            return True
        return paper.updated_at < datetime.now(UTC) - timedelta(days=ttl_days)

    async def set_entry_s2_id(self, entry_id: str, s2_id: str) -> None:
        result = await self._session.execute(select(Entry).where(Entry.id == entry_id))
        entry = result.scalar_one_or_none()
        if entry is not None:
            entry.s2_id = s2_id
            self._session.add(entry)

    async def upsert_paper(self, data: dict) -> None:
        statement = insert(S2Paper).values(data)
        statement = statement.on_conflict_do_update(
            index_elements=[S2Paper.s2_id],
            set_={key: value for key, value in data.items() if key != "s2_id"},
        )
        await self._session.execute(statement)

    async def upsert_papers_batch(self, records: list[dict]) -> None:
        if not records:
            return
        statement = insert(S2Paper).values(records)
        statement = statement.on_conflict_do_nothing(index_elements=[S2Paper.s2_id])
        await self._session.execute(statement)

    async def upsert_edges(self, edges: list[dict]) -> None:
        if not edges:
            return
        statement = insert(S2Citation).values(edges)
        statement = statement.on_conflict_do_update(
            index_elements=[S2Citation.source_id, S2Citation.target_id],
            set_={
                "contexts": statement.excluded.contexts,
                "intents": statement.excluded.intents,
                "is_influential": statement.excluded.is_influential,
            },
        )
        await self._session.execute(statement)

    async def unresolved_entries(self, limit: int) -> list[Entry]:
        result = await self._session.execute(
            select(Entry)
            .where(Entry.s2_id.is_(None))
            .order_by(Entry.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def commit(self) -> None:
        await self._session.commit()


def paper_to_record(paper: S2PaperSchema) -> dict:
    """Convert a Pydantic S2Paper to a flat dict for DB upsert."""
    authors_data = [
        {"authorId": author.authorId, "name": author.name}
        for author in paper.authors
        if author.authorId
    ]
    return {
        "s2_id": paper.paperId,
        "title": paper.title or "",
        "year": paper.year,
        "venue": paper.venue,
        "authors": authors_data,
        "abstract": paper.abstract,
        "tldr": paper.tldr.model_dump() if paper.tldr else None,
        "citation_count": paper.citationCount or 0,
        "reference_count": paper.referenceCount or 0,
        "influential_citation_count": paper.influentialCitationCount or 0,
        "is_open_access": paper.isOpenAccess or False,
        "open_access_pdf": paper.openAccessPdf,
        "fields_of_study": paper.fieldsOfStudy or [],
        "publication_types": paper.publicationTypes or [],
        "external_ids": paper.externalIds or {},
        "embedding": paper.embedding.model_dump() if paper.embedding else None,
        "updated_at": datetime.now(UTC),
    }
