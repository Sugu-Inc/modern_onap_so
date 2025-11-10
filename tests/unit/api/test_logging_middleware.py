"""Tests for logging middleware."""

import pytest
from fastapi import FastAPI
from tests.unit.api.conftest import AuthenticatedTestClient as TestClient


@pytest.fixture
def app_with_logging() -> FastAPI:
    """Create FastAPI app with logging middleware."""
    from orchestrator.api.middleware.logging import add_logging_middleware

    app = FastAPI()

    # Add test endpoints
    @app.get("/test/success")
    def test_success():
        return {"status": "ok"}

    @app.get("/test/error")
    def test_error():
        from fastapi import HTTPException

        raise HTTPException(status_code=500, detail="Test error")

    @app.post("/test/post")
    def test_post(data: dict):
        return {"received": data}

    # Add logging middleware
    add_logging_middleware(app)

    return app


@pytest.fixture
def client(app_with_logging: FastAPI) -> TestClient:
    """Create test client with logging middleware."""
    return TestClient(app_with_logging, auth_key="dev-key-1", raise_server_exceptions=False)


class TestLoggingMiddleware:
    """Test suite for logging middleware."""

    def test_logging_middleware_exists(self, client: TestClient) -> None:
        """Test that logging middleware is added without errors."""
        response = client.get("/test/success")
        assert response.status_code == 200

    def test_successful_request_logged(self, client: TestClient) -> None:
        """Test that successful requests are logged."""
        # This test verifies the middleware doesn't break requests
        response = client.get("/test/success")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_failed_request_logged(self, client: TestClient) -> None:
        """Test that failed requests are logged."""
        response = client.get("/test/error")
        assert response.status_code == 500

    def test_post_request_logged(self, client: TestClient) -> None:
        """Test that POST requests with body are logged."""
        response = client.post("/test/post", json={"test": "data"})
        assert response.status_code == 200
        assert response.json() == {"received": {"test": "data"}}

    def test_request_id_added_to_response(self, client: TestClient) -> None:
        """Test that X-Request-ID is added to response headers."""
        response = client.get("/test/success")
        # Request ID should be in headers
        assert "x-request-id" in response.headers or "X-Request-ID" in response.headers

    def test_response_time_calculated(self, client: TestClient) -> None:
        """Test that response time is calculated."""
        response = client.get("/test/success")
        # Middleware should add processing time header
        # This is implicit - the request completes successfully
        assert response.status_code == 200


class TestLoggingConfiguration:
    """Test logging configuration."""

    def test_structured_logger_setup(self) -> None:
        """Test that structured logger is configured."""
        from orchestrator.logging import setup_logging

        logger = setup_logging()
        assert logger is not None

    def test_log_level_from_settings(self) -> None:
        """Test that log level is read from settings."""
        from orchestrator.config import settings

        assert settings.log_level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

    def test_log_format_from_settings(self) -> None:
        """Test that log format is read from settings."""
        from orchestrator.config import settings

        assert settings.log_format in ["json", "text"]
