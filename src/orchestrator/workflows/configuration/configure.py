"""
Configuration workflow.

Orchestrates Ansible playbook execution on deployed VMs.
"""

from uuid import UUID

from orchestrator.clients.ansible.client import PlaybookStatus
from orchestrator.models.deployment import DeploymentStatus
from orchestrator.workflows.configuration.activities import (
    get_vm_addresses_activity,
    run_ansible_activity,
)
from orchestrator.workflows.configuration.models import (
    ConfigureWorkflowInput,
    ConfigureWorkflowResult,
)
from orchestrator.workflows.deployment.activities import update_deployment_status_activity


class ConfigureWorkflow:
    """
    Workflow for configuring deployed infrastructure using Ansible.

    Flow:
    1. Get VM IP addresses from resources
    2. Create Ansible inventory from IPs
    3. Run Ansible playbook
    4. Update deployment status based on result
    """

    def __init__(self, openstack_config: dict | None = None):
        """
        Initialize workflow.

        Args:
            openstack_config: OpenStack connection configuration
        """
        self.openstack_config = openstack_config or {}

    async def execute(self, workflow_input: ConfigureWorkflowInput) -> ConfigureWorkflowResult:
        """
        Execute configuration workflow.

        Args:
            workflow_input: Workflow input parameters

        Returns:
            Workflow execution result
        """
        try:
            # Step 1: Validate VMs exist
            server_ids = workflow_input.resources.get("server_ids", [])
            if not server_ids:
                return ConfigureWorkflowResult(
                    success=False,
                    deployment_id=workflow_input.deployment_id,
                    execution_id=None,
                    configured_hosts=[],
                    error="No VMs found in deployment resources",
                )

            # Step 2: Get VM IP addresses
            vm_addresses = await get_vm_addresses_activity(
                server_ids=server_ids,
                openstack_config=self.openstack_config,
            )

            # Step 3: Create Ansible inventory (comma-separated IPs)
            inventory = ",".join(vm_addresses.values()) + ","

            # Step 4: Run Ansible playbook
            ansible_result = await run_ansible_activity(
                playbook_path=workflow_input.playbook_path,
                inventory=inventory,
                extra_vars=workflow_input.extra_vars,
                limit=workflow_input.limit,
                ssh_private_key_path=None,  # TODO: Get from config or parameters
                timeout=300,
            )

            # Step 5: Determine success based on Ansible status
            success = ansible_result["status"] == PlaybookStatus.SUCCESSFUL

            if success:
                # Update deployment status to COMPLETED with configuration metadata
                await update_deployment_status_activity(
                    deployment_id=workflow_input.deployment_id,
                    status=DeploymentStatus.COMPLETED,
                    extra_metadata={
                        "last_configured_at": str(ansible_result["execution_id"]),
                        "configured_hosts": list(vm_addresses.values()),
                    },
                )

                return ConfigureWorkflowResult(
                    success=True,
                    deployment_id=workflow_input.deployment_id,
                    execution_id=ansible_result["execution_id"],
                    configured_hosts=list(vm_addresses.values()),
                    error=None,
                )
            else:
                # Update deployment status with error
                error_message = (
                    ansible_result["error"]
                    or f"Ansible playbook failed with status: {ansible_result['status']}"
                )

                await update_deployment_status_activity(
                    deployment_id=workflow_input.deployment_id,
                    status=DeploymentStatus.FAILED,
                    error={
                        "message": error_message,
                        "ansible_execution_id": str(ansible_result["execution_id"]),
                        "return_code": ansible_result["return_code"],
                    },
                )

                return ConfigureWorkflowResult(
                    success=False,
                    deployment_id=workflow_input.deployment_id,
                    execution_id=ansible_result["execution_id"],
                    configured_hosts=[],
                    error=error_message,
                )

        except Exception as e:
            # Handle any unexpected errors
            error_message = f"Configuration workflow failed: {e!s}"

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

            return ConfigureWorkflowResult(
                success=False,
                deployment_id=workflow_input.deployment_id,
                execution_id=None,
                configured_hosts=[],
                error=error_message,
            )


async def run_configure_workflow(
    deployment_id: UUID,
    playbook_path: str,
    extra_vars: dict,
    limit: str | None,
    resources: dict,
    openstack_config: dict | None = None,
) -> ConfigureWorkflowResult:
    """
    Convenience function to run configuration workflow.

    Args:
        deployment_id: Deployment to configure
        playbook_path: Path to Ansible playbook
        extra_vars: Extra variables for playbook
        limit: Limit to specific hosts
        resources: Deployment resources
        openstack_config: OpenStack configuration

    Returns:
        Workflow execution result
    """
    workflow_input = ConfigureWorkflowInput(
        deployment_id=deployment_id,
        playbook_path=playbook_path,
        extra_vars=extra_vars,
        limit=limit,
        resources=resources,
    )

    workflow = ConfigureWorkflow(openstack_config=openstack_config)
    return await workflow.execute(workflow_input)
