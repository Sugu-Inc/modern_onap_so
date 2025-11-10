"""
API key authentication middleware.

Provides API key-based authentication with read/write permissions.
"""

from dataclasses import dataclass

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from orchestrator.logging import logger


@dataclass
class AuthContext:
    """Authentication context attached to requests."""

    api_key: str
    permission: str  # "read" or "write"

    @property
    def can_read(self) -> bool:
        """Check if user has read permission."""
        return self.permission in ("read", "write")

    @property
    def can_write(self) -> bool:
        """Check if user has write permission."""
        return self.permission == "write"


class APIKeyAuth:
    """
    API key authentication handler.

    Validates API keys and checks permissions.
    """

    def __init__(self, api_keys_str: str) -> None:
        """
        Initialize API key auth.

        Args:
            api_keys_str: Comma-separated API keys with permissions (key:permission)
                         Example: "key1:write,key2:read"
        """
        self.api_keys = self._parse_api_keys(api_keys_str)

    def _parse_api_keys(self, api_keys_str: str) -> dict[str, str]:
        """
        Parse API keys from config string.

        Args:
            api_keys_str: Comma-separated API keys

        Returns:
            Dictionary mapping API key to permission
        """
        result = {}
        for key_permission in api_keys_str.split(","):
            key, permission = key_permission.split(":")
            result[key.strip()] = permission.strip()
        return result

    def validate_api_key(self, api_key: str | None) -> AuthContext | None:
        """
        Validate API key and return auth context.

        Args:
            api_key: API key to validate

        Returns:
            AuthContext if valid, None if invalid
        """
        if not api_key or api_key not in self.api_keys:
            return None

        return AuthContext(
            api_key=api_key,
            permission=self.api_keys[api_key],
        )


class AuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware for API key authentication.

    Checks X-API-Key header and validates permissions.
    """

    # Paths that don't require authentication
    PUBLIC_PATHS = {
        "/health",
        "/metrics",
        "/docs",
        "/redoc",
        "/openapi.json",
    }

    # Methods that require write permission
    WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

    def __init__(self, app: FastAPI, api_key_auth: APIKeyAuth) -> None:
        """
        Initialize auth middleware.

        Args:
            app: FastAPI application
            api_key_auth: API key authentication handler
        """
        super().__init__(app)
        self.api_key_auth = api_key_auth

    async def dispatch(self, request: Request, call_next):
        """
        Process request and check authentication.

        Args:
            request: HTTP request
            call_next: Next middleware in chain

        Returns:
            HTTP response
        """
        # Skip auth for public paths
        if request.url.path in self.PUBLIC_PATHS:
            return await call_next(request)

        # Get API key from header
        api_key = request.headers.get("X-API-Key")

        if not api_key:
            logger.warning(
                "auth_missing_api_key",
                path=request.url.path,
                method=request.method,
            )
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "API key required. Include X-API-Key header."},
            )

        # Validate API key
        auth_context = self.api_key_auth.validate_api_key(api_key)

        if not auth_context:
            logger.warning(
                "auth_invalid_api_key",
                path=request.url.path,
                method=request.method,
            )
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Invalid API key"},
            )

        # Check write permission for write methods
        if request.method in self.WRITE_METHODS and not auth_context.can_write:
            logger.warning(
                "auth_insufficient_permissions",
                path=request.url.path,
                method=request.method,
                permission=auth_context.permission,
            )
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"detail": "Write permission required for this operation"},
            )

        # Attach auth context to request state
        request.state.auth = auth_context

        logger.debug(
            "auth_success",
            path=request.url.path,
            method=request.method,
            permission=auth_context.permission,
        )

        # Continue to next middleware
        return await call_next(request)


def get_auth_context(request: Request) -> AuthContext:
    """
    Get authentication context from request.

    Args:
        request: HTTP request

    Returns:
        AuthContext if authenticated

    Raises:
        AttributeError: If request is not authenticated
    """
    return request.state.auth


def add_auth_middleware(app: FastAPI, api_keys_str: str) -> None:
    """
    Add authentication middleware to FastAPI app.

    Args:
        app: FastAPI application
        api_keys_str: Comma-separated API keys with permissions
    """
    api_key_auth = APIKeyAuth(api_keys_str)
    app.add_middleware(AuthMiddleware, api_key_auth=api_key_auth)
    logger.info("auth_middleware_added", key_count=len(api_key_auth.api_keys))
