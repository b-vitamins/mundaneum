"""
Background ingestion worker for Mundaneum.

Processes bibliography files in background, committing per-file
for immediate visibility in the UI.
"""

import asyncio
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Awaitable, Callable, Optional

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.logging import get_logger
from app.services.bibliography_contract import (
    BibliographySourceFile,
    discover_bibliography_sources,
)
from app.services.ingest import ensure_search_index_ready, ingest_bib_file

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

    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        ensure_index_ready: Callable[[], None] = ensure_search_index_ready,
        ingest_file: Callable[
            [AsyncSession, Path | BibliographySourceFile], Awaitable
        ] = ingest_bib_file,
        bib_scanner: Callable[
            [Path], Iterable[BibliographySourceFile]
        ] = discover_bibliography_sources,
    ):
        self.progress = IngestionProgress()
        self._task: Optional[asyncio.Task] = None
        self._session_factory = session_factory
        self._ensure_index_ready = ensure_index_ready
        self._ingest_file = ingest_file
        self._bib_scanner = bib_scanner

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
            self._ensure_index_ready()

            # Collect all bib files
            bib_files = list(self._bib_scanner(directory))
            self.progress.files_total = len(bib_files)

            logger.info(
                "Starting background ingestion: %d files in %s",
                len(bib_files),
                directory,
            )

            # Process each file
            for bib_source in bib_files:
                if asyncio.current_task().cancelled():
                    break

                await self._process_file(bib_source)
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

    async def _process_file(self, bib_source: BibliographySourceFile) -> None:
        """Process a single bib file - parse, ingest, index, commit."""
        self.progress.current_file = bib_source.source_file

        async with self._session_factory() as session:
            result = await self._ingest_file(session, bib_source)

        self.progress.entries_errors += result.errors
        self.progress.entries_imported += result.imported_count
        logger.debug(
            "Processed %s: %d entries", bib_source.source_file, result.total_parsed
        )
