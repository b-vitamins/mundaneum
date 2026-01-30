"""
Import service for Folio.

Handles importing BibTeX entries into the database.
"""

from pathlib import Path

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.logging import get_logger
from app.models import Author, Entry, EntryAuthor
from app.services.parser import normalize_name, scan_directory
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

        # Clear existing authors
        await session.execute(
            EntryAuthor.__table__.delete().where(EntryAuthor.entry_id == existing.id)
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
