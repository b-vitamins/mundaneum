from collections.abc import AsyncGenerator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.database import ensure_database_schema, get_db
from app.main import app


async def _dispose_database_pool() -> None:
    """Drop pooled connections so tests don't reuse loop-bound asyncpg sessions."""
    await app.state.services.database.engine.dispose()


_schema_ready = False


@pytest_asyncio.fixture
async def isolated_session_factory() -> AsyncGenerator[
    async_sessionmaker[AsyncSession], None
]:
    """Bind tests to a single connection wrapped in a rollback-only transaction."""
    global _schema_ready
    database = app.state.context.services.database
    original_factory = database.session_factory

    if not _schema_ready:
        await ensure_database_schema(database.engine)
        _schema_ready = True

    async with database.engine.connect() as connection:
        transaction = await connection.begin()
        session_factory = async_sessionmaker(
            bind=connection,
            class_=AsyncSession,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )

        async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
            async with session_factory() as session:
                yield session

        database.session_factory = session_factory
        app.state.services.database.session_factory = session_factory
        app.dependency_overrides[get_db] = override_get_db

        try:
            yield session_factory
        finally:
            app.dependency_overrides.pop(get_db, None)
            database.session_factory = original_factory
            app.state.services.database.session_factory = original_factory
            await transaction.rollback()
    await _dispose_database_pool()


@pytest_asyncio.fixture
async def client(isolated_session_factory):
    """Create async test client."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


@pytest_asyncio.fixture
async def db_session(
    isolated_session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncSession, None]:
    """Create a new database session for a test."""
    async with isolated_session_factory() as session:
        try:
            yield session
        finally:
            await session.rollback()
