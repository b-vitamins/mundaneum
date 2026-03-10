"""
Database configuration and session management.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


def _get_database_url() -> str:
    """Get database URL with async driver."""
    url = settings.database_url
    if "postgresql://" in url and "+asyncpg" not in url:
        url = url.replace("postgresql://", "postgresql+asyncpg://")
    return url


class Base(DeclarativeBase):
    """SQLAlchemy declarative base."""

    pass


def build_database_services() -> "DatabaseServices":
    from app.services.service_container import DatabaseServices

    engine = create_async_engine(
        _get_database_url(),
        echo=settings.debug,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_timeout=settings.db_pool_timeout,
        pool_pre_ping=True,  # Verify connections before use
    )
    session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    return DatabaseServices(engine=engine, session_factory=session_factory)


def get_engine() -> AsyncEngine:
    from app.services.service_container import get_service_container

    return get_service_container().database.engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    from app.services.service_container import get_service_container

    return get_service_container().database.session_factory


class _EngineProxy:
    def __getattr__(self, name: str):
        return getattr(get_engine(), name)


class _SessionFactoryProxy:
    def __call__(self, *args, **kwargs):
        return get_session_factory()(*args, **kwargs)


engine = _EngineProxy()
async_session = _SessionFactoryProxy()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Get database session for dependency injection."""
    async with get_session_factory()() as session:
        try:
            yield session
        finally:
            await session.close()


async def check_db_health(timeout: float = 5.0) -> bool:
    """Check database connectivity with timeout."""
    import asyncio

    from sqlalchemy import text

    async def _check() -> bool:
        async with get_session_factory()() as session:
            await session.execute(text("SELECT 1"))
            return True

    try:
        return await asyncio.wait_for(_check(), timeout=timeout)
    except (TimeoutError, Exception):
        return False
