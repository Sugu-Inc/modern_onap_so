# Test Strategy

This project follows a clear separation between unit and integration tests.

## Test Structure

```
tests/
├── unit/           # Fast tests with no external dependencies
├── integration/    # Tests requiring database or external services
└── fixtures/       # Shared test fixtures
```

## Unit Tests (`tests/unit/`)

**Characteristics:**
- ✅ Fast execution (< 1 second total)
- ✅ No external dependencies (no database, no network)
- ✅ Test business logic and validation
- ✅ Use mocks for external dependencies when needed

**What we test:**
- Configuration validation (`test_config.py`)
- Model properties and business logic (`test_deployment.py`)
- Pure Python functions and classes

**Run unit tests:**
```bash
pytest tests/unit/ -v
```

## Integration Tests (`tests/integration/`)

**Characteristics:**
- ⚠️ Require external services (PostgreSQL, etc.)
- ⚠️ Slower execution
- ✅ Test real database operations
- ✅ Test end-to-end workflows

**What we test:**
- Database connection (`test_db_connection.py`)
- Repository CRUD operations (`test_deployment_repository.py`)
- API endpoints (when added)
- Temporal workflows (when added)

**Run integration tests:**
```bash
# Requires running PostgreSQL (via Docker Compose)
docker compose -f docker/docker-compose.yml up -d postgres
pytest tests/integration/ -v -m integration
```

## Test Philosophy

### What We Test
1. **Our Code**: Business logic, validation, transformations
2. **Integration Points**: Database queries, API calls, external services

### What We Don't Test
1. **Framework Behavior**: SQLAlchemy ORM defaults, FastAPI routing (already tested by frameworks)
2. **Third-Party Libraries**: Pydantic validation internals (trust the library)

### Example: Deployment Model Tests

❌ **Bad** (Testing SQLAlchemy, not our code):
```python
def test_deployment_id_auto_generated():
    deployment = Deployment(name="test")
    assert deployment.id is not None  # SQLAlchemy default
```

✅ **Good** (Testing our business logic):
```python
def test_deployment_is_deletable():
    deployment = Deployment(status=DeploymentStatus.COMPLETED)
    assert deployment.is_deletable is True  # Our logic
```

## Running Tests

### All Tests
```bash
pytest
```

### Unit Tests Only (Fast)
```bash
pytest tests/unit/
```

### Integration Tests Only
```bash
pytest tests/integration/ -m integration
```

### With Coverage
```bash
pytest --cov=src/orchestrator --cov-report=html
```

### Specific Test
```bash
pytest tests/unit/test_config.py::TestSettings::test_api_keys_validation -v
```

## Test Markers

Tests are marked for easy filtering:

- `@pytest.mark.unit` - Unit tests (auto-applied to `tests/unit/`)
- `@pytest.mark.integration` - Integration tests (requires external services)
- `@pytest.mark.slow` - Slow tests (> 5 seconds)

## CI/CD

**GitHub Actions runs:**
1. Unit tests (always)
2. Integration tests (with PostgreSQL service)
3. Coverage enforcement (>90% for production code)

## Current Status

✅ **Unit Tests**: 23 tests, all passing
- Config: 11 tests
- Models: 12 tests

⚠️ **Integration Tests**: Require PostgreSQL setup
- Database connection: 9 tests
- Repository: 25 tests

## Best Practices

1. **Fast Feedback**: Unit tests should run in <1 second
2. **Isolation**: Each test is independent (no shared state)
3. **Clarity**: Test names describe what they're testing
4. **Coverage**: Aim for >90% on business logic
5. **Pragmatic**: Don't test framework behavior

## Adding New Tests

### For a New Model
```python
# tests/unit/models/test_my_model.py
def test_my_model_creation():
    model = MyModel(name="test")
    assert model.name == "test"

def test_my_model_business_logic():
    model = MyModel(status="active")
    assert model.is_active is True
```

### For a New Repository
```python
# tests/integration/test_my_repository.py
import pytest

pytestmark = pytest.mark.integration

@pytest.fixture
async def async_session():
    # Setup database session
    ...

async def test_repository_create(async_session):
    repo = MyRepository(async_session)
    result = await repo.create(...)
    assert result is not None
```

## Troubleshooting

### "asyncio_mode" warning
Fixed in pyproject.toml:
```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
```

### SQLite vs PostgreSQL
- Unit tests: Use mocks or don't test DB-specific behavior
- Integration tests: Use SQLite or PostgreSQL
- Production: PostgreSQL only

### Import errors
Ensure you're running from project root:
```bash
cd /path/to/onap_so_modern
pytest
```
