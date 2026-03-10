"""
Database configuration and dependency helpers.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING

from fastapi import Request
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

if TYPE_CHECKING:
    from app.services.service_container import DatabaseServices


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
        pool_pre_ping=True,
    )
    session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    return DatabaseServices(engine=engine, session_factory=session_factory)


async def get_db(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """Resolve a database session from the app-owned context."""
    session_factory = request.app.state.context.services.database.session_factory
    async with session_factory() as session:
        try:
            yield session
        finally:
            await session.close()


async def check_db_health(
    session_factory: async_sessionmaker[AsyncSession],
    timeout: float = 5.0,
) -> bool:
    """Check database connectivity with timeout."""
    import asyncio

    from sqlalchemy import text

    async def _check() -> bool:
        async with session_factory() as session:
            await session.execute(text("SELECT 1"))
            return True

    try:
        return await asyncio.wait_for(_check(), timeout=timeout)
    except (TimeoutError, Exception):
        return False
