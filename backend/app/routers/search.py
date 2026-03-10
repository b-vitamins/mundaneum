"""
Search router for Mundaneum API.
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import EntryType
from app.schemas.search import SearchFilters, SearchQuery, SearchResponse
from app.services.search_service import search_entries as execute_search

router = APIRouter(prefix="", tags=["search"])


@router.get("", response_model=SearchResponse)
async def search_entries(
    db: AsyncSession = Depends(get_db),
    q: Optional[str] = Query(None, description="Search query"),
    entry_type: EntryType | None = Query(None, description="Filter by entry type"),
    year_from: Optional[int] = Query(None, description="Minimum year"),
    year_to: Optional[int] = Query(None, description="Maximum year"),
    has_pdf: Optional[bool] = Query(None, description="Has PDF attached"),
    read: Optional[bool] = Query(None, description="Read status"),
    sort: Optional[str] = Query(None, description="Sort order (e.g. 'year:desc')"),
    limit: int = Query(20, ge=1, le=100, description="Results per page"),
    offset: int = Query(0, ge=0, description="Results offset"),
):
    """Search entries with explicit degradation handling."""
    query = SearchQuery(
        query=q,
        filters=SearchFilters(
            entry_type=entry_type,
            year_from=year_from,
            year_to=year_to,
            has_pdf=has_pdf,
            read=read,
        ),
        limit=limit,
        offset=offset,
        sort=sort,
    )
    return await execute_search(db, query)
