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
    description="""
    Create a new infrastructure deployment from a template.

    The deployment is created in PENDING status and returns immediately.
    A background workflow provisions the actual infrastructure asynchronously.

    **Request Body:**
    - `name`: Unique name for the deployment
    - `template`: Infrastructure template (VMs, networks configuration)
    - `parameters`: Optional parameters to override template defaults
    - `cloud_region`: Target cloud region (e.g., "us-west-1", "RegionOne")

    **Response:**
    - Returns the created deployment with status PENDING
    - Use GET /deployments/{id} to poll for status updates
    - Deployment will transition to IN_PROGRESS → COMPLETED (or FAILED)
    """,
    responses={
        202: {
            "description": "Deployment created successfully",
            "content": {
                "application/json": {
                    "example": {
                        "id": "550e8400-e29b-41d4-a716-446655440000",
                        "name": "my-web-app-prod",
                        "status": "PENDING",
                        "template": {
                            "vm_config": {"flavor": "m1.small", "image": "ubuntu-22.04"}
                        },
                        "parameters": {},
                        "cloud_region": "RegionOne",
                        "resources": None,
                        "error": None,
                        "created_at": "2025-01-10T12:00:00Z",
                        "updated_at": "2025-01-10T12:00:00Z",
                    }
                }
            },
        },
        422: {"description": "Validation error - invalid template or parameters"},
    },
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
    description="""
    Retrieve deployment details by ID.

    Returns complete deployment information including:
    - Current status (PENDING, IN_PROGRESS, COMPLETED, FAILED, etc.)
    - Template and parameters
    - Created resource IDs (if deployment completed)
    - Error details (if deployment failed)

    Use this endpoint to poll deployment status after creation.
    """,
    responses={
        200: {"description": "Deployment found"},
        404: {"description": "Deployment not found"},
    },
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
        Query(alias="status", description="Filter by deployment status"),
    ] = None,
    cloud_region: Annotated[str | None, Query(description="Filter by cloud region")] = None,
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
    status_code=status.HTTP_202_ACCEPTED,
    summary="Update deployment",
    description="Update deployment parameters and trigger infrastructure changes",
)
async def update_deployment(
    deployment_id: UUID,
    request: UpdateDeploymentRequest,
    repo: Annotated[DeploymentRepository, Depends(get_deployment_repository)],
) -> DeploymentResponse:
    """
    Update deployment and trigger infrastructure changes.

    This triggers an async workflow to:
    1. Resize VMs if flavor changed
    2. Update network if CIDR changed
    3. Update deployment status

    Args:
        deployment_id: Deployment unique identifier
        request: Update request with new parameters
        repo: Deployment repository

    Returns:
        Updated deployment details

    Raises:
        HTTPException: If deployment not found
    """
    # Get deployment to verify it exists and get current resources
    deployment = await repo.get_by_id(deployment_id)

    if not deployment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Deployment {deployment_id} not found",
        )

    # Update deployment parameters in DB
    update_kwargs = {}
    if request.parameters is not None:
        update_kwargs["parameters"] = request.parameters

    updated_deployment = await repo.update(deployment_id, **update_kwargs)

    # Trigger async workflow to update infrastructure
    # This is non-blocking - the workflow will update the deployment status
    if request.parameters:
        import asyncio

        from orchestrator.workflows.deployment.update import run_update_workflow

        # Extract OpenStack config from settings (simplified for now)
        openstack_config = {
            "auth_url": "http://localhost:5000/v3",  # TODO: Load from settings
            "username": "admin",
            "password": "secret",
            "project_name": "admin",
            "region_name": deployment.cloud_region,
        }

        # Start workflow in background (fire and forget)
        asyncio.create_task(
            run_update_workflow(
                deployment_id=deployment_id,
                cloud_region=deployment.cloud_region,
                current_resources=deployment.resources or {},
                updated_parameters=request.parameters,
                openstack_config=openstack_config,
            )
        )

    return DeploymentResponse.model_validate(updated_deployment)


@router.delete(
    "/{deployment_id}",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Delete deployment",
    description="Delete a deployment and deprovision all infrastructure resources",
)
async def delete_deployment(
    deployment_id: UUID,
    repo: Annotated[DeploymentRepository, Depends(get_deployment_repository)],
) -> None:
    """
    Delete deployment and deprovision infrastructure.

    This triggers an async workflow to:
    1. Delete all VMs
    2. Delete network
    3. Mark deployment as DELETED

    Args:
        deployment_id: Deployment unique identifier
        repo: Deployment repository

    Raises:
        HTTPException: If deployment not found
    """
    # Get deployment to verify it exists and get resources
    deployment = await repo.get_by_id(deployment_id)

    if not deployment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Deployment {deployment_id} not found",
        )

    # Trigger async workflow to deprovision infrastructure
    # This is non-blocking - the workflow will update the deployment status
    # Import asyncio to run workflow in background
    import asyncio

    from orchestrator.workflows.deployment.delete import run_delete_workflow

    # Extract OpenStack config from settings (simplified for now)
    openstack_config = {
        "auth_url": "http://localhost:5000/v3",  # TODO: Load from settings
        "username": "admin",
        "password": "secret",
        "project_name": "admin",
        "region_name": deployment.cloud_region,
    }

    # Start workflow in background (fire and forget)
    asyncio.create_task(
        run_delete_workflow(
            deployment_id=deployment_id,
            cloud_region=deployment.cloud_region,
            resources=deployment.resources or {},
            openstack_config=openstack_config,
        )
    )
