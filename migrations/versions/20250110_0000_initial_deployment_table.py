"""Initial deployment table

Revision ID: 001_initial
Revises:
Create Date: 2025-01-10 00:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Apply schema changes."""
    op.create_table(
        'deployments',
        sa.Column('id', sa.String(36), primary_key=True, nullable=False),
        sa.Column('name', sa.String(255), nullable=False, index=True),
        sa.Column(
            'status',
            sa.Enum(
                'PENDING',
                'IN_PROGRESS',
                'COMPLETED',
                'FAILED',
                'DELETING',
                'DELETED',
                name='deploymentstatus'
            ),
            nullable=False,
            index=True
        ),
        sa.Column('template', sa.JSON(), nullable=False),
        sa.Column('parameters', sa.JSON(), nullable=False),
        sa.Column('cloud_region', sa.String(100), nullable=False, index=True),
        sa.Column('resources', sa.JSON(), nullable=True),
        sa.Column('error', sa.JSON(), nullable=True),
        sa.Column('extra_metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    )

    # Create indexes for common queries
    op.create_index('ix_deployments_name', 'deployments', ['name'])
    op.create_index('ix_deployments_status', 'deployments', ['status'])
    op.create_index('ix_deployments_cloud_region', 'deployments', ['cloud_region'])
    op.create_index('ix_deployments_created_at', 'deployments', ['created_at'])


def downgrade() -> None:
    """Revert schema changes."""
    op.drop_index('ix_deployments_created_at', table_name='deployments')
    op.drop_index('ix_deployments_cloud_region', table_name='deployments')
    op.drop_index('ix_deployments_status', table_name='deployments')
    op.drop_index('ix_deployments_name', table_name='deployments')
    op.drop_table('deployments')
