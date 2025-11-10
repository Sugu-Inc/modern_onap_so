# Modern Infrastructure Orchestrator

A lightweight, cloud-native platform for deploying and managing infrastructure resources on OpenStack. Built from first principles with modern technologies for simplicity, reliability, and maintainability.

## Features

- **Simple Deployment**: Deploy VMs and networks with a single API call
- **Workflow Orchestration**: Reliable, durable workflows with Temporal
- **State Tracking**: Complete visibility into deployment status and history
- **Configuration Management**: Industry-standard Ansible for post-deployment configuration
- **Scalability**: Elastic scaling of deployed infrastructure

## Technology Stack

- **Language**: Python 3.12+
- **API Framework**: FastAPI + Uvicorn
- **Workflow Engine**: Temporal
- **Database**: PostgreSQL + SQLAlchemy (async)
- **Package Manager**: uv
- **Cloud Provider**: OpenStack (Nova, Neutron, Keystone)
- **Configuration**: Ansible
- **Testing**: pytest (>90% coverage required)

## Quick Start

### Prerequisites

- Python 3.12+
- uv package manager
- Docker and Docker Compose
- Access to an OpenStack environment

### Installation

1. **Install uv** (if not already installed):

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

2. **Clone the repository**:

```bash
git clone https://github.com/your-org/modern-orchestrator.git
cd modern-orchestrator
```

3. **Install dependencies**:

```bash
uv sync
```

4. **Setup environment**:

```bash
cp .env.example .env
# Edit .env with your configuration
```

5. **Start dependencies** (PostgreSQL, Temporal):

```bash
docker compose up -d
```

6. **Run database migrations**:

```bash
uv run alembic upgrade head
```

7. **Start the API server**:

```bash
uv run uvicorn src.orchestrator.main:app --reload
```

8. **Start Temporal worker** (in a separate terminal):

```bash
uv run python -m src.orchestrator.workflows.worker
```

### Verify Installation

```bash
# Check API health
curl http://localhost:8000/health

# Check API docs
open http://localhost:8000/docs
```

## Development

### Running Tests

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=src/orchestrator --cov-report=html

# Run only unit tests
uv run pytest tests/unit/

# Run only integration tests
uv run pytest tests/integration/
```

### Code Quality

```bash
# Lint code
uv run ruff check .

# Format code
uv run ruff format .

# Type check
uv run mypy src/
```

### Pre-commit Hooks

```bash
# Install pre-commit hooks
uv run pre-commit install

# Run manually
uv run pre-commit run --all-files
```

## Usage

### Deploy Infrastructure

```bash
curl -X POST http://localhost:8000/deployments \
  -H "X-API-Key: dev-key-1" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my-deployment",
    "template": "web-app-stack",
    "cloud_region": "RegionOne",
    "parameters": {
      "web_count": 2
    }
  }'
```

### Get Deployment Status

```bash
curl http://localhost:8000/deployments/{id} \
  -H "X-API-Key: dev-key-1"
```

### List Deployments

```bash
curl http://localhost:8000/deployments \
  -H "X-API-Key: dev-key-1"
```

### Delete Deployment

```bash
curl -X DELETE http://localhost:8000/deployments/{id} \
  -H "X-API-Key: dev-key-1"
```

## Project Structure

```
modern-orchestrator/
├── src/
│   └── orchestrator/
│       ├── main.py                 # FastAPI app
│       ├── config.py               # Settings
│       ├── logging.py              # Logging setup
│       ├── metrics.py              # Prometheus metrics
│       ├── api/                    # API endpoints
│       ├── clients/                # External clients (OpenStack, Ansible)
│       ├── db/                     # Database layer
│       ├── models/                 # SQLAlchemy models
│       ├── schemas/                # Pydantic schemas
│       ├── services/               # Business logic
│       ├── workflows/              # Temporal workflows
│       └── utils/                  # Utilities
├── tests/
│   ├── unit/                       # Unit tests
│   ├── integration/                # Integration tests
│   └── fixtures/                   # Test fixtures
├── migrations/                     # Alembic migrations
├── docker/                         # Docker configuration
├── k8s/                           # Kubernetes manifests
├── helm/                          # Helm charts
├── monitoring/                    # Monitoring config
├── docs/                          # Documentation
└── pyproject.toml                 # Project configuration
```

## Documentation

- [Technical Specification](spec.md) - Detailed architecture and design
- [System Flows](flows.md) - Data flows and orchestration patterns
- [Migration Plan](migration_plan.md) - Production migration strategy
- [Tasks](tasks.md) - Implementation task breakdown

## API Documentation

Interactive API documentation is available at:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests and linting (`pytest && ruff check .`)
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

## Testing Requirements

- Minimum 90% code coverage
- All tests must pass
- No linting errors
- Type checking must pass

## License

Apache 2.0

## Support

For issues and questions:
- GitHub Issues: https://github.com/your-org/modern-orchestrator/issues
- Documentation: See `docs/` directory

## Comparison to Legacy

This modern orchestrator simplifies infrastructure deployment compared to legacy ONAP SO:

| Aspect | Legacy ONAP SO | Modern Orchestrator |
|--------|---------------|---------------------|
| Lines of Code | 390,267 | ~15,000 |
| Tests | 502 (45 min) | 116 (8 min) |
| Tasks | 295 | 158 |
| Timeline | 6-9 months | 4-6 weeks MVP |
| Complexity | High (7 integrations) | Low (direct APIs) |

**Key Benefits:**
- 77% less test complexity
- 46% fewer tasks
- Direct API calls instead of multi-layer abstractions
- Modern Python stack instead of legacy Java
- Simple JSON templates instead of TOSCA parsing
