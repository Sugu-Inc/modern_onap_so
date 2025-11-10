"""
Unit tests for validation utilities.
"""

import pytest

from orchestrator.utils.validation import (
    sanitize_dict,
    sanitize_string,
    validate_cloud_region,
    validate_name,
    validate_playbook_path,
    validate_template,
)


class TestSanitizeString:
    """Test string sanitization."""

    def test_sanitize_normal_string(self) -> None:
        """Test sanitizing normal string."""
        result = sanitize_string("hello world")
        assert result == "hello world"

    def test_sanitize_removes_null_bytes(self) -> None:
        """Test that null bytes are removed."""
        result = sanitize_string("hello\x00world")
        assert result == "helloworld"

    def test_sanitize_removes_control_characters(self) -> None:
        """Test that control characters are removed."""
        result = sanitize_string("hello\x01\x02world")
        assert result == "helloworld"

    def test_sanitize_preserves_whitespace(self) -> None:
        """Test that whitespace is preserved."""
        result = sanitize_string("hello\nworld\ttab")
        assert "hello" in result
        assert "world" in result
        assert "tab" in result

    def test_sanitize_strips_whitespace(self) -> None:
        """Test that leading/trailing whitespace is stripped."""
        result = sanitize_string("  hello world  ")
        assert result == "hello world"

    def test_sanitize_exceeds_max_length(self) -> None:
        """Test that overly long strings raise error."""
        long_string = "a" * 1001
        with pytest.raises(ValueError, match="exceeds maximum length"):
            sanitize_string(long_string, max_length=1000)

    def test_sanitize_custom_max_length(self) -> None:
        """Test sanitization with custom max length."""
        result = sanitize_string("hello", max_length=10)
        assert result == "hello"


class TestValidateName:
    """Test name validation."""

    def test_validate_normal_name(self) -> None:
        """Test validating normal name."""
        result = validate_name("my-deployment-123")
        assert result == "my-deployment-123"

    def test_validate_alphanumeric_only(self) -> None:
        """Test name with only alphanumeric."""
        result = validate_name("deployment123")
        assert result == "deployment123"

    def test_validate_with_underscore(self) -> None:
        """Test name with underscores."""
        result = validate_name("my_deployment")
        assert result == "my_deployment"

    def test_validate_empty_name(self) -> None:
        """Test that empty name raises error."""
        with pytest.raises(ValueError, match="cannot be empty"):
            validate_name("")

    def test_validate_name_starts_with_hyphen(self) -> None:
        """Test that name cannot start with hyphen."""
        with pytest.raises(ValueError, match="must start with alphanumeric"):
            validate_name("-deployment")

    def test_validate_name_starts_with_underscore(self) -> None:
        """Test that name cannot start with underscore."""
        with pytest.raises(ValueError, match="must start with alphanumeric"):
            validate_name("_deployment")

    def test_validate_name_with_special_chars(self) -> None:
        """Test that special characters are rejected."""
        with pytest.raises(ValueError, match="alphanumeric characters"):
            validate_name("my@deployment")

    def test_validate_name_too_long(self) -> None:
        """Test that overly long names are rejected."""
        long_name = "a" * 256
        with pytest.raises(ValueError, match="exceeds maximum length"):
            validate_name(long_name)


class TestValidateCloudRegion:
    """Test cloud region validation."""

    def test_validate_normal_region(self) -> None:
        """Test validating normal region."""
        result = validate_cloud_region("us-west-1")
        assert result == "us-west-1"

    def test_validate_region_with_underscore(self) -> None:
        """Test region with underscores."""
        result = validate_cloud_region("RegionOne")
        assert result == "RegionOne"

    def test_validate_empty_region(self) -> None:
        """Test that empty region raises error."""
        with pytest.raises(ValueError, match="cannot be empty"):
            validate_cloud_region("")

    def test_validate_region_with_special_chars(self) -> None:
        """Test that special characters are rejected."""
        with pytest.raises(ValueError, match="alphanumeric characters"):
            validate_cloud_region("us-west@1")

    def test_validate_region_too_long(self) -> None:
        """Test that overly long regions are rejected."""
        long_region = "a" * 101
        with pytest.raises(ValueError, match="exceeds maximum length"):
            validate_cloud_region(long_region)


