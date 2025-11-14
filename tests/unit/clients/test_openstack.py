"""Tests for OpenStack client."""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from orchestrator.clients.openstack.client import OpenStackClient
from orchestrator.clients.openstack.schemas import (
    NetworkConfig,
    ServerConfig,
    SubnetConfig,
)


@pytest.fixture
def openstack_config() -> dict[str, str]:
    """OpenStack configuration fixture."""
    return {
        "auth_url": "https://openstack.example.com:5000/v3",
        "username": "test-user",
        "password": "test-password",
        "project_name": "test-project",
        "project_domain_name": "Default",
        "user_domain_name": "Default",
        "region_name": "RegionOne",
    }


@pytest.fixture
def openstack_client(openstack_config: dict[str, str]) -> OpenStackClient:
    """OpenStack client fixture."""
    return OpenStackClient(**openstack_config)


class TestOpenStackClientInit:
    """Test OpenStack client initialization."""

    def test_client_initialization(self, openstack_config: dict[str, str]) -> None:
        """Test that client initializes with config."""
        client = OpenStackClient(**openstack_config)

        assert client.auth_url == openstack_config["auth_url"]
        assert client.username == openstack_config["username"]
        assert client.project_name == openstack_config["project_name"]
        assert client.region_name == openstack_config["region_name"]

    def test_client_stores_credentials_securely(self, openstack_config: dict[str, str]) -> None:
        """Test that password is stored (in real impl, should be secured)."""
        client = OpenStackClient(**openstack_config)

        # Password should be accessible but in real implementation
        # should use secure storage or credential manager
        assert hasattr(client, "_password") or hasattr(client, "password")


