"""
Import service for Folio.

Handles importing BibTeX entries into the database.
"""

from pathlib import Path

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.logging import get_logger
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
    scan_directory,
)
from app.services.sync import (
    MeilisearchUnavailableError,
    ensure_index,
    sync_entries,
)

logger = get_logger(__name__)


async def get_or_create_author(session: AsyncSession, name: str) -> Author:
    """Get existing author or create new one."""
    normalized = normalize_name(name)

    result = await session.execute(
        select(Author).where(Author.normalized == normalized)
    )
    author = result.scalar_one_or_none()

    if not author:
        author = Author(name=name, normalized=normalized)
        session.add(author)
        await session.flush()

    return author


async def get_or_create_venue(session: AsyncSession, slug: str) -> Venue | None:
    """Get existing venue or create from known venues data."""
    if not slug:
        return None

    result = await session.execute(select(Venue).where(Venue.slug == slug))
    venue = result.scalar_one_or_none()

    if not venue:
        venue_info = get_venue_info(slug)
        if venue_info:
            name, category, aliases = venue_info
            venue = Venue(
                slug=slug,
                name=name,
                category=VenueCategory(category),
                aliases=aliases,
            )
            session.add(venue)
            await session.flush()
        else:
            return None

    return venue


async def get_or_create_subject(session: AsyncSession, slug: str) -> Subject | None:
    """Get existing subject or create new one."""
    if not slug:
        return None

    result = await session.execute(select(Subject).where(Subject.slug == slug))
    subject = result.scalar_one_or_none()

    if not subject:
        # Derive display name from slug
        name = slug.replace("-", " ").replace("_", " ").title()
        subject = Subject(slug=slug, name=name)
        session.add(subject)
        await session.flush()

    return subject


async def get_or_create_topic(session: AsyncSession, slug: str) -> Topic | None:
    """Get existing topic or create new one."""
    if not slug:
        return None

    result = await session.execute(select(Topic).where(Topic.slug == slug))
    topic = result.scalar_one_or_none()

    if not topic:
        # Derive display name from slug
        name = slug.replace("-", " ").replace("_", " ").title()
        topic = Topic(slug=slug, name=name)
        session.add(topic)
        await session.flush()

    return topic


async def ingest_entry(session: AsyncSession, entry_data: dict) -> Entry | None:
    """
    Import a single entry into the database.

    Upserts by citation_key: updates if exists, creates if new.
    Returns None if import fails.
    """
    citation_key = entry_data.get("citation_key")
    if not citation_key:
        logger.warning("Skipping entry without citation_key")
        return None

    # Get/create related entities
    venue = await get_or_create_venue(session, entry_data.get("venue_slug"))
    subject = await get_or_create_subject(session, entry_data.get("subject"))

    # Check if entry already exists
    result = await session.execute(
        select(Entry).where(Entry.citation_key == citation_key)
    )
    existing = result.scalar_one_or_none()

    if existing:
        # Update existing entry
        existing.entry_type = entry_data["entry_type"]
        existing.title = entry_data["title"]
        existing.year = entry_data["year"]
        existing.file_path = entry_data["file_path"]
        existing.required_fields = entry_data["required_fields"]
        existing.optional_fields = entry_data["optional_fields"]
        existing.source_file = entry_data["source_file"]
        existing.venue_id = venue.id if venue else None
        existing.subject_id = subject.id if subject else None

        # Clear existing authors and topics
        await session.execute(
            EntryAuthor.__table__.delete().where(EntryAuthor.entry_id == existing.id)
        )
        await session.execute(
            EntryTopic.__table__.delete().where(EntryTopic.entry_id == existing.id)
        )
        entry = existing
    else:
        # Create new entry
        entry = Entry(
            citation_key=citation_key,
            entry_type=entry_data["entry_type"],
            title=entry_data["title"],
            year=entry_data["year"],
            file_path=entry_data["file_path"],
            required_fields=entry_data["required_fields"],
            optional_fields=entry_data["optional_fields"],
            source_file=entry_data["source_file"],
            venue_id=venue.id if venue else None,
            subject_id=subject.id if subject else None,
        )
        session.add(entry)
        await session.flush()

    # Add authors (deduplicate by normalized name within this entry)
    seen_authors = set()
    for position, author_name in enumerate(entry_data.get("authors", [])):
        normalized = normalize_name(author_name)
        if normalized in seen_authors:
            continue  # Skip duplicate authors within same entry
        seen_authors.add(normalized)

        author = await get_or_create_author(session, author_name)

        # Check if relationship already exists
        existing_rel = await session.execute(
            select(EntryAuthor).where(
                EntryAuthor.entry_id == entry.id,
                EntryAuthor.author_id == author.id,
            )
        )
        if existing_rel.scalar_one_or_none():
            continue

        entry_author = EntryAuthor(
            entry_id=entry.id,
            author_id=author.id,
            position=position,
        )
        session.add(entry_author)

    # Add topics (many-to-many)
    for topic_slug in entry_data.get("topics", []):
        topic = await get_or_create_topic(session, topic_slug)
        if topic:
            # Check if relationship already exists
            existing_rel = await session.execute(
                select(EntryTopic).where(
                    EntryTopic.entry_id == entry.id,
                    EntryTopic.topic_id == topic.id,
                )
            )
            if existing_rel.scalar_one_or_none():
                continue

            entry_topic = EntryTopic(entry_id=entry.id, topic_id=topic.id)
            session.add(entry_topic)

    return entry


