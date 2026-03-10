"""
Generic runtime contracts and configuration.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from app.services.domain_events import DomainEventBus
from app.services.service_container import ServiceContainer
from app.services.system_health import HealthContributor


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


@dataclass(slots=True)
class RuntimeResources:
    """Runtime-owned services passed to job and health factories."""

    services: ServiceContainer
    events: DomainEventBus
    bibliography_path: Path
    backfill_policy: BackfillPolicy


JobFactory = Callable[[RuntimeResources], ManagedJob]
HealthContributorFactory = Callable[[RuntimeResources], HealthContributor]


@dataclass(slots=True)
class RuntimeDefinition:
    """Declarative runtime topology."""

    jobs: list[JobFactory]
    health_contributors: list[HealthContributorFactory]
