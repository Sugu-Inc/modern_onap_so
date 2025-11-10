"""
Scaling workflow.

Orchestrates VM scaling operations (scale-out and scale-in).
"""

from uuid import UUID

from orchestrator.models.deployment import DeploymentStatus
from orchestrator.workflows.deployment.activities import update_deployment_status_activity
from orchestrator.workflows.scaling.activities import scale_in_activity, scale_out_activity
from orchestrator.workflows.scaling.models import ScaleWorkflowInput, ScaleWorkflowResult


class ScaleWorkflow:
    """
    Workflow for scaling deployments.

    Flow:
    1. Validate scaling constraints (min/max count)
    2. Determine operation type (scale-out/scale-in/none)
    3. Execute scaling operation
    4. Update deployment status
    """

    def __init__(self, openstack_config: dict | None = None):
        """
        Initialize workflow.

        Args:
            openstack_config: OpenStack connection configuration
        """
        self.openstack_config = openstack_config or {}

    async def execute(self, workflow_input: ScaleWorkflowInput) -> ScaleWorkflowResult:
        """
        Execute scaling workflow.

        Args:
            workflow_input: Workflow input parameters

        Returns:
            Workflow execution result
        """
        try:
            # Step 1: Validate constraints
            if workflow_input.target_count < workflow_input.min_count:
                return ScaleWorkflowResult(
                    success=False,
                    deployment_id=workflow_input.deployment_id,
                    initial_count=workflow_input.current_count,
                    final_count=workflow_input.current_count,
                    operation="none",
                    new_server_ids=[],
                    removed_server_ids=[],
                    error=f"Target count ({workflow_input.target_count}) is below min_count ({workflow_input.min_count})",
                )

            if (
                workflow_input.max_count is not None
                and workflow_input.target_count > workflow_input.max_count
            ):
                return ScaleWorkflowResult(
                    success=False,
                    deployment_id=workflow_input.deployment_id,
                    initial_count=workflow_input.current_count,
                    final_count=workflow_input.current_count,
                    operation="none",
                    new_server_ids=[],
                    removed_server_ids=[],
                    error=f"Target count ({workflow_input.target_count}) exceeds max_count ({workflow_input.max_count})",
                )

            # Step 2: Determine operation type
            if workflow_input.target_count > workflow_input.current_count:
                # Scale-out
                count_to_add = workflow_input.target_count - workflow_input.current_count
                network_id = workflow_input.resources.get("network_id", "")

                # Execute scale-out activity
                scale_result = await scale_out_activity(
                    count_to_add=count_to_add,
                    template=workflow_input.template,
                    network_id=network_id,
                    cloud_region=workflow_input.cloud_region,
                    openstack_config=self.openstack_config,
                )

                if not scale_result["success"]:
                    # Update deployment status with error
                    await update_deployment_status_activity(
                        deployment_id=workflow_input.deployment_id,
                        status=DeploymentStatus.FAILED,
                        error={
                            "message": scale_result["error"],
                            "operation": "scale-out",
                        },
                    )

                    return ScaleWorkflowResult(
                        success=False,
                        deployment_id=workflow_input.deployment_id,
                        initial_count=workflow_input.current_count,
                        final_count=workflow_input.current_count,
                        operation="scale-out",
                        new_server_ids=[],
                        removed_server_ids=[],
                        error=scale_result["error"],
                    )

                # Update deployment status to COMPLETED
                await update_deployment_status_activity(
                    deployment_id=workflow_input.deployment_id,
                    status=DeploymentStatus.COMPLETED,
                )

                return ScaleWorkflowResult(
                    success=True,
                    deployment_id=workflow_input.deployment_id,
                    initial_count=workflow_input.current_count,
                    final_count=workflow_input.target_count,
                    operation="scale-out",
                    new_server_ids=scale_result["new_server_ids"],
                    removed_server_ids=[],
                    error=None,
                )

            elif workflow_input.target_count < workflow_input.current_count:
                # Scale-in
                count_to_remove = workflow_input.current_count - workflow_input.target_count
                server_ids = workflow_input.resources.get("server_ids", [])

                # Execute scale-in activity
                scale_result = await scale_in_activity(
                    server_ids=server_ids,
                    count_to_remove=count_to_remove,
                    min_count=workflow_input.min_count,
                    cloud_region=workflow_input.cloud_region,
                    openstack_config=self.openstack_config,
                )

                if not scale_result["success"]:
                    # Update deployment status with error
                    await update_deployment_status_activity(
                        deployment_id=workflow_input.deployment_id,
                        status=DeploymentStatus.FAILED,
                        error={
                            "message": scale_result["error"],
                            "operation": "scale-in",
                        },
                    )

                    return ScaleWorkflowResult(
                        success=False,
                        deployment_id=workflow_input.deployment_id,
                        initial_count=workflow_input.current_count,
                        final_count=workflow_input.current_count,
                        operation="scale-in",
                        new_server_ids=[],
                        removed_server_ids=[],
                        error=scale_result["error"],
                    )

                # Update deployment status to COMPLETED
                await update_deployment_status_activity(
                    deployment_id=workflow_input.deployment_id,
                    status=DeploymentStatus.COMPLETED,
                )

                return ScaleWorkflowResult(
                    success=True,
                    deployment_id=workflow_input.deployment_id,
                    initial_count=workflow_input.current_count,
                    final_count=workflow_input.target_count,
                    operation="scale-in",
                    new_server_ids=[],
                    removed_server_ids=scale_result["removed_server_ids"],
                    error=None,
                )

            else:
                # No scaling needed
                return ScaleWorkflowResult(
                    success=True,
                    deployment_id=workflow_input.deployment_id,
                    initial_count=workflow_input.current_count,
                    final_count=workflow_input.current_count,
                    operation="none",
                    new_server_ids=[],
                    removed_server_ids=[],
                    error=None,
                )

        except Exception as e:
            # Handle any unexpected errors
            error_message = f"Scaling workflow failed: {e!s}"

            # Try to update deployment status
            try:
                await update_deployment_status_activity(
                    deployment_id=workflow_input.deployment_id,
                    status=DeploymentStatus.FAILED,
                    error={"message": error_message},
                )
            except Exception:
                # If status update fails, log but don't fail the workflow result
                pass

            return ScaleWorkflowResult(
                success=False,
                deployment_id=workflow_input.deployment_id,
                initial_count=workflow_input.current_count,
                final_count=workflow_input.current_count,
                operation="none",
                new_server_ids=[],
                removed_server_ids=[],
                error=error_message,
            )


async def run_scale_workflow(
    deployment_id: UUID,
    current_count: int,
    target_count: int,
    min_count: int,
    max_count: int | None,
    resources: dict,
    template: dict,
    cloud_region: str,
    openstack_config: dict | None = None,
) -> ScaleWorkflowResult:
    """
    Convenience function to run scaling workflow.

    Args:
        deployment_id: Deployment to scale
        current_count: Current number of VMs
        target_count: Target number of VMs
        min_count: Minimum number of VMs
        max_count: Maximum number of VMs
        resources: Deployment resources
        template: VM template configuration
        cloud_region: Cloud region
        openstack_config: OpenStack configuration

    Returns:
        Workflow execution result
    """
    workflow_input = ScaleWorkflowInput(
        deployment_id=deployment_id,
        current_count=current_count,
        target_count=target_count,
        min_count=min_count,
        max_count=max_count,
        resources=resources,
        template=template,
        cloud_region=cloud_region,
    )

    workflow = ScaleWorkflow(openstack_config=openstack_config)
    return await workflow.execute(workflow_input)
