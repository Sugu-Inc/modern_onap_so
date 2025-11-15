#!/usr/bin/env python3
"""Initialize SQLite database for load testing."""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from sqlalchemy.ext.asyncio import create_async_engine
from orchestrator.models.base import Base
# Import all models so they are registered with Base
from orchestrator.models.deployment import Deployment  # noqa: F401


async def init_db():
    """Create all database tables."""
    engine = create_async_engine('sqlite+aiosqlite:///./load_test.db', echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    print('✓ Database schema created in load_test.db')


if __name__ == '__main__':
    asyncio.run(init_db())
