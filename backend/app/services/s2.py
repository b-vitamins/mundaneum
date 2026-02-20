"""
Semantic Scholar integration — composable, protocol-based architecture.

Design principles (Sussman, "Software Design for Flexibility"):
  - Generic mechanisms composed by specific policies.
  - Every behaviour is a composable strategy, not a hardcoded procedure.
  - Adding a new resolver, edge source, or rate policy never requires
    modifying existing code.

Architecture:
  S2Transport    — Rate-limited async HTTP with backoff.
  Resolver       — Protocol for entry → S2 paper ID mapping.
  PaperStore     — Protocol for persistence of S2 data.
  SyncOrchestrator — Composes the above into a single `ensure_synced()`.
"""

from __future__ import annotations

import asyncio
import enum
import logging
import time
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol, runtime_checkable

import httpx
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session
from app.models import Entry, S2Citation, S2Paper
from app.schemas.s2 import S2GraphResponse
from app.schemas.s2 import S2Paper as S2PaperSchema

logger = logging.getLogger(__name__)

S2_API_BASE = "https://api.semanticscholar.org/graph/v1"

# Fields we request for a full paper record
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


# ──────────────────────────────────────────────────────────
# SyncStatus — what callers observe
# ──────────────────────────────────────────────────────────


class SyncStatus(enum.Enum):
    """Result of an ensure_synced() call."""

    FRESH = "fresh"  # Data exists and is not stale
    SYNCED = "synced"  # Data was just fetched
    SYNCING = "syncing"  # Sync is in progress (poll later)
    FAILED = "failed"  # Sync attempted but failed
    NO_MATCH = "no_match"  # Entry could not be matched to any S2 paper


# ──────────────────────────────────────────────────────────
# S2Transport — rate-limited, backoff-aware HTTP
# ──────────────────────────────────────────────────────────


class S2Transport:
    """
    Async HTTP transport for the S2 API.

    Rate limiting: token-bucket (configurable).
    Backoff: exponential on 429, up to max_retries.
    API key: passed as x-api-key if configured.
    """

    def __init__(
        self,
        api_key: str | None = None,
        rate_limit: float = 0.9,
        max_retries: int = 5,
    ):
        self._api_key = api_key
        self._rate_limit = 10.0 if api_key else rate_limit
        self._max_retries = max_retries

        # Token bucket state
        self._tokens = self._rate_limit
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

        # Shared client (created lazily)
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            headers = {}
            if self._api_key:
                headers["x-api-key"] = self._api_key
            self._client = httpx.AsyncClient(
                timeout=30.0,
                headers=headers,
                limits=httpx.Limits(max_connections=5),
            )
        return self._client

    async def _acquire_token(self):
        """Block until a rate-limit token is available."""
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_refill
            self._tokens = min(
                self._rate_limit,
                self._tokens + elapsed * self._rate_limit,
            )
            self._last_refill = now

            if self._tokens < 1.0:
                wait = (1.0 - self._tokens) / self._rate_limit
                await asyncio.sleep(wait)
                self._tokens = 0.0
            else:
                self._tokens -= 1.0

    async def get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> dict | None:
        """GET a path under the S2 API base, with rate limiting and backoff."""
        url = f"{S2_API_BASE}/{path.lstrip('/')}"
        client = await self._get_client()

        for attempt in range(self._max_retries):
            await self._acquire_token()
            try:
                resp = await client.get(url, params=params)
                if resp.status_code == 200:
                    return resp.json()
                elif resp.status_code == 429:
                    wait = 2.0 * (2**attempt)
                    logger.warning(f"S2 429 rate-limit, retry in {wait:.1f}s ({path})")
                    await asyncio.sleep(wait)
                    continue
                elif resp.status_code == 404:
                    return None
                else:
                    logger.error(f"S2 {resp.status_code}: {resp.text[:200]} ({path})")
                    return None
            except httpx.TimeoutException:
                wait = 2.0 * (2**attempt)
                logger.warning(f"S2 timeout, retry in {wait:.1f}s ({path})")
                await asyncio.sleep(wait)
            except Exception as e:
                logger.error(f"S2 transport error: {e} ({path})")
                return None
        return None

    async def search(self, query: str, limit: int = 1) -> list[dict]:
        """Search papers by title via the S2 search API."""
        data = await self.get(
            "paper/search",
            params={"query": query, "limit": limit, "fields": "paperId,title"},
        )
        if data and "data" in data:
            return data["data"]
        return []

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()


