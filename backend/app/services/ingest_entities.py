"""
Entity preloading and relationship rebuilding for ingest.
"""

from dataclasses import dataclass, field
from typing import TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    Author,
    Entry,
    EntryAuthor,
    EntryTopic,
    Subject,
    Topic,
    Venue,
    VenueCategory,
)
from app.services.parser import (
    get_venue_info,
    normalize_name,
    parse_subject_name,
)

EntityWithSlug = TypeVar("EntityWithSlug", Venue, Subject, Topic)


@dataclass(slots=True)
class IngestBatchContext:
    """Preloaded entities for a batch ingest run."""

    authors_by_normalized: dict[str, Author] = field(default_factory=dict)
    venues_by_slug: dict[str, Venue] = field(default_factory=dict)
    subjects_by_slug: dict[str, Subject] = field(default_factory=dict)
    topics_by_slug: dict[str, Topic] = field(default_factory=dict)
    entries_by_citation_key: dict[str, Entry] = field(default_factory=dict)


def _unique_nonempty(values: list[str | None]) -> list[str]:
    return sorted({value for value in values if value})


def _unique_author_names(entries_data: list[dict]) -> list[str]:
    names: dict[str, str] = {}
    for entry_data in entries_data:
        for author_name in entry_data.get("authors", []):
            normalized = normalize_name(author_name)
            names.setdefault(normalized, author_name)
    return list(names.values())


def _build_subject(slug: str) -> Subject:
    parent, subarea, display_name = parse_subject_name(slug)
    parent_slug = parent.lower().replace(" ", "-")
    name = f"{parent}: {subarea}" if subarea else parent
    return Subject(
        slug=slug,
        name=name,
        parent_slug=parent_slug,
        display_name=display_name,
    )


def _build_topic(slug: str) -> Topic:
    return Topic(slug=slug, name=slug.replace("-", " ").replace("_", " ").title())


def _build_venue(slug: str) -> Venue | None:
    venue_info = get_venue_info(slug)
    if venue_info is None:
        return None
    name, category, aliases = venue_info
    return Venue(
        slug=slug,
        name=name,
        category=VenueCategory(category),
        aliases=aliases,
    )


async def _load_authors(
    session: AsyncSession,
    author_names: list[str],
) -> dict[str, Author]:
    if not author_names:
        return {}

    normalized_to_original = {
        normalize_name(author_name): author_name for author_name in author_names
    }
    result = await session.execute(
        select(Author).where(Author.normalized.in_(list(normalized_to_original)))
    )
    authors_by_normalized = {
        author.normalized: author for author in result.scalars().all()
    }

    missing = [
        normalized
        for normalized in normalized_to_original
        if normalized not in authors_by_normalized
    ]
    for normalized in missing:
        author = Author(
            name=normalized_to_original[normalized],
            normalized=normalized,
        )
        session.add(author)
        authors_by_normalized[normalized] = author

    if missing:
        await session.flush()
    return authors_by_normalized


async def _load_entities_by_slug(
    session: AsyncSession,
    model: type[EntityWithSlug],
    slugs: list[str],
) -> dict[str, EntityWithSlug]:
    if not slugs:
        return {}
    result = await session.execute(select(model).where(model.slug.in_(slugs)))
    return {entity.slug: entity for entity in result.scalars().all()}


async def _load_or_create_entities(
    session: AsyncSession,
    model: type[EntityWithSlug],
    slugs: list[str],
    *,
    factory,
) -> dict[str, EntityWithSlug]:
    entities_by_slug = await _load_entities_by_slug(session, model, slugs)
    created = False
    for slug in slugs:
        if slug in entities_by_slug:
            continue
        entity = factory(slug)
        if entity is None:
            continue
        session.add(entity)
        entities_by_slug[slug] = entity
        created = True
    if created:
        await session.flush()
    return entities_by_slug


