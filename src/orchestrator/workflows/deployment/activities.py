"""
Deployment workflow activities.

These are the individual units of work orchestrated by the deployment workflow.
Each activity is idempotent and can be retried safely.
"""

from uuid import UUID

from orchestrator.clients.openstack.client import OpenStackClient
from orchestrator.clients.openstack.schemas import (
    NetworkConfig,
    ServerConfig,
    SubnetConfig,
)
from orchestrator.db.connection import db_connection
from orchestrator.db.repositories.deployment_repository import DeploymentRepository
from orchestrator.logging import logger
from orchestrator.models.deployment import DeploymentStatus
from orchestrator.workflows.deployment.models import (
    NetworkCreationResult,
    VMCreationResult,
    VMStatusResult,
)


async def create_network_activity(
    deployment_id: UUID,
    network_name: str,
    subnet_cidr: str,
    cloud_region: str,
    openstack_config: dict,
) -> NetworkCreationResult:
    """
    Create OpenStack network and subnet.

    Args:
        deployment_id: Deployment ID for logging
        network_name: Name for the network
        subnet_cidr: CIDR block for subnet (e.g., "192.168.1.0/24")
        cloud_region: Cloud region
        openstack_config: OpenStack client configuration

    Returns:
        NetworkCreationResult with network and subnet IDs

    Raises:
        Exception: If network creation fails
    """
    logger.info(
        "activity_create_network_started",
        deployment_id=str(deployment_id),
        network_name=network_name,
    )

    async with OpenStackClient(**openstack_config) as client:
        # Create network
        network_config = NetworkConfig(name=network_name, admin_state_up=True)
        network_result = await client.create_network(network_config)
        network_id = network_result["id"]

        logger.info(
            "network_created",
            deployment_id=str(deployment_id),
            network_id=network_id,
        )

        # Create subnet
        subnet_config = SubnetConfig(
            name=f"{network_name}-subnet",
            network_id=network_id,
            cidr=subnet_cidr,
            ip_version=4,
            enable_dhcp=True,
        )
        subnet_result = await client.create_subnet(subnet_config)
        subnet_id = subnet_result["id"]

        logger.info(
            "subnet_created",
            deployment_id=str(deployment_id),
            subnet_id=subnet_id,
        )

        return NetworkCreationResult(
            network_id=network_id,
            subnet_id=subnet_id,
            network_name=network_name,
            subnet_cidr=subnet_cidr,
        )


async def create_vm_activity(
    deployment_id: UUID,
    vm_name: str,
    flavor: str,
    image: str,
    network_id: str,
    openstack_config: dict,
) -> VMCreationResult:
    """
    Create OpenStack VM.

    Args:
        deployment_id: Deployment ID for logging
        vm_name: Name for the VM
        flavor: Flavor ID or name
        image: Image ID or name
        network_id: Network ID to attach
        openstack_config: OpenStack client configuration

    Returns:
        VMCreationResult with server ID and status

    Raises:
        Exception: If VM creation fails
    """
    logger.info(
        "activity_create_vm_started",
        deployment_id=str(deployment_id),
        vm_name=vm_name,
    )

    async with OpenStackClient(**openstack_config) as client:
        server_config = ServerConfig(
            name=vm_name, flavor=flavor, image=image, networks=[network_id]
        )

        server_result = await client.create_server(server_config)
        server_id = server_result["id"]

        logger.info(
            "vm_created", deployment_id=str(deployment_id), server_id=server_id
        )

        return VMCreationResult(
            server_id=server_id, server_name=vm_name, status=server_result["status"]
        )


async def poll_vm_status_activity(
    deployment_id: UUID, server_id: str, openstack_config: dict
) -> VMStatusResult:
    """
    Poll VM status from OpenStack.

    Args:
        deployment_id: Deployment ID for logging
        server_id: Server ID to check
        openstack_config: OpenStack client configuration

    Returns:
        VMStatusResult with current status

    Raises:
        Exception: If status check fails
    """
    logger.info(
        "activity_poll_vm_status",
        deployment_id=str(deployment_id),
        server_id=server_id,
    )

    async with OpenStackClient(**openstack_config) as client:
        status_result = await client.get_server_status(server_id)

        # Check if VM is in a terminal state
        is_ready = status_result.status == "ACTIVE"
        is_error = status_result.status == "ERROR"

        # Extract IP address if available
        ip_address = None
        if status_result.addresses:
            # Try to get the first IP from any network
            for network_name, addresses in status_result.addresses.items():
                if addresses and len(addresses) > 0:
                    ip_address = addresses[0].get("addr")
                    break

        logger.info(
            "vm_status_polled",
            deployment_id=str(deployment_id),
            server_id=server_id,
            status=status_result.status,
            is_ready=is_ready,
        )

        if is_error:
            raise Exception(f"VM {server_id} entered ERROR state")

        return VMStatusResult(
            server_id=server_id,
            status=status_result.status,
            is_ready=is_ready,
            ip_address=ip_address,
        )


async def update_deployment_status_activity(
    deployment_id: UUID, status: DeploymentStatus, resources: dict | None = None, error: dict | None = None
) -> None:
    """
    Update deployment status in database.

    Args:
        deployment_id: Deployment ID to update
        status: New deployment status
        resources: Resource IDs to store (optional)
        error: Error information (optional)

    Raises:
        Exception: If database update fails
    """
    logger.info(
        "activity_update_deployment_status",
        deployment_id=str(deployment_id),
        status=status.value,
    )

    async with db_connection.session() as session:
        repo = DeploymentRepository(session)

        update_kwargs = {"status": status}
        if resources is not None:
            update_kwargs["resources"] = resources
        if error is not None:
            update_kwargs["error"] = error

        updated = await repo.update(deployment_id, **update_kwargs)

        if not updated:
            raise Exception(f"Deployment {deployment_id} not found")

        await session.commit()

        logger.info(
            "deployment_status_updated",
            deployment_id=str(deployment_id),
            status=status.value,
        )


async def rollback_resources_activity(
    deployment_id: UUID,
    network_id: str | None,
    server_ids: list[str],
    openstack_config: dict,
) -> None:
    """
    Rollback/delete created OpenStack resources.

    Args:
        deployment_id: Deployment ID for logging
        network_id: Network ID to delete (if any)
        server_ids: Server IDs to delete
        openstack_config: OpenStack client configuration

    Note:
        This activity attempts to delete all resources and logs errors
        but doesn't fail if deletion fails (best effort cleanup).
    """
    logger.info(
        "activity_rollback_started",
        deployment_id=str(deployment_id),
        server_count=len(server_ids),
        has_network=network_id is not None,
    )

    async with OpenStackClient(**openstack_config) as client:
        # Delete servers first
        for server_id in server_ids:
            try:
                await client.delete_server(server_id)
                logger.info(
                    "server_deleted_in_rollback",
                    deployment_id=str(deployment_id),
                    server_id=server_id,
                )
            except Exception as e:
                logger.error(
                    "server_deletion_failed_in_rollback",
                    deployment_id=str(deployment_id),
                    server_id=server_id,
                    error=str(e),
                )

        # Delete network (subnet will be deleted automatically)
        if network_id:
            try:
                await client.delete_network(network_id)
                logger.info(
                    "network_deleted_in_rollback",
                    deployment_id=str(deployment_id),
                    network_id=network_id,
                )
            except Exception as e:
                logger.error(
                    "network_deletion_failed_in_rollback",
                    deployment_id=str(deployment_id),
                    network_id=network_id,
                    error=str(e),
                )

    logger.info("activity_rollback_completed", deployment_id=str(deployment_id))
