# ONAP SO Modern - User Guide

This guide explains how to use the ONAP SO Modern orchestrator API to manage infrastructure deployments.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Authentication](#authentication)
3. [Deployments](#deployments)
4. [Configuration Management](#configuration-management)
5. [Scaling Operations](#scaling-operations)
6. [Monitoring](#monitoring)
7. [Error Handling](#error-handling)
8. [Best Practices](#best-practices)

## Getting Started

### API Overview

The ONAP SO Modern orchestrator provides a RESTful API for:
- Creating and managing infrastructure deployments
- Configuring deployed resources with Ansible
- Scaling deployments up and down
- Monitoring deployment status

**Base URL**: `http://your-server:8000`

**Interactive Documentation**: `http://your-server:8000/docs`

### Quick Start Example

```bash
# 1. Check API health
curl http://localhost:8000/health

# 2. Create a deployment
curl -X POST http://localhost:8000/v1/deployments \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "name": "my-web-app",
    "cloud_region": "RegionOne",
    "template": {
      "vm_config": {
        "flavor": "m1.small",
        "image": "ubuntu-20.04",
        "count": 2
      }
    },
    "parameters": {
      "ssh_key_name": "my-key"
    }
  }'

# 3. Check deployment status
curl http://localhost:8000/v1/deployments/{deployment-id} \
  -H "X-API-Key: your-api-key"
```

## Authentication

### API Keys

All API requests (except `/health`, `/metrics`, `/docs`) require an API key.

Include the API key in the `X-API-Key` header:

```bash
curl http://localhost:8000/v1/deployments \
  -H "X-API-Key: your-api-key"
```

### Permission Levels

**Write Permission**: Full access to create, update, and delete resources
```bash
# API key with write permission
X-API-Key: prod-admin-key
```

**Read Permission**: Read-only access to list and get resources
```bash
# API key with read permission
X-API-Key: monitoring-key
```

### Rate Limiting

Requests are rate-limited to prevent abuse:
- **Default**: 100 requests per 60 seconds per API key
- **Headers returned**:
  - `X-RateLimit-Limit`: Maximum requests allowed
  - `X-RateLimit-Remaining`: Remaining requests in current window
  - `X-RateLimit-Reset`: Unix timestamp when limit resets
  - `Retry-After`: Seconds to wait before retrying (on 429 error)

```bash
# Example response headers
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 87
X-RateLimit-Reset: 1641830400
```

If you exceed the rate limit, you'll receive a `429 Too Many Requests` response:

```json
{
  "detail": "Rate limit exceeded. Too many requests.",
  "retry_after": 45
}
```

## Deployments

### Create a Deployment

Create a new infrastructure deployment from a template.

**Endpoint**: `POST /v1/deployments`

**Request**:
```bash
curl -X POST http://localhost:8000/v1/deployments \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "name": "web-app-production",
    "cloud_region": "us-west-1",
    "template": {
      "vm_config": {
        "flavor": "m1.medium",
        "image": "ubuntu-22.04",
        "count": 3
      },
      "network_config": {
        "network_name": "private-net",
        "subnet_cidr": "192.168.1.0/24"
      }
    },
    "parameters": {
      "ssh_key_name": "prod-key",
      "security_groups": ["web-sg", "ssh-sg"]
    }
  }'
```

**Response** (202 Accepted):
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "web-app-production",
  "status": "PENDING",
  "template": {
    "vm_config": {
      "flavor": "m1.medium",
      "image": "ubuntu-22.04",
      "count": 3
    },
    "network_config": {
      "network_name": "private-net",
      "subnet_cidr": "192.168.1.0/24"
    }
  },
  "parameters": {
    "ssh_key_name": "prod-key",
    "security_groups": ["web-sg", "ssh-sg"]
  },
  "cloud_region": "us-west-1",
  "resources": null,
  "error": null,
  "created_at": "2025-01-10T12:00:00Z",
  "updated_at": "2025-01-10T12:00:00Z"
}
```

**Template Structure**:

```json
{
  "vm_config": {
    "flavor": "m1.small",        // Required: OpenStack flavor
    "image": "ubuntu-20.04",     // Required: Image name or ID
    "count": 2                   // Optional: Number of VMs (default: 1)
  },
  "network_config": {            // Optional
    "network_name": "my-net",
    "subnet_cidr": "10.0.0.0/24",
    "enable_dhcp": true
  },
  "volume_config": {             // Optional
    "size_gb": 100,
    "type": "ssd"
  }
}
```

**Deployment Statuses**:
- `PENDING`: Deployment created, waiting to start
- `IN_PROGRESS`: Actively provisioning infrastructure
- `COMPLETED`: Successfully deployed
- `FAILED`: Deployment failed (check `error` field)
- `SCALING`: Scaling operation in progress
- `CONFIGURING`: Running Ansible configuration

### Get Deployment

Retrieve details of a specific deployment.

**Endpoint**: `GET /v1/deployments/{deployment_id}`

**Request**:
```bash
curl http://localhost:8000/v1/deployments/550e8400-e29b-41d4-a716-446655440000 \
  -H "X-API-Key: your-api-key"
```

**Response** (200 OK):
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "web-app-production",
  "status": "COMPLETED",
  "template": { ... },
  "parameters": { ... },
  "cloud_region": "us-west-1",
  "resources": {
    "server_ids": ["vm-1", "vm-2", "vm-3"],
    "network_id": "net-123",
    "subnet_id": "subnet-456"
  },
  "error": null,
  "created_at": "2025-01-10T12:00:00Z",
  "updated_at": "2025-01-10T12:05:00Z"
}
```

### List Deployments

List all deployments with optional filtering.

**Endpoint**: `GET /v1/deployments`

**Query Parameters**:
- `status`: Filter by status (e.g., `COMPLETED`, `FAILED`)
- `cloud_region`: Filter by cloud region
- `limit`: Maximum results (default: 100)
- `offset`: Pagination offset (default: 0)

**Request**:
```bash
# List all deployments
curl http://localhost:8000/v1/deployments \
  -H "X-API-Key: your-api-key"

# Filter by status
curl "http://localhost:8000/v1/deployments?status=COMPLETED&limit=50" \
  -H "X-API-Key: your-api-key"

# Filter by region
curl "http://localhost:8000/v1/deployments?cloud_region=us-west-1" \
  -H "X-API-Key: your-api-key"
```

**Response** (200 OK):
```json
{
  "items": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "name": "web-app-production",
      "status": "COMPLETED",
      ...
    },
    {
      "id": "661f9511-f90c-22e5-b827-537726551111",
      "name": "database-cluster",
      "status": "IN_PROGRESS",
      ...
    }
  ],
  "total": 42,
  "limit": 100,
  "offset": 0
}
```

### Update Deployment

Update deployment parameters (name, parameters).

**Endpoint**: `PATCH /v1/deployments/{deployment_id}`

**Request**:
```bash
curl -X PATCH http://localhost:8000/v1/deployments/550e8400-e29b-41d4-a716-446655440000 \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "name": "web-app-production-updated",
    "parameters": {
      "ssh_key_name": "new-key",
      "security_groups": ["web-sg", "ssh-sg", "monitoring-sg"]
    }
  }'
```

**Response** (200 OK):
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "web-app-production-updated",
  "status": "COMPLETED",
  ...
}
```

### Delete Deployment

Delete a deployment and its associated resources.

**Endpoint**: `DELETE /v1/deployments/{deployment_id}`

**Request**:
```bash
curl -X DELETE http://localhost:8000/v1/deployments/550e8400-e29b-41d4-a716-446655440000 \
  -H "X-API-Key: your-api-key"
```

**Response** (204 No Content)

**Note**: Deletion is asynchronous. The deployment status will change to `DELETING`, then be removed when complete.

## Configuration Management

### Configure Deployment

Run Ansible playbooks to configure deployed infrastructure.

**Endpoint**: `POST /v1/deployments/{deployment_id}/configure`

**Request**:
```bash
curl -X POST http://localhost:8000/v1/deployments/550e8400-e29b-41d4-a716-446655440000/configure \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "playbook_path": "playbooks/webserver-setup.yml",
    "extra_vars": {
      "app_version": "2.1.0",
      "environment": "production",
      "enable_ssl": true
    },
    "limit": "web-server-*"
  }'
```

**Request Fields**:
- `playbook_path`: **Required**. Relative path to Ansible playbook (e.g., `playbooks/setup.yml`)
  - Must be relative path (no `..` or absolute paths)
  - Must end with `.yml` or `.yaml`
- `extra_vars`: Optional. Variables to pass to playbook
- `limit`: Optional. Limit execution to specific hosts (pattern matching)
- `ssh_private_key`: Optional. SSH key for authentication (PEM format)

**Response** (202 Accepted):
```json
{
  "execution_id": "123e4567-e89b-12d3-a456-426614174000",
  "deployment_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "running",
  "playbook_path": "playbooks/webserver-setup.yml",
  "extra_vars": {
    "app_version": "2.1.0",
    "environment": "production",
    "enable_ssl": true
  },
  "started_at": "2025-01-10T12:10:00Z"
}
```

**Playbook Status Values**:
- `running`: Playbook is executing
- `successful`: Playbook completed successfully
- `failed`: Playbook execution failed

### Example Playbook

```yaml
# playbooks/webserver-setup.yml
---
- name: Configure web servers
  hosts: all
  become: yes
  vars:
    app_version: "{{ app_version | default('1.0.0') }}"
    environment: "{{ environment | default('development') }}"
  tasks:
    - name: Install Nginx
      apt:
        name: nginx
        state: present

    - name: Deploy application
      copy:
        src: "app-{{ app_version }}.tar.gz"
        dest: /var/www/app.tar.gz

    - name: Extract application
      unarchive:
        src: /var/www/app.tar.gz
        dest: /var/www/html
        remote_src: yes
```

## Scaling Operations

### Scale Deployment

Scale the number of VMs in a deployment up or down.

**Endpoint**: `POST /v1/deployments/{deployment_id}/scale`

**Request**:
```bash
# Scale to 5 VMs
curl -X POST http://localhost:8000/v1/deployments/550e8400-e29b-41d4-a716-446655440000/scale \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "target_count": 5
  }'
```

**Request Fields**:
- `target_count`: **Required**. Target number of VMs (1-100)
- `max_count`: Optional. Maximum allowed VMs (safety limit)

**Response** (202 Accepted):
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "web-app-production",
  "status": "SCALING",
  "resources": {
    "server_ids": ["vm-1", "vm-2", "vm-3"],
    "target_count": 5
  },
  ...
}
```

**Scaling Behavior**:
- **Scale Out** (increase count): New VMs are provisioned
- **Scale In** (decrease count): Excess VMs are removed (LIFO - last created, first removed)

**Example - Scale Out**:
```bash
# Current: 3 VMs, Scale to 5 VMs
curl -X POST http://localhost:8000/v1/deployments/550e8400-e29b-41d4-a716-446655440000/scale \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{"target_count": 5}'

# Result: 2 new VMs provisioned (vm-4, vm-5)
```

**Example - Scale In**:
```bash
# Current: 5 VMs, Scale to 3 VMs
curl -X POST http://localhost:8000/v1/deployments/550e8400-e29b-41d4-a716-446655440000/scale \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{"target_count": 3}'

# Result: 2 VMs removed (vm-5, vm-4)
```

## Monitoring

### Health Check

Check API health and dependencies.

**Endpoint**: `GET /health`

**Request**:
```bash
curl http://localhost:8000/health
```

**Response** (200 OK):
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "checks": {
    "database": "healthy",
    "temporal": "healthy"
  }
}
```

**No authentication required** for health endpoint.

### Metrics

Prometheus-compatible metrics for monitoring.

**Endpoint**: `GET /metrics`

**Request**:
```bash
curl http://localhost:8000/metrics
```

**Response** (200 OK):
```
# HELP deployment_total Total number of deployments
# TYPE deployment_total counter
deployment_total{status="completed"} 42
deployment_total{status="failed"} 3

# HELP request_duration_seconds Request duration in seconds
# TYPE request_duration_seconds histogram
request_duration_seconds_bucket{method="POST",path="/v1/deployments",le="0.1"} 120
request_duration_seconds_bucket{method="POST",path="/v1/deployments",le="0.5"} 145
...
```

**No authentication required** for metrics endpoint.

## Error Handling

### HTTP Status Codes

- `200 OK`: Successful request
- `202 Accepted`: Request accepted, processing asynchronously
- `204 No Content`: Successful deletion
- `400 Bad Request`: Invalid request data
- `401 Unauthorized`: Missing or invalid API key
- `403 Forbidden`: Insufficient permissions
- `404 Not Found`: Resource not found
- `422 Unprocessable Entity`: Validation error
- `429 Too Many Requests`: Rate limit exceeded
- `500 Internal Server Error`: Server error

### Error Response Format

All errors return a JSON response with details:

```json
{
  "detail": "Deployment not found",
  "timestamp": "2025-01-10T12:00:00Z"
}
```

### Common Errors

#### 1. Authentication Error (401)

```json
{
  "detail": "API key required. Include X-API-Key header."
}
```

**Solution**: Include valid API key in `X-API-Key` header.

#### 2. Permission Error (403)

```json
{
  "detail": "Write permission required for this operation"
}
```

**Solution**: Use an API key with write permission.

#### 3. Validation Error (422)

```json
{
  "detail": [
    {
      "loc": ["body", "template", "vm_config", "image"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

**Solution**: Fix the validation error in your request.

#### 4. Rate Limit Error (429)

```json
{
  "detail": "Rate limit exceeded. Too many requests.",
  "retry_after": 45
}
```

**Solution**: Wait for `retry_after` seconds before retrying.

## Best Practices

### 1. API Key Security

- **Never commit API keys** to version control
- **Rotate keys regularly** (every 90 days)
- **Use read-only keys** for monitoring and reporting
- **Store keys securely** in environment variables or secret managers

```bash
# Good: Store in environment
export API_KEY="your-secret-key"
curl -H "X-API-Key: $API_KEY" ...

# Bad: Hardcode in scripts
curl -H "X-API-Key: actual-key-here" ...
```

### 2. Polling for Status

When creating deployments, poll for status updates:

```bash
# Create deployment
DEPLOYMENT_ID=$(curl -X POST http://localhost:8000/v1/deployments \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{ ... }' | jq -r '.id')

# Poll status every 10 seconds
while true; do
  STATUS=$(curl -s http://localhost:8000/v1/deployments/$DEPLOYMENT_ID \
    -H "X-API-Key: $API_KEY" | jq -r '.status')

  echo "Status: $STATUS"

  if [ "$STATUS" = "COMPLETED" ]; then
    echo "Deployment successful!"
    break
  elif [ "$STATUS" = "FAILED" ]; then
    echo "Deployment failed!"
    exit 1
  fi

  sleep 10
done
```

### 3. Error Handling

Always check response status and handle errors:

```python
import requests

def create_deployment(api_key, deployment_data):
    """Create deployment with proper error handling."""
    headers = {"X-API-Key": api_key}

    try:
        response = requests.post(
            "http://localhost:8000/v1/deployments",
            json=deployment_data,
            headers=headers,
            timeout=30
        )
        response.raise_for_status()
        return response.json()

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 429:
            # Rate limited - wait and retry
            retry_after = int(e.response.headers.get('Retry-After', 60))
            print(f"Rate limited. Retry after {retry_after} seconds")
            time.sleep(retry_after)
            return create_deployment(api_key, deployment_data)
        else:
            print(f"Error: {e.response.json()}")
            raise

    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
        raise
```

### 4. Template Validation

Validate templates before creating deployments:

```json
{
  "vm_config": {
    "flavor": "m1.small",        // ✓ Required
    "image": "ubuntu-20.04",     // ✓ Required
    "count": 2                   // ✓ Optional, default: 1
  }
}
```

Required fields:
- `vm_config.flavor`: Must be valid OpenStack flavor
- `vm_config.image`: Must be valid image name or ID

### 5. Naming Conventions

Use descriptive, consistent naming:

```bash
# Good names
web-app-production
database-cluster-staging
api-gateway-dev-us-east-1

# Bad names
test1
my-deployment
abc123
```

Rules:
- Start with alphanumeric character
- Use hyphens or underscores for separation
- Include environment and purpose
- Maximum 255 characters

### 6. Resource Tagging

Use parameters for metadata and tagging:

```json
{
  "parameters": {
    "environment": "production",
    "cost_center": "engineering",
    "project": "web-platform",
    "owner": "ops-team"
  }
}
```

## Python Client Example

```python
import requests
import time
from typing import Dict, Any

class OrchestrationClient:
    """Client for ONAP SO Modern orchestrator."""

    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({'X-API-Key': api_key})

    def create_deployment(self, name: str, cloud_region: str,
                         template: Dict[str, Any],
                         parameters: Dict[str, Any] = None) -> Dict[str, Any]:
        """Create a new deployment."""
        data = {
            "name": name,
            "cloud_region": cloud_region,
            "template": template,
            "parameters": parameters or {}
        }

        response = self.session.post(
            f"{self.base_url}/v1/deployments",
            json=data
        )
        response.raise_for_status()
        return response.json()

    def get_deployment(self, deployment_id: str) -> Dict[str, Any]:
        """Get deployment by ID."""
        response = self.session.get(
            f"{self.base_url}/v1/deployments/{deployment_id}"
        )
        response.raise_for_status()
        return response.json()

    def wait_for_deployment(self, deployment_id: str,
                           timeout: int = 600) -> Dict[str, Any]:
        """Wait for deployment to complete."""
        start_time = time.time()

        while time.time() - start_time < timeout:
            deployment = self.get_deployment(deployment_id)
            status = deployment['status']

            if status == 'COMPLETED':
                return deployment
            elif status == 'FAILED':
                raise Exception(f"Deployment failed: {deployment.get('error')}")

            time.sleep(10)

        raise TimeoutError("Deployment timed out")

    def scale_deployment(self, deployment_id: str,
                        target_count: int) -> Dict[str, Any]:
        """Scale deployment to target count."""
        response = self.session.post(
            f"{self.base_url}/v1/deployments/{deployment_id}/scale",
            json={"target_count": target_count}
        )
        response.raise_for_status()
        return response.json()

# Usage
client = OrchestrationClient(
    base_url="http://localhost:8000",
    api_key="your-api-key"
)

# Create deployment
deployment = client.create_deployment(
    name="web-app-prod",
    cloud_region="RegionOne",
    template={
        "vm_config": {
            "flavor": "m1.small",
            "image": "ubuntu-20.04",
            "count": 3
        }
    }
)

# Wait for completion
deployment = client.wait_for_deployment(deployment['id'])
print(f"Deployment completed: {deployment['resources']}")

# Scale up
deployment = client.scale_deployment(deployment['id'], target_count=5)
print(f"Scaling to 5 instances")
```

## Next Steps

- [Deployment Guide](./deployment-guide.md) - Deploy the orchestrator
- [Architecture Overview](./architecture.md) - System architecture
- [API Reference](http://localhost:8000/docs) - Interactive API docs
