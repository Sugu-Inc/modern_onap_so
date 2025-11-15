#!/usr/bin/env python3
"""
Seed the database with realistic deployment data for load testing.

This script creates thousands of deployment records with realistic:
- Status distribution (mostly COMPLETED, some IN_PROGRESS, fewer FAILED)
- Cloud regions
- Creation timestamps (spread over time)
- Resource configurations
- Template variations
"""

import asyncio
import random
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from orchestrator.models.base import Base
from orchestrator.models.deployment import Deployment, DeploymentStatus


# Realistic data pools
DEPLOYMENT_NAMES = [
    "web-app-prod", "api-gateway", "database-cluster", "cache-layer", "worker-pool",
    "frontend-service", "backend-service", "analytics-engine", "ml-pipeline", "data-warehouse",
    "message-queue", "search-service", "auth-service", "notification-service", "payment-service",
    "inventory-system", "order-processing", "customer-portal", "admin-dashboard", "monitoring-stack",
    "logging-infrastructure", "ci-cd-pipeline", "test-environment", "staging-env", "dev-sandbox",
]

CLOUD_REGIONS = ["RegionOne", "RegionTwo", "RegionThree", "us-east-1", "us-west-2", "eu-central-1"]

FLAVORS = ["m1.small", "m1.medium", "m1.large", "m1.xlarge", "c1.medium", "c1.large"]

IMAGES = ["ubuntu-22.04", "ubuntu-20.04", "debian-11", "centos-8", "rocky-9"]

VM_ROLES = ["web", "app", "db", "cache", "worker", "lb", "api", "queue"]

# Status distribution (realistic production scenario)
STATUS_WEIGHTS = {
    DeploymentStatus.COMPLETED: 0.70,    # 70% successfully deployed
    DeploymentStatus.IN_PROGRESS: 0.12,  # 12% currently deploying
    DeploymentStatus.FAILED: 0.08,       # 8% failed
    DeploymentStatus.PENDING: 0.05,      # 5% pending
    DeploymentStatus.DELETING: 0.03,     # 3% being deleted
    DeploymentStatus.DELETED: 0.02,      # 2% deleted (soft delete)
}


def generate_deployment_name(index: int) -> str:
    """Generate a realistic deployment name."""
    base_name = random.choice(DEPLOYMENT_NAMES)
    env = random.choice(["prod", "staging", "dev", "test", "qa"])
    region = random.choice(["us", "eu", "ap"])
    return f"{base_name}-{env}-{region}-{index:04d}"


def generate_vm_config() -> dict:
    """Generate realistic VM configuration."""
    num_roles = random.randint(1, 3)
    vm_config = {}

    for _ in range(num_roles):
        role = random.choice(VM_ROLES)
        vm_config[role] = {
            "flavor": random.choice(FLAVORS),
            "image": random.choice(IMAGES),
            "count": random.randint(1, 5) if role != "db" else random.randint(1, 3),
        }

    return vm_config


def generate_network_config() -> dict:
    """Generate realistic network configuration."""
    return {
        "cidr": f"10.{random.randint(0, 255)}.0.0/16",
        "enable_floating_ip": random.choice([True, False]),
        "security_groups": random.choice([["default"], ["web", "app"], ["default", "custom"]]),
    }


def generate_parameters() -> dict:
    """Generate realistic deployment parameters."""
    params = {
        "environment": random.choice(["production", "staging", "development", "qa"]),
        "auto_scale": random.choice([True, False]),
        "backup_enabled": random.choice([True, False]),
        "monitoring_enabled": random.choice([True, True, False]),  # weighted toward True
    }

    if params["auto_scale"]:
        params["min_instances"] = random.randint(1, 2)
        params["max_instances"] = random.randint(5, 10)

    return params


def generate_resources(status: DeploymentStatus) -> dict:
    """Generate resource IDs based on deployment status."""
    if status in [DeploymentStatus.PENDING, DeploymentStatus.FAILED]:
        return {}

    resources = {
        "network_id": f"net-{uuid4().hex[:12]}",
        "subnet_id": f"subnet-{uuid4().hex[:12]}",
    }

    if status in [DeploymentStatus.COMPLETED, DeploymentStatus.IN_PROGRESS, DeploymentStatus.DELETING]:
        num_servers = random.randint(1, 8)
        resources["server_ids"] = [f"vm-{uuid4().hex[:12]}" for _ in range(num_servers)]

    return resources


def generate_error(status: DeploymentStatus) -> dict | None:
    """Generate error information for failed deployments."""
    if status != DeploymentStatus.FAILED:
        return None

    errors = [
        {"code": "QUOTA_EXCEEDED", "message": "Insufficient quota for flavor m1.large"},
        {"code": "IMAGE_NOT_FOUND", "message": "Image ubuntu-22.04 not found in region"},
        {"code": "NETWORK_ERROR", "message": "Failed to create network: timeout"},
        {"code": "AUTH_FAILURE", "message": "Invalid OpenStack credentials"},
        {"code": "RESOURCE_UNAVAILABLE", "message": "No available hosts for flavor"},
    ]

    return random.choice(errors)


