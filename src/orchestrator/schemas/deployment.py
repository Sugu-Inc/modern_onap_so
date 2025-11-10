"""
Pydantic schemas for deployment API requests and responses.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from orchestrator.models.deployment import DeploymentStatus


class DeploymentBase(BaseModel):
    """Base schema for deployment data."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Deployment name",
        examples=["my-web-app-prod"],
    )
    cloud_region: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Cloud region identifier",
        examples=["us-west-1", "RegionOne"],
    )


class CreateDeploymentRequest(DeploymentBase):
    """Request schema for creating a deployment."""

    template: dict[str, Any] = Field(
        ...,
        description="Deployment template configuration",
        examples=[
            {
                "vm_config": {"web": {"flavor": "m1.small", "image": "ubuntu-22.04", "count": 2}},
                "network_config": {"cidr": "10.0.0.0/16"},
            }
        ],
    )
    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="User-provided parameters to override template defaults",
        examples=[{"web_count": 3, "environment": "production"}],
    )

    @field_validator("template")
    @classmethod
    def validate_template(cls, v: dict[str, Any]) -> dict[str, Any]:
        """Validate template has required fields."""
        if not v:
            raise ValueError("Template cannot be empty")
        return v


class UpdateDeploymentRequest(BaseModel):
    """Request schema for updating a deployment."""

    parameters: dict[str, Any] | None = Field(
        None,
        description="Updated parameters",
    )
    resources: dict[str, Any] | None = Field(
        None,
        description="Updated resource IDs",
    )


class DeploymentResponse(DeploymentBase):
    """Response schema for deployment data."""

    id: UUID = Field(..., description="Deployment unique identifier")
    status: DeploymentStatus = Field(..., description="Deployment status")
    template: dict[str, Any] = Field(..., description="Deployment template")
    parameters: dict[str, Any] = Field(..., description="Deployment parameters")
    resources: dict[str, Any] | None = Field(
        None,
        description="Created resource IDs (VMs, networks, etc.)",
    )
    error: dict[str, Any] | None = Field(
        None,
        description="Error details if deployment failed",
    )
    extra_metadata: dict[str, Any] | None = Field(
        None,
        description="Additional metadata",
    )
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    deleted_at: datetime | None = Field(None, description="Deletion timestamp")

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "name": "my-web-app-prod",
                "status": "COMPLETED",
                "template": {
                    "vm_config": {
                        "web": {"flavor": "m1.small", "image": "ubuntu-22.04", "count": 2}
                    }
                },
                "parameters": {"web_count": 2},
                "cloud_region": "us-west-1",
                "resources": {
                    "network_id": "net-123",
                    "vm_ids": ["vm-456", "vm-789"],
                },
                "error": None,
                "extra_metadata": None,
                "created_at": "2025-01-15T10:30:00Z",
                "updated_at": "2025-01-15T10:35:00Z",
                "deleted_at": None,
            }
        },
    }


class DeploymentListResponse(BaseModel):
    """Response schema for listing deployments."""

    items: list[DeploymentResponse] = Field(..., description="List of deployments")
    total: int = Field(..., ge=0, description="Total number of deployments")
    limit: int = Field(..., ge=1, description="Page size limit")
    offset: int = Field(..., ge=0, description="Page offset")

    model_config = {
        "json_schema_extra": {
            "example": {
                "items": [
                    {
                        "id": "550e8400-e29b-41d4-a716-446655440000",
                        "name": "web-app-1",
                        "status": "COMPLETED",
                        "cloud_region": "us-west-1",
                    }
                ],
                "total": 42,
                "limit": 10,
                "offset": 0,
            }
        }
    }
