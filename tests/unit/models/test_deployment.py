"""Tests for Deployment model."""

from datetime import UTC, datetime
from uuid import UUID

from orchestrator.models.deployment import Deployment, DeploymentStatus


class TestDeploymentStatus:
    """Test suite for DeploymentStatus enum."""

    def test_deployment_status_values(self) -> None:
        """Test DeploymentStatus enum values."""
        assert DeploymentStatus.PENDING == "PENDING"
        assert DeploymentStatus.IN_PROGRESS == "IN_PROGRESS"
        assert DeploymentStatus.COMPLETED == "COMPLETED"
        assert DeploymentStatus.FAILED == "FAILED"
        assert DeploymentStatus.DELETING == "DELETING"
        assert DeploymentStatus.DELETED == "DELETED"

    def test_deployment_status_members(self) -> None:
        """Test that all expected statuses are present."""
        expected_statuses = {
            "PENDING",
            "IN_PROGRESS",
            "COMPLETED",
            "FAILED",
            "DELETING",
            "DELETED",
        }
        actual_statuses = {status.value for status in DeploymentStatus}
        assert actual_statuses == expected_statuses


class TestDeployment:
    """Test suite for Deployment model."""

    def test_deployment_creation(self) -> None:
        """Test creating a deployment instance."""
        deployment = Deployment(
            name="test-deployment",
            status=DeploymentStatus.PENDING,
            template={"vm_config": {}},
            parameters={"count": 2},
            cloud_region="us-west-1",
        )

        assert deployment.name == "test-deployment"
        assert deployment.status == DeploymentStatus.PENDING
        assert deployment.template == {"vm_config": {}}
        assert deployment.parameters == {"count": 2}
        assert deployment.cloud_region == "us-west-1"
        assert deployment.resources is None
        assert deployment.error is None
        assert deployment.extra_metadata is None
        assert deployment.deleted_at is None

    def test_deployment_with_explicit_values(self) -> None:
        """Test deployment with all explicit values."""
        from uuid import uuid4

        deployment_id = uuid4()
        now = datetime.now(UTC)

        deployment = Deployment(
            id=deployment_id,
            name="test",
            status=DeploymentStatus.PENDING,
            template={},
            parameters={},
            cloud_region="region",
            created_at=now,
            updated_at=now,
        )

        assert deployment.id == deployment_id
        assert isinstance(deployment.id, UUID)
        assert deployment.status == DeploymentStatus.PENDING
        assert deployment.parameters == {}
        assert deployment.created_at == now
        assert deployment.updated_at == now

    def test_deployment_repr(self) -> None:
        """Test deployment string representation."""
        deployment = Deployment(
            name="test-deployment",
            status=DeploymentStatus.COMPLETED,
            template={},
            parameters={},
            cloud_region="us-west-1",
        )

        repr_str = repr(deployment)
        assert "Deployment" in repr_str
        assert "test-deployment" in repr_str
        assert "COMPLETED" in repr_str
        assert "us-west-1" in repr_str

    def test_is_active_property(self) -> None:
        """Test is_active property."""
        # Active states
        for status in [
            DeploymentStatus.PENDING,
            DeploymentStatus.IN_PROGRESS,
            DeploymentStatus.COMPLETED,
        ]:
            deployment = Deployment(
                name="test",
                status=status,
                template={},
                parameters={},
                cloud_region="region",
            )
            assert deployment.is_active is True

        # Inactive states
        for status in [
            DeploymentStatus.FAILED,
            DeploymentStatus.DELETING,
            DeploymentStatus.DELETED,
        ]:
            deployment = Deployment(
                name="test",
                status=status,
                template={},
                parameters={},
                cloud_region="region",
            )
            assert deployment.is_active is False

    def test_is_terminal_property(self) -> None:
        """Test is_terminal property."""
        # Terminal states
        for status in [
            DeploymentStatus.COMPLETED,
            DeploymentStatus.FAILED,
            DeploymentStatus.DELETED,
        ]:
            deployment = Deployment(
                name="test",
                status=status,
                template={},
                parameters={},
                cloud_region="region",
            )
            assert deployment.is_terminal is True

        # Non-terminal states
        for status in [
            DeploymentStatus.PENDING,
            DeploymentStatus.IN_PROGRESS,
            DeploymentStatus.DELETING,
        ]:
            deployment = Deployment(
                name="test",
                status=status,
                template={},
                parameters={},
                cloud_region="region",
            )
            assert deployment.is_terminal is False

    def test_is_deletable_property(self) -> None:
        """Test is_deletable property."""
        # Deletable states
        for status in [DeploymentStatus.COMPLETED, DeploymentStatus.FAILED]:
            deployment = Deployment(
                name="test",
                status=status,
                template={},
                parameters={},
                cloud_region="region",
            )
            assert deployment.is_deletable is True

        # Non-deletable states
        for status in [
            DeploymentStatus.PENDING,
            DeploymentStatus.IN_PROGRESS,
            DeploymentStatus.DELETING,
            DeploymentStatus.DELETED,
        ]:
            deployment = Deployment(
                name="test",
                status=status,
                template={},
                parameters={},
                cloud_region="region",
            )
            assert deployment.is_deletable is False

    def test_deployment_with_resources(self) -> None:
        """Test deployment with resources."""
        deployment = Deployment(
            name="test",
            template={},
            parameters={},
            cloud_region="region",
            resources={
                "network_id": "net-123",
                "vm_ids": ["vm-456", "vm-789"],
            },
        )

        assert deployment.resources is not None
        assert deployment.resources["network_id"] == "net-123"
        assert len(deployment.resources["vm_ids"]) == 2

    def test_deployment_with_error(self) -> None:
        """Test deployment with error details."""
        deployment = Deployment(
            name="test",
            status=DeploymentStatus.FAILED,
            template={},
            parameters={},
            cloud_region="region",
            error={
                "type": "QuotaExceeded",
                "message": "Insufficient quota",
                "failed_activity": "create_vm",
            },
        )

        assert deployment.error is not None
        assert deployment.error["type"] == "QuotaExceeded"
        assert deployment.error["message"] == "Insufficient quota"

    def test_deployment_with_extra_metadata(self) -> None:
        """Test deployment with extra metadata."""
        deployment = Deployment(
            name="test",
            template={},
            parameters={},
            cloud_region="region",
            extra_metadata={
                "configured": True,
                "playbook": "configure-web.yml",
            },
        )

        assert deployment.extra_metadata is not None
        assert deployment.extra_metadata["configured"] is True
        assert deployment.extra_metadata["playbook"] == "configure-web.yml"

    def test_deployment_with_deleted_at(self) -> None:
        """Test deployment with deleted_at timestamp."""
        deleted_time = datetime.now(UTC)
        deployment = Deployment(
            name="test",
            status=DeploymentStatus.DELETED,
            template={},
            parameters={},
            cloud_region="region",
            deleted_at=deleted_time,
        )

        assert deployment.deleted_at == deleted_time
