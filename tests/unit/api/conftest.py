"""
Shared fixtures for API tests.
"""

import pytest
from fastapi.testclient import TestClient
from starlette.testclient import ASGI3App
from typing import Any


class AuthenticatedTestClient(TestClient):
    """Test client that automatically adds auth headers."""

    def __init__(self, app: ASGI3App, auth_key: str = "dev-key-1", **kwargs: Any):
        # Initialize parent first
        super().__init__(app, **kwargs)
        # Store auth key for later use
        self._auth_key = auth_key

    def request(self, method: str, url: str, **kwargs: Any):
        """Override request to inject auth header."""
        # Get existing headers or create new dict
        headers = kwargs.get("headers", {})

        # Convert to dict if needed (handle various input types)
        if not isinstance(headers, dict):
            headers = dict(headers) if headers else {}
        else:
            # Make a copy to avoid mutating the original
            headers = headers.copy()

        # Add auth header if not present
        if "X-API-Key" not in headers and "x-api-key" not in headers:
            headers["X-API-Key"] = self._auth_key

        # Update kwargs with merged headers
        kwargs["headers"] = headers

        return super().request(method, url, **kwargs)


@pytest.fixture
def auth_headers() -> dict[str, str]:
    """
    Provide authentication headers for API tests.

    Returns:
        Dictionary with X-API-Key header using dev key from settings
    """
    return {"X-API-Key": "dev-key-1"}


@pytest.fixture
def read_only_auth_headers() -> dict[str, str]:
    """
    Provide read-only authentication headers for API tests.

    Returns:
        Dictionary with X-API-Key header using read-only dev key
    """
    return {"X-API-Key": "dev-key-2"}
