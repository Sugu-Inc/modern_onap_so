"""
Pydantic schemas for configuration API requests and responses.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from orchestrator.clients.ansible.client import PlaybookStatus


class ConfigurationRequest(BaseModel):
    """Request schema for configuring a deployment."""

    playbook_path: str = Field(
        ...,
        min_length=1,
        description="Path to Ansible playbook file",
        examples=["/playbooks/configure_webserver.yml", "playbooks/setup.yml"],
    )
    extra_vars: dict[str, Any] = Field(
        default_factory=dict,
        description="Extra variables to pass to Ansible playbook",
        examples=[
            {
                "app_version": "1.2.3",
                "environment": "production",
                "enable_ssl": True,
            }
        ],
    )
    limit: str | None = Field(
        None,
        description="Limit playbook execution to specific hosts",
        examples=["web-server-1", "web*"],
    )
    ssh_private_key: str | None = Field(
        None,
        description="SSH private key for authentication (PEM format)",
    )


class ConfigurationResponse(BaseModel):
    """Response schema for configuration execution status."""

    execution_id: UUID = Field(..., description="Unique execution identifier")
    deployment_id: UUID = Field(..., description="Deployment being configured")
    status: PlaybookStatus = Field(..., description="Configuration execution status")
    playbook_path: str = Field(..., description="Path to executed playbook")
    extra_vars: dict[str, Any] = Field(
        default_factory=dict, description="Variables passed to playbook"
    )
    started_at: datetime = Field(..., description="Execution start timestamp")
    completed_at: datetime | None = Field(
        None, description="Execution completion timestamp"
    )
    return_code: int | None = Field(None, description="Ansible return code")
    stats: dict[str, Any] = Field(
        default_factory=dict,
        description="Ansible execution statistics",
    )
    error: str | None = Field(None, description="Error message if execution failed")

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "example": {
                "execution_id": "123e4567-e89b-12d3-a456-426614174000",
                "deployment_id": "550e8400-e29b-41d4-a716-446655440000",
                "status": "successful",
                "playbook_path": "/playbooks/configure_webserver.yml",
                "extra_vars": {"app_version": "1.2.3", "environment": "production"},
                "started_at": "2025-01-15T10:30:00Z",
                "completed_at": "2025-01-15T10:35:00Z",
                "return_code": 0,
                "stats": {
                    "ok": {"web-server-1": 5, "web-server-2": 5},
                    "changed": {"web-server-1": 2, "web-server-2": 2},
                    "failures": {},
                },
                "error": None,
            }
        },
    }
