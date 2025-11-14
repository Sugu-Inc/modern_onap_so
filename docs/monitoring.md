# Monitoring and Observability Guide

This guide covers the complete monitoring setup for the ONAP SO Modern orchestrator, including metrics collection, alerting, and visualization.

## Table of Contents

1. [Overview](#overview)
2. [Metrics](#metrics)
3. [Prometheus Setup](#prometheus-setup)
4. [Grafana Dashboards](#grafana-dashboards)
5. [Alerting](#alerting)
6. [Logging](#logging)
7. [Tracing](#tracing)
8. [SLOs and SLIs](#slos-and-slis)
9. [Runbooks](#runbooks)

## Overview

The orchestrator provides comprehensive observability through:
- **Metrics**: Prometheus metrics for monitoring performance and health
- **Logs**: Structured JSON logging for debugging and audit trails
- **Alerts**: Automated alerting for critical issues
- **Dashboards**: Grafana dashboards for visualization

### Architecture

```
┌──────────────┐         ┌──────────────┐         ┌──────────────┐
│              │         │              │         │              │
│ Orchestrator │────────▶│  Prometheus  │────────▶│   Grafana    │
│     API      │ metrics │              │  query  │  Dashboards  │
│              │         │              │         │              │
└──────────────┘         └──────────────┘         └──────────────┘
                                │
                                │ alerts
                                ▼
                         ┌──────────────┐
                         │              │
                         │ Alertmanager │
                         │              │
                         └──────────────┘
```

## Metrics

### Exposed Metrics

The orchestrator exposes metrics at `/metrics` endpoint:

```bash
curl http://localhost:8000/metrics
```

### Available Metrics

#### HTTP Metrics

```prometheus
# Request counts by status code
http_requests_total{method="POST", path="/v1/deployments", status="202"}

# Request duration histogram
http_request_duration_seconds_bucket{method="POST", path="/v1/deployments", le="0.5"}

# Request size histogram
http_request_size_bytes_bucket{method="POST", path="/v1/deployments", le="1000"}

# Response size histogram
http_response_size_bytes_bucket{method="POST", path="/v1/deployments", le="5000"}
```

#### Deployment Metrics

```prometheus
# Total deployments by status
deployment_total{status="completed"}
deployment_total{status="failed"}

# Deployment duration histogram
deployment_duration_seconds_bucket{le="300"}

# Active deployments gauge
deployment_active{status="in_progress"}
```

#### Database Metrics

```prometheus
# Connection pool size
orchestrator_db_pool_size

# Available connections
orchestrator_db_pool_available

# Query duration histogram
db_query_duration_seconds_bucket{operation="select", le="0.1"}

# Query errors
db_query_errors_total{operation="insert"}
```

#### Cache Metrics

```prometheus
# Cache requests
cache_requests_total{cache="template"}

# Cache hits
cache_hit_total{cache="template"}

# Cache misses
cache_miss_total{cache="template"}

# Cache evictions
cache_evictions_total{cache="template"}
```

#### Rate Limiting Metrics

```prometheus
# Rate limit exceeded count
rate_limit_exceeded_total{client="api_key_123"}

# Rate limit remaining
rate_limit_remaining{client="api_key_123"}
```

## Prometheus Setup

### Installation

#### With Helm (Recommended)

```bash
# Add Prometheus Helm repository
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

# Install Prometheus Operator
helm install prometheus prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --create-namespace \
  --values prometheus-values.yaml
```

Example `prometheus-values.yaml`:

```yaml
prometheus:
  prometheusSpec:
    serviceMonitorSelector:
      matchLabels:
        prometheus: kube-prometheus
    retention: 30d
    storageSpec:
      volumeClaimTemplate:
        spec:
          accessModes: ["ReadWriteOnce"]
          resources:
            requests:
              storage: 100Gi

alertmanager:
  alertmanagerSpec:
    storage:
      volumeClaimTemplate:
        spec:
          accessModes: ["ReadWriteOnce"]
          resources:
            requests:
              storage: 10Gi

grafana:
  adminPassword: "CHANGE_ME"
  persistence:
    enabled: true
    size: 10Gi
```

#### Deploy ServiceMonitor

```bash
# Deploy the ServiceMonitor to auto-discover orchestrator pods
kubectl apply -f monitoring/prometheus/servicemonitor.yaml
```

The ServiceMonitor will automatically configure Prometheus to scrape the orchestrator metrics.

### Configure Alert Rules

```bash
# Deploy alert rules
kubectl apply -f monitoring/prometheus/alerts.yaml

# Deploy recording rules
kubectl apply -f monitoring/prometheus/recording-rules.yaml
```

### Verify Scraping

```bash
# Port forward to Prometheus
kubectl port-forward -n monitoring svc/prometheus-kube-prometheus-prometheus 9090:9090

# Open browser to http://localhost:9090
# Navigate to Status > Targets
# Verify orchestrator-api targets are UP
```

### Query Examples

```promql
# Current request rate
rate(http_requests_total{job="orchestrator-api"}[5m])

# Error rate
rate(http_requests_total{job="orchestrator-api",status=~"5.."}[5m])
/ rate(http_requests_total{job="orchestrator-api"}[5m])

# P95 latency
histogram_quantile(0.95,
  rate(http_request_duration_seconds_bucket{job="orchestrator-api"}[5m])
)

# Deployment success rate
rate(deployment_total{status="completed"}[5m])
/ rate(deployment_total[5m])
```

## Grafana Dashboards

### Installation

Grafana is typically installed with the Prometheus Operator:

```bash
# Port forward to Grafana
kubectl port-forward -n monitoring svc/prometheus-grafana 3000:80

# Access at http://localhost:3000
# Default credentials: admin / CHANGE_ME
```

### Import Dashboards

#### Method 1: Via UI

1. Log in to Grafana
2. Navigate to Dashboards → Import
3. Upload the JSON files from `monitoring/grafana/`
4. Select Prometheus datasource
5. Click Import

#### Method 2: Via ConfigMap

```bash
# Create ConfigMap with dashboards
kubectl create configmap grafana-dashboards-orchestrator \
  --from-file=monitoring/grafana/ \
  --namespace=monitoring

# Label ConfigMap for auto-discovery
kubectl label configmap grafana-dashboards-orchestrator \
  grafana_dashboard="1" \
  --namespace=monitoring

# Grafana will auto-load dashboards with this label
```

### Available Dashboards

#### 1. Orchestrator Overview

**Purpose**: High-level health and performance metrics

**Panels**:
- API Status (UP/DOWN)
- Request Rate
- Error Rate
- Active Pods
- Request Rate by Status
- Request Latency (P95)
- Deployments by Status
- Pod CPU Usage
- Pod Memory Usage
- Database Connections

**Use Cases**:
- Quick health check
- Identify immediate issues
- Monitor overall system performance

#### 2. Orchestrator Performance

**Purpose**: Detailed performance analysis

**Panels**:
- Request Latency Percentiles (P50, P95, P99)
- Request Rate by Endpoint
- Slowest Endpoints (Table)
- Error Rate by Endpoint (Table)
- Deployment Duration (P95)
- Deployment Success Rate
- Database Query Latency
- Cache Hit Rate
- Rate Limit Exceeded
- Request Size Distribution

**Use Cases**:
- Performance tuning
- Identify slow endpoints
- Optimize database queries
- Cache effectiveness analysis

### Dashboard URLs

After deployment:
- Overview: http://localhost:3000/d/orchestrator-overview
- Performance: http://localhost:3000/d/orchestrator-performance

## Alerting

### Alert Configuration

Alerts are configured in `monitoring/prometheus/alerts.yaml` with three priority levels:

#### Priority 1 (Critical) - Immediate Response Required

- **OrchestratorAPIDown**: API completely unavailable
- **OrchestratorHighErrorRate**: >5% error rate for 5 minutes
- **OrchestratorDatabaseDown**: Database connection lost
- **OrchestratorDeploymentFailureSpike**: Unusual deployment failures
- **OrchestratorSLOBreach**: Availability SLO violation

**Response Time**: < 15 minutes
**Notification**: PagerDuty, Phone, SMS

#### Priority 2 (High) - Response Within Hours

- **OrchestratorHighLatency**: P95 latency > 2s for 10 minutes
- **OrchestratorHighMemoryUsage**: >85% memory usage
- **OrchestratorHighCPUUsage**: >85% CPU usage
- **OrchestratorPodCrashLooping**: Pods restarting frequently
- **OrchestratorDatabaseConnectionPoolExhausted**: >90% connections used

**Response Time**: < 2 hours
**Notification**: PagerDuty, Email

#### Priority 3 (Medium) - Response Within Day

- **OrchestratorRateLimitExceeded**: High rate limit violations
- **OrchestratorSlowDeployments**: P95 deployment time > 10 minutes
- **OrchestratorCacheMissRateHigh**: >50% cache miss rate
- **OrchestratorLowReplicas**: < 2 pods available

**Response Time**: < 24 hours
**Notification**: Email, Slack

### Alertmanager Configuration

```yaml
# alertmanager-config.yaml
global:
  resolve_timeout: 5m

route:
  group_by: ['alertname', 'cluster']
  group_wait: 10s
  group_interval: 10s
  repeat_interval: 12h
  receiver: 'default'
  routes:
  - match:
      severity: critical
    receiver: 'pagerduty'
    continue: true
  - match:
      severity: warning
    receiver: 'slack'

receivers:
- name: 'default'
  email_configs:
  - to: 'ops-team@example.com'
    from: 'alertmanager@example.com'
    smarthost: 'smtp.example.com:587'
    auth_username: 'alertmanager'
    auth_password: 'password'

- name: 'pagerduty'
  pagerduty_configs:
  - service_key: 'YOUR_PAGERDUTY_KEY'

- name: 'slack'
  slack_configs:
  - api_url: 'https://hooks.slack.com/services/YOUR/WEBHOOK/URL'
    channel: '#orchestrator-alerts'
    title: '{{ .GroupLabels.alertname }}'
    text: '{{ range .Alerts }}{{ .Annotations.description }}{{ end }}'
```

Apply configuration:

```bash
kubectl create secret generic alertmanager-config \
  --from-file=alertmanager.yaml=alertmanager-config.yaml \
  --namespace=monitoring
```

### Silence Alerts

During maintenance windows:

```bash
# Create silence via API
curl -X POST http://localhost:9093/api/v2/silences \
  -H "Content-Type: application/json" \
  -d '{
    "matchers": [
      {"name": "alertname", "value": "OrchestratorAPIDown", "isRegex": false}
    ],
    "startsAt": "2025-01-15T10:00:00Z",
    "endsAt": "2025-01-15T12:00:00Z",
    "createdBy": "ops-team",
    "comment": "Planned maintenance"
  }'
```

Or via Grafana UI: Alerting → Silences → New Silence

## Logging

### Log Format

All logs are output in structured JSON format:

```json
{
  "event": "deployment_created",
  "deployment_id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "web-app-prod",
  "cloud_region": "us-west-1",
  "level": "info",
  "timestamp": "2025-01-15T10:30:00Z",
  "request_id": "req-123"
}
```

### Log Levels

- **DEBUG**: Detailed debugging information
- **INFO**: General informational messages
- **WARNING**: Warning messages for potential issues
- **ERROR**: Error messages for failures
- **CRITICAL**: Critical failures requiring immediate attention

### Log Collection

#### With Loki (Recommended for Kubernetes)

```bash
# Install Loki Stack
helm install loki grafana/loki-stack \
  --namespace=monitoring \
  --set grafana.enabled=false \
  --set prometheus.enabled=false

# Logs will be automatically collected from pods
```

#### Query Logs in Grafana

```logql
# All orchestrator logs
{namespace="onap-orchestrator"}

# Error logs only
{namespace="onap-orchestrator"} |= "error"

# Deployment-related logs
{namespace="onap-orchestrator"} |= "deployment"

# Filter by request ID
{namespace="onap-orchestrator"} | json | request_id="req-123"
```

### Log Retention

Configure log retention based on storage capacity:

```yaml
# loki-values.yaml
loki:
  config:
    table_manager:
      retention_deletes_enabled: true
      retention_period: 720h  # 30 days
```

## Tracing

### OpenTelemetry Integration (Future)

For distributed tracing across services:

```python
# Add to main.py (future enhancement)
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

tracer = trace.get_tracer(__name__)

FastAPIInstrumentor.instrument_app(app)
```

## SLOs and SLIs

### Service Level Objectives

#### Availability SLO
- **Target**: 99.5% availability (monthly)
- **Error Budget**: 0.5% (216 minutes/month)
- **Measurement**: Success rate of HTTP requests (non-5xx)

```promql
# 30-day availability
sum(rate(http_requests_total{status!~"5.."}[30d]))
/ sum(rate(http_requests_total[30d]))
```

#### Latency SLO
- **Target**: P99 latency < 3 seconds
- **Measurement**: 99th percentile response time

```promql
# 30-day P99 latency
histogram_quantile(0.99,
  rate(http_request_duration_seconds_bucket[30d])
)
```

#### Deployment Success SLO
- **Target**: 95% deployment success rate
- **Measurement**: Ratio of successful to total deployments

```promql
# 7-day deployment success rate
sum(rate(deployment_total{status="completed"}[7d]))
/ sum(rate(deployment_total[7d]))
```

### Service Level Indicators (SLIs)

Monitor these metrics to track SLO compliance:

1. **Availability**: `http_requests_total` success rate
2. **Latency**: `http_request_duration_seconds` percentiles
3. **Throughput**: `deployment_total` rate
4. **Error Rate**: `http_requests_total` 5xx rate

## Runbooks

### OrchestratorAPIDown

**Severity**: Critical (P1)

**Symptoms**:
- Health check endpoint returning errors
- All API requests failing
- Prometheus target shows DOWN

**Investigation**:
1. Check pod status: `kubectl get pods -n onap-orchestrator`
2. Check pod logs: `kubectl logs -n onap-orchestrator <pod-name>`
3. Check events: `kubectl get events -n onap-orchestrator`
4. Check resource usage: `kubectl top pods -n onap-orchestrator`

**Resolution**:
1. If pods are crash looping, check logs for errors
2. If database connection issue, verify database connectivity
3. If resource exhaustion, scale up pods or increase limits
4. Rollback recent changes if needed

### OrchestratorHighErrorRate

**Severity**: Critical (P1)

**Symptoms**:
- >5% of requests returning 5xx errors
- Error rate spike in dashboard

**Investigation**:
1. Check error breakdown by endpoint
2. Review error logs for common patterns
3. Check database health and query performance
4. Verify external service connectivity (OpenStack, Temporal)

**Resolution**:
1. If specific endpoint, investigate that endpoint's code
2. If database issue, check connection pool and queries
3. If external service issue, check service health
4. Scale resources if needed

### OrchestratorHighLatency

**Severity**: Warning (P2)

**Symptoms**:
- P95 latency > 2 seconds
- Slow response times

**Investigation**:
1. Identify slowest endpoints using Grafana dashboard
2. Check database query performance
3. Check CPU/memory usage
4. Check for resource contention

**Resolution**:
1. Optimize slow database queries
2. Add caching for frequently accessed data
3. Scale horizontally (add more pods)
4. Optimize code for slow endpoints

## Best Practices

### 1. Regular Review

- Review dashboards daily
- Analyze trends weekly
- Review SLOs monthly

### 2. Alert Fatigue Prevention

- Keep P1 alerts rare and actionable
- Use appropriate thresholds
- Group related alerts
- Use silences during maintenance

### 3. Documentation

- Keep runbooks up to date
- Document all alerts
- Share incident postmortems
- Update dashboards based on feedback

### 4. Capacity Planning

- Monitor resource trends
- Plan for growth
- Test scaling procedures
- Review limits regularly

## Troubleshooting

### No Metrics Appearing

```bash
# Check if metrics endpoint is accessible
kubectl port-forward -n onap-orchestrator svc/orchestrator-api 8000:8000
curl http://localhost:8000/metrics

# Check ServiceMonitor is created
kubectl get servicemonitor -n onap-orchestrator

# Check Prometheus targets
kubectl port-forward -n monitoring svc/prometheus-kube-prometheus-prometheus 9090:9090
# Visit http://localhost:9090/targets
```

### Dashboards Not Loading

```bash
# Check Grafana pod status
kubectl get pods -n monitoring | grep grafana

# Check Grafana logs
kubectl logs -n monitoring deployment/prometheus-grafana

# Verify datasource configuration
# Login to Grafana → Configuration → Data Sources
```

### Alerts Not Firing

```bash
# Check AlertManager status
kubectl get pods -n monitoring | grep alertmanager

# Check alert rules are loaded
kubectl port-forward -n monitoring svc/prometheus-kube-prometheus-prometheus 9090:9090
# Visit http://localhost:9090/rules

# Check AlertManager configuration
kubectl port-forward -n monitoring svc/prometheus-kube-prometheus-alertmanager 9093:9093
# Visit http://localhost:9093
```

## Next Steps

- [Deployment Guide](./deployment-guide.md) - Deploy the orchestrator
- [User Guide](./user-guide.md) - Use the API
- [Kubernetes Guide](./kubernetes-deployment.md) - Deploy to Kubernetes
