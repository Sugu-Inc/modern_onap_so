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

    def _add_auth_header(self, kwargs: dict) -> dict:
        """Add authentication header to request kwargs."""
        if "headers" not in kwargs or kwargs["headers"] is None:
            kwargs["headers"] = {}
        if "X-API-Key" not in kwargs["headers"]:
            kwargs["headers"]["X-API-Key"] = self.auth_key
        return kwargs

    def request(self, method: str, url: str, **kwargs):
        """Override request to add auth header."""
        kwargs = self._add_auth_header(kwargs)
        return super().request(method, url, **kwargs)

    def get(self, url: str, **kwargs):
        """GET request with auth header."""
        kwargs = self._add_auth_header(kwargs)
        return super().get(url, **kwargs)

    def post(self, url: str, **kwargs):
        """POST request with auth header."""
        kwargs = self._add_auth_header(kwargs)
        return super().post(url, **kwargs)

    def put(self, url: str, **kwargs):
        """PUT request with auth header."""
        kwargs = self._add_auth_header(kwargs)
        return super().put(url, **kwargs)

    def patch(self, url: str, **kwargs):
        """PATCH request with auth header."""
        kwargs = self._add_auth_header(kwargs)
        return super().patch(url, **kwargs)

    def delete(self, url: str, **kwargs):
        """DELETE request with auth header."""
        kwargs = self._add_auth_header(kwargs)
        return super().delete(url, **kwargs)


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
