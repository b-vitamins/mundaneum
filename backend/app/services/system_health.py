"""
System health aggregation for Mundaneum.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable

from app.config import VERSION, settings
from app.database import check_db_health
from app.services.sync import is_available as meili_available


@dataclass(slots=True)
class SystemHealthReport:
    """Normalized health state shared by public and admin endpoints."""

    database_available: bool
    search_available: bool
    bibliography_configured: bool
    bibliography_files_count: int

    def public_status(self) -> str:
        if self.database_available and self.search_available:
            return "ok"
        if self.database_available:
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
                "database": "ok" if self.database_available else "unavailable",
                "search": "ok" if self.search_available else "unavailable",
            },
        }

    def admin_payload(self) -> dict:
        return {
            "status": self.admin_status(),
            "database": "ok" if self.database_available else "unavailable",
            "search": "ok" if self.search_available else "unavailable",
            "bib_directory": "ok" if self.bibliography_configured else "not configured",
            "bib_files_count": self.bibliography_files_count,
        }


class SystemHealthService:
    """Probe-oriented health service with explicit policy inputs."""

    def __init__(
        self,
        *,
        db_probe: Callable[[], Awaitable[bool]] = check_db_health,
        search_probe: Callable[[], bool] = meili_available,
        bibliography_path: Path | None = None,
    ):
        self._db_probe = db_probe
        self._search_probe = search_probe
        self._bibliography_path = bibliography_path or Path(settings.bib_directory)

    async def get_report(self) -> SystemHealthReport:
        db_ok = await self._db_probe()
        search_ok = self._search_probe()

        bib_exists = self._bibliography_path.exists() and self._bibliography_path.is_dir()
        bib_count = len(list(self._bibliography_path.glob("**/*.bib"))) if bib_exists else 0

        return SystemHealthReport(
            database_available=db_ok,
            search_available=search_ok,
            bibliography_configured=bib_exists,
            bibliography_files_count=bib_count,
        )
