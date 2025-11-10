"""Tests for DeleteWorkflow."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from orchestrator.models.deployment import DeploymentStatus
from orchestrator.workflows.deployment.models import DeleteWorkflowInput, DeleteWorkflowResult


@pytest.fixture
def delete_workflow_input():
    """Create sample delete workflow input."""
    return DeleteWorkflowInput(
        deployment_id=uuid4(),
        cloud_region="RegionOne",
        resources={
            "network_id": "network-123",
            "subnet_id": "subnet-123",
            "server_ids": ["server-1", "server-2"],
        },
    )


@pytest.fixture
def mock_openstack_config():
    """Mock OpenStack configuration."""
    return {
        "auth_url": "http://keystone:5000/v3",
        "username": "admin",
        "password": "secret",
        "project_name": "admin",
        "region_name": "RegionOne",
    }


class TestDeleteWorkflow:
    """Test DeleteWorkflow class."""

    @pytest.mark.asyncio
    async def test_execute_success(
        self, delete_workflow_input: DeleteWorkflowInput, mock_openstack_config: dict
    ) -> None:
        """Test successful workflow execution."""
        from orchestrator.workflows.deployment.delete import DeleteWorkflow

        # Mock all activities
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
            workflow = DeleteWorkflow(openstack_config=mock_openstack_config)
            result = await workflow.execute(delete_workflow_input)

            # Verify result
            assert result.success is True
            assert result.deployment_id == delete_workflow_input.deployment_id
            assert result.error is None

            # Verify activities were called
            assert mock_delete_vm.call_count == 2  # 2 servers
            mock_delete_network.assert_called_once()
            assert mock_update_status.call_count == 2  # IN_PROGRESS and DELETED

    @pytest.mark.asyncio
    async def test_execute_vm_deletion_failure(
        self, delete_workflow_input: DeleteWorkflowInput, mock_openstack_config: dict
    ) -> None:
        """Test workflow when VM deletion fails."""
        from orchestrator.workflows.deployment.delete import DeleteWorkflow

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
            # Setup mocks
            mock_update_status.return_value = None
            mock_delete_vm.side_effect = Exception("VM deletion failed")
            mock_cleanup.return_value = None

            # Execute workflow
            workflow = DeleteWorkflow(openstack_config=mock_openstack_config)
            result = await workflow.execute(delete_workflow_input)

            # Verify failure result
            assert result.success is False
            assert result.error == "VM deletion failed"

            # Verify cleanup was called
            mock_cleanup.assert_called_once()

            # Verify status was updated to FAILED
            final_call = mock_update_status.call_args_list[-1]
            assert final_call[1]["status"] == DeploymentStatus.FAILED

    @pytest.mark.asyncio
    async def test_execute_network_deletion_failure(
        self, delete_workflow_input: DeleteWorkflowInput, mock_openstack_config: dict
    ) -> None:
        """Test workflow when network deletion fails."""
        from orchestrator.workflows.deployment.delete import DeleteWorkflow

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
            # Setup mocks
            mock_update_status.return_value = None
            mock_delete_vm.return_value = True
            mock_delete_network.side_effect = Exception("Network still in use")
            mock_cleanup.return_value = None

            # Execute workflow
            workflow = DeleteWorkflow(openstack_config=mock_openstack_config)
            result = await workflow.execute(delete_workflow_input)

            # Verify failure result
            assert result.success is False
            assert result.error == "Network still in use"

            # Verify cleanup was called
            mock_cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_with_no_resources(
        self, mock_openstack_config: dict
    ) -> None:
        """Test workflow when deployment has no resources."""
        from orchestrator.workflows.deployment.delete import DeleteWorkflow

        # Input with no resources
        workflow_input = DeleteWorkflowInput(
            deployment_id=uuid4(),
            cloud_region="RegionOne",
            resources={},
        )

        with patch(
            "orchestrator.workflows.deployment.delete.update_deployment_status_activity"
        ) as mock_update_status:
            mock_update_status.return_value = None

            # Execute workflow
            workflow = DeleteWorkflow(openstack_config=mock_openstack_config)
            result = await workflow.execute(workflow_input)

            # Verify success (nothing to delete)
            assert result.success is True
            assert result.error is None

            # Only status updates should be called
            assert mock_update_status.call_count == 2

    @pytest.mark.asyncio
    async def test_execute_partial_resources(
        self, mock_openstack_config: dict
    ) -> None:
        """Test workflow with only some resources (e.g., only network, no VMs)."""
        from orchestrator.workflows.deployment.delete import DeleteWorkflow

        # Input with only network
        workflow_input = DeleteWorkflowInput(
            deployment_id=uuid4(),
            cloud_region="RegionOne",
            resources={
                "network_id": "network-123",
                "subnet_id": "subnet-123",
            },
        )

        with (
            patch(
                "orchestrator.workflows.deployment.delete.update_deployment_status_activity"
            ) as mock_update_status,
            patch(
                "orchestrator.workflows.deployment.delete.delete_network_activity"
            ) as mock_delete_network,
        ):
            mock_update_status.return_value = None
            mock_delete_network.return_value = True

            # Execute workflow
            workflow = DeleteWorkflow(openstack_config=mock_openstack_config)
            result = await workflow.execute(workflow_input)

            # Verify success
            assert result.success is True

            # Verify network was deleted
            mock_delete_network.assert_called_once()


class TestRunDeleteWorkflow:
    """Test run_delete_workflow convenience function."""

    @pytest.mark.asyncio
    async def test_run_delete_workflow(self) -> None:
        """Test convenience function creates workflow and executes."""
        from orchestrator.workflows.deployment.delete import run_delete_workflow

        deployment_id = uuid4()
        resources = {"network_id": "net-123", "server_ids": ["vm-1"]}

        with patch(
            "orchestrator.workflows.deployment.delete.DeleteWorkflow"
        ) as mock_workflow_class:
            # Setup mock workflow instance
            mock_workflow = AsyncMock()
            mock_workflow_class.return_value = mock_workflow
            mock_workflow.execute.return_value = DeleteWorkflowResult(
                deployment_id=deployment_id, success=True
            )

            # Call convenience function
            result = await run_delete_workflow(
                deployment_id=deployment_id,
                cloud_region="RegionOne",
                resources=resources,
            )

            # Verify workflow was created and executed
            mock_workflow_class.assert_called_once()
            mock_workflow.execute.assert_called_once()

            # Verify input was constructed correctly
            execute_call = mock_workflow.execute.call_args
            workflow_input = execute_call[0][0]
            assert workflow_input.deployment_id == deployment_id
            assert workflow_input.cloud_region == "RegionOne"
            assert workflow_input.resources == resources

            # Verify result
            assert result.success is True
