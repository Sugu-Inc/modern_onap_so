"""
Configuration workflow activities.

These activities are designed to be idempotent and retriable.
"""

from pathlib import Path
from typing import Any

from orchestrator.clients.ansible.client import AnsibleClient, PlaybookResult


async def get_vm_addresses_activity(
    server_ids: list[str],
    openstack_config: dict[str, Any],
) -> dict[str, str]:
    """
    Get IP addresses for VMs.

    Args:
        server_ids: List of server IDs
        openstack_config: OpenStack connection configuration

    Returns:
        Dictionary mapping server_id to IP address

    Raises:
        Exception: If unable to get VM addresses
    """
    # TODO: Implement actual OpenStack API call to get server details
    # For now, return placeholder IPs based on server IDs
    # This will be implemented when OpenStack client has get_server_details method

    addresses = {}
    for i, server_id in enumerate(server_ids):
        # Placeholder: generate IP based on index
        addresses[server_id] = f"10.0.0.{5 + i}"

    return addresses


async def run_ansible_activity(
    playbook_path: str,
    inventory: str,
    extra_vars: dict[str, Any],
    limit: str | None = None,
    ssh_private_key_path: Path | None = None,
    timeout: int = 300,
) -> dict[str, Any]:
    """
    Run Ansible playbook on target hosts.

    Args:
        playbook_path: Path to Ansible playbook
        inventory: Ansible inventory (comma-separated IPs or inventory file)
        extra_vars: Extra variables to pass to playbook
        limit: Limit execution to specific hosts
        ssh_private_key_path: Path to SSH private key
        timeout: Timeout in seconds

    Returns:
        Dictionary with execution details:
        - execution_id: UUID of execution
        - status: PlaybookStatus
        - return_code: Ansible return code
        - stats: Ansible execution statistics
        - error: Error message if failed

    Raises:
        Exception: If Ansible execution fails critically
    """
    # Create Ansible client
    client = AnsibleClient(timeout=timeout)

    # Run playbook
    result: PlaybookResult = await client.run_playbook(
        playbook_path=Path(playbook_path),
        inventory=inventory,
        extra_vars=extra_vars,
        limit=limit,
        ssh_private_key_path=ssh_private_key_path,
    )

    # Convert to dictionary for workflow result
    return {
        "execution_id": result.execution_id,
        "status": result.status,
        "return_code": result.return_code,
        "stats": result.stats,
        "error": result.error,
    }
