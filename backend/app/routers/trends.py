"""
Trends API router for NER-derived signals.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.exceptions import NotFoundError
from app.modeling.trend_models import NerCrossVenueFlow, NerEmergence, NerTrend
from app.routers.entity_common import apply_sort, paginate
from app.schemas.trends import (
    CrossVenueFlowItem,
    EmergenceItem,
    TrendMoverItem,
    TrendPoint,
    TrendsDashboardStats,
    TrendSparkline,
)

router = APIRouter(prefix="/trends", tags=["trends"])


async def _ordered_distinct_strings(db: AsyncSession, column) -> list[str]:
    result = await db.execute(select(distinct(column)))
    return sorted([row[0] for row in result.all() if isinstance(row[0], str)])


@router.get("/stats", response_model=TrendsDashboardStats)
async def get_trends_stats(db: AsyncSession = Depends(get_db)) -> TrendsDashboardStats:
    """Summary stats for the trends dashboard header."""
    total_entities = (
        await db.scalar(select(func.count(distinct(NerTrend.canonical_id))))
    ) or 0
    total_trend_rows = (await db.scalar(select(func.count(NerTrend.id)))) or 0
    emerging_count = (await db.scalar(select(func.count(NerEmergence.id)))) or 0

    venues = await _ordered_distinct_strings(db, NerTrend.venue)
    labels = await _ordered_distinct_strings(db, NerTrend.label)

    year_min = await db.scalar(select(func.min(NerTrend.year)))
    year_max = await db.scalar(select(func.max(NerTrend.year)))
    year_range = [year_min, year_max] if year_min is not None and year_max is not None else []

    return TrendsDashboardStats(
        total_entities=total_entities,
        total_trend_rows=total_trend_rows,
        emerging_count=emerging_count,
        venues=venues,
        labels=labels,
        year_range=year_range,
    )


@router.get("/movers", response_model=list[TrendMoverItem])
async def get_movers(
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    sort_by: str = Query("momentum"),
    sort_order: str = Query("desc"),
    label: str | None = Query(None),
    venue: str | None = Query(None),
    year: int | None = Query(None),
    direction: str | None = Query(None),
) -> list[TrendMoverItem]:
    """Movers table: entities ranked by momentum, scoped to a specific year."""
    if year is None:
        year = await db.scalar(select(func.max(NerTrend.year)))
        if year is None:
            return []

    query = select(NerTrend).where(NerTrend.year == year)
    if label:
        query = query.where(NerTrend.label == label)
    if venue:
        query = query.where(NerTrend.venue == venue)
    if direction:
        query = query.where(NerTrend.change_direction == direction)

    query = apply_sort(
        query,
        sort_by=sort_by,
        sort_order=sort_order,
        sort_columns={
            "momentum": NerTrend.momentum,
            "prevalence": NerTrend.prevalence,
            "paper_hits": NerTrend.paper_hits,
            "name": NerTrend.canonical_surface,
            "prevalence_z": NerTrend.prevalence_z_by_year_label,
        },
    )
    query = paginate(query, limit=limit, offset=offset, max_limit=200)

    rows = (await db.execute(query)).scalars().all()
    return [
        TrendMoverItem(
            canonical_id=row.canonical_id,
            canonical_surface=row.canonical_surface,
            label=row.label,
            venue=row.venue,
            year=row.year,
            prevalence=row.prevalence,
            momentum=row.momentum,
            paper_hits=row.paper_hits,
            change_point=row.change_point,
            change_direction=row.change_direction,
            prevalence_z=row.prevalence_z_by_year_label,
        )
        for row in rows
    ]


@router.get("/sparkline/{canonical_id}", response_model=TrendSparkline)
async def get_sparkline(
    canonical_id: str,
    db: AsyncSession = Depends(get_db),
) -> TrendSparkline:
    """Get yearly prevalence and momentum points for one canonical entity."""
    query = (
        select(NerTrend)
        .where(NerTrend.canonical_id == canonical_id)
        .order_by(NerTrend.year.asc(), NerTrend.venue.asc())
    )
    rows = (await db.execute(query)).scalars().all()
    if not rows:
        raise NotFoundError("Trend data", canonical_id)

    return TrendSparkline(
        canonical_id=canonical_id,
        canonical_surface=rows[0].canonical_surface,
        label=rows[0].label,
        points=[
            TrendPoint(
                year=row.year,
                venue=row.venue,
                prevalence=row.prevalence,
                momentum=row.momentum,
                paper_hits=row.paper_hits,
            )
            for row in rows
        ],
    )


@router.get("/emergence", response_model=list[EmergenceItem])
async def get_emergence(
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    label: str | None = Query(None),
    venue: str | None = Query(None),
) -> list[EmergenceItem]:
    """Emergence watchlist: newly rising entities."""
    query = select(NerEmergence)
    if label:
        query = query.where(NerEmergence.label == label)
    if venue:
        query = query.where(NerEmergence.venue == venue)

    query = query.order_by(NerEmergence.emergence_score.desc())
    query = paginate(query, limit=limit, offset=offset, max_limit=200)

    rows = (await db.execute(query)).scalars().all()
    return [
        EmergenceItem(
            canonical_id=row.canonical_id,
            canonical_surface=row.canonical_surface,
            label=row.label,
            venue=row.venue,
            year=row.year,
            emergence_score=row.emergence_score,
            momentum=row.momentum,
            prevalence=row.prevalence,
            paper_hits=row.paper_hits,
        )
        for row in rows
    ]


@router.get("/flow", response_model=list[CrossVenueFlowItem])
async def get_cross_venue_flow(
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    label: str | None = Query(None),
    source_venue: str | None = Query(None),
    target_venue: str | None = Query(None),
    min_transfer_score: float = Query(0.0, ge=0.0),
) -> list[CrossVenueFlowItem]:
    """Cross-venue flow: entity transfer between venues."""
    query = select(NerCrossVenueFlow)
    if label:
        query = query.where(NerCrossVenueFlow.label == label)
    if source_venue:
        query = query.where(NerCrossVenueFlow.source_venue == source_venue)
    if target_venue:
        query = query.where(NerCrossVenueFlow.target_venue == target_venue)
    if min_transfer_score > 0:
        query = query.where(NerCrossVenueFlow.transfer_score >= min_transfer_score)

    query = query.order_by(NerCrossVenueFlow.transfer_score.desc())
    query = paginate(query, limit=limit, offset=offset, max_limit=200)

    rows = (await db.execute(query)).scalars().all()
    return [
        CrossVenueFlowItem(
            canonical_id=row.canonical_id,
            canonical_surface=row.canonical_surface,
            label=row.label,
            source_venue=row.source_venue,
            source_year=row.source_year,
            target_venue=row.target_venue,
            target_year=row.target_year,
            lag_years=row.lag_years,
            transfer_score=row.transfer_score,
        )
        for row in rows
    ]