# ──────────────────────────────────────────────────────────
# Resolver protocol + implementations
# ──────────────────────────────────────────────────────────


@runtime_checkable
class Resolver(Protocol):
    """Map a library Entry to an S2 paper ID."""

    async def resolve(self, entry: Entry, transport: S2Transport) -> str | None: ...


class DOIResolver:
    """Resolve via DOI — deterministic, sub-second."""

    async def resolve(self, entry: Entry, transport: S2Transport) -> str | None:
        doi = _extract_id(entry, "doi")
        if not doi:
            return None
        data = await transport.get(f"paper/DOI:{doi}", params={"fields": "paperId"})
        if data and data.get("paperId"):
            logger.info(f"Resolved '{entry.title[:40]}' via DOI:{doi}")
            return data["paperId"]
        return None


class ArXivResolver:
    """Resolve via ArXiv ID — deterministic, sub-second."""

    async def resolve(self, entry: Entry, transport: S2Transport) -> str | None:
        arxiv_id = _extract_id(entry, "arxiv", "eprint")
        if not arxiv_id:
            return None
        data = await transport.get(
            f"paper/ARXIV:{arxiv_id}", params={"fields": "paperId"}
        )
        if data and data.get("paperId"):
            logger.info(f"Resolved '{entry.title[:40]}' via ArXiv:{arxiv_id}")
            return data["paperId"]
        return None


class TitleResolver:
    """Fallback: search by title — 1-2s via direct API."""

    async def resolve(self, entry: Entry, transport: S2Transport) -> str | None:
        results = await transport.search(entry.title, limit=3)
        if not results:
            return None

        # Simple heuristic: take the first result whose title is close enough
        query_lower = entry.title.lower().strip()
        for r in results:
            title = (r.get("title") or "").lower().strip()
            if title and _title_similarity(query_lower, title) > 0.7:
                s2_id = r.get("paperId")
                if s2_id:
                    logger.info(f"Resolved '{entry.title[:40]}' via title search")
                    return s2_id

        # If nothing matches well, take the first result anyway (best effort)
        first = results[0].get("paperId")
        if first:
            logger.info(f"Resolved '{entry.title[:40]}' via title search (best-effort)")
            return first
        return None


def _extract_id(entry: Entry, *field_names: str) -> str | None:
    """Extract an identifier from entry's bibtex fields."""
    for fields in [entry.required_fields or {}, entry.optional_fields or {}]:
        for name in field_names:
            val = (
                fields.get(name) or fields.get(name.upper()) or fields.get(name.lower())
            )
            if val and isinstance(val, str) and val.strip():
                return val.strip()
    return None


def _title_similarity(a: str, b: str) -> float:
    """Jaccard similarity over word sets — fast and good enough."""
    wa, wb = set(a.split()), set(b.split())
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / len(wa | wb)


# ──────────────────────────────────────────────────────────
# PaperStore protocol + SQLAlchemy implementation
# ──────────────────────────────────────────────────────────


