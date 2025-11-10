"""
Deployment model for tracking infrastructure deployments.
"""

import enum
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import JSON, DateTime, Enum, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from orchestrator.models.base import BaseModel


class DeploymentStatus(str, enum.Enum):
    """Status of a deployment."""

    PENDING = "PENDING"  # Created, workflow not started
    IN_PROGRESS = "IN_PROGRESS"  # Workflow executing
    COMPLETED = "COMPLETED"  # Successfully deployed
    FAILED = "FAILED"  # Deployment failed
    DELETING = "DELETING"  # Teardown in progress
    DELETED = "DELETED"  # Successfully deleted


class Deployment(BaseModel):
    """
    Deployment model for tracking infrastructure deployments.

    Tracks the state of infrastructure deployed on cloud providers.
    """

    __tablename__ = "deployments"

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )

    status: Mapped[DeploymentStatus] = mapped_column(
        Enum(DeploymentStatus),
        nullable=False,
        default=DeploymentStatus.PENDING,
        index=True,
    )

    template: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        doc="Deployment template (VMs, networks configuration)",
    )

    parameters: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
        doc="User-provided parameters",
    )

    cloud_region: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        doc="Cloud region identifier",
    )

    resources: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
        doc="Created resource IDs (VMs, networks, etc.)",
    )

    error: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
        doc="Error details if deployment failed",
    )

    extra_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
        doc="Additional metadata (configuration status, scaling history, etc.)",
    )

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Timestamp when deployment was deleted",
    )

    def __repr__(self) -> str:
        """String representation of the deployment."""
        return (
            f"<Deployment(id={self.id}, name={self.name}, "
            f"status={self.status}, cloud_region={self.cloud_region})>"
        )

    @property
    def is_active(self) -> bool:
        """Check if deployment is in an active state."""
        return self.status in (
            DeploymentStatus.PENDING,
            DeploymentStatus.IN_PROGRESS,
            DeploymentStatus.COMPLETED,
        )

    @property
    def is_terminal(self) -> bool:
        """Check if deployment is in a terminal state."""
        return self.status in (
            DeploymentStatus.COMPLETED,
            DeploymentStatus.FAILED,
            DeploymentStatus.DELETED,
        )

    @property
    def is_deletable(self) -> bool:
        """Check if deployment can be deleted."""
        return self.status in (
            DeploymentStatus.COMPLETED,
            DeploymentStatus.FAILED,
        )
