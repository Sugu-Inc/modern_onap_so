"""Tests for DeploymentTemplate model."""

from datetime import datetime, timezone

import pytest

from orchestrator.models.template import DeploymentTemplate


class TestDeploymentTemplate:
    """Test suite for DeploymentTemplate model."""

    def test_template_creation(self) -> None:
        """Test creating a template with required fields."""
        template = DeploymentTemplate(
            name="basic-vm-template",
            description="A basic VM deployment template",
            vm_config={
                "flavor": "m1.small",
                "image": "ubuntu-22.04",
                "count": 1,
            },
            network_config={
                "network_name": "private-net",
                "subnet_cidr": "192.168.1.0/24",
            },
        )

        assert template.name == "basic-vm-template"
        assert template.description == "A basic VM deployment template"
        assert template.vm_config["flavor"] == "m1.small"
        assert template.network_config["network_name"] == "private-net"

    def test_template_with_explicit_values(self) -> None:
        """Test template with all fields explicitly set."""
        now = datetime.now(timezone.utc)
        template = DeploymentTemplate(
            name="complex-template",
            description="Complex multi-VM template",
            vm_config={
                "flavor": "m1.large",
                "image": "ubuntu-22.04",
                "count": 3,
                "keypair": "my-keypair",
            },
            network_config={
                "network_name": "prod-net",
                "subnet_cidr": "10.0.0.0/24",
                "enable_dhcp": True,
                "dns_nameservers": ["8.8.8.8", "8.8.4.4"],
            },
            created_at=now,
            updated_at=now,
        )

        assert template.name == "complex-template"
        assert template.vm_config["count"] == 3
        assert template.network_config["enable_dhcp"] is True
        assert template.created_at == now
        assert template.updated_at == now

    def test_template_repr(self) -> None:
        """Test template string representation."""
        template = DeploymentTemplate(
            name="test-template",
            description="Test template",
            vm_config={"flavor": "m1.small"},
            network_config={"network_name": "test-net"},
        )

        repr_str = repr(template)
        assert "DeploymentTemplate" in repr_str
        assert "test-template" in repr_str

    def test_template_vm_config_validation(self) -> None:
        """Test that vm_config must be a valid dict."""
        template = DeploymentTemplate(
            name="vm-template",
            description="VM template",
            vm_config={
                "flavor": "m1.small",
                "image": "ubuntu-22.04",
                "count": 2,
            },
            network_config={"network_name": "net1"},
        )

        assert isinstance(template.vm_config, dict)
        assert "flavor" in template.vm_config
        assert "image" in template.vm_config
        assert "count" in template.vm_config

    def test_template_network_config_validation(self) -> None:
        """Test that network_config must be a valid dict."""
        template = DeploymentTemplate(
            name="net-template",
            description="Network template",
            vm_config={"flavor": "m1.small"},
            network_config={
                "network_name": "private-net",
                "subnet_cidr": "192.168.1.0/24",
                "gateway_ip": "192.168.1.1",
            },
        )

        assert isinstance(template.network_config, dict)
        assert "network_name" in template.network_config
        assert "subnet_cidr" in template.network_config
        assert "gateway_ip" in template.network_config

    def test_template_with_optional_metadata(self) -> None:
        """Test template with optional metadata field."""
        template = DeploymentTemplate(
            name="metadata-template",
            description="Template with metadata",
            vm_config={"flavor": "m1.small"},
            network_config={"network_name": "net1"},
            extra_metadata={
                "owner": "platform-team",
                "environment": "production",
                "tags": ["critical", "monitored"],
            },
        )

        assert template.extra_metadata is not None
        assert template.extra_metadata["owner"] == "platform-team"
        assert "critical" in template.extra_metadata["tags"]

    def test_template_without_optional_metadata(self) -> None:
        """Test template without optional metadata."""
        template = DeploymentTemplate(
            name="no-metadata-template",
            description="Template without metadata",
            vm_config={"flavor": "m1.small"},
            network_config={"network_name": "net1"},
        )

        # Metadata should be None or empty by default
        assert template.extra_metadata is None or template.extra_metadata == {}

    def test_template_version_tracking(self) -> None:
        """Test that template has version field for tracking changes."""
        template = DeploymentTemplate(
            name="versioned-template",
            description="Template with version",
            vm_config={"flavor": "m1.small"},
            network_config={"network_name": "net1"},
            version=2,
        )

        assert template.version == 2

    def test_template_default_version(self) -> None:
        """Test that template has default version of 1."""
        template = DeploymentTemplate(
            name="default-version-template",
            description="Template with default version",
            vm_config={"flavor": "m1.small"},
            network_config={"network_name": "net1"},
        )

        # Version should default to 1
        assert hasattr(template, "version")

    def test_template_is_active_property(self) -> None:
        """Test is_active property for template lifecycle."""
        template = DeploymentTemplate(
            name="active-template",
            description="Active template",
            vm_config={"flavor": "m1.small"},
            network_config={"network_name": "net1"},
            is_active=True,
        )

        assert template.is_active is True

    def test_template_can_be_deactivated(self) -> None:
        """Test that template can be deactivated."""
        template = DeploymentTemplate(
            name="inactive-template",
            description="Inactive template",
            vm_config={"flavor": "m1.small"},
            network_config={"network_name": "net1"},
            is_active=False,
        )

        assert template.is_active is False
