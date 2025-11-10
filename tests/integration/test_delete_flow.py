"""Integration tests for delete deployment workflow.

Tests the full delete flow with database operations.
"""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from orchestrator.db.repositories.deployment_repository import DeploymentRepository
from orchestrator.models.base import Base
from orchestrator.models.deployment import Deployment, DeploymentStatus
from orchestrator.workflows.deployment.delete import DeleteWorkflow
from orchestrator.workflows.deployment.models import DeleteWorkflowInput

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


class TestDeleteDeploymentFlow:
    """Test delete deployment workflow end-to-end (T096, T097)."""

    async def test_delete_deployment_success(
        self, async_session: AsyncSession
    ) -> None:
        """Test successful deployment deletion end-to-end."""
        # Setup - Create deployment in database
        repository = DeploymentRepository(async_session)
        deployment = Deployment(
            name="test-deployment",
            status=DeploymentStatus.COMPLETED,
            template={"vm_config": {"flavor": "m1.small"}},
            parameters={},
            cloud_region="RegionOne",
            resources={
                "network_id": "network-123",
                "subnet_id": "subnet-123",
                "server_ids": ["server-1", "server-2"],
            },
        )
        created_deployment = await repository.create(deployment)
        await async_session.commit()

        # Create workflow input
        workflow_input = DeleteWorkflowInput(
            deployment_id=created_deployment.id,
            cloud_region="RegionOne",
            resources=created_deployment.resources or {},
        )

        # Mock activities
        with (
            patch(
                "orchestrator.workflows.deployment.delete.update_deployment_status_activity"
            ) as mock_update_status,
            patch(
                "orchestrator.workflows.deployment.delete.delete_vm_activity"
            ) as mock_delete_vm,
            patch(
                "orchestrator.workflows.deployment.delete.delete_network_activity"
            ) as mock_delete_network,
        ):
            # Setup mock returns
            mock_update_status.return_value = None
            mock_delete_vm.return_value = True
            mock_delete_network.return_value = True

            # Execute workflow
            workflow = DeleteWorkflow(
                openstack_config={
                    "auth_url": "http://localhost:5000/v3",
                    "username": "admin",
                    "password": "secret",
                    "project_name": "admin",
                    "region_name": "RegionOne",
                }
            )

            result = await workflow.execute(workflow_input)

            # Verify workflow result
            assert result.success is True
            assert result.deployment_id == created_deployment.id
            assert result.error is None

            # Verify VMs were deleted
            assert mock_delete_vm.call_count == 2  # 2 servers

            # Verify network was deleted
            mock_delete_network.assert_called_once()

            # Verify status updates
            assert mock_update_status.call_count == 2  # IN_PROGRESS and DELETED

    async def test_delete_deployment_with_vm_failure(
        self, async_session: AsyncSession
    ) -> None:
        """Test deployment deletion when VM deletion fails."""
        # Setup - Create deployment in database
        repository = DeploymentRepository(async_session)
        deployment = Deployment(
            name="test-deployment",
            status=DeploymentStatus.COMPLETED,
            template={"vm_config": {"flavor": "m1.small"}},
            parameters={},
            cloud_region="RegionOne",
            resources={
                "network_id": "network-123",
                "subnet_id": "subnet-123",
                "server_ids": ["server-1"],
            },
        )
        created_deployment = await repository.create(deployment)
        await async_session.commit()

        # Create workflow input
        workflow_input = DeleteWorkflowInput(
            deployment_id=created_deployment.id,
            cloud_region="RegionOne",
            resources=created_deployment.resources or {},
        )

        # Mock activities
        with (
            patch(
                "orchestrator.workflows.deployment.delete.update_deployment_status_activity"
            ) as mock_update_status,
            patch(
                "orchestrator.workflows.deployment.delete.delete_vm_activity"
            ) as mock_delete_vm,
            patch(
                "orchestrator.workflows.deployment.delete.cleanup_orphaned_resources_activity"
            ) as mock_cleanup,
        ):
            # Setup mocks - VM deletion fails
            mock_update_status.return_value = None
            mock_delete_vm.side_effect = Exception("Server not found")
            mock_cleanup.return_value = None

            # Execute workflow
            workflow = DeleteWorkflow(
                openstack_config={
                    "auth_url": "http://localhost:5000/v3",
                    "username": "admin",
                    "password": "secret",
                    "project_name": "admin",
                    "region_name": "RegionOne",
                }
            )

            result = await workflow.execute(workflow_input)

            # Verify workflow result
            assert result.success is False
            assert result.error == "Server not found"

            # Verify cleanup was called
            mock_cleanup.assert_called_once()

            # Verify status was updated to FAILED
            final_call = mock_update_status.call_args_list[-1]
            assert final_call[1]["status"] == DeploymentStatus.FAILED

    async def test_delete_deployment_with_no_resources(
        self, async_session: AsyncSession
    ) -> None:
        """Test deployment deletion when no resources exist."""
        # Setup - Create deployment in database with no resources
        repository = DeploymentRepository(async_session)
        deployment = Deployment(
            name="test-deployment",
            status=DeploymentStatus.COMPLETED,
            template={"vm_config": {"flavor": "m1.small"}},
            parameters={},
            cloud_region="RegionOne",
            resources={},
        )
        created_deployment = await repository.create(deployment)
        await async_session.commit()

        # Create workflow input
        workflow_input = DeleteWorkflowInput(
            deployment_id=created_deployment.id,
            cloud_region="RegionOne",
            resources={},
        )

        # Mock activities
        with patch(
            "orchestrator.workflows.deployment.delete.update_deployment_status_activity"
        ) as mock_update_status:
            mock_update_status.return_value = None

            # Execute workflow
            workflow = DeleteWorkflow(
                openstack_config={
                    "auth_url": "http://localhost:5000/v3",
                    "username": "admin",
                    "password": "secret",
                    "project_name": "admin",
                    "region_name": "RegionOne",
                }
            )

            result = await workflow.execute(workflow_input)

            # Verify workflow result - should succeed with no-op
            assert result.success is True
            assert result.error is None

            # Verify only status updates were called
            assert mock_update_status.call_count == 2


