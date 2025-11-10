"""
Integration tests for scaling workflow.

Tests the end-to-end scaling flow with real database.
"""

from unittest.mock import patch
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from orchestrator.db.repositories.deployment_repository import DeploymentRepository
from orchestrator.models.base import Base
from orchestrator.models.deployment import Deployment, DeploymentStatus
from orchestrator.workflows.scaling.scale import run_scale_workflow

pytestmark = pytest.mark.integration


@pytest.fixture
async def db_session():  # type: ignore[no-untyped-def]
    """Create test database session."""
    # Create in-memory SQLite database
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create session factory
    async_session_maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session_maker() as session:
        yield session

    # Cleanup
    await engine.dispose()


class TestScalingFlow:
    """Test end-to-end scaling flow."""

    @pytest.mark.asyncio
    async def test_scale_out_adds_vms(self, db_session: AsyncSession) -> None:
        """Test scale-out operation adds VMs."""
        # Create a completed deployment with 2 VMs
        deployment = Deployment(
            id=uuid4(),
            name="test-deployment",
            status=DeploymentStatus.COMPLETED,
            template={"vm_config": {"flavor": "m1.small", "image": "ubuntu-22.04"}},
            parameters={},
            cloud_region="RegionOne",
            resources={
                "server_ids": ["server-1", "server-2"],
                "network_id": "network-123",
            },
        )

        repo = DeploymentRepository(db_session)
        created_deployment = await repo.create(deployment)
        await db_session.commit()

        # Mock scaling activities
        with (
            patch("orchestrator.workflows.scaling.scale.scale_out_activity") as mock_scale_out,
            patch("orchestrator.workflows.scaling.scale.update_deployment_status_activity") as mock_update_status,
        ):
            # Setup mocks
            mock_scale_out.return_value = {
                "new_server_ids": ["server-3", "server-4"],
                "success": True,
                "error": None,
            }
            mock_update_status.return_value = None

            # Execute scaling workflow (2 → 4 VMs)
            result = await run_scale_workflow(
                deployment_id=created_deployment.id,
                current_count=2,
                target_count=4,
                min_count=1,
                max_count=10,
                resources=created_deployment.resources,
                template=created_deployment.template,
                cloud_region=created_deployment.cloud_region,
            )

            # Verify result
            assert result.success is True
            assert result.operation == "scale-out"
            assert result.initial_count == 2
            assert result.final_count == 4
            assert len(result.new_server_ids) == 2
            assert "server-3" in result.new_server_ids
            assert "server-4" in result.new_server_ids

            # Verify activity was called with correct parameters
            mock_scale_out.assert_called_once()
            call_kwargs = mock_scale_out.call_args[1]
            assert call_kwargs["count_to_add"] == 2
            assert call_kwargs["template"] == created_deployment.template
            assert call_kwargs["cloud_region"] == "RegionOne"

            # Verify status update was called
            mock_update_status.assert_called_once()
            call_kwargs = mock_update_status.call_args[1]
            assert call_kwargs["status"] == DeploymentStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_scale_in_removes_vms(self, db_session: AsyncSession) -> None:
        """Test scale-in operation removes VMs."""
        # Create a completed deployment with 4 VMs
        deployment = Deployment(
            id=uuid4(),
            name="test-deployment",
            status=DeploymentStatus.COMPLETED,
            template={"vm_config": {"flavor": "m1.small"}},
            parameters={},
            cloud_region="RegionOne",
            resources={
                "server_ids": ["server-1", "server-2", "server-3", "server-4"],
                "network_id": "network-123",
            },
        )

        repo = DeploymentRepository(db_session)
        created_deployment = await repo.create(deployment)
        await db_session.commit()

        # Mock scaling activities
        with (
            patch("orchestrator.workflows.scaling.scale.scale_in_activity") as mock_scale_in,
            patch("orchestrator.workflows.scaling.scale.update_deployment_status_activity") as mock_update_status,
        ):
            # Setup mocks
            mock_scale_in.return_value = {
                "removed_server_ids": ["server-3", "server-4"],
                "success": True,
                "error": None,
            }
            mock_update_status.return_value = None

            # Execute scaling workflow (4 → 2 VMs)
            result = await run_scale_workflow(
                deployment_id=created_deployment.id,
                current_count=4,
                target_count=2,
                min_count=1,
                max_count=10,
                resources=created_deployment.resources,
                template=created_deployment.template,
                cloud_region=created_deployment.cloud_region,
            )

            # Verify result
            assert result.success is True
            assert result.operation == "scale-in"
            assert result.initial_count == 4
            assert result.final_count == 2
            assert len(result.removed_server_ids) == 2
            assert "server-3" in result.removed_server_ids
            assert "server-4" in result.removed_server_ids

            # Verify activity was called with correct parameters
            mock_scale_in.assert_called_once()
            call_kwargs = mock_scale_in.call_args[1]
            assert call_kwargs["count_to_remove"] == 2
            assert call_kwargs["min_count"] == 1

            # Verify status update was called
            mock_update_status.assert_called_once()

    @pytest.mark.asyncio
    async def test_scale_respects_min_count(self, db_session: AsyncSession) -> None:
        """Test scaling respects minimum VM count constraint."""
        # Create a completed deployment with 2 VMs
        deployment = Deployment(
            id=uuid4(),
            name="test-deployment",
            status=DeploymentStatus.COMPLETED,
            template={"vm_config": {"flavor": "m1.small"}},
            parameters={},
            cloud_region="RegionOne",
            resources={
                "server_ids": ["server-1", "server-2"],
                "network_id": "network-123",
            },
        )

        repo = DeploymentRepository(db_session)
        created_deployment = await repo.create(deployment)
        await db_session.commit()

        # Try to scale below min_count
        result = await run_scale_workflow(
            deployment_id=created_deployment.id,
            current_count=2,
            target_count=0,
            min_count=1,
            max_count=10,
            resources=created_deployment.resources,
            template=created_deployment.template,
            cloud_region=created_deployment.cloud_region,
        )

        # Verify result - should fail
        assert result.success is False
        assert "below min_count" in result.error.lower()
        assert result.final_count == 2  # Should remain unchanged

    @pytest.mark.asyncio
    async def test_scale_respects_max_count(self, db_session: AsyncSession) -> None:
        """Test scaling respects maximum VM count constraint."""
        # Create a completed deployment with 2 VMs
        deployment = Deployment(
            id=uuid4(),
            name="test-deployment",
            status=DeploymentStatus.COMPLETED,
            template={"vm_config": {"flavor": "m1.small"}},
            parameters={},
            cloud_region="RegionOne",
            resources={
                "server_ids": ["server-1", "server-2"],
                "network_id": "network-123",
            },
        )

        repo = DeploymentRepository(db_session)
        created_deployment = await repo.create(deployment)
        await db_session.commit()

        # Try to scale above max_count
        result = await run_scale_workflow(
            deployment_id=created_deployment.id,
            current_count=2,
            target_count=12,
            min_count=1,
            max_count=10,
            resources=created_deployment.resources,
            template=created_deployment.template,
            cloud_region=created_deployment.cloud_region,
        )

        # Verify result - should fail
        assert result.success is False
        assert "exceeds max_count" in result.error.lower()
        assert result.final_count == 2  # Should remain unchanged

    @pytest.mark.asyncio
    async def test_scale_no_change_needed(self, db_session: AsyncSession) -> None:
        """Test scaling when current count equals target count."""
        # Create a completed deployment with 2 VMs
        deployment = Deployment(
            id=uuid4(),
            name="test-deployment",
            status=DeploymentStatus.COMPLETED,
            template={"vm_config": {"flavor": "m1.small"}},
            parameters={},
            cloud_region="RegionOne",
            resources={
                "server_ids": ["server-1", "server-2"],
                "network_id": "network-123",
            },
        )

        repo = DeploymentRepository(db_session)
        created_deployment = await repo.create(deployment)
        await db_session.commit()

        # Execute scaling with same count
        result = await run_scale_workflow(
            deployment_id=created_deployment.id,
            current_count=2,
            target_count=2,
            min_count=1,
            max_count=10,
            resources=created_deployment.resources,
            template=created_deployment.template,
            cloud_region=created_deployment.cloud_region,
        )

        # Verify result - should succeed with no operation
        assert result.success is True
        assert result.operation == "none"
        assert result.initial_count == 2
        assert result.final_count == 2
        assert result.new_server_ids == []
        assert result.removed_server_ids == []

    @pytest.mark.asyncio
    async def test_scale_out_failure_handling(self, db_session: AsyncSession) -> None:
        """Test scale-out failure handling."""
        # Create a completed deployment
        deployment = Deployment(
            id=uuid4(),
            name="test-deployment",
            status=DeploymentStatus.COMPLETED,
            template={"vm_config": {"flavor": "m1.small"}},
            parameters={},
            cloud_region="RegionOne",
            resources={
                "server_ids": ["server-1"],
                "network_id": "network-123",
            },
        )

        repo = DeploymentRepository(db_session)
        created_deployment = await repo.create(deployment)
        await db_session.commit()

        # Mock scaling activities with failure
        with (
            patch("orchestrator.workflows.scaling.scale.scale_out_activity") as mock_scale_out,
            patch("orchestrator.workflows.scaling.scale.update_deployment_status_activity") as mock_update_status,
        ):
            # Setup mocks - scale_out fails
            mock_scale_out.return_value = {
                "new_server_ids": [],
                "success": False,
                "error": "OpenStack API error: quota exceeded",
            }
            mock_update_status.return_value = None

            # Execute scaling workflow
            result = await run_scale_workflow(
                deployment_id=created_deployment.id,
                current_count=1,
                target_count=5,
                min_count=1,
                max_count=10,
                resources=created_deployment.resources,
                template=created_deployment.template,
                cloud_region=created_deployment.cloud_region,
            )

            # Verify result
            assert result.success is False
            assert "quota exceeded" in result.error.lower()

            # Verify status update was called with FAILED status
            mock_update_status.assert_called_once()
            call_kwargs = mock_update_status.call_args[1]
            assert call_kwargs["status"] == DeploymentStatus.FAILED
            assert "error" in call_kwargs
