"""
Repository for deployment database operations.

Provides CRUD operations for Deployment model.
"""

from typing import Any
from uuid import UUID

from sqlalchemy import select, func, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator.models.deployment import Deployment, DeploymentStatus


class DeploymentRepository:
    """Repository for deployment database operations."""

    def __init__(self, session: AsyncSession) -> None:
        """
        Initialize repository with database session.

        Args:
            session: AsyncSession for database operations
        """
        self.session = session

    async def create(self, deployment: Deployment) -> Deployment:
        """
        Create a new deployment.

        Args:
            deployment: Deployment instance to create

        Returns:
            Created deployment with ID and timestamps
        """
        self.session.add(deployment)
        await self.session.flush()
        await self.session.refresh(deployment)
        return deployment

    async def get_by_id(self, deployment_id: UUID) -> Deployment | None:
        """
        Get deployment by ID.

        Args:
            deployment_id: UUID of the deployment

        Returns:
            Deployment if found, None otherwise
        """
        result = await self.session.execute(
            select(Deployment).where(Deployment.id == deployment_id)
        )
        return result.scalar_one_or_none()

    async def get_by_name(self, name: str) -> Deployment | None:
        """
        Get deployment by name.

        Args:
            name: Name of the deployment

        Returns:
            Deployment if found, None otherwise
        """
        result = await self.session.execute(
            select(Deployment).where(Deployment.name == name)
        )
        return result.scalar_one_or_none()

    async def list(
        self,
        status: DeploymentStatus | None = None,
        cloud_region: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Deployment]:
        """
        List deployments with optional filtering.

        Args:
            status: Filter by deployment status
            cloud_region: Filter by cloud region
            limit: Maximum number of results (default 100)
            offset: Number of results to skip (default 0)

        Returns:
            List of deployments
        """
        query = select(Deployment)

        # Apply filters
        if status is not None:
            query = query.where(Deployment.status == status)
        if cloud_region is not None:
            query = query.where(Deployment.cloud_region == cloud_region)

        # Apply pagination
        query = query.limit(limit).offset(offset)

        # Order by created_at descending (newest first)
        query = query.order_by(Deployment.created_at.desc())

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def count(
        self,
        status: DeploymentStatus | None = None,
        cloud_region: str | None = None,
    ) -> int:
        """
        Count deployments with optional filtering.

        Args:
            status: Filter by deployment status
            cloud_region: Filter by cloud region

        Returns:
            Number of deployments matching criteria
        """
        query = select(func.count(Deployment.id))

        # Apply filters
        if status is not None:
            query = query.where(Deployment.status == status)
        if cloud_region is not None:
            query = query.where(Deployment.cloud_region == cloud_region)

        result = await self.session.execute(query)
        return result.scalar_one()

    async def update(self, deployment_id: UUID, **kwargs: Any) -> Deployment | None:
        """
        Update deployment fields.

        Args:
            deployment_id: UUID of the deployment
            **kwargs: Fields to update

        Returns:
            Updated deployment if found, None otherwise
        """
        # First check if deployment exists
        deployment = await self.get_by_id(deployment_id)
        if deployment is None:
            return None

        # Update fields
        for key, value in kwargs.items():
            if hasattr(deployment, key):
                setattr(deployment, key, value)

        await self.session.flush()
        await self.session.refresh(deployment)
        return deployment

    async def delete(self, deployment_id: UUID) -> bool:
        """
        Delete deployment (soft delete by setting deleted_at).

        Args:
            deployment_id: UUID of the deployment

        Returns:
            True if deleted, False if not found
        """
        deployment = await self.get_by_id(deployment_id)
        if deployment is None:
            return False

        # Soft delete
        from datetime import datetime, timezone

        deployment.status = DeploymentStatus.DELETED
        deployment.deleted_at = datetime.now(timezone.utc)
        await self.session.flush()
        return True

    async def hard_delete(self, deployment_id: UUID) -> bool:
        """
        Permanently delete deployment from database.

        Args:
            deployment_id: UUID of the deployment

        Returns:
            True if deleted, False if not found
        """
        result = await self.session.execute(
            delete(Deployment).where(Deployment.id == deployment_id)
        )
        return result.rowcount > 0

    async def exists(self, deployment_id: UUID) -> bool:
        """
        Check if deployment exists.

        Args:
            deployment_id: UUID of the deployment

        Returns:
            True if exists, False otherwise
        """
        result = await self.session.execute(
            select(func.count(Deployment.id)).where(Deployment.id == deployment_id)
        )
        return result.scalar_one() > 0
