"""
S2 corpus module — three S2DataSource implementations + ChainedSource combinator.

LocalCorpus   — DuckDB over the full S2 Academic Graph dump (~63 GB)
PostgresCache — wraps existing SQLAlchemy paper store (hot data)
LiveAPI       — wraps existing S2Transport (rate-limited fallback)
ChainedSource — tries each in order; first non-None wins

Design (Sussman):
  - Each source is independently useful.
  - The combinator composes them without any source knowing about the others.
  - Write-through: results from downstream sources are cached upstream.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from app.services.s2_protocol import EdgeRecord, PaperRecord, S2DataSource

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.services.s2 import S2Transport

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
        self._conn = None

    def _get_conn(self):
        """Lazy connection — only import duckdb when actually needed."""
        if self._conn is None:
            if not self._db_path.exists():
                logger.info("LocalCorpus: DuckDB not found at %s", self._db_path)
                return None
            import duckdb

            self._conn = duckdb.connect(str(self._db_path), read_only=True)
            logger.info("LocalCorpus: connected to %s", self._db_path)
        return self._conn

    def _sha_to_corpus_id(self, s2_id: str) -> int | None:
        """Convert a 40-char SHA paper ID to an integer corpus ID."""
        conn = self._get_conn()
        if conn is None:
            return None
        try:
            row = conn.execute(
                "SELECT corpusid FROM paper_ids WHERE sha = ? AND is_primary = true LIMIT 1",
                [s2_id],
            ).fetchone()
            return row[0] if row else None
        except Exception:
            return None

    def _corpus_id_to_sha(self, corpus_id: int) -> str | None:
        """Convert an integer corpus ID to a 40-char SHA paper ID."""
        conn = self._get_conn()
        if conn is None:
            return None
        try:
            row = conn.execute(
                "SELECT sha FROM paper_ids WHERE corpusid = ? AND is_primary = true LIMIT 1",
                [corpus_id],
            ).fetchone()
            return row[0] if row else None
        except Exception:
            return None

    def _row_to_paper(self, row: tuple, corpus_id: int) -> PaperRecord:
        """Convert a DuckDB row to PaperRecord."""
        # row: (title, year, venue, citationcount, referencecount,
        #        influentialcitationcount, isopenaccess, publicationdate)
        s2_id = self._corpus_id_to_sha(corpus_id)
        return PaperRecord(
            corpus_id=corpus_id,
            s2_id=s2_id,
            title=row[0] or "",
            year=row[1],
            venue=row[2],
            citation_count=row[3] or 0,
            reference_count=row[4] or 0,
            influential_citation_count=row[5] or 0,
            is_open_access=bool(row[6]),
        )

    async def get_paper(self, s2_id: str) -> PaperRecord | None:
        corpus_id = self._sha_to_corpus_id(s2_id)
        if corpus_id is None:
            return None
        return await self.get_paper_by_corpus_id(corpus_id)

    async def get_paper_by_corpus_id(self, corpus_id: int) -> PaperRecord | None:
        conn = self._get_conn()
        if conn is None:
            return None
        try:
            row = conn.execute(
                """SELECT title, year, venue, citationcount, referencecount,
                          influentialcitationcount, isopenaccess, publicationdate
                   FROM papers WHERE corpusid = ?""",
                [corpus_id],
            ).fetchone()
            if not row:
                return None
            paper = self._row_to_paper(row, corpus_id)

            # Enrich with abstract and TLDR if available
            abstract_row = conn.execute(
                "SELECT abstract FROM abstracts WHERE corpusid = ?", [corpus_id]
            ).fetchone()
            tldr_row = conn.execute(
                "SELECT text FROM tldrs WHERE corpusid = ?", [corpus_id]
            ).fetchone()

            # Enrich with authors
            author_rows = conn.execute(
                "SELECT authorid, name FROM paper_authors WHERE corpusid = ? ORDER BY position",
                [corpus_id],
            ).fetchall()

            # Build enriched record (frozen dataclass — create new one)
            return PaperRecord(
                corpus_id=paper.corpus_id,
                s2_id=paper.s2_id,
                title=paper.title,
                year=paper.year,
                venue=paper.venue,
                authors=[{"authorId": r[0], "name": r[1]} for r in author_rows],
                abstract=abstract_row[0] if abstract_row else None,
                tldr=tldr_row[0] if tldr_row else None,
                citation_count=paper.citation_count,
                reference_count=paper.reference_count,
                influential_citation_count=paper.influential_citation_count,
                is_open_access=paper.is_open_access,
            )
        except Exception as e:
            logger.warning("LocalCorpus.get_paper_by_corpus_id(%d): %s", corpus_id, e)
            return None

    async def get_references(self, s2_id: str) -> list[EdgeRecord] | None:
        corpus_id = self._sha_to_corpus_id(s2_id)
        if corpus_id is None:
            return None
        conn = self._get_conn()
        if conn is None:
            return None
        try:
            rows = conn.execute(
                """SELECT citedcorpusid, isinfluential
                   FROM citations WHERE citingcorpusid = ?""",
                [corpus_id],
            ).fetchall()
            return [
                EdgeRecord(
                    citing_corpus_id=corpus_id,
                    cited_corpus_id=r[0],
                    citing_s2_id=s2_id,
                    cited_s2_id=self._corpus_id_to_sha(r[0]),
                    is_influential=bool(r[1]),
                )
                for r in rows
            ]
        except Exception as e:
            logger.warning("LocalCorpus.get_references(%s): %s", s2_id, e)
            return None

    async def get_citations(self, s2_id: str) -> list[EdgeRecord] | None:
        corpus_id = self._sha_to_corpus_id(s2_id)
        if corpus_id is None:
            return None
        conn = self._get_conn()
        if conn is None:
            return None
        try:
            rows = conn.execute(
                """SELECT citingcorpusid, isinfluential
                   FROM citations WHERE citedcorpusid = ?""",
                [corpus_id],
            ).fetchall()
            return [
                EdgeRecord(
                    citing_corpus_id=r[0],
                    cited_corpus_id=corpus_id,
                    citing_s2_id=self._corpus_id_to_sha(r[0]),
                    cited_s2_id=s2_id,
                    is_influential=bool(r[1]),
                )
                for r in rows
            ]
        except Exception as e:
            logger.warning("LocalCorpus.get_citations(%s): %s", s2_id, e)
            return None

    async def resolve_id(self, id_type: str, identifier: str) -> str | None:
        conn = self._get_conn()
        if conn is None:
            return None
        try:
            row = conn.execute(
                """SELECT pi.sha FROM paper_external_ids ei
                   JOIN paper_ids pi ON ei.corpusid = pi.corpusid AND pi.is_primary = true
                   WHERE ei.source = ? AND ei.id = ? LIMIT 1""",
                [id_type, identifier],
            ).fetchone()
            return row[0] if row else None
        except Exception as e:
            logger.warning("LocalCorpus.resolve_id(%s, %s): %s", id_type, identifier, e)
            return None

    async def search(self, query: str, limit: int = 10) -> list[PaperRecord] | None:
        # DuckDB doesn't have full-text search; return None to fall through
        return None

    async def get_reference_ids(self, s2_id: str) -> set[str] | None:
        """Optimized: return just cited SHA IDs without full EdgeRecord overhead."""
        corpus_id = self._sha_to_corpus_id(s2_id)
        if corpus_id is None:
            return None
        conn = self._get_conn()
        if conn is None:
            return None
        try:
            rows = conn.execute(
                """SELECT pi.sha
                   FROM citations c
                   JOIN paper_ids pi ON c.citedcorpusid = pi.corpusid AND pi.is_primary = true
                   WHERE c.citingcorpusid = ?""",
                [corpus_id],
            ).fetchall()
            return {r[0] for r in rows}
        except Exception as e:
            logger.warning("LocalCorpus.get_reference_ids(%s): %s", s2_id, e)
            return None


# ──────────────────────────────────────────────────────────
# PostgresCache — wraps existing S2Paper/S2Citation tables
# ──────────────────────────────────────────────────────────


class PostgresCache:
    """S2DataSource backed by existing Folio PostgreSQL tables.

    Returns data only for papers that have been previously synced
    (library papers + their 1-hop neighborhoods).
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_paper(self, s2_id: str) -> PaperRecord | None:
        from sqlalchemy import select

        from app.models import S2Paper

        result = await self._session.execute(
            select(S2Paper).where(S2Paper.s2_id == s2_id)
        )
        paper = result.scalar_one_or_none()
        if not paper:
            return None

        tldr_text = None
        if paper.tldr and isinstance(paper.tldr, dict):
            tldr_text = paper.tldr.get("text")

        oa_url = None
        if paper.open_access_pdf and isinstance(paper.open_access_pdf, dict):
            oa_url = paper.open_access_pdf.get("url")

        return PaperRecord(
            s2_id=paper.s2_id,
            title=paper.title or "",
            year=paper.year,
            venue=paper.venue,
            authors=paper.authors or [],
            abstract=paper.abstract,
            tldr=tldr_text,
            citation_count=paper.citation_count or 0,
            reference_count=paper.reference_count or 0,
            influential_citation_count=paper.influential_citation_count or 0,
            is_open_access=paper.is_open_access or False,
            open_access_pdf_url=oa_url,
            fields_of_study=paper.fields_of_study or [],
            publication_types=paper.publication_types or [],
            external_ids=paper.external_ids or {},
        )

    async def get_paper_by_corpus_id(self, corpus_id: int) -> PaperRecord | None:
        # Postgres store doesn't index by corpus_id
        return None

    async def get_references(self, s2_id: str) -> list[EdgeRecord] | None:
        from sqlalchemy import select

        from app.models import S2Citation

        result = await self._session.execute(
            select(S2Citation).where(S2Citation.source_id == s2_id)
        )
        rows = result.scalars().all()
        if not rows:
            return None  # None = "I don't know" (no data synced for this paper)

        return [
            EdgeRecord(
                citing_s2_id=s2_id,
                cited_s2_id=r.target_id,
                is_influential=r.is_influential or False,
            )
            for r in rows
        ]

    async def get_citations(self, s2_id: str) -> list[EdgeRecord] | None:
        from sqlalchemy import select

        from app.models import S2Citation

        result = await self._session.execute(
            select(S2Citation).where(S2Citation.target_id == s2_id)
        )
        rows = result.scalars().all()
        if not rows:
            return None

        return [
            EdgeRecord(
                citing_s2_id=r.source_id,
                cited_s2_id=s2_id,
                is_influential=r.is_influential or False,
            )
            for r in rows
        ]

    async def resolve_id(self, id_type: str, identifier: str) -> str | None:
        # Postgres doesn't index external IDs for lookup
        return None

    async def search(self, query: str, limit: int = 10) -> list[PaperRecord] | None:
        return None

    async def get_reference_ids(self, s2_id: str) -> set[str] | None:
        refs = await self.get_references(s2_id)
        if refs is None:
            return None
        return {e.cited_s2_id for e in refs if e.cited_s2_id}

    # ── Write-through support ──

    async def store_paper(self, record: PaperRecord) -> None:
        """Cache a paper record into PostgreSQL (write-through)."""
        if not record.s2_id:
            return
        from app.services.s2 import SQLAlchemyPaperStore

        store = SQLAlchemyPaperStore(self._session)
        await store.upsert_paper(
            {
                "s2_id": record.s2_id,
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
                "fields_of_study": record.fields_of_study,
                "publication_types": record.publication_types,
                "external_ids": record.external_ids,
            }
        )


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
        return _api_dict_to_paper(data)

    async def get_paper_by_corpus_id(self, corpus_id: int) -> PaperRecord | None:
        data = await self._transport.get(
            f"paper/CorpusId:{corpus_id}", params={"fields": _LIVE_PAPER_FIELDS}
        )
        if not data:
            return None
        return _api_dict_to_paper(data)

    async def get_references(self, s2_id: str) -> list[EdgeRecord] | None:
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

    async def get_citations(self, s2_id: str) -> list[EdgeRecord] | None:
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
            return [_api_dict_to_paper(d) for d in data]
        return None

    async def get_reference_ids(self, s2_id: str) -> set[str] | None:
        refs = await self.get_references(s2_id)
        if refs is None:
            return None
        return {e.cited_s2_id for e in refs if e.cited_s2_id}


