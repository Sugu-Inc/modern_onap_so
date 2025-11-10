"""Tests for DeploymentWorkflow."""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from orchestrator.models.deployment import DeploymentStatus
from orchestrator.workflows.deployment.models import (
    DeploymentWorkflowInput,
    DeploymentWorkflowResult,
    NetworkCreationResult,
    VMCreationResult,
    VMStatusResult,
)


@pytest.fixture
def workflow_input():
    """Create sample workflow input."""
    return DeploymentWorkflowInput(
        deployment_id=uuid4(),
        cloud_region="RegionOne",
        template={
            "network_config": {"cidr": "10.0.0.0/24"},
            "vm_config": {"count": 2, "flavor": "m1.small", "image": "ubuntu-22.04"},
        },
        parameters={"vm_count": 2, "flavor": "m1.medium"},
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


class TestDeploymentWorkflow:
    """Test DeploymentWorkflow class."""

    @pytest.mark.asyncio
    async def test_execute_success(
        self, workflow_input: DeploymentWorkflowInput, mock_openstack_config: dict
    ) -> None:
        """Test successful workflow execution."""
        from orchestrator.workflows.deployment.deploy import DeploymentWorkflow

        # Mock all activities
        with (
            patch(
                "orchestrator.workflows.deployment.deploy.update_deployment_status_activity"
            ) as mock_update_status,
            patch(
                "orchestrator.workflows.deployment.deploy.create_network_activity"
            ) as mock_create_network,
            patch(
                "orchestrator.workflows.deployment.deploy.create_vm_activity"
            ) as mock_create_vm,
            patch(
                "orchestrator.workflows.deployment.deploy.poll_vm_status_activity"
            ) as mock_poll_status,
        ):
            # Setup mock returns
            mock_update_status.return_value = None
            mock_create_network.return_value = NetworkCreationResult(
                network_id="net-123",
                subnet_id="subnet-123",
                network_name="test-network",
                subnet_cidr="10.0.0.0/24",
            )
            mock_create_vm.return_value = VMCreationResult(
                server_id="vm-123", server_name="test-vm-0", status="BUILD"
            )
            mock_poll_status.return_value = VMStatusResult(
                server_id="vm-123",
                status="ACTIVE",
                is_ready=True,
                addresses={"test-network": [{"addr": "10.0.0.5"}]},
            )

            # Execute workflow
            workflow = DeploymentWorkflow(openstack_config=mock_openstack_config)
            result = await workflow.execute(workflow_input)

            # Verify result
            assert result.success is True
            assert result.deployment_id == workflow_input.deployment_id
            assert result.network_id == "net-123"
            assert result.subnet_id == "subnet-123"
            assert len(result.server_ids) == 2
            assert result.error is None

            # Verify activities were called
            assert mock_update_status.call_count == 2  # IN_PROGRESS and COMPLETED
            mock_create_network.assert_called_once()
            assert mock_create_vm.call_count == 2  # 2 VMs
            mock_poll_status.assert_called()  # Called multiple times for polling

    @pytest.mark.asyncio
    async def test_execute_network_creation_failure(
        self, workflow_input: DeploymentWorkflowInput, mock_openstack_config: dict
    ) -> None:
        """Test workflow failure during network creation."""
        from orchestrator.workflows.deployment.deploy import DeploymentWorkflow

        with (
            patch(
                "orchestrator.workflows.deployment.deploy.update_deployment_status_activity"
            ) as mock_update_status,
            patch(
                "orchestrator.workflows.deployment.deploy.create_network_activity"
            ) as mock_create_network,
            patch(
                "orchestrator.workflows.deployment.deploy.rollback_resources_activity"
            ) as mock_rollback,
        ):
            # Setup mock to raise exception
            mock_update_status.return_value = None
            mock_create_network.side_effect = Exception("Network creation failed")
            mock_rollback.return_value = None

            # Execute workflow
            workflow = DeploymentWorkflow(openstack_config=mock_openstack_config)
            result = await workflow.execute(workflow_input)

            # Verify failure result
            assert result.success is False
            assert result.error == "Network creation failed"
            assert result.network_id is None

            # Verify rollback was called
            mock_rollback.assert_called_once()

            # Verify status was updated to FAILED
            final_call = mock_update_status.call_args_list[-1]
            assert final_call[1]["status"] == DeploymentStatus.FAILED

    @pytest.mark.asyncio
    async def test_execute_vm_creation_failure(
        self, workflow_input: DeploymentWorkflowInput, mock_openstack_config: dict
    ) -> None:
        """Test workflow failure during VM creation."""
        from orchestrator.workflows.deployment.deploy import DeploymentWorkflow

        with (
            patch(
                "orchestrator.workflows.deployment.deploy.update_deployment_status_activity"
            ) as mock_update_status,
            patch(
                "orchestrator.workflows.deployment.deploy.create_network_activity"
            ) as mock_create_network,
            patch(
                "orchestrator.workflows.deployment.deploy.create_vm_activity"
            ) as mock_create_vm,
            patch(
                "orchestrator.workflows.deployment.deploy.rollback_resources_activity"
            ) as mock_rollback,
        ):
            # Setup mocks
            mock_update_status.return_value = None
            mock_create_network.return_value = NetworkCreationResult(
                network_id="net-123",
                subnet_id="subnet-123",
                network_name="test-network",
                subnet_cidr="10.0.0.0/24",
            )
            mock_create_vm.side_effect = Exception("VM creation failed")
            mock_rollback.return_value = None

            # Execute workflow
            workflow = DeploymentWorkflow(openstack_config=mock_openstack_config)
            result = await workflow.execute(workflow_input)

            # Verify failure result
            assert result.success is False
            assert result.error == "VM creation failed"
            assert result.network_id == "net-123"  # Network was created
            assert len(result.server_ids) == 0  # No VMs created

            # Verify rollback was called with network_id
            mock_rollback.assert_called_once()
            rollback_call = mock_rollback.call_args
            assert rollback_call[1]["network_id"] == "net-123"

    @pytest.mark.asyncio
    async def test_execute_vm_polling_timeout(
        self, workflow_input: DeploymentWorkflowInput, mock_openstack_config: dict
    ) -> None:
        """Test workflow failure when VM polling times out."""
        from orchestrator.workflows.deployment.deploy import DeploymentWorkflow

        with (
            patch(
                "orchestrator.workflows.deployment.deploy.update_deployment_status_activity"
            ) as mock_update_status,
            patch(
                "orchestrator.workflows.deployment.deploy.create_network_activity"
            ) as mock_create_network,
            patch(
                "orchestrator.workflows.deployment.deploy.create_vm_activity"
            ) as mock_create_vm,
            patch(
                "orchestrator.workflows.deployment.deploy.poll_vm_status_activity"
            ) as mock_poll_status,
            patch(
                "orchestrator.workflows.deployment.deploy.rollback_resources_activity"
            ) as mock_rollback,
            patch("orchestrator.workflows.deployment.deploy.asyncio.sleep"),  # Skip sleep
        ):
            # Setup mocks
            mock_update_status.return_value = None
            mock_create_network.return_value = NetworkCreationResult(
                network_id="net-123",
                subnet_id="subnet-123",
                network_name="test-network",
                subnet_cidr="10.0.0.0/24",
            )
            mock_create_vm.return_value = VMCreationResult(
                server_id="vm-123", server_name="test-vm-0", status="BUILD"
            )
            # VMs never become ready
            mock_poll_status.return_value = VMStatusResult(
                server_id="vm-123",
                status="BUILD",
                is_ready=False,
                addresses={},
            )
            mock_rollback.return_value = None

            # Execute workflow
            workflow = DeploymentWorkflow(openstack_config=mock_openstack_config)
            result = await workflow.execute(workflow_input)

            # Verify failure result
            assert result.success is False
            assert "did not become ACTIVE" in result.error
            assert len(result.server_ids) == 2  # VMs were created but not ready

            # Verify rollback was called with server_ids
            mock_rollback.assert_called_once()
            rollback_call = mock_rollback.call_args
            assert len(rollback_call[1]["server_ids"]) == 2

    @pytest.mark.asyncio
    async def test_execute_rollback_failure(
        self, workflow_input: DeploymentWorkflowInput, mock_openstack_config: dict
    ) -> None:
        """Test that workflow handles rollback failures gracefully."""
        from orchestrator.workflows.deployment.deploy import DeploymentWorkflow

        with (
            patch(
                "orchestrator.workflows.deployment.deploy.update_deployment_status_activity"
            ) as mock_update_status,
            patch(
                "orchestrator.workflows.deployment.deploy.create_network_activity"
            ) as mock_create_network,
            patch(
                "orchestrator.workflows.deployment.deploy.create_vm_activity"
            ) as mock_create_vm,
            patch(
                "orchestrator.workflows.deployment.deploy.rollback_resources_activity"
            ) as mock_rollback,
        ):
            # Setup mocks
            mock_update_status.return_value = None
            mock_create_network.return_value = NetworkCreationResult(
                network_id="net-123",
                subnet_id="subnet-123",
                network_name="test-network",
                subnet_cidr="10.0.0.0/24",
            )
            mock_create_vm.side_effect = Exception("VM creation failed")
            # Rollback also fails
            mock_rollback.side_effect = Exception("Rollback failed")

            # Execute workflow - should not raise exception
            workflow = DeploymentWorkflow(openstack_config=mock_openstack_config)
            result = await workflow.execute(workflow_input)

            # Verify workflow still returns failure result
            assert result.success is False
            assert result.error == "VM creation failed"

            # Verify status was still updated to FAILED
            final_call = mock_update_status.call_args_list[-1]
            assert final_call[1]["status"] == DeploymentStatus.FAILED

    @pytest.mark.asyncio
    async def test_execute_uses_parameters_over_template(
        self, workflow_input: DeploymentWorkflowInput, mock_openstack_config: dict
    ) -> None:
        """Test that parameters override template values."""
        from orchestrator.workflows.deployment.deploy import DeploymentWorkflow

        with (
            patch(
                "orchestrator.workflows.deployment.deploy.update_deployment_status_activity"
            ) as mock_update_status,
            patch(
                "orchestrator.workflows.deployment.deploy.create_network_activity"
            ) as mock_create_network,
            patch(
                "orchestrator.workflows.deployment.deploy.create_vm_activity"
            ) as mock_create_vm,
            patch(
                "orchestrator.workflows.deployment.deploy.poll_vm_status_activity"
            ) as mock_poll_status,
        ):
            # Setup mocks
            mock_update_status.return_value = None
            mock_create_network.return_value = NetworkCreationResult(
                network_id="net-123",
                subnet_id="subnet-123",
                network_name="test-network",
                subnet_cidr="10.0.0.0/24",
            )
            mock_create_vm.return_value = VMCreationResult(
                server_id="vm-123", server_name="test-vm-0", status="BUILD"
            )
            mock_poll_status.return_value = VMStatusResult(
                server_id="vm-123", status="ACTIVE", is_ready=True, addresses={}
            )

            # Execute workflow
            workflow = DeploymentWorkflow(openstack_config=mock_openstack_config)
            await workflow.execute(workflow_input)

            # Verify create_vm was called with parameter flavor (m1.medium), not template flavor (m1.small)
            create_vm_call = mock_create_vm.call_args
            assert create_vm_call[1]["flavor"] == "m1.medium"  # From parameters
            assert create_vm_call[1]["image"] == "ubuntu-22.04"  # From template


class TestRunDeploymentWorkflow:
    """Test run_deployment_workflow convenience function."""

    @pytest.mark.asyncio
    async def test_run_deployment_workflow(self) -> None:
        """Test convenience function creates workflow and executes."""
        from orchestrator.workflows.deployment.deploy import run_deployment_workflow

        deployment_id = uuid4()
        template = {"network_config": {}, "vm_config": {}}

        with (
            patch(
                "orchestrator.workflows.deployment.deploy.DeploymentWorkflow"
            ) as mock_workflow_class,
        ):
            # Setup mock workflow instance
            mock_workflow = AsyncMock()
            mock_workflow_class.return_value = mock_workflow
            mock_workflow.execute.return_value = DeploymentWorkflowResult(
                deployment_id=deployment_id, success=True
            )

            # Call convenience function
            result = await run_deployment_workflow(
                deployment_id=deployment_id,
                cloud_region="RegionOne",
                template=template,
                parameters={"test": "value"},
            )

            # Verify workflow was created and executed
            mock_workflow_class.assert_called_once()
            mock_workflow.execute.assert_called_once()

            # Verify input was constructed correctly
            execute_call = mock_workflow.execute.call_args
            workflow_input = execute_call[0][0]
            assert workflow_input.deployment_id == deployment_id
            assert workflow_input.cloud_region == "RegionOne"
            assert workflow_input.template == template
            assert workflow_input.parameters == {"test": "value"}

            # Verify result
            assert result.success is True
