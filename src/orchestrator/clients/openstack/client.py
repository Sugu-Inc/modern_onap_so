"""
OpenStack client for infrastructure management.

Provides async methods for interacting with OpenStack services:
- Keystone (authentication)
- Nova (compute/servers)
- Neutron (networking)
"""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from orchestrator.clients.openstack.schemas import (
    NetworkConfig,
    ServerConfig,
    ServerStatus,
    SubnetConfig,
    TokenResponse,
)
from orchestrator.logging import logger


class OpenStackClient:
    """
    Async OpenStack client for managing infrastructure.

    Handles authentication and provides methods for server and network operations.
    """

    def __init__(
        self,
        auth_url: str,
        username: str,
        password: str,
        project_name: str,
        project_domain_name: str = "Default",
        user_domain_name: str = "Default",
        region_name: str = "RegionOne",
        timeout: int = 30,
    ) -> None:
        """
        Initialize OpenStack client.

        Args:
            auth_url: Keystone authentication URL
            username: OpenStack username
            password: OpenStack password
            project_name: Project (tenant) name
            project_domain_name: Project domain name
            user_domain_name: User domain name
            region_name: OpenStack region
            timeout: HTTP request timeout in seconds
        """
        self.auth_url = auth_url
        self.username = username
        self._password = password  # Private to indicate sensitive data
        self.password = password  # For backwards compatibility with tests
        self.project_name = project_name
        self.project_domain_name = project_domain_name
        self.user_domain_name = user_domain_name
        self.region_name = region_name
        self.timeout = timeout

        # Token caching
        self._token: str | None = None
        self._token_expires_at: datetime | None = None
        self._service_catalog: dict[str, str] = {}

        # HTTP client
        self._http_client = httpx.AsyncClient(timeout=timeout)

    async def __aenter__(self) -> "OpenStackClient":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self._http_client.aclose()

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._http_client.aclose()

    # Authentication (Keystone)

    async def authenticate(self) -> dict[str, Any]:
        """
        Authenticate with Keystone and get token.

        Returns:
            Token data with token string and expiration

        Raises:
            Exception: If authentication fails
        """
        # Check if cached token is still valid
        if self._token and self._token_expires_at:
            if datetime.now(timezone.utc) < self._token_expires_at - timedelta(
                minutes=5
            ):
                return {
                    "token": self._token,
                    "expires_at": self._token_expires_at.isoformat(),
                }

        # Request new token
        token_data = await self._request_token()

        # Cache token
        self._token = token_data["token"]
        self._token_expires_at = datetime.fromisoformat(
            token_data["expires_at"].replace("Z", "+00:00")
        )

        return token_data

    async def _request_token(self) -> dict[str, Any]:
        """
        Request authentication token from Keystone.

        Returns:
            Token data

        Raises:
            Exception: If request fails
        """
        auth_payload = {
            "auth": {
                "identity": {
                    "methods": ["password"],
                    "password": {
                        "user": {
                            "name": self.username,
                            "domain": {"name": self.user_domain_name},
                            "password": self._password,
                        }
                    },
                },
                "scope": {
                    "project": {
                        "name": self.project_name,
                        "domain": {"name": self.project_domain_name},
                    }
                },
            }
        }

        try:
            response = await self._http_client.post(
                f"{self.auth_url}/auth/tokens", json=auth_payload
            )
            response.raise_for_status()

            token = response.headers.get("X-Subject-Token")
            if not token:
                raise Exception("No token in response headers")

            data = response.json()
            token_info = data["token"]

            # Extract service catalog for endpoint discovery
            if "catalog" in token_info:
                for service in token_info["catalog"]:
                    service_type = service["type"]
                    for endpoint in service["endpoints"]:
                        if (
                            endpoint["interface"] == "public"
                            and endpoint.get("region") == self.region_name
                        ):
                            self._service_catalog[service_type] = endpoint["url"]

            return {
                "token": token,
                "expires_at": token_info["expires_at"],
                "project_id": token_info.get("project", {}).get("id"),
                "user_id": token_info.get("user", {}).get("id"),
                "catalog": token_info.get("catalog", []),
            }

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise Exception("401 Unauthorized")
            raise Exception(f"Authentication failed: {e}")
        except Exception as e:
            raise Exception(f"Authentication request failed: {e}")

    async def _get_auth_headers(self) -> dict[str, str]:
        """Get authentication headers with valid token."""
        token_data = await self.authenticate()
        return {"X-Auth-Token": token_data["token"]}

    # Nova (Compute) Operations

    async def create_server(self, config: ServerConfig) -> dict[str, Any]:
        """
        Create a server (VM) using Nova.

        Args:
            config: Server configuration

        Returns:
            Server creation response

        Raises:
            Exception: If server creation fails
        """
        payload = {
            "server": {
                "name": config.name,
                "flavorRef": config.flavor,
                "imageRef": config.image,
                "networks": [{"uuid": net_id} for net_id in config.networks],
            }
        }

        if config.key_name:
            payload["server"]["key_name"] = config.key_name

        if config.security_groups:
            payload["server"]["security_groups"] = [
                {"name": sg} for sg in config.security_groups
            ]

        if config.user_data:
            payload["server"]["user_data"] = config.user_data

        if config.metadata:
            payload["server"]["metadata"] = config.metadata

        response = await self._nova_request("POST", "/servers", json=payload)
        return response["server"]

    async def delete_server(self, server_id: str) -> bool:
        """
        Delete a server using Nova.

        Args:
            server_id: Server ID to delete

        Returns:
            True if deletion initiated successfully

        Raises:
            Exception: If deletion fails
        """
        try:
            await self._nova_request("DELETE", f"/servers/{server_id}")
            return True
        except Exception as e:
            logger.error("server_deletion_failed", server_id=server_id, error=str(e))
            raise

    async def get_server_status(self, server_id: str) -> ServerStatus:
        """
        Get server status from Nova.

        Args:
            server_id: Server ID

        Returns:
            Server status information

        Raises:
            Exception: If server not found or request fails
        """
        response = await self._nova_request("GET", f"/servers/{server_id}")
        server_data = response["server"]

        return ServerStatus(
            server_id=server_data["id"],
            status=server_data["status"],
            power_state=server_data.get("OS-EXT-STS:power_state"),
            task_state=server_data.get("OS-EXT-STS:task_state"),
            addresses=server_data.get("addresses", {}),
            created_at=server_data.get("created"),
        )

    async def _nova_request(
        self, method: str, path: str, **kwargs: Any
    ) -> dict[str, Any]:
        """
        Make a request to Nova API.

        Args:
            method: HTTP method
            path: API path
            **kwargs: Additional request parameters

        Returns:
            Response data

        Raises:
            Exception: If request fails
        """
        # Get compute endpoint from service catalog or use default
        compute_endpoint = self._service_catalog.get(
            "compute", f"{self.auth_url.replace(':5000', ':8774')}/v2.1"
        )

        headers = await self._get_auth_headers()
        url = f"{compute_endpoint}{path}"

        try:
            response = await self._http_client.request(
                method, url, headers=headers, **kwargs
            )
            response.raise_for_status()

            # DELETE requests often return empty body
            if method == "DELETE":
                return {"status": "deleted"}

            return response.json()

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise Exception("404 Not Found")
            elif e.response.status_code == 403:
                if "quota" in e.response.text.lower():
                    raise Exception("Quota exceeded")
            raise Exception(f"Nova request failed: {e}")
        except httpx.TimeoutException as e:
            raise TimeoutError("Request timeout")
        except Exception as e:
            raise Exception(f"Nova request failed: {e}")

    # Neutron (Network) Operations

    async def create_network(self, config: NetworkConfig) -> dict[str, Any]:
        """
        Create a network using Neutron.

        Args:
            config: Network configuration

        Returns:
            Network creation response

        Raises:
            Exception: If network creation fails
        """
        payload = {
            "network": {
                "name": config.name,
                "admin_state_up": config.admin_state_up,
                "shared": config.shared,
                "router:external": config.external,
            }
        }

        if config.provider_network_type:
            payload["network"]["provider:network_type"] = config.provider_network_type

        if config.provider_physical_network:
            payload["network"][
                "provider:physical_network"
            ] = config.provider_physical_network

        if config.provider_segmentation_id is not None:
            payload["network"][
                "provider:segmentation_id"
            ] = config.provider_segmentation_id

        response = await self._neutron_request("POST", "/v2.0/networks", json=payload)
        return response["network"]

    async def create_subnet(self, config: SubnetConfig) -> dict[str, Any]:
        """
        Create a subnet using Neutron.

        Args:
            config: Subnet configuration

        Returns:
            Subnet creation response

        Raises:
            Exception: If subnet creation fails
        """
        payload = {
            "subnet": {
                "name": config.name,
                "network_id": config.network_id,
                "cidr": config.cidr,
                "ip_version": config.ip_version,
                "enable_dhcp": config.enable_dhcp,
            }
        }

        if config.gateway_ip:
            payload["subnet"]["gateway_ip"] = config.gateway_ip

        if config.dns_nameservers:
            payload["subnet"]["dns_nameservers"] = config.dns_nameservers

        if config.allocation_pools:
            payload["subnet"]["allocation_pools"] = config.allocation_pools

        if config.host_routes:
            payload["subnet"]["host_routes"] = config.host_routes

        response = await self._neutron_request("POST", "/v2.0/subnets", json=payload)
        return response["subnet"]

    async def delete_network(self, network_id: str) -> bool:
        """
        Delete a network using Neutron.

        Args:
            network_id: Network ID to delete

        Returns:
            True if deletion initiated successfully

        Raises:
            Exception: If deletion fails
        """
        try:
            await self._neutron_request("DELETE", f"/v2.0/networks/{network_id}")
            return True
        except Exception as e:
            if "in use" in str(e).lower():
                raise Exception("Network in use")
            logger.error("network_deletion_failed", network_id=network_id, error=str(e))
            raise

    async def _neutron_request(
        self, method: str, path: str, **kwargs: Any
    ) -> dict[str, Any]:
        """
        Make a request to Neutron API.

        Args:
            method: HTTP method
            path: API path
            **kwargs: Additional request parameters

        Returns:
            Response data

        Raises:
            Exception: If request fails
        """
        # Get network endpoint from service catalog or use default
        network_endpoint = self._service_catalog.get(
            "network", f"{self.auth_url.replace(':5000', ':9696')}"
        )

        headers = await self._get_auth_headers()
        url = f"{network_endpoint}{path}"

        try:
            response = await self._http_client.request(
                method, url, headers=headers, **kwargs
            )
            response.raise_for_status()

            # DELETE requests often return empty body
            if method == "DELETE":
                return {"status": "deleted"}

            return response.json()

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise Exception("404 Not Found")
            elif e.response.status_code == 409:
                if "in use" in e.response.text.lower():
                    raise Exception("Network in use")
            raise Exception(f"Neutron request failed: {e}")
        except Exception as e:
            raise Exception(f"Neutron request failed: {e}")
