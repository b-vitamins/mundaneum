"""
Mutation services for collections.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import ConflictError, NotFoundError
from app.logging import get_logger
from app.models import Collection, CollectionEntry, Entry
from app.schemas.collections import CollectionCreate, CollectionResponse

logger = get_logger(__name__)


async def create_collection(
    db: AsyncSession,
    data: CollectionCreate,
) -> CollectionResponse:
    result = await db.execute(select(Collection).where(Collection.name == data.name))
    if result.scalar_one_or_none():
        raise ConflictError("Collection already exists")

    collection = Collection(name=data.name)
    db.add(collection)
    await db.commit()

    logger.info("Created collection: %s", collection.name)
    return CollectionResponse(id=str(collection.id), name=collection.name, entry_count=0)


async def add_entry_to_collection(
    db: AsyncSession,
    *,
    collection_id: UUID,
    entry_id: UUID,
) -> dict:
    collection = await db.get(Collection, collection_id)
    if collection is None:
        raise NotFoundError("Collection", str(collection_id))

    entry = await db.get(Entry, entry_id)
    if entry is None:
        raise NotFoundError("Entry", str(entry_id))

    result = await db.execute(
        select(CollectionEntry).where(
            CollectionEntry.collection_id == collection_id,
            CollectionEntry.entry_id == entry_id,
        )
    )
    if result.scalar_one_or_none():
        raise ConflictError("Entry already in collection")

    result = await db.execute(
        select(CollectionEntry.sort_order)
        .where(CollectionEntry.collection_id == collection_id)
        .order_by(CollectionEntry.sort_order.desc())
        .limit(1)
    )
    max_order = result.scalar() or 0

    db.add(
        CollectionEntry(
            collection_id=collection_id,
            entry_id=entry_id,
            sort_order=max_order + 1,
        )
    )
    await db.commit()

    logger.info("Added entry %s to collection %s", entry.citation_key, collection.name)
    return {"status": "added"}


async def remove_entry_from_collection(
    db: AsyncSession,
    *,
    collection_id: UUID,
    entry_id: UUID,
) -> dict:
    result = await db.execute(
        select(CollectionEntry).where(
            CollectionEntry.collection_id == collection_id,
            CollectionEntry.entry_id == entry_id,
        )
    )
    collection_entry = result.scalar_one_or_none()

    if collection_entry is None:
        raise NotFoundError("Entry in collection")

    await db.delete(collection_entry)
    await db.commit()

    logger.info("Removed entry from collection")
    return {"status": "removed"}


async def delete_collection(
    db: AsyncSession,
    *,
    collection_id: UUID,
) -> dict:
    collection = await db.get(Collection, collection_id)
    if collection is None:
        raise NotFoundError("Collection", str(collection_id))

    name = collection.name
    await db.delete(collection)
    await db.commit()

    logger.info("Deleted collection: %s", name)
    return {"status": "deleted"}
