"""
Application runtime wiring for Mundaneum.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

from app.config import settings
from app.database import check_db_health
from app.logging import get_logger
from app.services.domain_events import DomainEventBus
from app.services.ingest import ensure_search_index_ready, ingest_bib_file
from app.services.service_container import ServiceContainer
from app.services.system_health import HealthContributor, SystemHealthService
from app.services.worker import IngestionWorker

logger = get_logger(__name__)


@dataclass(slots=True)
class BackfillPolicy:
    """Operational policy for background backfill scheduling."""

    initial_delay_seconds: int
    idle_delay_seconds: int
    batch_delay_seconds: int
    error_delay_seconds: int
    batch_size: int


class ManagedJob:
    """Small protocol-style base for supervised background jobs."""

    name: str

    async def start(self) -> None:  # pragma: no cover - interface surface
        raise NotImplementedError

    async def stop(self) -> None:  # pragma: no cover - interface surface
        raise NotImplementedError

    def status(self) -> dict:  # pragma: no cover - interface surface
        raise NotImplementedError


class BibliographyIngestJob(ManagedJob):
    """Supervise background bibliography ingestion."""

    name = "bibliography_ingest"

    def __init__(self, *, bibliography_path: Path, worker: IngestionWorker):
        self._bibliography_path = bibliography_path
        self._worker = worker

    async def start(self) -> None:
        if self._bibliography_path.exists() and self._bibliography_path.is_dir():
            logger.info(
                "Bibliography directory found, starting background ingestion from %s",
                self._bibliography_path,
            )
            await self._worker.start(self._bibliography_path)
        else:
            logger.info(
                "No bibliography directory at %s, skipping auto-ingest",
                self._bibliography_path,
            )

    async def trigger(self, directory: Path | None = None) -> dict:
        """Start ingestion manually or return current progress when already running."""
        if self._worker.is_running:
            return {"message": "Ingestion already running", **self.status()}

        target_directory = directory or self._bibliography_path
        await self._worker.start(target_directory)
        return {"message": "Ingestion started", **self.status()}

    async def stop(self) -> None:
        await self._worker.stop()

    def status(self) -> dict:
        return self._worker.get_status()


class S2BackfillJob(ManagedJob):
    """Supervise the S2 backfill loop separately from ingest."""

    name = "s2_backfill"

    def __init__(
        self,
        *,
        services: ServiceContainer,
        backfill_policy: BackfillPolicy,
    ):
        self._services = services
        self._backfill_policy = backfill_policy
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
        await asyncio.sleep(self._backfill_policy.initial_delay_seconds)
        orchestrator = self._services.s2_runtime.orchestrator
        logger.info("S2 backfill loop started")

        while True:
            try:
                resolved = await orchestrator.backfill(
                    batch_size=self._backfill_policy.batch_size
                )
                delay = (
                    self._backfill_policy.batch_delay_seconds
                    if resolved
                    else self._backfill_policy.idle_delay_seconds
                )
                await asyncio.sleep(delay)
            except asyncio.CancelledError:
                break
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.error("S2 backfill error: %s", exc)
                await asyncio.sleep(self._backfill_policy.error_delay_seconds)


class BackgroundSupervisor:
    """Own process background jobs and expose them through a registry."""

    def __init__(self, jobs: list[ManagedJob]):
        self._jobs = {job.name: job for job in jobs}

    async def start(self) -> None:
        for job in self._jobs.values():
            await job.start()

    async def stop(self) -> None:
        for job in reversed(list(self._jobs.values())):
            await job.stop()

    def get_job(self, name: str) -> ManagedJob:
        return self._jobs[name]

    def snapshot(self) -> dict[str, dict]:
        return {name: job.status() for name, job in self._jobs.items()}


@dataclass(slots=True)
class AppRuntime:
    """Process-owned runtime services."""

    services: ServiceContainer
    health: SystemHealthService
    supervisor: BackgroundSupervisor

    async def start(self) -> None:
        await self.supervisor.start()

    async def stop(self) -> None:
        await self.supervisor.stop()
        await self.services.s2_runtime.close()
        await self.services.database.engine.dispose()

    def get_job(self, name: str) -> ManagedJob:
        return self.supervisor.get_job(name)


def build_app_runtime(
    services: ServiceContainer,
    events: DomainEventBus,
) -> AppRuntime:
    bibliography_path = Path(settings.bib_directory)
    backfill_policy = BackfillPolicy(
        initial_delay_seconds=settings.s2_backfill_initial_delay_seconds,
        idle_delay_seconds=settings.s2_backfill_idle_delay_seconds,
        batch_delay_seconds=settings.s2_backfill_batch_delay_seconds,
        error_delay_seconds=settings.s2_backfill_error_delay_seconds,
        batch_size=settings.s2_backfill_batch_size,
    )
    jobs: list[ManagedJob] = [
        BibliographyIngestJob(
            bibliography_path=bibliography_path,
            worker=IngestionWorker(
                session_factory=services.database.session_factory,
                ensure_index_ready=lambda: ensure_search_index_ready(
                    services.search.indexer
                ),
                ingest_file=lambda session, path: ingest_bib_file(
                    session,
                    path,
                    search_index=services.search.indexer,
                    event_bus=events,
                ),
            ),
        ),
        S2BackfillJob(
            services=services,
            backfill_policy=backfill_policy,
        ),
    ]
    return AppRuntime(
        services=services,
        health=SystemHealthService(
            contributors=[
                HealthContributor(
                    name="database",
                    probe=lambda: check_db_health(services.database.session_factory),
                ),
                HealthContributor(
                    name="search",
                    probe=services.search.indexer.is_available,
                ),
            ],
            bibliography_path=bibliography_path,
        ),
        supervisor=BackgroundSupervisor(jobs),
    )
