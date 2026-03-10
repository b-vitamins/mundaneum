"""
Sync orchestration for Semantic Scholar records.
"""

from __future__ import annotations

import asyncio
import enum
import logging
from datetime import UTC, datetime
from typing import Any, Callable

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session
from app.models import Entry
from app.schemas.s2 import S2GraphResponse
from app.schemas.s2 import S2Paper as S2PaperSchema
from app.services.s2_protocol import S2DataSource
from app.services.s2_resolvers import Resolver, default_resolvers, extract_identifier
from app.services.s2_store import FULL_PAPER_FIELDS, PaperStore, SQLAlchemyPaperStore, paper_to_record
from app.services.s2_transport import S2Transport

logger = logging.getLogger(__name__)


class SyncStatus(enum.Enum):
    """Result of an ensure_synced() call."""

    FRESH = "fresh"
    SYNCED = "synced"
    SYNCING = "syncing"
    FAILED = "failed"
    NO_MATCH = "no_match"


class SyncOrchestrator:
    """
    Compose transport, resolvers, and store into one sync API.
    """

    def __init__(
        self,
        transport: S2Transport,
        resolvers: list[Resolver],
        source: S2DataSource,
        sync_registry,
        session_factory: Callable[[], Any] = async_session,
        store_factory=None,
    ):
        self._transport = transport
        self._resolvers = resolvers
        self._source = source
        self._sync_registry = sync_registry
        self._session_factory = session_factory
        self._store_factory = store_factory or (
            lambda session: SQLAlchemyPaperStore(session)
        )

    async def ensure_synced(self, entry_id: str, force: bool = False) -> SyncStatus:
        """Ensure an entry has up-to-date S2 data."""
        if not await self._sync_registry.claim(entry_id):
            return SyncStatus.SYNCING

        try:
            async with self._session_factory() as session:
                store = self._store_factory(session)
                entry = await store.get_entry(entry_id)
                if not entry:
                    logger.error("Entry %s not found", entry_id)
                    return SyncStatus.FAILED

                s2_id = entry.s2_id
                if not s2_id:
                    s2_id = await self._resolve(entry)
                    if not s2_id:
                        logger.warning("Could not resolve S2 ID for '%s'", entry.title[:40])
                        return SyncStatus.NO_MATCH
                    await store.set_entry_s2_id(entry_id, s2_id)
                    await store.commit()

                if not force and not await store.is_stale(
                    s2_id,
                    settings.s2_staleness_days,
                ):
                    return SyncStatus.FRESH

                return await self._sync_paper(s2_id, store)
        finally:
            await self._sync_registry.release(entry_id)

    async def backfill(self, batch_size: int = 10) -> int:
        """Resolve and sync unresolved entries. Returns count resolved."""
        resolved = 0
        async with self._session_factory() as session:
            store = self._store_factory(session)
            entries = await store.unresolved_entries(batch_size)

            for entry in entries:
                try:
                    status = await self.ensure_synced(str(entry.id))
                    if status in (SyncStatus.SYNCED, SyncStatus.FRESH):
                        resolved += 1
                    elif status == SyncStatus.NO_MATCH:
                        logger.info("No S2 match for '%s', skipping", entry.title[:40])
                except Exception as exc:
                    logger.error("Backfill error for %s: %s", entry.id, exc)

        if resolved:
            logger.info("Backfill: resolved %d/%d entries", resolved, len(entries))
        return resolved

    async def _resolve(self, entry: Entry) -> str | None:
        """Try local corpus first for deterministic IDs, then API resolvers."""
        if self._source:
            doi = extract_identifier(entry, "doi")
            if doi:
                s2_id = await self._source.resolve_id("DOI", doi)
                if s2_id:
                    logger.info("Resolved '%s' via DuckDB DOI:%s", entry.title[:40], doi)
                    return s2_id

            arxiv_id = extract_identifier(entry, "arxiv", "eprint")
            if arxiv_id:
                s2_id = await self._source.resolve_id("ArXiv", arxiv_id)
                if s2_id:
                    logger.info(
                        "Resolved '%s' via DuckDB ArXiv:%s",
                        entry.title[:40],
                        arxiv_id,
                    )
                    return s2_id

        for resolver in self._resolvers:
            try:
                s2_id = await resolver.resolve(entry, self._transport)
                if s2_id:
                    return s2_id
            except Exception as exc:
                logger.warning(
                    "%s failed for '%s': %s",
                    resolver.__class__.__name__,
                    entry.title[:30],
                    exc,
                )
        return None

    async def _sync_paper(self, s2_id: str, store: PaperStore) -> SyncStatus:
        """Sync paper metadata and edges from corpus first, then API."""
        if self._source:
            record = await self._source.get_paper(s2_id)
            if record:
                paper_record = {
                    "s2_id": record.s2_id or s2_id,
                    "title": record.title,
                    "year": record.year,
                    "venue": record.venue,
                    "authors": record.authors,
                    "abstract": record.abstract,
                    "tldr": {"text": record.tldr} if record.tldr else None,
                    "citation_count": record.citation_count,
                    "reference_count": record.reference_count,
                    "influential_citation_count": record.influential_citation_count,
                    "is_open_access": record.is_open_access,
                }
                await store.upsert_paper(paper_record)

                citation_edges = await self._source.get_citations(s2_id) or []
                reference_edges = await self._source.get_references(s2_id) or []

                papers: list[dict] = []
                edges: list[dict] = []
                for edge in citation_edges:
                    papers.append({"s2_id": edge.citing_s2_id or "", "title": ""})
                    edges.append(
                        {
                            "source_id": edge.citing_s2_id or "",
                            "target_id": s2_id,
                            "is_influential": edge.is_influential,
                        }
                    )
                for edge in reference_edges:
                    papers.append({"s2_id": edge.cited_s2_id or "", "title": ""})
                    edges.append(
                        {
                            "source_id": s2_id,
                            "target_id": edge.cited_s2_id or "",
                            "is_influential": edge.is_influential,
                        }
                    )

                await store.upsert_papers_batch(papers)
                await store.upsert_edges(edges)
                await store.commit()

                logger.info(
                    "Synced %s from DuckDB: %d citations, %d references",
                    s2_id,
                    len(citation_edges),
                    len(reference_edges),
                )
                return SyncStatus.SYNCED

        fields = ",".join(FULL_PAPER_FIELDS)
        data = await self._transport.get(f"paper/{s2_id}", params={"fields": fields})
        if not data:
            return SyncStatus.FAILED

        try:
            paper = S2PaperSchema(**data)
        except ValidationError as exc:
            logger.error("S2 paper parse error (%s): %s", s2_id, exc)
            return SyncStatus.FAILED

        await store.upsert_paper(paper_to_record(paper))

        max_edges = settings.s2_max_edges
        citation_task = self._fetch_edges(s2_id, "citations", max_edges)
        reference_task = self._fetch_edges(s2_id, "references", max_edges)
        citation_result, reference_result = await asyncio.gather(
            citation_task,
            reference_task,
        )

        papers: list[dict] = []
        edges: list[dict] = []
        for sub_record, edge_record in citation_result:
            papers.append(sub_record)
            edges.append(edge_record)
        for sub_record, edge_record in reference_result:
            papers.append(sub_record)
            edges.append(edge_record)

        await store.upsert_papers_batch(papers)
        await store.upsert_edges(edges)
        await store.commit()

        logger.info(
            "Synced %s: %d citations, %d references",
            s2_id,
            len(citation_result),
            len(reference_result),
        )
        return SyncStatus.SYNCED

    async def _fetch_edges(
        self,
        s2_id: str,
        edge_type: str,
        max_total: int,
    ) -> list[tuple[dict, dict]]:
        """Paginate through citations or references."""
        prefix = "citingPaper" if edge_type == "citations" else "citedPaper"
        fields_list = [
            "contexts",
            "intents",
            "isInfluential",
            f"{prefix}.paperId",
            f"{prefix}.title",
            f"{prefix}.year",
            f"{prefix}.venue",
            f"{prefix}.authors",
            f"{prefix}.citationCount",
        ]
        fields = ",".join(fields_list)

        results: list[tuple[dict, dict]] = []
        offset = 0
        page_size = min(100, max_total)

        while offset < max_total:
            data = await self._transport.get(
                f"paper/{s2_id}/{edge_type}",
                params={
                    "fields": fields,
                    "limit": page_size,
                    "offset": offset,
                },
            )
            if not data:
                break

            try:
                response = S2GraphResponse(**data)
            except ValidationError as exc:
                logger.error("S2 edge parse error (%s/%s): %s", s2_id, edge_type, exc)
                break

            if not response.data:
                break

            for item in response.data:
                sub = item.citingPaper if edge_type == "citations" else item.citedPaper
                if not sub or not sub.paperId:
                    continue

                authors_data = [
                    {"authorId": author.authorId, "name": author.name}
                    for author in sub.authors
                    if author.authorId
                ]
                paper_record = {
                    "s2_id": sub.paperId,
                    "title": sub.title or "Unknown",
                    "year": sub.year,
                    "venue": sub.venue,
                    "authors": authors_data,
                    "citation_count": sub.citationCount or 0,
                    "updated_at": datetime.now(UTC),
                }
                edge_record = {
                    "source_id": sub.paperId if edge_type == "citations" else s2_id,
                    "target_id": s2_id if edge_type == "citations" else sub.paperId,
                    "contexts": item.contexts,
                    "intents": item.intents,
                    "is_influential": item.isInfluential,
                }
                results.append((paper_record, edge_record))

            offset += len(response.data)
            if len(response.data) < page_size:
                break

        return results


def create_sync_orchestrator(
    *,
    source: S2DataSource,
    sync_registry,
    transport: S2Transport | None = None,
    resolvers: list[Resolver] | None = None,
    session_factory: Callable[[], Any] = async_session,
    store_factory=None,
) -> SyncOrchestrator:
    """Create a sync orchestrator with default transport and resolver policy."""
    return SyncOrchestrator(
        transport=transport
        or S2Transport(
            api_key=settings.s2_api_key,
            rate_limit=settings.s2_rate_limit,
        ),
        resolvers=resolvers or default_resolvers(),
        source=source,
        sync_registry=sync_registry,
        session_factory=session_factory,
        store_factory=store_factory,
    )
