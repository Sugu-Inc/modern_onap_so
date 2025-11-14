"""
Unit tests for API authentication middleware.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from orchestrator.api.middleware.auth import (
    APIKeyAuth,
    AuthContext,
    add_auth_middleware,
    get_auth_context,
)


class TestAPIKeyAuth:
    """Test APIKeyAuth middleware."""

    def test_parse_api_keys(self) -> None:
        """Test parsing API keys from config string."""
        api_keys_str = "key1:write,key2:read,key3:write"
        auth = APIKeyAuth(api_keys_str)

        assert auth.api_keys == {
            "key1": "write",
            "key2": "read",
            "key3": "write",
        }

    def test_validate_api_key_valid_write(self) -> None:
        """Test validating write API key."""
        auth = APIKeyAuth("test-key:write")
        result = auth.validate_api_key("test-key")

        assert result is not None
        assert result.api_key == "test-key"
        assert result.permission == "write"
        assert result.can_write is True
        assert result.can_read is True

    def test_validate_api_key_valid_read(self) -> None:
        """Test validating read API key."""
        auth = APIKeyAuth("test-key:read")
        result = auth.validate_api_key("test-key")

        assert result is not None
        assert result.api_key == "test-key"
        assert result.permission == "read"
        assert result.can_write is False
        assert result.can_read is True

    def test_validate_api_key_invalid(self) -> None:
        """Test validating invalid API key."""
        auth = APIKeyAuth("valid-key:write")
        result = auth.validate_api_key("invalid-key")

        assert result is None

    def test_validate_api_key_empty(self) -> None:
        """Test validating empty API key."""
        auth = APIKeyAuth("valid-key:write")
        result = auth.validate_api_key("")

        assert result is None

    def test_validate_api_key_none(self) -> None:
        """Test validating None API key."""
        auth = APIKeyAuth("valid-key:write")
        result = auth.validate_api_key(None)

        assert result is None


class TestAuthMiddleware:
    """Test auth middleware integration."""

    @pytest.mark.asyncio
    async def test_middleware_allows_health_endpoint(self) -> None:
        """Test that health endpoints are exempt from auth."""
        app = FastAPI()
        add_auth_middleware(app, "test-key:write")

        @app.get("/health")
        async def health() -> dict:
            return {"status": "ok"}

        # Create test client
        from httpx import AsyncClient, ASGITransport

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    @pytest.mark.asyncio
    async def test_middleware_allows_docs_endpoint(self) -> None:
        """Test that docs endpoints are exempt from auth."""
        app = FastAPI()
        add_auth_middleware(app, "test-key:write")

        # FastAPI auto-creates /docs endpoint
        from httpx import AsyncClient, ASGITransport

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/docs")

        # Docs endpoint should be accessible (302 or 200)
        assert response.status_code in (200, 404)  # 404 if docs disabled

    @pytest.mark.asyncio
    async def test_middleware_blocks_protected_endpoint_without_key(self) -> None:
        """Test that protected endpoints require API key."""
        app = FastAPI()
        add_auth_middleware(app, "test-key:write")

        @app.get("/api/data")
        async def get_data() -> dict:
            return {"data": "secret"}

        from httpx import AsyncClient, ASGITransport

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/data")

        assert response.status_code == 401
        assert "detail" in response.json()
        assert "API key required" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_middleware_blocks_protected_endpoint_with_invalid_key(self) -> None:
        """Test that invalid API key is rejected."""
        app = FastAPI()
        add_auth_middleware(app, "valid-key:write")

        @app.get("/api/data")
        async def get_data() -> dict:
            return {"data": "secret"}

        from httpx import AsyncClient, ASGITransport

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/data",
                headers={"X-API-Key": "invalid-key"},
            )

        assert response.status_code == 401
        assert "detail" in response.json()
        assert "Invalid API key" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_middleware_allows_protected_endpoint_with_valid_key(self) -> None:
        """Test that valid API key allows access."""
        app = FastAPI()
        add_auth_middleware(app, "valid-key:write")

        @app.get("/api/data")
        async def get_data() -> dict:
            return {"data": "secret"}

        from httpx import AsyncClient, ASGITransport

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/data",
                headers={"X-API-Key": "valid-key"},
            )

        assert response.status_code == 200
        assert response.json() == {"data": "secret"}

    @pytest.mark.asyncio
    async def test_middleware_blocks_write_endpoint_with_read_key(self) -> None:
        """Test that read-only key cannot access write endpoints."""
        app = FastAPI()
        add_auth_middleware(app, "read-key:read")

        @app.post("/api/data")
        async def create_data() -> dict:
            return {"id": "123"}

        from httpx import AsyncClient, ASGITransport

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/data",
                headers={"X-API-Key": "read-key"},
                json={"name": "test"},
            )

        assert response.status_code == 403
        assert "detail" in response.json()
        assert "write permission required" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_middleware_allows_read_endpoint_with_read_key(self) -> None:
        """Test that read key can access GET endpoints."""
        app = FastAPI()
        add_auth_middleware(app, "read-key:read")

        @app.get("/api/data")
        async def get_data() -> dict:
            return {"data": "public"}

        from httpx import AsyncClient, ASGITransport

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/data",
                headers={"X-API-Key": "read-key"},
            )

        assert response.status_code == 200
        assert response.json() == {"data": "public"}

    @pytest.mark.asyncio
    async def test_auth_context_available_in_endpoint(self) -> None:
        """Test that auth context is available in endpoint."""
        app = FastAPI()
        add_auth_middleware(app, "test-key:write")

        @app.get("/api/me")
        async def get_me(request: Request) -> dict:
            auth = get_auth_context(request)
            return {
                "api_key": auth.api_key,
                "permission": auth.permission,
                "can_write": auth.can_write,
            }

        from httpx import AsyncClient, ASGITransport

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/me",
                headers={"X-API-Key": "test-key"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["api_key"] == "test-key"
        assert data["permission"] == "write"
        assert data["can_write"] is True


class TestAuthContext:
    """Test AuthContext dataclass."""

    def test_auth_context_write_permissions(self) -> None:
        """Test write permission context."""
        ctx = AuthContext(api_key="key", permission="write")
        assert ctx.can_write is True
        assert ctx.can_read is True

    def test_auth_context_read_permissions(self) -> None:
        """Test read permission context."""
        ctx = AuthContext(api_key="key", permission="read")
        assert ctx.can_write is False
        assert ctx.can_read is True
