# Modern Infrastructure Orchestrator - Technical Specification

## Executive Summary

The Modern Infrastructure Orchestrator is a lightweight, cloud-native platform for deploying and managing infrastructure resources on OpenStack. Built from first principles with modern technologies, it provides simple, reliable orchestration without the complexity of enterprise telecommunications platforms.

**Version:** 1.0.0 (Initial Release)
**Status:** Development
**License:** Apache 2.0
**Primary Language:** Python 3.12+

**Key Differentiators:**
- **Simplified**: Direct API calls instead of multi-layer abstractions
- **Modern**: FastAPI, Temporal, PostgreSQL - battle-tested cloud-native stack
- **Fast**: 4-6 weeks to MVP vs 6-9 months for legacy approaches
- **Maintainable**: 158 tasks vs 295, 77% less test complexity

---

## Business Overview

### Purpose and Value Proposition

The Modern Infrastructure Orchestrator solves the fundamental challenge of infrastructure provisioning without the overhead of complex enterprise orchestration platforms. It provides:

1. **Simple Deployment**: Deploy VMs and networks with a single API call
2. **Workflow Orchestration**: Reliable, durable workflows with Temporal
3. **State Tracking**: Complete visibility into deployment status and history
4. **Configuration Management**: Industry-standard Ansible for post-deployment configuration
5. **Scalability**: Elastic scaling of deployed infrastructure

### Target Users and Use Cases

**Primary Users:**
- DevOps Engineers managing cloud infrastructure
- Platform Teams building internal developer platforms
- SREs automating infrastructure provisioning
- Small to medium cloud service providers

**Key Use Cases:**
- **Infrastructure Provisioning**: Automated deployment of VMs, networks, and storage
- **Application Hosting**: Deploy multi-tier applications on OpenStack
- **Development Environments**: Spin up/down ephemeral environments
- **Scaling Operations**: Manual and automated scaling of deployments
- **Lifecycle Management**: Update and teardown infrastructure cleanly

### Business Benefits

1. **Reduced Complexity**: No unnecessary enterprise features - just what you need
2. **Faster Time-to-Value**: MVP in 4-6 weeks vs months for enterprise platforms
3. **Lower TCO**: Simple stack means less operational overhead
4. **Developer Velocity**: Modern Python stack attracts talent, easy to extend
5. **Reliability**: Temporal ensures workflows complete even through failures
6. **Observability**: Built-in Prometheus metrics and structured logging

---

## Product Overview

### Core Capabilities

#### 1. Infrastructure Deployment
- Deploy VMs with configurable size, image, network configuration
- Create networks with custom subnets and routing
- Attach storage volumes
- All provisioned via OpenStack APIs (Nova, Neutron, Cinder)
- Template-based deployments for reproducibility

#### 2. Workflow Orchestration
- Temporal workflows for reliable execution
- Asynchronous operation support
- Automatic retries and error handling
- Workflow state persistence
- Activity-based architecture for composability

#### 3. Deployment Management
- Full CRUD operations on deployments
- Real-time status tracking
- Deployment history and audit trail
- Clean resource cleanup on deletion
- Orphaned resource detection and cleanup

#### 4. Configuration Management
- Ansible playbook execution on deployed VMs
- SSH-based configuration
- Idempotent configuration application
- Configuration status tracking

#### 5. Scaling
- Horizontal scaling (add/remove VMs)
- Minimum instance count enforcement
- Graceful scale-down with resource cleanup

---

## Architecture

### High-Level Architecture

The architecture follows a modern, cloud-native design with clean separation of concerns:

