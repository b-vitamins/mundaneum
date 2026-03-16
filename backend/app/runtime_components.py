"""
Concrete runtime job and health registrations.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Awaitable, Callable

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import settings
from app.database import check_db_health
from app.logging import get_logger
from app.modeling.library_models import Entry
from app.modeling.ner_models import NerRelease
from app.runtime_models import ManagedJob, RuntimeDefinition, RuntimeResources
from app.services.bibliography_repository import BibliographyRepositoryError
from app.services.ingest import ensure_search_index_ready, ingest_bib_file
from app.services.ner_ingest import (
    ingest_ner_release,
    load_release_manifest,
    release_id_from_manifest,
    resolve_signals_release_dir,
)
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


async def _latest_ner_release_id(
    session_factory: async_sessionmaker[AsyncSession],
) -> str | None:
    async with session_factory() as session:
        return await session.scalar(
            select(NerRelease.release_id).order_by(NerRelease.created_at.desc()).limit(1)
        )


async def _entry_count(session_factory: async_sessionmaker[AsyncSession]) -> int:
    async with session_factory() as session:
        count = await session.scalar(select(func.count(Entry.id)))
    return int(count or 0)


async def run_ner_auto_ingest_once(
    *,
    session_factory: async_sessionmaker[AsyncSession],
    signals_path: str | Path,
    wait_for_entries: bool,
    wait_timeout_seconds: int,
    poll_interval_seconds: float,
    ingest_release: Callable[[AsyncSession, Path], Awaitable[dict]],
) -> dict:
    try:
        release_dir = resolve_signals_release_dir(signals_path)
    except (FileNotFoundError, NotADirectoryError, ValueError) as exc:
        return {
            "status": "skipped",
            "message": str(exc),
            "release_id": None,
        }

    manifest = load_release_manifest(release_dir)
    release_id = release_id_from_manifest(manifest, release_dir)
    target_entry_count = max(1, int(manifest.get("entries_seen") or 0))

    current_release_id = await _latest_ner_release_id(session_factory)
    if current_release_id == release_id:
        return {
            "status": "skipped",
            "message": f"NER release '{release_id}' is already ingested",
            "release_id": release_id,
        }

    if wait_for_entries:
        deadline = asyncio.get_running_loop().time() + max(wait_timeout_seconds, 0)
        while True:
            available_entries = await _entry_count(session_factory)
            if available_entries >= target_entry_count:
                break

            if wait_timeout_seconds <= 0 or asyncio.get_running_loop().time() >= deadline:
                return {
                    "status": "skipped",
                    "message": (
                        "NER auto-ingest skipped: bibliography entries not ready "
                        f"(have {available_entries}, need {target_entry_count}) "
                        f"within {wait_timeout_seconds}s"
                    ),
                    "release_id": release_id,
                }

            await asyncio.sleep(max(poll_interval_seconds, 0.1))

    async with session_factory() as session:
        result = await ingest_release(session, release_dir)

    return {
        "status": "complete",
        "message": f"Auto-ingested NER release '{result.get('release_id', release_id)}'",
        "release_id": str(result.get("release_id", release_id)),
        "result": result,
    }


class NerAutoIngestJob(ManagedJob):
    """Run a safe one-shot NER ingest at startup when a new release is available."""

    name = "ner_auto_ingest"

    def __init__(
        self,
        *,
        resources: RuntimeResources,
        ingest_release: Callable[[AsyncSession, Path], Awaitable[dict]] = ingest_ner_release,
    ):
        self._resources = resources
        self._ingest_release = ingest_release
        self._task: asyncio.Task | None = None
        self._status = "idle"
        self._message = "Not started"
        self._release_id: str | None = None
        self._last_result: dict | None = None

    async def start(self) -> None:
        if not settings.ner_auto_ingest_enabled:
            self._status = "disabled"
            self._message = "Disabled by configuration"
            return

        if self._task is None or self._task.done():
            self._status = "running"
            self._message = "Checking NER release state"
            self._task = asyncio.create_task(self._run_once())

    async def stop(self) -> None:
        if self._task is not None and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
            self._status = "idle"
            self._message = "Stopped"

    def status(self) -> dict:
        return {
            "status": self._status,
            "enabled": settings.ner_auto_ingest_enabled,
            "release_id": self._release_id,
            "message": self._message,
            "result": self._last_result,
        }

    async def _run_once(self) -> None:
        try:
            outcome = await run_ner_auto_ingest_once(
                session_factory=self._resources.services.database.session_factory,
                signals_path=settings.ner_signals_path,
                wait_for_entries=settings.ner_auto_ingest_wait_for_entries,
                wait_timeout_seconds=settings.ner_auto_ingest_wait_timeout_seconds,
                poll_interval_seconds=settings.ner_auto_ingest_poll_interval_seconds,
                ingest_release=self._ingest_release,
            )
            self._status = str(outcome.get("status", "error"))
            self._message = str(outcome.get("message", ""))
            self._release_id = (
                str(outcome["release_id"]) if outcome.get("release_id") else None
            )
            self._last_result = outcome.get("result")
            if self._status == "complete":
                logger.info(self._message)
            elif self._status == "skipped":
                logger.info(self._message)
            else:
                logger.warning(self._message)
        except Exception as exc:
            self._status = "error"
            self._message = f"NER auto-ingest failed: {exc}"
            logger.exception(self._message)


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


def build_ner_auto_ingest_job(resources: RuntimeResources) -> ManagedJob:
    return NerAutoIngestJob(resources=resources)


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
    jobs=[
        build_bibliography_ingest_job,
        build_ner_auto_ingest_job,
        build_s2_backfill_job,
    ],
    health_contributors=[
        build_database_health_contributor,
        build_search_health_contributor,
    ],
)
