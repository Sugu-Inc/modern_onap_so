"""
Configuration API endpoints.

Provides REST API for configuring deployed infrastructure using Ansible.
"""

import asyncio
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator.clients.ansible.client import PlaybookStatus
from orchestrator.db.connection import get_db
from orchestrator.db.repositories.deployment_repository import DeploymentRepository
from orchestrator.models.deployment import DeploymentStatus
from orchestrator.schemas.configuration import ConfigurationRequest, ConfigurationResponse

router = APIRouter(prefix="/v1/deployments", tags=["configurations"])


def get_deployment_repository(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DeploymentRepository:
    """Dependency for deployment repository."""
    return DeploymentRepository(db)


async def run_configure_workflow(
    deployment_id: UUID,
    playbook_path: str,
    extra_vars: dict,
    limit: str | None = None,
    ssh_private_key: str | None = None,
) -> UUID:
    """
    Run configuration workflow asynchronously.

    This is a placeholder that will be replaced with actual workflow implementation.

    Args:
        deployment_id: Deployment to configure
        playbook_path: Path to Ansible playbook
        extra_vars: Extra variables for playbook
        limit: Limit to specific hosts
        ssh_private_key: SSH private key for authentication

    Returns:
        Execution ID
    """
    # TODO: Replace with actual ConfigureWorkflow implementation (T108-T111)
    execution_id = uuid4()
    return execution_id


@router.post(
    "/{deployment_id}/configure",
    response_model=ConfigurationResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Configure deployment",
    description="Configure a deployed infrastructure using Ansible playbooks",
)
async def configure_deployment(
    deployment_id: UUID,
    request: ConfigurationRequest,
    repo: Annotated[DeploymentRepository, Depends(get_deployment_repository)],
) -> ConfigurationResponse:
    """
    Configure a deployment using Ansible.

    Args:
        deployment_id: Deployment ID to configure
        request: Configuration request with playbook details
        repo: Deployment repository

    Returns:
        Configuration execution details

    Raises:
        HTTPException: If deployment not found or cannot be configured
    """
    # Get deployment
    deployment = await repo.get_by_id(deployment_id)
    if not deployment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Deployment {deployment_id} not found",
        )

    # Check deployment is in COMPLETED state
    if deployment.status != DeploymentStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Deployment {deployment_id} cannot be configured. "
            f"Current status: {deployment.status}. "
            "Only COMPLETED deployments can be configured.",
        )

    # Generate execution ID
    execution_id = uuid4()
    started_at = datetime.now(UTC)

    # Trigger configuration workflow asynchronously
    asyncio.create_task(
        run_configure_workflow(
            deployment_id=deployment_id,
            playbook_path=request.playbook_path,
            extra_vars=request.extra_vars,
            limit=request.limit,
            ssh_private_key=request.ssh_private_key,
        )
    )

    # Return immediate response
    return ConfigurationResponse(
        execution_id=execution_id,
        deployment_id=deployment_id,
        status=PlaybookStatus.RUNNING,
        playbook_path=request.playbook_path,
        extra_vars=request.extra_vars,
        started_at=started_at,
        completed_at=None,
        return_code=None,
        stats={},
        error=None,
    )
