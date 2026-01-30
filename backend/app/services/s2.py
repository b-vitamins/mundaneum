import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from pydantic import ValidationError
from semanticscholar import SemanticScholar
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.models import Entry, S2Citation, S2Paper
from app.schemas.s2 import S2GraphResponse
from app.schemas.s2 import S2Paper as S2PaperSchema

logger = logging.getLogger(__name__)


class S2Service:
    """
    Service for interacting with Semantic Scholar API and syncing data.
    """

    def __init__(self):
        # Initialize client with a timeout (default is usually 10s)
        self.sch = SemanticScholar(timeout=30)
        # Fields to fetch for the main paper
        self.paper_fields = [
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
        # Fields to fetch for related papers (citations/references)
        # We need contexts and intents for the edges
        self.related_fields = [
            "paperId",
            "title",
            "year",
            "venue",
            "authors",
            "contexts",
            "intents",
            "isInfluential",
        ]

    async def _fetch_paper_sync(self, s2_id: str) -> S2PaperSchema | None:
        """Fetch main paper using raw API to allow uniform backoff handling."""
        fields = ",".join(self.paper_fields)
        url = f"https://api.semanticscholar.org/graph/v1/paper/{s2_id}"
        params = {"fields": fields}
        data = await self._fetch_with_backoff(url, params)
        if data:
            try:
                return S2PaperSchema(**data)
            except ValidationError as e:
                logger.error(f"Failed to parse S2 paper {s2_id}: {e}")
        return None

    async def _search_paper_sync(self, query: str) -> dict[str, Any] | None:
        """Search for a paper by title."""
        loop = asyncio.get_running_loop()
        try:
            results = await loop.run_in_executor(
                None, lambda: self.sch.search_paper(query, limit=1)
            )
            if results and len(results) > 0:
                return results[0]
            return None
        except Exception as e:
            logger.error(f"Failed to search paper {query}: {e}")
            return None

    async def resolve_s2_id(self, entry: Entry, session: AsyncSession) -> str | None:
        """Try to find S2 ID for an entry if missing."""
        if entry.s2_id:
            return entry.s2_id

        logger.info(f"Resolving S2 ID for '{entry.title}'")
        paper = await self._search_paper_sync(entry.title)

        if paper and paper.paperId:
            entry.s2_id = paper.paperId
            session.add(entry)
            await session.commit()
            return paper.paperId

        return None

    async def _fetch_with_backoff(self, url: str, params: dict = None) -> dict | None:
        """Fetch URL with exponential backoff for 429s."""
        retries = 0
        max_retries = 5
        base_delay = 2.0  # Start with 2 seconds (1 RPS safe)

        async with httpx.AsyncClient(timeout=30.0) as client:
            while retries < max_retries:
                try:
                    resp = await client.get(url, params=params)
                    if resp.status_code == 200:
                        return resp.json()
                    elif resp.status_code == 429:
                        wait = base_delay * (2**retries)
                        logger.warning(f"S2 Rate limit (429). Retrying in {wait}s...")
                        await asyncio.sleep(wait)
                        retries += 1
                        continue
                    elif resp.status_code == 404:
                        logger.warning(f"S2 Resource not found: {url}")
                        return None
                    else:
                        logger.error(f"S2 API Error {resp.status_code}: {resp.text}")
                        return None
                except Exception as e:
                    logger.error(f"Request failed: {e}")
                    return None
        return None

    async def sync_paper(self, entry_id: str, force: bool = False):
        """
        Main sync task.
        1. Resolve S2 ID.
        2. Check staleness.
        3. Fetch main paper metadata (lightweight).
        4. Fetch Citations (capped).
        5. Fetch References (capped).
        """
        async with async_session() as session:
            stmt = select(Entry).where(Entry.id == entry_id)
            result = await session.execute(stmt)
            entry = result.scalar_one_or_none()

            if not entry:
                logger.error(f"Entry {entry_id} not found")
                return

            s2_id = await self.resolve_s2_id(entry, session)
            if not s2_id:
                logger.warning(f"Could not resolve S2 ID for entry {entry_id}")
                return

            # Check staleness
            stmt = select(S2Paper).where(S2Paper.s2_id == s2_id)
            result = await session.execute(stmt)
            existing_paper = result.scalar_one_or_none()

            if existing_paper:
                # If updated within last 7 days, skip
                if (
                    not force
                    and existing_paper.updated_at
                    and existing_paper.updated_at
                    > datetime.now(UTC) - timedelta(days=7)
                ):
                    logger.info(f"S2 data for {s2_id} is fresh. Skipping sync.")
                    return
            else:
                logger.info(f"No existing S2 paper found for {s2_id}")

            # 1. Fetch Main Paper (LIMITED fields)
            paper_data = await self._fetch_paper_sync(s2_id)
            if not paper_data:
                return

            await self._upsert_s2_paper(session, paper_data)
            await session.commit()  # Commit main paper first

            # 2. Sync Citations and References in Parallel
            logger.info(f"Syncing edges for {s2_id}...")
            await asyncio.gather(
                self._sync_edges_raw(session, s2_id, "citations", limit=50),
                self._sync_edges_raw(session, s2_id, "references", limit=50),
            )

            logger.info(f"Synced S2 data for {s2_id}")

    async def _upsert_s2_paper(self, session: AsyncSession, paper: S2PaperSchema):
        """Upsert S2Paper record from Pydantic model."""

        # Prepare authors list of dicts
        authors_data = [
            {"authorId": a.authorId, "name": a.name}
            for a in paper.authors
            if a.authorId
        ]

        # Handle TLDR and Embedding
        tldr_data = paper.tldr.model_dump() if paper.tldr else None
        embedding_data = paper.embedding.model_dump() if paper.embedding else None

        record = {
            "s2_id": paper.paperId,
            "title": paper.title or "",
            "year": paper.year,
            "venue": paper.venue,
            "authors": authors_data,
            "abstract": paper.abstract,
            "tldr": tldr_data,
            "citation_count": paper.citationCount,
            "reference_count": paper.referenceCount,
            "influential_citation_count": paper.influentialCitationCount,
            "is_open_access": paper.isOpenAccess,
            "open_access_pdf": paper.openAccessPdf,
            "fields_of_study": paper.fieldsOfStudy,
            "publication_types": paper.publicationTypes,
            "external_ids": paper.externalIds,
            "embedding": embedding_data,
            "updated_at": datetime.now(UTC),
        }

        stmt = insert(S2Paper).values(record)
        stmt = stmt.on_conflict_do_update(
            index_elements=[S2Paper.s2_id],
            set_={k: v for k, v in record.items() if k != "s2_id"},
        )
        await session.execute(stmt)

    async def _sync_edges_raw(
        self, session: AsyncSession, s2_id: str, edge_type: str, limit: int = 50
    ):
        """
        Fetch edges using raw API with limits.
        edge_type: 'citations' or 'references'
        """
        prefix = "citingPaper" if edge_type == "citations" else "citedPaper"

        # correct fields for raw API endpoint
        fields_list = [
            "contexts",
            "intents",
            "isInfluential",
            f"{prefix}.paperId",
            f"{prefix}.title",
            f"{prefix}.year",
            f"{prefix}.venue",
            f"{prefix}.authors",
        ]
        fields_str = ",".join(fields_list)

        url = f"https://api.semanticscholar.org/graph/v1/paper/{s2_id}/{edge_type}"
        params = {"fields": fields_str, "limit": limit}

        data = await self._fetch_with_backoff(url, params)
        if not data:
            return

        try:
            # We map the raw response to our schema manually or via Pydantic
            # The structure is { data: [ { contexts: [], citingPaper: {} } ] }
            response_schema = S2GraphResponse(**data)
        except ValidationError as e:
            logger.error(f"Failed to parse {edge_type} for {s2_id}: {e}")
            return

        papers_to_upsert = []
        citations_to_upsert = []

        for item in response_schema.data:
            # item is S2GraphEdge
            sub = item.citingPaper if edge_type == "citations" else item.citedPaper

            if not sub or not sub.paperId:
                continue

            # Store node data (minimal)
            # Use model_dump to get dict, but we want flat structure for DB
            authors_data = [
                {"authorId": a.authorId, "name": a.name}
                for a in sub.authors
                if a.authorId
            ]

            p_rec = {
                "s2_id": sub.paperId,
                "title": sub.title or "Unknown",
                "year": sub.year,
                "venue": sub.venue,
                "authors": authors_data,
                "updated_at": datetime.now(UTC),
            }
            papers_to_upsert.append(p_rec)

            # Store edge data
            c_rec = {
                "source_id": sub.paperId if edge_type == "citations" else s2_id,
                "target_id": s2_id if edge_type == "citations" else sub.paperId,
                "contexts": item.contexts,
                "intents": item.intents,
                "is_influential": item.isInfluential,
            }
            citations_to_upsert.append(c_rec)

        if papers_to_upsert:
            stmt = insert(S2Paper).values(papers_to_upsert)
            # Shallow update: ONLY update updated_at if exists
            # We do NOT want to overwrite a full record with a partial one
            # actually, DO NOTHING is better if we want to preserve old data
            # But let's just touch updated_at to show we saw it?
            # No, if we have a full record, we want to keep it.
            # If we have a partial record, this is another partial record.
            stmt = stmt.on_conflict_do_nothing(index_elements=[S2Paper.s2_id])
            await session.execute(stmt)

        if citations_to_upsert:
            stmt_c = insert(S2Citation).values(citations_to_upsert)
            stmt_c = stmt_c.on_conflict_do_update(
                index_elements=[S2Citation.source_id, S2Citation.target_id],
                set_={
                    "contexts": stmt_c.excluded.contexts,
                    "intents": stmt_c.excluded.intents,
                    "is_influential": stmt_c.excluded.is_influential,
                },
            )
            await session.execute(stmt_c)

        await session.commit()
