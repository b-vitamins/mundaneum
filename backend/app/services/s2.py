"""
Compatibility surface for Semantic Scholar services.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Entry
from app.schemas.s2 import S2Paper as S2PaperSchema
from app.services.s2_resolvers import (
    ArXivResolver,
    DOIResolver,
    Resolver,
    TitleResolver,
    default_resolvers as _default_resolvers,
)
from app.services.s2_runtime import SyncRegistry
from app.services.s2_store import FULL_PAPER_FIELDS, PaperStore, SQLAlchemyPaperStore, paper_to_record
from app.services.s2_sync import SyncOrchestrator, SyncStatus, create_sync_orchestrator
from app.services.s2_transport import S2Transport

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
    "get_sync_orchestrator",
    "paper_to_record",
    "resolve_entry_s2_id",
    "sync_entry",
    "upsert_s2_paper",
]


async def sync_entry(entry_id: str, force: bool = False) -> SyncStatus:
    """Public entry-point for syncing one library entry against S2."""
    return await get_sync_orchestrator().ensure_synced(entry_id, force=force)


async def background_sync_entry(entry_id: str, force: bool = False) -> None:
    """Background-safe sync wrapper with error logging."""
    import logging

    logger = logging.getLogger(__name__)
    try:
        await sync_entry(entry_id, force=force)
    except Exception as exc:
        logger.warning("Background sync failed for %s: %s", entry_id, exc)


async def resolve_entry_s2_id(
    entry: Entry,
    session: AsyncSession,
    transport: S2Transport | None = None,
    resolvers: list[Resolver] | None = None,
) -> str | None:
    """Resolve and persist an S2 paper ID for an entry using the current policy."""
    if entry.s2_id:
        return entry.s2_id

    from app.services.s2_runtime import get_s2_runtime

    orchestrator = create_sync_orchestrator(
        source=get_s2_runtime().data_source,
        sync_registry=SyncRegistry(),
        transport=transport,
        resolvers=resolvers,
    )
    s2_id = await orchestrator._resolve(entry)
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


def get_sync_orchestrator() -> SyncOrchestrator:
    """Compatibility wrapper returning the runtime-owned orchestrator."""
    from app.services.s2_runtime import get_s2_runtime

    return get_s2_runtime().orchestrator
