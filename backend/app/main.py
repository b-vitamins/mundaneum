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
from app.database import get_db
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
from app.runtime import build_app_runtime
from app.services.service_container import build_service_container, set_service_container

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle manager."""
    setup_logging()
    logger.info("Starting Mundaneum v%s", VERSION)
    runtime = app.state.runtime

    report = await runtime.health.get_report()

    if not report.database_available:
        logger.error(
            "Database is not available - application may not function correctly"
        )
    if not report.search_available:
        logger.warning("Meilisearch is not available - search will be degraded")

    await runtime.start()

    yield

    logger.info("Shutting down Mundaneum")
    await runtime.stop()


app = FastAPI(
    title=settings.app_name,
    description="Research intelligence platform for books and papers",
    version=VERSION,
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)
app.state.services = build_service_container()
set_service_container(app.state.services)
app.state.runtime = build_app_runtime(app.state.services)

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
async def health(request: Request):
    """Health check endpoint."""
    return (await request.app.state.runtime.health.get_report()).public_payload()


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