class TestOrphanedResourceCleanup:
    """Test orphaned resource cleanup (T098)."""

    async def test_cleanup_orphaned_resources(
        self, async_session: AsyncSession
    ) -> None:
        """Test cleanup of orphaned resources after failed deletion."""
        # Setup - Create deployment in database
        repository = DeploymentRepository(async_session)
        deployment = Deployment(
            name="test-deployment",
            status=DeploymentStatus.COMPLETED,
            template={"vm_config": {"flavor": "m1.small"}},
            parameters={},
            cloud_region="RegionOne",
            resources={
                "network_id": "network-123",
                "subnet_id": "subnet-123",
                "server_ids": ["server-1", "server-2"],
            },
        )
        created_deployment = await repository.create(deployment)
        await async_session.commit()

        # Create workflow input
        workflow_input = DeleteWorkflowInput(
            deployment_id=created_deployment.id,
            cloud_region="RegionOne",
            resources=created_deployment.resources or {},
        )

        # Mock activities - network deletion fails
        with (
            patch(
                "orchestrator.workflows.deployment.delete.update_deployment_status_activity"
            ) as mock_update_status,
            patch(
                "orchestrator.workflows.deployment.delete.delete_vm_activity"
            ) as mock_delete_vm,
            patch(
                "orchestrator.workflows.deployment.delete.delete_network_activity"
            ) as mock_delete_network,
            patch(
                "orchestrator.workflows.deployment.delete.cleanup_orphaned_resources_activity"
            ) as mock_cleanup,
        ):
            # Setup mocks - VMs deleted but network deletion fails
            mock_update_status.return_value = None
            mock_delete_vm.return_value = True
            mock_delete_network.side_effect = Exception("Network still in use")
            mock_cleanup.return_value = None

            # Execute workflow
            workflow = DeleteWorkflow(
                openstack_config={
                    "auth_url": "http://localhost:5000/v3",
                    "username": "admin",
                    "password": "secret",
                    "project_name": "admin",
                    "region_name": "RegionOne",
                }
            )

            result = await workflow.execute(workflow_input)

            # Verify workflow failed
            assert result.success is False
            assert "Network still in use" in result.error

            # Verify cleanup was called with all resources
            mock_cleanup.assert_called_once()
            cleanup_call = mock_cleanup.call_args
            assert cleanup_call[1]["deployment_id"] == created_deployment.id
            assert cleanup_call[1]["resources"]["network_id"] == "network-123"
            assert cleanup_call[1]["resources"]["server_ids"] == ["server-1", "server-2"]

    async def test_cleanup_handles_partial_failures(
        self, async_session: AsyncSession
    ) -> None:
        """Test that cleanup handles partial failures gracefully."""
        from orchestrator.workflows.deployment.activities import (
            cleanup_orphaned_resources_activity,
        )

        # Mock OpenStack client
        with patch(
            "orchestrator.workflows.deployment.activities.OpenStackClient"
        ) as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            # First server deletion succeeds, second fails, network fails
            mock_client.delete_server.side_effect = [
                None,  # First server succeeds
                Exception("Server not found"),  # Second server fails
            ]
            mock_client.delete_network.side_effect = Exception("Network in use")

            # Execute cleanup
            await cleanup_orphaned_resources_activity(
                deployment_id=uuid4(),
                resources={
                    "network_id": "network-123",
                    "server_ids": ["server-1", "server-2"],
                },
                openstack_config={
                    "auth_url": "http://localhost:5000/v3",
                    "username": "admin",
                    "password": "secret",
                    "project_name": "admin",
                    "region_name": "RegionOne",
                },
            )

            # Verify cleanup attempted all resources despite failures
            assert mock_client.delete_server.call_count == 2
            mock_client.delete_network.assert_called_once()

    async def test_deployment_status_after_failed_deletion(
        self, async_session: AsyncSession
    ) -> None:
        """Test deployment status is updated to FAILED after failed deletion."""
        # Setup - Create deployment in database
        repository = DeploymentRepository(async_session)
        deployment = Deployment(
            name="test-deployment",
            status=DeploymentStatus.COMPLETED,
            template={"vm_config": {"flavor": "m1.small"}},
            parameters={},
            cloud_region="RegionOne",
            resources={
                "network_id": "network-123",
                "server_ids": ["server-1"],
            },
        )
        created_deployment = await repository.create(deployment)
        await async_session.commit()

        # Create workflow input
        workflow_input = DeleteWorkflowInput(
            deployment_id=created_deployment.id,
            cloud_region="RegionOne",
            resources=created_deployment.resources or {},
        )

        # Mock activities - VM deletion fails
        with (
            patch(
                "orchestrator.workflows.deployment.delete.update_deployment_status_activity"
            ) as mock_update_status,
            patch(
                "orchestrator.workflows.deployment.delete.delete_vm_activity"
            ) as mock_delete_vm,
            patch(
                "orchestrator.workflows.deployment.delete.cleanup_orphaned_resources_activity"
            ) as mock_cleanup,
        ):
            mock_update_status.return_value = None
            mock_delete_vm.side_effect = Exception("Deletion failed")
            mock_cleanup.return_value = None

            # Execute workflow
            workflow = DeleteWorkflow(
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

            # Verify final status update was FAILED
            status_calls = [
                call[1]["status"]
                for call in mock_update_status.call_args_list
                if "status" in call[1]
            ]
            assert DeploymentStatus.IN_PROGRESS in status_calls
            assert DeploymentStatus.FAILED in status_calls

            # Verify error details were provided
            final_call = mock_update_status.call_args_list[-1]
            assert "error" in final_call[1]
            assert final_call[1]["error"] is not None
