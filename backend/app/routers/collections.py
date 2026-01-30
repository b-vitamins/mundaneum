"""
Collections router for Folio API.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.exceptions import ConflictError, NotFoundError
from app.logging import get_logger
from app.models import Collection, CollectionEntry, Entry

logger = get_logger(__name__)

router = APIRouter(prefix="/collections", tags=["collections"])


class CollectionCreate(BaseModel):
    """Request model for creating a collection."""

    name: str


class CollectionUpdate(BaseModel):
    """Request model for updating a collection."""

    name: str | None = None
    description: str | None = None


class CollectionResponse(BaseModel):
    """Response model for collection list items."""

    id: str
    name: str
    entry_count: int

    model_config = {"from_attributes": True}


class CollectionEntryItem(BaseModel):
    """Response model for entries in a collection."""

    id: str
    title: str
    year: int | None = None
    sort_order: int


class CollectionDetailResponse(CollectionResponse):
    """Response model for collection detail view."""

    description: str | None = None
    entries: list[CollectionEntryItem]


@router.get("", response_model=list[CollectionResponse])
async def list_collections(
    db: AsyncSession = Depends(get_db),
    limit: int = Query(100, ge=1, le=1000, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Results offset"),
):
    """List all collections."""
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
            id=str(c.id),
            name=c.name,
            entry_count=len(c.entries),
        )
        for c in collections
    ]


@router.post("", response_model=CollectionResponse, status_code=201)
async def create_collection(
    data: CollectionCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new collection."""
    # Check for duplicate name
    result = await db.execute(select(Collection).where(Collection.name == data.name))
    if result.scalar_one_or_none():
        raise ConflictError("Collection already exists")

    collection = Collection(name=data.name)
    db.add(collection)
    await db.commit()

    logger.info("Created collection: %s", collection.name)
    return CollectionResponse(
        id=str(collection.id), name=collection.name, entry_count=0
    )


@router.get("/{collection_id}", response_model=CollectionDetailResponse)
async def get_collection(
    collection_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get collection with its entries."""
    result = await db.execute(
        select(Collection)
        .options(selectinload(Collection.entries).selectinload(CollectionEntry.entry))
        .where(Collection.id == collection_id)
    )
    collection = result.scalar_one_or_none()

    if not collection:
        raise NotFoundError("Collection", str(collection_id))

    entries = [
        CollectionEntryItem(
            id=str(ce.entry.id),
            title=ce.entry.title,
            year=ce.entry.year,
            sort_order=ce.sort_order,
        )
        for ce in sorted(collection.entries, key=lambda x: x.sort_order)
    ]

    return CollectionDetailResponse(
        id=str(collection.id),
        name=collection.name,
        description=collection.description,
        entry_count=len(entries),
        entries=entries,
    )


@router.post("/{collection_id}/entries/{entry_id}", status_code=201)
async def add_entry_to_collection(
    collection_id: UUID,
    entry_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Add an entry to a collection."""
    # Verify collection exists
    collection = await db.get(Collection, collection_id)
    if not collection:
        raise NotFoundError("Collection", str(collection_id))

    # Verify entry exists
    entry = await db.get(Entry, entry_id)
    if not entry:
        raise NotFoundError("Entry", str(entry_id))

    # Check if already in collection
    result = await db.execute(
        select(CollectionEntry).where(
            CollectionEntry.collection_id == collection_id,
            CollectionEntry.entry_id == entry_id,
        )
    )
    if result.scalar_one_or_none():
        raise ConflictError("Entry already in collection")

    # Get max sort order
    result = await db.execute(
        select(CollectionEntry.sort_order)
        .where(CollectionEntry.collection_id == collection_id)
        .order_by(CollectionEntry.sort_order.desc())
        .limit(1)
    )
    max_order = result.scalar() or 0

    ce = CollectionEntry(
        collection_id=collection_id,
        entry_id=entry_id,
        sort_order=max_order + 1,
    )
    db.add(ce)
    await db.commit()

    logger.info("Added entry %s to collection %s", entry.citation_key, collection.name)
    return {"status": "added"}


@router.delete("/{collection_id}/entries/{entry_id}")
async def remove_entry_from_collection(
    collection_id: UUID,
    entry_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Remove an entry from a collection."""
    result = await db.execute(
        select(CollectionEntry).where(
            CollectionEntry.collection_id == collection_id,
            CollectionEntry.entry_id == entry_id,
        )
    )
    ce = result.scalar_one_or_none()

    if not ce:
        raise NotFoundError("Entry in collection")

    await db.delete(ce)
    await db.commit()

    logger.info("Removed entry from collection")
    return {"status": "removed"}


@router.delete("/{collection_id}")
async def delete_collection(
    collection_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Delete a collection."""
    collection = await db.get(Collection, collection_id)
    if not collection:
        raise NotFoundError("Collection", str(collection_id))

    name = collection.name
    await db.delete(collection)
    await db.commit()

    logger.info("Deleted collection: %s", name)
    return {"status": "deleted"}
