"""
Database connection and session management.

Provides async SQLAlchemy engine and session factory for database operations.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool, Pool

from orchestrator.config import settings


class DatabaseConnection:
    """Manages database connections and sessions."""

    def __init__(self, database_url: str | None = None, pool_size: int = 5, max_overflow: int = 10) -> None:
        """
        Initialize database connection.

        Args:
            database_url: PostgreSQL connection URL. Uses settings if not provided.
            pool_size: Number of connections to maintain in the pool.
            max_overflow: Maximum overflow size of the pool.
        """
        self.database_url = database_url or str(settings.database_url)
        self.pool_size = pool_size
        self.max_overflow = max_overflow
        self._engine: AsyncEngine | None = None
        self._session_factory: async_sessionmaker[AsyncSession] | None = None

    @property
    def engine(self) -> AsyncEngine:
        """Get or create the async engine."""
        if self._engine is None:
            self._engine = self._create_engine()
        return self._engine

    @property
    def session_factory(self) -> async_sessionmaker[AsyncSession]:
        """Get or create the session factory."""
        if self._session_factory is None:
            self._session_factory = self._create_session_factory()
        return self._session_factory

    def _create_engine(self) -> AsyncEngine:
        """Create async SQLAlchemy engine."""
        # Use NullPool for testing to avoid connection pool issues
        pool_class: type[Pool] | None = None if settings.debug else None

        engine = create_async_engine(
            self.database_url,
            echo=settings.debug,
            pool_pre_ping=True,
            pool_size=self.pool_size,
            max_overflow=self.max_overflow,
            poolclass=pool_class,
        )
        return engine

    def _create_session_factory(self) -> async_sessionmaker[AsyncSession]:
        """Create async session factory."""
        return async_sessionmaker(
            bind=self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
            autocommit=False,
        )

    async def get_session(self) -> AsyncSession:
        """
        Get a new database session.

        Returns:
            AsyncSession: New database session.
        """
        return self.session_factory()

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        """
        Context manager for database sessions.

        Yields:
            AsyncSession: Database session that will be automatically closed.

        Example:
            async with db_connection.session() as session:
                result = await session.execute(query)
        """
        async_session = self.session_factory()
        try:
            yield async_session
            await async_session.commit()
        except Exception:
            await async_session.rollback()
            raise
        finally:
            await async_session.close()

    async def close(self) -> None:
        """Close database connections."""
        if self._engine is not None:
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None

    async def health_check(self) -> bool:
        """
        Check database connection health.

        Returns:
            bool: True if database is reachable, False otherwise.
        """
        try:
            async with self.session() as session:
                await session.execute("SELECT 1")
            return True
        except Exception:
            return False


# Global database connection instance
db_connection = DatabaseConnection()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency for FastAPI to get database sessions.

    Yields:
        AsyncSession: Database session for request handling.

    Example:
        @app.get("/items")
        async def list_items(db: AsyncSession = Depends(get_db)):
            result = await db.execute(select(Item))
            return result.scalars().all()
    """
    async with db_connection.session() as session:
        yield session
