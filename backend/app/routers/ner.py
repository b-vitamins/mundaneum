"""
NER entity API router.
"""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database import get_db
from app.exceptions import ValidationError
from app.modeling.library_models import Entry, EntryAuthor
from app.modeling.ner_models import EntryNerEntity, NerEntity
from app.routers.entity_common import (
    apply_sort,
    entry_authors,
    entry_venue,
    fetch_scalar_or_404,
    paginate,
)
from app.schemas.ner import (
    EntryNerFact,
    NerEntityDetail,
    NerEntityEntryItem,
    NerEntityLabelStat,
    NerEntityListItem,
    NerIngestResponse,
)
from app.services.ner_ingest import ingest_ner_release, resolve_signals_release_dir

router = APIRouter(prefix="/ner", tags=["ner"])


def _resolve_release_dir(directory: str | None) -> Path:
    """Resolve an ingest target; supports root signals directory autoselection."""
    try:
        return resolve_signals_release_dir(Path(directory or settings.ner_signals_path))
    except (FileNotFoundError, NotADirectoryError, ValueError) as exc:
        raise ValidationError(str(exc)) from exc


@router.get("/entities", response_model=list[NerEntityListItem])
async def list_entities(
    db: AsyncSession = Depends(get_db),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    sort_by: str = Query("paper_hits"),
    sort_order: str = Query("desc"),
    label: str | None = Query(None),
) -> list[NerEntityListItem]:
    """List canonical NER entities with optional label filter."""
    query = select(NerEntity)
    if label:
        query = query.where(NerEntity.label == label)

    query = apply_sort(
        query,
        sort_by=sort_by,
        sort_order=sort_order,
        sort_columns={
            "paper_hits": NerEntity.paper_hits,
            "name": NerEntity.canonical_surface,
            "years_active": NerEntity.years_active,
            "label": NerEntity.label,
        },
    )
    query = paginate(query, limit=limit, offset=offset, max_limit=500)

    entities = (await db.execute(query)).scalars().all()
    return [
        NerEntityListItem(
            canonical_id=entity.canonical_id,
            canonical_surface=entity.canonical_surface,
            label=entity.label,
            paper_hits=entity.paper_hits,
            years_active=entity.years_active,
        )
        for entity in entities
    ]


@router.get("/labels", response_model=list[NerEntityLabelStat])
async def list_entity_labels(
    db: AsyncSession = Depends(get_db),
) -> list[NerEntityLabelStat]:
    """List entity-label aggregates for UI filters."""
    rows = (
        await db.execute(
            select(
                NerEntity.label,
                func.count(NerEntity.id),
                func.sum(NerEntity.paper_hits),
            )
            .group_by(NerEntity.label)
            .order_by(func.sum(NerEntity.paper_hits).desc(), NerEntity.label.asc())
        )
    ).all()
    return [
        NerEntityLabelStat(
            label=label,
            entities=int(entity_count or 0),
            paper_hits=int(paper_hits or 0),
        )
        for label, entity_count, paper_hits in rows
    ]


@router.get("/entities/{canonical_id}", response_model=NerEntityDetail)
async def get_entity(
    canonical_id: str,
    db: AsyncSession = Depends(get_db),
) -> NerEntityDetail:
    """Get details for a single NER entity."""
    entity = await fetch_scalar_or_404(
        db,
        select(NerEntity).where(NerEntity.canonical_id == canonical_id),
        detail="Entity not found",
    )
    return NerEntityDetail(
        canonical_id=entity.canonical_id,
        canonical_surface=entity.canonical_surface,
        label=entity.label,
        first_year=entity.first_year,
        last_year=entity.last_year,
        paper_hits=entity.paper_hits,
        mention_total=entity.mention_total,
        venue_count=entity.venue_count,
        venues=entity.venues or [],
        years_active=entity.years_active,
    )


@router.get("/entities/{canonical_id}/entries", response_model=list[NerEntityEntryItem])
async def get_entity_entries(
    canonical_id: str,
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    sort_by: str = Query("year"),
    sort_order: str = Query("desc"),
) -> list[NerEntityEntryItem]:
    """List papers that mention a specific NER entity."""
    entity_id = await fetch_scalar_or_404(
        db,
        select(NerEntity.id).where(NerEntity.canonical_id == canonical_id),
        detail="Entity not found",
    )

    query = (
        select(Entry, EntryNerEntity.confidence, EntryNerEntity.mention_count)
        .join(EntryNerEntity, EntryNerEntity.entry_id == Entry.id)
        .where(EntryNerEntity.ner_entity_id == entity_id)
        .options(
            selectinload(Entry.authors).selectinload(EntryAuthor.author),
            selectinload(Entry.venue),
        )
    )
    query = apply_sort(
        query,
        sort_by=sort_by,
        sort_order=sort_order,
        sort_columns={
            "year": Entry.year,
            "title": Entry.title,
            "created_at": Entry.created_at,
        },
    )
    query = paginate(query, limit=limit, offset=offset, max_limit=200)

    rows = (await db.execute(query)).unique().all()
    return [
        NerEntityEntryItem(
            id=str(entry.id),
            citation_key=entry.citation_key,
            title=entry.title,
            year=entry.year,
            authors=entry_authors(entry),
            venue=entry_venue(entry),
            confidence=confidence,
            mention_count=mention_count,
        )
        for entry, confidence, mention_count in rows
    ]


@router.get("/entries/{entry_id}", response_model=list[EntryNerFact])
async def get_entry_entities(
    entry_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> list[EntryNerFact]:
    """List all NER entities extracted from a specific paper."""
    query = (
        select(NerEntity, EntryNerEntity.confidence, EntryNerEntity.mention_count)
        .join(EntryNerEntity, EntryNerEntity.ner_entity_id == NerEntity.id)
        .where(EntryNerEntity.entry_id == entry_id)
        .order_by(EntryNerEntity.confidence.desc(), NerEntity.canonical_surface.asc())
    )
    rows = (await db.execute(query)).all()
    return [
        EntryNerFact(
            canonical_id=entity.canonical_id,
            canonical_surface=entity.canonical_surface,
            label=entity.label,
            confidence=confidence,
            mention_count=mention_count,
        )
        for entity, confidence, mention_count in rows
    ]


@router.post("/ingest", response_model=NerIngestResponse)
async def trigger_ner_ingest(
    directory: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> NerIngestResponse:
    """Ingest a NER signals-product release directory."""
    release_dir = _resolve_release_dir(directory)
    if not (release_dir / "manifest.json").exists():
        raise ValidationError(f"manifest.json not found in {release_dir}")

    result = await ingest_ner_release(db, release_dir)
    return NerIngestResponse(**result)
