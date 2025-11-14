"""
Delete deployment workflow.

Orchestrates the deletion of infrastructure resources.
"""

import asyncio

from orchestrator.logging import logger
from orchestrator.models.deployment import DeploymentStatus
from orchestrator.workflows.deployment.activities import (
    cleanup_orphaned_resources_activity,
    delete_network_activity,
    delete_vm_activity,
    update_deployment_status_activity,
)
from orchestrator.workflows.deployment.models import (
    DeleteWorkflowInput,
    DeleteWorkflowResult,
)


class DeleteWorkflow:
    """Workflow for deleting infrastructure deployments."""

    def __init__(self, openstack_config: dict):
        """
        Initialize delete workflow.

        Args:
            openstack_config: OpenStack client configuration
        """
        self.openstack_config = openstack_config

    async def execute(self, workflow_input: DeleteWorkflowInput) -> DeleteWorkflowResult:
        """
        Execute delete workflow.

        Steps:
        1. Update deployment status to IN_PROGRESS
        2. Delete VMs in parallel
        3. Delete network
        4. Update deployment status to DELETED

        On error:
        - Run cleanup for orphaned resources
        - Update deployment status to FAILED

        Args:
            workflow_input: Workflow input parameters

        Returns:
            DeleteWorkflowResult with success status
        """
        deployment_id = workflow_input.deployment_id
        resources = workflow_input.resources

        logger.info(
            "delete_workflow_started",
            deployment_id=str(deployment_id),
            cloud_region=workflow_input.cloud_region,
            resources=resources,
        )

        try:
            # Step 1: Update status to IN_PROGRESS
            await update_deployment_status_activity(
                deployment_id=deployment_id,
                status=DeploymentStatus.IN_PROGRESS,
            )

            # Step 2: Delete VMs in parallel
            server_ids = resources.get("server_ids", [])
            if server_ids:
                logger.info(
                    "deleting_servers",
                    deployment_id=str(deployment_id),
                    server_count=len(server_ids),
                )

                delete_vm_tasks = [
                    delete_vm_activity(
                        deployment_id=deployment_id,
                        server_id=server_id,
                        openstack_config=self.openstack_config,
                    )
                    for server_id in server_ids
                ]

                await asyncio.gather(*delete_vm_tasks)

                logger.info(
                    "servers_deleted",
                    deployment_id=str(deployment_id),
                    server_count=len(server_ids),
                )

            # Step 3: Delete network
            network_id = resources.get("network_id")
            if network_id:
                logger.info(
                    "deleting_network",
                    deployment_id=str(deployment_id),
                    network_id=network_id,
                )

                await delete_network_activity(
                    deployment_id=deployment_id,
                    network_id=network_id,
                    openstack_config=self.openstack_config,
                )

                logger.info(
                    "network_deleted",
                    deployment_id=str(deployment_id),
                    network_id=network_id,
                )

            # Step 4: Update deployment status to DELETED
            await update_deployment_status_activity(
                deployment_id=deployment_id,
                status=DeploymentStatus.DELETED,
            )

            logger.info(
                "delete_workflow_completed",
                deployment_id=str(deployment_id),
            )

            return DeleteWorkflowResult(
                deployment_id=deployment_id,
                success=True,
            )

        except Exception as e:
            logger.error(
                "delete_workflow_failed",
                deployment_id=str(deployment_id),
                error=str(e),
            )

            # Best-effort cleanup of orphaned resources
            try:
                await cleanup_orphaned_resources_activity(
                    deployment_id=deployment_id,
                    resources=resources,
                    openstack_config=self.openstack_config,
                )
            except Exception as cleanup_error:
                logger.error(
                    "cleanup_orphaned_resources_failed",
                    deployment_id=str(deployment_id),
                    error=str(cleanup_error),
                )

            # Update deployment status to FAILED
            try:
                await update_deployment_status_activity(
                    deployment_id=deployment_id,
                    status=DeploymentStatus.FAILED,
                    error={
                        "message": str(e),
                        "phase": "deletion",
                    },
                )
            except Exception as status_error:
                logger.error(
                    "failed_to_update_deployment_status",
                    deployment_id=str(deployment_id),
                    error=str(status_error),
                )

            return DeleteWorkflowResult(
                deployment_id=deployment_id,
                success=False,
                error=str(e),
            )


async def run_delete_workflow(
    deployment_id: object,
    cloud_region: str,
    resources: dict,
    openstack_config: dict | None = None,
) -> DeleteWorkflowResult:
    """
    Convenience function to run delete workflow.

    Args:
        deployment_id: Deployment ID
        cloud_region: Cloud region
        resources: Resources to delete
        openstack_config: Optional OpenStack configuration

    Returns:
        DeleteWorkflowResult
    """
    if openstack_config is None:
        # TODO: Load from settings/config
        openstack_config = {}

    workflow_input = DeleteWorkflowInput(
        deployment_id=deployment_id,
        cloud_region=cloud_region,
        resources=resources,
    )

    workflow = DeleteWorkflow(openstack_config=openstack_config)
    return await workflow.execute(workflow_input)
