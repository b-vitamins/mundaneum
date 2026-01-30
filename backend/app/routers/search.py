"""
Search router for Folio API.
"""

from typing import Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.services.sync import search as meili_search

router = APIRouter(prefix="", tags=["search"])


class SearchResponse(BaseModel):
    """Response model for search results."""

    hits: list[dict]
    total: int
    processing_time_ms: int


@router.get("", response_model=SearchResponse)
async def search_entries(
    q: Optional[str] = Query(None, description="Search query"),
    entry_type: Optional[str] = Query(None, description="Filter by entry type"),
    year_from: Optional[int] = Query(None, description="Minimum year"),
    year_to: Optional[int] = Query(None, description="Maximum year"),
    has_pdf: Optional[bool] = Query(None, description="Has PDF attached"),
    read: Optional[bool] = Query(None, description="Read status"),
    sort: Optional[str] = Query(None, description="Sort order (e.g. 'year:desc')"),
    limit: int = Query(20, ge=1, le=100, description="Results per page"),
    offset: int = Query(0, ge=0, description="Results offset"),
):
    """Search entries using Meilisearch."""
    filters = {}

    if entry_type:
        filters["entry_type"] = entry_type
    if year_from is not None and year_to is not None:
        filters["year"] = [year_from, year_to]
    if has_pdf is not None:
        filters["has_pdf"] = has_pdf
    if read is not None:
        filters["read"] = read

    return meili_search(q, filters, limit, offset, sort)
