"""
Integration tests for configuration workflow.

Tests the end-to-end configuration flow with real database.
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from orchestrator.clients.ansible.client import PlaybookStatus
from orchestrator.db.repositories.deployment_repository import DeploymentRepository
from orchestrator.models.base import Base
from orchestrator.models.deployment import Deployment, DeploymentStatus
from orchestrator.workflows.configuration.configure import run_configure_workflow

pytestmark = pytest.mark.integration


@pytest.fixture
async def db_session():
    """Create test database session."""
    # Create in-memory SQLite database
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create session factory
    async_session_maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session_maker() as session:
        yield session

    # Cleanup
    await engine.dispose()


class TestConfigureDeploymentFlow:
    """Test end-to-end configuration flow."""

    @pytest.mark.asyncio
    async def test_configure_deployment_success(self, db_session: AsyncSession) -> None:
        """Test successful configuration of a deployment."""
        # Create a completed deployment
        deployment = Deployment(
            id=uuid4(),
            name="test-deployment",
            status=DeploymentStatus.COMPLETED,
            template={"vm_config": {"flavor": "m1.small"}},
            parameters={},
            cloud_region="RegionOne",
            resources={
                "server_ids": ["vm-123", "vm-456"],
                "network_id": "net-123",
            },
        )

        repo = DeploymentRepository(db_session)
        created_deployment = await repo.create(deployment)
        await db_session.commit()

        # Mock Ansible execution and status updates
        with (
            patch(
                "orchestrator.workflows.configuration.activities.AnsibleClient"
            ) as mock_client_class,
            patch(
                "orchestrator.workflows.configuration.activities.get_vm_addresses_activity"
            ) as mock_get_addresses,
            patch(
                "orchestrator.workflows.configuration.configure.update_deployment_status_activity"
            ) as mock_update_status,
        ):
            # Setup mocks
            mock_get_addresses.return_value = {
                "vm-123": "10.0.0.5",
                "vm-456": "10.0.0.6",
            }
            mock_update_status.return_value = None

            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            mock_playbook_result = MagicMock()
            mock_playbook_result.execution_id = uuid4()
            mock_playbook_result.status = PlaybookStatus.SUCCESSFUL
            mock_playbook_result.return_code = 0
            mock_playbook_result.stats = {"ok": {"10.0.0.5": 5, "10.0.0.6": 5}}
            mock_playbook_result.error = None

            mock_client.run_playbook = AsyncMock(return_value=mock_playbook_result)

            # Execute configuration workflow
            result = await run_configure_workflow(
                deployment_id=created_deployment.id,
                playbook_path="/playbooks/configure_web.yml",
                extra_vars={"app_version": "1.2.3"},
                limit=None,
                resources=created_deployment.resources,
            )

            # Verify result
            assert result.success is True
            assert result.deployment_id == created_deployment.id
            assert result.execution_id == mock_playbook_result.execution_id
            assert len(result.configured_hosts) == 2
            assert "10.0.0.5" in result.configured_hosts
            assert "10.0.0.6" in result.configured_hosts

            # Verify status update was called
            mock_update_status.assert_called_once()

    @pytest.mark.asyncio
    async def test_configure_deployment_with_failure(self, db_session: AsyncSession) -> None:
        """Test configuration with playbook failure."""
        # Create a completed deployment
        deployment = Deployment(
            id=uuid4(),
            name="test-deployment",
            status=DeploymentStatus.COMPLETED,
            template={"vm_config": {"flavor": "m1.small"}},
            parameters={},
            cloud_region="RegionOne",
            resources={
                "server_ids": ["vm-123"],
                "network_id": "net-123",
            },
        )

        repo = DeploymentRepository(db_session)
        created_deployment = await repo.create(deployment)
        await db_session.commit()

        # Mock Ansible execution with failure
        with (
            patch(
                "orchestrator.workflows.configuration.activities.AnsibleClient"
            ) as mock_client_class,
            patch(
                "orchestrator.workflows.configuration.activities.get_vm_addresses_activity"
            ) as mock_get_addresses,
            patch(
                "orchestrator.workflows.configuration.configure.update_deployment_status_activity"
            ) as mock_update_status,
        ):
            # Setup mocks
            mock_get_addresses.return_value = {"vm-123": "10.0.0.5"}
            mock_update_status.return_value = None

            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            mock_playbook_result = MagicMock()
            mock_playbook_result.execution_id = uuid4()
            mock_playbook_result.status = PlaybookStatus.FAILED
            mock_playbook_result.return_code = 2
            mock_playbook_result.stats = {"failures": {"10.0.0.5": 1}}
            mock_playbook_result.error = "Task failed on host"

            mock_client.run_playbook = AsyncMock(return_value=mock_playbook_result)

            # Execute configuration workflow
            result = await run_configure_workflow(
                deployment_id=created_deployment.id,
                playbook_path="/playbooks/configure_web.yml",
                extra_vars={},
                limit=None,
                resources=created_deployment.resources,
            )

            # Verify result
            assert result.success is False
            assert result.error is not None
            assert "Task failed" in result.error
            assert result.configured_hosts == []

            # Verify status update was called with error
            mock_update_status.assert_called_once()
            call_kwargs = mock_update_status.call_args[1]
            assert "error" in call_kwargs

    @pytest.mark.asyncio
    async def test_configure_deployment_no_vms(self, db_session: AsyncSession) -> None:
        """Test configuration with no VMs in resources."""
        # Create deployment without VMs
        deployment = Deployment(
            id=uuid4(),
            name="test-deployment",
            status=DeploymentStatus.COMPLETED,
            template={"vm_config": {"flavor": "m1.small"}},
            parameters={},
            cloud_region="RegionOne",
            resources={"network_id": "net-123"},  # No server_ids
        )

        repo = DeploymentRepository(db_session)
        created_deployment = await repo.create(deployment)
        await db_session.commit()

        # Execute configuration workflow
        result = await run_configure_workflow(
            deployment_id=created_deployment.id,
            playbook_path="/playbooks/configure_web.yml",
            extra_vars={},
            limit=None,
            resources=created_deployment.resources,
        )

        # Verify result
        assert result.success is False
        assert "No VMs found" in result.error
        assert result.configured_hosts == []

    @pytest.mark.asyncio
    async def test_configure_deployment_with_limit(self, db_session: AsyncSession) -> None:
        """Test configuration with host limit."""
        # Create a completed deployment with multiple VMs
        deployment = Deployment(
            id=uuid4(),
            name="test-deployment",
            status=DeploymentStatus.COMPLETED,
            template={"vm_config": {"flavor": "m1.small"}},
            parameters={},
            cloud_region="RegionOne",
            resources={
                "server_ids": ["vm-123", "vm-456", "vm-789"],
                "network_id": "net-123",
            },
        )

        repo = DeploymentRepository(db_session)
        created_deployment = await repo.create(deployment)
        await db_session.commit()

        # Mock Ansible execution and status updates
        with (
            patch(
                "orchestrator.workflows.configuration.activities.AnsibleClient"
            ) as mock_client_class,
            patch(
                "orchestrator.workflows.configuration.activities.get_vm_addresses_activity"
            ) as mock_get_addresses,
            patch(
                "orchestrator.workflows.configuration.configure.update_deployment_status_activity"
            ) as mock_update_status,
        ):
            # Setup mocks
            mock_get_addresses.return_value = {
                "vm-123": "10.0.0.5",
                "vm-456": "10.0.0.6",
                "vm-789": "10.0.0.7",
            }
            mock_update_status.return_value = None

            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            mock_playbook_result = MagicMock()
            mock_playbook_result.execution_id = uuid4()
            mock_playbook_result.status = PlaybookStatus.SUCCESSFUL
            mock_playbook_result.return_code = 0
            mock_playbook_result.stats = {"ok": {"10.0.0.5": 5}}  # Only one host
            mock_playbook_result.error = None

            mock_client.run_playbook = AsyncMock(return_value=mock_playbook_result)

            # Execute configuration workflow with limit
            result = await run_configure_workflow(
                deployment_id=created_deployment.id,
                playbook_path="/playbooks/configure_web.yml",
                extra_vars={},
                limit="vm-123",  # Limit to single VM
                resources=created_deployment.resources,
            )

            # Verify result
            assert result.success is True

            # Verify limit was passed to Ansible
            call_kwargs = mock_client.run_playbook.call_args[1]
            assert call_kwargs["limit"] == "vm-123"