```
┌─────────────────────────────────────────────────────────┐
│                    Northbound Clients                    │
│         (Web UI, CLI, External Systems, CI/CD)          │
└─────────────────────┬───────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────┐
│                  FastAPI Application                     │
│         RESTful Deployment & Management APIs             │
│              (Middleware: Auth, Logging)                 │
└──────┬──────────────────────────────────┬───────────────┘
       │                                  │
       │                                  │
       ▼                                  ▼
┌─────────────────┐              ┌─────────────────┐
│  Service Layer  │              │ Temporal Client │
│ (Business Logic)│              │   (Workflows)   │
└────────┬────────┘              └────────┬────────┘
         │                                │
         │                                │
         ▼                                ▼
┌─────────────────┐              ┌─────────────────┐
│  Repository     │              │ Temporal Server │
│    Layer        │              │  (Orchestration)│
└────────┬────────┘              └────────┬────────┘
         │                                │
         ▼                                ▼
┌─────────────────┐              ┌─────────────────┐
│   PostgreSQL    │              │   Activities    │
│   (State DB)    │              │  (OpenStack,    │
└─────────────────┘              │   Ansible)      │
                                 └────────┬────────┘
                                          │
                                          ▼
                         ┌────────────────────────────────┐
                         │     External Systems           │
                         │  (OpenStack, Ansible Hosts)    │
                         └────────────────────────────────┘

```

### Component Details

#### API Layer (FastAPI)
**Purpose:** Provide RESTful interface to clients

**Key Functions:**
- Deployment CRUD endpoints
- Status query endpoints
- Configuration management endpoints
- Scaling endpoints
- Health check and metrics

**Modules:**
- `src/orchestrator/main.py`: FastAPI application
- `src/orchestrator/api/v1/deployments.py`: Deployment endpoints
- `src/orchestrator/api/v1/configurations.py`: Configuration endpoints
- `src/orchestrator/api/v1/scaling.py`: Scaling endpoints
- `src/orchestrator/api/health.py`: Health check

**APIs Exposed:**
- `POST /deployments`: Create deployment
- `GET /deployments/{id}`: Get deployment status
- `GET /deployments`: List all deployments
- `PATCH /deployments/{id}`: Update deployment
- `DELETE /deployments/{id}`: Delete deployment
- `POST /deployments/{id}/configure`: Apply configuration
- `POST /deployments/{id}/scale`: Scale deployment
- `GET /health`: Health check
- `GET /metrics`: Prometheus metrics

**Middleware:**
- Authentication (API key based)
- Request logging (structured logs)
- Error handling (consistent error responses)
- CORS handling
- Rate limiting

#### Service Layer
**Purpose:** Business logic and orchestration coordination

**Key Functions:**
- Request validation
- Template resolution
- Workflow triggering
- State management
- Error handling

**Modules:**
- `src/orchestrator/services/deployment_service.py`: Deployment business logic
- `src/orchestrator/services/cache.py`: Template caching

**Design Patterns:**
- Dependency injection for testability
- Async/await for I/O operations
- Repository pattern for data access

#### Workflow Layer (Temporal)
**Purpose:** Reliable, durable workflow execution

**Technology:** Temporal (Python SDK)

**Key Functions:**
- Workflow orchestration
- Activity execution
- Retry logic
- Timeout handling
- State persistence
- Event-driven execution

**Workflows:**
- `DeployWorkflow`: Orchestrate VM and network deployment
- `DeleteWorkflow`: Clean teardown of resources
- `UpdateWorkflow`: Modify existing deployments
- `ConfigureWorkflow`: Apply Ansible configuration
- `ScaleWorkflow`: Scale deployment up/down

**Activities:**
- `create_network`: Create OpenStack network
- `create_vm`: Create OpenStack VM instance
- `poll_vm_status`: Wait for VM to be active
- `delete_vm`: Delete OpenStack VM
- `delete_network`: Delete OpenStack network
- `cleanup_resources`: Clean up orphaned resources
- `resize_vm`: Resize VM
- `run_ansible`: Execute Ansible playbook
- `scale_out`: Add VM instances
- `scale_in`: Remove VM instances

