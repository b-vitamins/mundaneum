from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Entry, EntryAuthor, EntryTopic, Topic
from app.routers.entity_common import (
    apply_sort,
    entity_entry_payload,
    paginate,
)
from app.schemas.entities import TopicDetail, TopicEntryItem, TopicListItem

router = APIRouter(prefix="/topics", tags=["topics"])


@router.get("", response_model=list[TopicListItem])
async def list_topics(
    limit: int = 100,
    offset: int = 0,
    sort_by: str = "name",
    sort_order: str = "asc",
    db: AsyncSession = Depends(get_db),
) -> list[TopicListItem]:
    """
    List all topics with entry counts.
    """
    # Subquery for entry counts
    entry_count_subq = (
        select(
            EntryTopic.topic_id,
            func.count(EntryTopic.entry_id).label("entry_count"),
        )
        .group_by(EntryTopic.topic_id)
        .subquery()
    )

    # Main query
    query = select(
        Topic,
        func.coalesce(entry_count_subq.c.entry_count, 0).label("entry_count"),
    ).outerjoin(entry_count_subq, Topic.id == entry_count_subq.c.topic_id)

    query = apply_sort(
        query,
        sort_by=sort_by,
        sort_order=sort_order,
        sort_columns={
            "name": Topic.name,
            "entry_count": entry_count_subq.c.entry_count,
        },
    )
    query = paginate(query, limit=limit, offset=offset)

    result = await db.execute(query)
    rows = result.all()

    return [
        TopicListItem(
            id=str(row.Topic.id),
            slug=row.Topic.slug,
            name=row.Topic.name,
            entry_count=row.entry_count,
        )
        for row in rows
    ]


@router.get("/{slug}", response_model=TopicDetail)
async def get_topic(
    slug: str,
    db: AsyncSession = Depends(get_db),
) -> TopicDetail:
    """Get topic details by slug."""
    # First get the topic
    result = await db.execute(select(Topic).where(Topic.slug == slug))
    topic = result.scalar_one_or_none()

    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")

    # Get entry count
    entry_count = await db.scalar(
        select(func.count(EntryTopic.entry_id)).where(EntryTopic.topic_id == topic.id)
    )

    return TopicDetail(
        id=str(topic.id),
        slug=topic.slug,
        name=topic.name,
        entry_count=entry_count or 0,
    )


@router.get("/{slug}/entries", response_model=list[TopicEntryItem])
async def get_topic_entries(
    slug: str,
    limit: int = 50,
    offset: int = 0,
    sort_by: str = "year",
    sort_order: str = "desc",
    db: AsyncSession = Depends(get_db),
) -> list[TopicEntryItem]:
    """Get all entries in a specific topic."""
    # First check topic exists
    topic_check = await db.execute(select(Topic.id).where(Topic.slug == slug))
    topic_id = topic_check.scalar_one_or_none()
    if not topic_id:
        raise HTTPException(status_code=404, detail="Topic not found")

    # Get entries via join
    query = (
        select(Entry)
        .join(EntryTopic, Entry.id == EntryTopic.entry_id)
        .where(EntryTopic.topic_id == topic_id)
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
            "title": Entry.title,
            "created_at": Entry.created_at,
            "year": Entry.year,
        },
    )
    query = paginate(query, limit=limit, offset=offset)

    result = await db.execute(query)
    entries = result.scalars().all()

    return [TopicEntryItem(**entity_entry_payload(entry)) for entry in entries]
