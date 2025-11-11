#!/bin/bash
# Script to test CI checks locally before pushing

set -e

echo "======================================"
echo "Testing CI checks locally"
echo "======================================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print status
print_status() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✓ $2 passed${NC}"
    else
        echo -e "${RED}✗ $2 failed${NC}"
        return 1
    fi
}

echo ""
echo "1. Checking Poetry installation..."
if ! command -v poetry &> /dev/null; then
    echo -e "${RED}Poetry is not installed. Please install it first.${NC}"
    exit 1
fi
print_status 0 "Poetry check"

echo ""
echo "2. Installing dependencies..."
poetry install --no-interaction
print_status $? "Dependency installation"

echo ""
echo "3. Running linting checks..."
echo "   - Running ruff (lint)..."
poetry run ruff check . || LINT_FAILED=1
echo "   - Running ruff (format check)..."
poetry run ruff format --check . || FORMAT_FAILED=1

if [ -n "$LINT_FAILED" ] || [ -n "$FORMAT_FAILED" ]; then
    echo -e "${YELLOW}⚠ Linting issues found. Run 'poetry run ruff check --fix .' to fix.${NC}"
else
    print_status 0 "Linting"
fi

echo ""
echo "4. Running type checks..."
poetry run mypy src/ || TYPE_FAILED=1

if [ -n "$TYPE_FAILED" ]; then
    echo -e "${YELLOW}⚠ Type check issues found.${NC}"
else
    print_status 0 "Type checking"
fi

echo ""
echo "5. Running unit tests..."
export DATABASE_URL="postgresql+asyncpg://orchestrator:password@localhost:5432/orchestrator_test"
export TEMPORAL_HOST="localhost:7233"
export API_KEYS="test-key-1:write,test-key-2:read"
export SECRET_KEY="test-secret-key-minimum-32-characters-long-for-testing"
export OPENSTACK_AUTH_URL="http://fake:5000/v3"
export OPENSTACK_USERNAME="fake"
export OPENSTACK_PASSWORD="fake"
export OPENSTACK_PROJECT_NAME="fake"

poetry run pytest tests/unit/ --cov=src/orchestrator --cov-report=term-missing --cov-fail-under=80 -v
print_status $? "Unit tests"

echo ""
echo "6. Building package..."
poetry build
print_status $? "Package build"

echo ""
echo "7. Running security checks..."
poetry run pip install bandit[toml] > /dev/null 2>&1
poetry run bandit -r src/ || SECURITY_FAILED=1

if [ -n "$SECURITY_FAILED" ]; then
    echo -e "${YELLOW}⚠ Security issues found.${NC}"
else
    print_status 0 "Security scan"
fi

echo ""
echo "======================================"
if [ -n "$LINT_FAILED" ] || [ -n "$FORMAT_FAILED" ] || [ -n "$TYPE_FAILED" ] || [ -n "$SECURITY_FAILED" ]; then
    echo -e "${YELLOW}⚠ Some checks have warnings but tests passed${NC}"
    echo "Review the warnings above before pushing."
    exit 0
else
    echo -e "${GREEN}✓ All CI checks passed!${NC}"
    echo "Ready to push to remote."
    exit 0
fi