**Modules:**
- `src/orchestrator/workflows/client.py`: Temporal client
- `src/orchestrator/workflows/worker.py`: Worker factory
- `src/orchestrator/workflows/deployment/deploy.py`: Deploy workflow
- `src/orchestrator/workflows/deployment/delete.py`: Delete workflow
- `src/orchestrator/workflows/deployment/update.py`: Update workflow
- `src/orchestrator/workflows/deployment/activities.py`: Deployment activities
- `src/orchestrator/workflows/configuration/configure.py`: Configuration workflow
- `src/orchestrator/workflows/configuration/activities.py`: Configuration activities
- `src/orchestrator/workflows/scaling/scale.py`: Scaling workflow
- `src/orchestrator/workflows/scaling/activities.py`: Scaling activities

#### Data Layer
**Purpose:** Persistent state storage

**Database:** PostgreSQL 15+

**ORM:** SQLAlchemy 2.0 (async)

**Key Tables:**
- `deployments`: Deployment records
  - id (UUID, PK)
  - name (String)
  - status (Enum: PENDING, IN_PROGRESS, COMPLETED, FAILED, DELETING)
  - template (JSONB)
  - parameters (JSONB)
  - cloud_region (String)
  - resources (JSONB) - Created resource IDs
  - created_at (Timestamp)
  - updated_at (Timestamp)
  - deleted_at (Timestamp, nullable)

- `deployment_templates`: Reusable templates
  - id (UUID, PK)
  - name (String)
  - description (Text)
  - vm_config (JSONB)
  - network_config (JSONB)
  - created_at (Timestamp)
  - updated_at (Timestamp)

**Modules:**
- `src/orchestrator/db/connection.py`: Database connection
- `src/orchestrator/models/deployment.py`: Deployment model
- `src/orchestrator/models/template.py`: Template model
- `src/orchestrator/db/repositories/deployment_repository.py`: Deployment data access

#### OpenStack Client
**Purpose:** Direct OpenStack API integration

**APIs Used:**
- **Keystone** (Identity): Authentication
- **Nova** (Compute): VM creation, deletion, resize
- **Neutron** (Network): Network, subnet, router creation
- **Cinder** (Block Storage): Volume management (future)

**Modules:**
- `src/orchestrator/clients/openstack/client.py`: OpenStack client
- `src/orchestrator/clients/openstack/schemas.py`: OpenStack request/response schemas

**Design:**
- Direct REST API calls (no OpenStack SDK dependency)
- Token caching for performance
- Retry logic with exponential backoff
- Circuit breaker for failure handling

#### Ansible Client
**Purpose:** Configuration management integration

**Technology:** ansible-runner (subprocess execution)

**Modules:**
- `src/orchestrator/clients/ansible/client.py`: Ansible client

**Key Functions:**
- Execute playbooks on target hosts
- Stream playbook output
- Track execution status
- Handle failures

---

## Technology Stack

### Core Technologies

**Programming Language:**
- Python 3.12+
- Type hints for all public APIs
- Async/await for I/O operations

**API Framework:**
- FastAPI 0.104+
- Uvicorn (ASGI server)
- Pydantic for request/response validation

**Workflow Engine:**
- Temporal 1.5+
- Durable workflows with state persistence
- Activity-based architecture

**Database:**
- PostgreSQL 15+
- SQLAlchemy 2.0 (async mode)
- Alembic for migrations

**Package Manager:**
- uv (ultra-fast Python package installer)
- pyproject.toml for project configuration

**Cloud Provider:**
- OpenStack (Nova, Neutron, Keystone, Cinder)
- Direct REST API calls

**Configuration Management:**
- Ansible 2.15+
- ansible-runner for programmatic execution

**Containerization:**
- Docker
- Docker Compose for local development
- Kubernetes for production

### Supporting Libraries

**HTTP Clients:**
- httpx (async HTTP client)
- requests (sync fallback)

**Logging:**
- structlog (structured logging)
- Python logging stdlib

**Metrics:**
- prometheus-client
- FastAPI Prometheus middleware

