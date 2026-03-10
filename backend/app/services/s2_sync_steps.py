"""
Composable steps for S2 sync orchestration.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from pydantic import ValidationError

from app.schemas.s2 import S2GraphResponse
from app.schemas.s2 import S2Paper as S2PaperSchema
from app.services.s2_protocol import S2DataSource
from app.services.s2_resolvers import Resolver, extract_identifier
from app.services.s2_store import FULL_PAPER_FIELDS, PaperStore, paper_to_record
from app.services.s2_transport import S2Transport

if TYPE_CHECKING:
    from app.models import Entry
    from app.services.s2_sync import SyncStatus

logger = logging.getLogger(__name__)


class ResolutionStep:
    """Resolve a library entry to an S2 paper ID."""

    def __init__(
        self,
        *,
        source: S2DataSource,
        transport: S2Transport,
        resolvers: list[Resolver],
    ):
        self._source = source
        self._transport = transport
        self._resolvers = resolvers

    async def resolve(self, entry: "Entry") -> str | None:
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


class CorpusHydrationStep:
    """Hydrate one paper from the local corpus when available."""

    def __init__(self, *, source: S2DataSource):
        self._source = source

    async def hydrate(self, s2_id: str, store: PaperStore) -> "SyncStatus | None":
        from app.services.s2_sync import SyncStatus

        record = await self._source.get_paper(s2_id)
        if not record:
            return None

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


class EdgeFetchStep:
    """Fetch paginated edges from the live API."""

    def __init__(self, *, transport: S2Transport):
        self._transport = transport

    async def fetch(
        self,
        s2_id: str,
        edge_type: str,
        max_total: int,
    ) -> list[tuple[dict, dict]]:
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


class ApiHydrationStep:
    """Hydrate one paper from the live API."""

    def __init__(
        self,
        *,
        transport: S2Transport,
        edge_fetcher: EdgeFetchStep,
    ):
        self._transport = transport
        self._edge_fetcher = edge_fetcher

    async def hydrate(
        self,
        s2_id: str,
        store: PaperStore,
        *,
        max_edges: int,
    ) -> "SyncStatus":
        from app.services.s2_sync import SyncStatus

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

        citation_result, reference_result = await asyncio.gather(
            self._edge_fetcher.fetch(s2_id, "citations", max_edges),
            self._edge_fetcher.fetch(s2_id, "references", max_edges),
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
