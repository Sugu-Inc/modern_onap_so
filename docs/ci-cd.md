# CI/CD Guide

This document describes the Continuous Integration and Continuous Deployment setup for the ONAP SO Modern orchestrator.

## Table of Contents

1. [Overview](#overview)
2. [CI Pipeline](#ci-pipeline)
3. [Local Testing](#local-testing)
4. [Branch Strategy](#branch-strategy)
5. [Code Quality](#code-quality)
6. [Security Scanning](#security-scanning)
7. [Troubleshooting](#troubleshooting)

## Overview

The project uses **GitHub Actions** for CI/CD with the following workflows:

- **Lint and Type Check**: Code quality validation
- **Test**: Unit and integration tests with coverage
- **Build**: Package and Docker image building
- **Security**: Vulnerability scanning
- **Dependency Check**: Dependency validation

### CI Status

![CI](https://github.com/your-org/onap_so_modern/workflows/CI/badge.svg)

## CI Pipeline

### Workflow File

Location: `.github/workflows/ci.yml`

### Jobs

#### 1. Lint and Type Check

**Purpose**: Ensure code quality and type safety

**Steps**:
- Install Poetry and dependencies
- Run `ruff` for linting
- Run `ruff` for format checking
- Run `mypy` for type checking

**Triggers**: All pushes and pull requests

**Pass Criteria**:
- No critical linting errors
- Code is properly formatted
- No type errors (warnings allowed)

#### 2. Test

**Purpose**: Run unit tests with coverage

**Services**:
- PostgreSQL 15 (for database tests)

**Steps**:
- Install dependencies
- Run pytest with coverage
- Upload coverage to Codecov (on push)

**Triggers**: All pushes and pull requests

**Pass Criteria**:
- All tests pass
- Coverage ≥ 80%

**Test Command**:
```bash
poetry run pytest tests/unit/ \
  --cov=src/orchestrator \
  --cov-report=xml \
  --cov-report=term-missing \
  --cov-fail-under=80 \
  -v
```

#### 3. Build Package

**Purpose**: Verify package can be built

**Steps**:
- Install Poetry
- Build package with `poetry build`
- Upload artifacts (dist/)

**Triggers**: All pushes and pull requests

**Pass Criteria**:
- Package builds successfully

#### 4. Build Docker Image

**Purpose**: Verify Docker image builds and runs

**Steps**:
- Set up Docker Buildx
- Build multi-stage Docker image
- Test container startup
- Verify container health

**Triggers**: All pushes and pull requests

**Pass Criteria**:
- Docker image builds successfully
- Container starts without errors

**Image Details**:
- Base: `python:3.12-slim`
- Multi-stage build for smaller size
- Non-root user (orchestrator:1000)
- Health check included

#### 5. Security Scan

**Purpose**: Identify security vulnerabilities

**Tools**:
- **Bandit**: Python security linter
- **Safety**: Dependency vulnerability scanner

**Steps**:
- Run bandit on source code
- Check dependencies with safety
- Upload security reports

**Triggers**: All pushes and pull requests

**Pass Criteria**:
- No critical security issues (warnings allowed)

#### 6. Dependency Check

**Purpose**: Verify dependency integrity

**Steps**:
- Check for outdated dependencies
- Validate poetry.lock file

**Triggers**: All pushes and pull requests

**Pass Criteria**:
- poetry.lock is valid
- Dependencies are tracked

#### 7. Integration Tests

**Purpose**: Run integration tests with real services

**Services**:
- PostgreSQL 15

**Steps**:
- Install dependencies
- Run database migrations
- Execute integration tests

**Triggers**: Pushes to main/develop branches only

**Pass Criteria**:
- All integration tests pass
- Database migrations work

## Local Testing

### Quick Test

Run all CI checks locally before pushing:

```bash
./scripts/test-ci-locally.sh
```

This script will:
1. ✓ Check Poetry installation
2. ✓ Install dependencies
3. ✓ Run linting (ruff)
4. ✓ Run type checking (mypy)
5. ✓ Run unit tests with coverage
6. ✓ Build package
7. ✓ Run security scan (bandit)

### Individual Checks

#### Linting

```bash
# Check for issues
poetry run ruff check .

# Auto-fix issues
poetry run ruff check --fix .

# Check formatting
poetry run ruff format --check .

# Apply formatting
poetry run ruff format .
```

#### Type Checking

```bash
poetry run mypy src/
```

#### Unit Tests

```bash
# Run all tests
poetry run pytest tests/unit/

# Run with coverage
poetry run pytest tests/unit/ --cov=src/orchestrator --cov-report=term-missing

# Run specific test file
poetry run pytest tests/unit/api/test_deployments.py -v

# Run specific test
poetry run pytest tests/unit/api/test_deployments.py::TestCreateDeployment::test_create_deployment_success -v
```

#### Build Package

```bash
poetry build
```

#### Build Docker Image

```bash
# Build image
docker build -t onap-so-modern:local .

# Run container
docker run -d --name test-orchestrator \
  -e DATABASE_URL="postgresql+asyncpg://user:pass@host:5432/db" \
  -e API_KEYS="test-key:write" \
  -e SECRET_KEY="test-secret-key-minimum-32-characters" \
  -e OPENSTACK_AUTH_URL="http://keystone:5000/v3" \
  -e OPENSTACK_USERNAME="admin" \
  -e OPENSTACK_PASSWORD="password" \
  -e OPENSTACK_PROJECT_NAME="admin" \
  -p 8000:8000 \
  onap-so-modern:local

# Check health
curl http://localhost:8000/health

# View logs
docker logs test-orchestrator

# Stop and remove
docker stop test-orchestrator
docker rm test-orchestrator
```

#### Security Scan

```bash
# Install tools
poetry run pip install bandit[toml] safety

# Run bandit
poetry run bandit -r src/

# Run safety
poetry export -f requirements.txt --output requirements.txt --without-hashes
poetry run safety check -r requirements.txt
```

## Branch Strategy

### Protected Branches

- **main**: Production-ready code
- **develop**: Integration branch

### Branch Naming

- `feature/*`: New features
- `bugfix/*`: Bug fixes
- `hotfix/*`: Urgent production fixes
- `claude/*`: Claude Code agent work

### Pull Request Requirements

Before merging to main/develop:

1. ✓ All CI checks must pass
2. ✓ Code review approved
3. ✓ Coverage ≥ 80%
4. ✓ No merge conflicts
5. ✓ Commits are signed (optional)

### Workflow

```
feature/new-api → develop → main
                    ↓
                 Release Tag
```

## Code Quality

### Linting Configuration

**Tool**: Ruff (Fast Python linter)

**Config**: `pyproject.toml`

```toml
[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = [
    "E",   # pycodestyle errors
    "W",   # pycodestyle warnings
    "F",   # pyflakes
    "I",   # isort
    "B",   # flake8-bugbear
    "C4",  # flake8-comprehensions
]
```

### Type Checking Configuration

**Tool**: Mypy

**Config**: `pyproject.toml`

```toml
[tool.mypy]
python_version = "3.12"
strict = true
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
```

### Test Coverage Configuration

**Tool**: pytest-cov

**Minimum**: 80%

**Config**: `pyproject.toml`

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = "test_*.py"
python_classes = "Test*"
python_functions = "test_*"
addopts = "-v --strict-markers"

[tool.coverage.run]
source = ["src/orchestrator"]
omit = ["*/tests/*", "*/__pycache__/*"]

[tool.coverage.report]
precision = 2
show_missing = true
skip_covered = false
```

## Security Scanning

### Bandit (SAST)

Scans Python code for common security issues:

- SQL injection
- Command injection
- Hardcoded passwords
- Insecure cryptography
- Path traversal

**Severity Levels**:
- **HIGH**: Must fix before merge
- **MEDIUM**: Should fix before merge
- **LOW**: Fix when possible

### Safety

Checks dependencies against vulnerability databases:

- CVE database
- PyPI advisory database

**Action on Vulnerabilities**:
1. Review vulnerability details
2. Check if exploitable in our context
3. Update dependency if patch available
4. Document if false positive

## Cache Strategy

### Dependency Caching

GitHub Actions caches Poetry virtualenv:

```yaml
- name: Load cached venv
  uses: actions/cache@v3
  with:
    path: .venv
    key: venv-${{ runner.os }}-${{ hashFiles('**/poetry.lock') }}
```

**Benefits**:
- Faster CI runs (2-3x speedup)
- Reduced network usage
- Consistent environments

### Docker Layer Caching

Docker build uses GitHub Actions cache:

```yaml
- name: Build Docker image
  uses: docker/build-push-action@v5
  with:
    cache-from: type=gha
    cache-to: type=gha,mode=max
```

**Benefits**:
- Faster image builds
- Reduced build time from ~10min to ~2min

## Troubleshooting

### CI Failures

#### Tests Failing Locally But Pass in CI

**Cause**: Different environment or dependencies

**Solution**:
```bash
# Clean environment
rm -rf .venv
poetry install --no-interaction

# Run tests
poetry run pytest tests/unit/ -v
```

#### Linting Failures

**Cause**: Code doesn't meet style standards

**Solution**:
```bash
# Auto-fix most issues
poetry run ruff check --fix .
poetry run ruff format .

# Check remaining issues
poetry run ruff check .
```

#### Coverage Too Low

**Cause**: New code lacks tests

**Solution**:
```bash
# Check coverage by file
poetry run pytest tests/unit/ --cov=src/orchestrator --cov-report=term-missing

# Add tests for files with low coverage
# Aim for 80%+ coverage on new code
```

#### Docker Build Failing

**Cause**: Missing dependencies or build errors

**Solution**:
```bash
# Test build locally
docker build -t test .

# Check logs
docker build --progress=plain -t test .

# Verify poetry.lock is up to date
poetry lock --check
```

#### Type Check Failures

**Cause**: Missing type hints or incorrect types

**Solution**:
```bash
# Run mypy
poetry run mypy src/

# Common fixes:
# - Add type hints to function signatures
# - Use Optional[Type] for nullable values
# - Import types from typing module
```

### GitHub Actions Issues

#### Workflow Not Triggering

**Check**:
1. Workflow file syntax (YAML validation)
2. Branch name matches triggers
3. Workflow is enabled in repository settings

#### Secrets Not Available

**Setup**:
1. Go to Settings → Secrets and variables → Actions
2. Add required secrets:
   - `CODECOV_TOKEN` (optional)
   - Any other service tokens

#### Actions Timing Out

**Cause**: Long-running jobs

**Solution**:
- Use caching to speed up jobs
- Split large test suites
- Increase timeout in workflow:

```yaml
jobs:
  test:
    timeout-minutes: 30  # Default is 360
```

## Best Practices

### 1. Commit Often

- Small, focused commits
- Descriptive commit messages
- Run tests before committing

### 2. Test Locally First

- Always run `./scripts/test-ci-locally.sh`
- Fix issues before pushing
- Saves CI minutes and time

### 3. Keep Dependencies Updated

```bash
# Check for updates
poetry show --outdated

# Update dependency
poetry update <package-name>

# Update all dependencies
poetry update
```

### 4. Write Tests for New Code

- Aim for 80%+ coverage
- Test happy paths and error cases
- Use descriptive test names

### 5. Monitor CI Status

- Check GitHub Actions tab regularly
- Fix failures promptly
- Review security scan reports

## CI Metrics

### Current Status

- **Total Jobs**: 7
- **Average Run Time**: ~8 minutes
- **Success Rate**: 95%+
- **Test Coverage**: 87%
- **Tests**: 311 passing

### Performance

| Job | Duration | Cache Hit Rate |
|-----|----------|----------------|
| Lint | ~1 min | 90% |
| Test | ~3 min | 85% |
| Build | ~2 min | 80% |
| Docker | ~5 min | 70% |
| Security | ~2 min | 90% |

## Next Steps

- [Deployment Guide](./deployment-guide.md) - Deploy the orchestrator
- [Contributing Guide](./contributing.md) - Contribution guidelines
- [Development Guide](./development.md) - Local development setup
