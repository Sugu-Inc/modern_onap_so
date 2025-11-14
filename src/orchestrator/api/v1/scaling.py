"""
Scaling API endpoints.

Handles scale-out and scale-in operations for deployments.
"""

import asyncio
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator.db.connection import get_db
from orchestrator.db.repositories.deployment_repository import DeploymentRepository
from orchestrator.models.deployment import DeploymentStatus
from orchestrator.schemas.scaling import ScaleRequest, ScaleResponse

router = APIRouter(prefix="/v1/deployments", tags=["scaling"])


def get_deployment_repository(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DeploymentRepository:
    """Dependency for deployment repository."""
    return DeploymentRepository(db)


async def run_scale_workflow(
    deployment_id: UUID,
    current_count: int,
    target_count: int,
    min_count: int,
    max_count: int | None,
) -> UUID:
    """
    Run scaling workflow asynchronously.

    Args:
        deployment_id: Deployment to scale
        current_count: Current number of VMs
        target_count: Target number of VMs
        min_count: Minimum number of VMs
        max_count: Maximum number of VMs (optional)

    Returns:
        Execution ID
    """
    # TODO: Implement actual workflow execution
    # This is a placeholder that will be replaced with real workflow
    await asyncio.sleep(0.1)  # Simulate async work
    return uuid4()


@router.post("/{deployment_id}/scale", response_model=ScaleResponse, status_code=status.HTTP_202_ACCEPTED)
async def scale_deployment(
    deployment_id: UUID,
    scale_request: ScaleRequest,
    repo: Annotated[DeploymentRepository, Depends(get_deployment_repository)],
) -> ScaleResponse:
    """
    Scale a deployment up or down.

    Triggers a scaling workflow to add or remove VMs from the deployment.

    Args:
        deployment_id: Deployment to scale
        scale_request: Scaling parameters
        repo: Deployment repository

    Returns:
        ScaleResponse with execution details

    Raises:
        HTTPException: If deployment not found or invalid state
    """
    # Get deployment
    deployment = await repo.get_by_id(deployment_id)
    if not deployment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Deployment {deployment_id} not found",
        )

    # Validate deployment state
    if deployment.status != DeploymentStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Deployment {deployment_id} (status: {deployment.status}) cannot be scaled. Must be in COMPLETED state.",
        )

    # Get current VM count
    server_ids = deployment.resources.get("server_ids", []) if deployment.resources else []
    current_count = len(server_ids)

    # Validate max_count constraint
    if scale_request.max_count is not None and scale_request.target_count > scale_request.max_count:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Target count ({scale_request.target_count}) exceeds max_count ({scale_request.max_count})",
        )

    # Determine operation type
    if scale_request.target_count > current_count:
        operation = "scale-out"
    elif scale_request.target_count < current_count:
        operation = "scale-in"
    else:
        operation = "none"

    # Trigger scaling workflow asynchronously
    execution_id = await run_scale_workflow(
        deployment_id=deployment_id,
        current_count=current_count,
        target_count=scale_request.target_count,
        min_count=scale_request.min_count,
        max_count=scale_request.max_count,
    )

    # Return response
    return ScaleResponse(
        execution_id=execution_id,
        deployment_id=deployment_id,
        status="running",
        current_count=current_count,
        target_count=scale_request.target_count,
        operation=operation,
        started_at=datetime.now(UTC),
        completed_at=None,
        error=None,
    )
