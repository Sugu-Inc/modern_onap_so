"""
Main FastAPI application.

This is the entry point for the Modern Infrastructure Orchestrator API.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from orchestrator.api.middleware.errors import add_error_handlers
from orchestrator.api.middleware.logging import add_logging_middleware
from orchestrator.api.v1 import configurations, deployments, health, metrics
from orchestrator.logging import logger
from orchestrator.metrics import setup_metrics


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    Application lifespan manager.

    Handles startup and shutdown tasks.
    """
    # Startup
    logger.info("application_starting", version="1.0.0")
    setup_metrics()
    # TODO: Initialize database connection pool
    # TODO: Initialize Temporal client
    yield
    # Shutdown
    logger.info("application_shutting_down")
    # TODO: Close database connections
    # TODO: Close Temporal client


# Create FastAPI application
app = FastAPI(
    title="Modern Infrastructure Orchestrator",
    description="A lightweight, cloud-native platform for deploying and managing infrastructure",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Add middleware (order matters: logging first, then errors)
add_logging_middleware(app)
add_error_handlers(app)

# Include routers
app.include_router(health.router, tags=["health"])
app.include_router(metrics.router)
app.include_router(deployments.router)
app.include_router(configurations.router)
