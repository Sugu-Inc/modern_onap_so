"""Tests for configuration API endpoints."""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi import status
from tests.unit.api.conftest import AuthenticatedTestClient as TestClient

from orchestrator.main import app
from orchestrator.models.deployment import Deployment, DeploymentStatus


@pytest.fixture
def client() -> TestClient:
    """Create test client."""
    return TestClient(app, auth_key="dev-key-1", raise_server_exceptions=False)


@pytest.fixture
def mock_deployment_repository():  # type: ignore[no-untyped-def]
    """Mock deployment repository."""
    with patch("orchestrator.api.v1.configurations.DeploymentRepository") as mock_repo_class:
        mock_repo = AsyncMock()
        mock_repo_class.return_value = mock_repo
        yield mock_repo


class TestConfigureDeployment:
    """Test POST /deployments/{id}/configure endpoint."""

    def test_configure_deployment_success(
        self, client: TestClient, mock_deployment_repository: AsyncMock
    ) -> None:
        """Test successful configuration initiation."""
        deployment_id = uuid4()

        # Mock deployment exists and is in COMPLETED state
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

        # Mock configuration workflow
        with patch("orchestrator.api.v1.configurations.run_configure_workflow") as mock_workflow:
            mock_workflow.return_value = AsyncMock()

            # Execute request
            response = client.post(
                f"/v1/deployments/{deployment_id}/configure",
                json={
                    "playbook_path": "/playbooks/configure_web.yml",
                    "extra_vars": {"app_version": "1.2.3"},
                },
            )

        # Verify response
        assert response.status_code == status.HTTP_202_ACCEPTED
        data = response.json()
        assert data["deployment_id"] == str(deployment_id)
        assert data["status"] == "running"
        assert "execution_id" in data

    def test_configure_deployment_not_found(
        self, client: TestClient, mock_deployment_repository: AsyncMock
    ) -> None:
        """Test configuration when deployment doesn't exist."""
        deployment_id = uuid4()

        # Mock deployment not found
        mock_deployment_repository.get_by_id.return_value = None

        # Execute request
        response = client.post(
            f"/v1/deployments/{deployment_id}/configure",
            json={
                "playbook_path": "/playbooks/configure_web.yml",
            },
        )

        # Verify response
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.json()["detail"].lower()

    def test_configure_deployment_invalid_state(
        self, client: TestClient, mock_deployment_repository: AsyncMock
    ) -> None:
        """Test configuration when deployment is not in COMPLETED state."""
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
            f"/v1/deployments/{deployment_id}/configure",
            json={
                "playbook_path": "/playbooks/configure_web.yml",
            },
        )

        # Verify response
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "cannot be configured" in response.json()["detail"].lower()

    def test_configure_deployment_missing_playbook(self, client: TestClient) -> None:
        """Test configuration with missing playbook_path."""
        deployment_id = uuid4()

        # Execute request without playbook_path
        response = client.post(
            f"/v1/deployments/{deployment_id}/configure",
            json={
                "extra_vars": {"app_version": "1.2.3"},
            },
        )

        # Verify response
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_configure_deployment_empty_playbook(
        self, client: TestClient, mock_deployment_repository: AsyncMock
    ) -> None:
        """Test configuration with empty playbook_path."""
        deployment_id = uuid4()

        # Mock deployment exists
        mock_deployment = Deployment(
            id=deployment_id,
            name="test-deployment",
            status=DeploymentStatus.COMPLETED,
            template={"vm_config": {"flavor": "m1.small"}},
            parameters={},
            cloud_region="RegionOne",
        )
        mock_deployment_repository.get_by_id.return_value = mock_deployment

        # Execute request with empty playbook
        response = client.post(
            f"/v1/deployments/{deployment_id}/configure",
            json={
                "playbook_path": "",
            },
        )

        # Verify response
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_configure_deployment_with_limit(
        self, client: TestClient, mock_deployment_repository: AsyncMock
    ) -> None:
        """Test configuration with host limit."""
        deployment_id = uuid4()

        # Mock deployment exists
        mock_deployment = Deployment(
            id=deployment_id,
            name="test-deployment",
            status=DeploymentStatus.COMPLETED,
            template={"vm_config": {"flavor": "m1.small"}},
            parameters={},
            cloud_region="RegionOne",
            resources={
                "server_ids": ["server-1", "server-2"],
            },
        )
        mock_deployment_repository.get_by_id.return_value = mock_deployment

        # Mock configuration workflow
        with patch("orchestrator.api.v1.configurations.run_configure_workflow") as mock_workflow:
            mock_workflow.return_value = AsyncMock()

            # Execute request with limit
            response = client.post(
                f"/v1/deployments/{deployment_id}/configure",
                json={
                    "playbook_path": "/playbooks/configure_web.yml",
                    "limit": "server-1",
                },
            )

        # Verify response
        assert response.status_code == status.HTTP_202_ACCEPTED

    def test_configure_deployment_with_extra_vars(
        self, client: TestClient, mock_deployment_repository: AsyncMock
    ) -> None:
        """Test configuration with extra variables."""
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

        # Mock configuration workflow
        with patch("orchestrator.api.v1.configurations.run_configure_workflow") as mock_workflow:
            mock_workflow.return_value = AsyncMock()

            # Execute request with extra vars
            response = client.post(
                f"/v1/deployments/{deployment_id}/configure",
                json={
                    "playbook_path": "/playbooks/configure_web.yml",
                    "extra_vars": {
                        "app_version": "1.2.3",
                        "environment": "production",
                        "enable_ssl": True,
                    },
                },
            )

        # Verify response
        assert response.status_code == status.HTTP_202_ACCEPTED
        data = response.json()
        assert "execution_id" in data

    def test_configure_deployment_workflow_triggered(
        self, client: TestClient, mock_deployment_repository: AsyncMock
    ) -> None:
        """Test that configuration workflow is triggered correctly."""
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

        # Mock configuration workflow
        with patch("orchestrator.api.v1.configurations.run_configure_workflow") as mock_workflow:
            # Execute request
            response = client.post(
                f"/v1/deployments/{deployment_id}/configure",
                json={
                    "playbook_path": "/playbooks/configure_web.yml",
                    "extra_vars": {"key": "value"},
                    "limit": "server-1",
                },
            )

        # Verify workflow was called
        assert response.status_code == status.HTTP_202_ACCEPTED
        mock_workflow.assert_called_once()

        # Verify workflow was called with correct parameters
        call_kwargs = mock_workflow.call_args[1]
        assert call_kwargs["deployment_id"] == deployment_id
        assert call_kwargs["playbook_path"] == "/playbooks/configure_web.yml"
        assert call_kwargs["extra_vars"] == {"key": "value"}
        assert call_kwargs["limit"] == "server-1"
