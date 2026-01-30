"""
Import router for Folio API.
"""

from pathlib import Path

from fastapi import APIRouter, Depends
from pydantic import BaseModel, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.exceptions import ValidationError
from app.logging import get_logger
from app.services.ingest import ingest_directory

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
):
    """
    Import BibTeX files from a directory.

    If directory is not specified, uses the configured default.
    """
    directory = request.directory or settings.bib_directory

    # Validate directory exists
    path = Path(directory)
    if not path.exists():
        raise ValidationError("Directory does not exist")
    if not path.is_dir():
        raise ValidationError("Path is not a directory")

    logger.info("Starting import from: %s", directory)
    result = await ingest_directory(db, directory)

    return ImportResponse(**result)
