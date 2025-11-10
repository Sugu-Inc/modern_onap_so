"""Tests for UpdateWorkflow."""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from orchestrator.models.deployment import DeploymentStatus
from orchestrator.workflows.deployment.models import UpdateWorkflowInput, UpdateWorkflowResult


@pytest.fixture
def update_workflow_input():
    """Create sample update workflow input."""
    return UpdateWorkflowInput(
        deployment_id=uuid4(),
        cloud_region="RegionOne",
        current_resources={
            "network_id": "network-123",
            "subnet_id": "subnet-123",
            "server_ids": ["server-1", "server-2"],
        },
        updated_parameters={
            "flavor": "m1.large",  # Resize from m1.small to m1.large
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


class TestUpdateWorkflow:
    """Test UpdateWorkflow class."""

    @pytest.mark.asyncio
    async def test_execute_success_resize_vms(
        self, update_workflow_input: UpdateWorkflowInput, mock_openstack_config: dict
    ) -> None:
        """Test successful workflow execution with VM resize."""
        from orchestrator.workflows.deployment.update import UpdateWorkflow

        # Mock all activities
        with (
            patch(
                "orchestrator.workflows.deployment.update.update_deployment_status_activity"
            ) as mock_update_status,
            patch("orchestrator.workflows.deployment.update.resize_vm_activity") as mock_resize_vm,
        ):
            # Setup mock returns
            mock_update_status.return_value = None
            mock_resize_vm.return_value = True

            # Execute workflow
            workflow = UpdateWorkflow(openstack_config=mock_openstack_config)
            result = await workflow.execute(update_workflow_input)

            # Verify result
            assert result.success is True
            assert result.deployment_id == update_workflow_input.deployment_id
            assert result.error is None

            # Verify activities were called
            assert mock_resize_vm.call_count == 2  # 2 servers resized
            assert mock_update_status.call_count == 2  # IN_PROGRESS and COMPLETED

    @pytest.mark.asyncio
    async def test_execute_vm_resize_failure(
        self, update_workflow_input: UpdateWorkflowInput, mock_openstack_config: dict
    ) -> None:
        """Test workflow when VM resize fails."""
        from orchestrator.workflows.deployment.update import UpdateWorkflow

        with (
            patch(
                "orchestrator.workflows.deployment.update.update_deployment_status_activity"
            ) as mock_update_status,
            patch("orchestrator.workflows.deployment.update.resize_vm_activity") as mock_resize_vm,
        ):
            # Setup mocks
            mock_update_status.return_value = None
            mock_resize_vm.side_effect = Exception("VM resize failed")

            # Execute workflow
            workflow = UpdateWorkflow(openstack_config=mock_openstack_config)
            result = await workflow.execute(update_workflow_input)

            # Verify failure result
            assert result.success is False
            assert result.error == "VM resize failed"

            # Verify status was updated to FAILED
            final_call = mock_update_status.call_args_list[-1]
            assert final_call[1]["status"] == DeploymentStatus.FAILED

    @pytest.mark.asyncio
    async def test_execute_with_no_changes(self, mock_openstack_config: dict) -> None:
        """Test workflow when no changes are requested."""
        from orchestrator.workflows.deployment.update import UpdateWorkflow

        # Input with no updated parameters
        workflow_input = UpdateWorkflowInput(
            deployment_id=uuid4(),
            cloud_region="RegionOne",
            current_resources={
                "network_id": "network-123",
                "server_ids": ["server-1"],
            },
            updated_parameters={},
        )

        with patch(
            "orchestrator.workflows.deployment.update.update_deployment_status_activity"
        ) as mock_update_status:
            mock_update_status.return_value = None

            # Execute workflow
            workflow = UpdateWorkflow(openstack_config=mock_openstack_config)
            result = await workflow.execute(workflow_input)

            # Verify success (nothing to update)
            assert result.success is True
            assert result.error is None

            # Only status updates should be called (IN_PROGRESS and COMPLETED)
            assert mock_update_status.call_count == 2

    @pytest.mark.asyncio
    async def test_execute_network_update(self, mock_openstack_config: dict) -> None:
        """Test workflow with network configuration update."""
        from orchestrator.workflows.deployment.update import UpdateWorkflow

        # Input with network update
        workflow_input = UpdateWorkflowInput(
            deployment_id=uuid4(),
            cloud_region="RegionOne",
            current_resources={
                "network_id": "network-123",
                "subnet_id": "subnet-123",
                "server_ids": ["server-1"],
            },
            updated_parameters={
                "network_cidr": "10.0.1.0/24",  # Change subnet CIDR
            },
        )

        with (
            patch(
                "orchestrator.workflows.deployment.update.update_deployment_status_activity"
            ) as mock_update_status,
            patch(
                "orchestrator.workflows.deployment.update.update_network_activity"
            ) as mock_update_network,
        ):
            mock_update_status.return_value = None
            mock_update_network.return_value = {
                "network_id": "network-123",
                "subnet_id": "subnet-456",
            }

            # Execute workflow
            workflow = UpdateWorkflow(openstack_config=mock_openstack_config)
            result = await workflow.execute(workflow_input)

            # Verify success
            assert result.success is True

            # Verify network was updated
            mock_update_network.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_combined_updates(self, mock_openstack_config: dict) -> None:
        """Test workflow with both VM resize and network update."""
        from orchestrator.workflows.deployment.update import UpdateWorkflow

        # Input with both updates
        workflow_input = UpdateWorkflowInput(
            deployment_id=uuid4(),
            cloud_region="RegionOne",
            current_resources={
                "network_id": "network-123",
                "subnet_id": "subnet-123",
                "server_ids": ["server-1", "server-2"],
            },
            updated_parameters={
                "flavor": "m1.xlarge",
                "network_cidr": "10.0.2.0/24",
            },
        )

        with (
            patch(
                "orchestrator.workflows.deployment.update.update_deployment_status_activity"
            ) as mock_update_status,
            patch("orchestrator.workflows.deployment.update.resize_vm_activity") as mock_resize_vm,
            patch(
                "orchestrator.workflows.deployment.update.update_network_activity"
            ) as mock_update_network,
        ):
            mock_update_status.return_value = None
            mock_resize_vm.return_value = True
            mock_update_network.return_value = {
                "network_id": "network-123",
                "subnet_id": "subnet-789",
            }

            # Execute workflow
            workflow = UpdateWorkflow(openstack_config=mock_openstack_config)
            result = await workflow.execute(workflow_input)

            # Verify success
            assert result.success is True

            # Verify both operations were performed
            assert mock_resize_vm.call_count == 2  # 2 VMs resized
            mock_update_network.assert_called_once()


class TestRunUpdateWorkflow:
    """Test run_update_workflow convenience function."""

    @pytest.mark.asyncio
    async def test_run_update_workflow(self) -> None:
        """Test convenience function creates workflow and executes."""
        from orchestrator.workflows.deployment.update import run_update_workflow

        deployment_id = uuid4()
        current_resources = {"network_id": "net-123", "server_ids": ["vm-1"]}
        updated_parameters = {"flavor": "m1.large"}

        with patch(
            "orchestrator.workflows.deployment.update.UpdateWorkflow"
        ) as mock_workflow_class:
            # Setup mock workflow instance
            mock_workflow = AsyncMock()
            mock_workflow_class.return_value = mock_workflow
            mock_workflow.execute.return_value = UpdateWorkflowResult(
                deployment_id=deployment_id, success=True
            )

            # Call convenience function
            result = await run_update_workflow(
                deployment_id=deployment_id,
                cloud_region="RegionOne",
                current_resources=current_resources,
                updated_parameters=updated_parameters,
            )

            # Verify workflow was created and executed
            mock_workflow_class.assert_called_once()
            mock_workflow.execute.assert_called_once()

            # Verify input was constructed correctly
            execute_call = mock_workflow.execute.call_args
            workflow_input = execute_call[0][0]
            assert workflow_input.deployment_id == deployment_id
            assert workflow_input.cloud_region == "RegionOne"
            assert workflow_input.current_resources == current_resources
            assert workflow_input.updated_parameters == updated_parameters

            # Verify result
            assert result.success is True
