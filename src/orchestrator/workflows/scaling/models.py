"""
Data models for scaling workflows.
"""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ScaleWorkflowInput(BaseModel):
    """Input parameters for scaling workflow."""

    deployment_id: UUID = Field(..., description="Deployment to scale")
    current_count: int = Field(..., description="Current number of VMs")
    target_count: int = Field(..., description="Target number of VMs")
    min_count: int = Field(..., description="Minimum number of VMs to maintain")
    max_count: int | None = Field(None, description="Maximum number of VMs allowed")
    resources: dict[str, Any] = Field(..., description="Current deployment resources")
    template: dict[str, Any] = Field(..., description="VM template configuration")
    cloud_region: str = Field(..., description="Cloud region for deployment")


class ScaleWorkflowResult(BaseModel):
    """Result of scaling workflow execution."""

    success: bool = Field(..., description="Whether scaling succeeded")
    deployment_id: UUID = Field(..., description="Deployment that was scaled")
    initial_count: int = Field(..., description="Initial number of VMs")
    final_count: int = Field(..., description="Final number of VMs")
    operation: str = Field(..., description="Scaling operation (scale-out, scale-in, none)")
    new_server_ids: list[str] = Field(
        default_factory=list,
        description="Server IDs of newly created VMs (scale-out)",
    )
    removed_server_ids: list[str] = Field(
        default_factory=list,
        description="Server IDs of removed VMs (scale-in)",
    )
    error: str | None = Field(None, description="Error message if failed")
