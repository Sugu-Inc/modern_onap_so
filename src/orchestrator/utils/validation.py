"""
Input validation and sanitization utilities.

Provides additional validation beyond Pydantic for security.
"""

import re
from typing import Any


def sanitize_string(value: str, max_length: int = 1000) -> str:
    """
    Sanitize string input to prevent XSS and injection attacks.

    Args:
        value: Input string to sanitize
        max_length: Maximum allowed length

    Returns:
        Sanitized string

    Raises:
        ValueError: If string is too long
    """
    if len(value) > max_length:
        raise ValueError(f"String exceeds maximum length of {max_length}")

    # Remove null bytes
    sanitized = value.replace("\x00", "")

    # Remove control characters except whitespace
    sanitized = "".join(
        char for char in sanitized if char.isprintable() or char.isspace()
    )

    return sanitized.strip()


def validate_name(value: str) -> str:
    """
    Validate and sanitize name fields.

    Names must:
    - Be 1-255 characters
    - Start with alphanumeric
    - Contain only alphanumeric, hyphens, underscores

    Args:
        value: Name to validate

    Returns:
        Validated name

    Raises:
        ValueError: If name is invalid
    """
    if not value:
        raise ValueError("Name cannot be empty")

    if len(value) > 255:
        raise ValueError("Name exceeds maximum length of 255 characters")

    # Check pattern: alphanumeric start, then alphanumeric/hyphen/underscore
    pattern = r"^[a-zA-Z0-9][a-zA-Z0-9\-_]*$"
    if not re.match(pattern, value):
        raise ValueError(
            "Name must start with alphanumeric and contain only "
            "alphanumeric characters, hyphens, and underscores"
        )

    return value


def validate_cloud_region(value: str) -> str:
    """
    Validate cloud region name.

    Args:
        value: Cloud region to validate

    Returns:
        Validated region

    Raises:
        ValueError: If region is invalid
    """
    if not value:
        raise ValueError("Cloud region cannot be empty")

    if len(value) > 100:
        raise ValueError("Cloud region exceeds maximum length of 100 characters")

    # Allow alphanumeric, hyphens, underscores
    pattern = r"^[a-zA-Z0-9\-_]+$"
    if not re.match(pattern, value):
        raise ValueError(
            "Cloud region must contain only alphanumeric characters, "
            "hyphens, and underscores"
        )

    return value


def validate_playbook_path(value: str) -> str:
    """
    Validate Ansible playbook path to prevent path traversal.

    Args:
        value: Playbook path to validate

    Returns:
        Validated path

    Raises:
        ValueError: If path is invalid or contains traversal attempts
    """
    if not value:
        raise ValueError("Playbook path cannot be empty")

    # Check for path traversal attempts
    if ".." in value:
        raise ValueError("Path traversal detected - '..' not allowed")

    # Check for absolute paths (should be relative)
    if value.startswith("/"):
        raise ValueError("Absolute paths not allowed - use relative paths")

    # Must end with .yml or .yaml
    if not (value.endswith(".yml") or value.endswith(".yaml")):
        raise ValueError("Playbook path must end with .yml or .yaml")

    # Sanitize and check length
    sanitized = sanitize_string(value, max_length=500)

    return sanitized


def sanitize_dict(data: dict[str, Any], max_depth: int = 10) -> dict[str, Any]:
    """
    Sanitize dictionary recursively.

    Args:
        data: Dictionary to sanitize
        max_depth: Maximum nesting depth

    Returns:
        Sanitized dictionary

    Raises:
        ValueError: If nesting is too deep
    """
    if max_depth <= 0:
        raise ValueError("Dictionary nesting exceeds maximum depth")

    result = {}
    for key, value in data.items():
        # Sanitize keys
        if isinstance(key, str):
            sanitized_key = sanitize_string(key, max_length=100)
        else:
            sanitized_key = str(key)

        # Sanitize values
        if isinstance(value, str):
            result[sanitized_key] = sanitize_string(value)
        elif isinstance(value, dict):
            result[sanitized_key] = sanitize_dict(value, max_depth - 1)
        elif isinstance(value, list):
            result[sanitized_key] = [
                sanitize_dict(item, max_depth - 1) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            result[sanitized_key] = value

    return result


def validate_template(template: dict[str, Any]) -> dict[str, Any]:
    """
    Validate infrastructure template structure.

    Args:
        template: Template to validate

    Returns:
        Validated template

    Raises:
        ValueError: If template is invalid
    """
    if not template:
        raise ValueError("Template cannot be empty")

    # Sanitize the entire template
    sanitized = sanitize_dict(template)

    # Validate required top-level keys
    if "vm_config" not in sanitized:
        raise ValueError("Template must contain 'vm_config' key")

    vm_config = sanitized["vm_config"]
    if not isinstance(vm_config, dict):
        raise ValueError("'vm_config' must be a dictionary")

    # Validate VM config has required fields
    required_fields = ["flavor", "image"]
    for field in required_fields:
        if field not in vm_config:
            raise ValueError(f"'vm_config' must contain '{field}' key")

    return sanitized
