"""Tests for ScaleWorkflow."""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from orchestrator.models.deployment import DeploymentStatus
from orchestrator.workflows.scaling.models import ScaleWorkflowInput, ScaleWorkflowResult


@pytest.fixture
def scale_input():  # type: ignore[no-untyped-def]
    """Create test scale workflow input."""
    return ScaleWorkflowInput(
        deployment_id=uuid4(),
        current_count=2,
        target_count=4,
        min_count=1,
        max_count=10,
        resources={
            "server_ids": ["server-1", "server-2"],
            "network_id": "network-123",
        },
        template={"vm_config": {"flavor": "m1.small", "image": "ubuntu-22.04"}},
        cloud_region="RegionOne",
    )


class TestScaleWorkflow:
    """Test scale workflow orchestration."""

    @pytest.mark.asyncio
    async def test_scale_out_success(self, scale_input: ScaleWorkflowInput) -> None:
        """Test successful scale-out (adding VMs)."""
        from orchestrator.workflows.scaling.scale import ScaleWorkflow

        # Mock activities
        with (
            patch("orchestrator.workflows.scaling.scale.scale_out_activity") as mock_scale_out,
            patch("orchestrator.workflows.scaling.scale.update_deployment_status_activity") as mock_update_status,
        ):
            # Setup mocks
            mock_scale_out.return_value = {
                "new_server_ids": ["server-3", "server-4"],
                "success": True,
            }
            mock_update_status.return_value = None

            # Execute workflow
            workflow = ScaleWorkflow()
            result = await workflow.execute(scale_input)

            # Verify result
            assert result.success is True
            assert result.deployment_id == scale_input.deployment_id
            assert result.initial_count == 2
            assert result.final_count == 4
            assert result.operation == "scale-out"
            assert len(result.new_server_ids) == 2
            assert "server-3" in result.new_server_ids
            assert "server-4" in result.new_server_ids

            # Verify activities were called
            mock_scale_out.assert_called_once()
            call_kwargs = mock_scale_out.call_args[1]
            assert call_kwargs["count_to_add"] == 2
            assert call_kwargs["template"] == scale_input.template
            assert call_kwargs["cloud_region"] == scale_input.cloud_region

    @pytest.mark.asyncio
    async def test_scale_in_success(self, scale_input: ScaleWorkflowInput) -> None:
        """Test successful scale-in (removing VMs)."""
        from orchestrator.workflows.scaling.scale import ScaleWorkflow

        # Modify input for scale-in (4 → 2)
        scale_input.current_count = 4
        scale_input.target_count = 2
        scale_input.resources["server_ids"] = [
            "server-1",
            "server-2",
            "server-3",
            "server-4",
        ]

        # Mock activities
        with (
            patch("orchestrator.workflows.scaling.scale.scale_in_activity") as mock_scale_in,
            patch("orchestrator.workflows.scaling.scale.update_deployment_status_activity") as mock_update_status,
        ):
            # Setup mocks
            mock_scale_in.return_value = {
                "removed_server_ids": ["server-3", "server-4"],
                "success": True,
            }
            mock_update_status.return_value = None

            # Execute workflow
            workflow = ScaleWorkflow()
            result = await workflow.execute(scale_input)

            # Verify result
            assert result.success is True
            assert result.deployment_id == scale_input.deployment_id
            assert result.initial_count == 4
            assert result.final_count == 2
            assert result.operation == "scale-in"
            assert len(result.removed_server_ids) == 2
            assert "server-3" in result.removed_server_ids
            assert "server-4" in result.removed_server_ids

            # Verify activities were called
            mock_scale_in.assert_called_once()
            call_kwargs = mock_scale_in.call_args[1]
            assert call_kwargs["count_to_remove"] == 2
            assert call_kwargs["min_count"] == scale_input.min_count

    @pytest.mark.asyncio
    async def test_no_scaling_needed(self, scale_input: ScaleWorkflowInput) -> None:
        """Test when current count equals target count."""
        from orchestrator.workflows.scaling.scale import ScaleWorkflow

        # Modify input so no scaling is needed
        scale_input.target_count = 2  # Same as current_count

        # Mock activities (should not be called)
        with (
            patch("orchestrator.workflows.scaling.scale.scale_out_activity") as mock_scale_out,
            patch("orchestrator.workflows.scaling.scale.scale_in_activity") as mock_scale_in,
            patch("orchestrator.workflows.scaling.scale.update_deployment_status_activity") as mock_update_status,
        ):
            mock_update_status.return_value = None

            # Execute workflow
            workflow = ScaleWorkflow()
            result = await workflow.execute(scale_input)

            # Verify result
            assert result.success is True
            assert result.operation == "none"
            assert result.initial_count == 2
            assert result.final_count == 2
            assert result.new_server_ids == []
            assert result.removed_server_ids == []

            # Verify scaling activities were not called
            mock_scale_out.assert_not_called()
            mock_scale_in.assert_not_called()

    @pytest.mark.asyncio
    async def test_scale_out_respects_max_count(self, scale_input: ScaleWorkflowInput) -> None:
        """Test scale-out respects max_count constraint."""
        from orchestrator.workflows.scaling.scale import ScaleWorkflow

        # Try to scale beyond max_count
        scale_input.target_count = 12  # Exceeds max_count=10
        scale_input.max_count = 10

        # Execute workflow
        workflow = ScaleWorkflow()
        result = await workflow.execute(scale_input)

        # Verify result - should cap at max_count
        assert result.success is False
        assert "exceeds max_count" in result.error.lower()

    @pytest.mark.asyncio
    async def test_scale_in_respects_min_count(self, scale_input: ScaleWorkflowInput) -> None:
        """Test scale-in respects min_count constraint."""
        from orchestrator.workflows.scaling.scale import ScaleWorkflow

        # Try to scale below min_count
        scale_input.current_count = 3
        scale_input.target_count = 0  # Below min_count=1
        scale_input.min_count = 1
        scale_input.resources["server_ids"] = ["server-1", "server-2", "server-3"]

        # Execute workflow
        workflow = ScaleWorkflow()
        result = await workflow.execute(scale_input)

        # Verify result - should fail
        assert result.success is False
        assert "below min_count" in result.error.lower()

    @pytest.mark.asyncio
    async def test_scale_out_failure(self, scale_input: ScaleWorkflowInput) -> None:
        """Test scale-out failure handling."""
        from orchestrator.workflows.scaling.scale import ScaleWorkflow

        # Mock activities
        with (
            patch("orchestrator.workflows.scaling.scale.scale_out_activity") as mock_scale_out,
            patch("orchestrator.workflows.scaling.scale.update_deployment_status_activity") as mock_update_status,
        ):
            # Setup mocks - scale_out fails
            mock_scale_out.return_value = {
                "new_server_ids": [],
                "success": False,
                "error": "Failed to create VMs",
            }
            mock_update_status.return_value = None

            # Execute workflow
            workflow = ScaleWorkflow()
            result = await workflow.execute(scale_input)

            # Verify result
            assert result.success is False
            assert "Failed to create VMs" in result.error

            # Verify status update was called with error
            mock_update_status.assert_called_once()
            call_kwargs = mock_update_status.call_args[1]
            assert call_kwargs["status"] == DeploymentStatus.FAILED

    @pytest.mark.asyncio
    async def test_scale_in_failure(self, scale_input: ScaleWorkflowInput) -> None:
        """Test scale-in failure handling."""
        from orchestrator.workflows.scaling.scale import ScaleWorkflow

        # Modify input for scale-in
        scale_input.current_count = 4
        scale_input.target_count = 2
        scale_input.resources["server_ids"] = [
            "server-1",
            "server-2",
            "server-3",
            "server-4",
        ]

        # Mock activities
        with (
            patch("orchestrator.workflows.scaling.scale.scale_in_activity") as mock_scale_in,
            patch("orchestrator.workflows.scaling.scale.update_deployment_status_activity") as mock_update_status,
        ):
            # Setup mocks - scale_in fails
            mock_scale_in.return_value = {
                "removed_server_ids": [],
                "success": False,
                "error": "Failed to delete VMs",
            }
            mock_update_status.return_value = None

            # Execute workflow
            workflow = ScaleWorkflow()
            result = await workflow.execute(scale_input)

            # Verify result
            assert result.success is False
            assert "Failed to delete VMs" in result.error

            # Verify status update was called with error
            mock_update_status.assert_called_once()


