"""
Collections router for Mundaneum API.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.collections import (
    CollectionCreate,
    CollectionDetailResponse,
    CollectionResponse,
)
from app.services.collection_mutations import (
    add_entry_to_collection as add_entry_to_collection_service,
)
from app.services.collection_mutations import (
    create_collection as create_collection_service,
)
from app.services.collection_mutations import (
    delete_collection as delete_collection_service,
)
from app.services.collection_mutations import (
    remove_entry_from_collection as remove_entry_from_collection_service,
)
from app.services.collection_queries import (
    get_collection_detail as get_collection_detail_service,
)
from app.services.collection_queries import (
    list_collections as list_collections_service,
)

router = APIRouter(prefix="/collections", tags=["collections"])


@router.get("", response_model=list[CollectionResponse])
async def list_collections(
    db: AsyncSession = Depends(get_db),
    limit: int = Query(100, ge=1, le=1000, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Results offset"),
):
    """List all collections."""
    return await list_collections_service(db, limit=limit, offset=offset)


@router.post("", response_model=CollectionResponse, status_code=201)
async def create_collection(
    data: CollectionCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new collection."""
    return await create_collection_service(db, data)


@router.get("/{collection_id}", response_model=CollectionDetailResponse)
async def get_collection(
    collection_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get collection with its entries."""
    return await get_collection_detail_service(db, collection_id)


@router.post("/{collection_id}/entries/{entry_id}", status_code=201)
async def add_entry_to_collection(
    collection_id: UUID,
    entry_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Add an entry to a collection."""
    return await add_entry_to_collection_service(
        db,
        collection_id=collection_id,
        entry_id=entry_id,
    )


@router.delete("/{collection_id}/entries/{entry_id}")
async def remove_entry_from_collection(
    collection_id: UUID,
    entry_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Remove an entry from a collection."""
    return await remove_entry_from_collection_service(
        db,
        collection_id=collection_id,
        entry_id=entry_id,
    )


@router.delete("/{collection_id}")
async def delete_collection(
    collection_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Delete a collection."""
    return await delete_collection_service(db, collection_id=collection_id)