**Testing:**
- pytest 7.4+
- pytest-asyncio
- pytest-cov (>90% coverage requirement)
- pytest-mock
- httpx (for mocking HTTP calls)

**Code Quality:**
- ruff (linter + formatter)
- mypy (type checking)
- pre-commit hooks

**Development:**
- GitHub Actions (CI/CD)
- Dependabot (dependency updates)

### DevOps and Deployment

**Version Control:**
- Git / GitHub

**CI/CD:**
- GitHub Actions
- Automated testing on PR
- Coverage reporting
- Security scanning

**Code Quality:**
- ruff (all-in-one linter)
- mypy (type safety)
- pytest-cov (>90% coverage gate)

**Deployment:**
- Docker images
- Kubernetes manifests
- Helm charts
- Docker Compose for dev

**Monitoring:**
- Prometheus (metrics)
- Grafana (dashboards)
- Structured logs (JSON format)

---

## Project Structure

### Repository Organization

```
modern-orchestrator/
├── src/
│   └── orchestrator/
│       ├── main.py                 # FastAPI app
│       ├── config.py               # Settings
│       ├── logging.py              # Logging setup
│       ├── metrics.py              # Prometheus metrics
│       ├── api/
│       │   ├── v1/
│       │   │   ├── deployments.py  # Deployment endpoints
│       │   │   ├── configurations.py # Config endpoints
│       │   │   └── scaling.py      # Scaling endpoints
│       │   ├── health.py           # Health check
│       │   └── middleware/
│       │       ├── auth.py         # Authentication
│       │       ├── logging.py      # Request logging
│       │       └── errors.py       # Error handling
│       ├── services/
│       │   ├── deployment_service.py
│       │   └── cache.py
│       ├── workflows/
│       │   ├── client.py           # Temporal client
│       │   ├── worker.py           # Worker factory
│       │   ├── base.py             # Base classes
│       │   ├── deployment/
│       │   │   ├── deploy.py       # Deploy workflow
│       │   │   ├── delete.py       # Delete workflow
│       │   │   ├── update.py       # Update workflow
│       │   │   ├── activities.py   # Activities
│       │   │   └── models.py       # Workflow models
│       │   ├── configuration/
│       │   │   ├── configure.py
│       │   │   └── activities.py
│       │   └── scaling/
│       │       ├── scale.py
│       │       └── activities.py
│       ├── clients/
│       │   ├── openstack/
│       │   │   ├── client.py       # OpenStack client
│       │   │   └── schemas.py      # API schemas
│       │   └── ansible/
│       │       └── client.py       # Ansible client
│       ├── db/
│       │   ├── connection.py       # DB connection
│       │   └── repositories/
│       │       └── deployment_repository.py
│       ├── models/
│       │   ├── base.py             # Base model
│       │   ├── deployment.py       # Deployment model
│       │   └── template.py         # Template model
│       ├── schemas/
│       │   ├── deployment.py       # Deployment schemas
│       │   ├── configuration.py    # Config schemas
│       │   └── scaling.py          # Scaling schemas
│       └── utils/
│           ├── retry.py            # Retry logic
│           └── circuit_breaker.py  # Circuit breaker
├── tests/
│   ├── unit/
│   │   ├── models/
│   │   ├── clients/
│   │   ├── services/
│   │   ├── workflows/
│   │   └── api/
│   ├── integration/
│   │   ├── test_deploy_flow.py
│   │   ├── test_delete_flow.py
│   │   ├── test_configure_flow.py
│   │   └── test_scaling_flow.py
│   └── fixtures/
│       ├── openstack_responses.py
│       ├── temporal_mocks.py
│       └── deployment_fixtures.py
├── migrations/                     # Alembic migrations
│   ├── env.py
│   └── versions/
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
├── k8s/                           # Kubernetes manifests
│   ├── deployment.yaml
│   ├── service.yaml
│   └── configmap.yaml
├── helm/                          # Helm charts
│   └── orchestrator/
│       ├── Chart.yaml
│       ├── values.yaml
│       └── templates/
├── monitoring/
│   ├── alerts.yaml                # Prometheus alerts
│   └── dashboards/                # Grafana dashboards
├── docs/
│   ├── deployment.md
│   ├── user-guide.md
│   └── runbook.md
├── .github/
│   └── workflows/
│       └── ci.yml                 # GitHub Actions
├── pyproject.toml                 # Project config
├── .env.example                   # Environment variables
└── README.md
```

