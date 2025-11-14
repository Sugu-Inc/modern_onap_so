"""
DeploymentService for managing deployment lifecycle.

This service layer coordinates between the API, repository, and workflows.
"""

from typing import Any
from uuid import UUID

from orchestrator.db.repositories.deployment_repository import DeploymentRepository
from orchestrator.logging import logger
from orchestrator.models.deployment import Deployment, DeploymentStatus
from orchestrator.schemas.deployment import (
    CreateDeploymentRequest,
    DeploymentResponse,
)


class DeploymentService:
    """
    Service for managing deployments.

    Handles business logic and coordinates between repository and workflows.
    """

    def __init__(
        self, repository: DeploymentRepository, workflow_client: object | None = None
    ) -> None:
        """
        Initialize deployment service.

        Args:
            repository: Deployment repository for database operations
            workflow_client: Temporal workflow client (optional, for testing)
        """
        self.repository = repository
        self.workflow_client = workflow_client

    async def create_deployment(self, request: CreateDeploymentRequest) -> DeploymentResponse:
        """
        Create a new deployment.

        Args:
            request: Deployment creation request

        Returns:
            Created deployment response

        Raises:
            ValueError: If template is empty or invalid
        """
        # Validate template
        if not request.template:
            raise ValueError("Template cannot be empty")

        # Create deployment in PENDING status
        deployment = Deployment(
            name=request.name,
            status=DeploymentStatus.PENDING,
            template=request.template,
            parameters=request.parameters,
            cloud_region=request.cloud_region,
        )

        # Save to database
        created_deployment = await self.repository.create(deployment)

        logger.info(
            "deployment_created",
            deployment_id=str(created_deployment.id),
            name=created_deployment.name,
            cloud_region=created_deployment.cloud_region,
        )

        # Trigger async workflow (non-blocking)
        if self.workflow_client:
            try:
                await self.workflow_client.start_deployment_workflow(  # type: ignore[attr-defined]
                    created_deployment.id
                )
                logger.info(
                    "deployment_workflow_triggered",
                    deployment_id=str(created_deployment.id),
                )
            except Exception as e:
                logger.error(
                    "deployment_workflow_trigger_failed",
                    deployment_id=str(created_deployment.id),
                    error=str(e),
                )
                # Don't fail the request - deployment is created,
                # workflow can be retried later

        return DeploymentResponse.model_validate(created_deployment)

    async def get_deployment(self, deployment_id: UUID) -> DeploymentResponse | None:
        """
        Get deployment by ID.

        Args:
            deployment_id: Deployment unique identifier

        Returns:
            Deployment response or None if not found
        """
        deployment = await self.repository.get_by_id(deployment_id)

        if not deployment:
            return None

        return DeploymentResponse.model_validate(deployment)

    async def list_deployments(
        self,
        status: DeploymentStatus | None = None,
        cloud_region: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[DeploymentResponse], int]:
        """
        List deployments with optional filtering.

        Args:
            status: Filter by deployment status
            cloud_region: Filter by cloud region
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            Tuple of (deployment list, total count)
        """
        # Get deployments and count
        deployments = await self.repository.list(
            status=status, cloud_region=cloud_region, limit=limit, offset=offset
        )

        total = await self.repository.count(status=status, cloud_region=cloud_region)

        # Convert to response schemas
        deployment_responses = [DeploymentResponse.model_validate(d) for d in deployments]

        return deployment_responses, total

    async def update_deployment(
        self, deployment_id: UUID, **kwargs: Any
    ) -> DeploymentResponse | None:
        """
        Update deployment.

        Args:
            deployment_id: Deployment unique identifier
            **kwargs: Fields to update

        Returns:
            Updated deployment response or None if not found
        """
        updated_deployment = await self.repository.update(deployment_id, **kwargs)

        if not updated_deployment:
            return None

        logger.info(
            "deployment_updated",
            deployment_id=str(deployment_id),
            updates=list(kwargs.keys()),
        )

        return DeploymentResponse.model_validate(updated_deployment)

    async def delete_deployment(self, deployment_id: UUID) -> bool:
        """
        Delete deployment (soft delete).

        Args:
            deployment_id: Deployment unique identifier

        Returns:
            True if deleted, False if not found
        """
        result = await self.repository.delete(deployment_id)

        if result:
            logger.info("deployment_deleted", deployment_id=str(deployment_id))

        return result
