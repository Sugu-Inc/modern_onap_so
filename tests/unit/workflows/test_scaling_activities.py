"""
Unit tests for scaling activities.
"""

import pytest

from orchestrator.workflows.scaling.activities import scale_in_activity, scale_out_activity


class TestScaleOutActivity:
    """Test scale out activity."""

    @pytest.mark.asyncio
    async def test_scale_out_creates_servers(self) -> None:
        """Test scaling out creates new server IDs."""
        result = await scale_out_activity(
            count_to_add=3,
            template={"vm_config": {"flavor": "m1.small"}},
            network_id="network-123",
            cloud_region="RegionOne",
        )

        assert result["success"] is True
        assert result["error"] is None
        assert len(result["new_server_ids"]) == 3
        assert all(isinstance(sid, str) for sid in result["new_server_ids"])

    @pytest.mark.asyncio
    async def test_scale_out_single_vm(self) -> None:
        """Test scaling out with a single VM."""
        result = await scale_out_activity(
            count_to_add=1,
            template={"vm_config": {"flavor": "m1.medium"}},
            network_id="network-456",
            cloud_region="RegionTwo",
        )

        assert result["success"] is True
        assert len(result["new_server_ids"]) == 1

    @pytest.mark.asyncio
    async def test_scale_out_with_openstack_config(self) -> None:
        """Test scaling out with OpenStack config."""
        openstack_config = {
            "auth_url": "http://localhost:5000/v3",
            "username": "admin",
            "password": "secret",
        }

        result = await scale_out_activity(
            count_to_add=2,
            template={"vm_config": {"flavor": "m1.small"}},
            network_id="network-789",
            cloud_region="RegionOne",
            openstack_config=openstack_config,
        )

        assert result["success"] is True
        assert len(result["new_server_ids"]) == 2


class TestScaleInActivity:
    """Test scale in activity."""

    @pytest.mark.asyncio
    async def test_scale_in_removes_servers(self) -> None:
        """Test scaling in removes servers."""
        server_ids = ["server-1", "server-2", "server-3", "server-4", "server-5"]

        result = await scale_in_activity(
            server_ids=server_ids,
            count_to_remove=2,
            min_count=1,
            cloud_region="RegionOne",
        )

        assert result["success"] is True
        assert result["error"] is None
        assert len(result["removed_server_ids"]) == 2
        # Should remove last 2 servers
        assert result["removed_server_ids"] == ["server-4", "server-5"]

    @pytest.mark.asyncio
    async def test_scale_in_single_vm(self) -> None:
        """Test scaling in with a single VM removal."""
        server_ids = ["server-1", "server-2", "server-3"]

        result = await scale_in_activity(
            server_ids=server_ids,
            count_to_remove=1,
            min_count=1,
            cloud_region="RegionOne",
        )

        assert result["success"] is True
        assert len(result["removed_server_ids"]) == 1
        assert result["removed_server_ids"] == ["server-3"]

    @pytest.mark.asyncio
    async def test_scale_in_respects_min_count(self) -> None:
        """Test that scale in respects minimum count."""
        server_ids = ["server-1", "server-2", "server-3"]

        result = await scale_in_activity(
            server_ids=server_ids,
            count_to_remove=3,  # Would leave 0, but min is 1
            min_count=1,
            cloud_region="RegionOne",
        )

        assert result["success"] is False
        assert result["error"] is not None
        assert "would leave 0 (min: 1)" in result["error"]
        assert result["removed_server_ids"] == []

    @pytest.mark.asyncio
    async def test_scale_in_exact_min_count(self) -> None:
        """Test scaling in to exactly the minimum count."""
        server_ids = ["server-1", "server-2", "server-3"]

        result = await scale_in_activity(
            server_ids=server_ids,
            count_to_remove=2,  # Will leave 1, which equals min
            min_count=1,
            cloud_region="RegionOne",
        )

        assert result["success"] is True
        assert len(result["removed_server_ids"]) == 2

    @pytest.mark.asyncio
    async def test_scale_in_with_openstack_config(self) -> None:
        """Test scaling in with OpenStack config."""
        server_ids = ["server-1", "server-2", "server-3", "server-4"]
        openstack_config = {
            "auth_url": "http://localhost:5000/v3",
            "username": "admin",
            "password": "secret",
        }

        result = await scale_in_activity(
            server_ids=server_ids,
            count_to_remove=2,
            min_count=1,
            cloud_region="RegionOne",
            openstack_config=openstack_config,
        )

        assert result["success"] is True
        assert len(result["removed_server_ids"]) == 2

    @pytest.mark.asyncio
    async def test_scale_in_higher_min_count(self) -> None:
        """Test scaling in with higher minimum count."""
        server_ids = ["server-1", "server-2", "server-3", "server-4", "server-5"]

        result = await scale_in_activity(
            server_ids=server_ids,
            count_to_remove=3,  # Would leave 2, but min is 3
            min_count=3,
            cloud_region="RegionOne",
        )

        assert result["success"] is False
        assert "would leave 2 (min: 3)" in result["error"]
