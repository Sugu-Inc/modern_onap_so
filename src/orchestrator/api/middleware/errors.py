"""
Error handling middleware.

Provides centralized error handling for the API.
"""

from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from orchestrator.config import settings


class ErrorResponse:
    """Standard error response format."""

    def __init__(self, detail: str, status_code: int = 500) -> None:
        """Initialize error response."""
        self.detail = detail
        self.status_code = status_code

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "detail": self.detail,
            "status_code": self.status_code,
        }


async def http_exception_handler(
    request: Request, exc: HTTPException
) -> JSONResponse:
    """
    Handle HTTP exceptions.

    Args:
        request: The incoming request
        exc: The HTTP exception

    Returns:
        JSONResponse with error details
    """
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError | ValidationError
) -> JSONResponse:
    """
    Handle validation errors.

    Args:
        request: The incoming request
        exc: The validation error

    Returns:
        JSONResponse with validation error details
    """
    # Extract validation errors
    if isinstance(exc, RequestValidationError):
        errors = exc.errors()
    else:
        errors = exc.errors() if hasattr(exc, "errors") else []

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": "Validation error",
            "errors": errors,
        },
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Handle generic exceptions.

    Args:
        request: The incoming request
        exc: The exception

    Returns:
        JSONResponse with error details
    """
    # Log the actual exception for debugging
    # TODO: Add structured logging here

    # In production, don't expose internal error details
    detail = "Internal server error"
    if settings.debug:
        # In debug mode, include exception details
        detail = f"Internal server error: {str(exc)}"

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": detail},
    )


def add_error_handlers(app: FastAPI) -> None:
    """
    Add error handlers to the FastAPI application.

    Args:
        app: The FastAPI application
    """
    # HTTP exceptions (404, 403, etc.)
    app.add_exception_handler(HTTPException, http_exception_handler)

    # Validation errors (422)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(ValidationError, validation_exception_handler)

    # Generic exceptions (500)
    app.add_exception_handler(Exception, generic_exception_handler)