def _api_dict_to_paper(data: dict) -> PaperRecord:
    """Convert an S2 API response dict to a PaperRecord."""
    tldr = data.get("tldr")
    tldr_text = tldr.get("text") if isinstance(tldr, dict) else None

    oa_pdf = data.get("openAccessPdf")
    oa_url = oa_pdf.get("url") if isinstance(oa_pdf, dict) else None

    authors = data.get("authors") or []

    fos = data.get("fieldsOfStudy") or data.get("s2FieldsOfStudy") or []
    if fos and isinstance(fos[0], dict):
        fos = [f.get("category", "") for f in fos]

    return PaperRecord(
        s2_id=data.get("paperId"),
        title=data.get("title", ""),
        year=data.get("year"),
        venue=data.get("venue"),
        authors=[
            {"authorId": a.get("authorId"), "name": a.get("name")} for a in authors
        ],
        abstract=data.get("abstract"),
        tldr=tldr_text,
        citation_count=data.get("citationCount", 0),
        reference_count=data.get("referenceCount", 0),
        influential_citation_count=data.get("influentialCitationCount", 0),
        is_open_access=data.get("isOpenAccess", False),
        open_access_pdf_url=oa_url,
        fields_of_study=fos,
        publication_types=data.get("publicationTypes") or [],
        external_ids=data.get("externalIds") or {},
    )


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
        cache: PostgresCache | None = None,
    ):
        self._sources = sources
        self._cache = cache

    async def get_paper(self, s2_id: str) -> PaperRecord | None:
        for source in self._sources:
            result = await source.get_paper(s2_id)
            if result is not None:
                # Write-through: cache if this came from a non-cache source
                if self._cache and source is not self._cache:
                    try:
                        await self._cache.store_paper(result)
                    except Exception as e:
                        logger.debug("ChainedSource write-through failed: %s", e)
                return result
        return None

    async def get_paper_by_corpus_id(self, corpus_id: int) -> PaperRecord | None:
        for source in self._sources:
            result = await source.get_paper_by_corpus_id(corpus_id)
            if result is not None:
                return result
        return None

    async def get_references(self, s2_id: str) -> list[EdgeRecord] | None:
        for source in self._sources:
            result = await source.get_references(s2_id)
            if result is not None:
                return result
        return None

    async def get_citations(self, s2_id: str) -> list[EdgeRecord] | None:
        for source in self._sources:
            result = await source.get_citations(s2_id)
            if result is not None:
                return result
        return None

    async def resolve_id(self, id_type: str, identifier: str) -> str | None:
        for source in self._sources:
            result = await source.resolve_id(id_type, identifier)
            if result is not None:
                return result
        return None

    async def search(self, query: str, limit: int = 10) -> list[PaperRecord] | None:
        for source in self._sources:
            result = await source.search(query, limit=limit)
            if result is not None:
                return result
        return None

    async def get_reference_ids(self, s2_id: str) -> set[str] | None:
        for source in self._sources:
            result = await source.get_reference_ids(s2_id)
            if result is not None:
                return result
        return None
