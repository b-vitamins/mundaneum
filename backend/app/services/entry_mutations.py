"""
Entry mutation helpers.
"""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Entry
from app.services.domain_events import DomainEventBus, EntriesChanged
from app.services.entry_queries import get_entry


async def update_entry_read(
    db: AsyncSession,
    entry_id: UUID,
    *,
    read: bool,
    event_bus: DomainEventBus | None = None,
) -> Entry:
    """Persist a read-state mutation."""
    entry = await get_entry(db, entry_id, include_relationships=False)
    entry.read = read
    await db.commit()
    if event_bus is not None:
        await event_bus.publish(EntriesChanged(entry_ids=(str(entry.id),)))
    return entry


async def update_entry_notes(
    db: AsyncSession,
    entry_id: UUID,
    *,
    notes: str,
    event_bus: DomainEventBus | None = None,
) -> Entry:
    """Persist an entry notes mutation."""
    entry = await get_entry(db, entry_id, include_relationships=False)
    entry.notes = notes
    await db.commit()
    if event_bus is not None:
        await event_bus.publish(EntriesChanged(entry_ids=(str(entry.id),)))
    return entry
