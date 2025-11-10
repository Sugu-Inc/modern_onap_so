"""Integration tests for DeploymentRepository.

These tests require a database and are marked as integration tests.
Run with: pytest -m integration
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from orchestrator.db.repositories.deployment_repository import DeploymentRepository
from orchestrator.models.base import Base
from orchestrator.models.deployment import Deployment, DeploymentStatus

pytestmark = pytest.mark.integration


@pytest.fixture
async def async_session() -> AsyncSession:
    """Create an async database session for testing."""
    # Use SQLite in-memory database for testing
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create session factory
    async_session_factory = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    # Yield session
    async with async_session_factory() as session:
        yield session

    # Cleanup
    await engine.dispose()


@pytest.fixture
def deployment_repository(async_session: AsyncSession) -> DeploymentRepository:
    """Create a deployment repository for testing."""
    return DeploymentRepository(async_session)


class TestDeploymentRepository:
    """Test suite for DeploymentRepository."""

    async def test_create_deployment(
        self,
        deployment_repository: DeploymentRepository,
        async_session: AsyncSession,
    ) -> None:
        """Test creating a deployment."""
        deployment = Deployment(
            name="test-deployment",
            status=DeploymentStatus.PENDING,
            template={"vm_config": {}},
            parameters={"count": 2},
            cloud_region="us-west-1",
        )

        created = await deployment_repository.create(deployment)
        await async_session.commit()

        assert created.id is not None
        assert created.name == "test-deployment"
        assert created.status == DeploymentStatus.PENDING
        assert created.created_at is not None
        assert created.updated_at is not None

    async def test_get_by_id(
        self,
        deployment_repository: DeploymentRepository,
        async_session: AsyncSession,
    ) -> None:
        """Test getting deployment by ID."""
        # Create deployment
        deployment = Deployment(
            name="test",
            template={},
            parameters={},
            cloud_region="region",
        )
        created = await deployment_repository.create(deployment)
        await async_session.commit()

        # Get by ID
        found = await deployment_repository.get_by_id(created.id)
        assert found is not None
        assert found.id == created.id
        assert found.name == "test"

    async def test_get_by_id_not_found(
        self, deployment_repository: DeploymentRepository
    ) -> None:
        """Test getting deployment by ID when not found."""
        result = await deployment_repository.get_by_id(uuid4())
        assert result is None

    async def test_get_by_name(
        self,
        deployment_repository: DeploymentRepository,
        async_session: AsyncSession,
    ) -> None:
        """Test getting deployment by name."""
        # Create deployment
        deployment = Deployment(
            name="unique-name",
            template={},
            parameters={},
            cloud_region="region",
        )
        await deployment_repository.create(deployment)
        await async_session.commit()

        # Get by name
        found = await deployment_repository.get_by_name("unique-name")
        assert found is not None
        assert found.name == "unique-name"

    async def test_get_by_name_not_found(
        self, deployment_repository: DeploymentRepository
    ) -> None:
        """Test getting deployment by name when not found."""
        result = await deployment_repository.get_by_name("nonexistent")
        assert result is None

    async def test_list_deployments(
        self,
        deployment_repository: DeploymentRepository,
        async_session: AsyncSession,
    ) -> None:
        """Test listing deployments."""
        # Create multiple deployments
        for i in range(5):
            deployment = Deployment(
                name=f"deployment-{i}",
                template={},
                parameters={},
                cloud_region="us-west-1",
            )
            await deployment_repository.create(deployment)
        await async_session.commit()

        # List all
        deployments = await deployment_repository.list()
        assert len(deployments) == 5

    async def test_list_with_status_filter(
        self,
        deployment_repository: DeploymentRepository,
        async_session: AsyncSession,
    ) -> None:
        """Test listing deployments with status filter."""
        # Create deployments with different statuses
        deployment1 = Deployment(
            name="pending",
            status=DeploymentStatus.PENDING,
            template={},
            parameters={},
            cloud_region="region",
        )
        deployment2 = Deployment(
            name="completed",
            status=DeploymentStatus.COMPLETED,
            template={},
            parameters={},
            cloud_region="region",
        )
        await deployment_repository.create(deployment1)
        await deployment_repository.create(deployment2)
        await async_session.commit()

        # Filter by COMPLETED
        completed = await deployment_repository.list(status=DeploymentStatus.COMPLETED)
        assert len(completed) == 1
        assert completed[0].status == DeploymentStatus.COMPLETED

    async def test_list_with_region_filter(
        self,
        deployment_repository: DeploymentRepository,
        async_session: AsyncSession,
    ) -> None:
        """Test listing deployments with region filter."""
        # Create deployments in different regions
        deployment1 = Deployment(
            name="us-west",
            template={},
            parameters={},
            cloud_region="us-west-1",
        )
        deployment2 = Deployment(
            name="us-east",
            template={},
            parameters={},
            cloud_region="us-east-1",
        )
        await deployment_repository.create(deployment1)
        await deployment_repository.create(deployment2)
        await async_session.commit()

        # Filter by region
        us_west = await deployment_repository.list(cloud_region="us-west-1")
        assert len(us_west) == 1
        assert us_west[0].cloud_region == "us-west-1"

    async def test_list_with_pagination(
        self,
        deployment_repository: DeploymentRepository,
        async_session: AsyncSession,
    ) -> None:
        """Test listing deployments with pagination."""
        # Create 10 deployments
        for i in range(10):
            deployment = Deployment(
                name=f"deployment-{i}",
                template={},
                parameters={},
                cloud_region="region",
            )
            await deployment_repository.create(deployment)
        await async_session.commit()

        # Get first page
        page1 = await deployment_repository.list(limit=5, offset=0)
        assert len(page1) == 5

        # Get second page
        page2 = await deployment_repository.list(limit=5, offset=5)
        assert len(page2) == 5

        # No overlap
        page1_ids = {d.id for d in page1}
        page2_ids = {d.id for d in page2}
        assert page1_ids.isdisjoint(page2_ids)

    async def test_count(
        self,
        deployment_repository: DeploymentRepository,
        async_session: AsyncSession,
    ) -> None:
        """Test counting deployments."""
        # Create deployments
        for i in range(3):
            deployment = Deployment(
                name=f"deployment-{i}",
                template={},
                parameters={},
                cloud_region="region",
            )
            await deployment_repository.create(deployment)
        await async_session.commit()

        # Count all
        total = await deployment_repository.count()
        assert total == 3

    async def test_count_with_filters(
        self,
        deployment_repository: DeploymentRepository,
        async_session: AsyncSession,
    ) -> None:
        """Test counting deployments with filters."""
        # Create deployments
        deployment1 = Deployment(
            name="completed-us-west",
            status=DeploymentStatus.COMPLETED,
            template={},
            parameters={},
            cloud_region="us-west-1",
        )
        deployment2 = Deployment(
            name="pending-us-west",
            status=DeploymentStatus.PENDING,
            template={},
            parameters={},
            cloud_region="us-west-1",
        )
        deployment3 = Deployment(
            name="completed-us-east",
            status=DeploymentStatus.COMPLETED,
            template={},
            parameters={},
            cloud_region="us-east-1",
        )
        await deployment_repository.create(deployment1)
        await deployment_repository.create(deployment2)
        await deployment_repository.create(deployment3)
        await async_session.commit()

        # Count by status
        completed_count = await deployment_repository.count(
            status=DeploymentStatus.COMPLETED
        )
        assert completed_count == 2

        # Count by region
        us_west_count = await deployment_repository.count(cloud_region="us-west-1")
        assert us_west_count == 2

        # Count by both
        completed_us_west = await deployment_repository.count(
            status=DeploymentStatus.COMPLETED, cloud_region="us-west-1"
        )
        assert completed_us_west == 1

    async def test_update_deployment(
        self,
        deployment_repository: DeploymentRepository,
        async_session: AsyncSession,
    ) -> None:
        """Test updating deployment."""
        # Create deployment
        deployment = Deployment(
            name="test",
            status=DeploymentStatus.PENDING,
            template={},
            parameters={},
            cloud_region="region",
        )
        created = await deployment_repository.create(deployment)
        await async_session.commit()

        # Update status
        updated = await deployment_repository.update(
            created.id, status=DeploymentStatus.COMPLETED
        )
        await async_session.commit()

        assert updated is not None
        assert updated.status == DeploymentStatus.COMPLETED

    async def test_update_deployment_not_found(
        self, deployment_repository: DeploymentRepository
    ) -> None:
        """Test updating deployment when not found."""
        result = await deployment_repository.update(uuid4(), status=DeploymentStatus.COMPLETED)
        assert result is None

    async def test_delete_deployment(
        self,
        deployment_repository: DeploymentRepository,
        async_session: AsyncSession,
    ) -> None:
        """Test soft deleting deployment."""
        # Create deployment
        deployment = Deployment(
            name="test",
            template={},
            parameters={},
            cloud_region="region",
        )
        created = await deployment_repository.create(deployment)
        await async_session.commit()

        # Delete
        deleted = await deployment_repository.delete(created.id)
        await async_session.commit()

        assert deleted is True

        # Verify soft delete
        found = await deployment_repository.get_by_id(created.id)
        assert found is not None
        assert found.status == DeploymentStatus.DELETED
        assert found.deleted_at is not None

    async def test_delete_deployment_not_found(
        self, deployment_repository: DeploymentRepository
    ) -> None:
        """Test deleting deployment when not found."""
        result = await deployment_repository.delete(uuid4())
        assert result is False

    async def test_hard_delete_deployment(
        self,
        deployment_repository: DeploymentRepository,
        async_session: AsyncSession,
    ) -> None:
        """Test permanently deleting deployment."""
        # Create deployment
        deployment = Deployment(
            name="test",
            template={},
            parameters={},
            cloud_region="region",
        )
        created = await deployment_repository.create(deployment)
        await async_session.commit()

        # Hard delete
        deleted = await deployment_repository.hard_delete(created.id)
        await async_session.commit()

        assert deleted is True

        # Verify permanently deleted
        found = await deployment_repository.get_by_id(created.id)
        assert found is None

    async def test_exists(
        self,
        deployment_repository: DeploymentRepository,
        async_session: AsyncSession,
    ) -> None:
        """Test checking if deployment exists."""
        # Create deployment
        deployment = Deployment(
            name="test",
            template={},
            parameters={},
            cloud_region="region",
        )
        created = await deployment_repository.create(deployment)
        await async_session.commit()

        # Check exists
        exists = await deployment_repository.exists(created.id)
        assert exists is True

        # Check non-existent
        not_exists = await deployment_repository.exists(uuid4())
        assert not_exists is False
