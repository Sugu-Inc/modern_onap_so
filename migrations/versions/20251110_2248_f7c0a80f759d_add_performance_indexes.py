"""add_performance_indexes

Revision ID: f7c0a80f759d
Revises: dc70b626b97d
Create Date: 2025-11-10 22:48:21.447199+00:00

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f7c0a80f759d"
down_revision: Union[str, None] = "dc70b626b97d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Apply schema changes."""
    # Add indexes for commonly queried timestamp fields
    op.create_index(
        op.f("ix_deployments_created_at"),
        "deployments",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_deployments_updated_at"),
        "deployments",
        ["updated_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_deployments_deleted_at"),
        "deployments",
        ["deleted_at"],
        unique=False,
    )

    # Add composite index for common query pattern: filter by status and sort by creation time
    op.create_index(
        op.f("ix_deployments_status_created_at"),
        "deployments",
        ["status", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    """Revert schema changes."""
    # Drop indexes in reverse order
    op.drop_index(op.f("ix_deployments_status_created_at"), table_name="deployments")
    op.drop_index(op.f("ix_deployments_deleted_at"), table_name="deployments")
    op.drop_index(op.f("ix_deployments_updated_at"), table_name="deployments")
    op.drop_index(op.f("ix_deployments_created_at"), table_name="deployments")
