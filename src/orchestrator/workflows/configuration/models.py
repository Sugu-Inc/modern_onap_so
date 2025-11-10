"""
Data models for configuration workflows.
"""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ConfigureWorkflowInput(BaseModel):
    """Input parameters for configuration workflow."""

    deployment_id: UUID = Field(..., description="Deployment to configure")
    playbook_path: str = Field(..., description="Path to Ansible playbook")
    extra_vars: dict[str, Any] = Field(
        default_factory=dict, description="Extra variables for playbook"
    )
    limit: str | None = Field(None, description="Limit to specific hosts")
    resources: dict[str, Any] = Field(..., description="Deployment resources")


class ConfigureWorkflowResult(BaseModel):
    """Result of configuration workflow execution."""

    success: bool = Field(..., description="Whether configuration succeeded")
    deployment_id: UUID = Field(..., description="Deployment that was configured")
    execution_id: UUID | None = Field(None, description="Ansible execution ID")
    configured_hosts: list[str] = Field(
        default_factory=list, description="List of configured host IPs"
    )
    error: str | None = Field(None, description="Error message if failed")
