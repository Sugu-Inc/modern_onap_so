"""
Main FastAPI application.

This is the entry point for the Modern Infrastructure Orchestrator API.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from orchestrator.api.middleware.auth import add_auth_middleware
from orchestrator.api.middleware.errors import add_error_handlers
from orchestrator.api.middleware.logging import add_logging_middleware
from orchestrator.api.v1 import configurations, deployments, health, metrics, scaling
from orchestrator.config import settings
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
    description="""
## Overview

A lightweight, cloud-native platform for deploying and managing cloud infrastructure.

**Key Features:**
* 🚀 Deploy VMs and networks on OpenStack
* 🔧 Configure deployed resources with Ansible
* 📊 Scale deployments up and down
* 🔄 Manage complete infrastructure lifecycle
* 📈 Built-in metrics and monitoring

## Architecture

This service provides a REST API for orchestrating infrastructure deployments:
- **Deployments**: Create, read, update, and delete infrastructure
- **Configuration**: Run Ansible playbooks on deployed VMs
- **Scaling**: Dynamically scale VM counts
- **Workflows**: Automated multi-step orchestration

## Authentication

API endpoints require API key authentication. Include your key in the `X-API-Key` header:
```
X-API-Key: your-api-key-here
```

## Rate Limiting

API requests are rate limited to 100 requests per minute per API key.
    """,
    version="1.0.0",
    lifespan=lifespan,
    contact={
        "name": "Infrastructure Team",
        "email": "infra@example.com",
    },
    license_info={
        "name": "Apache 2.0",
        "url": "https://www.apache.org/licenses/LICENSE-2.0.html",
    },
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    openapi_tags=[
        {
            "name": "health",
            "description": "Health check and readiness endpoints",
        },
        {
            "name": "metrics",
            "description": "Prometheus metrics for monitoring",
        },
        {
            "name": "deployments",
            "description": "Create, read, update, and delete infrastructure deployments",
        },
        {
            "name": "configurations",
            "description": "Configure deployed VMs using Ansible playbooks",
        },
        {
            "name": "scaling",
            "description": "Scale deployments by adding or removing VMs",
        },
    ],
)

# Add middleware (order matters: logging first, then auth, then errors)
add_logging_middleware(app)
add_auth_middleware(app, settings.api_keys)
add_error_handlers(app)

# Include routers
app.include_router(health.router, tags=["health"])
app.include_router(metrics.router)
app.include_router(deployments.router)
app.include_router(configurations.router)
app.include_router(scaling.router)
