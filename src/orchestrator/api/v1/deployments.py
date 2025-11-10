"""
Deployment API endpoints.

Provides REST API for managing infrastructure deployments.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator.db.connection import get_db
from orchestrator.db.repositories.deployment_repository import DeploymentRepository
from orchestrator.models.deployment import Deployment, DeploymentStatus
from orchestrator.schemas.deployment import (
    CreateDeploymentRequest,
    DeploymentListResponse,
    DeploymentResponse,
    UpdateDeploymentRequest,
)

router = APIRouter(prefix="/v1/deployments", tags=["deployments"])


def get_deployment_repository(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DeploymentRepository:
    """Dependency for deployment repository."""
    return DeploymentRepository(db)


@router.post(
    "",
    response_model=DeploymentResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Create deployment",
    description="Create a new infrastructure deployment from a template",
)
async def create_deployment(
    request: CreateDeploymentRequest,
    repo: Annotated[DeploymentRepository, Depends(get_deployment_repository)],
) -> DeploymentResponse:
    """
    Create a new deployment.

    Args:
        request: Deployment creation request
        repo: Deployment repository

    Returns:
        Created deployment details

    Raises:
        HTTPException: If deployment creation fails
    """
    # Create deployment in PENDING status
    deployment = Deployment(
        name=request.name,
        status=DeploymentStatus.PENDING,
        template=request.template,
        parameters=request.parameters,
        cloud_region=request.cloud_region,
    )

    created_deployment = await repo.create(deployment)

    # TODO: Trigger async workflow to provision infrastructure
    # await workflow_client.start_deployment_workflow(created_deployment.id)

    return DeploymentResponse.model_validate(created_deployment)


@router.get(
    "/{deployment_id}",
    response_model=DeploymentResponse,
    summary="Get deployment",
    description="Get deployment details by ID",
)
async def get_deployment(
    deployment_id: UUID,
    repo: Annotated[DeploymentRepository, Depends(get_deployment_repository)],
) -> DeploymentResponse:
    """
    Get deployment by ID.

    Args:
        deployment_id: Deployment unique identifier
        repo: Deployment repository

    Returns:
        Deployment details

    Raises:
        HTTPException: If deployment not found
    """
    deployment = await repo.get_by_id(deployment_id)

    if not deployment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Deployment {deployment_id} not found",
        )

    return DeploymentResponse.model_validate(deployment)


@router.get(
    "",
    response_model=DeploymentListResponse,
    summary="List deployments",
    description="List deployments with optional filtering and pagination",
)
async def list_deployments(
    repo: Annotated[DeploymentRepository, Depends(get_deployment_repository)],
    status_filter: Annotated[
        DeploymentStatus | None,
        Query(
            alias="status", description="Filter by deployment status"
        ),
    ] = None,
    cloud_region: Annotated[
        str | None, Query(description="Filter by cloud region")
    ] = None,
    limit: Annotated[int, Query(ge=1, le=1000, description="Page size")] = 100,
    offset: Annotated[int, Query(ge=0, description="Page offset")] = 0,
) -> DeploymentListResponse:
    """
    List deployments with filtering and pagination.

    Args:
        repo: Deployment repository
        status_filter: Optional status filter
        cloud_region: Optional cloud region filter
        limit: Maximum number of results
        offset: Number of results to skip

    Returns:
        Paginated list of deployments
    """
    # Get deployments and total count
    deployments = await repo.list(
        status=status_filter,
        cloud_region=cloud_region,
        limit=limit,
        offset=offset,
    )

    total = await repo.count(
        status=status_filter,
        cloud_region=cloud_region,
    )

    # Convert to response schemas
    items = [DeploymentResponse.model_validate(d) for d in deployments]

    return DeploymentListResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.patch(
    "/{deployment_id}",
    response_model=DeploymentResponse,
    summary="Update deployment",
    description="Update deployment parameters or resources",
)
async def update_deployment(
    deployment_id: UUID,
    request: UpdateDeploymentRequest,
    repo: Annotated[DeploymentRepository, Depends(get_deployment_repository)],
) -> DeploymentResponse:
    """
    Update deployment.

    Args:
        deployment_id: Deployment unique identifier
        request: Update request
        repo: Deployment repository

    Returns:
        Updated deployment details

    Raises:
        HTTPException: If deployment not found
    """
    # Build update kwargs
    update_kwargs = {}
    if request.parameters is not None:
        update_kwargs["parameters"] = request.parameters
    if request.resources is not None:
        update_kwargs["resources"] = request.resources

    # Update deployment
    updated_deployment = await repo.update(deployment_id, **update_kwargs)

    if not updated_deployment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Deployment {deployment_id} not found",
        )

    return DeploymentResponse.model_validate(updated_deployment)


@router.delete(
    "/{deployment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete deployment",
    description="Soft delete a deployment (marks as deleted)",
)
async def delete_deployment(
    deployment_id: UUID,
    repo: Annotated[DeploymentRepository, Depends(get_deployment_repository)],
) -> None:
    """
    Delete deployment (soft delete).

    Args:
        deployment_id: Deployment unique identifier
        repo: Deployment repository

    Raises:
        HTTPException: If deployment not found
    """
    # TODO: Trigger async workflow to deprovision infrastructure
    # await workflow_client.start_delete_workflow(deployment_id)

    success = await repo.delete(deployment_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Deployment {deployment_id} not found",
        )