---

## Data Models

### Deployment

**Purpose:** Track infrastructure deployment state

**Schema:**
```python
class Deployment(BaseModel):
    id: UUID
    name: str
    status: DeploymentStatus  # PENDING, IN_PROGRESS, COMPLETED, FAILED, DELETING
    template: dict  # Deployment template (VMs, networks)
    parameters: dict  # User-provided parameters
    cloud_region: str  # OpenStack region
    resources: dict  # Created resource IDs (VMs, networks)
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime]
```

**Lifecycle:**
1. PENDING: Created, workflow not started
2. IN_PROGRESS: Workflow executing
3. COMPLETED: Successfully deployed
4. FAILED: Deployment failed
5. DELETING: Teardown in progress

### DeploymentTemplate

**Purpose:** Reusable deployment templates

**Schema:**
```python
class DeploymentTemplate(BaseModel):
    id: UUID
    name: str
    description: str
    vm_config: dict  # VM configuration (flavor, image, count)
    network_config: dict  # Network configuration (CIDR, subnets)
    created_at: datetime
    updated_at: datetime
```

**Example Template:**
```json
{
  "name": "web-app-stack",
  "description": "3-tier web application",
  "vm_config": {
    "web": {
      "flavor": "m1.small",
      "image": "ubuntu-22.04",
      "count": 2
    },
    "app": {
      "flavor": "m1.medium",
      "image": "ubuntu-22.04",
      "count": 3
    },
    "db": {
      "flavor": "m1.large",
      "image": "ubuntu-22.04",
      "count": 1
    }
  },
  "network_config": {
    "cidr": "10.0.0.0/16",
    "subnets": {
      "web": "10.0.1.0/24",
      "app": "10.0.2.0/24",
      "db": "10.0.3.0/24"
    }
  }
}
```

---

## Operational Model

### Deployment Architecture

**Development:**
- Docker Compose with all dependencies
- Local PostgreSQL and Temporal
- Mock OpenStack (Mimic or DevStack)

**Production:**
- Kubernetes deployment
- Managed PostgreSQL (RDS, Cloud SQL, or self-hosted)
- Temporal Cloud or self-hosted Temporal cluster
- Production OpenStack

**Scaling Considerations:**
- Horizontal scaling of API pods
- Worker pools for Temporal activities
- PostgreSQL read replicas for queries
- Redis for caching (future)

### Request Flow Example

**Deployment Creation Flow:**

1. **Client** sends POST request:
   ```
   POST /deployments
   Content-Type: application/json

   {
     "name": "my-app",
     "template": "web-app-stack",
     "cloud_region": "us-west-1",
     "parameters": {
       "web_count": 2
     }
   }
   ```

2. **API Layer** receives request:
   - Validates request schema (Pydantic)
   - Authenticates client (API key)
   - Returns 202 Accepted with deployment ID

3. **Service Layer** processes:
   - Validates template exists
   - Creates deployment record (status: PENDING)
   - Starts Temporal workflow
   - Updates status to IN_PROGRESS
   - Returns deployment ID

4. **Temporal Workflow** executes:
   - `create_network` activity:
     - Call OpenStack Neutron API
     - Create network, subnet, router
     - Return network ID
   - `create_vm` activity (for each VM):
     - Call OpenStack Nova API
     - Create VM instance
     - Return VM ID
   - `poll_vm_status` activity:
     - Poll Nova API until VM is ACTIVE
     - Retry on transient errors
   - `update_deployment_status` activity:
     - Update deployment record
     - Set status to COMPLETED
     - Store resource IDs