async def _load_existing_entries(
    session: AsyncSession,
    citation_keys: list[str],
) -> dict[str, Entry]:
    if not citation_keys:
        return {}

    result = await session.execute(
        select(Entry)
        .where(Entry.citation_key.in_(citation_keys))
        .options(
            selectinload(Entry.authors).selectinload(EntryAuthor.author),
            selectinload(Entry.topics).selectinload(EntryTopic.topic),
            selectinload(Entry.venue),
            selectinload(Entry.subject),
        )
    )
    return {entry.citation_key: entry for entry in result.scalars().all()}


async def build_ingest_context(
    session: AsyncSession,
    entries_data: list[dict],
) -> IngestBatchContext:
    """Preload and create related entities for a batch of BibTeX entries."""
    citation_keys = _unique_nonempty(
        [entry_data.get("citation_key") for entry_data in entries_data]
    )
    venue_slugs = _unique_nonempty(
        [entry_data.get("venue_slug") for entry_data in entries_data]
    )
    subject_slugs = _unique_nonempty(
        [entry_data.get("subject") for entry_data in entries_data]
    )
    topic_slugs = _unique_nonempty(
        [
            topic_slug
            for entry_data in entries_data
            for topic_slug in entry_data.get("topics", [])
        ]
    )
    author_names = _unique_author_names(entries_data)

    return IngestBatchContext(
        authors_by_normalized=await _load_authors(session, author_names),
        venues_by_slug=await _load_or_create_entities(
            session,
            Venue,
            venue_slugs,
            factory=_build_venue,
        ),
        subjects_by_slug=await _load_or_create_entities(
            session,
            Subject,
            subject_slugs,
            factory=_build_subject,
        ),
        topics_by_slug=await _load_or_create_entities(
            session,
            Topic,
            topic_slugs,
            factory=_build_topic,
        ),
        entries_by_citation_key=await _load_existing_entries(session, citation_keys),
    )


def apply_entry_fields(
    entry: Entry,
    entry_data: dict,
    context: IngestBatchContext,
    *,
    created: bool,
) -> None:
    """Apply parsed BibTeX fields onto an ORM entry."""
    source_role = entry_data.get("source_role", "canonical")
    if not created and source_role != "canonical":
        return

    entry.entry_type = entry_data["entry_type"]
    entry.title = entry_data["title"]
    entry.year = entry_data["year"]
    entry.file_path = entry_data["file_path"]
    entry.required_fields = entry_data["required_fields"]
    entry.optional_fields = entry_data["optional_fields"]
    entry.source_file = entry_data["source_file"]
    entry.venue = context.venues_by_slug.get(entry_data.get("venue_slug"))
    entry.subject = context.subjects_by_slug.get(entry_data.get("subject"))


def rebuild_author_links(
    entry: Entry,
    entry_data: dict,
    context: IngestBatchContext,
    *,
    created: bool,
) -> None:
    """Rebuild author relations from parsed author order."""
    source_role = entry_data.get("source_role", "canonical")
    if not created and source_role != "canonical":
        return

    entry.authors.clear()

    seen_authors: set[str] = set()
    for position, author_name in enumerate(entry_data.get("authors", [])):
        normalized = normalize_name(author_name)
        if normalized in seen_authors:
            continue
        seen_authors.add(normalized)

        author = context.authors_by_normalized.get(normalized)
        if author is None:
            continue

        entry.authors.append(
            EntryAuthor(
                author=author,
                position=position,
            )
        )


def sync_topic_links(
    entry: Entry,
    entry_data: dict,
    context: IngestBatchContext,
    *,
    created: bool,
) -> None:
    """Apply curated topic links without clobbering canonical entry state."""
    source_role = entry_data.get("source_role", "canonical")
    if source_role != "curated":
        return

    if created:
        entry.topics.clear()

    existing_topics = {
        entry_topic.topic.slug for entry_topic in entry.topics if entry_topic.topic
    }
    for topic_slug in entry_data.get("topics", []):
        if topic_slug in existing_topics:
            continue

        topic = context.topics_by_slug.get(topic_slug)
        if topic is None:
            continue

        entry.topics.append(EntryTopic(topic=topic))
        existing_topics.add(topic_slug)
