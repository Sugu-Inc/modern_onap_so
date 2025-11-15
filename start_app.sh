#!/bin/bash
# Start the Modern Orchestrator API for load testing

export DATABASE_URL="sqlite+aiosqlite:///./load_test.db"
export TEMPORAL_HOST="localhost:7233"
export LOG_LEVEL="WARNING"
export PYTHONPATH="src:$PYTHONPATH"

# Load API keys from .env
export $(grep -v '^#' .env | grep API_KEYS | xargs)

echo "Starting Modern Orchestrator API on http://localhost:8000"
echo "Press Ctrl+C to stop"

uvicorn orchestrator.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --log-level warning \
    --no-access-log