5. **Client** polls for status:
   ```
   GET /deployments/{id}
   ```

   Response:
   ```json
   {
     "id": "uuid",
     "name": "my-app",
     "status": "COMPLETED",
     "resources": {
       "network_id": "net-123",
       "vm_ids": ["vm-456", "vm-789"]
     },
     "created_at": "2025-01-15T10:30:00Z",
     "updated_at": "2025-01-15T10:35:00Z"
   }
   ```

### Monitoring and Observability

**Logging:**
- Structured JSON logs (structlog)
- Log levels: DEBUG, INFO, WARNING, ERROR
- Request ID tracking across all logs
- Correlation IDs for workflow tracing

**Metrics (Prometheus):**
- `deployments_total{status}`: Total deployments by status
- `deployment_duration_seconds{status}`: Deployment duration histogram
- `openstack_api_calls_total{method, status}`: OpenStack API call metrics
- `workflow_execution_duration_seconds{workflow}`: Workflow execution time
- `api_request_duration_seconds{endpoint, method}`: API response time
- `database_query_duration_seconds{operation}`: Database query time

**Health Checks:**
- `/health`: Liveness probe (API is running)
- `/health/ready`: Readiness probe (dependencies available)
  - PostgreSQL connection
  - Temporal connection
  - OpenStack API reachability

**Tracing (Future):**
- OpenTelemetry integration
- Distributed tracing across workflows
- Span correlation

---

## Security

### Authentication and Authorization

**API Security:**
- API key authentication
- HTTP Bearer token
- Key rotation support
- Rate limiting per key

**Configuration:**
```python
# .env
API_KEY_HEADER=X-API-Key
API_KEYS=key1:write,key2:read
RATE_LIMIT_PER_MINUTE=100
```

**Authorization Levels:**
- `read`: GET endpoints only
- `write`: Full CRUD access

### Secrets Management

**Database Credentials:**
- Environment variables
- Kubernetes secrets
- Vault integration (future)

**OpenStack Credentials:**
- Encrypted in database
- Rotation support
- Per-cloud-region credentials

**Ansible SSH Keys:**
- Stored in Kubernetes secrets
- Mounted as files in worker pods

### Input Validation

**All inputs validated:**
- Pydantic schemas for API requests
- SQL injection prevention (SQLAlchemy ORM)
- SSRF prevention (whitelist OpenStack endpoints)
- Path traversal prevention (no user-provided file paths)

### Security Scanning

**Practices:**
- Dependabot for dependency updates
- Bandit for Python security linting
- Trivy for container scanning
- OWASP Top 10 compliance

---

## Development Workflow

### Building the Project

**Prerequisites:**
- Python 3.12+
- uv package manager
- Docker (for local testing)

**Setup:**
```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone repository
git clone https://github.com/org/modern-orchestrator.git
cd modern-orchestrator

# Install dependencies
uv sync

# Setup environment
cp .env.example .env

# Start dependencies (PostgreSQL, Temporal)
docker compose up -d

# Run migrations
uv run alembic upgrade head

# Start API server
uv run uvicorn src.orchestrator.main:app --reload

# Start Temporal worker (separate terminal)
uv run python -m src.orchestrator.workflows.worker
```

### Testing

**Run Tests:**
```bash
# All tests
uv run pytest

# Unit tests only
uv run pytest tests/unit/

# Integration tests
uv run pytest tests/integration/

# With coverage
uv run pytest --cov=src/orchestrator --cov-report=html

# Coverage requirement: >90%
uv run pytest --cov=src/orchestrator --cov-fail-under=90
```

**Test Strategy:**
- Unit tests: Pure logic, mocked dependencies
- Integration tests: Full flow with mock OpenStack
- E2E tests: Against real OpenStack (CI only)

### Code Quality

