"""
Main FastAPI application.

This is the entry point for the Modern Infrastructure Orchestrator API.
"""

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from orchestrator.api.middleware.errors import add_error_handlers
from orchestrator.api.v1 import health
from orchestrator.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    Application lifespan manager.

    Handles startup and shutdown tasks.
    """
    # Startup
    # TODO: Initialize database connection pool
    # TODO: Initialize Temporal client
    yield
    # Shutdown
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

# Add error handlers
add_error_handlers(app)

# Include routers
app.include_router(health.router, tags=["health"])
