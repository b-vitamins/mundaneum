"""
Concrete runtime job and health registrations.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from app.config import settings
from app.database import check_db_health
from app.logging import get_logger
from app.runtime_models import ManagedJob, RuntimeDefinition, RuntimeResources
from app.services.bibliography_repository import BibliographyRepositoryError
from app.services.ingest import ensure_search_index_ready, ingest_bib_file
from app.services.system_health import HealthContributor
from app.services.worker import IngestionWorker

logger = get_logger(__name__)


class BibliographyIngestJob(ManagedJob):
    """Supervise background bibliography ingestion."""

    name = "bibliography_ingest"

    def __init__(self, *, resources: RuntimeResources, worker: IngestionWorker):
        self._resources = resources
        self._worker = worker
        self._bootstrap_task: asyncio.Task | None = None

    async def start(self) -> None:
        if self._bootstrap_task is None or self._bootstrap_task.done():
            self._bootstrap_task = asyncio.create_task(self._bootstrap_ingest())

    async def trigger(self, directory: Path | None = None) -> dict:
        """Start ingestion manually or return current progress when already running."""
        if self._worker.is_running or self._is_preparing():
            return {"message": "Ingestion already running", **self.status()}

        target_directory = directory
        if target_directory is None:
            target_directory = (
                await self._resources.bibliography_repository.ensure_checkout(
                    refresh=settings.bibliography_runtime_sync_enabled
                )
            )
        await self._worker.start(target_directory)
        return {"message": "Ingestion started", **self.status()}

    async def stop(self) -> None:
        if self._bootstrap_task is not None and not self._bootstrap_task.done():
            self._bootstrap_task.cancel()
            try:
                await self._bootstrap_task
            except asyncio.CancelledError:
                pass
            self._bootstrap_task = None
        await self._worker.stop()

    def status(self) -> dict:
        return {
            **self._worker.get_status(),
            "preparing": self._is_preparing(),
        }

    async def _bootstrap_ingest(self) -> None:
        try:
            bibliography_path = (
                await self._resources.bibliography_repository.ensure_checkout(
                    refresh=settings.bibliography_runtime_sync_enabled
                )
            )
        except BibliographyRepositoryError as exc:
            logger.warning(
                "Could not prepare bibliography checkout, skipping auto-ingest: %s",
                exc,
            )
            return

        logger.info(
            "Bibliography checkout ready, starting background ingestion from %s",
            bibliography_path,
        )
        await self._worker.start(bibliography_path)

    def _is_preparing(self) -> bool:
        return self._bootstrap_task is not None and not self._bootstrap_task.done()


class S2BackfillJob(ManagedJob):
    """Supervise the S2 backfill loop separately from ingest."""

    name = "s2_backfill"

    def __init__(self, resources: RuntimeResources):
        self._resources = resources
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    def status(self) -> dict:
        running = self._task is not None and not self._task.done()
        return {"status": "running" if running else "idle"}

    async def _run(self) -> None:
        await asyncio.sleep(self._resources.backfill_policy.initial_delay_seconds)
        orchestrator = self._resources.services.s2_runtime.orchestrator
        logger.info("S2 backfill loop started")

        while True:
            try:
                resolved = await orchestrator.backfill(
                    batch_size=self._resources.backfill_policy.batch_size
                )
                delay = (
                    self._resources.backfill_policy.batch_delay_seconds
                    if resolved
                    else self._resources.backfill_policy.idle_delay_seconds
                )
                await asyncio.sleep(delay)
            except asyncio.CancelledError:
                break
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.error("S2 backfill error: %s", exc)
                await asyncio.sleep(self._resources.backfill_policy.error_delay_seconds)


def build_bibliography_ingest_job(resources: RuntimeResources) -> ManagedJob:
    return BibliographyIngestJob(
        resources=resources,
        worker=IngestionWorker(
            session_factory=resources.services.database.session_factory,
            ensure_index_ready=lambda: ensure_search_index_ready(
                resources.services.search.indexer
            ),
            ingest_file=lambda session, path: ingest_bib_file(
                session,
                path,
                search_index=resources.services.search.indexer,
                event_bus=resources.events,
            ),
        ),
    )


def build_s2_backfill_job(resources: RuntimeResources) -> ManagedJob:
    return S2BackfillJob(resources)


def build_database_health_contributor(resources: RuntimeResources) -> HealthContributor:
    return HealthContributor(
        name="database",
        probe=lambda: check_db_health(resources.services.database.session_factory),
    )


def build_search_health_contributor(resources: RuntimeResources) -> HealthContributor:
    return HealthContributor(
        name="search",
        probe=resources.services.search.indexer.is_available,
    )


DEFAULT_RUNTIME_DEFINITION = RuntimeDefinition(
    jobs=[build_bibliography_ingest_job, build_s2_backfill_job],
    health_contributors=[
        build_database_health_contributor,
        build_search_health_contributor,
    ],
)
