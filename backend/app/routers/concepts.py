"""
Concept graph API router: bundles and co-occurrence.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.modeling.concept_models import NerBundle, NerCooccurrenceEdge
from app.modeling.ner_models import NerEntity
from app.routers.entity_common import fetch_scalar_or_404, paginate
from app.schemas.concepts import (
    BundleDetail,
    BundleListItem,
    BundleTopEntity,
    CooccurrenceEdgeItem,
    EntityNeighbor,
)

router = APIRouter(prefix="/concepts", tags=["concepts"])


def _split_node_key(node_key: str) -> tuple[str | None, str | None]:
    """Split node keys like 'label|canonical_id' into parts."""
    if "|" not in node_key:
        return None, None
    label, canonical_id = node_key.split("|", 1)
    return label or None, canonical_id or None


def _growth_indicator(yearly: dict[str, int], lifecycle: str | None) -> str:
    """Derive growth trend from lifecycle or yearly paper counts."""
    if lifecycle in {"growing", "declining"}:
        return lifecycle
    if lifecycle == "stable" and not yearly:
        return "stable"

    years = sorted(yearly.keys())
    if len(years) < 2:
        return "stable"

    last = yearly.get(years[-1], 0)
    prev = yearly.get(years[-2], 0)
    if prev == 0:
        return "growing" if last > 0 else "stable"

    ratio = last / prev
    if ratio > 1.1:
        return "growing"
    if ratio < 0.9:
        return "declining"
    return "stable"


def _normalize_top_entity(item: dict) -> BundleTopEntity:
    node_key = item.get("node_key")
    _, canonical_id = _split_node_key(node_key) if isinstance(node_key, str) else (None, None)
    return BundleTopEntity(
        canonical_id=item.get("canonical_id") or canonical_id,
        canonical_surface=item.get("canonical_surface", ""),
        label=item.get("label", ""),
        node_key=node_key if isinstance(node_key, str) else None,
        paper_hits=int(item.get("paper_hits", 0)),
    )


def _matches_node_suffix(column, canonical_id: str):
    """Match node columns containing canonical IDs as suffixes."""
    suffix = f"|{canonical_id}"
    return column.endswith(suffix, autoescape=True) | (column == canonical_id)


@router.get("/bundles", response_model=list[BundleListItem])
async def list_bundles(
    db: AsyncSession = Depends(get_db),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> list[BundleListItem]:
    """List concept bundles."""
    query = select(NerBundle).order_by(NerBundle.size.desc(), NerBundle.bundle_index.asc())
    query = paginate(query, limit=limit, offset=offset, max_limit=500)

    result = await db.execute(query)
    bundles = result.scalars().all()

    return [
        BundleListItem(
            bundle_index=bundle.bundle_index,
            bundle_id=bundle.bundle_id,
            lifecycle=bundle.lifecycle,
            size=bundle.size,
            venue_count=bundle.venue_count,
            venue_coverage=bundle.venue_coverage or [],
            top_entities=[
                _normalize_top_entity(entity)
                for entity in (bundle.top_entities or [])[:5]
                if isinstance(entity, dict)
            ],
            growth_indicator=_growth_indicator(
                bundle.yearly_paper_counts or {},
                bundle.lifecycle,
            ),
        )
        for bundle in bundles
    ]


@router.get("/bundles/{bundle_index}", response_model=BundleDetail)
async def get_bundle(
    bundle_index: int,
    db: AsyncSession = Depends(get_db),
) -> BundleDetail:
    """Get full detail for a single concept bundle."""
    bundle = await fetch_scalar_or_404(
        db,
        select(NerBundle).where(NerBundle.bundle_index == bundle_index),
        detail="Bundle not found",
    )

    return BundleDetail(
        bundle_index=bundle.bundle_index,
        bundle_id=bundle.bundle_id,
        lifecycle=bundle.lifecycle,
        birth_year=bundle.birth_year,
        latest_year=bundle.latest_year,
        size=bundle.size,
        latest_year_papers=bundle.latest_year_papers,
        venue_count=bundle.venue_count,
        growth_rate=bundle.growth_rate,
        cohesion=bundle.cohesion,
        internal_edge_weight=bundle.internal_edge_weight,
        external_edge_weight=bundle.external_edge_weight,
        venue_coverage=bundle.venue_coverage or [],
        members=bundle.members or [],
        top_entities=[
            _normalize_top_entity(entity)
            for entity in (bundle.top_entities or [])
            if isinstance(entity, dict)
        ],
        yearly_paper_counts={
            str(year): int(count)
            for year, count in (bundle.yearly_paper_counts or {}).items()
        },
        previous_year_papers=bundle.previous_year_papers,
    )


@router.get("/neighbors/{canonical_id}", response_model=list[EntityNeighbor])
async def get_entity_neighbors(
    canonical_id: str,
    db: AsyncSession = Depends(get_db),
    limit: int = Query(20, ge=1, le=100),
    venue: str | None = Query(None),
    year: int | None = Query(None),
) -> list[EntityNeighbor]:
    """Get co-occurring entities ranked by co-occurrence paper count."""
    left_query = (
        select(
            NerCooccurrenceEdge.right_node,
            NerCooccurrenceEdge.right_label,
            func.sum(NerCooccurrenceEdge.paper_count).label("total_papers"),
        )
        .where(_matches_node_suffix(NerCooccurrenceEdge.left_node, canonical_id))
        .group_by(NerCooccurrenceEdge.right_node, NerCooccurrenceEdge.right_label)
    )
    right_query = (
        select(
            NerCooccurrenceEdge.left_node,
            NerCooccurrenceEdge.left_label,
            func.sum(NerCooccurrenceEdge.paper_count).label("total_papers"),
        )
        .where(_matches_node_suffix(NerCooccurrenceEdge.right_node, canonical_id))
        .group_by(NerCooccurrenceEdge.left_node, NerCooccurrenceEdge.left_label)
    )

    if venue:
        left_query = left_query.where(NerCooccurrenceEdge.venue == venue)
        right_query = right_query.where(NerCooccurrenceEdge.venue == venue)
    if year:
        left_query = left_query.where(NerCooccurrenceEdge.year == year)
        right_query = right_query.where(NerCooccurrenceEdge.year == year)

    left_result = await db.execute(left_query)
    right_result = await db.execute(right_query)

    neighbor_totals: dict[str, tuple[str, int]] = {}
    for node_key, label, papers in [*left_result.all(), *right_result.all()]:
        prev_label, prev_papers = neighbor_totals.get(node_key, (label, 0))
        neighbor_totals[node_key] = (prev_label or label, prev_papers + int(papers or 0))

    sorted_neighbors = sorted(
        neighbor_totals.items(),
        key=lambda item: item[1][1],
        reverse=True,
    )[:limit]

    canonical_ids = {
        canonical
        for node_key, _ in sorted_neighbors
        for _, canonical in [_split_node_key(node_key)]
        if canonical is not None
    }
    entity_surface_map: dict[str, str] = {}
    if canonical_ids:
        surface_rows = await db.execute(
            select(NerEntity.canonical_id, NerEntity.canonical_surface).where(
                NerEntity.canonical_id.in_(canonical_ids)
            )
        )
        entity_surface_map = {row[0]: row[1] for row in surface_rows.all()}

    items: list[EntityNeighbor] = []
    for node_key, (fallback_label, paper_count) in sorted_neighbors:
        parsed_label, parsed_canonical_id = _split_node_key(node_key)
        canonical_neighbor_id = parsed_canonical_id or node_key
        items.append(
            EntityNeighbor(
                canonical_id=canonical_neighbor_id,
                canonical_surface=entity_surface_map.get(
                    canonical_neighbor_id,
                    canonical_neighbor_id,
                ),
                label=parsed_label or fallback_label or "",
                paper_count=paper_count,
            )
        )
    return items


@router.get("/edges", response_model=list[CooccurrenceEdgeItem])
async def get_cooccurrence_edges(
    db: AsyncSession = Depends(get_db),
    canonical_id: str | None = Query(None),
    venue: str | None = Query(None),
    year: int | None = Query(None),
    min_paper_count: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> list[CooccurrenceEdgeItem]:
    """Get co-occurrence edges, optionally filtered by entity, venue, and year."""
    query = select(NerCooccurrenceEdge)

    if canonical_id:
        query = query.where(
            _matches_node_suffix(NerCooccurrenceEdge.left_node, canonical_id)
            | _matches_node_suffix(NerCooccurrenceEdge.right_node, canonical_id)
        )
    if venue:
        query = query.where(NerCooccurrenceEdge.venue == venue)
    if year:
        query = query.where(NerCooccurrenceEdge.year == year)
    if min_paper_count > 1:
        query = query.where(NerCooccurrenceEdge.paper_count >= min_paper_count)

    query = query.order_by(NerCooccurrenceEdge.paper_count.desc())
    query = paginate(query, limit=limit, offset=offset, max_limit=500)

    rows = (await db.execute(query)).scalars().all()

    return [
        CooccurrenceEdgeItem(
            left_node=edge.left_node,
            left_canonical_id=_split_node_key(edge.left_node)[1],
            left_label=edge.left_label,
            right_node=edge.right_node,
            right_canonical_id=_split_node_key(edge.right_node)[1],
            right_label=edge.right_label,
            paper_count=edge.paper_count,
            venue=edge.venue,
            year=edge.year,
        )
        for edge in rows
    ]
