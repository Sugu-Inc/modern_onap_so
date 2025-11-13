"""
Shared fixtures for API tests.
"""

import pytest
from fastapi.testclient import TestClient
from starlette.testclient import ASGI3App
from typing import Any


class AuthenticatedTestClient(TestClient):
    """Test client that automatically adds auth headers."""

    def __init__(self, app: ASGI3App, auth_key: str = "test-key-1", **kwargs: Any):
        # Store auth key before calling parent
        self._auth_key = auth_key

        # Set up default headers with auth key
        default_headers = {"X-API-Key": auth_key}

        # Merge with any existing headers from kwargs
        if "headers" in kwargs:
            # If headers provided, merge them (user headers take precedence)
            default_headers.update(kwargs["headers"])

        # Pass merged headers to parent
        kwargs["headers"] = default_headers
        super().__init__(app, **kwargs)

        # Also set headers attribute directly (for compatibility with different httpx versions)
        self.headers.update({"X-API-Key": auth_key})

    def _inject_auth_header(self, kwargs: dict[str, Any]) -> dict[str, Any]:
        """Inject auth header into kwargs if not present."""
        if "headers" not in kwargs:
            kwargs["headers"] = {}

        # Handle different header types
        if isinstance(kwargs["headers"], dict):
            if "X-API-Key" not in kwargs["headers"]:
                kwargs["headers"]["X-API-Key"] = self._auth_key

        return kwargs

    def get(self, url: str, **kwargs: Any):
        """GET request with auth header."""
        kwargs = self._inject_auth_header(kwargs)
        return super().get(url, **kwargs)

    def post(self, url: str, **kwargs: Any):
        """POST request with auth header."""
        kwargs = self._inject_auth_header(kwargs)
        return super().post(url, **kwargs)

    def put(self, url: str, **kwargs: Any):
        """PUT request with auth header."""
        kwargs = self._inject_auth_header(kwargs)
        return super().put(url, **kwargs)

    def patch(self, url: str, **kwargs: Any):
        """PATCH request with auth header."""
        kwargs = self._inject_auth_header(kwargs)
        return super().patch(url, **kwargs)

    def delete(self, url: str, **kwargs: Any):
        """DELETE request with auth header."""
        kwargs = self._inject_auth_header(kwargs)
        return super().delete(url, **kwargs)


@pytest.fixture
def auth_headers() -> dict[str, str]:
    """
    Provide authentication headers for API tests.

    Returns:
        Dictionary with X-API-Key header using test key from CI settings
    """
    return {"X-API-Key": "test-key-1"}


@pytest.fixture
def read_only_auth_headers() -> dict[str, str]:
    """
    Provide read-only authentication headers for API tests.

    Returns:
        Dictionary with X-API-Key header using read-only test key
    """
    return {"X-API-Key": "test-key-2"}
