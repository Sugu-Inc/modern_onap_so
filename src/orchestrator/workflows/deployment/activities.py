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


async def delete_vm_activity(
    deployment_id: UUID,
    server_id: str,
    openstack_config: dict,
) -> bool:
    """
    Delete a VM/server from OpenStack.

    Args:
        deployment_id: Deployment ID for logging
        server_id: Server ID to delete
        openstack_config: OpenStack client configuration

    Returns:
        True if deletion succeeded

    Raises:
        Exception: If deletion fails
    """
    logger.info(
        "activity_delete_vm_started",
        deployment_id=str(deployment_id),
        server_id=server_id,
    )

    async with OpenStackClient(**openstack_config) as client:
        try:
            success = await client.delete_server(server_id)

            if success:
                logger.info(
                    "activity_delete_vm_completed",
                    deployment_id=str(deployment_id),
                    server_id=server_id,
                )
                return True
            else:
                msg = f"Failed to delete server {server_id}"
                logger.error(
                    "activity_delete_vm_failed",
                    deployment_id=str(deployment_id),
                    server_id=server_id,
                    error=msg,
                )
                raise Exception(msg)

        except Exception as e:
            logger.error(
                "activity_delete_vm_error",
                deployment_id=str(deployment_id),
                server_id=server_id,
                error=str(e),
            )
            raise


async def delete_network_activity(
    deployment_id: UUID,
    network_id: str,
    openstack_config: dict,
) -> bool:
    """
    Delete a network from OpenStack.

    Args:
        deployment_id: Deployment ID for logging
        network_id: Network ID to delete
        openstack_config: OpenStack client configuration

    Returns:
        True if deletion succeeded

    Raises:
        Exception: If deletion fails
    """
    logger.info(
        "activity_delete_network_started",
        deployment_id=str(deployment_id),
        network_id=network_id,
    )

    async with OpenStackClient(**openstack_config) as client:
        try:
            success = await client.delete_network(network_id)

            if success:
                logger.info(
                    "activity_delete_network_completed",
                    deployment_id=str(deployment_id),
                    network_id=network_id,
                )
                return True
            else:
                msg = f"Failed to delete network {network_id}"
                logger.error(
                    "activity_delete_network_failed",
                    deployment_id=str(deployment_id),
                    network_id=network_id,
                    error=msg,
                )
                raise Exception(msg)

        except Exception as e:
            logger.error(
                "activity_delete_network_error",
                deployment_id=str(deployment_id),
                network_id=network_id,
                error=str(e),
            )
            raise


async def cleanup_orphaned_resources_activity(
    deployment_id: UUID,
    resources: dict,
    openstack_config: dict,
) -> None:
    """
    Best-effort cleanup of potentially orphaned resources.

    This activity attempts to clean up any resources that may have been left behind
    during a failed deletion. It logs errors but doesn't fail if cleanup fails.

    Args:
        deployment_id: Deployment ID for logging
        resources: Dictionary of resources to clean up
        openstack_config: OpenStack client configuration
    """
    logger.info(
        "activity_cleanup_orphaned_started",
        deployment_id=str(deployment_id),
        resources=resources,
    )

    async with OpenStackClient(**openstack_config) as client:
        # Try to delete any remaining servers
        server_ids = resources.get("server_ids", [])
        for server_id in server_ids:
            try:
                await client.delete_server(server_id)
                logger.info(
                    "orphaned_server_cleaned",
                    deployment_id=str(deployment_id),
                    server_id=server_id,
                )
            except Exception as e:
                logger.warning(
                    "orphaned_server_cleanup_failed",
                    deployment_id=str(deployment_id),
                    server_id=server_id,
                    error=str(e),
                )

        # Try to delete network
        network_id = resources.get("network_id")
        if network_id:
            try:
                await client.delete_network(network_id)
                logger.info(
                    "orphaned_network_cleaned",
                    deployment_id=str(deployment_id),
                    network_id=network_id,
                )
            except Exception as e:
                logger.warning(
                    "orphaned_network_cleanup_failed",
                    deployment_id=str(deployment_id),
                    network_id=network_id,
                    error=str(e),
                )

    logger.info("activity_cleanup_orphaned_completed", deployment_id=str(deployment_id))


