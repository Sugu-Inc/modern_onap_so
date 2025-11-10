"""Tests for ConfigureWorkflow."""

from pathlib import Path
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from orchestrator.clients.ansible.client import PlaybookStatus
from orchestrator.workflows.configuration.models import (
    ConfigureWorkflowInput,
    ConfigureWorkflowResult,
)


@pytest.fixture
def workflow_input():
    """Create sample workflow input."""
    return ConfigureWorkflowInput(
        deployment_id=uuid4(),
        playbook_path="/playbooks/configure_web.yml",
        extra_vars={"app_version": "1.2.3", "environment": "production"},
        limit=None,
        resources={
            "server_ids": ["vm-123", "vm-456"],
            "network_id": "net-123",
        },
    )


class TestConfigureWorkflow:
    """Test ConfigureWorkflow class."""

    @pytest.mark.asyncio
    async def test_execute_success(self, workflow_input: ConfigureWorkflowInput) -> None:
        """Test successful workflow execution."""
        from orchestrator.workflows.configuration.configure import ConfigureWorkflow

        # Mock activities
        with (
            patch(
                "orchestrator.workflows.configuration.configure.get_vm_addresses_activity"
            ) as mock_get_addresses,
            patch(
                "orchestrator.workflows.configuration.configure.run_ansible_activity"
            ) as mock_run_ansible,
            patch(
                "orchestrator.workflows.configuration.configure.update_deployment_status_activity"
            ) as mock_update_status,
        ):
            # Setup mock returns
            mock_get_addresses.return_value = {
                "vm-123": "10.0.0.5",
                "vm-456": "10.0.0.6",
            }
            mock_run_ansible.return_value = {
                "execution_id": uuid4(),
                "status": PlaybookStatus.SUCCESSFUL,
                "return_code": 0,
                "stats": {"ok": {"10.0.0.5": 5, "10.0.0.6": 5}},
                "error": None,
            }
            mock_update_status.return_value = None

            # Execute workflow
            workflow = ConfigureWorkflow()
            result = await workflow.execute(workflow_input)

            # Verify result
            assert result.success is True
            assert result.deployment_id == workflow_input.deployment_id
            assert result.execution_id is not None
            assert result.configured_hosts == ["10.0.0.5", "10.0.0.6"]
            assert result.error is None

            # Verify activities were called
            mock_get_addresses.assert_called_once()
            mock_run_ansible.assert_called_once()
            assert mock_update_status.call_count == 1

    @pytest.mark.asyncio
    async def test_execute_playbook_failure(
        self, workflow_input: ConfigureWorkflowInput
    ) -> None:
        """Test workflow execution with playbook failure."""
        from orchestrator.workflows.configuration.configure import ConfigureWorkflow

        # Mock activities
        with (
            patch(
                "orchestrator.workflows.configuration.configure.get_vm_addresses_activity"
            ) as mock_get_addresses,
            patch(
                "orchestrator.workflows.configuration.configure.run_ansible_activity"
            ) as mock_run_ansible,
            patch(
                "orchestrator.workflows.configuration.configure.update_deployment_status_activity"
            ) as mock_update_status,
        ):
            # Setup mock returns
            mock_get_addresses.return_value = {
                "vm-123": "10.0.0.5",
                "vm-456": "10.0.0.6",
            }
            mock_run_ansible.return_value = {
                "execution_id": uuid4(),
                "status": PlaybookStatus.FAILED,
                "return_code": 2,
                "stats": {"ok": {"10.0.0.5": 3}, "failures": {"10.0.0.6": 1}},
                "error": "Task failed on host 10.0.0.6",
            }
            mock_update_status.return_value = None

            # Execute workflow
            workflow = ConfigureWorkflow()
            result = await workflow.execute(workflow_input)

            # Verify result
            assert result.success is False
            assert result.deployment_id == workflow_input.deployment_id
            assert result.execution_id is not None
            assert "Task failed" in result.error
            assert result.configured_hosts == []

            # Verify status update was called with error
            mock_update_status.assert_called_once()
            call_kwargs = mock_update_status.call_args[1]
            assert "error" in call_kwargs

    @pytest.mark.asyncio
    async def test_execute_no_vms(self, workflow_input: ConfigureWorkflowInput) -> None:
        """Test workflow execution with no VMs."""
        from orchestrator.workflows.configuration.configure import ConfigureWorkflow

        # Modify input to have no VMs
        workflow_input.resources = {"network_id": "net-123"}

        # Mock activities
        with (
            patch(
                "orchestrator.workflows.configuration.configure.get_vm_addresses_activity"
            ) as mock_get_addresses,
            patch(
                "orchestrator.workflows.configuration.configure.run_ansible_activity"
            ) as mock_run_ansible,
            patch(
                "orchestrator.workflows.configuration.configure.update_deployment_status_activity"
            ) as mock_update_status,
        ):
            # Execute workflow
            workflow = ConfigureWorkflow()
            result = await workflow.execute(workflow_input)

            # Verify result
            assert result.success is False
            assert "No VMs found" in result.error
            assert result.configured_hosts == []

            # Verify activities were not called (except status update)
            mock_get_addresses.assert_not_called()
            mock_run_ansible.assert_not_called()
            mock_update_status.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_with_limit(self, workflow_input: ConfigureWorkflowInput) -> None:
        """Test workflow execution with host limit."""
        from orchestrator.workflows.configuration.configure import ConfigureWorkflow

        # Add limit to input
        workflow_input.limit = "vm-123"

        # Mock activities
        with (
            patch(
                "orchestrator.workflows.configuration.configure.get_vm_addresses_activity"
            ) as mock_get_addresses,
            patch(
                "orchestrator.workflows.configuration.configure.run_ansible_activity"
            ) as mock_run_ansible,
            patch(
                "orchestrator.workflows.configuration.configure.update_deployment_status_activity"
            ) as mock_update_status,
        ):
            # Setup mock returns
            mock_get_addresses.return_value = {
                "vm-123": "10.0.0.5",
                "vm-456": "10.0.0.6",
            }
            mock_run_ansible.return_value = {
                "execution_id": uuid4(),
                "status": PlaybookStatus.SUCCESSFUL,
                "return_code": 0,
                "stats": {"ok": {"10.0.0.5": 5}},
                "error": None,
            }
            mock_update_status.return_value = None

            # Execute workflow
            workflow = ConfigureWorkflow()
            result = await workflow.execute(workflow_input)

            # Verify result
            assert result.success is True

            # Verify ansible was called with limit
            call_kwargs = mock_run_ansible.call_args[1]
            assert call_kwargs["limit"] == "vm-123"

    @pytest.mark.asyncio
    async def test_execute_ansible_timeout(
        self, workflow_input: ConfigureWorkflowInput
    ) -> None:
        """Test workflow execution with Ansible timeout."""
        from orchestrator.workflows.configuration.configure import ConfigureWorkflow

        # Mock activities
        with (
            patch(
                "orchestrator.workflows.configuration.configure.get_vm_addresses_activity"
            ) as mock_get_addresses,
            patch(
                "orchestrator.workflows.configuration.configure.run_ansible_activity"
            ) as mock_run_ansible,
            patch(
                "orchestrator.workflows.configuration.configure.update_deployment_status_activity"
            ) as mock_update_status,
        ):
            # Setup mock returns
            mock_get_addresses.return_value = {
                "vm-123": "10.0.0.5",
                "vm-456": "10.0.0.6",
            }
            mock_run_ansible.return_value = {
                "execution_id": uuid4(),
                "status": PlaybookStatus.TIMEOUT,
                "return_code": None,
                "stats": {},
                "error": "Playbook execution timed out after 300 seconds",
            }
            mock_update_status.return_value = None

            # Execute workflow
            workflow = ConfigureWorkflow()
            result = await workflow.execute(workflow_input)

            # Verify result
            assert result.success is False
            assert "timed out" in result.error.lower()
            assert result.configured_hosts == []

    @pytest.mark.asyncio
    async def test_execute_exception_handling(
        self, workflow_input: ConfigureWorkflowInput
    ) -> None:
        """Test workflow execution handles exceptions gracefully."""
        from orchestrator.workflows.configuration.configure import ConfigureWorkflow

        # Mock activities
        with (
            patch(
                "orchestrator.workflows.configuration.configure.get_vm_addresses_activity"
            ) as mock_get_addresses,
            patch(
                "orchestrator.workflows.configuration.configure.run_ansible_activity"
            ) as mock_run_ansible,
            patch(
                "orchestrator.workflows.configuration.configure.update_deployment_status_activity"
            ) as mock_update_status,
        ):
            # Setup mock to raise exception
            mock_get_addresses.side_effect = Exception("Failed to get VM addresses")
            mock_update_status.return_value = None

            # Execute workflow
            workflow = ConfigureWorkflow()
            result = await workflow.execute(workflow_input)

            # Verify result
            assert result.success is False
            assert "Failed to get VM addresses" in result.error
            assert result.configured_hosts == []

            # Verify run_ansible was not called
            mock_run_ansible.assert_not_called()


class TestRunConfigureWorkflow:
    """Test run_configure_workflow convenience function."""

    @pytest.mark.asyncio
    async def test_run_configure_workflow(self) -> None:
        """Test that run_configure_workflow executes the workflow."""
        from orchestrator.workflows.configuration.configure import run_configure_workflow

        deployment_id = uuid4()

        # Mock the workflow execution
        with patch(
            "orchestrator.workflows.configuration.configure.ConfigureWorkflow"
        ) as mock_workflow_class:
            mock_workflow = AsyncMock()
            mock_workflow_class.return_value = mock_workflow
            mock_workflow.execute.return_value = ConfigureWorkflowResult(
                success=True,
                deployment_id=deployment_id,
                execution_id=uuid4(),
                configured_hosts=["10.0.0.5"],
                error=None,
            )

            # Execute function
            result = await run_configure_workflow(
                deployment_id=deployment_id,
                playbook_path="/playbooks/test.yml",
                extra_vars={"key": "value"},
                limit=None,
                resources={"server_ids": ["vm-123"]},
            )

            # Verify workflow was created and executed
            mock_workflow_class.assert_called_once()
            mock_workflow.execute.assert_called_once()

            # Verify result
            assert result.success is True
            assert result.deployment_id == deployment_id