**Linting and Formatting:**
```bash
# Lint
uv run ruff check .

# Format
uv run ruff format .

# Type check
uv run mypy src/
```

**Pre-commit Hooks:**
```bash
# Install
uv run pre-commit install

# Run manually
uv run pre-commit run --all-files
```

### Workflow Development

**Creating a New Workflow:**

1. Define workflow in `src/orchestrator/workflows/<module>/<workflow>.py`
2. Define activities in `src/orchestrator/workflows/<module>/activities.py`
3. Write unit tests in `tests/unit/workflows/test_<workflow>.py`
4. Register workflow in worker
5. Trigger from service layer

**Example:**
```python
# workflows/deployment/deploy.py
from temporalio import workflow

@workflow.defn
class DeployWorkflow:
    @workflow.run
    async def run(self, deployment_id: str) -> dict:
        # Workflow logic
        network_id = await workflow.execute_activity(
            create_network,
            args=[deployment_id],
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=RetryPolicy(maximum_attempts=3)
        )
        return {"network_id": network_id}
```

---

## Configuration Management

### Environment Variables

**Required:**
```bash
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/orchestrator

# Temporal
TEMPORAL_HOST=localhost:7233
TEMPORAL_NAMESPACE=default

# OpenStack
OPENSTACK_AUTH_URL=http://openstack:5000/v3
OPENSTACK_USERNAME=admin
OPENSTACK_PASSWORD=secret
OPENSTACK_PROJECT_NAME=admin

# API
API_HOST=0.0.0.0
API_PORT=8000
API_WORKERS=4

# Security
API_KEYS=key1:write,key2:read
SECRET_KEY=your-secret-key-here

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json
```

**Optional:**
```bash
# Caching
REDIS_URL=redis://localhost:6379/0
CACHE_TTL_SECONDS=300

# Monitoring
PROMETHEUS_PORT=9090
SENTRY_DSN=https://...

# Ansible
ANSIBLE_SSH_KEY_PATH=/keys/ansible_rsa
ANSIBLE_VERBOSITY=0
```

### Configuration File

**config.py using Pydantic Settings:**
```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str
    temporal_host: str
    openstack_auth_url: str
    api_keys: str
    log_level: str = "INFO"

    class Config:
        env_file = ".env"

settings = Settings()
```

---

## API Reference

### Deployments

**Create Deployment**
```http
POST /deployments
Content-Type: application/json
X-API-Key: your-api-key

{
  "name": "my-deployment",
  "template": "web-app-stack",
  "cloud_region": "us-west-1",
  "parameters": {
    "web_count": 2
  }
}

Response: 202 Accepted
{
  "id": "uuid",
  "name": "my-deployment",
  "status": "PENDING"
}
```

**Get Deployment**
```http
GET /deployments/{id}
X-API-Key: your-api-key

Response: 200 OK
{
  "id": "uuid",
  "name": "my-deployment",
  "status": "COMPLETED",
  "resources": {
    "network_id": "net-123",
    "vm_ids": ["vm-456"]
  },
  "created_at": "2025-01-15T10:30:00Z"
}
```

**List Deployments**
```http
GET /deployments?status=COMPLETED&limit=10&offset=0
X-API-Key: your-api-key

Response: 200 OK
{
  "items": [...],
  "total": 42,
  "limit": 10,
  "offset": 0
}
```

**Delete Deployment**
```http
DELETE /deployments/{id}
X-API-Key: your-api-key

Response: 202 Accepted
{
  "id": "uuid",
  "status": "DELETING"
}
```

### Configuration

**Apply Configuration**
```http
POST /deployments/{id}/configure
Content-Type: application/json
X-API-Key: your-api-key

{
  "playbook": "configure-web.yml",
  "inventory": {
    "web_servers": ["10.0.1.10", "10.0.1.11"]
  },
  "extra_vars": {
    "app_port": 8080
  }
}

Response: 202 Accepted
{
  "deployment_id": "uuid",
  "status": "CONFIGURING"
}
```

