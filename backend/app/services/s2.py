"""
Compatibility surface for Semantic Scholar services.
"""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import Entry
from app.schemas.s2 import S2Paper as S2PaperSchema
from app.services.s2_protocol import S2DataSource
from app.services.s2_resolvers import (
    ArXivResolver,
    DOIResolver,
    Resolver,
    TitleResolver,
    default_resolvers as _default_resolvers,
)
from app.services.s2_runtime import SyncRegistry
from app.services.s2_store import (
    FULL_PAPER_FIELDS,
    PaperStore,
    SQLAlchemyPaperStore,
    paper_to_record,
)
from app.services.s2_sync import SyncOrchestrator, SyncStatus, create_sync_orchestrator
from app.services.s2_transport import S2Transport

logger = logging.getLogger(__name__)

__all__ = [
    "ArXivResolver",
    "DOIResolver",
    "FULL_PAPER_FIELDS",
    "PaperStore",
    "Resolver",
    "S2Transport",
    "SQLAlchemyPaperStore",
    "SyncOrchestrator",
    "SyncStatus",
    "TitleResolver",
    "_default_resolvers",
    "background_sync_entry",
    "create_sync_orchestrator",
    "paper_to_record",
    "resolve_entry_s2_id",
    "sync_entry",
    "upsert_s2_paper",
]


async def sync_entry(
    orchestrator: SyncOrchestrator,
    entry_id: str,
    force: bool = False,
) -> SyncStatus:
    """Public entry-point for syncing one library entry against S2."""
    return await orchestrator.ensure_synced(entry_id, force=force)


async def background_sync_entry(
    orchestrator: SyncOrchestrator,
    entry_id: str,
    force: bool = False,
) -> None:
    """Background-safe sync wrapper with error logging."""
    try:
        await sync_entry(orchestrator, entry_id, force=force)
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.warning("Background sync failed for %s: %s", entry_id, exc)


async def resolve_entry_s2_id(
    entry: Entry,
    session: AsyncSession,
    *,
    source: S2DataSource,
    session_factory: async_sessionmaker[AsyncSession],
    transport: S2Transport | None = None,
    resolvers: list[Resolver] | None = None,
) -> str | None:
    """Resolve and persist an S2 paper ID for an entry using the current policy."""
    if entry.s2_id:
        return entry.s2_id

    orchestrator = create_sync_orchestrator(
        source=source,
        sync_registry=SyncRegistry(),
        transport=transport,
        resolvers=resolvers,
        session_factory=session_factory,
    )
    s2_id = await orchestrator.resolve_entry(entry)
    if not s2_id:
        return None

    store = SQLAlchemyPaperStore(session)
    await store.set_entry_s2_id(str(entry.id), s2_id)
    await store.commit()
    return s2_id


async def upsert_s2_paper(session: AsyncSession, paper: S2PaperSchema) -> None:
    """Persist one normalized S2 paper record."""
    store = SQLAlchemyPaperStore(session)
    await store.upsert_paper(paper_to_record(paper))
    await store.commit()
