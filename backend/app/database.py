"""
Database configuration and session management.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
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


engine = create_async_engine(
    _get_database_url(),
    echo=settings.debug,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_timeout=settings.db_pool_timeout,
    pool_pre_ping=True,  # Verify connections before use
)

async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """SQLAlchemy declarative base."""

    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Get database session for dependency injection."""
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()


async def check_db_health(timeout: float = 5.0) -> bool:
    """Check database connectivity with timeout."""
    import asyncio

    from sqlalchemy import text

    async def _check() -> bool:
        async with async_session() as session:
            await session.execute(text("SELECT 1"))
            return True

    try:
        return await asyncio.wait_for(_check(), timeout=timeout)
    except (TimeoutError, Exception):
        return False
