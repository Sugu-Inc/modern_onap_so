"""Integration tests for update deployment workflow.

Tests the full update flow with database operations.
"""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from orchestrator.db.repositories.deployment_repository import DeploymentRepository
from orchestrator.models.base import Base
from orchestrator.models.deployment import Deployment, DeploymentStatus
from orchestrator.workflows.deployment.update import UpdateWorkflow
from orchestrator.workflows.deployment.models import UpdateWorkflowInput

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


class TestUpdateDeploymentFlow:
    """Test update deployment workflow end-to-end (T099, T100)."""

    async def test_update_deployment_success_vm_resize(
        self, async_session: AsyncSession
    ) -> None:
        """Test successful deployment update with VM resize."""
        # Setup - Create deployment in database
        repository = DeploymentRepository(async_session)
        deployment = Deployment(
            name="test-deployment",
            status=DeploymentStatus.COMPLETED,
            template={"vm_config": {"flavor": "m1.small"}},
            parameters={"flavor": "m1.small"},
            cloud_region="RegionOne",
            resources={
                "network_id": "network-123",
                "subnet_id": "subnet-123",
                "server_ids": ["server-1", "server-2"],
            },
        )
        created_deployment = await repository.create(deployment)
        await async_session.commit()

        # Create workflow input - resize to m1.large
        workflow_input = UpdateWorkflowInput(
            deployment_id=created_deployment.id,
            cloud_region="RegionOne",
            current_resources=created_deployment.resources or {},
            updated_parameters={"flavor": "m1.large"},
        )

        # Mock activities
        with (
            patch(
                "orchestrator.workflows.deployment.update.update_deployment_status_activity"
            ) as mock_update_status,
            patch(
                "orchestrator.workflows.deployment.update.resize_vm_activity"
            ) as mock_resize_vm,
        ):
            # Setup mock returns
            mock_update_status.return_value = None
            mock_resize_vm.return_value = True

            # Execute workflow
            workflow = UpdateWorkflow(
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

            # Verify VMs were resized
            assert mock_resize_vm.call_count == 2  # 2 servers

            # Verify resize was called with correct flavor
            for call in mock_resize_vm.call_args_list:
                assert call[1]["new_flavor"] == "m1.large"

            # Verify status updates
            assert mock_update_status.call_count == 2  # IN_PROGRESS and COMPLETED

    async def test_update_deployment_success_network_change(
        self, async_session: AsyncSession
    ) -> None:
        """Test successful deployment update with network configuration change."""
        # Setup - Create deployment in database
        repository = DeploymentRepository(async_session)
        deployment = Deployment(
            name="test-deployment",
            status=DeploymentStatus.COMPLETED,
            template={"vm_config": {"flavor": "m1.small"}},
            parameters={"network_cidr": "10.0.0.0/24"},
            cloud_region="RegionOne",
            resources={
                "network_id": "network-123",
                "subnet_id": "subnet-123",
                "server_ids": ["server-1"],
            },
        )
        created_deployment = await repository.create(deployment)
        await async_session.commit()

        # Create workflow input - change network CIDR
        workflow_input = UpdateWorkflowInput(
            deployment_id=created_deployment.id,
            cloud_region="RegionOne",
            current_resources=created_deployment.resources or {},
            updated_parameters={"network_cidr": "10.0.1.0/24"},
        )

        # Mock activities
        with (
            patch(
                "orchestrator.workflows.deployment.update.update_deployment_status_activity"
            ) as mock_update_status,
            patch(
                "orchestrator.workflows.deployment.update.update_network_activity"
            ) as mock_update_network,
        ):
            # Setup mock returns
            mock_update_status.return_value = None
            mock_update_network.return_value = {
                "network_id": "network-123",
                "subnet_id": "subnet-456",  # New subnet ID
            }

            # Execute workflow
            workflow = UpdateWorkflow(
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
            assert result.error is None

            # Verify network was updated
            mock_update_network.assert_called_once()
            assert mock_update_network.call_args[1]["new_cidr"] == "10.0.1.0/24"

            # Verify updated resources include new subnet ID
            assert result.updated_resources["subnet_id"] == "subnet-456"

    async def test_update_deployment_combined_changes(
        self, async_session: AsyncSession
    ) -> None:
        """Test deployment update with both VM resize and network change."""
        # Setup - Create deployment in database
        repository = DeploymentRepository(async_session)
        deployment = Deployment(
            name="test-deployment",
            status=DeploymentStatus.COMPLETED,
            template={"vm_config": {"flavor": "m1.small"}},
            parameters={"flavor": "m1.small", "network_cidr": "10.0.0.0/24"},
            cloud_region="RegionOne",
            resources={
                "network_id": "network-123",
                "subnet_id": "subnet-123",
                "server_ids": ["server-1", "server-2"],
            },
        )
        created_deployment = await repository.create(deployment)
        await async_session.commit()

        # Create workflow input - both changes
        workflow_input = UpdateWorkflowInput(
            deployment_id=created_deployment.id,
            cloud_region="RegionOne",
            current_resources=created_deployment.resources or {},
            updated_parameters={"flavor": "m1.xlarge", "network_cidr": "10.0.2.0/24"},
        )

        # Mock activities
        with (
            patch(
                "orchestrator.workflows.deployment.update.update_deployment_status_activity"
            ) as mock_update_status,
            patch(
                "orchestrator.workflows.deployment.update.resize_vm_activity"
            ) as mock_resize_vm,
            patch(
                "orchestrator.workflows.deployment.update.update_network_activity"
            ) as mock_update_network,
        ):
            # Setup mock returns
            mock_update_status.return_value = None
            mock_resize_vm.return_value = True
            mock_update_network.return_value = {
                "network_id": "network-123",
                "subnet_id": "subnet-789",
            }

            # Execute workflow
            workflow = UpdateWorkflow(
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

            # Verify both operations were performed
            assert mock_resize_vm.call_count == 2  # 2 VMs
            mock_update_network.assert_called_once()

    async def test_update_deployment_with_resize_failure(
        self, async_session: AsyncSession
    ) -> None:
        """Test deployment update when VM resize fails."""
        # Setup - Create deployment in database
        repository = DeploymentRepository(async_session)
        deployment = Deployment(
            name="test-deployment",
            status=DeploymentStatus.COMPLETED,
            template={"vm_config": {"flavor": "m1.small"}},
            parameters={"flavor": "m1.small"},
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
        workflow_input = UpdateWorkflowInput(
            deployment_id=created_deployment.id,
            cloud_region="RegionOne",
            current_resources=created_deployment.resources or {},
            updated_parameters={"flavor": "m1.invalid"},
        )

        # Mock activities
        with (
            patch(
                "orchestrator.workflows.deployment.update.update_deployment_status_activity"
            ) as mock_update_status,
            patch(
                "orchestrator.workflows.deployment.update.resize_vm_activity"
            ) as mock_resize_vm,
        ):
            # Setup mocks - resize fails
            mock_update_status.return_value = None
            mock_resize_vm.side_effect = Exception("Invalid flavor")

            # Execute workflow
            workflow = UpdateWorkflow(
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
            assert "Invalid flavor" in result.error

            # Verify status was updated to FAILED
            final_call = mock_update_status.call_args_list[-1]
            assert final_call[1]["status"] == DeploymentStatus.FAILED
            assert final_call[1]["error"] is not None

    async def test_update_deployment_no_changes(
        self, async_session: AsyncSession
    ) -> None:
        """Test deployment update when no changes are requested."""
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

        # Create workflow input with no updates
        workflow_input = UpdateWorkflowInput(
            deployment_id=created_deployment.id,
            cloud_region="RegionOne",
            current_resources=created_deployment.resources or {},
            updated_parameters={},
        )

        # Mock activities
        with patch(
            "orchestrator.workflows.deployment.update.update_deployment_status_activity"
        ) as mock_update_status:
            mock_update_status.return_value = None

            # Execute workflow
            workflow = UpdateWorkflow(
                openstack_config={
                    "auth_url": "http://localhost:5000/v3",
                    "username": "admin",
                    "password": "secret",
                    "project_name": "admin",
                    "region_name": "RegionOne",
                }
            )

            result = await workflow.execute(workflow_input)

            # Verify workflow succeeded (no-op)
            assert result.success is True
            assert result.error is None

            # Verify only status updates were called
            assert mock_update_status.call_count == 2

    async def test_update_deployment_status_transitions(
        self, async_session: AsyncSession
    ) -> None:
        """Test deployment status transitions during update."""
        # Setup - Create deployment in database
        repository = DeploymentRepository(async_session)
        deployment = Deployment(
            name="test-deployment",
            status=DeploymentStatus.COMPLETED,
            template={"vm_config": {"flavor": "m1.small"}},
            parameters={"flavor": "m1.small"},
            cloud_region="RegionOne",
            resources={
                "network_id": "network-123",
                "server_ids": ["server-1"],
            },
        )
        created_deployment = await repository.create(deployment)
        await async_session.commit()

        # Create workflow input
        workflow_input = UpdateWorkflowInput(
            deployment_id=created_deployment.id,
            cloud_region="RegionOne",
            current_resources=created_deployment.resources or {},
            updated_parameters={"flavor": "m1.large"},
        )

        # Mock activities
        with (
            patch(
                "orchestrator.workflows.deployment.update.update_deployment_status_activity"
            ) as mock_update_status,
            patch(
                "orchestrator.workflows.deployment.update.resize_vm_activity"
            ) as mock_resize_vm,
        ):
            mock_update_status.return_value = None
            mock_resize_vm.return_value = True

            # Execute workflow
            workflow = UpdateWorkflow(
                openstack_config={
                    "auth_url": "http://localhost:5000/v3",
                    "username": "admin",
                    "password": "secret",
                    "project_name": "admin",
                    "region_name": "RegionOne",
                }
            )

            result = await workflow.execute(workflow_input)

            # Verify workflow succeeded
            assert result.success is True

            # Verify status transitions
            status_calls = [
                call[1]["status"]
                for call in mock_update_status.call_args_list
                if "status" in call[1]
            ]
            assert DeploymentStatus.IN_PROGRESS in status_calls
            assert DeploymentStatus.COMPLETED in status_calls

            # Verify final call included updated resources
            final_call = mock_update_status.call_args_list[-1]
            assert "resources" in final_call[1]

    async def test_update_deployment_preserves_resources(
        self, async_session: AsyncSession
    ) -> None:
        """Test that update preserves existing resources correctly."""
        # Setup - Create deployment in database
        repository = DeploymentRepository(async_session)
        deployment = Deployment(
            name="test-deployment",
            status=DeploymentStatus.COMPLETED,
            template={"vm_config": {"flavor": "m1.small"}},
            parameters={"flavor": "m1.small"},
            cloud_region="RegionOne",
            resources={
                "network_id": "network-123",
                "subnet_id": "subnet-123",
                "server_ids": ["server-1", "server-2"],
                "custom_data": "should-be-preserved",
            },
        )
        created_deployment = await repository.create(deployment)
        await async_session.commit()

        # Create workflow input - only resize VMs
        workflow_input = UpdateWorkflowInput(
            deployment_id=created_deployment.id,
            cloud_region="RegionOne",
            current_resources=created_deployment.resources or {},
            updated_parameters={"flavor": "m1.large"},
        )

        # Mock activities
        with (
            patch(
                "orchestrator.workflows.deployment.update.update_deployment_status_activity"
            ) as mock_update_status,
            patch(
                "orchestrator.workflows.deployment.update.resize_vm_activity"
            ) as mock_resize_vm,
        ):
            mock_update_status.return_value = None
            mock_resize_vm.return_value = True

            # Execute workflow
            workflow = UpdateWorkflow(
                openstack_config={
                    "auth_url": "http://localhost:5000/v3",
                    "username": "admin",
                    "password": "secret",
                    "project_name": "admin",
                    "region_name": "RegionOne",
                }
            )

            result = await workflow.execute(workflow_input)

            # Verify workflow succeeded
            assert result.success is True

            # Verify existing resources were preserved
            assert result.updated_resources["network_id"] == "network-123"
            assert result.updated_resources["subnet_id"] == "subnet-123"
            assert result.updated_resources["server_ids"] == ["server-1", "server-2"]
            assert result.updated_resources["custom_data"] == "should-be-preserved"
