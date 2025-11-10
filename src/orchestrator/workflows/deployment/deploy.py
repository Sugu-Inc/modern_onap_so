"""
Deployment workflow implementation.

Orchestrates the creation of infrastructure resources using activities.
"""

import asyncio
from uuid import UUID

from orchestrator.config import settings
from orchestrator.logging import logger
from orchestrator.models.deployment import DeploymentStatus
from orchestrator.workflows.deployment.activities import (
    create_network_activity,
    create_vm_activity,
    poll_vm_status_activity,
    rollback_resources_activity,
    update_deployment_status_activity,
)
from orchestrator.workflows.deployment.models import (
    DeploymentWorkflowInput,
    DeploymentWorkflowResult,
)


class DeploymentWorkflow:
    """
    Workflow for deploying infrastructure.

    Orchestrates network creation, VM creation, and status updates.
    Implements error handling with automatic rollback on failure.
    """

    def __init__(self, openstack_config: dict | None = None):
        """
        Initialize deployment workflow.

        Args:
            openstack_config: OpenStack client configuration (optional, uses settings if not provided)
        """
        self.openstack_config = openstack_config or {
            "auth_url": settings.openstack_auth_url,
            "username": settings.openstack_username,
            "password": settings.openstack_password,
            "project_name": settings.openstack_project_name,
            "region_name": settings.openstack_region,
        }

    async def execute(
        self, workflow_input: DeploymentWorkflowInput
    ) -> DeploymentWorkflowResult:
        """
        Execute deployment workflow.

        Steps:
        1. Update status to IN_PROGRESS
        2. Create network and subnet
        3. Create VMs
        4. Poll VMs until ACTIVE
        5. Update deployment with resources and mark COMPLETED

        On error: Rollback all resources and mark FAILED.

        Args:
            workflow_input: Workflow input parameters

        Returns:
            DeploymentWorkflowResult with success status and resource IDs
        """
        deployment_id = workflow_input.deployment_id
        template = workflow_input.template
        parameters = workflow_input.parameters

        logger.info("deployment_workflow_started", deployment_id=str(deployment_id))

        # Track created resources for rollback
        network_id: str | None = None
        subnet_id: str | None = None
        server_ids: list[str] = []

        try:
            # Step 1: Update status to IN_PROGRESS
            await update_deployment_status_activity(
                deployment_id, DeploymentStatus.IN_PROGRESS
            )

            # Step 2: Create network
            network_config = template.get("network_config", {})
            network_name = f"{workflow_input.deployment_id}-network"
            subnet_cidr = network_config.get("cidr", "192.168.1.0/24")

            network_result = await create_network_activity(
                deployment_id=deployment_id,
                network_name=network_name,
                subnet_cidr=subnet_cidr,
                cloud_region=workflow_input.cloud_region,
                openstack_config=self.openstack_config,
            )

            network_id = network_result.network_id
            subnet_id = network_result.subnet_id

            logger.info(
                "deployment_network_created",
                deployment_id=str(deployment_id),
                network_id=network_id,
            )

            # Step 3: Create VMs
            vm_config = template.get("vm_config", {})
            vm_count = parameters.get("vm_count", vm_config.get("count", 1))
            flavor = parameters.get("flavor", vm_config.get("flavor", "m1.small"))
            image = parameters.get("image", vm_config.get("image", "ubuntu-22.04"))

            # Create VMs in parallel
            vm_tasks = []
            for i in range(vm_count):
                vm_name = f"{deployment_id}-vm-{i}"
                vm_tasks.append(
                    create_vm_activity(
                        deployment_id=deployment_id,
                        vm_name=vm_name,
                        flavor=flavor,
                        image=image,
                        network_id=network_id,
                        openstack_config=self.openstack_config,
                    )
                )

            vm_results = await asyncio.gather(*vm_tasks)
            server_ids = [result.server_id for result in vm_results]

            logger.info(
                "deployment_vms_created",
                deployment_id=str(deployment_id),
                server_count=len(server_ids),
            )

            # Step 4: Poll VMs until all are ACTIVE
            max_poll_attempts = 60  # 5 minutes with 5 second intervals
            poll_interval = 5

            for attempt in range(max_poll_attempts):
                # Check status of all VMs
                status_tasks = [
                    poll_vm_status_activity(
                        deployment_id=deployment_id,
                        server_id=server_id,
                        openstack_config=self.openstack_config,
                    )
                    for server_id in server_ids
                ]

                status_results = await asyncio.gather(*status_tasks)

                # Check if all VMs are ready
                all_ready = all(result.is_ready for result in status_results)

                if all_ready:
                    logger.info(
                        "deployment_vms_ready",
                        deployment_id=str(deployment_id),
                        attempt=attempt + 1,
                    )
                    break

                # Not ready yet, wait before next poll
                if attempt < max_poll_attempts - 1:
                    await asyncio.sleep(poll_interval)
            else:
                # Timeout reached
                raise Exception(
                    f"VMs did not become ACTIVE within {max_poll_attempts * poll_interval} seconds"
                )

            # Step 5: Update deployment with success
            resources = {
                "network_id": network_id,
                "subnet_id": subnet_id,
                "server_ids": server_ids,
            }

            await update_deployment_status_activity(
                deployment_id=deployment_id,
                status=DeploymentStatus.COMPLETED,
                resources=resources,
            )

            logger.info("deployment_workflow_completed", deployment_id=str(deployment_id))

            return DeploymentWorkflowResult(
                deployment_id=deployment_id,
                success=True,
                network_id=network_id,
                subnet_id=subnet_id,
                server_ids=server_ids,
            )

        except Exception as e:
            logger.error(
                "deployment_workflow_failed",
                deployment_id=str(deployment_id),
                error=str(e),
            )

            # Rollback: Delete created resources
            try:
                await rollback_resources_activity(
                    deployment_id=deployment_id,
                    network_id=network_id,
                    server_ids=server_ids,
                    openstack_config=self.openstack_config,
                )
            except Exception as rollback_error:
                logger.error(
                    "rollback_failed",
                    deployment_id=str(deployment_id),
                    error=str(rollback_error),
                )

            # Update deployment status to FAILED
            error_info = {"message": str(e), "type": type(e).__name__}

            await update_deployment_status_activity(
                deployment_id=deployment_id,
                status=DeploymentStatus.FAILED,
                error=error_info,
            )

            return DeploymentWorkflowResult(
                deployment_id=deployment_id,
                success=False,
                network_id=network_id,
                subnet_id=subnet_id,
                server_ids=server_ids,
                error=str(e),
            )


async def run_deployment_workflow(
    deployment_id: UUID, cloud_region: str, template: dict, parameters: dict | None = None
) -> DeploymentWorkflowResult:
    """
    Convenience function to run deployment workflow.

    Args:
        deployment_id: Deployment ID
        cloud_region: Cloud region
        template: Deployment template
        parameters: Deployment parameters

    Returns:
        DeploymentWorkflowResult
    """
    workflow_input = DeploymentWorkflowInput(
        deployment_id=deployment_id,
        cloud_region=cloud_region,
        template=template,
        parameters=parameters or {},
    )

    workflow = DeploymentWorkflow()
    return await workflow.execute(workflow_input)
