"""
Workflow data models for deployment orchestration.

These models define the data structures passed between workflow activities.
"""

from uuid import UUID

from pydantic import BaseModel, Field


class DeploymentWorkflowInput(BaseModel):
    """Input for deployment workflow."""

    deployment_id: UUID = Field(..., description="Deployment ID to process")
    cloud_region: str = Field(..., description="Target cloud region")
    template: dict = Field(..., description="Deployment template")
    parameters: dict = Field(default_factory=dict, description="Deployment parameters")


class NetworkCreationResult(BaseModel):
    """Result of network creation activity."""

    network_id: str = Field(..., description="Created network ID")
    subnet_id: str = Field(..., description="Created subnet ID")
    network_name: str = Field(..., description="Network name")
    subnet_cidr: str = Field(..., description="Subnet CIDR")


class VMCreationResult(BaseModel):
    """Result of VM creation activity."""

    server_id: str = Field(..., description="Created server ID")
    server_name: str = Field(..., description="Server name")
    status: str = Field(..., description="Initial server status")


class VMStatusResult(BaseModel):
    """Result of VM status polling activity."""

    server_id: str = Field(..., description="Server ID")
    status: str = Field(..., description="Current server status")
    is_ready: bool = Field(..., description="Whether server is ready")
    ip_address: str | None = Field(None, description="Server IP address if available")


class DeploymentWorkflowResult(BaseModel):
    """Final result of deployment workflow."""

    deployment_id: UUID = Field(..., description="Deployment ID")
    success: bool = Field(..., description="Whether deployment succeeded")
    network_id: str | None = Field(None, description="Created network ID")
    subnet_id: str | None = Field(None, description="Created subnet ID")
    server_ids: list[str] = Field(
        default_factory=list, description="Created server IDs"
    )
    error: str | None = Field(None, description="Error message if failed")


class RollbackInput(BaseModel):
    """Input for rollback operations."""

    deployment_id: UUID = Field(..., description="Deployment ID")
    network_id: str | None = Field(None, description="Network ID to delete")
    subnet_id: str | None = Field(None, description="Subnet ID to delete")
    server_ids: list[str] = Field(
        default_factory=list, description="Server IDs to delete"
    )
    reason: str = Field(..., description="Reason for rollback")


class DeleteWorkflowInput(BaseModel):
    """Input for delete deployment workflow."""

    deployment_id: UUID = Field(..., description="Deployment ID to delete")
    cloud_region: str = Field(..., description="Cloud region")
    resources: dict = Field(default_factory=dict, description="Resources to delete")


class DeleteWorkflowResult(BaseModel):
    """Result of delete deployment workflow."""

    deployment_id: UUID = Field(..., description="Deployment ID")
    success: bool = Field(..., description="Whether deletion succeeded")
    error: str | None = Field(None, description="Error message if failed")


class UpdateWorkflowInput(BaseModel):
    """Input for update deployment workflow."""

    deployment_id: UUID = Field(..., description="Deployment ID to update")
    cloud_region: str = Field(..., description="Cloud region")
    current_resources: dict = Field(
        default_factory=dict, description="Current deployed resources"
    )
    updated_parameters: dict = Field(
        default_factory=dict, description="Parameters to update"
    )


class UpdateWorkflowResult(BaseModel):
    """Result of update deployment workflow."""

    deployment_id: UUID = Field(..., description="Deployment ID")
    success: bool = Field(..., description="Whether update succeeded")
    updated_resources: dict = Field(
        default_factory=dict, description="Updated resource information"
    )
    error: str | None = Field(None, description="Error message if failed")


