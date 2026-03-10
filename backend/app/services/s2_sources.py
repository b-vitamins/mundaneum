"""
Concrete Semantic Scholar source implementations.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from pathlib import Path
from typing import TYPE_CHECKING

from app.services.s2_corpus_mappers import CorpusRowMapper
from app.services.s2_corpus_queries import (
    ABSTRACT_BY_CORPUS_ID_QUERY,
    AUTHORS_BY_CORPUS_ID_QUERY,
    BATCH_CORPUS_ID_TO_SHA_QUERY,
    CITATIONS_BY_CITED_QUERY,
    CORPUS_ID_TO_SHA_QUERY,
    PAPER_BY_CORPUS_ID_QUERY,
    REFERENCE_IDS_QUERY,
    REFERENCES_BY_CITING_QUERY,
    RESOLVE_EXTERNAL_ID_QUERY,
    SHA_TO_CORPUS_ID_QUERY,
    TLDR_BY_CORPUS_ID_QUERY,
    DuckDBQuerySpec,
)
from app.services.s2_protocol import EdgeRecord, PaperRecord

if TYPE_CHECKING:
    from app.services.s2_transport import S2Transport

logger = logging.getLogger(__name__)

_LIVE_PAPER_FIELDS = (
    "paperId,title,year,venue,authors,abstract,tldr,citationCount,"
    "referenceCount,influentialCitationCount,isOpenAccess,openAccessPdf,"
    "fieldsOfStudy,publicationTypes,externalIds"
)


class LocalCorpus:
    """S2DataSource backed by a local DuckDB database."""

    def __init__(self, db_path: str | Path):
        self._db_path = Path(db_path)
        self._local = threading.local()

    def _get_conn(self):
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            return conn
        if not self._db_path.exists():
            logger.info("LocalCorpus: DuckDB not found at %s", self._db_path)
            return None

        import duckdb

        conn = duckdb.connect(str(self._db_path), read_only=True)
        self._local.conn = conn
        logger.info(
            "LocalCorpus: connected to %s (thread %s)",
            self._db_path,
            threading.current_thread().name,
        )
        return conn

    def _fetchone(
        self,
        query: DuckDBQuerySpec,
        params: list[object],
        *,
        limit: int | None = None,
    ):
        conn = self._get_conn()
        if conn is None:
            return None
        try:
            statement = query.render(value_count=len(params), limit=limit)
            return conn.execute(statement, query.bind(params, limit=limit)).fetchone()
        except Exception:
            if query.fallback_sql is None:
                raise
            statement = query.render(
                use_fallback=True,
                value_count=len(params),
                limit=limit,
            )
            return conn.execute(statement, query.bind(params, limit=limit)).fetchone()

    def _fetchall(
        self,
        query: DuckDBQuerySpec,
        params: list[object],
        *,
        limit: int | None = None,
    ):
        conn = self._get_conn()
        if conn is None:
            return []
        try:
            statement = query.render(value_count=len(params), limit=limit)
            return conn.execute(statement, query.bind(params, limit=limit)).fetchall()
        except Exception:
            if query.fallback_sql is None:
                raise
            statement = query.render(
                use_fallback=True,
                value_count=len(params),
                limit=limit,
            )
            return conn.execute(statement, query.bind(params, limit=limit)).fetchall()

    def _sha_to_corpus_id(self, s2_id: str) -> int | None:
        row = self._fetchone(SHA_TO_CORPUS_ID_QUERY, [s2_id])
        return row[0] if row else None

    def _corpus_id_to_sha(self, corpus_id: int) -> str | None:
        row = self._fetchone(CORPUS_ID_TO_SHA_QUERY, [corpus_id])
        return row[0] if row else None

    def _batch_corpus_id_to_sha(self, corpus_ids: list[int], chunk_size: int = 500) -> dict[int, str]:
        if not corpus_ids:
            return {}

        result: dict[int, str] = {}
        try:
            for index in range(0, len(corpus_ids), chunk_size):
                chunk = corpus_ids[index : index + chunk_size]
                rows = self._fetchall(BATCH_CORPUS_ID_TO_SHA_QUERY, chunk)
                for corpus_id, sha in rows:
                    result[corpus_id] = sha
        except Exception as exc:
            logger.warning("_batch_corpus_id_to_sha: %s", exc)
        return result

    async def get_paper(self, s2_id: str) -> PaperRecord | None:
        return await asyncio.to_thread(self._sync_get_paper, s2_id)

    def _sync_get_paper(self, s2_id: str) -> PaperRecord | None:
        corpus_id = self._sha_to_corpus_id(s2_id)
        if corpus_id is None:
            return None
        return self._sync_get_paper_by_corpus_id(corpus_id)

    async def get_paper_by_corpus_id(self, corpus_id: int) -> PaperRecord | None:
        return await asyncio.to_thread(self._sync_get_paper_by_corpus_id, corpus_id)

    def _sync_get_paper_by_corpus_id(self, corpus_id: int) -> PaperRecord | None:
        try:
            row = self._fetchone(PAPER_BY_CORPUS_ID_QUERY, [corpus_id])
            if row is None:
                return None

            paper = CorpusRowMapper.paper_from_row(
                row,
                corpus_id=corpus_id,
                s2_id=self._corpus_id_to_sha(corpus_id),
            )
            abstract_row = self._fetchone(ABSTRACT_BY_CORPUS_ID_QUERY, [corpus_id])
            tldr_row = self._fetchone(TLDR_BY_CORPUS_ID_QUERY, [corpus_id])
            author_rows = self._fetchall(AUTHORS_BY_CORPUS_ID_QUERY, [corpus_id])
            return CorpusRowMapper.enrich_paper(
                paper,
                abstract_row=abstract_row,
                tldr_row=tldr_row,
                author_rows=author_rows,
            )
        except Exception as exc:
            logger.warning("LocalCorpus.get_paper_by_corpus_id(%d): %s", corpus_id, exc)
            return None

    async def get_references(
        self,
        s2_id: str,
        *,
        limit: int | None = None,
    ) -> list[EdgeRecord] | None:
        return await asyncio.to_thread(self._sync_get_references, s2_id, limit)

    def _sync_get_references(
        self,
        s2_id: str,
        limit: int | None = None,
    ) -> list[EdgeRecord] | None:
        corpus_id = self._sha_to_corpus_id(s2_id)
        if corpus_id is None:
            return None
        try:
            rows = self._fetchall(REFERENCES_BY_CITING_QUERY, [corpus_id], limit=limit)
            cited_ids = [row[0] for row in rows if row[0] is not None]
            sha_map = self._batch_corpus_id_to_sha(cited_ids)
            return CorpusRowMapper.reference_edges(
                rows,
                citing_corpus_id=corpus_id,
                citing_s2_id=s2_id,
                sha_map=sha_map,
            )
        except Exception as exc:
            logger.warning("LocalCorpus.get_references(%s): %s", s2_id, exc)
            return None

    async def get_citations(
        self,
        s2_id: str,
        *,
        limit: int | None = None,
    ) -> list[EdgeRecord] | None:
        return await asyncio.to_thread(self._sync_get_citations, s2_id, limit)

    def _sync_get_citations(
        self,
        s2_id: str,
        limit: int | None = None,
    ) -> list[EdgeRecord] | None:
        corpus_id = self._sha_to_corpus_id(s2_id)
        if corpus_id is None:
            return None
        try:
            rows = self._fetchall(CITATIONS_BY_CITED_QUERY, [corpus_id], limit=limit)
            citing_ids = [row[0] for row in rows if row[0] is not None]
            sha_map = self._batch_corpus_id_to_sha(citing_ids)
            return CorpusRowMapper.citation_edges(
                rows,
                cited_corpus_id=corpus_id,
                cited_s2_id=s2_id,
                sha_map=sha_map,
            )
        except Exception as exc:
            logger.warning("LocalCorpus.get_citations(%s): %s", s2_id, exc)
            return None

    async def resolve_id(self, id_type: str, identifier: str) -> str | None:
        return await asyncio.to_thread(self._sync_resolve_id, id_type, identifier)

    def _sync_resolve_id(self, id_type: str, identifier: str) -> str | None:
        try:
            row = self._fetchone(RESOLVE_EXTERNAL_ID_QUERY, [id_type, identifier])
            return row[0] if row else None
        except Exception as exc:
            logger.warning("LocalCorpus.resolve_id(%s, %s): %s", id_type, identifier, exc)
            return None

    async def search(self, query: str, limit: int = 10) -> list[PaperRecord] | None:
        return None

    async def get_reference_ids(self, s2_id: str) -> set[str] | None:
        return await asyncio.to_thread(self._sync_get_reference_ids, s2_id)

    def _sync_get_reference_ids(self, s2_id: str) -> set[str] | None:
        corpus_id = self._sha_to_corpus_id(s2_id)
        if corpus_id is None:
            return None
        try:
            rows = self._fetchall(REFERENCE_IDS_QUERY, [corpus_id])
            return {row[0] for row in rows}
        except Exception as exc:
            logger.warning("LocalCorpus.get_reference_ids(%s): %s", s2_id, exc)
            return None


class LiveAPI:
    """S2DataSource backed by the live S2 REST API."""

    def __init__(self, transport: S2Transport):
        self._transport = transport

    async def get_paper(self, s2_id: str) -> PaperRecord | None:
        data = await self._transport.get(
            f"paper/{s2_id}",
            params={"fields": _LIVE_PAPER_FIELDS},
        )
        if not data:
            return None
        return CorpusRowMapper.api_paper(data)

    async def get_paper_by_corpus_id(self, corpus_id: int) -> PaperRecord | None:
        data = await self._transport.get(
            f"paper/CorpusId:{corpus_id}",
            params={"fields": _LIVE_PAPER_FIELDS},
        )
        if not data:
            return None
        return CorpusRowMapper.api_paper(data)

    async def get_references(
        self,
        s2_id: str,
        *,
        limit: int | None = None,
    ) -> list[EdgeRecord] | None:
        data = await self._transport.get(
            f"paper/{s2_id}/references",
            params={"fields": "citedPaper.paperId,isInfluential", "limit": "500"},
        )
        if not data or not data.get("data"):
            return None

        edges = [
            EdgeRecord(
                citing_s2_id=s2_id,
                cited_s2_id=(item.get("citedPaper") or {}).get("paperId"),
                is_influential=item.get("isInfluential", False),
            )
            for item in data["data"]
            if (item.get("citedPaper") or {}).get("paperId")
        ]
        return edges[:limit] if limit is not None else edges

    async def get_citations(
        self,
        s2_id: str,
        *,
        limit: int | None = None,
    ) -> list[EdgeRecord] | None:
        data = await self._transport.get(
            f"paper/{s2_id}/citations",
            params={"fields": "citingPaper.paperId,isInfluential", "limit": "500"},
        )
        if not data or not data.get("data"):
            return None

        edges = [
            EdgeRecord(
                citing_s2_id=(item.get("citingPaper") or {}).get("paperId"),
                cited_s2_id=s2_id,
                is_influential=item.get("isInfluential", False),
            )
            for item in data["data"]
            if (item.get("citingPaper") or {}).get("paperId")
        ]
        return edges[:limit] if limit is not None else edges

    async def resolve_id(self, id_type: str, identifier: str) -> str | None:
        if id_type == "DOI":
            data = await self._transport.get(f"paper/DOI:{identifier}")
        elif id_type == "ArXiv":
            data = await self._transport.get(f"paper/ARXIV:{identifier}")
        elif id_type == "title":
            results = await self._transport.search(identifier, limit=1)
            data = results[0] if results else None
        else:
            data = await self._transport.get(f"paper/{id_type}:{identifier}")

        if data and isinstance(data, dict):
            return data.get("paperId")
        return None

    async def search(self, query: str, limit: int = 10) -> list[PaperRecord] | None:
        data = await self._transport.search(query, limit=limit)
        if not data or not isinstance(data, list):
            return None
        return [CorpusRowMapper.api_paper(item) for item in data]

    async def get_reference_ids(self, s2_id: str) -> set[str] | None:
        refs = await self.get_references(s2_id)
        if refs is None:
            return None
        return {edge.cited_s2_id for edge in refs if edge.cited_s2_id}
