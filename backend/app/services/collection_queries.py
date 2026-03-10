"""
Query services for collections.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.exceptions import NotFoundError
from app.models import Collection, CollectionEntry
from app.schemas.collections import (
    CollectionDetailResponse,
    CollectionEntryItem,
    CollectionResponse,
)


async def list_collections(
    db: AsyncSession,
    *,
    limit: int,
    offset: int,
) -> list[CollectionResponse]:
    result = await db.execute(
        select(Collection)
        .options(selectinload(Collection.entries))
        .order_by(Collection.sort_order, Collection.name)
        .limit(limit)
        .offset(offset)
    )
    collections = result.scalars().all()
    return [
        CollectionResponse(
            id=str(collection.id),
            name=collection.name,
            entry_count=len(collection.entries),
        )
        for collection in collections
    ]


async def get_collection_detail(
    db: AsyncSession,
    collection_id: UUID,
) -> CollectionDetailResponse:
    result = await db.execute(
        select(Collection)
        .options(selectinload(Collection.entries).selectinload(CollectionEntry.entry))
        .where(Collection.id == collection_id)
    )
    collection = result.scalar_one_or_none()

    if collection is None:
        raise NotFoundError("Collection", str(collection_id))

    entries = [
        CollectionEntryItem(
            id=str(collection_entry.entry.id),
            title=collection_entry.entry.title,
            year=collection_entry.entry.year,
            sort_order=collection_entry.sort_order,
        )
        for collection_entry in sorted(
            collection.entries,
            key=lambda item: item.sort_order,
        )
    ]

    return CollectionDetailResponse(
        id=str(collection.id),
        name=collection.name,
        description=collection.description,
        entry_count=len(entries),
        entries=entries,
    )
