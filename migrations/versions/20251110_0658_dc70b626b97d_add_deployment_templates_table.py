"""add_deployment_templates_table

Revision ID: dc70b626b97d
Revises: 001_initial
Create Date: 2025-11-10 06:58:28.426041+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'dc70b626b97d'
down_revision: Union[str, None] = '001_initial'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Apply schema changes."""
    op.create_table(
        "deployment_templates",
        # Base model columns (from BaseModel)
        sa.Column("id", sa.UUID, primary_key=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            onupdate=sa.text("now()"),
            nullable=False,
        ),
        # Template-specific columns
        sa.Column("name", sa.Text, nullable=False, index=True, comment="Template name"),
        sa.Column(
            "description", sa.Text, nullable=False, comment="Template description"
        ),
        sa.Column(
            "vm_config",
            sa.JSON,
            nullable=False,
            comment="VM/compute resource configuration",
        ),
        sa.Column(
            "network_config", sa.JSON, nullable=False, comment="Network configuration"
        ),
        sa.Column(
            "extra_metadata", sa.JSON, nullable=True, comment="Additional metadata"
        ),
        sa.Column(
            "version",
            sa.Integer,
            nullable=False,
            server_default="1",
            comment="Template version",
        ),
        sa.Column(
            "is_active",
            sa.Boolean,
            nullable=False,
            server_default="true",
            comment="Whether template is active",
        ),
    )

    # Create index on name for faster lookups
    op.create_index("ix_deployment_templates_name", "deployment_templates", ["name"])

    # Create composite index on name and version for versioned lookups
    op.create_index(
        "ix_deployment_templates_name_version",
        "deployment_templates",
        ["name", "version"],
        unique=True,
    )


def downgrade() -> None:
    """Revert schema changes."""
    op.drop_index("ix_deployment_templates_name_version", table_name="deployment_templates")
    op.drop_index("ix_deployment_templates_name", table_name="deployment_templates")
    op.drop_table("deployment_templates")
