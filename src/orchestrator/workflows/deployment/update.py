"""
Update deployment workflow.

Orchestrates the update of existing infrastructure resources.
"""

import asyncio

from orchestrator.logging import logger
from orchestrator.models.deployment import DeploymentStatus
from orchestrator.workflows.deployment.activities import (
    resize_vm_activity,
    update_deployment_status_activity,
    update_network_activity,
)
from orchestrator.workflows.deployment.models import (
    UpdateWorkflowInput,
    UpdateWorkflowResult,
)


class UpdateWorkflow:
    """Workflow for updating infrastructure deployments."""

    def __init__(self, openstack_config: dict):
        """
        Initialize update workflow.

        Args:
            openstack_config: OpenStack client configuration
        """
        self.openstack_config = openstack_config

    async def execute(self, workflow_input: UpdateWorkflowInput) -> UpdateWorkflowResult:
        """
        Execute update workflow.

        Steps:
        1. Update deployment status to IN_PROGRESS
        2. Resize VMs if flavor changed (in parallel)
        3. Update network if CIDR changed
        4. Update deployment status to COMPLETED

        On error:
        - Update deployment status to FAILED

        Args:
            workflow_input: Workflow input parameters

        Returns:
            UpdateWorkflowResult with success status
        """
        deployment_id = workflow_input.deployment_id
        current_resources = workflow_input.current_resources
        updated_parameters = workflow_input.updated_parameters

        logger.info(
            "update_workflow_started",
            deployment_id=str(deployment_id),
            cloud_region=workflow_input.cloud_region,
            updates=updated_parameters,
        )

        updated_resources = current_resources.copy()

        try:
            # Step 1: Update status to IN_PROGRESS
            await update_deployment_status_activity(
                deployment_id=deployment_id,
                status=DeploymentStatus.IN_PROGRESS,
            )

            # Step 2: Resize VMs if flavor changed
            new_flavor = updated_parameters.get("flavor")
            if new_flavor:
                server_ids = current_resources.get("server_ids", [])

                if server_ids:
                    logger.info(
                        "resizing_servers",
                        deployment_id=str(deployment_id),
                        server_count=len(server_ids),
                        new_flavor=new_flavor,
                    )

                    resize_tasks = [
                        resize_vm_activity(
                            deployment_id=deployment_id,
                            server_id=server_id,
                            new_flavor=new_flavor,
                            openstack_config=self.openstack_config,
                        )
                        for server_id in server_ids
                    ]

                    await asyncio.gather(*resize_tasks)

                    logger.info(
                        "servers_resized",
                        deployment_id=str(deployment_id),
                        server_count=len(server_ids),
                    )

            # Step 3: Update network if CIDR changed
            new_cidr = updated_parameters.get("network_cidr")
            if new_cidr:
                network_id = current_resources.get("network_id")
                subnet_id = current_resources.get("subnet_id")

                if network_id and subnet_id:
                    logger.info(
                        "updating_network",
                        deployment_id=str(deployment_id),
                        network_id=network_id,
                        new_cidr=new_cidr,
                    )

                    network_result = await update_network_activity(
                        deployment_id=deployment_id,
                        network_id=network_id,
                        subnet_id=subnet_id,
                        new_cidr=new_cidr,
                        openstack_config=self.openstack_config,
                    )

                    # Update resources with new subnet ID
                    updated_resources.update(network_result)

                    logger.info(
                        "network_updated",
                        deployment_id=str(deployment_id),
                        network_result=network_result,
                    )

            # Step 4: Update deployment status to COMPLETED
            await update_deployment_status_activity(
                deployment_id=deployment_id,
                status=DeploymentStatus.COMPLETED,
                resources=updated_resources,
            )

            logger.info(
                "update_workflow_completed",
                deployment_id=str(deployment_id),
            )

            return UpdateWorkflowResult(
                deployment_id=deployment_id,
                success=True,
                updated_resources=updated_resources,
            )

        except Exception as e:
            logger.error(
                "update_workflow_failed",
                deployment_id=str(deployment_id),
                error=str(e),
            )

            # Update deployment status to FAILED
            try:
                await update_deployment_status_activity(
                    deployment_id=deployment_id,
                    status=DeploymentStatus.FAILED,
                    error={
                        "message": str(e),
                        "phase": "update",
                    },
                )
            except Exception as status_error:
                logger.error(
                    "failed_to_update_deployment_status",
                    deployment_id=str(deployment_id),
                    error=str(status_error),
                )

            return UpdateWorkflowResult(
                deployment_id=deployment_id,
                success=False,
                updated_resources={},
                error=str(e),
            )


async def run_update_workflow(
    deployment_id,
    cloud_region: str,
    current_resources: dict,
    updated_parameters: dict,
    openstack_config: dict | None = None,
) -> UpdateWorkflowResult:
    """
    Convenience function to run update workflow.

    Args:
        deployment_id: Deployment ID
        cloud_region: Cloud region
        current_resources: Current deployed resources
        updated_parameters: Parameters to update
        openstack_config: Optional OpenStack configuration

    Returns:
        UpdateWorkflowResult
    """
    if openstack_config is None:
        # TODO: Load from settings/config
        openstack_config = {}

    workflow_input = UpdateWorkflowInput(
        deployment_id=deployment_id,
        cloud_region=cloud_region,
        current_resources=current_resources,
        updated_parameters=updated_parameters,
    )

    workflow = UpdateWorkflow(openstack_config=openstack_config)
    return await workflow.execute(workflow_input)
