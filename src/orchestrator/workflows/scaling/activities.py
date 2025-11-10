"""
Scaling workflow activities.

These activities are designed to be idempotent and retriable.
"""

from typing import Any

from orchestrator.clients.openstack.client import OpenStackClient


async def scale_out_activity(
    count_to_add: int,
    template: dict[str, Any],
    network_id: str,
    cloud_region: str,
    openstack_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Scale out by creating additional VMs.

    Args:
        count_to_add: Number of VMs to create
        template: VM template configuration
        network_id: Network ID to attach VMs to
        cloud_region: Cloud region for deployment
        openstack_config: OpenStack connection configuration

    Returns:
        Dictionary with:
        - new_server_ids: List of created server IDs
        - success: Boolean indicating success
        - error: Error message if failed

    Raises:
        Exception: If VM creation fails critically
    """
    # TODO: Implement actual OpenStack VM creation
    # For now, return placeholder server IDs
    # This will be implemented when OpenStack client has batch create methods

    new_server_ids = []
    try:
        for i in range(count_to_add):
            # Placeholder: generate server ID
            server_id = f"server-{hash(f'{cloud_region}-{i}') % 10000}"
            new_server_ids.append(server_id)

        return {
            "new_server_ids": new_server_ids,
            "success": True,
            "error": None,
        }
    except Exception as e:
        return {
            "new_server_ids": [],
            "success": False,
            "error": str(e),
        }


async def scale_in_activity(
    server_ids: list[str],
    count_to_remove: int,
    min_count: int,
    cloud_region: str,
    openstack_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Scale in by removing VMs.

    Args:
        server_ids: List of current server IDs
        count_to_remove: Number of VMs to remove
        min_count: Minimum number of VMs to maintain
        cloud_region: Cloud region for deployment
        openstack_config: OpenStack connection configuration

    Returns:
        Dictionary with:
        - removed_server_ids: List of removed server IDs
        - success: Boolean indicating success
        - error: Error message if failed

    Raises:
        Exception: If VM deletion fails critically
    """
    # Validate we won't go below min_count
    remaining_count = len(server_ids) - count_to_remove
    if remaining_count < min_count:
        return {
            "removed_server_ids": [],
            "success": False,
            "error": f"Cannot remove {count_to_remove} VMs - would leave {remaining_count} (min: {min_count})",
        }

    # TODO: Implement actual OpenStack VM deletion
    # For now, just select the last N servers to remove
    # In production, this should intelligently select which VMs to remove (e.g., newest first)

    try:
        # Select servers to remove (take last N)
        servers_to_remove = server_ids[-count_to_remove:]

        # TODO: Call OpenStack client to delete servers
        # client = OpenStackClient(config=openstack_config)
        # for server_id in servers_to_remove:
        #     await client.delete_server(server_id, cloud_region)

        return {
            "removed_server_ids": servers_to_remove,
            "success": True,
            "error": None,
        }
    except Exception as e:
        return {
            "removed_server_ids": [],
            "success": False,
            "error": str(e),
        }
