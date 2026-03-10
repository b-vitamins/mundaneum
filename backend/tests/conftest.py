import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app


async def _dispose_database_pool() -> None:
    """Drop pooled connections so tests don't reuse loop-bound asyncpg sessions."""
    await app.state.services.database.engine.dispose()


@pytest_asyncio.fixture
async def client():
    """Create async test client."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
    await _dispose_database_pool()


@pytest_asyncio.fixture
async def db_session():
    """Create a new database session for a test."""
    from app.database import async_session

    async with async_session() as session:
        yield session
        # Rollback any changes
        await session.rollback()
    await _dispose_database_pool()
