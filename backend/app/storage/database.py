"""
Database connection and session management.
"""
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.storage.models import Base

# Create async engine
engine = create_async_engine(
    settings.MYSQL_URL,
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

# Create async session factory
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class SafeSession:
    """Session wrapper that auto-wraps raw SQL strings with text()."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def execute(self, statement, *args, **kwargs):
        if isinstance(statement, str):
            statement = text(statement)
        return await self._session.execute(statement, *args, **kwargs)

    async def commit(self):
        await self._session.commit()

    async def rollback(self):
        await self._session.rollback()

    async def close(self):
        await self._session.close()


async def init_db():
    """Initialize database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db():
    """Close database connection."""
    await engine.dispose()


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[SafeSession, None]:
    """Get database session with auto text() wrapping."""
    async with async_session_factory() as session:
        safe = SafeSession(session)
        try:
            yield safe
            await safe.commit()
        except Exception:
            await safe.rollback()
            raise
        finally:
            await safe.close()


async def get_db() -> AsyncSession:
    """Dependency for FastAPI."""
    async with async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
