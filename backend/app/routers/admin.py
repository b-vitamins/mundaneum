"""
Admin router for Mundaneum API.

Provides backup/restore, ingest, and health endpoints for administration.
"""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.logging import get_logger
from app.schemas.admin import ExportData, HealthResponse, ImportResult, IngestRequest
from app.services.admin_backup import (
    export_user_state as export_user_state_service,
)
from app.services.admin_backup import (
    import_user_state as import_user_state_service,
)
from app.services.admin_ingest import (
    get_ingest_status as get_ingest_status_service,
)
from app.services.admin_ingest import start_ingest as start_ingest_service

logger = get_logger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/export", response_model=ExportData)
async def export_user_state(db: AsyncSession = Depends(get_db)):
    """
    Export all user state (notes, read status, collections).

    This data can be restored after a fresh ingest to recover user work.
    """
    export_data = await export_user_state_service(db)

    logger.info(
        "Exported %d entries and %d collections",
        len(export_data.entries),
        len(export_data.collections),
    )

    return export_data


@router.post("/import", response_model=ImportResult)
async def import_user_state(
    data: ExportData,
    db: AsyncSession = Depends(get_db),
):
    """
    Import user state from a backup.

    Updates notes, read status, and recreates collections.
    Entries must already exist (from ingest) - this only restores user state.
    """
    result = await import_user_state_service(db, data)

    logger.info(
        "Imported: %d entries updated, %d collections created/updated",
        result.entries_updated,
        result.collections_created + result.collections_updated,
    )

    return result


@router.get("/ingest/status")
async def get_ingest_status(request: Request):
    """
    Get current ingestion worker status.

    Returns progress information for background ingestion.
    """
    return get_ingest_status_service(request.app.state.context.runtime)


@router.post("/ingest/start")
async def start_ingest(
    request: IngestRequest,
    http_request: Request,
):
    """
    Manually trigger background ingestion.

    If already running, returns current status without restarting.
    """
    return await start_ingest_service(http_request.app.state.context.runtime, request.directory)


@router.get("/health", response_model=HealthResponse)
async def detailed_health(request: Request):
    """
    Detailed health check for admin dashboard.
    """
    report = await request.app.state.runtime.health.get_report()
    return HealthResponse(**report.admin_payload())
