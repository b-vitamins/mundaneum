"""
Background ingestion worker for Mundaneum.

Processes bibliography files in background, committing per-file
for immediate visibility in the UI.
"""

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.logging import get_logger
from app.services.parser import find_bib_files, parse_bib_file
from app.services.sync import MeilisearchUnavailableError, ensure_index, sync_entries


from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.models import Entry, EntryAuthor

logger = get_logger(__name__)


class WorkerStatus(str, Enum):
    """Status of the ingestion worker."""

    IDLE = "idle"
    RUNNING = "running"
    COMPLETE = "complete"
    ERROR = "error"


@dataclass
class IngestionProgress:
    """Progress tracking for ingestion."""

    status: WorkerStatus = WorkerStatus.IDLE
    files_total: int = 0
    files_done: int = 0
    entries_imported: int = 0
    entries_errors: int = 0
    current_file: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None


class IngestionWorker:
    """
    Background worker that processes bibliography files.

    Commits after each file for immediate visibility.
    """

    def __init__(self):
        self.progress = IngestionProgress()
        self._task: Optional[asyncio.Task] = None

    @property
    def is_running(self) -> bool:
        return self.progress.status == WorkerStatus.RUNNING

    def get_status(self) -> dict:
        """Get current worker status as dict."""
        return {
            "status": self.progress.status.value,
            "files_total": self.progress.files_total,
            "files_done": self.progress.files_done,
            "entries_imported": self.progress.entries_imported,
            "entries_errors": self.progress.entries_errors,
            "current_file": self.progress.current_file,
            "started_at": self.progress.started_at.isoformat()
            if self.progress.started_at
            else None,
            "completed_at": self.progress.completed_at.isoformat()
            if self.progress.completed_at
            else None,
            "error_message": self.progress.error_message,
        }

    async def start(self, directory: Path) -> None:
        """
        Start background ingestion from directory.

        This is the main entry point - call this from app lifespan.
        """
        if self.is_running:
            logger.warning("Ingestion already running, ignoring start request")
            return

        self._task = asyncio.create_task(self._run(directory))

    async def stop(self) -> None:
        """Stop the worker if running."""
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self.progress.status = WorkerStatus.IDLE

    async def _run(self, directory: Path) -> None:
        """Main worker loop - process all files in directory."""
        self.progress = IngestionProgress(
            status=WorkerStatus.RUNNING,
            started_at=datetime.now(UTC),
        )

        try:
            # Ensure Meilisearch index exists
            try:
                ensure_index()
            except MeilisearchUnavailableError:
                logger.warning("Meilisearch unavailable, search will not be updated")

            # Collect all bib files
            bib_files = list(find_bib_files(directory))
            self.progress.files_total = len(bib_files)

            logger.info(
                "Starting background ingestion: %d files in %s",
                len(bib_files),
                directory,
            )

            # Process each file
            for bib_path in bib_files:
                if asyncio.current_task().cancelled():
                    break

                await self._process_file(bib_path)
                self.progress.files_done += 1

                # Small yield to allow other tasks to run
                await asyncio.sleep(0)

            self.progress.status = WorkerStatus.COMPLETE
            self.progress.completed_at = datetime.now(UTC)
            self.progress.current_file = None

            logger.info(
                "Background ingestion complete: %d files, %d entries imported, %d errors",
                self.progress.files_done,
                self.progress.entries_imported,
                self.progress.entries_errors,
            )

        except asyncio.CancelledError:
            logger.info("Ingestion cancelled")
            self.progress.status = WorkerStatus.IDLE
            raise
        except Exception as e:
            logger.exception("Background ingestion failed: %s", e)
            self.progress.status = WorkerStatus.ERROR
            self.progress.error_message = str(e)

    async def _process_file(self, bib_path: Path) -> None:
        """Process a single bib file - parse, ingest, index, commit."""
        self.progress.current_file = bib_path.name

        # Parse file
        entries_data = parse_bib_file(bib_path)
        if not entries_data:
            return

        imported_ids = []

        # Import to database
        async with async_session() as session:
            imported_entries = await self._ingest_entries(session, entries_data)

            if imported_entries:
                # Collect IDs before commit
                imported_ids = [e.id for e in imported_entries]

                # Commit this file's entries
                await session.commit()

        # Sync to Meilisearch (in separate read-only transaction with eager loading)
        if imported_ids:
            try:
                async with async_session() as session:
                    stmt = (
                        select(Entry)
                        .options(
                            selectinload(Entry.authors).selectinload(EntryAuthor.author)
                        )
                        .where(Entry.id.in_(imported_ids))
                    )
                    result = await session.execute(stmt)
                    entries_to_sync = result.scalars().all()

                    sync_entries(entries_to_sync)
            except MeilisearchUnavailableError:
                pass  # Already warned at startup
            except Exception as e:
                logger.warning("Failed to index entries from %s: %s", bib_path.name, e)

        logger.debug("Processed %s: %d entries", bib_path.name, len(entries_data))

    async def _ingest_entries(
        self, session: AsyncSession, entries_data: list[dict]
    ) -> list:
        """Ingest entries from parsed data, return imported Entry objects."""
        from app.services.ingest import ingest_entry

        imported = []
        for entry_data in entries_data:
            try:
                entry = await ingest_entry(session, entry_data)
                if entry:
                    imported.append(entry)
                    self.progress.entries_imported += 1
            except Exception as e:
                logger.warning(
                    "Failed to ingest %s: %s",
                    entry_data.get("citation_key", "unknown"),
                    e,
                )
                self.progress.entries_errors += 1

        return imported


# Global worker instance
worker = IngestionWorker()
