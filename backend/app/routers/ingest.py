"""
Import router for Mundaneum API.
"""

from pathlib import Path

from fastapi import APIRouter, Depends
from pydantic import BaseModel, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import get_bibliography_repository, get_events, get_search_index
from app.exceptions import ValidationError
from app.logging import get_logger
from app.services.bibliography_repository import BibliographyRepositoryService
from app.services.domain_events import DomainEventBus
from app.services.ingest import ingest_directory
from app.services.sync import SearchIndexService

logger = get_logger(__name__)

router = APIRouter(prefix="/ingest", tags=["ingest"])


class ImportRequest(BaseModel):
    """Request model for BibTeX import."""

    directory: str | None = None  # Uses config default if not provided

    @field_validator("directory")
    @classmethod
    def validate_directory(cls, v: str | None) -> str | None:
        """Validate directory path to prevent traversal attacks."""
        if v is None:
            return v

        # Normalize path
        path = Path(v).resolve()

        # Must be absolute
        if not path.is_absolute():
            raise ValueError("Directory must be an absolute path")

        # No path traversal
        if ".." in str(path):
            raise ValueError("Path traversal not allowed")

        return str(path)


class ImportResponse(BaseModel):
    """Response model for import results."""

    imported: int
    errors: int
    total_parsed: int


@router.post("", response_model=ImportResponse)
async def import_bibtex(
    request: ImportRequest,
    db: AsyncSession = Depends(get_db),
    search_index: SearchIndexService = Depends(get_search_index),
    event_bus: DomainEventBus = Depends(get_events),
    bibliography_repository: BibliographyRepositoryService = Depends(
        get_bibliography_repository
    ),
):
    """
    Import BibTeX files from a directory.

    If directory is not specified, uses the configured default.
    """
    path = (
        Path(request.directory)
        if request.directory is not None
        else await bibliography_repository.ensure_checkout(
            refresh=settings.bibliography_runtime_sync_enabled
        )
    )
    if not path.exists():
        raise ValidationError("Directory does not exist")
    if not path.is_dir():
        raise ValidationError("Path is not a directory")

    logger.info("Starting import from: %s", path)
    result = await ingest_directory(
        db,
        path,
        search_index=search_index,
        event_bus=event_bus,
    )

    return ImportResponse(**result)
