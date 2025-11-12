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
        # Set up default headers with auth key
        default_headers = {"X-API-Key": auth_key}

        # Merge with any existing headers from kwargs
        if "headers" in kwargs:
            # If headers provided, merge them (user headers take precedence)
            default_headers.update(kwargs["headers"])

        # Pass merged headers to parent
        kwargs["headers"] = default_headers
        super().__init__(app, **kwargs)


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
