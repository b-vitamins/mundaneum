"""
S2 data sources — composable, protocol-based corpus access.

Sources (chained in priority order):
  LocalCorpus  — DuckDB bulk corpus (233M papers, 5B citations)
  LiveAPI      — wraps existing S2Transport (rate-limited fallback)
  ChainedSource — tries each in order; first non-None wins

Design (Sussman):
  - Each source is independently useful.
  - The combinator composes them without any source knowing about the others.
  - Write-through: results from downstream sources are cached upstream.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from pathlib import Path
from typing import TYPE_CHECKING

from app.services.s2_protocol import EdgeRecord, PaperRecord, S2DataSource
from app.services.s2_corpus_mapping import (
    api_dict_to_paper,
    citation_edges_from_rows,
    enrich_paper_record,
    paper_record_from_row,
    reference_edges_from_rows,
)
from app.services.s2_corpus_queries import (
    abstract_row_query,
    author_rows_query,
    batch_primary_sha_query,
    citations_query,
    external_id_query,
    paper_row_query,
    primary_corpus_id_query,
    primary_sha_query,
    reference_ids_query,
    references_query,
    tldr_row_query,
)
from app.services.s2_source_registry import SourceRegistry

if TYPE_CHECKING:
    from app.services.s2_transport import S2Transport

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────
# LocalCorpus — DuckDB over S2 dataset dumps
# ──────────────────────────────────────────────────────────


class LocalCorpus:
    """S2DataSource backed by a local DuckDB database.

    The DuckDB file is read-only at query time (populated by the
    ingestion pipeline). All queries are synchronous but fast
    (sub-millisecond for indexed lookups).
    """

    def __init__(self, db_path: str | Path):
        self._db_path = Path(db_path)
        self._local = threading.local()

    def _get_conn(self):
        """Return a per-thread DuckDB connection (thread-safe).

        Each thread in the asyncio thread pool gets its own connection.
        DuckDB supports concurrent read-only connections to the same file.
        """
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

    def _sha_to_corpus_id(self, s2_id: str) -> int | None:
        """Convert a 40-char SHA paper ID to an integer corpus ID."""
        conn = self._get_conn()
        if conn is None:
            return None
        try:
            row = primary_corpus_id_query(s2_id).fetchone(conn)
            return row[0] if row else None
        except Exception:
            return None

    def _corpus_id_to_sha(self, corpus_id: int) -> str | None:
        """Convert an integer corpus ID to a 40-char SHA paper ID."""
        conn = self._get_conn()
        if conn is None:
            return None
        try:
            row = primary_sha_query(corpus_id).fetchone(conn)
            return row[0] if row else None
        except Exception:
            return None

    def _batch_corpus_id_to_sha(
        self, corpus_ids: list[int], chunk_size: int = 500
    ) -> dict[int, str]:
        """Batch convert corpus IDs to SHA paper IDs in O(1) DuckDB queries.

        Returns a dict mapping corpus_id → sha for all IDs that were found.
        Much faster than calling _corpus_id_to_sha in a loop.
        """
        if not corpus_ids:
            return {}
        conn = self._get_conn()
        if conn is None:
            return {}
        result: dict[int, str] = {}
        try:
            for i in range(0, len(corpus_ids), chunk_size):
                chunk = corpus_ids[i : i + chunk_size]
                query = batch_primary_sha_query(chunk)
                if query is None:
                    continue
                rows = query.fetchall(conn)
                for cid, sha in rows:
                    result[cid] = sha
        except Exception as e:
            logger.warning("_batch_corpus_id_to_sha: %s", e)
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
        conn = self._get_conn()
        if conn is None:
            return None
        try:
            row = paper_row_query(corpus_id).fetchone(conn)
            if not row:
                return None
            paper = paper_record_from_row(
                row,
                corpus_id=corpus_id,
                s2_id=self._corpus_id_to_sha(corpus_id),
            )
            return enrich_paper_record(
                paper,
                abstract_row=abstract_row_query(corpus_id).fetchone(conn),
                tldr_row=tldr_row_query(corpus_id).fetchone(conn),
                author_rows=author_rows_query(corpus_id).fetchall(conn),
            )
        except Exception as e:
            logger.warning("LocalCorpus.get_paper_by_corpus_id(%d): %s", corpus_id, e)
            return None

    async def get_references(
        self,
        s2_id: str,
        *,
        limit: int | None = None,
    ) -> list[EdgeRecord] | None:
        return await asyncio.to_thread(self._sync_get_references, s2_id, limit)

    def _sync_get_references(
        self, s2_id: str, limit: int | None = None
    ) -> list[EdgeRecord] | None:
        corpus_id = self._sha_to_corpus_id(s2_id)
        if corpus_id is None:
            return None
        conn = self._get_conn()
        if conn is None:
            return None
        try:
            rows = references_query(corpus_id, limit=limit).fetchall(conn)

            # Batch reverse-lookup: corpus_id → sha
            cited_ids = [r[0] for r in rows if r[0] is not None]
            sha_map = self._batch_corpus_id_to_sha(cited_ids)
            return reference_edges_from_rows(
                rows,
                citing_corpus_id=corpus_id,
                citing_s2_id=s2_id,
                sha_map=sha_map,
            )
        except Exception as e:
            logger.warning("LocalCorpus.get_references(%s): %s", s2_id, e)
            return None

    async def get_citations(
        self,
        s2_id: str,
        *,
        limit: int | None = None,
    ) -> list[EdgeRecord] | None:
        return await asyncio.to_thread(self._sync_get_citations, s2_id, limit)

    def _sync_get_citations(
        self, s2_id: str, limit: int | None = None
    ) -> list[EdgeRecord] | None:
        corpus_id = self._sha_to_corpus_id(s2_id)
        if corpus_id is None:
            return None
        conn = self._get_conn()
        if conn is None:
            return None
        try:
            rows = citations_query(corpus_id, limit=limit).fetchall(conn)

            # Batch reverse-lookup: corpus_id → sha
            citing_ids = [r[0] for r in rows if r[0] is not None]
            sha_map = self._batch_corpus_id_to_sha(citing_ids)
            return citation_edges_from_rows(
                rows,
                cited_corpus_id=corpus_id,
                cited_s2_id=s2_id,
                sha_map=sha_map,
            )
        except Exception as e:
            logger.warning("LocalCorpus.get_citations(%s): %s", s2_id, e)
            return None

    async def resolve_id(self, id_type: str, identifier: str) -> str | None:
        return await asyncio.to_thread(self._sync_resolve_id, id_type, identifier)

    def _sync_resolve_id(self, id_type: str, identifier: str) -> str | None:
        conn = self._get_conn()
        if conn is None:
            return None
        try:
            row = external_id_query(id_type, identifier).fetchone(conn)
            return row[0] if row else None
        except Exception as e:
            logger.warning("LocalCorpus.resolve_id(%s, %s): %s", id_type, identifier, e)
            return None

    async def search(self, query: str, limit: int = 10) -> list[PaperRecord] | None:
        # DuckDB doesn't have full-text search; return None to fall through
        return None

    async def get_reference_ids(self, s2_id: str) -> set[str] | None:
        return await asyncio.to_thread(self._sync_get_reference_ids, s2_id)

    def _sync_get_reference_ids(self, s2_id: str) -> set[str] | None:
        """Optimized: return just cited SHA IDs without full EdgeRecord overhead."""
        corpus_id = self._sha_to_corpus_id(s2_id)
        if corpus_id is None:
            return None
        conn = self._get_conn()
        if conn is None:
            return None
        try:
            rows = reference_ids_query(corpus_id).fetchall(conn)
            return {r[0] for r in rows}
        except Exception as e:
            logger.warning("LocalCorpus.get_reference_ids(%s): %s", s2_id, e)
            return None


# ──────────────────────────────────────────────────────────
# LiveAPI — wraps existing S2Transport
# ──────────────────────────────────────────────────────────

# Fields to request from the S2 API
_LIVE_PAPER_FIELDS = (
    "paperId,title,year,venue,authors,abstract,tldr,citationCount,"
    "referenceCount,influentialCitationCount,isOpenAccess,openAccessPdf,"
    "fieldsOfStudy,publicationTypes,externalIds"
)


class LiveAPI:
    """S2DataSource backed by the live S2 REST API.

    This is the fallback source — always has data (if the paper exists),
    but is rate-limited and slow.
    """

    def __init__(self, transport: S2Transport):
        self._transport = transport

    async def get_paper(self, s2_id: str) -> PaperRecord | None:
        data = await self._transport.get(
            f"paper/{s2_id}", params={"fields": _LIVE_PAPER_FIELDS}
        )
        if not data:
            return None
        return api_dict_to_paper(data)

    async def get_paper_by_corpus_id(self, corpus_id: int) -> PaperRecord | None:
        data = await self._transport.get(
            f"paper/CorpusId:{corpus_id}", params={"fields": _LIVE_PAPER_FIELDS}
        )
        if not data:
            return None
        return api_dict_to_paper(data)

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
        edges = []
        for item in data["data"]:
            cited = item.get("citedPaper") or {}
            cited_id = cited.get("paperId")
            if cited_id:
                edges.append(
                    EdgeRecord(
                        citing_s2_id=s2_id,
                        cited_s2_id=cited_id,
                        is_influential=item.get("isInfluential", False),
                    )
                )
        return edges

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
        edges = []
        for item in data["data"]:
            citing = item.get("citingPaper") or {}
            citing_id = citing.get("paperId")
            if citing_id:
                edges.append(
                    EdgeRecord(
                        citing_s2_id=citing_id,
                        cited_s2_id=s2_id,
                        is_influential=item.get("isInfluential", False),
                    )
                )
        return edges

    async def resolve_id(self, id_type: str, identifier: str) -> str | None:
        if id_type == "DOI":
            data = await self._transport.get(f"paper/DOI:{identifier}")
        elif id_type == "ArXiv":
            data = await self._transport.get(f"paper/ARXIV:{identifier}")
        elif id_type == "title":
            results = await self._transport.search(identifier, limit=1)
            if results:
                data = results[0] if isinstance(results, list) else results
            else:
                data = None
        else:
            data = await self._transport.get(f"paper/{id_type}:{identifier}")

        if data and isinstance(data, dict):
            return data.get("paperId")
        return None

    async def search(self, query: str, limit: int = 10) -> list[PaperRecord] | None:
        data = await self._transport.search(query, limit=limit)
        if not data:
            return None
        if isinstance(data, list):
            return [api_dict_to_paper(d) for d in data]
        return None

    async def get_reference_ids(self, s2_id: str) -> set[str] | None:
        refs = await self.get_references(s2_id)
        if refs is None:
            return None
        return {e.cited_s2_id for e in refs if e.cited_s2_id}

# ──────────────────────────────────────────────────────────
# ChainedSource — the combinator
# ──────────────────────────────────────────────────────────


class ChainedSource:
    """Try each source in order. First non-None result wins.

    Optionally caches results from downstream sources into a
    designated cache (write-through), so the next query takes
    the fast path.
    """

    def __init__(
        self,
        sources: list[S2DataSource],
    ):
        self._registry = SourceRegistry(sources)

    async def _resolve(self, operation):
        return await self._registry.first_result(operation)

    async def get_paper(self, s2_id: str) -> PaperRecord | None:
        return await self._resolve(lambda source: source.get_paper(s2_id))

    async def get_paper_by_corpus_id(self, corpus_id: int) -> PaperRecord | None:
        return await self._resolve(
            lambda source: source.get_paper_by_corpus_id(corpus_id)
        )

    async def get_references(
        self,
        s2_id: str,
        *,
        limit: int | None = None,
    ) -> list[EdgeRecord] | None:
        return await self._resolve(
            lambda source: source.get_references(s2_id, limit=limit)
        )

    async def get_citations(
        self,
        s2_id: str,
        *,
        limit: int | None = None,
    ) -> list[EdgeRecord] | None:
        return await self._resolve(
            lambda source: source.get_citations(s2_id, limit=limit)
        )

    async def resolve_id(self, id_type: str, identifier: str) -> str | None:
        return await self._resolve(
            lambda source: source.resolve_id(id_type, identifier)
        )

    async def search(self, query: str, limit: int = 10) -> list[PaperRecord] | None:
        return await self._resolve(lambda source: source.search(query, limit=limit))

    async def get_reference_ids(self, s2_id: str) -> set[str] | None:
        return await self._resolve(lambda source: source.get_reference_ids(s2_id))


def get_local_source() -> LocalCorpus | None:
    """Return the runtime-owned LocalCorpus instance.

    Used by graph construction where we want instant results from DuckDB
    without ever blocking on LiveAPI calls.
    """
    from app.services.s2_runtime import get_s2_runtime

    return get_s2_runtime().local_source


def get_data_source() -> ChainedSource:
    """Return the runtime-owned chained data source.

    Chain: LocalCorpus (DuckDB, instant) → LiveAPI (S2 Transport, fallback).
    """
    from app.services.s2_runtime import get_s2_runtime

    return get_s2_runtime().data_source
