"""
Scaling API request and response schemas.

Defines the data models for scaling operations (scale-out/scale-in).
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, ValidationError, model_validator
from pydantic_core import PydanticCustomError


class ScaleRequest(BaseModel):
    """Request to scale a deployment."""

    target_count: int = Field(
        ...,
        ge=1,
        description="Target number of VMs for the deployment",
    )
    min_count: int = Field(
        default=1,
        ge=1,
        description="Minimum number of VMs to maintain",
    )
    max_count: int | None = Field(
        default=None,
        ge=1,
        description="Maximum number of VMs allowed (optional)",
    )

    @model_validator(mode="after")
    def validate_counts(self) -> "ScaleRequest":
        """Validate count constraints."""
        # Validate target_count >= min_count
        if self.target_count < self.min_count:
            raise PydanticCustomError(
                "value_error",
                "target_count ({target}) cannot be less than min_count ({min})",
                {"target": self.target_count, "min": self.min_count},
            )

        # Validate max_count >= min_count
        if self.max_count is not None and self.max_count < self.min_count:
            raise PydanticCustomError(
                "value_error",
                "max_count ({max}) cannot be less than min_count ({min})",
                {"max": self.max_count, "min": self.min_count},
            )

        return self


class ScaleResponse(BaseModel):
    """Response from a scaling operation."""

    execution_id: UUID = Field(..., description="Unique execution identifier")
    deployment_id: UUID = Field(..., description="Deployment being scaled")
    status: str = Field(..., description="Scaling execution status (running, completed, failed)")
    current_count: int = Field(..., description="Current number of VMs")
    target_count: int = Field(..., description="Target number of VMs")
    operation: str = Field(..., description="Scaling operation (scale-out, scale-in, none)")
    started_at: datetime = Field(..., description="Execution start timestamp")
    completed_at: datetime | None = Field(None, description="Execution completion timestamp")
    error: str | None = Field(None, description="Error message if execution failed")


class ScaleStatus(BaseModel):
    """Status of a scaling operation."""

    execution_id: UUID = Field(..., description="Unique execution identifier")
    deployment_id: UUID = Field(..., description="Deployment being scaled")
    status: str = Field(..., description="Current status")
    progress: dict[str, Any] = Field(
        default_factory=dict,
        description="Progress details (VMs created/deleted)",
    )
    started_at: datetime = Field(..., description="When scaling started")
    completed_at: datetime | None = Field(None, description="When scaling completed")
    error: str | None = Field(None, description="Error message if failed")
