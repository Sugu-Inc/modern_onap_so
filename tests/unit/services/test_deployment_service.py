"""Tests for DeploymentService."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from orchestrator.models.deployment import Deployment, DeploymentStatus
from orchestrator.schemas.deployment import (
    CreateDeploymentRequest,
    DeploymentResponse,
)


def create_mock_deployment(**kwargs):
    """Create a mock deployment with all required attributes."""
    defaults = {
        "id": kwargs.get("id", uuid4()),
        "name": "test-deployment",
        "status": DeploymentStatus.PENDING,
        "template": {"vm_config": {"flavor": "m1.small", "image": "ubuntu-20.04"}},
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
    mock = MagicMock(spec=Deployment)
    for key, value in defaults.items():
        setattr(mock, key, value)
    return mock


@pytest.fixture
def mock_repository() -> AsyncMock:
    """Mock deployment repository."""
    return AsyncMock()


@pytest.fixture
def mock_workflow_client() -> AsyncMock:
    """Mock Temporal workflow client."""
    return AsyncMock()


@pytest.fixture
def deployment_service(mock_repository: AsyncMock, mock_workflow_client: AsyncMock):
    """Create DeploymentService with mocked dependencies."""
    from orchestrator.services.deployment_service import DeploymentService

    return DeploymentService(repository=mock_repository, workflow_client=mock_workflow_client)


class TestCreateDeployment:
    """Test create_deployment method."""

    @pytest.mark.asyncio
    async def test_create_deployment_success(
        self,
        deployment_service,
        mock_repository: AsyncMock,
        mock_workflow_client: AsyncMock,
    ) -> None:
        """Test successful deployment creation."""
        request = CreateDeploymentRequest(
            name="test-deployment",
            cloud_region="RegionOne",
            template={"vm_config": {"flavor": "m1.small", "image": "ubuntu-20.04"}},
            parameters={"env": "test"},
        )

        deployment_id = uuid4()
        mock_deployment = create_mock_deployment(
            id=deployment_id, name=request.name, status=DeploymentStatus.PENDING
        )
        mock_repository.create.return_value = mock_deployment

        result = await deployment_service.create_deployment(request)

        # Verify repository was called
        mock_repository.create.assert_called_once()
        created_deployment = mock_repository.create.call_args[0][0]
        assert created_deployment.name == request.name
        assert created_deployment.status == DeploymentStatus.PENDING

        # Verify workflow was triggered
        mock_workflow_client.start_deployment_workflow.assert_called_once_with(deployment_id)

        # Verify response
        assert isinstance(result, DeploymentResponse)
        assert result.id == deployment_id
        assert result.status == DeploymentStatus.PENDING

    @pytest.mark.asyncio
    async def test_create_deployment_with_empty_template(
        self, deployment_service, mock_repository: AsyncMock
    ) -> None:
        """Test deployment creation with empty template raises error."""
        # Empty template validation happens at the Pydantic schema level
        with pytest.raises(ValueError, match="Template cannot be empty"):
            CreateDeploymentRequest(
                name="test-deployment",
                cloud_region="RegionOne",
                template={},  # Empty template
                parameters={},
            )

        # Repository should not be called
        mock_repository.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_deployment_workflow_trigger_fails(
        self,
        deployment_service,
        mock_repository: AsyncMock,
        mock_workflow_client: AsyncMock,
    ) -> None:
        """Test that deployment is created even if workflow trigger fails."""
        request = CreateDeploymentRequest(
            name="test-deployment",
            cloud_region="RegionOne",
            template={"vm_config": {"flavor": "m1.small", "image": "ubuntu-20.04"}},
            parameters={},
        )

        deployment_id = uuid4()
        mock_deployment = create_mock_deployment(id=deployment_id)
        mock_repository.create.return_value = mock_deployment
        mock_workflow_client.start_deployment_workflow.side_effect = Exception(
            "Workflow client error"
        )

        # Should still return the deployment even if workflow fails
        result = await deployment_service.create_deployment(request)

        assert isinstance(result, DeploymentResponse)
        mock_repository.create.assert_called_once()


class TestGetDeployment:
    """Test get_deployment method."""

    @pytest.mark.asyncio
    async def test_get_deployment_success(
        self, deployment_service, mock_repository: AsyncMock
    ) -> None:
        """Test successful deployment retrieval."""
        deployment_id = uuid4()
        mock_deployment = create_mock_deployment(
            id=deployment_id, status=DeploymentStatus.COMPLETED
        )
        mock_repository.get_by_id.return_value = mock_deployment

        result = await deployment_service.get_deployment(deployment_id)

        assert isinstance(result, DeploymentResponse)
        assert result.id == deployment_id
        mock_repository.get_by_id.assert_called_once_with(deployment_id)

    @pytest.mark.asyncio
    async def test_get_deployment_not_found(
        self, deployment_service, mock_repository: AsyncMock
    ) -> None:
        """Test getting non-existent deployment returns None."""
        deployment_id = uuid4()
        mock_repository.get_by_id.return_value = None

        result = await deployment_service.get_deployment(deployment_id)

        assert result is None
        mock_repository.get_by_id.assert_called_once_with(deployment_id)


class TestListDeployments:
    """Test list_deployments method."""

    @pytest.mark.asyncio
    async def test_list_deployments_success(
        self, deployment_service, mock_repository: AsyncMock
    ) -> None:
        """Test successful deployment listing."""
        mock_deployment1 = create_mock_deployment(id=uuid4(), name="deployment-1")
        mock_deployment2 = create_mock_deployment(id=uuid4(), name="deployment-2")

        mock_repository.list.return_value = [mock_deployment1, mock_deployment2]
        mock_repository.count.return_value = 2

        deployments, total = await deployment_service.list_deployments(limit=10, offset=0)

        assert len(deployments) == 2
        assert total == 2
        assert all(isinstance(d, DeploymentResponse) for d in deployments)
        mock_repository.list.assert_called_once_with(
            status=None, cloud_region=None, limit=10, offset=0
        )
        mock_repository.count.assert_called_once_with(status=None, cloud_region=None)

    @pytest.mark.asyncio
    async def test_list_deployments_with_filters(
        self, deployment_service, mock_repository: AsyncMock
    ) -> None:
        """Test listing deployments with status filter."""
        mock_deployment = create_mock_deployment(id=uuid4(), status=DeploymentStatus.COMPLETED)

        mock_repository.list.return_value = [mock_deployment]
        mock_repository.count.return_value = 1

        deployments, total = await deployment_service.list_deployments(
            status=DeploymentStatus.COMPLETED, cloud_region="RegionOne", limit=10, offset=0
        )

        assert len(deployments) == 1
        assert total == 1
        mock_repository.list.assert_called_once_with(
            status=DeploymentStatus.COMPLETED,
            cloud_region="RegionOne",
            limit=10,
            offset=0,
        )

    @pytest.mark.asyncio
    async def test_list_deployments_empty(
        self, deployment_service, mock_repository: AsyncMock
    ) -> None:
        """Test listing when no deployments exist."""
        mock_repository.list.return_value = []
        mock_repository.count.return_value = 0

        deployments, total = await deployment_service.list_deployments(limit=10, offset=0)

        assert len(deployments) == 0
        assert total == 0


class TestUpdateDeployment:
    """Test update_deployment method."""

    @pytest.mark.asyncio
    async def test_update_deployment_success(
        self, deployment_service, mock_repository: AsyncMock
    ) -> None:
        """Test successful deployment update."""
        deployment_id = uuid4()
        mock_deployment = create_mock_deployment(id=deployment_id)
        mock_repository.update.return_value = mock_deployment

        result = await deployment_service.update_deployment(
            deployment_id, status=DeploymentStatus.COMPLETED
        )

        assert isinstance(result, DeploymentResponse)
        mock_repository.update.assert_called_once_with(
            deployment_id, status=DeploymentStatus.COMPLETED
        )

    @pytest.mark.asyncio
    async def test_update_deployment_not_found(
        self, deployment_service, mock_repository: AsyncMock
    ) -> None:
        """Test updating non-existent deployment returns None."""
        deployment_id = uuid4()
        mock_repository.update.return_value = None

        result = await deployment_service.update_deployment(
            deployment_id, status=DeploymentStatus.FAILED
        )

        assert result is None


class TestDeleteDeployment:
    """Test delete_deployment method."""

    @pytest.mark.asyncio
    async def test_delete_deployment_success(
        self, deployment_service, mock_repository: AsyncMock
    ) -> None:
        """Test successful deployment deletion."""
        deployment_id = uuid4()
        mock_repository.delete.return_value = True

        result = await deployment_service.delete_deployment(deployment_id)

        assert result is True
        mock_repository.delete.assert_called_once_with(deployment_id)

    @pytest.mark.asyncio
    async def test_delete_deployment_not_found(
        self, deployment_service, mock_repository: AsyncMock
    ) -> None:
        """Test deleting non-existent deployment returns False."""
        deployment_id = uuid4()
        mock_repository.delete.return_value = False

        result = await deployment_service.delete_deployment(deployment_id)

        assert result is False
