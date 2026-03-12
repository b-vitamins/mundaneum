"""
System health aggregation for Mundaneum.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable

from app.config import VERSION, settings
from app.services.bibliography_repository import BibliographyRepositoryService


@dataclass(slots=True)
class HealthContributor:
    """Named health probe for runtime-owned infrastructure."""

    name: str
    probe: Callable[[], bool | Awaitable[bool]]

    async def check(self) -> bool:
        result = self.probe()
        if inspect.isawaitable(result):
            return await result
        return result


@dataclass(slots=True)
class SystemHealthReport:
    """Normalized health state shared by public and admin endpoints."""

    services: dict[str, bool]
    bibliography_status: str
    bibliography_repo_url: str
    bibliography_checkout_path: str
    bibliography_files_count: int

    @property
    def database_available(self) -> bool:
        return self.services.get("database", False)

    @property
    def search_available(self) -> bool:
        return self.services.get("search", False)

    def public_status(self) -> str:
        if self.services and all(self.services.values()):
            return "ok"
        if any(self.services.values()):
            return "degraded"
        return "unhealthy"

    def admin_status(self) -> str:
        if self.database_available and self.search_available:
            return "healthy"
        if self.database_available:
            return "degraded"
        return "unhealthy"

    def public_payload(self) -> dict:
        return {
            "status": self.public_status(),
            "version": VERSION,
            "services": {
                name: "ok" if available else "unavailable"
                for name, available in self.services.items()
            },
        }

    def admin_payload(self) -> dict:
        return {
            "status": self.admin_status(),
            "database": "ok" if self.database_available else "unavailable",
            "search": "ok" if self.search_available else "unavailable",
            "bibliography": self.bibliography_status,
            "bibliography_repo_url": self.bibliography_repo_url,
            "bibliography_checkout_path": self.bibliography_checkout_path,
            "bib_files_count": self.bibliography_files_count,
        }


class SystemHealthService:
    """Probe-oriented health service with explicit policy inputs."""

    def __init__(
        self,
        *,
        contributors: list[HealthContributor],
        bibliography_repository: BibliographyRepositoryService | None = None,
    ):
        self._contributors = {
            contributor.name: contributor for contributor in contributors
        }
        self._bibliography_repository = (
            bibliography_repository
            or BibliographyRepositoryService(
                repo_url=settings.bibliography_repo_url,
                checkout_path=Path(settings.bibliography_checkout_path),
                ref=settings.bibliography_repo_ref,
                timeout_seconds=settings.bibliography_sync_timeout_seconds,
            )
        )

    async def get_report(self) -> SystemHealthReport:
        service_statuses = {
            name: await contributor.check()
            for name, contributor in self._contributors.items()
        }
        bibliography_state = await self._bibliography_repository.describe_checkout()

        return SystemHealthReport(
            services=service_statuses,
            bibliography_status="ok"
            if bibliography_state.exists
            else "not checked out",
            bibliography_repo_url=bibliography_state.repo_url,
            bibliography_checkout_path=str(bibliography_state.checkout_path),
            bibliography_files_count=bibliography_state.files_count,
        )
