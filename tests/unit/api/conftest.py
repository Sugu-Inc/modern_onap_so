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
        # Store auth key before passing to parent
        self._auth_key = auth_key
        # Initialize parent without auth_key in kwargs
        super().__init__(app, **kwargs)

    def request(self, method: str, url: str, **kwargs: Any):
        """Override request to add auth header."""
        # Inject auth header if not already present
        if "headers" not in kwargs:
            kwargs["headers"] = {}
        if isinstance(kwargs["headers"], dict):
            if "X-API-Key" not in kwargs["headers"] and "x-api-key" not in kwargs["headers"]:
                kwargs["headers"]["X-API-Key"] = self._auth_key
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
