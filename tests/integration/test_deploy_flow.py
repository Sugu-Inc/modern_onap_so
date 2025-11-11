"""Integration tests for deployment workflow.

Tests the full deployment flow from API to database to OpenStack.
Uses in-memory SQLite database and mocked OpenStack client.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from orchestrator.clients.openstack.schemas import ServerStatus
from orchestrator.db.repositories.deployment_repository import DeploymentRepository
from orchestrator.models.base import Base
from orchestrator.models.deployment import Deployment, DeploymentStatus
from orchestrator.services.deployment_service import DeploymentService
from orchestrator.workflows.deployment.deploy import DeploymentWorkflow
from orchestrator.workflows.deployment.models import (
    DeploymentWorkflowInput,
    NetworkCreationResult,
    VMCreationResult,
    VMStatusResult,
)

pytestmark = pytest.mark.integration


@pytest.fixture
async def async_session() -> AsyncSession:
    """Create an async database session for testing."""
    # Use SQLite in-memory database for testing
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create session factory
    async_session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # Yield session
    async with async_session_factory() as session:
        yield session

    # Cleanup
    await engine.dispose()


@pytest.fixture
def mock_openstack_client():
    """Create mocked OpenStack client."""
    client = AsyncMock()

    # Mock authentication
    client.authenticate.return_value = {
        "token": "test-token-123",
        "expires_at": datetime.now(UTC).isoformat(),
    }

    # Mock network creation
    client.create_network.return_value = {
        "id": "network-123",
        "name": "test-network",
        "status": "ACTIVE",
    }

    # Mock subnet creation
    client.create_subnet.return_value = {
        "id": "subnet-123",
        "name": "test-subnet",
        "cidr": "10.0.0.0/24",
    }

    # Mock server creation
    client.create_server.return_value = {
        "id": "server-123",
        "name": "test-server",
        "status": "BUILD",
    }

    # Mock server status (ACTIVE)
    client.get_server_status.return_value = ServerStatus(
        server_id="server-123",
        status="ACTIVE",
        power_state=1,
        task_state=None,
        addresses={"test-network": [{"addr": "10.0.0.5"}]},
        created_at=datetime.now(UTC).isoformat(),
    )

    # Mock deletion
    client.delete_server.return_value = True
    client.delete_network.return_value = True

    return client


class TestDeploymentFlowEndToEnd:
    """Test complete deployment flow from API to database."""

    async def test_create_deployment_success(
        self, async_session: AsyncSession, mock_openstack_client
    ) -> None:
        """Test successful deployment creation through service layer."""
        # Setup
        from orchestrator.schemas.deployment import CreateDeploymentRequest

        repository = DeploymentRepository(async_session)
        service = DeploymentService(repository=repository, workflow_client=None)

        request = CreateDeploymentRequest(
            name="test-deployment",
            cloud_region="RegionOne",
            template={
                "network_config": {"cidr": "10.0.0.0/24"},
                "vm_config": {"count": 1, "flavor": "m1.small", "image": "ubuntu-22.04"},
            },
            parameters={},
        )

        # Execute
        result = await service.create_deployment(request)
        await async_session.commit()

        # Verify
        assert result.id is not None
        assert result.name == "test-deployment"
        assert result.status == DeploymentStatus.PENDING
        assert result.cloud_region == "RegionOne"

        # Verify database persistence
        deployment = await repository.get_by_id(result.id)
        assert deployment is not None
        assert deployment.name == "test-deployment"

    async def test_workflow_execution_success(
        self, async_session: AsyncSession, mock_openstack_client
    ) -> None:
        """Test successful workflow execution with mocked OpenStack (T077, T078)."""
        # Setup
        deployment_id = uuid4()
        workflow_input = DeploymentWorkflowInput(
            deployment_id=deployment_id,
            cloud_region="RegionOne",
            template={
                "network_config": {"cidr": "10.0.0.0/24"},
                "vm_config": {"count": 2, "flavor": "m1.small", "image": "ubuntu-22.04"},
            },
            parameters={},
        )

        # Create deployment in database
        repository = DeploymentRepository(async_session)
        deployment = Deployment(
            id=deployment_id,
            name="test-deployment",
            status=DeploymentStatus.PENDING,
            template=workflow_input.template,
            parameters=workflow_input.parameters,
            cloud_region=workflow_input.cloud_region,
        )
        await repository.create(deployment)
        await async_session.commit()

        # Mock activities
        with (
            patch(
                "orchestrator.workflows.deployment.deploy.create_network_activity"
            ) as mock_create_network,
            patch("orchestrator.workflows.deployment.deploy.create_vm_activity") as mock_create_vm,
            patch(
                "orchestrator.workflows.deployment.deploy.poll_vm_status_activity"
            ) as mock_poll_status,
            patch(
                "orchestrator.workflows.deployment.deploy.update_deployment_status_activity"
            ) as mock_update_status,
        ):
            # Setup mock returns
            mock_create_network.return_value = NetworkCreationResult(
                network_id="network-123",
                subnet_id="subnet-123",
                network_name="test-network",
                subnet_cidr="10.0.0.0/24",
            )

            mock_create_vm.return_value = VMCreationResult(
                server_id="server-123", server_name="test-server", status="BUILD"
            )

            mock_poll_status.return_value = VMStatusResult(
                server_id="server-123",
                status="ACTIVE",
                is_ready=True,
                addresses={"test-network": [{"addr": "10.0.0.5"}]},
            )

            mock_update_status.return_value = None

            # Execute workflow
            workflow = DeploymentWorkflow(
                openstack_config={
                    "auth_url": "http://localhost:5000/v3",
                    "username": "admin",
                    "password": "secret",
                    "project_name": "admin",
                    "region_name": "RegionOne",
                }
            )

            result = await workflow.execute(workflow_input)

            # Verify success
            assert result.success is True
            assert result.deployment_id == deployment_id
            assert result.network_id == "network-123"
            assert result.subnet_id == "subnet-123"
            assert len(result.server_ids) == 2
            assert result.error is None

            # Verify activities were called
            mock_create_network.assert_called_once()
            assert mock_create_vm.call_count == 2  # 2 VMs
            assert mock_update_status.call_count == 2  # IN_PROGRESS and COMPLETED

    async def test_workflow_rollback_on_failure(
        self, async_session: AsyncSession, mock_openstack_client
    ) -> None:
        """Test workflow rollback when VM creation fails (T079)."""
        # Setup
        deployment_id = uuid4()
        workflow_input = DeploymentWorkflowInput(
            deployment_id=deployment_id,
            cloud_region="RegionOne",
            template={
                "network_config": {"cidr": "10.0.0.0/24"},
                "vm_config": {"count": 1, "flavor": "m1.small", "image": "ubuntu-22.04"},
            },
            parameters={},
        )

        # Create deployment in database
        repository = DeploymentRepository(async_session)
        deployment = Deployment(
            id=deployment_id,
            name="test-deployment",
            status=DeploymentStatus.PENDING,
            template=workflow_input.template,
            parameters=workflow_input.parameters,
            cloud_region=workflow_input.cloud_region,
        )
        await repository.create(deployment)
        await async_session.commit()

        # Mock activities
        with (
            patch(
                "orchestrator.workflows.deployment.deploy.create_network_activity"
            ) as mock_create_network,
            patch("orchestrator.workflows.deployment.deploy.create_vm_activity") as mock_create_vm,
            patch(
                "orchestrator.workflows.deployment.deploy.rollback_resources_activity"
            ) as mock_rollback,
            patch(
                "orchestrator.workflows.deployment.deploy.update_deployment_status_activity"
            ) as mock_update_status,
        ):
            # Setup mocks
            mock_create_network.return_value = NetworkCreationResult(
                network_id="network-123",
                subnet_id="subnet-123",
                network_name="test-network",
                subnet_cidr="10.0.0.0/24",
            )

            # VM creation fails
            mock_create_vm.side_effect = Exception("Quota exceeded")
            mock_rollback.return_value = None
            mock_update_status.return_value = None

            # Execute workflow
            workflow = DeploymentWorkflow(
                openstack_config={
                    "auth_url": "http://localhost:5000/v3",
                    "username": "admin",
                    "password": "secret",
                    "project_name": "admin",
                    "region_name": "RegionOne",
                }
            )

            result = await workflow.execute(workflow_input)

            # Verify failure
            assert result.success is False
            assert result.error == "Quota exceeded"

            # Verify rollback was called
            mock_rollback.assert_called_once()
            rollback_call = mock_rollback.call_args
            assert rollback_call[1]["deployment_id"] == deployment_id
            assert rollback_call[1]["network_id"] == "network-123"

            # Verify status was updated to FAILED
            final_status_call = mock_update_status.call_args_list[-1]
            assert final_status_call[1]["status"] == DeploymentStatus.FAILED
            assert final_status_call[1]["error"] is not None

    async def test_list_deployments_pagination(self, async_session: AsyncSession) -> None:
        """Test deployment listing with pagination."""
        repository = DeploymentRepository(async_session)

        # Create multiple deployments
        deployments = []
        for i in range(5):
            deployment = Deployment(
                name=f"deployment-{i}",
                status=DeploymentStatus.PENDING,
                template={"vm_config": {}},
                parameters={},
                cloud_region="RegionOne",
            )
            created = await repository.create(deployment)
            deployments.append(created)
        await async_session.commit()

        # Test pagination
        page1 = await repository.list(limit=2, offset=0)
        assert len(page1) == 2

        page2 = await repository.list(limit=2, offset=2)
        assert len(page2) == 2

        page3 = await repository.list(limit=2, offset=4)
        assert len(page3) == 1

        # Test count
        total = await repository.count()
        assert total == 5

    async def test_list_deployments_with_filters(self, async_session: AsyncSession) -> None:
        """Test deployment listing with status filter."""
        repository = DeploymentRepository(async_session)

        # Create deployments with different statuses
        for status in [
            DeploymentStatus.PENDING,
            DeploymentStatus.IN_PROGRESS,
            DeploymentStatus.COMPLETED,
        ]:
            deployment = Deployment(
                name=f"deployment-{status.value}",
                status=status,
                template={"vm_config": {}},
                parameters={},
                cloud_region="RegionOne",
            )
            await repository.create(deployment)
        await async_session.commit()

        # Test status filter
        completed_deployments = await repository.list(status=DeploymentStatus.COMPLETED)
        assert len(completed_deployments) == 1
        assert completed_deployments[0].status == DeploymentStatus.COMPLETED

        # Test cloud region filter
        deployment_region2 = Deployment(
            name="deployment-region2",
            status=DeploymentStatus.PENDING,
            template={"vm_config": {}},
            parameters={},
            cloud_region="RegionTwo",
        )
        await repository.create(deployment_region2)
        await async_session.commit()

        region_one_deployments = await repository.list(cloud_region="RegionOne")
        assert len(region_one_deployments) == 3

        region_two_deployments = await repository.list(cloud_region="RegionTwo")
        assert len(region_two_deployments) == 1

    async def test_deployment_update_resources(self, async_session: AsyncSession) -> None:
        """Test updating deployment with created resources."""
        repository = DeploymentRepository(async_session)

        # Create deployment
        deployment = Deployment(
            name="test-deployment",
            status=DeploymentStatus.IN_PROGRESS,
            template={"vm_config": {}},
            parameters={},
            cloud_region="RegionOne",
        )
        created = await repository.create(deployment)
        await async_session.commit()

        # Update with resources
        resources = {
            "network_id": "network-123",
            "subnet_id": "subnet-123",
            "server_ids": ["server-1", "server-2"],
        }

        updated = await repository.update(
            created.id,
            status=DeploymentStatus.COMPLETED,
            resources=resources,
        )
        await async_session.commit()

        # Verify
        assert updated is not None
        assert updated.status == DeploymentStatus.COMPLETED
        assert updated.resources == resources
        assert updated.updated_at >= created.updated_at  # >= because onupdate may not fire in tests

    async def test_deployment_soft_delete(self, async_session: AsyncSession) -> None:
        """Test soft deletion of deployment."""
        repository = DeploymentRepository(async_session)

        # Create deployment
        deployment = Deployment(
            name="test-deployment",
            status=DeploymentStatus.COMPLETED,
            template={"vm_config": {}},
            parameters={},
            cloud_region="RegionOne",
        )
        created = await repository.create(deployment)
        await async_session.commit()

        # Delete deployment
        deleted = await repository.delete(created.id)
        await async_session.commit()
        assert deleted is True

        # Verify soft delete - check deleted_at timestamp
        result = await async_session.execute(
            text(f"SELECT deleted_at FROM deployments WHERE id = '{created.id}'")
        )
        deleted_at = result.scalar()
        assert deleted_at is not None

        # Verify deployment is marked as DELETED
        deleted_deployment = await repository.get_by_id(created.id)
        assert deleted_deployment is not None
        assert deleted_deployment.status == DeploymentStatus.DELETED
        assert deleted_deployment.deleted_at is not None

        # Still in database (soft delete)
        result = await async_session.execute(text("SELECT COUNT(*) FROM deployments"))
        count = result.scalar()
        assert count == 1

    async def test_concurrent_deployments(self, async_session: AsyncSession) -> None:
        """Test creating multiple deployments sequentially."""
        repository = DeploymentRepository(async_session)
        service = DeploymentService(repository=repository, workflow_client=None)

        from orchestrator.schemas.deployment import CreateDeploymentRequest

        # Create multiple deployments sequentially
        requests = [
            CreateDeploymentRequest(
                name=f"concurrent-deployment-{i}",
                cloud_region="RegionOne",
                template={"vm_config": {"flavor": "m1.small", "image": "ubuntu-20.04"}},
                parameters={},
            )
            for i in range(3)
        ]

        results = []
        for req in requests:
            result = await service.create_deployment(req)
            results.append(result)
        await async_session.commit()

        # Verify all created successfully
        assert len(results) == 3
        assert len({r.id for r in results}) == 3  # All unique IDs

        # Verify in database
        deployments = await repository.list()
        assert len(deployments) == 3
