# ONAP SO Modern - Deployment Guide

This guide provides comprehensive instructions for deploying the ONAP SO Modern infrastructure orchestrator in production and development environments.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Environment Setup](#environment-setup)
3. [Database Setup](#database-setup)
4. [Configuration](#configuration)
5. [Deployment Options](#deployment-options)
6. [Security Configuration](#security-configuration)
7. [Monitoring Setup](#monitoring-setup)
8. [Troubleshooting](#troubleshooting)

## Prerequisites

### System Requirements

- **OS**: Linux (Ubuntu 20.04+, RHEL 8+, or compatible)
- **Python**: 3.12 or higher
- **Memory**: Minimum 4GB RAM (8GB+ recommended for production)
- **CPU**: 2+ cores (4+ recommended for production)
- **Disk**: 20GB+ available space

### Required Services

- **PostgreSQL**: 14.0 or higher
- **Temporal**: Latest version for workflow orchestration
- **OpenStack**: Compatible cloud environment
- **Redis**: 6.0+ (optional, for caching)

### Development Tools

- **Poetry**: For Python dependency management
- **Docker**: For containerized deployments (optional)
- **Docker Compose**: For local development (optional)

## Environment Setup

### 1. Install Python Dependencies

```bash
# Install Poetry (if not already installed)
curl -sSL https://install.python-poetry.org | python3 -

# Clone the repository
git clone https://github.com/your-org/onap_so_modern.git
cd onap_so_modern

# Install dependencies
poetry install

# Activate virtual environment
poetry shell
```

### 2. Install PostgreSQL

#### Ubuntu/Debian
```bash
sudo apt update
sudo apt install postgresql postgresql-contrib
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

#### RHEL/CentOS
```bash
sudo dnf install postgresql-server postgresql-contrib
sudo postgresql-setup --initdb
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

### 3. Install Temporal

```bash
# Using Docker Compose (recommended for development)
git clone https://github.com/temporalio/docker-compose.git temporal-docker
cd temporal-docker
docker-compose up -d

# Or install Temporal server natively
# Follow instructions at: https://docs.temporal.io/docs/server/quick-install
```

## Database Setup

### 1. Create Database and User

```bash
# Connect to PostgreSQL
sudo -u postgres psql

# Create database and user
CREATE DATABASE orchestrator;
CREATE USER orchestrator WITH ENCRYPTED PASSWORD 'your-secure-password';
GRANT ALL PRIVILEGES ON DATABASE orchestrator TO orchestrator;

# Exit PostgreSQL
\q
```

### 2. Run Database Migrations

```bash
# Set database URL
export DATABASE_URL="postgresql+asyncpg://orchestrator:your-secure-password@localhost:5432/orchestrator"

# Run Alembic migrations
poetry run alembic upgrade head
```

### 3. Verify Database Setup

```bash
# Connect to database
psql -U orchestrator -d orchestrator -h localhost

# List tables
\dt

# You should see: deployments, alembic_version
```

## Configuration

### 1. Create Environment File

Create a `.env` file in the project root:

```bash
# Database Configuration
DATABASE_URL=postgresql+asyncpg://orchestrator:your-password@localhost:5432/orchestrator
DB_POOL_SIZE=10
DB_MAX_OVERFLOW=20
DB_POOL_TIMEOUT=30
DB_POOL_RECYCLE=3600

# Temporal Configuration
TEMPORAL_HOST=localhost:7233
TEMPORAL_NAMESPACE=default
TEMPORAL_TASK_QUEUE=orchestrator-tasks

# OpenStack Configuration
OPENSTACK_AUTH_URL=http://your-openstack:5000/v3
OPENSTACK_USERNAME=admin
OPENSTACK_PASSWORD=your-openstack-password
OPENSTACK_PROJECT_NAME=admin
OPENSTACK_PROJECT_DOMAIN_NAME=Default
OPENSTACK_USER_DOMAIN_NAME=Default
OPENSTACK_REGION_NAME=RegionOne

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
API_WORKERS=4
API_RELOAD=false

# Security Configuration
API_KEYS=prod-key-1:write,prod-key-2:read
SECRET_KEY=your-very-secure-secret-key-minimum-32-characters-long
RATE_LIMIT_ENABLED=true
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_WINDOW_SECONDS=60

# Logging Configuration
LOG_LEVEL=INFO
LOG_FORMAT=json

# Caching Configuration (Optional)
REDIS_URL=redis://localhost:6379/0
CACHE_TTL_SECONDS=300

# Monitoring Configuration (Optional)
PROMETHEUS_PORT=9090
SENTRY_DSN=

# Ansible Configuration (Optional)
ANSIBLE_SSH_KEY_PATH=/keys/ansible_rsa
ANSIBLE_VERBOSITY=0

# Development Settings
DEBUG=false
```

### 2. Generate Secure Keys

```bash
# Generate API keys
python -c "import secrets; print(f'{secrets.token_urlsafe(32)}:write')"
python -c "import secrets; print(f'{secrets.token_urlsafe(32)}:read')"

# Generate secret key
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

### 3. Configure OpenStack Credentials

Ensure your OpenStack credentials have sufficient permissions:
- Create/delete compute instances
- Create/delete networks
- Create/delete security groups
- Manage floating IPs

## Deployment Options

### Option 1: Development Deployment

For local development and testing:

```bash
# Start the API server with auto-reload
poetry run uvicorn orchestrator.main:app --reload --host 0.0.0.0 --port 8000

# Or use the development script
poetry run python -m orchestrator.main
```

Access the API at: http://localhost:8000
- API Docs: http://localhost:8000/docs
- Health: http://localhost:8000/health

### Option 2: Production Deployment (Systemd)

Create a systemd service for production deployment:

#### 1. Create Service File

```bash
sudo nano /etc/systemd/system/orchestrator.service
```

```ini
[Unit]
Description=ONAP SO Modern Orchestrator API
After=network.target postgresql.service

[Service]
Type=notify
User=orchestrator
Group=orchestrator
WorkingDirectory=/opt/orchestrator
Environment="PATH=/opt/orchestrator/.venv/bin"
EnvironmentFile=/opt/orchestrator/.env
ExecStart=/opt/orchestrator/.venv/bin/gunicorn orchestrator.main:app \
    --workers 4 \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:8000 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile -
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

#### 2. Enable and Start Service

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable service
sudo systemctl enable orchestrator

# Start service
sudo systemctl start orchestrator

# Check status
sudo systemctl status orchestrator

# View logs
sudo journalctl -u orchestrator -f
```

### Option 3: Docker Deployment

#### 1. Build Docker Image

```bash
# Build the image
docker build -t onap-so-modern:latest .

# Or use docker-compose
docker-compose build
```

#### 2. Run with Docker Compose

```bash
# Start all services (API, PostgreSQL, Temporal, Redis)
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

### Option 4: Kubernetes Deployment

See [kubernetes-deployment.md](./kubernetes-deployment.md) for Kubernetes and Helm deployment instructions.

## Security Configuration

### 1. API Key Management

API keys support two permission levels:
- `write`: Full access (create, read, update, delete)
- `read`: Read-only access (get, list)

```bash
# Format: key:permission
API_KEYS=production-admin-key:write,monitoring-key:read,partner-key:write
```

### 2. Rate Limiting

Configure rate limits to protect against abuse:

```bash
# Enable rate limiting
RATE_LIMIT_ENABLED=true

# 100 requests per 60 seconds per API key/IP
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_WINDOW_SECONDS=60
```

Rate limit headers in responses:
- `X-RateLimit-Limit`: Maximum requests allowed
- `X-RateLimit-Remaining`: Remaining requests in window
- `X-RateLimit-Reset`: Unix timestamp when limit resets

### 3. Input Validation

All API inputs are automatically validated and sanitized to prevent:
- XSS attacks
- SQL injection
- Path traversal
- Null byte injection

### 4. TLS/HTTPS Configuration

#### Using Nginx as Reverse Proxy

```nginx
server {
    listen 443 ssl http2;
    server_name orchestrator.example.com;

    ssl_certificate /etc/ssl/certs/orchestrator.crt;
    ssl_certificate_key /etc/ssl/private/orchestrator.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
        proxy_connect_timeout 75s;
    }
}
```

## Monitoring Setup

### 1. Health Checks

```bash
# Basic health check
curl http://localhost:8000/health

# Expected response:
{
  "status": "healthy",
  "version": "1.0.0",
  "checks": {
    "database": "healthy"
  }
}
```

### 2. Prometheus Metrics

```bash
# Access metrics endpoint
curl http://localhost:8000/metrics

# Metrics include:
# - Request counts and durations
# - Deployment statuses
# - Database connection pool stats
# - Rate limiter stats
```

### 3. Structured Logging

Logs are output in JSON format for easy parsing:

```json
{
  "event": "deployment_created",
  "deployment_id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "web-app-prod",
  "cloud_region": "RegionOne",
  "level": "info",
  "timestamp": "2025-01-10T12:00:00Z"
}
```

Configure log aggregation with:
- ELK Stack (Elasticsearch, Logstash, Kibana)
- Splunk
- Datadog
- CloudWatch

## Troubleshooting

### Common Issues

#### 1. Database Connection Errors

```bash
# Check PostgreSQL is running
sudo systemctl status postgresql

# Test connection
psql -U orchestrator -d orchestrator -h localhost

# Check connection pool settings
# Increase pool size if seeing timeout errors
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=40
```

#### 2. Temporal Connection Issues

```bash
# Check Temporal is running
docker ps | grep temporal

# Test connection
temporal workflow list

# Check configuration
TEMPORAL_HOST=localhost:7233
TEMPORAL_NAMESPACE=default
```

#### 3. Rate Limiting Issues

```bash
# Check rate limit headers
curl -I -H "X-API-Key: your-key" http://localhost:8000/v1/deployments

# Increase limits if legitimate traffic is blocked
RATE_LIMIT_REQUESTS=200
RATE_LIMIT_WINDOW_SECONDS=60

# Or disable temporarily
RATE_LIMIT_ENABLED=false
```

#### 4. OpenStack Authentication Failures

```bash
# Test OpenStack credentials
openstack --os-auth-url $OPENSTACK_AUTH_URL \
  --os-username $OPENSTACK_USERNAME \
  --os-password $OPENSTACK_PASSWORD \
  --os-project-name $OPENSTACK_PROJECT_NAME \
  server list

# Check service catalog
openstack catalog list
```

### Debug Mode

Enable debug mode for detailed logging:

```bash
DEBUG=true
LOG_LEVEL=DEBUG

# Restart service
sudo systemctl restart orchestrator
```

### Logging and Diagnostics

```bash
# View application logs
sudo journalctl -u orchestrator -n 100 -f

# Check API server status
curl http://localhost:8000/health

# Monitor database connections
psql -U orchestrator -d orchestrator -c "SELECT count(*) FROM pg_stat_activity;"

# Check system resources
htop
df -h
free -m
```

## Performance Tuning

### 1. Database Optimization

```bash
# Increase connection pool
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=40

# Tune PostgreSQL
# Edit /etc/postgresql/14/main/postgresql.conf
shared_buffers = 256MB
effective_cache_size = 1GB
maintenance_work_mem = 128MB
max_connections = 200
```

### 2. API Server Scaling

```bash
# Increase worker count (CPU cores * 2 + 1)
API_WORKERS=9

# Or use Gunicorn with more workers
gunicorn orchestrator.main:app \
    --workers 9 \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:8000
```

### 3. Caching

```bash
# Enable Redis caching
REDIS_URL=redis://localhost:6379/0
CACHE_TTL_SECONDS=300
```

## Backup and Recovery

### Database Backups

```bash
# Create backup
pg_dump -U orchestrator -d orchestrator -F c -f backup-$(date +%Y%m%d).dump

# Restore from backup
pg_restore -U orchestrator -d orchestrator backup-20250110.dump

# Automated backups (add to crontab)
0 2 * * * /usr/bin/pg_dump -U orchestrator -d orchestrator -F c -f /backups/orchestrator-$(date +\%Y\%m\%d).dump
```

## Next Steps

- [User Guide](./user-guide.md) - Learn how to use the API
- [Architecture Overview](./architecture.md) - Understand system design
- [API Reference](http://localhost:8000/docs) - Interactive API documentation