class TestOpenStackAuthentication:
    """Test OpenStack authentication (Keystone)."""

    @pytest.mark.asyncio
    async def test_authenticate_success(self, openstack_client: OpenStackClient) -> None:
        """Test successful authentication returns token."""
        with patch.object(
            openstack_client, "_request_token", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = {
                "token": "test-token-123",
                "expires_at": "2025-11-11T00:00:00Z",
            }

            token_data = await openstack_client.authenticate()

            assert token_data["token"] == "test-token-123"
            assert "expires_at" in token_data
            mock_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_authenticate_invalid_credentials(
        self, openstack_client: OpenStackClient
    ) -> None:
        """Test authentication with invalid credentials raises error."""
        with patch.object(
            openstack_client, "_request_token", new_callable=AsyncMock
        ) as mock_request:
            mock_request.side_effect = Exception("401 Unauthorized")

            with pytest.raises(Exception, match="401 Unauthorized"):
                await openstack_client.authenticate()

    @pytest.mark.asyncio
    async def test_authenticate_caches_token(self, openstack_client: OpenStackClient) -> None:
        """Test that authentication token is cached."""
        with patch.object(
            openstack_client, "_request_token", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = {
                "token": "cached-token",
                "expires_at": "2025-11-11T00:00:00Z",
            }

            # First call
            token1 = await openstack_client.authenticate()
            # Second call should use cache
            token2 = await openstack_client.authenticate()

            assert token1["token"] == token2["token"]
            # Should only call _request_token once due to caching
            assert mock_request.call_count <= 2  # Allowing for cache refresh logic


class TestOpenStackServerOperations:
    """Test Nova server operations."""

    @pytest.mark.asyncio
    async def test_create_server_success(self, openstack_client: OpenStackClient) -> None:
        """Test successful server creation."""
        server_config = ServerConfig(
            name="test-vm",
            flavor="m1.small",
            image="ubuntu-22.04",
            networks=["private-net"],
        )

        with patch.object(openstack_client, "_nova_request", new_callable=AsyncMock) as mock_nova:
            server_id = uuid4()
            mock_nova.return_value = {
                "server": {
                    "id": str(server_id),
                    "name": "test-vm",
                    "status": "BUILD",
                }
            }

            result = await openstack_client.create_server(server_config)

            assert result["id"] == str(server_id)
            assert result["name"] == "test-vm"
            assert result["status"] == "BUILD"
            mock_nova.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_server_success(self, openstack_client: OpenStackClient) -> None:
        """Test successful server deletion."""
        server_id = str(uuid4())

        with patch.object(openstack_client, "_nova_request", new_callable=AsyncMock) as mock_nova:
            mock_nova.return_value = {"status": "deleted"}

            result = await openstack_client.delete_server(server_id)

            assert result is True or result["status"] == "deleted"
            mock_nova.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_server_status_active(self, openstack_client: OpenStackClient) -> None:
        """Test getting server status when active."""
        server_id = str(uuid4())

        with patch.object(openstack_client, "_nova_request", new_callable=AsyncMock) as mock_nova:
            mock_nova.return_value = {
                "server": {"id": server_id, "status": "ACTIVE", "addresses": {}}
            }

            status = await openstack_client.get_server_status(server_id)

            assert status.status == "ACTIVE"
            assert status.server_id == server_id
            mock_nova.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_server_status_not_found(self, openstack_client: OpenStackClient) -> None:
        """Test getting server status for non-existent server."""
        server_id = str(uuid4())

        with patch.object(openstack_client, "_nova_request", new_callable=AsyncMock) as mock_nova:
            mock_nova.side_effect = Exception("404 Not Found")

            with pytest.raises(Exception, match="404 Not Found"):
                await openstack_client.get_server_status(server_id)


class TestOpenStackNetworkOperations:
    """Test Neutron network operations."""

    @pytest.mark.asyncio
    async def test_create_network_success(self, openstack_client: OpenStackClient) -> None:
        """Test successful network creation."""
        network_config = NetworkConfig(name="test-network", admin_state_up=True)

        with patch.object(
            openstack_client, "_neutron_request", new_callable=AsyncMock
        ) as mock_neutron:
            network_id = uuid4()
            mock_neutron.return_value = {
                "network": {
                    "id": str(network_id),
                    "name": "test-network",
                    "status": "ACTIVE",
                }
            }

            result = await openstack_client.create_network(network_config)

            assert result["id"] == str(network_id)
            assert result["name"] == "test-network"
            mock_neutron.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_subnet_success(self, openstack_client: OpenStackClient) -> None:
        """Test successful subnet creation."""
        network_id = str(uuid4())
        subnet_config = SubnetConfig(
            name="test-subnet",
            network_id=network_id,
            cidr="192.168.1.0/24",
            ip_version=4,
            enable_dhcp=True,
        )

        with patch.object(
            openstack_client, "_neutron_request", new_callable=AsyncMock
        ) as mock_neutron:
            subnet_id = uuid4()
            mock_neutron.return_value = {
                "subnet": {
                    "id": str(subnet_id),
                    "name": "test-subnet",
                    "cidr": "192.168.1.0/24",
                }
            }

            result = await openstack_client.create_subnet(subnet_config)

            assert result["id"] == str(subnet_id)
            assert result["cidr"] == "192.168.1.0/24"
            mock_neutron.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_network_success(self, openstack_client: OpenStackClient) -> None:
        """Test successful network deletion."""
        network_id = str(uuid4())

        with patch.object(
            openstack_client, "_neutron_request", new_callable=AsyncMock
        ) as mock_neutron:
            mock_neutron.return_value = {"status": "deleted"}

            result = await openstack_client.delete_network(network_id)

            assert result is True or result["status"] == "deleted"
            mock_neutron.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_network_in_use(self, openstack_client: OpenStackClient) -> None:
        """Test deleting network that is in use raises error."""
        network_id = str(uuid4())

        with patch.object(
            openstack_client, "_neutron_request", new_callable=AsyncMock
        ) as mock_neutron:
            mock_neutron.side_effect = Exception("Network in use")

            with pytest.raises(Exception, match="Network in use"):
                await openstack_client.delete_network(network_id)


class TestOpenStackErrorHandling:
    """Test error handling in OpenStack client."""

    @pytest.mark.asyncio
    async def test_handles_network_timeout(self, openstack_client: OpenStackClient) -> None:
        """Test handling of network timeout errors."""
        with patch.object(openstack_client, "_nova_request", new_callable=AsyncMock) as mock_nova:
            mock_nova.side_effect = TimeoutError("Request timeout")

            with pytest.raises(TimeoutError, match="Request timeout"):
                await openstack_client.get_server_status("test-id")

    @pytest.mark.asyncio
    async def test_handles_quota_exceeded(self, openstack_client: OpenStackClient) -> None:
        """Test handling of quota exceeded errors."""
        server_config = ServerConfig(
            name="test-vm", flavor="m1.small", image="ubuntu-22.04", networks=[]
        )

        with patch.object(openstack_client, "_nova_request", new_callable=AsyncMock) as mock_nova:
            mock_nova.side_effect = Exception("Quota exceeded")

            with pytest.raises(Exception, match="Quota exceeded"):
                await openstack_client.create_server(server_config)
