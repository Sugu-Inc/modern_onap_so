"""
OpenStack API schemas.

Pydantic models for OpenStack API requests and responses.
"""

from typing import Any

from pydantic import BaseModel, Field


class ServerConfig(BaseModel):
    """Configuration for creating an OpenStack server (VM)."""

    name: str = Field(..., description="Server name")
    flavor: str = Field(..., description="Flavor ID or name (e.g., 'm1.small')")
    image: str = Field(..., description="Image ID or name (e.g., 'ubuntu-22.04')")
    networks: list[str] = Field(default_factory=list, description="List of network IDs to attach")
    key_name: str | None = Field(None, description="SSH keypair name")
    security_groups: list[str] = Field(default_factory=list, description="Security group names")
    user_data: str | None = Field(None, description="Cloud-init user data script")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Server metadata")


class ServerStatus(BaseModel):
    """Status information for an OpenStack server."""

    server_id: str = Field(..., description="Server ID")
    status: str = Field(..., description="Server status (e.g., ACTIVE, BUILD, ERROR)")
    power_state: int | None = Field(None, description="Power state code")
    task_state: str | None = Field(None, description="Current task state")
    addresses: dict[str, Any] = Field(default_factory=dict, description="Network addresses")
    created_at: str | None = Field(None, description="Creation timestamp")


class NetworkConfig(BaseModel):
    """Configuration for creating an OpenStack network."""

    name: str = Field(..., description="Network name")
    admin_state_up: bool = Field(True, description="Administrative state")
    shared: bool = Field(False, description="Whether network is shared")
    external: bool = Field(False, description="Whether network is external")
    provider_network_type: str | None = Field(
        None, description="Provider network type (flat, vlan, vxlan, etc.)"
    )
    provider_physical_network: str | None = Field(
        None, description="Physical network for provider networks"
    )
    provider_segmentation_id: int | None = Field(
        None, description="Segmentation ID for provider networks"
    )


class SubnetConfig(BaseModel):
    """Configuration for creating an OpenStack subnet."""

    name: str = Field(..., description="Subnet name")
    network_id: str = Field(..., description="Parent network ID")
    cidr: str = Field(..., description="CIDR block (e.g., '192.168.1.0/24')")
    ip_version: int = Field(4, description="IP version (4 or 6)")
    enable_dhcp: bool = Field(True, description="Enable DHCP")
    gateway_ip: str | None = Field(None, description="Gateway IP address")
    dns_nameservers: list[str] = Field(default_factory=list, description="DNS nameserver IPs")
    allocation_pools: list[dict[str, str]] = Field(
        default_factory=list,
        description="IP allocation pools [{'start': '...', 'end': '...'}]",
    )
    host_routes: list[dict[str, str]] = Field(default_factory=list, description="Host routes")


class TokenResponse(BaseModel):
    """Keystone authentication token response."""

    token: str = Field(..., description="Authentication token")
    expires_at: str = Field(..., description="Token expiration timestamp")
    project_id: str | None = Field(None, description="Project (tenant) ID")
    user_id: str | None = Field(None, description="User ID")
    catalog: list[dict[str, Any]] = Field(default_factory=list, description="Service catalog")