class TestValidatePlaybookPath:
    """Test playbook path validation."""

    def test_validate_normal_playbook(self) -> None:
        """Test validating normal playbook path."""
        result = validate_playbook_path("playbooks/setup.yml")
        assert result == "playbooks/setup.yml"

    def test_validate_playbook_yaml_extension(self) -> None:
        """Test playbook with .yaml extension."""
        result = validate_playbook_path("setup.yaml")
        assert result == "setup.yaml"

    def test_validate_empty_path(self) -> None:
        """Test that empty path raises error."""
        with pytest.raises(ValueError, match="cannot be empty"):
            validate_playbook_path("")

    def test_validate_path_traversal(self) -> None:
        """Test that path traversal is blocked."""
        with pytest.raises(ValueError, match="Path traversal detected"):
            validate_playbook_path("../../etc/passwd.yml")

    def test_validate_absolute_path(self) -> None:
        """Test that absolute paths are rejected."""
        with pytest.raises(ValueError, match="Absolute paths not allowed"):
            validate_playbook_path("/etc/ansible/setup.yml")

    def test_validate_missing_extension(self) -> None:
        """Test that files without .yml/.yaml are rejected."""
        with pytest.raises(ValueError, match="must end with"):
            validate_playbook_path("playbooks/setup.txt")

    def test_validate_playbook_too_long(self) -> None:
        """Test that overly long paths are rejected."""
        long_path = "a" * 500 + ".yml"
        with pytest.raises(ValueError, match="exceeds maximum length"):
            validate_playbook_path(long_path)


class TestSanitizeDict:
    """Test dictionary sanitization."""

    def test_sanitize_simple_dict(self) -> None:
        """Test sanitizing simple dictionary."""
        data = {"key": "value", "number": 123}
        result = sanitize_dict(data)
        assert result["key"] == "value"
        assert result["number"] == 123

    def test_sanitize_nested_dict(self) -> None:
        """Test sanitizing nested dictionary."""
        data = {"outer": {"inner": "value"}}
        result = sanitize_dict(data)
        assert result["outer"]["inner"] == "value"

    def test_sanitize_dict_with_list(self) -> None:
        """Test sanitizing dictionary with list."""
        data = {"items": [{"name": "item1"}, {"name": "item2"}]}
        result = sanitize_dict(data)
        assert len(result["items"]) == 2
        assert result["items"][0]["name"] == "item1"

    def test_sanitize_removes_null_bytes_in_values(self) -> None:
        """Test that null bytes in values are removed."""
        data = {"key": "value\x00with\x00nulls"}
        result = sanitize_dict(data)
        assert "\x00" not in result["key"]

    def test_sanitize_dict_max_depth(self) -> None:
        """Test that excessive nesting raises error."""
        # Create deeply nested dict
        data: dict = {}
        current = data
        for i in range(15):
            current["nested"] = {}
            current = current["nested"]

        with pytest.raises(ValueError, match="exceeds maximum depth"):
            sanitize_dict(data, max_depth=10)

    def test_sanitize_dict_preserves_types(self) -> None:
        """Test that non-string types are preserved."""
        data = {"int": 42, "float": 3.14, "bool": True, "none": None}
        result = sanitize_dict(data)
        assert result["int"] == 42
        assert result["float"] == 3.14
        assert result["bool"] is True
        assert result["none"] is None


class TestValidateTemplate:
    """Test template validation."""

    def test_validate_normal_template(self) -> None:
        """Test validating normal template."""
        template = {
            "vm_config": {"flavor": "m1.small", "image": "ubuntu-22.04"},
            "network_config": {"cidr": "192.168.1.0/24"},
        }
        result = validate_template(template)
        assert "vm_config" in result
        assert result["vm_config"]["flavor"] == "m1.small"

    def test_validate_empty_template(self) -> None:
        """Test that empty template raises error."""
        with pytest.raises(ValueError, match="cannot be empty"):
            validate_template({})

    def test_validate_template_missing_vm_config(self) -> None:
        """Test that template without vm_config raises error."""
        template = {"network_config": {}}
        with pytest.raises(ValueError, match="must contain 'vm_config'"):
            validate_template(template)

    def test_validate_template_vm_config_not_dict(self) -> None:
        """Test that vm_config must be a dictionary."""
        template = {"vm_config": "not-a-dict"}
        with pytest.raises(ValueError, match="must be a dictionary"):
            validate_template(template)

    def test_validate_template_missing_flavor(self) -> None:
        """Test that vm_config must have flavor."""
        template = {"vm_config": {"image": "ubuntu-22.04"}}
        with pytest.raises(ValueError, match="must contain 'flavor'"):
            validate_template(template)

    def test_validate_template_missing_image(self) -> None:
        """Test that vm_config must have image."""
        template = {"vm_config": {"flavor": "m1.small"}}
        with pytest.raises(ValueError, match="must contain 'image'"):
            validate_template(template)

    def test_validate_template_sanitizes_content(self) -> None:
        """Test that template content is sanitized."""
        template = {
            "vm_config": {
                "flavor": "m1.small\x00",
                "image": "ubuntu-22.04",
            }
        }
        result = validate_template(template)
        assert "\x00" not in result["vm_config"]["flavor"]
