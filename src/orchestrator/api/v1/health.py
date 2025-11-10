"""
Health check endpoint.

Provides application health status and readiness checks.
"""

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator.config import settings
from orchestrator.db.connection import db_connection, get_db

router = APIRouter()


class HealthResponse(BaseModel):
    """Health check response model."""

    status: str = Field(..., description="Overall health status", examples=["healthy"])
    version: str = Field(..., description="Application version", examples=["1.0.0"])
    timestamp: str = Field(
        ..., description="Current timestamp", examples=["2025-01-10T12:00:00Z"]
    )
    database: str = Field(
        ..., description="Database connection status", examples=["connected"]
    )


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health Check",
    description="Check the health status of the application and its dependencies",
)
async def health_check(db: AsyncSession = Depends(get_db)) -> HealthResponse:
    """
    Health check endpoint.

    Returns the current health status of the application including:
    - Overall status
    - Version information
    - Current timestamp
    - Database connection status

    This endpoint can be used by:
    - Load balancers for health checks
    - Monitoring systems for alerting
    - Kubernetes readiness/liveness probes
    """
    # Check database connectivity
    database_status = "connected"
    try:
        # Try a simple query to verify database is responsive
        await db.execute("SELECT 1")
    except Exception:
        database_status = "disconnected"

    return HealthResponse(
        status="healthy",
        version="1.0.0",
        timestamp=datetime.now(timezone.utc).isoformat(),
        database=database_status,
    )
