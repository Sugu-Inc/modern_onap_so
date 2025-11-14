"""
DeploymentTemplate model for infrastructure deployment templates.

Defines reusable templates for deploying infrastructure resources.
"""

from typing import Any

from sqlalchemy import JSON, Boolean, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from orchestrator.models.base import BaseModel


class DeploymentTemplate(BaseModel):
    """
    Template for infrastructure deployments.

    Defines the configuration for VMs, networks, and other resources
    that can be deployed. Templates are versioned and can be activated
    or deactivated.
    """

    __tablename__ = "deployment_templates"

    # Template identification
    name: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    # Configuration
    vm_config: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, comment="VM/compute resource configuration"
    )
    network_config: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, comment="Network configuration"
    )

    # Optional metadata (named 'extra_metadata' to avoid SQLAlchemy reserved name)
    extra_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, nullable=True, comment="Additional metadata"
    )

    # Version tracking
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, comment="Template version"
    )

    # Lifecycle management
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, comment="Whether template is active"
    )

    def __repr__(self) -> str:
        """Return string representation of template."""
        return (
            f"<DeploymentTemplate(id={self.id}, name='{self.name}', "
            f"version={self.version}, is_active={self.is_active})>"
        )
