# Kubernetes Deployment Guide

This guide provides instructions for deploying the ONAP SO Modern orchestrator on Kubernetes using either raw manifests (Kustomize) or Helm charts.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Deployment with Helm](#deployment-with-helm)
3. [Deployment with Kustomize](#deployment-with-kustomize)
4. [Post-Deployment Tasks](#post-deployment-tasks)
5. [Scaling and High Availability](#scaling-and-high-availability)
6. [Monitoring](#monitoring)
7. [Troubleshooting](#troubleshooting)

## Prerequisites

### Required Tools

- **kubectl**: Kubernetes CLI (v1.24+)
- **Helm**: Package manager for Kubernetes (v3.0+, for Helm deployment)
- **kustomize**: Template-free Kubernetes customization (v4.0+, for Kustomize deployment)

```bash
# Install kubectl
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl

# Install Helm
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash

# Verify installations
kubectl version --client
helm version
kustomize version
```

### Kubernetes Cluster

- **Kubernetes**: v1.24 or higher
- **Ingress Controller**: Nginx Ingress Controller (recommended)
- **Cert Manager**: For TLS certificate management (optional)
- **Metrics Server**: For HPA (HorizontalPodAutoscaler)

### Required Services

Deploy these dependencies before installing the orchestrator:

1. **PostgreSQL Database**
2. **Temporal Workflow Engine**
3. **OpenStack Environment** (configured and accessible)

## Deployment with Helm

Helm is the recommended deployment method for production environments.

### 1. Prepare Values File

Create a custom `values-prod.yaml` file:

```yaml
# values-prod.yaml
replicaCount: 5

image:
  repository: your-registry.com/onap-so-modern
  pullPolicy: IfNotPresent
  tag: "1.0.0"

ingress:
  enabled: true
  className: "nginx"
  annotations:
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
  hosts:
    - host: orchestrator.yourdomain.com
      paths:
        - path: /
          pathType: Prefix
  tls:
    - secretName: orchestrator-tls
      hosts:
        - orchestrator.yourdomain.com

resources:
  limits:
    cpu: 2000m
    memory: 4Gi
  requests:
    cpu: 500m
    memory: 1Gi

autoscaling:
  enabled: true
  minReplicas: 5
  maxReplicas: 20
  targetCPUUtilizationPercentage: 60
  targetMemoryUtilizationPercentage: 70

config:
  temporal:
    host: "temporal.temporal-system:7233"
  openstack:
    authUrl: "https://your-openstack.com:5000/v3"
    username: "admin"
    projectName: "production"
    regionName: "RegionOne"
  logging:
    level: "INFO"
  rateLimit:
    enabled: true
    requests: 200
    windowSeconds: 60
  database:
    poolSize: 20
    maxOverflow: 40

secrets:
  databaseUrl: "postgresql+asyncpg://orchestrator:SECURE_PASSWORD@postgres:5432/orchestrator"
  apiKeys: "production-key-1:write,monitoring-key-2:read"
  secretKey: "your-secure-secret-key-at-least-32-characters-long"
  openstackPassword: "SECURE_OPENSTACK_PASSWORD"
```

### 2. Install with Helm

```bash
# Add Helm repository (if published)
# helm repo add onap https://charts.onap.org
# helm repo update

# Install from local chart
helm install orchestrator ./helm/orchestrator \
  --namespace onap-orchestrator \
  --create-namespace \
  --values values-prod.yaml

# Or install with inline values
helm install orchestrator ./helm/orchestrator \
  --namespace onap-orchestrator \
  --create-namespace \
  --set image.tag=1.0.0 \
  --set-string secrets.databaseUrl="postgresql+asyncpg://user:pass@host:5432/db" \
  --set-string secrets.apiKeys="key1:write,key2:read" \
  --set-string secrets.secretKey="your-32-char-secret-key" \
  --set-string secrets.openstackPassword="password"
```

### 3. Verify Installation

```bash
# Check deployment status
kubectl get pods -n onap-orchestrator
kubectl get svc -n onap-orchestrator
kubectl get ingress -n onap-orchestrator

# Check pod logs
kubectl logs -n onap-orchestrator -l app.kubernetes.io/name=orchestrator -f

# Check application health
kubectl port-forward -n onap-orchestrator svc/orchestrator 8000:8000
curl http://localhost:8000/health
```

### 4. Upgrade Deployment

```bash
# Upgrade with new values
helm upgrade orchestrator ./helm/orchestrator \
  --namespace onap-orchestrator \
  --values values-prod.yaml

# Upgrade with specific image version
helm upgrade orchestrator ./helm/orchestrator \
  --namespace onap-orchestrator \
  --set image.tag=1.1.0 \
  --reuse-values
```

### 5. Uninstall

```bash
# Uninstall release
helm uninstall orchestrator --namespace onap-orchestrator

# Delete namespace (optional)
kubectl delete namespace onap-orchestrator
```

## Deployment with Kustomize

Kustomize provides a template-free approach to Kubernetes configuration.

### 1. Review and Customize

The project includes Kustomize overlays for different environments:

```
k8s/
├── base/                 # Base manifests
│   ├── deployment.yaml
│   ├── service.yaml
│   ├── configmap.yaml
│   ├── secret.yaml
│   ├── ingress.yaml
│   ├── hpa.yaml
│   ├── pdb.yaml
│   └── kustomization.yaml
└── overlays/
    ├── dev/             # Development environment
    │   ├── kustomization.yaml
    │   ├── deployment-patch.yaml
    │   └── configmap-patch.yaml
    └── prod/            # Production environment
        ├── kustomization.yaml
        ├── deployment-patch.yaml
        └── hpa-patch.yaml
```

### 2. Update Secrets

**IMPORTANT**: Update `k8s/base/secret.yaml` with your actual secrets:

```bash
# Generate secrets
kubectl create secret generic orchestrator-secrets \
  --from-literal=database-url='postgresql+asyncpg://user:pass@host:5432/db' \
  --from-literal=api-keys='key1:write,key2:read' \
  --from-literal=secret-key='your-32-char-secret-key' \
  --from-literal=openstack-password='openstack-password' \
  --namespace=onap-orchestrator \
  --dry-run=client -o yaml > k8s/base/secret-generated.yaml

# Or use sealed-secrets / external-secrets for production
```

### 3. Deploy with Kustomize

#### Development Environment

```bash
# Preview what will be deployed
kubectl kustomize k8s/overlays/dev

# Apply to cluster
kubectl apply -k k8s/overlays/dev

# Verify deployment
kubectl get all -n onap-orchestrator-dev
```

#### Production Environment

```bash
# Preview what will be deployed
kubectl kustomize k8s/overlays/prod

# Apply to cluster
kubectl apply -k k8s/overlays/prod

# Verify deployment
kubectl get all -n onap-orchestrator

# Check pod status
kubectl get pods -n onap-orchestrator -l app=orchestrator -w
```

### 4. Update Deployment

```bash
# Make changes to manifests, then apply
kubectl apply -k k8s/overlays/prod

# Or use diff to see what will change
kubectl diff -k k8s/overlays/prod
```

### 5. Delete Deployment

```bash
# Delete resources
kubectl delete -k k8s/overlays/prod

# Or delete namespace
kubectl delete namespace onap-orchestrator
```

## Post-Deployment Tasks

### 1. Verify Database Connectivity

```bash
# Exec into pod
POD=$(kubectl get pod -n onap-orchestrator -l app=orchestrator -o jsonpath='{.items[0].metadata.name}')
kubectl exec -n onap-orchestrator -it $POD -- python -c "
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
async def test():
    engine = create_async_engine('$DATABASE_URL')
    async with engine.connect() as conn:
        await conn.execute('SELECT 1')
    print('Database connection successful!')
asyncio.run(test())
"
```

### 2. Run Database Migrations

```bash
# Create a migration job
kubectl run migration --rm -i -n onap-orchestrator \
  --image=onap-so-modern:1.0.0 \
  --restart=Never \
  --env="DATABASE_URL=$DATABASE_URL" \
  -- alembic upgrade head
```

### 3. Test API Endpoints

```bash
# Port forward to access API
kubectl port-forward -n onap-orchestrator svc/orchestrator-api 8000:8000

# Test health endpoint
curl http://localhost:8000/health

# Test with API key
curl http://localhost:8000/v1/deployments \
  -H "X-API-Key: your-api-key"
```

### 4. Configure Monitoring

```bash
# Verify Prometheus scraping
kubectl get servicemonitor -n onap-orchestrator

# Check metrics endpoint
kubectl port-forward -n onap-orchestrator svc/orchestrator-api 8000:8000
curl http://localhost:8000/metrics
```

## Scaling and High Availability

### Horizontal Pod Autoscaling

The deployment includes HPA for automatic scaling:

```bash
# Check HPA status
kubectl get hpa -n onap-orchestrator

# Describe HPA
kubectl describe hpa orchestrator-api -n onap-orchestrator

# Manually scale (overrides HPA temporarily)
kubectl scale deployment orchestrator-api -n onap-orchestrator --replicas=10
```

### Manual Scaling

```bash
# With Helm
helm upgrade orchestrator ./helm/orchestrator \
  --namespace onap-orchestrator \
  --set replicaCount=10 \
  --reuse-values

# With kubectl
kubectl scale deployment orchestrator-api -n onap-orchestrator --replicas=10
```

### Pod Disruption Budget

The deployment includes PDB to ensure availability during voluntary disruptions:

```bash
# Check PDB status
kubectl get pdb -n onap-orchestrator

# Describe PDB
kubectl describe pdb orchestrator-api -n onap-orchestrator
```

### Anti-Affinity Rules

Pods are configured with anti-affinity to spread across nodes:

```yaml
affinity:
  podAntiAffinity:
    preferredDuringSchedulingIgnoredDuringExecution:
    - weight: 100
      podAffinityTerm:
        labelSelector:
          matchExpressions:
          - key: app
            operator: In
            values:
            - orchestrator
        topologyKey: kubernetes.io/hostname
```

## Monitoring

### Prometheus Metrics

The application exposes metrics at `/metrics`:

```bash
# Port forward and view metrics
kubectl port-forward -n onap-orchestrator svc/orchestrator-api 8000:8000
curl http://localhost:8000/metrics

# Metrics include:
# - request_duration_seconds
# - deployment_total
# - database_connections
# - rate_limit_exceeded_total
```

### Logs

```bash
# View logs from all pods
kubectl logs -n onap-orchestrator -l app=orchestrator -f

# View logs from specific pod
kubectl logs -n onap-orchestrator <pod-name> -f

# View previous container logs (after crash)
kubectl logs -n onap-orchestrator <pod-name> -f --previous

# Export logs to file
kubectl logs -n onap-orchestrator -l app=orchestrator --tail=-1 > logs.txt
```

### Health Checks

```bash
# Check liveness probe
kubectl get pods -n onap-orchestrator -o json | \
  jq '.items[].status.conditions[] | select(.type=="Ready")'

# Manually test health endpoint
kubectl exec -n onap-orchestrator <pod-name> -- \
  curl -f http://localhost:8000/health
```

## Troubleshooting

### Common Issues

#### 1. Pods Not Starting (ImagePullBackOff)

```bash
# Check image pull status
kubectl describe pod -n onap-orchestrator <pod-name>

# Verify image exists
docker pull your-registry.com/onap-so-modern:1.0.0

# Add image pull secrets if using private registry
kubectl create secret docker-registry regcred \
  --docker-server=your-registry.com \
  --docker-username=username \
  --docker-password=password \
  --namespace=onap-orchestrator

# Update deployment to use secret
# Add to deployment.yaml:
imagePullSecrets:
- name: regcred
```

#### 2. CrashLoopBackOff

```bash
# Check pod logs
kubectl logs -n onap-orchestrator <pod-name>

# Check previous logs
kubectl logs -n onap-orchestrator <pod-name> --previous

# Common causes:
# - Database connection failure
# - Missing environment variables
# - Application startup errors

# Exec into pod to debug
kubectl exec -n onap-orchestrator -it <pod-name> -- /bin/bash
```

#### 3. Service Not Accessible

```bash
# Check service
kubectl get svc -n onap-orchestrator
kubectl describe svc orchestrator-api -n onap-orchestrator

# Check endpoints
kubectl get endpoints -n onap-orchestrator

# Test from another pod
kubectl run test -n onap-orchestrator --rm -i --tty \
  --image=curlimages/curl -- \
  curl http://orchestrator-api:8000/health
```

#### 4. Ingress Not Working

```bash
# Check ingress
kubectl get ingress -n onap-orchestrator
kubectl describe ingress orchestrator-api -n onap-orchestrator

# Check ingress controller
kubectl get pods -n ingress-nginx

# Test without ingress (port-forward)
kubectl port-forward -n onap-orchestrator svc/orchestrator-api 8000:8000
curl http://localhost:8000/health
```

#### 5. Database Connection Issues

```bash
# Test from pod
kubectl exec -n onap-orchestrator -it <pod-name> -- \
  python -c "import psycopg2; print('Testing...')"

# Check secret
kubectl get secret orchestrator-secrets -n onap-orchestrator -o yaml

# Verify database is accessible
kubectl run psql-test --rm -i -n onap-orchestrator \
  --image=postgres:14 -- \
  psql postgresql://user:pass@host:5432/db -c "SELECT 1"
```

### Debug Mode

Enable debug logging:

```bash
# With Helm
helm upgrade orchestrator ./helm/orchestrator \
  --namespace onap-orchestrator \
  --set config.logging.level=DEBUG \
  --reuse-values

# With Kustomize (edit configmap)
kubectl edit configmap orchestrator-config -n onap-orchestrator
# Change log-level: "DEBUG"

# Restart pods to apply
kubectl rollout restart deployment orchestrator-api -n onap-orchestrator
```

### Resource Constraints

```bash
# Check resource usage
kubectl top pods -n onap-orchestrator

# Check node resources
kubectl top nodes

# Describe pod to see resource requests/limits
kubectl describe pod -n onap-orchestrator <pod-name>

# Adjust resources with Helm
helm upgrade orchestrator ./helm/orchestrator \
  --namespace onap-orchestrator \
  --set resources.requests.memory=2Gi \
  --set resources.limits.memory=8Gi \
  --reuse-values
```

## Security Best Practices

### 1. Use Secrets Management

Instead of storing secrets in version control, use:

- **Sealed Secrets**: Encrypt secrets for safe storage
- **External Secrets Operator**: Sync from external secret stores
- **Vault**: HashiCorp Vault integration

```bash
# Example with Sealed Secrets
kubeseal --format=yaml < secret.yaml > sealed-secret.yaml
kubectl apply -f sealed-secret.yaml
```

### 2. Network Policies

Create network policies to restrict traffic:

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: orchestrator-network-policy
  namespace: onap-orchestrator
spec:
  podSelector:
    matchLabels:
      app: orchestrator
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          name: ingress-nginx
    ports:
    - protocol: TCP
      port: 8000
  egress:
  - to:
    - namespaceSelector:
        matchLabels:
          name: postgres
    ports:
    - protocol: TCP
      port: 5432
```

### 3. Pod Security Standards

Apply pod security standards:

```bash
# Label namespace with security standard
kubectl label namespace onap-orchestrator \
  pod-security.kubernetes.io/enforce=restricted \
  pod-security.kubernetes.io/audit=restricted \
  pod-security.kubernetes.io/warn=restricted
```

## Next Steps

- [User Guide](./user-guide.md) - Learn how to use the API
- [Deployment Guide](./deployment-guide.md) - Other deployment options
- [Monitoring Guide](./monitoring.md) - Set up comprehensive monitoring