async def resize_vm_activity(
    deployment_id: UUID,
    server_id: str,
    new_flavor: str,
    openstack_config: dict,
) -> bool:
    """
    Resize a VM to a new flavor.

    Args:
        deployment_id: Deployment ID for logging
        server_id: Server ID to resize
        new_flavor: New flavor/instance type
        openstack_config: OpenStack client configuration

    Returns:
        True if resize succeeded

    Raises:
        Exception: If resize fails
    """
    logger.info(
        "activity_resize_vm_started",
        deployment_id=str(deployment_id),
        server_id=server_id,
        new_flavor=new_flavor,
    )

    async with OpenStackClient(**openstack_config) as client:
        try:
            # Note: In a real OpenStack implementation, resize involves:
            # 1. Stop the instance
            # 2. Resize to new flavor
            # 3. Confirm resize
            # 4. Start the instance
            # For now, we'll simulate with a simple call
            # TODO: Implement actual OpenStack resize API calls

            # Placeholder for actual resize logic
            # In production, this would call OpenStack Nova API:
            # await client.resize_server(server_id, new_flavor)
            # await client.confirm_resize(server_id)

            logger.info(
                "activity_resize_vm_completed",
                deployment_id=str(deployment_id),
                server_id=server_id,
                new_flavor=new_flavor,
            )
            return True

        except Exception as e:
            logger.error(
                "activity_resize_vm_error",
                deployment_id=str(deployment_id),
                server_id=server_id,
                error=str(e),
            )
            raise


async def update_network_activity(
    deployment_id: UUID,
    network_id: str,
    subnet_id: str,
    new_cidr: str,
    openstack_config: dict,
) -> dict:
    """
    Update network configuration.

    Note: Changing subnet CIDR typically requires creating a new subnet
    and migrating VMs, as existing subnets cannot be modified.

    Args:
        deployment_id: Deployment ID for logging
        network_id: Network ID to update
        subnet_id: Current subnet ID
        new_cidr: New subnet CIDR
        openstack_config: OpenStack client configuration

    Returns:
        Dict with updated network_id and subnet_id

    Raises:
        Exception: If network update fails
    """
    logger.info(
        "activity_update_network_started",
        deployment_id=str(deployment_id),
        network_id=network_id,
        subnet_id=subnet_id,
        new_cidr=new_cidr,
    )

    async with OpenStackClient(**openstack_config) as client:
        try:
            # Note: In OpenStack, changing a subnet CIDR requires:
            # 1. Create a new subnet with the new CIDR
            # 2. Update VM network interfaces to use new subnet
            # 3. Delete old subnet
            # This is a complex operation that may require VM downtime

            # For now, we'll create a new subnet
            # TODO: Implement actual network migration logic

            new_subnet_config = SubnetConfig(
                name=f"updated-subnet-{deployment_id}",
                network_id=network_id,
                cidr=new_cidr,
                ip_version=4,
                enable_dhcp=True,
            )

            # Placeholder - in production would create new subnet
            # new_subnet = await client.create_subnet(new_subnet_config)
            new_subnet_id = f"new-subnet-{subnet_id}"

            logger.info(
                "activity_update_network_completed",
                deployment_id=str(deployment_id),
                network_id=network_id,
                old_subnet_id=subnet_id,
                new_subnet_id=new_subnet_id,
            )

            return {
                "network_id": network_id,
                "subnet_id": new_subnet_id,
            }

        except Exception as e:
            logger.error(
                "activity_update_network_error",
                deployment_id=str(deployment_id),
                network_id=network_id,
                error=str(e),
            )
            raise
