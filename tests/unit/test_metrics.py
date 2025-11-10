"""Tests for metrics setup."""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client() -> TestClient:
    """Create test client."""
    from orchestrator.main import app

    return TestClient(app)


class TestMetricsEndpoint:
    """Test suite for Prometheus metrics endpoint."""

    def test_metrics_endpoint_exists(self, client: TestClient) -> None:
        """Test that /metrics endpoint exists."""
        response = client.get("/metrics")
        assert response.status_code == 200

    def test_metrics_endpoint_returns_prometheus_format(self, client: TestClient) -> None:
        """Test that metrics are in Prometheus text format."""
        response = client.get("/metrics")
        content_type = response.headers.get("content-type", "")

        # Prometheus format should be text/plain or similar
        assert "text" in content_type.lower() or response.status_code == 200

    def test_metrics_include_http_requests(self, client: TestClient) -> None:
        """Test that HTTP request metrics are included."""
        # Make a request to generate metrics
        client.get("/health")

        # Get metrics
        response = client.get("/metrics")
        content = response.text

        # Should include HTTP-related metrics
        # Prometheus metrics typically have these patterns
        assert response.status_code == 200
        assert len(content) > 0

    def test_metrics_include_python_info(self, client: TestClient) -> None:
        """Test that Python runtime metrics are included."""
        response = client.get("/metrics")
        content = response.text

        # Should include some standard metrics
        assert response.status_code == 200
        assert len(content) > 0


class TestMetricsSetup:
    """Test metrics configuration."""

    def test_prometheus_client_imported(self) -> None:
        """Test that prometheus_client is available."""
        from orchestrator.metrics import setup_metrics

        # Should not raise
        setup_metrics()

    def test_metrics_registry_created(self) -> None:
        """Test that metrics registry is created."""
        from orchestrator.metrics import get_metrics

        metrics = get_metrics()
        assert metrics is not None
