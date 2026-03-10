"""
Schemas for collection APIs.
"""

from pydantic import BaseModel


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
