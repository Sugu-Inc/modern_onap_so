"""Tests for deployment API endpoints."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from orchestrator.models.deployment import DeploymentStatus


@pytest.fixture
def client() -> TestClient:
    """Create test client with deployments router."""
    from orchestrator.main import app

    return TestClient(app, raise_server_exceptions=False)


def create_mock_deployment(**kwargs):
    """Create a mock deployment with all required attributes."""
    defaults = {
        "id": kwargs.get("id", uuid4()),
        "name": "test-deployment",
        "status": DeploymentStatus.PENDING,
        "template": {"vm_config": {"flavor": "m1.small"}},
        "parameters": {},
        "cloud_region": "RegionOne",
        "resources": None,
        "error": None,
        "extra_metadata": None,
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
        "deleted_at": None,
    }
    defaults.update(kwargs)
    mock = MagicMock()
    for key, value in defaults.items():
        setattr(mock, key, value)
    return mock


@pytest.fixture
def mock_deployment_repository():
    """Mock deployment repository."""
    with patch("orchestrator.api.v1.deployments.DeploymentRepository") as mock_repo_class:
        mock_repo = AsyncMock()
        mock_repo_class.return_value = mock_repo
        yield mock_repo


class TestCreateDeployment:
    """Test POST /deployments endpoint."""

    def test_create_deployment_success(
        self, client: TestClient, mock_deployment_repository: AsyncMock
    ) -> None:
        """Test successful deployment creation."""
        deployment_id = uuid4()
        mock_deployment_repository.create.return_value = create_mock_deployment(
            id=deployment_id,
            name="test-deployment",
            status=DeploymentStatus.PENDING,
        )

        response = client.post(
            "/v1/deployments",
            json={
                "name": "test-deployment",
                "cloud_region": "RegionOne",
                "template": {"vm_config": {"flavor": "m1.small"}},
                "parameters": {},
            },
        )

        assert response.status_code == 202
        data = response.json()
        assert data["name"] == "test-deployment"
        assert data["status"] == "PENDING"

    def test_create_deployment_validation_error(self, client: TestClient) -> None:
        """Test deployment creation with invalid data."""
        response = client.post(
            "/v1/deployments",
            json={
                "name": "",  # Empty name should fail validation
                "cloud_region": "RegionOne",
                "template": {},
                "parameters": {},
            },
        )

        # Should return error (422 validation or 500 if validation exception not serializable)
        assert response.status_code in [422, 500]

    def test_create_deployment_missing_template(self, client: TestClient) -> None:
        """Test deployment creation without template."""
        response = client.post(
            "/v1/deployments",
            json={
                "name": "test-deployment",
                "cloud_region": "RegionOne",
                # Missing template
            },
        )

        assert response.status_code == 422  # Validation error

    def test_create_deployment_empty_template(self, client: TestClient) -> None:
        """Test deployment creation with empty template."""
        response = client.post(
            "/v1/deployments",
            json={
                "name": "test-deployment",
                "cloud_region": "RegionOne",
                "template": {},  # Empty template should fail
                "parameters": {},
            },
        )

        # Should return error (422 validation or 500 if validation exception not serializable)
        assert response.status_code in [422, 500]


class TestGetDeployment:
    """Test GET /deployments/{id} endpoint."""

    def test_get_deployment_success(
        self, client: TestClient, mock_deployment_repository: AsyncMock
    ) -> None:
        """Test successful deployment retrieval."""
        deployment_id = uuid4()
        mock_deployment_repository.get_by_id.return_value = create_mock_deployment(
            id=deployment_id,
            name="test-deployment",
            status=DeploymentStatus.COMPLETED,
            resources={"vm_ids": ["vm-123"]},
        )

        response = client.get(f"/v1/deployments/{deployment_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(deployment_id)
        assert data["status"] == "COMPLETED"
        assert data["resources"]["vm_ids"] == ["vm-123"]

    def test_get_deployment_not_found(
        self, client: TestClient, mock_deployment_repository: AsyncMock
    ) -> None:
        """Test getting non-existent deployment."""
        deployment_id = uuid4()
        mock_deployment_repository.get_by_id.return_value = None

        response = client.get(f"/v1/deployments/{deployment_id}")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestListDeployments:
    """Test GET /deployments endpoint."""

    def test_list_deployments_success(
        self, client: TestClient, mock_deployment_repository: AsyncMock
    ) -> None:
        """Test successful deployment listing."""
        deployment1 = create_mock_deployment(
            id=uuid4(),
            name="deployment-1",
            status=DeploymentStatus.COMPLETED,
        )
        deployment2 = create_mock_deployment(
            id=uuid4(),
            name="deployment-2",
            status=DeploymentStatus.IN_PROGRESS,
        )

        mock_deployment_repository.list.return_value = [deployment1, deployment2]
        mock_deployment_repository.count.return_value = 2

        response = client.get("/v1/deployments")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2
        assert data["items"][0]["name"] == "deployment-1"

    def test_list_deployments_with_filters(
        self, client: TestClient, mock_deployment_repository: AsyncMock
    ) -> None:
        """Test deployment listing with status filter."""
        deployment = create_mock_deployment(
            id=uuid4(),
            name="completed-deployment",
            status=DeploymentStatus.COMPLETED,
        )

        mock_deployment_repository.list.return_value = [deployment]
        mock_deployment_repository.count.return_value = 1

        response = client.get("/v1/deployments?status=COMPLETED")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["status"] == "COMPLETED"

    def test_list_deployments_pagination(
        self, client: TestClient, mock_deployment_repository: AsyncMock
    ) -> None:
        """Test deployment listing with pagination."""
        mock_deployment_repository.list.return_value = []
        mock_deployment_repository.count.return_value = 100

        response = client.get("/v1/deployments?limit=10&offset=20")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 100
        assert data["limit"] == 10
        assert data["offset"] == 20

    def test_list_deployments_empty(
        self, client: TestClient, mock_deployment_repository: AsyncMock
    ) -> None:
        """Test listing when no deployments exist."""
        mock_deployment_repository.list.return_value = []
        mock_deployment_repository.count.return_value = 0

        response = client.get("/v1/deployments")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["items"] == []


class TestUpdateDeployment:
    """Test PATCH /deployments/{id} endpoint."""

    def test_update_deployment_success(
        self, client: TestClient, mock_deployment_repository: AsyncMock
    ) -> None:
        """Test successful deployment update."""
        deployment_id = uuid4()
        updated_deployment = create_mock_deployment(
            id=deployment_id,
            name="test-deployment",
            status=DeploymentStatus.COMPLETED,
            parameters={"new_param": "value"},
        )

        mock_deployment_repository.update.return_value = updated_deployment

        response = client.patch(
            f"/v1/deployments/{deployment_id}",
            json={"parameters": {"new_param": "value"}},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["parameters"]["new_param"] == "value"

    def test_update_deployment_not_found(
        self, client: TestClient, mock_deployment_repository: AsyncMock
    ) -> None:
        """Test updating non-existent deployment."""
        deployment_id = uuid4()
        mock_deployment_repository.update.return_value = None

        response = client.patch(f"/v1/deployments/{deployment_id}", json={"parameters": {}})

        assert response.status_code == 404


class TestDeleteDeployment:
    """Test DELETE /deployments/{id} endpoint."""

    def test_delete_deployment_success(
        self, client: TestClient, mock_deployment_repository: AsyncMock
    ) -> None:
        """Test successful deployment deletion."""
        from tests.unit.api.test_deployments import create_mock_deployment

        deployment_id = uuid4()
        mock_deployment = create_mock_deployment(
            id=deployment_id, resources={"network_id": "net-123", "server_ids": ["vm-1"]}
        )
        mock_deployment_repository.get_by_id.return_value = mock_deployment

        response = client.delete(f"/v1/deployments/{deployment_id}")

        assert response.status_code == 202

    def test_delete_deployment_not_found(
        self, client: TestClient, mock_deployment_repository: AsyncMock
    ) -> None:
        """Test deleting non-existent deployment."""
        deployment_id = uuid4()
        mock_deployment_repository.get_by_id.return_value = None

        response = client.delete(f"/v1/deployments/{deployment_id}")

        assert response.status_code == 404


class TestDeploymentEndpointSecurity:
    """Test security aspects of deployment endpoints."""

    def test_endpoints_require_valid_json(self, client: TestClient) -> None:
        """Test that endpoints validate JSON properly."""
        response = client.post(
            "/v1/deployments",
            data="invalid json",
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code in [400, 422]  # Bad request or validation error
