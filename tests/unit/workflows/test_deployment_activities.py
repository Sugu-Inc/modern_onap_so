"""
Unit tests for deployment workflow activities.
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from orchestrator.models.deployment import DeploymentStatus
from orchestrator.workflows.deployment.activities import (
    cleanup_orphaned_resources_activity,
    create_network_activity,
    create_vm_activity,
    delete_network_activity,
    delete_vm_activity,
    poll_vm_status_activity,
    resize_vm_activity,
    rollback_resources_activity,
    update_deployment_status_activity,
    update_network_activity,
)


class TestUpdateDeploymentStatusActivity:
    """Test update deployment status activity."""

    @pytest.mark.asyncio
    async def test_update_status_success(self) -> None:
        """Test updating deployment status."""
        deployment_id = uuid4()

        with patch("orchestrator.workflows.deployment.activities.db_connection") as mock_db:
            mock_session = AsyncMock()
            mock_repo = AsyncMock()
            mock_repo.update.return_value = MagicMock()  # Non-None to indicate success

            mock_db.session.return_value.__aenter__.return_value = mock_session

            with patch(
                "orchestrator.workflows.deployment.activities.DeploymentRepository"
            ) as mock_repo_class:
                mock_repo_class.return_value = mock_repo

                await update_deployment_status_activity(
                    deployment_id=deployment_id,
                    status=DeploymentStatus.COMPLETED,
                )

                mock_repo.update.assert_called_once_with(
                    deployment_id, status=DeploymentStatus.COMPLETED
                )
                mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_status_with_resources(self) -> None:
        """Test updating deployment status with resources."""
        deployment_id = uuid4()
        resources = {"server_ids": ["server-1", "server-2"]}

        with patch("orchestrator.workflows.deployment.activities.db_connection") as mock_db:
            mock_session = AsyncMock()
            mock_repo = AsyncMock()
            mock_repo.update.return_value = MagicMock()

            mock_db.session.return_value.__aenter__.return_value = mock_session

            with patch(
                "orchestrator.workflows.deployment.activities.DeploymentRepository"
            ) as mock_repo_class:
                mock_repo_class.return_value = mock_repo

                await update_deployment_status_activity(
                    deployment_id=deployment_id,
                    status=DeploymentStatus.COMPLETED,
                    resources=resources,
                )

                mock_repo.update.assert_called_once_with(
                    deployment_id,
                    status=DeploymentStatus.COMPLETED,
                    resources=resources,
                )

    @pytest.mark.asyncio
    async def test_update_status_with_error(self) -> None:
        """Test updating deployment status with error."""
        deployment_id = uuid4()
        error = {"message": "Deployment failed"}

        with patch("orchestrator.workflows.deployment.activities.db_connection") as mock_db:
            mock_session = AsyncMock()
            mock_repo = AsyncMock()
            mock_repo.update.return_value = MagicMock()

            mock_db.session.return_value.__aenter__.return_value = mock_session

            with patch(
                "orchestrator.workflows.deployment.activities.DeploymentRepository"
            ) as mock_repo_class:
                mock_repo_class.return_value = mock_repo

                await update_deployment_status_activity(
                    deployment_id=deployment_id,
                    status=DeploymentStatus.FAILED,
                    error=error,
                )

                mock_repo.update.assert_called_once_with(
                    deployment_id,
                    status=DeploymentStatus.FAILED,
                    error=error,
                )

    @pytest.mark.asyncio
    async def test_update_status_deployment_not_found(self) -> None:
        """Test updating non-existent deployment raises error."""
        deployment_id = uuid4()

        with patch("orchestrator.workflows.deployment.activities.db_connection") as mock_db:
            mock_session = AsyncMock()
            mock_repo = AsyncMock()
            mock_repo.update.return_value = None  # Deployment not found

            mock_db.session.return_value.__aenter__.return_value = mock_session

            with patch(
                "orchestrator.workflows.deployment.activities.DeploymentRepository"
            ) as mock_repo_class:
                mock_repo_class.return_value = mock_repo

                with pytest.raises(Exception, match="Deployment .* not found"):
                    await update_deployment_status_activity(
                        deployment_id=deployment_id,
                        status=DeploymentStatus.COMPLETED,
                    )


class TestCreateNetworkActivity:
    """Test create network activity."""

    @pytest.mark.asyncio
    async def test_create_network_success(self) -> None:
        """Test creating network and subnet."""
        deployment_id = uuid4()

        with patch(
            "orchestrator.workflows.deployment.activities.OpenStackClient"
        ) as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = AsyncMock()

            # Mock network creation
            mock_client.create_network.return_value = {"id": "network-123"}
            # Mock subnet creation
            mock_client.create_subnet.return_value = {"id": "subnet-456"}

            mock_client_class.return_value = mock_client

            result = await create_network_activity(
                deployment_id=deployment_id,
                network_name="test-network",
                subnet_cidr="192.168.1.0/24",
                cloud_region="RegionOne",
                openstack_config={"auth_url": "http://localhost:5000"},
            )

            assert result.network_id == "network-123"
            assert result.subnet_id == "subnet-456"
            assert result.network_name == "test-network"
            assert result.subnet_cidr == "192.168.1.0/24"


class TestCleanupOrphanedResourcesActivity:
    """Test cleanup orphaned resources activity."""

    @pytest.mark.asyncio
    async def test_cleanup_with_servers_and_network(self) -> None:
        """Test cleanup with both servers and network."""
        deployment_id = uuid4()

        with patch(
            "orchestrator.workflows.deployment.activities.OpenStackClient"
        ) as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = AsyncMock()

            mock_client_class.return_value = mock_client

            await cleanup_orphaned_resources_activity(
                deployment_id=deployment_id,
                resources={
                    "server_ids": ["server-1", "server-2"],
                    "network_id": "network-123",
                },
                openstack_config={"auth_url": "http://localhost:5000"},
            )

            # Should attempt to delete both servers
            assert mock_client.delete_server.call_count == 2
            # Should attempt to delete network
            mock_client.delete_network.assert_called_once_with("network-123")

    @pytest.mark.asyncio
    async def test_cleanup_with_server_failure(self) -> None:
        """Test cleanup continues even if server deletion fails."""
        deployment_id = uuid4()

        with patch(
            "orchestrator.workflows.deployment.activities.OpenStackClient"
        ) as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = AsyncMock()

            # First server deletion fails
            mock_client.delete_server.side_effect = [
                Exception("Server deletion failed"),
                None,  # Second succeeds
            ]

            mock_client_class.return_value = mock_client

            # Should not raise exception (best-effort cleanup)
            await cleanup_orphaned_resources_activity(
                deployment_id=deployment_id,
                resources={
                    "server_ids": ["server-1", "server-2"],
                },
                openstack_config={"auth_url": "http://localhost:5000"},
            )

            # Should have attempted both deletions
            assert mock_client.delete_server.call_count == 2

    @pytest.mark.asyncio
    async def test_cleanup_with_network_failure(self) -> None:
        """Test cleanup continues even if network deletion fails."""
        deployment_id = uuid4()

        with patch(
            "orchestrator.workflows.deployment.activities.OpenStackClient"
        ) as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = AsyncMock()

            # Network deletion fails
            mock_client.delete_network.side_effect = Exception("Network deletion failed")

            mock_client_class.return_value = mock_client

            # Should not raise exception (best-effort cleanup)
            await cleanup_orphaned_resources_activity(
                deployment_id=deployment_id,
                resources={
                    "network_id": "network-123",
                },
                openstack_config={"auth_url": "http://localhost:5000"},
            )

            mock_client.delete_network.assert_called_once_with("network-123")

    @pytest.mark.asyncio
    async def test_cleanup_with_no_network(self) -> None:
        """Test cleanup when no network ID is present."""
        deployment_id = uuid4()

        with patch(
            "orchestrator.workflows.deployment.activities.OpenStackClient"
        ) as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = AsyncMock()

            mock_client_class.return_value = mock_client

            await cleanup_orphaned_resources_activity(
                deployment_id=deployment_id,
                resources={
                    "server_ids": ["server-1"],
                    # No network_id
                },
                openstack_config={"auth_url": "http://localhost:5000"},
            )

            # Should delete server but not attempt network deletion
            mock_client.delete_server.assert_called_once()
            mock_client.delete_network.assert_not_called()


# Note: Additional tests for OpenStack integration activities (create_vm, poll_vm, delete_vm, etc.)
# are covered through integration tests. Unit testing these requires extensive mocking of
# OpenStack client interactions which is better validated through integration testing.
