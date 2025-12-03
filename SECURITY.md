# Security Policy and Audit Report

## Modern ONAP Service Orchestrator

**Audit Date:** December 2024
**Codebase Version:** 10,105 LOC (3,779 production + 6,326 tests)
**Test Coverage:** 87%

---

## Table of Contents

1. [Security Overview](#security-overview)
2. [Vulnerability Disclosure](#vulnerability-disclosure)
3. [Security Architecture](#security-architecture)
4. [Identified Vulnerabilities](#identified-vulnerabilities)
5. [Security Controls](#security-controls)
6. [Recommendations](#recommendations)
7. [Compliance Checklist](#compliance-checklist)

---

## Security Overview

This document provides a comprehensive security audit of the Modern ONAP Service Orchestrator, a Python/FastAPI-based infrastructure orchestration platform that integrates with OpenStack and Ansible.

### Threat Model

The application faces the following primary threat vectors:

| Threat | Risk Level | Mitigation Status |
|--------|------------|-------------------|
| Unauthorized API Access | High | Mitigated (API Key Auth) |
| Injection Attacks (SQL, Command) | High | Mitigated (ORM, Validation) |
| Credential Exposure | High | Partially Mitigated |
| Denial of Service | Medium | Mitigated (Rate Limiting) |
| Path Traversal | Medium | Mitigated (Input Validation) |
| Information Disclosure | Medium | Mitigated (Error Handling) |

---

## Vulnerability Disclosure

### Reporting Security Issues

If you discover a security vulnerability, please report it responsibly:

1. **DO NOT** create a public GitHub issue
2. Email security concerns to the maintainers privately
3. Provide detailed steps to reproduce the vulnerability
4. Allow reasonable time for a fix before public disclosure

### Supported Versions

| Version | Supported |
|---------|-----------|
| 1.x.x   | Yes       |
| < 1.0   | No        |

---

## Security Architecture

### Authentication Flow

```
┌─────────┐      ┌──────────────┐      ┌─────────────┐
│  Client │─────>│ Auth Middle- │─────>│  API Route  │
│         │      │    ware      │      │             │
└─────────┘      └──────────────┘      └─────────────┘
     │                  │                     │
     │  X-API-Key       │  Validate Key       │
     │  Header          │  Check Permission   │
     │                  │  Attach Context     │
```

### Data Flow Security

```
┌─────────┐    ┌──────────┐    ┌──────────┐    ┌───────────┐
│  Input  │───>│ Pydantic │───>│ Sanitize │───>│  Business │
│         │    │ Validate │    │          │    │   Logic   │
└─────────┘    └──────────┘    └──────────┘    └───────────┘
```

---

## Identified Vulnerabilities

### Critical (0)

No critical vulnerabilities identified.

### High Severity (0)

No high severity vulnerabilities identified.

### Medium Severity (2)

#### 1. Hardcoded Default Bind to All Interfaces (CWE-605)

**File:** `src/orchestrator/config.py:95`
**Bandit ID:** B104
**Status:** Known Risk (Intentional for Container Deployment)

```python
api_host: str = Field(
    default="0.0.0.0",
    description="API server host",
)
```

**Risk:** Binding to `0.0.0.0` exposes the service on all network interfaces.

**Mitigation:**
- This is intentional for containerized deployments
- In production, network policies and firewalls should restrict access
- Kubernetes NetworkPolicies should limit ingress

**Recommendation:** Document this behavior and ensure network-level controls are in place.

#### 2. Hardcoded Default Credentials in Configuration

**File:** `src/orchestrator/config.py`
**Status:** Development Defaults Only

```python
database_url: PostgresDsn = Field(
    default="postgresql+asyncpg://orchestrator:password@localhost:5432/orchestrator",
)
openstack_password: str = Field(
    default="secret",
)
secret_key: str = Field(
    default="change-this-in-production-to-a-secure-random-string",
)
```

**Risk:** Default credentials could be accidentally used in production.

**Mitigation:**
- All defaults are clearly marked for development only
- Production deployments MUST use environment variables
- Secret key validation requires minimum 32 characters

**Recommendation:** Add startup check that fails if default credentials are used in non-debug mode.

### Low Severity (1)

#### 1. Try-Except-Pass Pattern (CWE-703)

**File:** `src/orchestrator/workflows/scaling/scale.py:205`
**Bandit ID:** B110

```python
except Exception:
    # If status update fails, log but don't fail the workflow result
    pass
```

**Risk:** Silent exception handling could mask errors.

**Mitigation:** This is intentional - workflow completion should not fail due to status update issues.

**Recommendation:** Add logging within the except block for observability.

---

## Security Controls

### 1. Authentication & Authorization

**Location:** `src/orchestrator/api/middleware/auth.py`

| Feature | Status | Details |
|---------|--------|---------|
| API Key Authentication | Implemented | X-API-Key header required |
| Permission Levels | Implemented | read/write permissions |
| Public Path Bypass | Implemented | /health, /metrics, /docs |
| Write Protection | Implemented | POST/PUT/PATCH/DELETE require write permission |

**Strengths:**
- Simple, stateless authentication
- Clear permission model
- Comprehensive logging of auth events

**Weaknesses:**
- No token expiration (API keys are long-lived)
- No key rotation mechanism built-in
- No multi-factor authentication

### 2. Input Validation & Sanitization

**Location:** `src/orchestrator/utils/validation.py`

| Function | Protection |
|----------|------------|
| `sanitize_string()` | Null bytes, control chars, length limits |
| `validate_name()` | Alphanumeric pattern enforcement |
| `validate_cloud_region()` | Strict character whitelist |
| `validate_playbook_path()` | Path traversal prevention |
| `sanitize_dict()` | Recursive sanitization, depth limits |
| `validate_template()` | Schema validation |

**Strengths:**
- Comprehensive path traversal protection (`..` blocked)
- Null byte injection prevention
- Control character filtering
- Recursive depth limits (10 levels)
- Length constraints on all inputs

**Weaknesses:**
- No HTML/XSS sanitization (API returns JSON only - acceptable)

### 3. Rate Limiting

**Location:** `src/orchestrator/api/middleware/rate_limit.py`

| Configuration | Default |
|---------------|---------|
| Requests per window | 100 |
| Window duration | 60 seconds |
| Algorithm | Sliding window |

**Features:**
- Per API-key rate limiting
- IP-based fallback for unauthenticated requests
- Automatic memory cleanup
- Standard rate limit headers (X-RateLimit-*)
- Retry-After header on limit exceeded

### 4. Database Security

**Location:** `src/orchestrator/db/connection.py`

| Feature | Status |
|---------|--------|
| Parameterized Queries | Yes (SQLAlchemy ORM) |
| Connection Pooling | Yes |
| Pool Pre-Ping | Yes |
| Connection Recycling | Yes (3600s default) |
| Async Connections | Yes |

**SQL Injection Prevention:**
- All database queries use SQLAlchemy ORM
- No raw SQL string concatenation
- Parameterized queries for all operations

### 5. Error Handling

**Location:** `src/orchestrator/api/middleware/errors.py`

| Mode | Behavior |
|------|----------|
| Production | Generic "Internal server error" message |
| Debug | Includes exception details |

**Strengths:**
- Stack traces hidden in production
- Validation errors return structured details
- Consistent error response format

### 6. Logging & Monitoring

**Location:** `src/orchestrator/logging.py`

| Feature | Status |
|---------|--------|
| Structured Logging | Yes (structlog) |
| JSON Output | Yes (production) |
| Auth Event Logging | Yes |
| Rate Limit Logging | Yes |
| Request Logging | Yes |

**Security Events Logged:**
- Authentication failures
- Invalid API keys
- Insufficient permissions
- Rate limit exceeded
- Validation errors

### 7. Docker Security

**Location:** `Dockerfile`

| Control | Status |
|---------|--------|
| Non-root User | Yes (`orchestrator` UID 1000) |
| Multi-stage Build | Yes |
| Minimal Base Image | Yes (`python:3.12-slim`) |
| Health Checks | Yes |
| Read-only Mounts | Yes (SSH keys) |

### 8. Kubernetes Security

**Location:** `k8s/base/rbac.yaml`

| Control | Status |
|---------|--------|
| Service Account | Yes |
| RBAC | Yes |
| Minimal Permissions | Yes (get configmaps, get secrets) |
| Namespace Isolation | Yes |

**Secrets Management:**
- Template file with `CHANGE_ME` placeholders
- Instructions for kubectl or external secrets operators
- Secrets not committed to version control

---

## Security Testing

### Automated Security Scans

**Location:** `.github/workflows/ci.yml`

| Tool | Purpose | Status |
|------|---------|--------|
| Bandit | Python security linter | Enabled |
| Safety | Dependency vulnerability check | Enabled |
| mypy | Type checking | Enabled |
| ruff | Code quality | Enabled |

### Current Scan Results

**Bandit Report (security-report.json):**
- Lines scanned: 5,318 LOC
- High severity: 0
- Medium severity: 1 (bind all interfaces - intentional)
- Low severity: 1 (try-except-pass - intentional)

---

## Recommendations

### Immediate Actions (Priority: High)

1. **Add Production Credential Check**
   ```python
   # In config.py or main.py
   if not settings.debug:
       if "change-this" in settings.secret_key.lower():
           raise ValueError("Production requires a secure SECRET_KEY")
   ```

2. **Add Logging to Silent Exception Handlers**
   ```python
   except Exception as e:
       logger.warning("status_update_failed", error=str(e))
       pass
   ```

3. **Implement API Key Rotation**
   - Add endpoint for key rotation
   - Consider key expiration dates

### Short-term Actions (Priority: Medium)

4. **Enable TLS/HTTPS**
   - Add TLS termination documentation
   - Provide example nginx/ingress configurations

5. **Add Security Headers Middleware**
   ```python
   # Recommended headers
   X-Content-Type-Options: nosniff
   X-Frame-Options: DENY
   X-XSS-Protection: 1; mode=block
   Content-Security-Policy: default-src 'self'
   ```

6. **Implement Request ID Tracing**
   - Add correlation IDs for request tracing
   - Include in all log entries

7. **Add Audit Logging**
   - Log all state-changing operations
   - Include actor, action, resource, timestamp

### Long-term Actions (Priority: Low)

8. **Consider OAuth2/OIDC Integration**
   - For enterprise deployments
   - Integration with identity providers

9. **Implement Secrets Rotation**
   - Database credentials
   - OpenStack credentials
   - API keys

10. **Add Network Policies**
    - Kubernetes NetworkPolicy examples
    - Ingress/egress restrictions

---

## Compliance Checklist

### OWASP Top 10 (2021)

| Risk | Status | Notes |
|------|--------|-------|
| A01: Broken Access Control | Mitigated | API key + permissions |
| A02: Cryptographic Failures | Partial | Need TLS documentation |
| A03: Injection | Mitigated | ORM + validation |
| A04: Insecure Design | Mitigated | Security by design |
| A05: Security Misconfiguration | Partial | Default credentials warning |
| A06: Vulnerable Components | Monitored | Safety scans in CI |
| A07: Auth Failures | Mitigated | Rate limiting, logging |
| A08: Data Integrity Failures | Mitigated | Input validation |
| A09: Logging Failures | Mitigated | Structured logging |
| A10: SSRF | Mitigated | URL validation |

### CWE Coverage

| CWE ID | Description | Status |
|--------|-------------|--------|
| CWE-89 | SQL Injection | Protected (ORM) |
| CWE-78 | OS Command Injection | Protected (ansible-runner) |
| CWE-22 | Path Traversal | Protected (validation) |
| CWE-287 | Authentication Issues | Protected (API keys) |
| CWE-306 | Missing Authentication | Protected (middleware) |
| CWE-352 | CSRF | N/A (API only) |
| CWE-400 | Resource Exhaustion | Protected (rate limiting) |
| CWE-605 | Bind All Interfaces | Documented Risk |
| CWE-703 | Error Handling | Minor Issue |

---

## Credential Security Summary

### Credentials Handled

| Credential | Storage | Security |
|------------|---------|----------|
| API Keys | Environment variable | Not exposed in logs |
| Database URL | Environment variable | Connection pooling |
| OpenStack Password | Environment variable | Memory only |
| Secret Key | Environment variable | Min 32 chars enforced |
| SSH Keys | File mount (read-only) | Container isolation |

### Secrets NOT to Commit

- `.env` files with real credentials
- `k8s/base/secret.yaml` with real values
- SSH private keys
- API keys
- Database passwords

---

## Version History

| Date | Version | Changes |
|------|---------|---------|
| Dec 2024 | 1.0 | Initial security audit |

---

## Contact

For security concerns, contact the maintainers directly. Do not create public issues for security vulnerabilities.
