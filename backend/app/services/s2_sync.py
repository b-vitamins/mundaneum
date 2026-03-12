"""
Sync orchestration for Semantic Scholar records.
"""

from __future__ import annotations

import enum
import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import settings
from app.services.s2_protocol import S2DataSource
from app.services.s2_resolvers import Resolver, default_resolvers
from app.services.s2_store import SQLAlchemyPaperStore
from app.services.s2_sync_steps import (
    ApiHydrationStep,
    CorpusHydrationStep,
    EdgeFetchStep,
    ResolutionStep,
)
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
    """Compose sync steps into one explicit pipeline."""

    def __init__(
        self,
        *,
        sync_registry,
        session_factory: async_sessionmaker[AsyncSession],
        resolver: ResolutionStep,
        corpus_hydrator: CorpusHydrationStep,
        api_hydrator: ApiHydrationStep,
        store_factory=None,
    ):
        self._sync_registry = sync_registry
        self._session_factory = session_factory
        self._resolver = resolver
        self._corpus_hydrator = corpus_hydrator
        self._api_hydrator = api_hydrator
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
                    s2_id = await self._resolver.resolve(entry)
                    if not s2_id:
                        logger.warning(
                            "Could not resolve S2 ID for '%s'", entry.title[:40]
                        )
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

    async def resolve_entry(self, entry) -> str | None:
        """Expose the resolution step for compatibility helpers."""
        return await self._resolver.resolve(entry)

    async def _sync_paper(self, s2_id: str, store) -> SyncStatus:
        corpus_status = await self._corpus_hydrator.hydrate(s2_id, store)
        if corpus_status is not None:
            return corpus_status
        return await self._api_hydrator.hydrate(
            s2_id,
            store,
            max_edges=settings.s2_max_edges,
        )


def create_sync_orchestrator(
    *,
    source: S2DataSource,
    sync_registry,
    transport: S2Transport | None = None,
    resolvers: list[Resolver] | None = None,
    session_factory: async_sessionmaker[AsyncSession],
    store_factory=None,
) -> SyncOrchestrator:
    """Create a sync orchestrator with default transport and resolver policy."""
    transport = transport or S2Transport(
        api_key=settings.s2_api_key,
        rate_limit=settings.s2_rate_limit,
    )
    resolver = ResolutionStep(
        source=source,
        transport=transport,
        resolvers=resolvers or default_resolvers(),
    )
    edge_fetcher = EdgeFetchStep(transport=transport)
    return SyncOrchestrator(
        sync_registry=sync_registry,
        session_factory=session_factory,
        resolver=resolver,
        corpus_hydrator=CorpusHydrationStep(source=source),
        api_hydrator=ApiHydrationStep(
            transport=transport,
            edge_fetcher=edge_fetcher,
        ),
        store_factory=store_factory,
    )