### Scaling

**Scale Deployment**
```http
POST /deployments/{id}/scale
Content-Type: application/json
X-API-Key: your-api-key

{
  "target_count": 5,
  "vm_type": "web"
}

Response: 202 Accepted
{
  "deployment_id": "uuid",
  "status": "SCALING"
}
```

---

## Comparison: Legacy vs Modern

| Aspect | Legacy ONAP SO | Modern Orchestrator |
|--------|---------------|---------------------|
| **Language** | Java 8 | Python 3.12+ |
| **API Framework** | JBoss/JAX-RS | FastAPI |
| **Workflow Engine** | Camunda BPMN | Temporal |
| **Database** | MariaDB (3 separate DBs) | PostgreSQL (single DB) |
| **Inventory** | A&AI (complex inventory system) | PostgreSQL tables |
| **Model Distribution** | SDC/TOSCA parsing | Simple JSON templates |
| **Network Provisioning** | SDN-C adapter | Direct Neutron API |
| **Configuration** | APPC (complex LCM) | Ansible playbooks |
| **Optimization** | OOF (ML-based placement) | Simple placement rules |
| **Build System** | Maven | uv |
| **Lines of Code** | 390,267 (production) | ~15,000 (est.) |
| **Tests** | 502 tests (45 min) | 116 tests (8 min) |
| **Task Count** | 295 tasks | 158 tasks |
| **Timeline** | 6-9 months | 4-6 weeks MVP |
| **Complexity** | High (7 ONAP integrations) | Low (direct APIs) |
| **Maintainability** | Low | High |
| **Developer Velocity** | Slow | Fast |

---

## Roadmap

### MVP (Weeks 1-4)
- Phase 1: Project setup
- Phase 2: Core platform (US0)
- Phase 3: Deploy infrastructure (US1)
- Phase 4: Delete deployments (US2 - partial)

**Delivers:**
- Deploy VMs and networks on OpenStack
- Track deployment status
- Delete deployments with cleanup
- Basic error handling

### v1.0 (Weeks 5-6)
- Phase 4: Update deployments (US2 - complete)
- Phase 5: Configuration management (US3)
- Phase 6: Scaling (US4)

**Delivers:**
- Full deployment lifecycle
- Ansible-based configuration
- Horizontal scaling

### v1.1 (Week 7+)
- Phase 7: Production hardening
  - Security (auth, rate limiting)
  - Performance (caching, indexes)
  - Resilience (retries, circuit breakers)
  - Monitoring (alerts, dashboards)
  - Documentation

**Delivers:**
- Production-ready platform
- Complete observability
- Comprehensive documentation

### Future Enhancements
- Multi-cloud support (AWS, Azure, GCP)
- Web UI
- CLI tool
- Terraform provider
- Auto-scaling based on metrics
- Cost optimization recommendations
- Template marketplace

---

## Conclusion

The Modern Infrastructure Orchestrator demonstrates that **simplicity beats complexity**. By applying first principles thinking, we've created a platform that:

**Eliminates Unnecessary Complexity:**
- 77% fewer tests (502 → 116)
- 46% fewer tasks (295 → 158)
- No unnecessary integrations (A&AI, SDC, SDN-C, APPC, OOF removed)

**Delivers Core Value:**
- Deploy infrastructure reliably
- Manage lifecycle cleanly
- Configure with industry-standard tools
- Scale elastically

**Built for Modern Teams:**
- Python 3.12+ (developer-friendly)
- FastAPI (high performance, easy to learn)
- Temporal (reliable workflows out of the box)
- PostgreSQL (battle-tested, simple)

**Timeline:** 4-6 weeks to MVP vs 6-9 months for legacy approach.

This platform proves that you don't need enterprise complexity to solve infrastructure orchestration. **Direct APIs + Modern workflows + Clean architecture = Simple, reliable, maintainable orchestration.**