class TestRunScaleWorkflow:
    """Test run_scale_workflow convenience function."""

    @pytest.mark.asyncio
    async def test_run_scale_workflow(self) -> None:
        """Test run_scale_workflow function."""
        from orchestrator.workflows.scaling.scale import run_scale_workflow

        deployment_id = uuid4()

        # Mock workflow execution
        with patch("orchestrator.workflows.scaling.scale.ScaleWorkflow") as mock_workflow_class:
            mock_workflow = AsyncMock()
            mock_workflow_class.return_value = mock_workflow

            mock_result = ScaleWorkflowResult(
                success=True,
                deployment_id=deployment_id,
                initial_count=2,
                final_count=4,
                operation="scale-out",
                new_server_ids=["server-3", "server-4"],
                removed_server_ids=[],
                error=None,
            )
            mock_workflow.execute.return_value = mock_result

            # Execute function
            result = await run_scale_workflow(
                deployment_id=deployment_id,
                current_count=2,
                target_count=4,
                min_count=1,
                max_count=10,
                resources={"server_ids": ["server-1", "server-2"]},
                template={"vm_config": {"flavor": "m1.small"}},
                cloud_region="RegionOne",
            )

            # Verify result
            assert result.success is True
            assert result.final_count == 4
            mock_workflow.execute.assert_called_once()