def generate_metadata(status: DeploymentStatus) -> dict:
    """Generate extra metadata."""
    metadata = {
        "created_by": random.choice(["admin", "deploy-bot", "user-123", "ci-cd-pipeline"]),
        "tags": random.sample(["production", "critical", "experimental", "legacy", "microservice"], k=random.randint(1, 3)),
    }

    if status == DeploymentStatus.COMPLETED and random.random() > 0.5:
        metadata["scaling_history"] = [
            {
                "timestamp": (datetime.now(UTC) - timedelta(days=random.randint(1, 30))).isoformat(),
                "from_count": random.randint(2, 4),
                "to_count": random.randint(4, 8),
            }
        ]

    return metadata


def select_status() -> DeploymentStatus:
    """Select a deployment status based on realistic distribution."""
    rand = random.random()
    cumulative = 0.0

    for status, weight in STATUS_WEIGHTS.items():
        cumulative += weight
        if rand <= cumulative:
            return status

    return DeploymentStatus.COMPLETED


async def seed_database(count: int = 5000, database_url: str = "sqlite+aiosqlite:///./load_test.db") -> None:
    """Seed the database with deployment records."""

    print(f"{'='*60}")
    print(f"Seeding Database with {count:,} Deployments")
    print(f"{'='*60}")
    print(f"Database: {database_url}")
    print()

    # Create engine and session
    engine = create_async_engine(database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # Create tables if they don't exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    print("✓ Database schema ready")
    print()
    print("Generating deployment data...")

    # Generate deployments in batches
    batch_size = 500
    total_batches = (count + batch_size - 1) // batch_size

    start_time = datetime.now(UTC)

    for batch_num in range(total_batches):
        batch_start = batch_num * batch_size
        batch_end = min(batch_start + batch_size, count)
        batch_count = batch_end - batch_start

        deployments = []

        for i in range(batch_start, batch_end):
            status = select_status()

            # Create timestamp spread over the last 90 days
            days_ago = random.randint(0, 90)
            hours_ago = random.randint(0, 23)
            minutes_ago = random.randint(0, 59)
            created_at = datetime.now(UTC) - timedelta(days=days_ago, hours=hours_ago, minutes=minutes_ago)

            # Updated timestamp is after created
            updated_delta = timedelta(minutes=random.randint(1, 60))
            updated_at = created_at + updated_delta

            # Deleted timestamp for deleted deployments
            deleted_at = None
            if status == DeploymentStatus.DELETED:
                deleted_at = updated_at + timedelta(hours=random.randint(1, 24))

            deployment = Deployment(
                id=uuid4(),
                name=generate_deployment_name(i),
                status=status,
                template={
                    "vm_config": generate_vm_config(),
                    "network_config": generate_network_config(),
                },
                parameters=generate_parameters(),
                cloud_region=random.choice(CLOUD_REGIONS),
                resources=generate_resources(status),
                error=generate_error(status),
                extra_metadata=generate_metadata(status),
                created_at=created_at,
                updated_at=updated_at,
                deleted_at=deleted_at,
            )

            deployments.append(deployment)

        # Insert batch
        async with async_session() as session:
            async with session.begin():
                session.add_all(deployments)

        progress = (batch_end / count) * 100
        print(f"  Batch {batch_num + 1}/{total_batches}: Inserted {batch_count:,} deployments ({progress:.1f}% complete)")

    await engine.dispose()

    elapsed = (datetime.now(UTC) - start_time).total_seconds()

    print()
    print(f"{'='*60}")
    print(f"✓ Successfully seeded {count:,} deployments in {elapsed:.2f} seconds")
    print(f"{'='*60}")
    print()
    print("Status Distribution:")
    for status, weight in STATUS_WEIGHTS.items():
        expected_count = int(count * weight)
        print(f"  {status.value:15s}: ~{expected_count:,} ({weight*100:.0f}%)")
    print()


async def verify_seed(database_url: str = "sqlite+aiosqlite:///./load_test.db") -> None:
    """Verify the seeded data."""
    from sqlalchemy import func, select

    print("Verifying seeded data...")
    print()

    engine = create_async_engine(database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # Total count
        result = await session.execute(select(func.count(Deployment.id)))
        total = result.scalar()
        print(f"Total deployments: {total:,}")
        print()

        # Count by status
        print("Actual distribution:")
        for status in DeploymentStatus:
            result = await session.execute(
                select(func.count(Deployment.id)).where(Deployment.status == status)
            )
            count = result.scalar()
            percentage = (count / total * 100) if total > 0 else 0
            print(f"  {status.value:15s}: {count:,} ({percentage:.1f}%)")
        print()

        # Count by region
        print("Deployments by region:")
        for region in CLOUD_REGIONS:
            result = await session.execute(
                select(func.count(Deployment.id)).where(Deployment.cloud_region == region)
            )
            count = result.scalar()
            print(f"  {region:15s}: {count:,}")
        print()

    await engine.dispose()
    print("✓ Verification complete")
    print()


async def main() -> None:
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Seed database with realistic deployment data")
    parser.add_argument("--count", type=int, default=5000, help="Number of deployments to create (default: 5000)")
    parser.add_argument("--database-url", default="sqlite+aiosqlite:///./load_test.db", help="Database URL")
    parser.add_argument("--verify", action="store_true", help="Verify seeded data after insertion")

    args = parser.parse_args()

    await seed_database(count=args.count, database_url=args.database_url)

    if args.verify:
        await verify_seed(database_url=args.database_url)


if __name__ == "__main__":
    asyncio.run(main())
