"""Tests for health endpoint."""

import pytest
from tests.unit.api.conftest import AuthenticatedTestClient as TestClient


class TestHealthEndpoint:
    """Test suite for health endpoint."""

    def test_health_endpoint_exists(self, client: TestClient) -> None:
        """Test that health endpoint exists and returns 200."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_endpoint_returns_json(self, client: TestClient) -> None:
        """Test that health endpoint returns JSON response."""
        response = client.get("/health")
        assert response.headers["content-type"] == "application/json"

    def test_health_endpoint_structure(self, client: TestClient) -> None:
        """Test that health endpoint returns expected structure."""
        response = client.get("/health")
        data = response.json()

        assert "status" in data
        assert "version" in data
        assert "timestamp" in data

    def test_health_endpoint_status_healthy(self, client: TestClient) -> None:
        """Test that health endpoint returns healthy status."""
        response = client.get("/health")
        data = response.json()

        assert data["status"] == "healthy"

    def test_health_endpoint_includes_database_check(self, client: TestClient) -> None:
        """Test that health endpoint includes database status."""
        response = client.get("/health")
        data = response.json()

        assert "database" in data
        assert data["database"] in ["connected", "disconnected"]


@pytest.fixture
def client() -> TestClient:
    """Create a test client for the FastAPI app."""
    from orchestrator.main import app

    return TestClient(app, auth_key="test-key-1")
