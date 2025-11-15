#!/bin/bash
set -e

echo "============================================"
echo "Starting Modern Orchestrator for Load Test"
echo "============================================"
echo ""

# Export environment variables for SQLite-based testing
export DATABASE_URL="sqlite+aiosqlite:///./load_test.db"
export TEMPORAL_HOST="localhost:7233"
export LOG_LEVEL="WARNING"  # Reduce logging noise during load test
export API_WORKERS="1"  # Single worker for simplicity
export API_HOST="0.0.0.0"
export API_PORT="8000"

# Load API keys from .env
export $(grep API_KEYS ../.env | xargs)

echo "Configuration:"
echo "  - Database: SQLite (load_test.db)"
echo "  - API Port: 8000"
echo "  - Log Level: WARNING"
echo "  - Workers: 1"
echo ""

# Check if Poetry is installed
if ! command -v poetry &> /dev/null; then
    echo "ERROR: Poetry is not installed"
    exit 1
fi

# Install dependencies
echo "Installing dependencies..."
cd ..
poetry install --no-root --quiet
echo "✓ Dependencies installed"
echo ""

# Check if database needs initialization
if [ ! -f "load_test.db" ]; then
    echo "Initializing database with schema..."
    # Create database schema using SQLAlchemy
    poetry run python -c "
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from orchestrator.db.models import Base

async def init_db():
    engine = create_async_engine('sqlite+aiosqlite:///./load_test.db')
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()

asyncio.run(init_db())
print('✓ Database schema created')
"
fi

echo ""
echo "Starting API server..."
echo "Access the API at: http://localhost:8000"
echo "API Documentation: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop the server"
echo "============================================"
echo ""

# Start the application
cd load_test
poetry run uvicorn orchestrator.api.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --log-level warning \
    --no-access-log