@runtime_checkable
class PaperStore(Protocol):
    """Persistence layer for S2 data."""

    async def get_paper(self, s2_id: str) -> S2Paper | None: ...
    async def upsert_paper(self, data: dict) -> None: ...
    async def upsert_papers_batch(self, records: list[dict]) -> None: ...
    async def upsert_edges(self, edges: list[dict]) -> None: ...
    async def is_stale(self, s2_id: str, ttl_days: int) -> bool: ...
    async def set_entry_s2_id(self, entry_id: str, s2_id: str) -> None: ...
    async def unresolved_entries(self, limit: int) -> list[Entry]: ...
    async def get_entry(self, entry_id: str) -> Entry | None: ...


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
        if not paper:
            return True
        if not paper.updated_at:
            return True
        return paper.updated_at < datetime.now(UTC) - timedelta(days=ttl_days)

    async def set_entry_s2_id(self, entry_id: str, s2_id: str) -> None:
        result = await self._session.execute(select(Entry).where(Entry.id == entry_id))
        entry = result.scalar_one_or_none()
        if entry:
            entry.s2_id = s2_id
            self._session.add(entry)
            await self._session.commit()

    async def upsert_paper(self, data: dict) -> None:
        stmt = insert(S2Paper).values(data)
        stmt = stmt.on_conflict_do_update(
            index_elements=[S2Paper.s2_id],
            set_={k: v for k, v in data.items() if k != "s2_id"},
        )
        await self._session.execute(stmt)
        await self._session.commit()

    async def upsert_papers_batch(self, records: list[dict]) -> None:
        if not records:
            return
        stmt = insert(S2Paper).values(records)
        stmt = stmt.on_conflict_do_nothing(index_elements=[S2Paper.s2_id])
        await self._session.execute(stmt)
        await self._session.commit()

    async def upsert_edges(self, edges: list[dict]) -> None:
        if not edges:
            return
        stmt = insert(S2Citation).values(edges)
        stmt = stmt.on_conflict_do_update(
            index_elements=[S2Citation.source_id, S2Citation.target_id],
            set_={
                "contexts": stmt.excluded.contexts,
                "intents": stmt.excluded.intents,
                "is_influential": stmt.excluded.is_influential,
            },
        )
        await self._session.execute(stmt)
        await self._session.commit()

    async def unresolved_entries(self, limit: int) -> list[Entry]:
        result = await self._session.execute(
            select(Entry)
            .where(Entry.s2_id.is_(None))
            .order_by(Entry.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())


# ──────────────────────────────────────────────────────────
# SyncOrchestrator — the single entry point
# ──────────────────────────────────────────────────────────


# In-flight sync tracking (prevents duplicate concurrent syncs)
_sync_locks: dict[str, asyncio.Event] = {}


class SyncOrchestrator:
    """
    Composes transport, resolvers, and store into a single API.

    ensure_synced(entry_id) is the *only* method callers need.
    It is always idempotent, never blocks unnecessarily, and
    returns a SyncStatus so callers can decide what to show.
    """

    def __init__(
        self,
        transport: S2Transport,
        resolvers: list[Resolver],
        store_factory=None,
    ):
        self._transport = transport
        self._resolvers = resolvers
        self._store_factory = store_factory or (
            lambda session: SQLAlchemyPaperStore(session)
        )

    async def ensure_synced(self, entry_id: str, force: bool = False) -> SyncStatus:
        """
        Ensure an entry has up-to-date S2 data.

        1. If data is fresh → FRESH
        2. If another task is syncing this entry → SYNCING
        3. Resolve S2 ID if missing (DOI → ArXiv → Title)
        4. Fetch paper metadata + edges
        5. Return SYNCED or FAILED
        """
        # Check if already syncing
        if entry_id in _sync_locks:
            return SyncStatus.SYNCING

        async with async_session() as session:
            store = self._store_factory(session)
            entry = await store.get_entry(entry_id)
            if not entry:
                logger.error(f"Entry {entry_id} not found")
                return SyncStatus.FAILED

            # Resolve S2 ID if missing
            s2_id = entry.s2_id
            if not s2_id:
                s2_id = await self._resolve(entry)
                if not s2_id:
                    logger.warning(f"Could not resolve S2 ID for '{entry.title[:40]}'")
                    return SyncStatus.NO_MATCH
                await store.set_entry_s2_id(entry_id, s2_id)

            # Check staleness
            if not force and not await store.is_stale(
                s2_id, settings.s2_staleness_days
            ):
                return SyncStatus.FRESH

            # Mark as syncing
            event = asyncio.Event()
            _sync_locks[entry_id] = event

            try:
                status = await self._sync_paper(s2_id, store)
                return status
            finally:
                _sync_locks.pop(entry_id, None)
                event.set()

    async def backfill(self, batch_size: int = 10) -> int:
        """Resolve and sync unresolved entries. Returns count resolved."""
        resolved = 0
        async with async_session() as session:
            store = self._store_factory(session)
            entries = await store.unresolved_entries(batch_size)

            for entry in entries:
                try:
                    status = await self.ensure_synced(str(entry.id))
                    if status in (SyncStatus.SYNCED, SyncStatus.FRESH):
                        resolved += 1
                    elif status == SyncStatus.NO_MATCH:
                        logger.info(f"No S2 match for '{entry.title[:40]}', skipping")
                except Exception as e:
                    logger.error(f"Backfill error for {entry.id}: {e}")

        if resolved:
            logger.info(f"Backfill: resolved {resolved}/{len(entries)} entries")
        return resolved

    async def _resolve(self, entry: Entry) -> str | None:
        """Try each resolver in order. First hit wins."""
        for resolver in self._resolvers:
            try:
                s2_id = await resolver.resolve(entry, self._transport)
                if s2_id:
                    return s2_id
            except Exception as e:
                logger.warning(
                    f"{resolver.__class__.__name__} failed for "
                    f"'{entry.title[:30]}': {e}"
                )
        return None

    async def _sync_paper(self, s2_id: str, store: PaperStore) -> SyncStatus:
        """Fetch paper metadata and edges from S2 API."""
        # 1. Fetch main paper
        fields = ",".join(FULL_PAPER_FIELDS)
        data = await self._transport.get(f"paper/{s2_id}", params={"fields": fields})
        if not data:
            return SyncStatus.FAILED

        try:
            paper = S2PaperSchema(**data)
        except ValidationError as e:
            logger.error(f"S2 paper parse error ({s2_id}): {e}")
            return SyncStatus.FAILED

        # Upsert main paper
        paper_record = _paper_to_record(paper)
        await store.upsert_paper(paper_record)

        # 2. Fetch edges (citations + references) in parallel
        max_edges = settings.s2_max_edges
        cit_task = self._fetch_edges(s2_id, "citations", max_edges)
        ref_task = self._fetch_edges(s2_id, "references", max_edges)
        cit_result, ref_result = await asyncio.gather(cit_task, ref_task)

        # 3. Store edges
        papers: list[dict] = []
        edges: list[dict] = []

        for sub, edge in cit_result:
            papers.append(sub)
            edges.append(edge)
        for sub, edge in ref_result:
            papers.append(sub)
            edges.append(edge)

        await store.upsert_papers_batch(papers)
        await store.upsert_edges(edges)

        logger.info(
            f"Synced {s2_id}: {len(cit_result)} citations, {len(ref_result)} references"
        )
        return SyncStatus.SYNCED

    async def _fetch_edges(
        self,
        s2_id: str,
        edge_type: str,
        max_total: int,
    ) -> list[tuple[dict, dict]]:
        """
        Paginate through citations or references.
        Returns list of (paper_record, edge_record) tuples.
        """
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
        fields_str = ",".join(fields_list)

        results: list[tuple[dict, dict]] = []
        offset = 0
        page_size = min(100, max_total)  # S2 max page size

        while offset < max_total:
            data = await self._transport.get(
                f"paper/{s2_id}/{edge_type}",
                params={
                    "fields": fields_str,
                    "limit": page_size,
                    "offset": offset,
                },
            )
            if not data:
                break

            try:
                response = S2GraphResponse(**data)
            except ValidationError as e:
                logger.error(f"S2 edge parse error ({s2_id}/{edge_type}): {e}")
                break

            if not response.data:
                break

            for item in response.data:
                sub = item.citingPaper if edge_type == "citations" else item.citedPaper
                if not sub or not sub.paperId:
                    continue

                authors_data = [
                    {"authorId": a.authorId, "name": a.name}
                    for a in sub.authors
                    if a.authorId
                ]

                paper_rec = {
                    "s2_id": sub.paperId,
                    "title": sub.title or "Unknown",
                    "year": sub.year,
                    "venue": sub.venue,
                    "authors": authors_data,
                    "citation_count": sub.citationCount or 0,
                    "updated_at": datetime.now(UTC),
                }

                edge_rec = {
                    "source_id": sub.paperId if edge_type == "citations" else s2_id,
                    "target_id": s2_id if edge_type == "citations" else sub.paperId,
                    "contexts": item.contexts,
                    "intents": item.intents,
                    "is_influential": item.isInfluential,
                }

                results.append((paper_rec, edge_rec))

            # Next page
            offset += len(response.data)
            if len(response.data) < page_size:
                break  # No more pages

        return results


# ──────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────


def _paper_to_record(paper: S2PaperSchema) -> dict:
    """Convert a Pydantic S2Paper to a flat dict for DB upsert."""
    authors_data = [
        {"authorId": a.authorId, "name": a.name} for a in paper.authors if a.authorId
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


# ──────────────────────────────────────────────────────────
# Factory — wires everything together
# ──────────────────────────────────────────────────────────

_orchestrator: SyncOrchestrator | None = None


def get_sync_orchestrator() -> SyncOrchestrator:
    """
    Singleton factory for the sync orchestrator.

    Lazy-creates the transport, resolver chain, and orchestrator
    on first call. Subsequent calls return the same instance.
    """
    global _orchestrator
    if _orchestrator is None:
        transport = S2Transport(
            api_key=settings.s2_api_key,
            rate_limit=settings.s2_rate_limit,
        )
        resolvers: list[Resolver] = [
            DOIResolver(),
            ArXivResolver(),
            TitleResolver(),
        ]
        _orchestrator = SyncOrchestrator(
            transport=transport,
            resolvers=resolvers,
        )
    return _orchestrator
