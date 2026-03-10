"""
Admin-oriented ingestion controls.
"""

from __future__ import annotations

from pathlib import Path

from app.config import settings
from app.exceptions import MundaneumError
from app.services.worker import worker


def get_ingest_status() -> dict:
    return worker.get_status()


def resolve_ingest_directory(directory: str | None) -> Path:
    path = Path(directory or settings.bib_directory)
    if not path.exists() or not path.is_dir():
        raise MundaneumError(
            f"Directory not found: {path}",
            status_code=400,
        )
    return path


async def start_ingest(directory: str | None) -> dict:
    if worker.is_running:
        return {"message": "Ingestion already running", **worker.get_status()}

    path = resolve_ingest_directory(directory)
    await worker.start(path)
    return {"message": "Ingestion started", **worker.get_status()}
