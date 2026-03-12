"""
Small domain-event bus for internal projections.
"""

from __future__ import annotations

import inspect
from collections import defaultdict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.logging import get_logger
from app.models import Entry
from app.services.entry_queries import entry_load_options
from app.services.sync import MeilisearchUnavailableError, SearchIndexService

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class EntriesChanged:
    """Projection event for one or more entry upserts/mutations."""

    entry_ids: tuple[str, ...]


EventHandler = Callable[[object], None | Awaitable[None]]


class DomainEventBus:
    """In-process event bus for app-owned projections."""

    def __init__(self):
        self._handlers: dict[type[object], list[EventHandler]] = defaultdict(list)

    def subscribe(self, event_type: type[object], handler: EventHandler) -> None:
        self._handlers[event_type].append(handler)

    async def publish(self, event: object) -> None:
        for handler in self._handlers[type(event)]:
            result = handler(event)
            if inspect.isawaitable(result):
                await result


class SearchProjection:
    """Project entry changes into the Meilisearch index."""

    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        search_index: SearchIndexService,
    ):
        self._session_factory = session_factory
        self._search_index = search_index

    async def on_entries_changed(self, event: EntriesChanged) -> None:
        if not event.entry_ids:
            return

        try:
            self._search_index.ensure_index()
        except MeilisearchUnavailableError:
            logger.warning(
                "Skipping search projection because Meilisearch is unavailable"
            )
            return

        async with self._session_factory() as session:
            entry_ids = [UUID(entry_id) for entry_id in event.entry_ids]
            result = await session.execute(
                entry_load_options(select(Entry).where(Entry.id.in_(entry_ids)))
            )
            entries = result.scalars().all()

        if not entries:
            return

        try:
            self._search_index.sync_entries(entries)
        except MeilisearchUnavailableError:
            logger.warning("Skipping entry sync because Meilisearch is unavailable")


def build_domain_event_bus(
    *,
    session_factory: async_sessionmaker[AsyncSession],
    search_index: SearchIndexService,
) -> DomainEventBus:
    """Build the runtime event bus and register projection subscribers."""
    bus = DomainEventBus()
    projection = SearchProjection(
        session_factory=session_factory,
        search_index=search_index,
    )
    bus.subscribe(EntriesChanged, projection.on_entries_changed)
    return bus
