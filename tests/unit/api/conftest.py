"""
Shared fixtures for API tests.
"""

import pytest
from fastapi.testclient import TestClient


class AuthenticatedTestClient(TestClient):
    """Test client that automatically adds auth headers."""

    def __init__(self, *args, **kwargs):
        self.auth_key = kwargs.pop("auth_key", "dev-key-1")
        super().__init__(*args, **kwargs)

    def request(self, method: str, url: str, **kwargs):
        """Override request to add auth header."""
        if "headers" not in kwargs or kwargs["headers"] is None:
            kwargs["headers"] = {}
        if "X-API-Key" not in kwargs["headers"]:
            kwargs["headers"]["X-API-Key"] = self.auth_key
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
