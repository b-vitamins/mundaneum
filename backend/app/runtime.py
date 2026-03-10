"""
Application runtime wiring for Mundaneum.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.config import settings
from app.runtime_components import DEFAULT_RUNTIME_DEFINITION
from app.runtime_models import (
    BackfillPolicy,
    ManagedJob,
    RuntimeDefinition,
    RuntimeResources,
)
from app.services.domain_events import DomainEventBus
from app.services.service_container import ServiceContainer
from app.services.system_health import SystemHealthService


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

    def snapshot(self) -> dict[str, dict]:
        return self.supervisor.snapshot()


def build_app_runtime(
    services: ServiceContainer,
    events: DomainEventBus,
    definition: RuntimeDefinition | None = None,
) -> AppRuntime:
    bibliography_path = Path(settings.bib_directory)
    runtime_resources = RuntimeResources(
        services=services,
        events=events,
        bibliography_path=bibliography_path,
        backfill_policy=BackfillPolicy(
            initial_delay_seconds=settings.s2_backfill_initial_delay_seconds,
            idle_delay_seconds=settings.s2_backfill_idle_delay_seconds,
            batch_delay_seconds=settings.s2_backfill_batch_delay_seconds,
            error_delay_seconds=settings.s2_backfill_error_delay_seconds,
            batch_size=settings.s2_backfill_batch_size,
        ),
    )
    runtime_definition = definition or DEFAULT_RUNTIME_DEFINITION
    jobs = [factory(runtime_resources) for factory in runtime_definition.jobs]
    contributors = [
        factory(runtime_resources)
        for factory in runtime_definition.health_contributors
    ]

    return AppRuntime(
        services=services,
        health=SystemHealthService(
            contributors=contributors,
            bibliography_path=bibliography_path,
        ),
        supervisor=BackgroundSupervisor(jobs),
    )
