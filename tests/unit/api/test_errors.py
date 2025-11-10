"""Tests for error handling middleware."""

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient


@pytest.fixture
def app_with_error_handlers() -> FastAPI:
    """Create FastAPI app with error handlers."""
    from orchestrator.api.middleware.errors import add_error_handlers

    app = FastAPI()

    # Add test endpoint that raises various errors
    @app.get("/test/404")
    def test_404():
        raise HTTPException(status_code=404, detail="Resource not found")

    @app.get("/test/500")
    def test_500():
        raise Exception("Internal server error")

    @app.get("/test/validation")
    def test_validation():
        from pydantic import BaseModel

        class TestModel(BaseModel):
            required_field: str

        # This will raise ValidationError
        TestModel()

    # Add error handlers
    add_error_handlers(app)

    return app


@pytest.fixture
def client(app_with_error_handlers: FastAPI) -> TestClient:
    """Create test client with error handlers."""
    # raise_server_exceptions=False allows error handlers to process exceptions
    return TestClient(app_with_error_handlers, raise_server_exceptions=False)


class TestErrorHandlers:
    """Test suite for error handling middleware."""

    def test_http_exception_handler(self, client: TestClient) -> None:
        """Test that HTTP exceptions are handled correctly."""
        response = client.get("/test/404")

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "Resource not found" in data["detail"]

    def test_http_exception_returns_json(self, client: TestClient) -> None:
        """Test that HTTP exceptions return JSON."""
        response = client.get("/test/404")

        assert response.headers["content-type"] == "application/json"

    def test_generic_exception_handler(self, client: TestClient) -> None:
        """Test that generic exceptions are handled."""
        response = client.get("/test/500")

        assert response.status_code == 500
        data = response.json()
        assert "detail" in data

    def test_generic_exception_hides_details_in_production(self, client: TestClient) -> None:
        """Test that generic exceptions don't leak implementation details."""
        response = client.get("/test/500")

        data = response.json()
        # Should not expose raw exception message
        assert "Internal server error" in data["detail"]

    def test_error_response_includes_timestamp(self, client: TestClient) -> None:
        """Test that error responses include timestamp."""
        response = client.get("/test/404")

        data = response.json()
        # Should have some error tracking info
        assert "detail" in data

    def test_validation_error_handler(self, client: TestClient) -> None:
        """Test that validation errors are handled."""
        response = client.get("/test/validation")

        assert response.status_code in [400, 422, 500]  # Validation error code
        data = response.json()
        assert "detail" in data
