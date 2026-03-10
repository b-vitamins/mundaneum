"""
Parse/import/sync pipeline for BibTeX ingest.
"""

from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.logging import get_logger
from app.models import Entry
from app.services.domain_events import DomainEventBus, EntriesChanged
from app.services.ingest_entities import (
    apply_entry_fields,
    build_ingest_context,
    rebuild_author_links,
    rebuild_topic_links,
)
from app.services.parser import find_bib_files, parse_bib_file
from app.services.sync import (
    MeilisearchUnavailableError,
    SearchIndexService,
)

logger = get_logger(__name__)


@dataclass(slots=True)
class IngestResult:
    """Outcome for a file or directory ingest run."""

    imported_entries: list[Entry] = field(default_factory=list)
    imported_count: int = 0
    errors: int = 0
    total_parsed: int = 0

    def extend(self, other: "IngestResult") -> None:
        self.imported_entries.extend(other.imported_entries)
        self.imported_count += other.imported_count
        self.errors += other.errors
        self.total_parsed += other.total_parsed


async def ingest_entries_batch(
    session: AsyncSession,
    entries_data: list[dict],
) -> tuple[list[Entry], int]:
    """Ingest a batch of parsed entries with preloaded related entities."""
    context = await build_ingest_context(session, entries_data)
    imported: list[Entry] = []
    errors = 0

    for entry_data in entries_data:
        citation_key = entry_data.get("citation_key")
        if not citation_key:
            logger.warning("Skipping entry without citation_key")
            errors += 1
            continue

        try:
            async with session.begin_nested():
                entry = context.entries_by_citation_key.get(citation_key)
                if entry is None:
                    entry = Entry(
                        citation_key=citation_key,
                        entry_type=entry_data["entry_type"],
                        title=entry_data["title"],
                        source_file=entry_data["source_file"],
                    )
                    session.add(entry)
                    context.entries_by_citation_key[citation_key] = entry

                apply_entry_fields(entry, entry_data, context)
                rebuild_author_links(entry, entry_data, context)
                rebuild_topic_links(entry, entry_data, context)
                await session.flush()
                imported.append(entry)
        except IntegrityError as exc:
            logger.warning("Integrity error for %s: %s", citation_key, exc)
            errors += 1
        except Exception as exc:
            logger.error("Error importing %s: %s", citation_key, exc)
            errors += 1

    return imported, errors


async def sync_imported_entries(
    entries: list[Entry],
    search_index: SearchIndexService | None = None,
    event_bus: DomainEventBus | None = None,
) -> None:
    """Publish imported entry changes for downstream projections."""
    if not entries:
        return

    if event_bus is not None:
        await event_bus.publish(
            EntriesChanged(entry_ids=tuple(str(entry.id) for entry in entries))
        )
        return

    if search_index is None:
        return

    try:
        search_index.sync_entries(entries)
    except MeilisearchUnavailableError:
        logger.warning("Could not sync to Meilisearch (unavailable)")
    except Exception as exc:
        logger.warning("Could not sync to Meilisearch: %s", exc)


def ensure_search_index_ready(search_index: SearchIndexService | None = None) -> None:
    """Best-effort Meilisearch bootstrap shared by all ingest entry points."""
    if search_index is None:
        return
    try:
        search_index.ensure_index()
    except MeilisearchUnavailableError:
        logger.warning("Meilisearch unavailable, import will skip indexing")
    except Exception as exc:
        logger.warning("Could not configure Meilisearch: %s", exc)


async def ingest_parsed_entries(
    session: AsyncSession,
    entries_data: list[dict],
    *,
    batch_size: int = 100,
    commit: bool = True,
    sync_search: bool = True,
    search_index: SearchIndexService | None = None,
    event_bus: DomainEventBus | None = None,
) -> IngestResult:
    """Ingest parsed entries through one shared batching and sync pipeline."""
    result = IngestResult(total_parsed=len(entries_data))

    for index in range(0, len(entries_data), batch_size):
        batch = entries_data[index : index + batch_size]
        batch_imported, batch_errors = await ingest_entries_batch(session, batch)
        result.errors += batch_errors

        try:
            if commit:
                await session.commit()
        except Exception as exc:
            logger.error("Batch commit failed: %s", exc)
            await session.rollback()
            result.errors += len(batch_imported)
            continue

        result.imported_entries.extend(batch_imported)
        result.imported_count += len(batch_imported)

    if sync_search:
        await sync_imported_entries(
            result.imported_entries,
            search_index,
            event_bus,
        )

    return result


async def ingest_bib_file(
    session: AsyncSession,
    bib_path: Path,
    *,
    batch_size: int = 100,
    sync_search: bool = True,
    search_index: SearchIndexService | None = None,
    event_bus: DomainEventBus | None = None,
) -> IngestResult:
    """Parse and ingest one bibliography file using the shared pipeline."""
    entries_data = parse_bib_file(bib_path)
    if not entries_data:
        return IngestResult()
    return await ingest_parsed_entries(
        session,
        entries_data,
        batch_size=batch_size,
        commit=True,
        sync_search=sync_search,
        search_index=search_index,
        event_bus=event_bus,
    )


async def ingest_entry(session: AsyncSession, entry_data: dict) -> Entry | None:
    """Import a single entry into the database."""
    imported, _ = await ingest_entries_batch(session, [entry_data])
    return imported[0] if imported else None


async def ingest_directory(
    session: AsyncSession,
    directory: str | Path,
    *,
    search_index: SearchIndexService | None = None,
    event_bus: DomainEventBus | None = None,
) -> dict:
    """Import all `.bib` files from a directory and return aggregate stats."""
    directory = Path(directory)

    if not directory.exists():
        logger.error("Directory does not exist: %s", directory)
        return {"imported": 0, "errors": 0, "total_parsed": 0}

    if not directory.is_dir():
        logger.error("Path is not a directory: %s", directory)
        return {"imported": 0, "errors": 0, "total_parsed": 0}

    bib_files = list(find_bib_files(directory))
    if not bib_files:
        logger.warning("No bibliography files found in %s", directory)
        return {"imported": 0, "errors": 0, "total_parsed": 0}

    logger.info("Scanning directory: %s (%d files)", directory, len(bib_files))
    ensure_search_index_ready(search_index)

    result = IngestResult()
    for bib_path in bib_files:
        file_result = await ingest_bib_file(
            session,
            bib_path,
            search_index=search_index,
            event_bus=event_bus,
        )
        result.extend(file_result)
        logger.info(
            "Parsed %d entries from %s",
            file_result.total_parsed,
            bib_path.name,
        )

    logger.info(
        "Import complete: %d imported, %d errors, %d total",
        result.imported_count,
        result.errors,
        result.total_parsed,
    )

    return {
        "imported": result.imported_count,
        "errors": result.errors,
        "total_parsed": result.total_parsed,
    }
