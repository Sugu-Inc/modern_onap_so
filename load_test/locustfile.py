"""
Load test for Modern Orchestrator API using Locust.

This load test simulates realistic user workflows including:
- Health check monitoring
- Read-heavy workloads (listing and polling deployments)
- Write operations (creating deployments)
- Complete deployment lifecycle workflows
"""

import json
import random
import time
from typing import Any

from locust import HttpUser, TaskSet, between, task


class HealthCheckUser(HttpUser):
    """User that only performs health checks - simulates monitoring systems."""

    wait_time = between(1, 3)
    weight = 10  # 10% of users

    @task
    def health_check(self) -> None:
        """Check application health."""
        self.client.get("/health", name="/health")

    @task
    def metrics(self) -> None:
        """Fetch Prometheus metrics."""
        self.client.get("/metrics", name="/metrics")


class ReadHeavyUser(HttpUser):
    """User performing mostly read operations - simulates dashboard/monitoring."""

    wait_time = between(0.5, 2)
    weight = 50  # 50% of users
    api_keys = [
        "load-test-key-1:read",
        "load-test-key-2:read",
        "load-test-key-3:read",
        "load-test-key-4:read",
        "load-test-key-5:read",
    ]

    def on_start(self) -> None:
        """Initialize user with random API key."""
        self.api_key = random.choice(self.api_keys).split(":")[0]
        self.headers = {"X-API-Key": self.api_key}

    @task(10)
    def list_deployments(self) -> None:
        """List deployments with pagination."""
        limit = random.choice([10, 20, 50])
        offset = random.randint(0, 100)
        self.client.get(
            f"/v1/deployments?limit={limit}&offset={offset}",
            headers=self.headers,
            name="/v1/deployments [LIST]",
        )

    @task(5)
    def list_with_status_filter(self) -> None:
        """List deployments filtered by status."""
        status = random.choice(["PENDING", "IN_PROGRESS", "COMPLETED", "FAILED"])
        self.client.get(
            f"/v1/deployments?status={status}",
            headers=self.headers,
            name="/v1/deployments?status= [FILTER]",
        )

    @task(3)
    def list_with_region_filter(self) -> None:
        """List deployments filtered by cloud region."""
        region = random.choice(["RegionOne", "RegionTwo", "RegionThree"])
        self.client.get(
            f"/v1/deployments?cloud_region={region}",
            headers=self.headers,
            name="/v1/deployments?cloud_region= [FILTER]",
        )

    @task(1)
    def health_check(self) -> None:
        """Occasional health checks."""
        self.client.get("/health", name="/health")


class WriteUser(HttpUser):
    """User performing write operations - simulates active users creating infrastructure."""

    wait_time = between(2, 5)
    weight = 30  # 30% of users
    api_keys = [
        "load-test-key-6:write",
        "load-test-key-7:write",
        "load-test-key-8:write",
        "load-test-key-9:write",
        "load-test-key-10:write",
    ]

    def on_start(self) -> None:
        """Initialize user with random API key."""
        self.api_key = random.choice(self.api_keys).split(":")[0]
        self.headers = {
            "X-API-Key": self.api_key,
            "Content-Type": "application/json",
        }
        self.created_deployments: list[str] = []

    @task(10)
    def create_deployment(self) -> None:
        """Create a new deployment."""
        deployment_name = f"load-test-{self.api_key[-4:]}-{int(time.time())}-{random.randint(1000, 9999)}"

        payload = {
            "name": deployment_name,
            "template": {
                "vm_config": {
                    "web": {
                        "flavor": random.choice(["m1.small", "m1.medium", "m1.large"]),
                        "image": "ubuntu-22.04",
                        "count": random.randint(1, 3),
                    }
                },
                "network_config": {
                    "cidr": "10.0.0.0/16"
                },
            },
            "parameters": {
                "environment": random.choice(["dev", "staging", "prod"]),
                "auto_scale": random.choice([True, False]),
            },
            "cloud_region": random.choice(["RegionOne", "RegionTwo", "RegionThree"]),
        }

        with self.client.post(
            "/v1/deployments",
            json=payload,
            headers=self.headers,
            catch_response=True,
            name="/v1/deployments [CREATE]",
        ) as response:
            if response.status_code == 201:
                try:
                    data = response.json()
                    deployment_id = data.get("id")
                    if deployment_id:
                        self.created_deployments.append(deployment_id)
                        response.success()
                except Exception:
                    response.failure("Failed to parse deployment ID")
            elif response.status_code == 429:
                response.failure("Rate limited")
            else:
                response.failure(f"Unexpected status code: {response.status_code}")

    @task(5)
    def get_deployment_details(self) -> None:
        """Get details of a previously created deployment."""
        if self.created_deployments:
            deployment_id = random.choice(self.created_deployments)
            self.client.get(
                f"/v1/deployments/{deployment_id}",
                headers=self.headers,
                name="/v1/deployments/{id} [GET]",
            )

    @task(3)
    def update_deployment(self) -> None:
        """Update a previously created deployment."""
        if self.created_deployments:
            deployment_id = random.choice(self.created_deployments)

            payload = {
                "parameters": {
                    "updated_at": int(time.time()),
                    "load_test": True,
                }
            }

            self.client.patch(
                f"/v1/deployments/{deployment_id}",
                json=payload,
                headers=self.headers,
                name="/v1/deployments/{id} [UPDATE]",
            )

    @task(1)
    def delete_deployment(self) -> None:
        """Delete a previously created deployment."""
        if len(self.created_deployments) > 3:  # Keep at least 3 for other operations
            deployment_id = self.created_deployments.pop(0)
            self.client.delete(
                f"/v1/deployments/{deployment_id}",
                headers=self.headers,
                name="/v1/deployments/{id} [DELETE]",
            )


