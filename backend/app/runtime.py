"""
Application runtime wiring for Mundaneum.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

from app.config import settings
from app.logging import get_logger
from app.services.service_container import ServiceContainer
from app.services.system_health import SystemHealthService
from app.services.worker import worker as ingestion_worker

logger = get_logger(__name__)


@dataclass(slots=True)
class BackfillPolicy:
    """Operational policy for background backfill scheduling."""

    initial_delay_seconds: int
    idle_delay_seconds: int
    batch_delay_seconds: int
    error_delay_seconds: int
    batch_size: int


class BackgroundSupervisor:
    """Own the process background tasks and their scheduling policy."""

    def __init__(
        self,
        *,
        bibliography_path: Path,
        backfill_policy: BackfillPolicy,
        services: ServiceContainer,
    ):
        self._bibliography_path = bibliography_path
        self._backfill_policy = backfill_policy
        self._services = services
        self._backfill_task: asyncio.Task | None = None

    async def start(self) -> None:
        if self._bibliography_path.exists() and self._bibliography_path.is_dir():
            logger.info(
                "Bibliography directory found, starting background ingestion from %s",
                self._bibliography_path,
            )
            await ingestion_worker.start(self._bibliography_path)
        else:
            logger.info(
                "No bibliography directory at %s, skipping auto-ingest",
                self._bibliography_path,
            )

        self._backfill_task = asyncio.create_task(self._run_s2_backfill())

    async def stop(self) -> None:
        if self._backfill_task is not None:
            self._backfill_task.cancel()
            try:
                await self._backfill_task
            except asyncio.CancelledError:
                pass

        await self._services.s2_runtime.close()
        await ingestion_worker.stop()

    async def _run_s2_backfill(self) -> None:
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
            except Exception as exc:
                logger.error("S2 backfill error: %s", exc)
                await asyncio.sleep(self._backfill_policy.error_delay_seconds)


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
        await self.services.database.engine.dispose()


def build_app_runtime(services: ServiceContainer) -> AppRuntime:
    bibliography_path = Path(settings.bib_directory)
    backfill_policy = BackfillPolicy(
        initial_delay_seconds=settings.s2_backfill_initial_delay_seconds,
        idle_delay_seconds=settings.s2_backfill_idle_delay_seconds,
        batch_delay_seconds=settings.s2_backfill_batch_delay_seconds,
        error_delay_seconds=settings.s2_backfill_error_delay_seconds,
        batch_size=settings.s2_backfill_batch_size,
    )
    return AppRuntime(
        services=services,
        health=SystemHealthService(bibliography_path=bibliography_path),
        supervisor=BackgroundSupervisor(
            bibliography_path=bibliography_path,
            backfill_policy=backfill_policy,
            services=services,
        ),
    )
