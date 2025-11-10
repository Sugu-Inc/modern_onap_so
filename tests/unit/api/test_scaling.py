"""Tests for scaling API endpoints."""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from orchestrator.main import app
from orchestrator.models.deployment import Deployment, DeploymentStatus


@pytest.fixture
def client() -> TestClient:
    """Create test client."""
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def mock_deployment_repository():  # type: ignore[no-untyped-def]
    """Mock deployment repository."""
    with patch("orchestrator.api.v1.scaling.DeploymentRepository") as mock_repo_class:
        mock_repo = AsyncMock()
        mock_repo_class.return_value = mock_repo
        yield mock_repo


class TestScaleDeployment:
    """Test POST /deployments/{id}/scale endpoint."""

    def test_scale_out_success(
        self, client: TestClient, mock_deployment_repository: AsyncMock
    ) -> None:
        """Test successful scale-out operation."""
        deployment_id = uuid4()

        # Mock deployment exists with 2 VMs
        mock_deployment = Deployment(
            id=deployment_id,
            name="test-deployment",
            status=DeploymentStatus.COMPLETED,
            template={"vm_config": {"flavor": "m1.small"}},
            parameters={},
            cloud_region="RegionOne",
            resources={
                "server_ids": ["server-1", "server-2"],
                "network_id": "network-123",
            },
        )
        mock_deployment_repository.get_by_id.return_value = mock_deployment

        # Mock scaling workflow
        execution_id = uuid4()
        with patch("orchestrator.api.v1.scaling.run_scale_workflow") as mock_workflow:
            mock_workflow.return_value = execution_id

            # Execute scale-out request (2 → 4 VMs)
            response = client.post(
                f"/v1/deployments/{deployment_id}/scale",
                json={
                    "target_count": 4,
                    "min_count": 1,
                },
            )

        # Verify response
        assert response.status_code == status.HTTP_202_ACCEPTED
        data = response.json()
        assert data["deployment_id"] == str(deployment_id)
        assert data["status"] == "running"
        assert data["current_count"] == 2
        assert data["target_count"] == 4
        assert data["operation"] == "scale-out"
        assert "execution_id" in data

    def test_scale_in_success(
        self, client: TestClient, mock_deployment_repository: AsyncMock
    ) -> None:
        """Test successful scale-in operation."""
        deployment_id = uuid4()

        # Mock deployment exists with 4 VMs
        mock_deployment = Deployment(
            id=deployment_id,
            name="test-deployment",
            status=DeploymentStatus.COMPLETED,
            template={"vm_config": {"flavor": "m1.small"}},
            parameters={},
            cloud_region="RegionOne",
            resources={
                "server_ids": ["server-1", "server-2", "server-3", "server-4"],
                "network_id": "network-123",
            },
        )
        mock_deployment_repository.get_by_id.return_value = mock_deployment

        # Mock scaling workflow
        execution_id = uuid4()
        with patch("orchestrator.api.v1.scaling.run_scale_workflow") as mock_workflow:
            mock_workflow.return_value = execution_id

            # Execute scale-in request (4 → 2 VMs)
            response = client.post(
                f"/v1/deployments/{deployment_id}/scale",
                json={
                    "target_count": 2,
                    "min_count": 1,
                },
            )

        # Verify response
        assert response.status_code == status.HTTP_202_ACCEPTED
        data = response.json()
        assert data["deployment_id"] == str(deployment_id)
        assert data["status"] == "running"
        assert data["current_count"] == 4
        assert data["target_count"] == 2
        assert data["operation"] == "scale-in"

    def test_scale_no_change(
        self, client: TestClient, mock_deployment_repository: AsyncMock
    ) -> None:
        """Test scaling when current count equals target count."""
        deployment_id = uuid4()

        # Mock deployment exists with 2 VMs
        mock_deployment = Deployment(
            id=deployment_id,
            name="test-deployment",
            status=DeploymentStatus.COMPLETED,
            template={"vm_config": {"flavor": "m1.small"}},
            parameters={},
            cloud_region="RegionOne",
            resources={
                "server_ids": ["server-1", "server-2"],
                "network_id": "network-123",
            },
        )
        mock_deployment_repository.get_by_id.return_value = mock_deployment

        # Mock scaling workflow
        execution_id = uuid4()
        with patch("orchestrator.api.v1.scaling.run_scale_workflow") as mock_workflow:
            mock_workflow.return_value = execution_id

            # Execute scale request with same count (2 → 2 VMs)
            response = client.post(
                f"/v1/deployments/{deployment_id}/scale",
                json={
                    "target_count": 2,
                    "min_count": 1,
                },
            )

        # Verify response
        assert response.status_code == status.HTTP_202_ACCEPTED
        data = response.json()
        assert data["operation"] == "none"

    def test_scale_deployment_not_found(
        self, client: TestClient, mock_deployment_repository: AsyncMock
    ) -> None:
        """Test scaling when deployment doesn't exist."""
        deployment_id = uuid4()

        # Mock deployment not found
        mock_deployment_repository.get_by_id.return_value = None

        # Execute request
        response = client.post(
            f"/v1/deployments/{deployment_id}/scale",
            json={
                "target_count": 3,
            },
        )

        # Verify response
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.json()["detail"].lower()

    def test_scale_deployment_invalid_state(
        self, client: TestClient, mock_deployment_repository: AsyncMock
    ) -> None:
        """Test scaling when deployment is not in COMPLETED state."""
        deployment_id = uuid4()

        # Mock deployment exists but in PENDING state
        mock_deployment = Deployment(
            id=deployment_id,
            name="test-deployment",
            status=DeploymentStatus.PENDING,
            template={"vm_config": {"flavor": "m1.small"}},
            parameters={},
            cloud_region="RegionOne",
        )
        mock_deployment_repository.get_by_id.return_value = mock_deployment

        # Execute request
        response = client.post(
            f"/v1/deployments/{deployment_id}/scale",
            json={
                "target_count": 3,
            },
        )

        # Verify response
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "cannot be scaled" in response.json()["detail"].lower()

    def test_scale_missing_target_count(self, client: TestClient) -> None:
        """Test scaling with missing target_count."""
        deployment_id = uuid4()

        # Execute request without target_count
        response = client.post(
            f"/v1/deployments/{deployment_id}/scale",
            json={},
        )

        # Verify response
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_scale_invalid_target_count(self, client: TestClient) -> None:
        """Test scaling with target_count less than min_count."""
        deployment_id = uuid4()

        # Execute request with target_count < min_count
        # This should fail validation before reaching the endpoint
        response = client.post(
            f"/v1/deployments/{deployment_id}/scale",
            json={
                "target_count": 1,
                "min_count": 2,
            },
        )

        # Verify response
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_scale_exceeds_max_count(
        self, client: TestClient, mock_deployment_repository: AsyncMock
    ) -> None:
        """Test scaling when target_count exceeds max_count."""
        deployment_id = uuid4()

        # Mock deployment exists
        mock_deployment = Deployment(
            id=deployment_id,
            name="test-deployment",
            status=DeploymentStatus.COMPLETED,
            template={"vm_config": {"flavor": "m1.small"}},
            parameters={},
            cloud_region="RegionOne",
            resources={"server_ids": ["server-1"]},
        )
        mock_deployment_repository.get_by_id.return_value = mock_deployment

        # Execute request with target_count > max_count
        response = client.post(
            f"/v1/deployments/{deployment_id}/scale",
            json={
                "target_count": 10,
                "min_count": 1,
                "max_count": 5,
            },
        )

        # Verify response
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "exceeds max_count" in response.json()["detail"].lower()

    def test_scale_with_max_count(
        self, client: TestClient, mock_deployment_repository: AsyncMock
    ) -> None:
        """Test scaling with max_count validation."""
        deployment_id = uuid4()

        # Mock deployment exists
        mock_deployment = Deployment(
            id=deployment_id,
            name="test-deployment",
            status=DeploymentStatus.COMPLETED,
            template={"vm_config": {"flavor": "m1.small"}},
            parameters={},
            cloud_region="RegionOne",
            resources={"server_ids": ["server-1"]},
        )
        mock_deployment_repository.get_by_id.return_value = mock_deployment

        # Mock scaling workflow
        execution_id = uuid4()
        with patch("orchestrator.api.v1.scaling.run_scale_workflow") as mock_workflow:
            mock_workflow.return_value = execution_id

            # Execute request with valid max_count
            response = client.post(
                f"/v1/deployments/{deployment_id}/scale",
                json={
                    "target_count": 3,
                    "min_count": 1,
                    "max_count": 5,
                },
            )

        # Verify response
        assert response.status_code == status.HTTP_202_ACCEPTED
        data = response.json()
        assert data["target_count"] == 3
