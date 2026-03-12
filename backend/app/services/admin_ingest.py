"""
Admin-oriented ingestion controls.
"""

from __future__ import annotations

from pathlib import Path

from app.exceptions import MundaneumError
from app.runtime import AppRuntime
from app.runtime_components import BibliographyIngestJob


def _get_ingest_job(runtime: AppRuntime) -> BibliographyIngestJob:
    job = runtime.get_job("bibliography_ingest")
    if not isinstance(job, BibliographyIngestJob):
        raise MundaneumError(
            "Bibliography ingest job is not configured", status_code=500
        )
    return job


def get_ingest_status(runtime: AppRuntime) -> dict:
    return _get_ingest_job(runtime).status()


async def resolve_ingest_directory(
    runtime: AppRuntime, directory: str | None
) -> Path | None:
    if directory is None:
        return None

    path = Path(directory)
    if not path.exists() or not path.is_dir():
        raise MundaneumError(f"Directory not found: {path}", status_code=400)
    return path


async def start_ingest(runtime: AppRuntime, directory: str | None) -> dict:
    path = await resolve_ingest_directory(runtime, directory)
    return await _get_ingest_job(runtime).trigger(path)
