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
from app.exceptions import FolioError
from app.logging import get_logger, setup_logging
from app.middleware import RequestIDMiddleware
from app.models import Author, Collection, Entry
from app.routers import admin, collections, entries, ingest, search
from app.services.sync import is_available as meili_available

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle manager."""
    setup_logging()
    logger.info("Starting Folio v%s", VERSION)

    # Startup validation
    db_ok = await check_db_health()
    meili_ok = meili_available()

    if not db_ok:
        logger.error(
            "Database is not available - application may not function correctly"
        )
    if not meili_ok:
        logger.warning("Meilisearch is not available - search will be degraded")

    yield

    logger.info("Shutting down Folio")
    await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    description="Private library for books and papers",
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
@app.exception_handler(FolioError)
async def folio_exception_handler(request: Request, exc: FolioError):
    """Handle Folio-specific exceptions."""
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
app.include_router(entries.router, prefix="/api")
app.include_router(collections.router, prefix="/api")
app.include_router(ingest.router, prefix="/api")
app.include_router(search.router, prefix="/api/search")


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
