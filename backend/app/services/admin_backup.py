"""
Backup and restore application services for admin flows.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Collection, CollectionEntry, Entry
from app.schemas.admin import (
    ExportData,
    ExportedCollection,
    ExportedEntry,
    ImportResult,
)


async def export_user_state(db: AsyncSession) -> ExportData:
    result = await db.execute(
        select(Entry).where((Entry.notes.isnot(None)) | (Entry.read == True))  # noqa
    )
    entries_with_state = result.scalars().all()

    exported_entries = [
        ExportedEntry(
            citation_key=entry.citation_key,
            notes=entry.notes,
            read=entry.read,
        )
        for entry in entries_with_state
    ]

    result = await db.execute(
        select(Collection).options(
            selectinload(Collection.entries).selectinload(CollectionEntry.entry)
        )
    )
    collections = result.scalars().all()

    exported_collections = [
        ExportedCollection(
            name=collection.name,
            description=collection.description,
            sort_order=collection.sort_order,
            entry_keys=[
                collection_entry.entry.citation_key
                for collection_entry in collection.entries
                if collection_entry.entry
            ],
        )
        for collection in collections
    ]

    return ExportData(
        exported_at=datetime.now(UTC).isoformat(),
        entries=exported_entries,
        collections=exported_collections,
    )


async def import_user_state(
    db: AsyncSession,
    data: ExportData,
) -> ImportResult:
    errors: list[str] = []
    entries_updated = 0
    entries_skipped = 0
    collections_created = 0
    collections_updated = 0

    result = await db.execute(select(Entry))
    all_entries = {entry.citation_key: entry for entry in result.scalars().all()}

    for exported_entry in data.entries:
        entry = all_entries.get(exported_entry.citation_key)
        if entry is None:
            entries_skipped += 1
            errors.append(f"Entry not found: {exported_entry.citation_key}")
            continue

        entry.notes = exported_entry.notes
        entry.read = exported_entry.read
        entries_updated += 1

    for exported_collection in data.collections:
        result = await db.execute(
            select(Collection).where(Collection.name == exported_collection.name)
        )
        collection = result.scalar_one_or_none()

        if collection is None:
            collection = Collection(
                name=exported_collection.name,
                description=exported_collection.description,
                sort_order=exported_collection.sort_order,
            )
            db.add(collection)
            await db.flush()
            collections_created += 1
        else:
            collection.description = exported_collection.description
            collection.sort_order = exported_collection.sort_order
            await db.execute(
                CollectionEntry.__table__.delete().where(
                    CollectionEntry.collection_id == collection.id
                )
            )
            collections_updated += 1

        for index, citation_key in enumerate(exported_collection.entry_keys):
            entry = all_entries.get(citation_key)
            if entry is None:
                errors.append(
                    f"Collection '{exported_collection.name}': entry not found: {citation_key}"
                )
                continue

            db.add(
                CollectionEntry(
                    collection_id=collection.id,
                    entry_id=entry.id,
                    sort_order=index,
                )
            )

    await db.commit()

    return ImportResult(
        entries_updated=entries_updated,
        entries_skipped=entries_skipped,
        collections_created=collections_created,
        collections_updated=collections_updated,
        errors=errors,
    )
