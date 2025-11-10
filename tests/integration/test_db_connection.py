"""Tests for database connection."""

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator.db.connection import DatabaseConnection


@pytest.fixture
async def db_connection() -> DatabaseConnection:
    """Create a test database connection."""
    # Use SQLite in memory for testing
    connection = DatabaseConnection(
        database_url="sqlite+aiosqlite:///:memory:",
        pool_size=1,
        max_overflow=0,
    )
    yield connection
    await connection.close()


class TestDatabaseConnection:
    """Test suite for DatabaseConnection class."""

    async def test_engine_creation(self, db_connection: DatabaseConnection) -> None:
        """Test that engine is created correctly."""
        engine = db_connection.engine
        assert engine is not None
        assert engine == db_connection.engine  # Should return same instance

    async def test_session_factory_creation(
        self, db_connection: DatabaseConnection
    ) -> None:
        """Test that session factory is created correctly."""
        factory = db_connection.session_factory
        assert factory is not None
        assert factory == db_connection.session_factory  # Should return same instance

    async def test_get_session(self, db_connection: DatabaseConnection) -> None:
        """Test getting a new session."""
        session = await db_connection.get_session()
        assert isinstance(session, AsyncSession)
        await session.close()

    async def test_session_context_manager(
        self, db_connection: DatabaseConnection
    ) -> None:
        """Test session context manager."""
        async with db_connection.session() as session:
            assert isinstance(session, AsyncSession)
            # Execute a simple query
            result = await session.execute(text("SELECT 1"))
            assert result.scalar() == 1

    async def test_session_context_manager_commit(
        self, db_connection: DatabaseConnection
    ) -> None:
        """Test that session context manager commits on success."""
        # Create a simple table
        async with db_connection.session() as session:
            await session.execute(
                text("CREATE TABLE test_table (id INTEGER PRIMARY KEY, name TEXT)")
            )

        # Verify table was created (commit worked)
        async with db_connection.session() as session:
            result = await session.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' AND name='test_table'")
            )
            assert result.scalar() == "test_table"

    async def test_session_context_manager_rollback(
        self, db_connection: DatabaseConnection
    ) -> None:
        """Test that session context manager rolls back on error."""
        # Create a table
        async with db_connection.session() as session:
            await session.execute(
                text("CREATE TABLE test_table (id INTEGER PRIMARY KEY, name TEXT)")
            )

        # Try to insert invalid data (should rollback)
        with pytest.raises(Exception):
            async with db_connection.session() as session:
                await session.execute(
                    text("INSERT INTO test_table (id, name) VALUES (1, 'test')")
                )
                # Force an error
                raise Exception("Test error")

        # Verify no data was inserted (rollback worked)
        async with db_connection.session() as session:
            result = await session.execute(text("SELECT COUNT(*) FROM test_table"))
            assert result.scalar() == 0

    async def test_health_check_success(
        self, db_connection: DatabaseConnection
    ) -> None:
        """Test health check with valid connection."""
        is_healthy = await db_connection.health_check()
        assert is_healthy is True

    async def test_health_check_failure(self) -> None:
        """Test health check with invalid connection."""
        # Create connection with invalid URL
        connection = DatabaseConnection(database_url="postgresql+asyncpg://invalid:5432/db")
        is_healthy = await connection.health_check()
        assert is_healthy is False
        await connection.close()

    async def test_close_connection(self, db_connection: DatabaseConnection) -> None:
        """Test closing database connection."""
        # Get engine to create it
        _ = db_connection.engine

        # Close connection
        await db_connection.close()

        # Engine should be None after closing
        assert db_connection._engine is None
        assert db_connection._session_factory is None