async def ingest_directory(session: AsyncSession, directory: str | Path) -> dict:
    """
    Import all .bib files from a directory into the database.

    Returns import statistics.
    """
    directory = Path(directory)

    if not directory.exists():
        logger.error("Directory does not exist: %s", directory)
        return {"imported": 0, "errors": 0, "total_parsed": 0}

    if not directory.is_dir():
        logger.error("Path is not a directory: %s", directory)
        return {"imported": 0, "errors": 0, "total_parsed": 0}

    # Parse all .bib files
    logger.info("Scanning directory: %s", directory)
    entries_data = scan_directory(directory)

    if not entries_data:
        logger.warning("No entries found in %s", directory)
        return {"imported": 0, "errors": 0, "total_parsed": 0}

    # Ensure Meilisearch index exists
    try:
        ensure_index()
    except MeilisearchUnavailableError:
        logger.warning("Meilisearch unavailable, import will skip indexing")
    except Exception as e:
        logger.warning("Could not configure Meilisearch: %s", e)

    imported = []
    errors = 0

    # Process in batches for memory efficiency
    batch_size = 100
    for i in range(0, len(entries_data), batch_size):
        batch = entries_data[i : i + batch_size]

        for entry_data in batch:
            try:
                entry = await ingest_entry(session, entry_data)
                if entry:
                    imported.append(entry)
            except IntegrityError as e:
                logger.warning(
                    "Integrity error for %s: %s", entry_data.get("citation_key"), e
                )
                await session.rollback()
                errors += 1
            except Exception as e:
                logger.error(
                    "Error importing %s: %s", entry_data.get("citation_key"), e
                )
                errors += 1

        # Commit after each batch
        try:
            await session.commit()
        except Exception as e:
            logger.error("Batch commit failed: %s", e)
            await session.rollback()
            errors += len(batch)
            imported = [e for e in imported if e not in batch]

    # Sync to Meilisearch
    if imported:
        try:
            # Re-fetch entries with eager loading to ensure relationships are available
            # for the sync function which accesses them synchronously
            from sqlalchemy.orm import selectinload

            stmt = (
                select(Entry)
                .options(selectinload(Entry.authors).selectinload(EntryAuthor.author))
                .where(Entry.id.in_([e.id for e in imported]))
            )
            result = await session.execute(stmt)
            entries_to_sync = result.scalars().all()

            sync_entries(entries_to_sync)
        except MeilisearchUnavailableError:
            logger.warning("Could not sync to Meilisearch (unavailable)")
        except Exception as e:
            logger.warning("Could not sync to Meilisearch: %s", e)

    logger.info(
        "Import complete: %d imported, %d errors, %d total",
        len(imported),
        errors,
        len(entries_data),
    )

    return {
        "imported": len(imported),
        "errors": errors,
        "total_parsed": len(entries_data),
    }