class FullWorkflowUser(HttpUser):
    """User executing complete deployment lifecycle - simulates real-world usage."""

    wait_time = between(3, 8)
    weight = 10  # 10% of users
    api_keys = [
        "load-test-key-11:write",
        "load-test-key-12:write",
    ]

    def on_start(self) -> None:
        """Initialize user with random API key."""
        self.api_key = random.choice(self.api_keys).split(":")[0]
        self.headers = {
            "X-API-Key": self.api_key,
            "Content-Type": "application/json",
        }

    @task
    def complete_deployment_workflow(self) -> None:
        """Execute a complete deployment lifecycle."""
        deployment_name = f"workflow-{self.api_key[-4:]}-{int(time.time())}"

        # Step 1: Create deployment
        payload = {
            "name": deployment_name,
            "template": {
                "vm_config": {
                    "app": {
                        "flavor": "m1.medium",
                        "image": "ubuntu-22.04",
                        "count": 2,
                    }
                },
                "network_config": {
                    "cidr": "10.1.0.0/16"
                },
            },
            "parameters": {
                "environment": "production",
                "ha_enabled": True,
            },
            "cloud_region": "RegionOne",
        }

        with self.client.post(
            "/v1/deployments",
            json=payload,
            headers=self.headers,
            catch_response=True,
            name="[WORKFLOW] Create deployment",
        ) as response:
            if response.status_code != 201:
                response.failure(f"Failed to create deployment: {response.status_code}")
                return

            try:
                deployment_id = response.json().get("id")
                if not deployment_id:
                    response.failure("No deployment ID in response")
                    return
            except Exception:
                response.failure("Failed to parse deployment ID")
                return

        # Step 2: Poll status (simulate waiting)
        for _ in range(3):
            time.sleep(0.5)  # Small delay between polls
            self.client.get(
                f"/v1/deployments/{deployment_id}",
                headers=self.headers,
                name="[WORKFLOW] Poll status",
            )

        # Step 3: Configure deployment (would normally wait for COMPLETED status)
        config_payload = {
            "playbook_path": "playbooks/setup.yml",
            "extra_vars": {
                "app_version": "1.0.0",
                "environment": "production",
            },
        }

        self.client.post(
            f"/v1/deployments/{deployment_id}/configure",
            json=config_payload,
            headers=self.headers,
            name="[WORKFLOW] Configure",
        )

        # Step 4: Scale deployment
        scale_payload = {
            "target_count": 3,
            "min_count": 1,
            "max_count": 5,
        }

        self.client.post(
            f"/v1/deployments/{deployment_id}/scale",
            json=scale_payload,
            headers=self.headers,
            name="[WORKFLOW] Scale",
        )

        # Step 5: Final status check
        self.client.get(
            f"/v1/deployments/{deployment_id}",
            headers=self.headers,
            name="[WORKFLOW] Final check",
        )

        # Step 6: Cleanup - delete deployment
        self.client.delete(
            f"/v1/deployments/{deployment_id}",
            headers=self.headers,
            name="[WORKFLOW] Delete",
        )
