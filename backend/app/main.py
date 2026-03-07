"""
FastAPI application entry point.
"""

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import VERSION, settings
from app.database import check_db_health, engine, get_db
from app.exceptions import MundaneumError
from app.logging import get_logger, setup_logging
from app.middleware import RequestIDMiddleware
from app.models import Author, Collection, Entry
from app.routers import (
    admin,
    authors,
    collections,
    entries,
    graph,
    ingest,
    search,
    subjects,
    topics,
    venues,
)
from app.services.sync import is_available as meili_available
from app.services.worker import worker as ingestion_worker

logger = get_logger(__name__)

# Default bibliography path inside container
BIBLIOGRAPHY_PATH = "/bibliography"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle manager."""
    import asyncio

    setup_logging()
    logger.info("Starting Mundaneum v%s", VERSION)

    # Startup validation
    db_ok = await check_db_health()
    meili_ok = meili_available()

    if not db_ok:
        logger.error(
            "Database is not available - application may not function correctly"
        )
    if not meili_ok:
        logger.warning("Meilisearch is not available - search will be degraded")

    # Start background ingestion if bibliography directory exists
    from pathlib import Path

    bib_dir = Path(BIBLIOGRAPHY_PATH)
    if bib_dir.exists() and bib_dir.is_dir():
        logger.info("Bibliography directory found, starting background ingestion")
        await ingestion_worker.start(bib_dir)
    else:
        logger.info(
            "No bibliography directory at %s, skipping auto-ingest", BIBLIOGRAPHY_PATH
        )

    # Start S2 backfill loop (resolves unsynced entries in background)
    async def _s2_backfill_loop():
        from app.services.s2 import get_sync_orchestrator

        # Wait for ingestion to settle before starting backfill
        await asyncio.sleep(30)
        orchestrator = get_sync_orchestrator()
        logger.info("S2 backfill loop started")

        while True:
            try:
                resolved = await orchestrator.backfill(batch_size=10)
                if resolved == 0:
                    await asyncio.sleep(300)  # Check every 5 min when idle
                else:
                    await asyncio.sleep(5)  # Brief pause between batches
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("S2 backfill error: %s", e)
                await asyncio.sleep(60)

    backfill_task = asyncio.create_task(_s2_backfill_loop())

    yield

    # Shutdown
    logger.info("Shutting down Mundaneum")
    backfill_task.cancel()
    try:
        await backfill_task
    except asyncio.CancelledError:
        pass
    await ingestion_worker.stop()
    await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    description="Research intelligence platform for books and papers",
    version=VERSION,
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request ID middleware for correlation
app.add_middleware(RequestIDMiddleware)


# Exception handlers
@app.exception_handler(MundaneumError)
async def mundaneum_exception_handler(request: Request, exc: MundaneumError):
    """Handle Mundaneum-specific exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message, **exc.detail},
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle uncaught exceptions."""
    logger.exception("Unhandled exception: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


app.include_router(admin.router, prefix="/api")
app.include_router(authors.router, prefix="/api")
app.include_router(entries.router, prefix="/api")
app.include_router(graph.router, prefix="/api")
app.include_router(collections.router, prefix="/api")
app.include_router(ingest.router, prefix="/api")
app.include_router(search.router, prefix="/api/search")
app.include_router(venues.router, prefix="/api")
app.include_router(subjects.router, prefix="/api")
app.include_router(topics.router, prefix="/api")


@app.get("/health")
async def health():
    """Health check endpoint."""
    db_ok = await check_db_health()
    meili_ok = meili_available()

    if db_ok and meili_ok:
        status = "ok"
    elif db_ok:
        status = "degraded"
    else:
        status = "unhealthy"

    return {
        "status": status,
        "version": VERSION,
        "services": {
            "database": "ok" if db_ok else "unavailable",
            "search": "ok" if meili_ok else "unavailable",
        },
    }


@app.get("/api/stats")
async def stats(db: AsyncSession = Depends(get_db)):
    """Get library statistics."""
    entries_count = await db.scalar(select(func.count(Entry.id))) or 0
    authors_count = await db.scalar(select(func.count(Author.id))) or 0
    collections_count = await db.scalar(select(func.count(Collection.id))) or 0

    return {
        "entries": entries_count,
        "authors": authors_count,
        "collections": collections_count,
    }
