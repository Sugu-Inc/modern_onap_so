# Production Migration Plan: Legacy ONAP SO → Modern Orchestrator

## Executive Summary

**Migration Type:** Phased Migration with Parallel Run
**Strategy:** Blue-Green + Canary + Shadow Mode
**Timeline:** 8-12 weeks (after new system is production-ready)
**Risk Level:** Medium-High (different architecture, live traffic)
**Rollback Capability:** Full rollback at any phase

**Key Principle:** Zero downtime, gradual migration, validate at every step.

---

## Table of Contents

1. [Migration Overview](#1-migration-overview)
2. [Pre-Migration Assessment](#2-pre-migration-assessment)
3. [Data Migration Strategy](#3-data-migration-strategy)
4. [Traffic Migration Phases](#4-traffic-migration-phases)
5. [Rollback Procedures](#5-rollback-procedures)
6. [Risk Assessment and Mitigation](#6-risk-assessment-and-mitigation)
7. [Validation and Testing](#7-validation-and-testing)
8. [Cutover Procedures](#8-cutover-procedures)
9. [Post-Migration Monitoring](#9-post-migration-monitoring)
10. [Operational Handover](#10-operational-handover)

---

## 1. Migration Overview

### 1.1 Migration Challenges

**Fundamental Differences:**
- **Different Architecture:** Camunda BPMN → Temporal, Java → Python
- **Different Data Models:** 3 MariaDB databases + A&AI → 1 PostgreSQL database
- **Different APIs:** `/ecomp/mso/infra/serviceInstances` → `/deployments`
- **Different Workflows:** 125 BPMN XML files → Python Temporal workflows
- **No Direct Upgrade Path:** Cannot migrate in-place

**Live System Constraints:**
- **Existing Deployments:** Legacy system manages active infrastructure
- **In-Flight Workflows:** Camunda workflows may be running for hours
- **API Clients:** VID, external systems depend on legacy APIs
- **Operational Knowledge:** Team trained on legacy system

### 1.2 Migration Strategy

**Chosen Approach:** **Phased Migration with Parallel Run**

**Why This Approach?**
- ✅ Zero downtime (both systems run in parallel)
- ✅ Gradual traffic shift (validate incrementally)
- ✅ Full rollback capability (at any phase)
- ✅ Time to train operations team
- ✅ Validate new system with real traffic (shadow mode)

**Strategy Phases:**
1. **Phase 0:** Pre-migration setup (2 weeks)
2. **Phase 1:** Shadow mode (2-3 weeks)
3. **Phase 2:** New deployments only (2-3 weeks)
4. **Phase 3:** Gradual traffic migration (2-4 weeks)
5. **Phase 4:** Legacy sunset (1-2 weeks)

**Total Timeline:** 8-12 weeks post-implementation

---

## 2. Pre-Migration Assessment

### 2.1 Inventory Current State

**Step 1: Catalog All Active Deployments**

```sql
-- Run on legacy Request DB
SELECT
    request_id,
    request_status,
    service_instance_id,
    service_instance_name,
    start_time,
    request_action
FROM infra_active_requests
WHERE request_status IN ('IN_PROGRESS', 'PENDING', 'COMPLETE')
ORDER BY start_time DESC;
```

**Deliverable:**
- Count of active deployments
- Count of in-flight workflows
- List of service types in use
- List of cloud regions in use

**Step 2: Identify API Clients**

```bash
# Analyze API logs to identify clients
grep "POST /ecomp/mso/infra" /var/log/mso/*.log | \
  awk '{print $1}' | sort | uniq -c | sort -nr
```

**Deliverable:**
- List of API clients (VID, external systems, scripts)
- API call volume per client
- API patterns (create, delete, query)

**Step 3: Assess Infrastructure Dependencies**

**Deliverable:**
- OpenStack regions in use
- Network topologies deployed
- VM flavors/images in use
- Volume attachments
- External integrations (SDN-C, APPC, A&AI status)

### 2.2 Compatibility Analysis

**API Compatibility Check:**

| Legacy Endpoint | Modern Endpoint | Compatible? | Migration Path |
|----------------|-----------------|-------------|----------------|
| `POST /serviceInstances` | `POST /deployments` | ❌ No | API Gateway transformation |
| `GET /orchestrationRequests/{id}` | `GET /deployments/{id}` | ⚠️ Partial | Response format differs |
| `DELETE /serviceInstances/{id}` | `DELETE /deployments/{id}` | ⚠️ Partial | Different payload |

**Data Compatibility Check:**

| Legacy Data | Modern Equivalent | Migration Required? |
|-------------|-------------------|---------------------|
| Service Instance (A&AI) | Deployment (PostgreSQL) | ✅ Yes - mapping needed |
| VNF + VF Modules | VM instances (flat list) | ✅ Yes - flatten hierarchy |
| Heat Stack IDs | OpenStack resource IDs | ✅ Yes - direct mapping |
| TOSCA models | JSON templates | ⚠️ Manual conversion |

---

## 3. Data Migration Strategy

### 3.1 Historical Data Migration

**Decision:** **Do NOT migrate historical data**

**Rationale:**
- Different data models (incompatible schemas)
- Historical data rarely accessed
- Legacy system remains available for queries
- Focus on forward-looking migration

**Alternative:** **Read-Only Legacy System**
- Keep legacy system running in read-only mode
- Queries for historical data go to legacy
- New operations go to modern system

### 3.2 Active Deployment Migration

**Approach:** **Dual-Write Pattern**

**Phase 1: Inventory Sync**

```python
# Migration script: sync_deployments.py
# Reads legacy A&AI, writes to modern PostgreSQL

async def sync_active_deployments():
    # 1. Query A&AI for all service instances
    legacy_services = await aai_client.query_services()

    # 2. For each service, extract deployment info
    for service in legacy_services:
        vnfs = await aai_client.query_vnfs(service.id)
        networks = await aai_client.query_networks(service.id)

        # 3. Map to modern Deployment model
        deployment = Deployment(
            id=service.service_instance_id,
            name=service.service_instance_name,
            status=map_status(service.orchestration_status),
            template=infer_template(vnfs, networks),
            parameters={},  # Not recoverable from A&AI
            cloud_region=service.cloud_region,
            resources={
                "legacy_service_id": service.id,
                "vm_ids": [vnf.vnf_id for vnf in vnfs],
                "network_ids": [net.network_id for net in networks]
            },
            metadata={
                "migrated_from_legacy": True,
                "legacy_orchestration_status": service.orchestration_status
            },
            created_at=service.created_at,
            updated_at=service.updated_at
        )

        # 4. Write to modern PostgreSQL
        await deployment_repo.create(deployment)
```

**Status Mapping:**

| Legacy Status (A&AI) | Modern Status |
|---------------------|---------------|
| Active | COMPLETED |
| Assigned | PENDING |
| Created | IN_PROGRESS |
| PendingDelete | DELETING |
| InventoryFailed | FAILED |

**Phase 2: Validation**

```python
# Validate migration accuracy
async def validate_migration():
    legacy_count = await aai_client.count_services()
    modern_count = await deployment_repo.count()

    assert legacy_count == modern_count, f"Count mismatch: {legacy_count} vs {modern_count}"

    # Sample validation
    sample_deployments = await deployment_repo.list(limit=100)
    for deployment in sample_deployments:
        legacy_service = await aai_client.get_service(deployment.id)
        assert_equivalent(deployment, legacy_service)
```

### 3.3 Template Migration

**Manual Process:**

1. **Export Heat Templates** from SO Catalog
2. **Convert to JSON Templates** using conversion tool
3. **Validate Templates** against modern schema
4. **Import to Modern System** via API

**Conversion Tool:**

```python
# convert_heat_to_json.py
def convert_heat_template(heat_template):
    """Convert Heat template to modern JSON template."""

    # Parse Heat YAML
    heat = yaml.safe_load(heat_template)

    # Extract VM configuration
    vm_config = {}
    for resource_name, resource in heat['resources'].items():
        if resource['type'] == 'OS::Nova::Server':
            vm_type = extract_vm_type(resource_name)
            vm_config[vm_type] = {
                'flavor': resource['properties']['flavor'],
                'image': resource['properties']['image'],
                'count': 1  # Heat doesn't specify count
            }

    # Extract network configuration
    network_config = {}
    for resource_name, resource in heat['resources'].items():
        if resource['type'] == 'OS::Neutron::Net':
            network_config['cidr'] = extract_cidr(resource)
            network_config['subnets'] = extract_subnets(heat)

    # Create modern template
    return {
        'name': heat.get('description', 'Migrated Template'),
        'description': f"Migrated from Heat: {heat_template['heat_template_artifact_uuid']}",
        'vm_config': vm_config,
        'network_config': network_config
    }
```

---

## 4. Traffic Migration Phases

### Phase 0: Pre-Migration Setup (2 weeks)

**Goal:** Deploy modern system alongside legacy

**Tasks:**
1. ✅ Deploy modern orchestrator to production (separate cluster)
2. ✅ Run inventory sync script (initial load)
3. ✅ Deploy API Gateway (for traffic routing)
4. ✅ Configure monitoring and alerting
5. ✅ Train operations team on new system

**Validation:**
- [ ] Modern system deployed and healthy
- [ ] PostgreSQL populated with active deployments
- [ ] API Gateway routing configured
- [ ] Monitoring dashboards operational
- [ ] Operations team trained

**Architecture:**

```
                    ┌─────────────────┐
                    │   API Gateway   │
                    │   (Kong/NGINX)  │
                    └────────┬────────┘
                             │
                ┌────────────┼────────────┐
                │                         │
                ▼                         ▼
    ┌───────────────────────┐   ┌─────────────────────┐
    │  Legacy ONAP SO       │   │  Modern Orchestrator │
    │  (100% traffic)       │   │  (0% traffic)        │
    │                       │   │                      │
    │  - Camunda BPMN       │   │  - Temporal          │
    │  - MariaDB x3         │   │  - PostgreSQL        │
    │  - A&AI integration   │   │  - Direct OpenStack  │
    └───────────────────────┘   └─────────────────────┘
```

### Phase 1: Shadow Mode (2-3 weeks)

**Goal:** Validate modern system with real traffic (read-only)

**Strategy:** Dual-write + validation

**Implementation:**

```python
# API Gateway configuration (Kong/NGINX)
# Route all traffic to legacy, duplicate to modern (async)

@app.post("/deployments")
async def create_deployment(request: Request):
    # 1. Forward to legacy (synchronous)
    legacy_response = await forward_to_legacy(request)

    # 2. Send to modern (asynchronous, fire-and-forget)
    asyncio.create_task(shadow_to_modern(request))

    # 3. Return legacy response (no impact on clients)
    return legacy_response

async def shadow_to_modern(request: Request):
    try:
        # Transform request to modern format
        modern_request = transform_request(request)

        # Call modern API
        modern_response = await modern_client.create_deployment(modern_request)

        # Compare responses (log differences)
        compare_and_log(legacy_response, modern_response)

    except Exception as e:
        # Log error but don't fail (shadow mode)
        logger.error(f"Shadow mode error: {e}")
```

**Validation Metrics:**

| Metric | Target | Status |
|--------|--------|--------|
| Shadow success rate | >95% | Monitor |
| Response time difference | <500ms | Monitor |
| Resource ID match | 100% | Validate |
| Error rate | <1% | Monitor |

**Deliverables:**
- [ ] Shadow mode running for 2 weeks
- [ ] No critical errors in modern system
- [ ] Response comparison report (differences documented)
- [ ] Performance benchmarks (modern vs legacy)

**Decision Point:** Go/No-Go for Phase 2
- ✅ **Go if:** Shadow success rate >95%, no data corruption, acceptable performance
- ❌ **No-Go if:** Critical errors, data corruption, unacceptable performance

### Phase 2: New Deployments Only (2-3 weeks)

**Goal:** Route all NEW deployment requests to modern system

**Strategy:** Route based on operation type

**Implementation:**

```nginx
# API Gateway routing rules
location /deployments {
    # New deployments → Modern
    if ($request_method = POST) {
        proxy_pass http://modern-orchestrator:8000;
    }

    # Queries → Route based on deployment source
    if ($request_method = GET) {
        # Check if deployment exists in modern system
        auth_request /check_modern;
        auth_request_set $route $upstream_http_x_route;
        proxy_pass http://$route;
    }

    # Deletes → Route to source system
    if ($request_method = DELETE) {
        auth_request /check_source;
        auth_request_set $route $upstream_http_x_route;
        proxy_pass http://$route;
    }
}
```

**Routing Logic:**

```python
# Routing service: check_source.py
@app.get("/check_source")
async def check_deployment_source(deployment_id: str):
    # Check modern system first
    modern_deployment = await modern_repo.get_by_id(deployment_id)
    if modern_deployment:
        return {"X-Route": "modern-orchestrator:8000"}

    # Fall back to legacy
    legacy_deployment = await legacy_client.get_deployment(deployment_id)
    if legacy_deployment:
        return {"X-Route": "legacy-onap-so:8080"}

    # Not found
    raise HTTPException(status_code=404)
```

**Monitoring:**

```python
# Monitor traffic split
metrics = {
    "legacy_deployments": 0,
    "modern_deployments": 0,
    "legacy_queries": 0,
    "modern_queries": 0
}

# Alert if modern error rate >2%
if (modern_errors / modern_total) > 0.02:
    alert("Modern system error rate high")
```

**Validation:**
- [ ] All new deployments successful on modern system
- [ ] Queries routed correctly (modern vs legacy)
- [ ] Deletes working on both systems
- [ ] No cross-system conflicts

**Decision Point:** Go/No-Go for Phase 3
- ✅ **Go if:** New deployments working, error rate <2%, operations confident
- ❌ **No-Go if:** Critical failures, data corruption, operational concerns

### Phase 3: Gradual Traffic Migration (2-4 weeks)

**Goal:** Migrate existing deployments from legacy to modern

**Strategy:** Canary deployment (gradual percentage increase)

**Week 1: 10% Migration**

```python
# Migration script: migrate_deployments.py
async def migrate_batch(percentage: float = 0.10):
    # 1. Get deployments to migrate (oldest first)
    legacy_deployments = await legacy_client.list_deployments(
        limit=int(total_deployments * percentage),
        order_by="created_at ASC"
    )

    # 2. For each deployment, migrate lifecycle management
    for deployment in legacy_deployments:
        # 2a. Validate deployment is stable (not in-flight)
        if deployment.status == "IN_PROGRESS":
            continue  # Skip in-flight workflows

        # 2b. Create in modern system (if not exists)
        if not await modern_repo.exists(deployment.id):
            await sync_deployment(deployment)

        # 2c. Update routing table
        await routing_db.update(deployment.id, route="modern")

        # 2d. Validate resource access
        await validate_openstack_access(deployment)

    # 3. Monitor for 24 hours before next batch
    await asyncio.sleep(86400)
```

**Migration Schedule:**

| Week | Percentage | Deployments | Validation Period | Rollback Window |
|------|-----------|-------------|-------------------|-----------------|
| 1 | 10% | ~100 | 3 days | Immediate |
| 2 | 25% | ~250 | 3 days | Immediate |
| 3 | 50% | ~500 | 3 days | 24 hours |
| 4 | 75% | ~750 | 3 days | 24 hours |
| 5 | 100% | ~1000 | 7 days | 48 hours |

**Health Checks:**

```python
# Continuous validation during migration
async def validate_migrated_deployments():
    migrated = await routing_db.get_modern_deployments()

    for deployment_id in migrated:
        # Check modern system can access resources
        deployment = await modern_repo.get_by_id(deployment_id)

        # Verify OpenStack resources exist
        for vm_id in deployment.resources["vm_ids"]:
            vm = await openstack_client.get_server(vm_id)
            assert vm.status == "ACTIVE", f"VM {vm_id} not active"

        # Test delete dry-run (don't actually delete)
        can_delete = await test_delete_capability(deployment_id)
        assert can_delete, f"Cannot delete {deployment_id}"
```

**Rollback Procedure (if needed):**

```python
async def rollback_migration(deployment_id: str):
    # 1. Update routing to legacy
    await routing_db.update(deployment_id, route="legacy")

    # 2. Verify legacy system can still manage
    legacy_status = await legacy_client.get_deployment(deployment_id)
    assert legacy_status is not None

    # 3. Log rollback
    logger.warning(f"Rolled back deployment {deployment_id} to legacy")
```

**Success Criteria (Per Week):**
- [ ] Error rate <1% for migrated deployments
- [ ] No resource orphaning
- [ ] All CRUD operations working
- [ ] Performance within SLA
- [ ] Zero data loss

**Decision Point (Each Week):** Continue/Pause/Rollback
- ✅ **Continue if:** Success criteria met, no critical issues
- ⏸️ **Pause if:** Error rate 1-3%, investigate before proceeding
- ❌ **Rollback if:** Error rate >3%, data corruption, resource orphaning

### Phase 4: Legacy Sunset (1-2 weeks)

**Goal:** Decommission legacy system

**Preconditions:**
- ✅ 100% traffic on modern system for 7+ days
- ✅ No critical issues
- ✅ Operations team confident
- ✅ Rollback plan documented

**Step 1: Read-Only Mode (Week 1)**

```python
# Make legacy API read-only
@app.post("/serviceInstances")
async def create_service_instance_readonly():
    return {
        "error": "Legacy system is read-only. Use new API: POST /deployments",
        "status": 410  # Gone
    }

@app.get("/serviceInstances/{id}")
async def get_service_instance(id: str):
    # Still allow reads for historical data
    return await legacy_service.get(id)
```

**Step 2: Monitoring Period (Week 1)**
- Monitor for any legacy API calls
- Alert on any POST/DELETE/PATCH requests
- Provide migration guidance to clients

**Step 3: Archive Data (Week 2)**

```bash
# Export legacy data for archival
mysqldump --all-databases > legacy_onap_so_backup_$(date +%Y%m%d).sql
tar -czf legacy_onap_logs_$(date +%Y%m%d).tar.gz /var/log/mso/

# Upload to long-term storage
aws s3 cp legacy_onap_so_backup_*.sql s3://archives/onap-so/
```

**Step 4: Decommission (Week 2)**

```bash
# Stop legacy services
kubectl scale deployment legacy-onap-so --replicas=0

# Keep databases for 90 days (compliance)
# Mark for deletion after retention period
```

**Final Validation:**
- [ ] No legacy API calls in 7 days
- [ ] All clients migrated to modern API
- [ ] Data archived
- [ ] Legacy system stopped
- [ ] Documentation updated

---

## 5. Rollback Procedures

### 5.1 Rollback Decision Criteria

**When to Rollback:**
- ❌ Error rate >5% for >1 hour
- ❌ Data corruption detected
- ❌ Critical resource orphaning
- ❌ Security breach
- ❌ Performance degradation >50%

### 5.2 Phase-Specific Rollback

**Phase 1 (Shadow Mode):**
```bash
# Simply stop shadow traffic
# No impact on production (legacy handles all traffic)
kubectl scale deployment modern-orchestrator --replicas=0
```

**Phase 2 (New Deployments Only):**
```nginx
# Revert API Gateway routing
location /deployments {
    # Route all to legacy
    proxy_pass http://legacy-onap-so:8080/ecomp/mso/infra/serviceInstances;
}
```

**Phase 3 (Gradual Migration):**
```python
# Rollback migrated deployments
async def rollback_all_migrated():
    migrated_ids = await routing_db.get_modern_deployments()

    for deployment_id in migrated_ids:
        await rollback_migration(deployment_id)

    # Verify all back on legacy
    assert await routing_db.count_modern() == 0
```

**Phase 4 (Legacy Sunset):**
```bash
# Restart legacy system
kubectl scale deployment legacy-onap-so --replicas=3

# Revert API Gateway
# All traffic back to legacy
```

### 5.3 Rollback Testing

**Required:** Test rollback procedure in staging BEFORE each phase

```python
# Rollback test suite
async def test_rollback():
    # 1. Migrate test deployment
    test_deployment = await migrate_deployment("test-123")

    # 2. Verify on modern system
    assert await modern_repo.exists("test-123")

    # 3. Perform rollback
    await rollback_migration("test-123")

    # 4. Verify on legacy system
    legacy_deployment = await legacy_client.get("test-123")
    assert legacy_deployment is not None

    # 5. Test CRUD operations on legacy
    await legacy_client.update("test-123", {...})
    await legacy_client.delete("test-123")
```

---

## 6. Risk Assessment and Mitigation

### 6.1 High-Risk Scenarios

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| **Data corruption during migration** | Medium | High | Validation scripts, checksums, rollback |
| **Resource orphaning** | Medium | Medium | Orphan detection, cleanup scripts |
| **In-flight workflow failure** | Low | High | Complete before migration, manual intervention |
| **API client incompatibility** | Medium | Medium | API Gateway transformation, client updates |
| **Performance degradation** | Low | Medium | Load testing, gradual rollout |
| **Operational errors** | Medium | Medium | Training, runbooks, dry-runs |

### 6.2 Mitigation Strategies

**Data Corruption:**
```python
# Checksum validation
async def validate_migration_integrity():
    for deployment_id in migrated_deployments:
        # Get from both systems
        modern = await modern_repo.get_by_id(deployment_id)
        legacy = await aai_client.get_service(deployment_id)

        # Compare critical fields
        assert modern.name == legacy.service_instance_name
        assert len(modern.resources["vm_ids"]) == len(legacy.vnfs)

        # Verify OpenStack resources match
        for vm_id in modern.resources["vm_ids"]:
            assert vm_id in [vnf.vnf_id for vnf in legacy.vnfs]
```

**Resource Orphaning:**
```python
# Orphan detection
async def detect_orphaned_resources():
    # Get all VMs in OpenStack
    all_vms = await openstack_client.list_servers()

    # Get all VMs tracked in modern system
    tracked_vms = set()
    async for deployment in modern_repo.iter_all():
        tracked_vms.update(deployment.resources.get("vm_ids", []))

    # Find orphans
    orphaned = [vm for vm in all_vms if vm.id not in tracked_vms]

    if orphaned:
        alert(f"Found {len(orphaned)} orphaned VMs: {orphaned}")
```

**In-Flight Workflows:**
```python
# Pre-migration check
async def check_in_flight_workflows():
    # Query Camunda for active workflows
    active_workflows = await camunda_client.query_active()

    if active_workflows:
        raise PreMigrationCheckFailed(
            f"Cannot migrate: {len(active_workflows)} workflows in progress. "
            f"Wait for completion or manually abort."
        )
```

---

## 7. Validation and Testing

### 7.1 Pre-Migration Testing (Staging Environment)

**Test Scenarios:**

1. **End-to-End Deployment Test**
   ```bash
   # Test full deployment lifecycle in staging
   ./tests/e2e/test_migration_deployment.sh
   ```

2. **Data Migration Test**
   ```bash
   # Migrate staging data and validate
   python migrate_deployments.py --env=staging --validate
   ```

3. **Performance Test**
   ```bash
   # Load test with realistic traffic
   locust -f tests/performance/migration_load_test.py --users=100
   ```

4. **Rollback Test**
   ```bash
   # Test rollback at each phase
   ./tests/rollback/test_phase_rollback.sh --phase=2
   ```

### 7.2 Production Validation (Per Phase)

**Automated Validation:**

```python
# Run after each phase
async def validate_phase(phase: int):
    validations = [
        validate_api_responses(),
        validate_resource_access(),
        validate_data_consistency(),
        validate_performance_sla(),
        validate_error_rates()
    ]

    results = await asyncio.gather(*validations)

    if not all(results):
        raise PhaseValidationFailed(f"Phase {phase} validation failed")
```

**Manual Validation Checklist:**

- [ ] Sample 10 deployments and verify correctness
- [ ] Test create, read, update, delete operations
- [ ] Verify OpenStack resources accessible
- [ ] Check monitoring dashboards
- [ ] Review error logs
- [ ] Confirm no data loss

---

## 8. Cutover Procedures

### 8.1 Final Cutover Checklist

**24 Hours Before:**
- [ ] Communicate cutover window to stakeholders
- [ ] Freeze legacy system changes (no new features)
- [ ] Complete final data sync
- [ ] Verify rollback procedures tested
- [ ] Operations team briefed

**6 Hours Before:**
- [ ] Put legacy system in read-only mode (except critical)
- [ ] Complete all in-flight workflows
- [ ] Final inventory sync
- [ ] Pre-warm modern system (scale up)

**1 Hour Before:**
- [ ] Final validation of modern system
- [ ] Confirm monitoring operational
- [ ] Confirm on-call team available
- [ ] Final go/no-go decision

**Cutover (15 minutes):**
```bash
# 1. Stop legacy write traffic
kubectl annotate service legacy-onap-so "readonly=true"

# 2. Final data sync
python migrate_deployments.py --final-sync

# 3. Switch API Gateway
kubectl apply -f api-gateway-modern.yaml

# 4. Validate traffic
curl https://orchestrator.example.com/health
```

**Post-Cutover (1 hour):**
- [ ] Monitor error rates (target: <1%)
- [ ] Verify sample deployments working
- [ ] Check resource access
- [ ] Confirm no rollback triggers

### 8.2 Communication Plan

**Stakeholders:**
- Executive leadership
- Operations team
- Development team
- API clients (VID, external systems)
- Infrastructure team

**Communication Timeline:**

| When | Audience | Message | Medium |
|------|----------|---------|--------|
| 4 weeks before | All | Migration plan overview | Email + meeting |
| 2 weeks before | Operations | Training sessions | Workshop |
| 1 week before | API clients | API changes, testing window | Email + docs |
| 24 hours before | All | Cutover window announced | Email + Slack |
| During cutover | Operations | Real-time status | Slack channel |
| Post-cutover | All | Success confirmation | Email |

---

## 9. Post-Migration Monitoring

### 9.1 Monitoring Duration

**Intensive Monitoring:** 4 weeks post-cutover

**Week 1:** 24/7 on-call, hourly checks
**Week 2:** Daily checks, rapid response
**Week 3:** Normal monitoring, weekly review
**Week 4:** Standard operations

### 9.2 Key Metrics

**System Health:**
```python
# Monitor these metrics
metrics = {
    "api_error_rate": {
        "threshold": 0.01,  # 1%
        "alert": "high"
    },
    "deployment_success_rate": {
        "threshold": 0.95,  # 95%
        "alert": "high"
    },
    "api_response_time_p95": {
        "threshold": 500,  # ms
        "alert": "medium"
    },
    "workflow_completion_rate": {
        "threshold": 0.98,  # 98%
        "alert": "high"
    }
}
```

**Daily Reports:**

```python
# Generate daily migration report
async def generate_daily_report():
    return {
        "date": datetime.now(),
        "deployments_on_modern": await count_modern_deployments(),
        "deployments_on_legacy": await count_legacy_deployments(),
        "new_deployments_24h": await count_new_deployments(),
        "errors_24h": await count_errors(),
        "performance": await get_performance_metrics()
    }
```

### 9.3 Incident Response

**Severity Levels:**

- **P0 (Critical):** Data loss, system down, rollback triggered
- **P1 (High):** Error rate >5%, performance degraded >50%
- **P2 (Medium):** Error rate 2-5%, minor issues
- **P3 (Low):** Cosmetic issues, non-critical bugs

**Response Procedures:**

```yaml
# incident_response.yaml
P0_Critical:
  response_time: "15 minutes"
  escalation: "Immediate - wake up on-call"
  actions:
    - Assess impact
    - Consider rollback
    - Engage incident commander

P1_High:
  response_time: "30 minutes"
  escalation: "Page on-call team"
  actions:
    - Investigate root cause
    - Mitigate if possible
    - Prepare rollback if needed

P2_Medium:
  response_time: "2 hours"
  escalation: "Slack notification"
  actions:
    - Log and track
    - Fix in next release

P3_Low:
  response_time: "Next business day"
  escalation: "Ticket created"
  actions:
    - Add to backlog
```

---

## 10. Operational Handover

### 10.1 Knowledge Transfer

**Training Sessions:**

1. **System Architecture** (4 hours)
   - Modern orchestrator architecture
   - Temporal workflows
   - PostgreSQL schema
   - OpenStack integration

2. **Operations** (4 hours)
   - Deployment procedures
   - Monitoring and alerting
   - Troubleshooting
   - Incident response

3. **Hands-On Labs** (8 hours)
   - Create/delete deployments
   - Investigate failures
   - Rollback procedures
   - Log analysis

**Deliverables:**
- [ ] Operations runbook (see docs/runbook.md)
- [ ] Troubleshooting guide
- [ ] Incident response playbook
- [ ] Architecture diagrams
- [ ] Video tutorials

### 10.2 Documentation Handover

**Required Documentation:**

1. **System Documentation**
   - target_spec.md (architecture)
   - target_flows.md (workflows)
   - API documentation (OpenAPI)

2. **Operational Documentation**
   - Deployment guide (how to deploy)
   - Runbook (how to operate)
   - Troubleshooting guide
   - Monitoring guide

3. **Migration Documentation**
   - migration_plan.md (this document)
   - Migration history log
   - Lessons learned

### 10.3 Support Transition

**Support Model:**

| Week | Primary Support | Secondary Support |
|------|----------------|-------------------|
| 1-2 | Migration team (24/7) | Operations team |
| 3-4 | Migration team (on-call) | Operations team |
| 5+ | Operations team | Migration team (consulting) |

**Handover Criteria:**

- [ ] Operations team trained (100% completion)
- [ ] All runbooks reviewed
- [ ] 10+ successful incident resolutions by ops team
- [ ] Confidence vote from ops team
- [ ] No P0/P1 incidents in 2 weeks

---

## 11. Success Criteria

### 11.1 Migration Success Metrics

| Metric | Target | Actual | Status |
|--------|--------|--------|--------|
| **Zero data loss** | 100% | TBD | ⏳ |
| **Downtime** | 0 minutes | TBD | ⏳ |
| **Error rate** | <1% | TBD | ⏳ |
| **Performance** | <500ms p95 | TBD | ⏳ |
| **Deployment success rate** | >95% | TBD | ⏳ |
| **Rollback required** | No | TBD | ⏳ |

### 11.2 Business Success Criteria

- [ ] All existing deployments migrated
- [ ] All API clients migrated
- [ ] Operations team confident
- [ ] No customer complaints
- [ ] Legacy system decommissioned
- [ ] Cost savings realized

### 11.3 Sign-Off

**Required Approvals:**

- [ ] CTO / Engineering Lead
- [ ] Operations Manager
- [ ] Infrastructure Lead
- [ ] Security Team
- [ ] Product Owner

---

## 12. Appendices

### Appendix A: API Transformation Examples

**Legacy Request → Modern Request:**

```python
# Legacy API
POST /ecomp/mso/infra/serviceInstances/v2
{
  "requestDetails": {
    "modelInfo": {
      "modelType": "service",
      "modelName": "vFW-service"
    },
    "cloudConfiguration": {
      "lcpCloudRegionId": "RegionOne",
      "tenantId": "tenant-123"
    }
  }
}

# Transform to Modern API
POST /deployments
{
  "name": "vFW-service-instance-1",
  "template": "vFW-service",
  "cloud_region": "RegionOne",
  "parameters": {}
}
```

### Appendix B: Deployment Mapping Examples

**A&AI Service Instance → Modern Deployment:**

```json
{
  "legacy": {
    "service-instance-id": "12345",
    "service-instance-name": "my-service",
    "orchestration-status": "Active",
    "vnfs": [
      {"vnf-id": "vnf-1", "vnf-name": "firewall-1"},
      {"vnf-id": "vnf-2", "vnf-name": "firewall-2"}
    ],
    "networks": [
      {"network-id": "net-1", "network-name": "internal-net"}
    ]
  },
  "modern": {
    "id": "12345",
    "name": "my-service",
    "status": "COMPLETED",
    "template": "firewall-service",
    "resources": {
      "network_id": "net-1",
      "vm_ids": ["vnf-1", "vnf-2"]
    },
    "metadata": {
      "migrated_from_legacy": true
    }
  }
}
```

### Appendix C: Rollback Scripts

```bash
#!/bin/bash
# rollback.sh - Emergency rollback script

set -e

echo "=== Emergency Rollback to Legacy ONAP SO ==="
echo "This will route all traffic back to legacy system"
read -p "Are you sure? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "Rollback cancelled"
    exit 0
fi

echo "1. Stopping modern orchestrator..."
kubectl scale deployment modern-orchestrator --replicas=0

echo "2. Reverting API Gateway routing..."
kubectl apply -f config/api-gateway-legacy.yaml

echo "3. Ensuring legacy system is running..."
kubectl scale deployment legacy-onap-so --replicas=3
kubectl wait --for=condition=ready pod -l app=legacy-onap-so --timeout=300s

echo "4. Validating legacy system..."
curl -f http://legacy-onap-so:8080/health || {
    echo "ERROR: Legacy system not healthy!"
    exit 1
}

echo "✅ Rollback complete. All traffic routed to legacy system."
echo "Next steps:"
echo "  1. Investigate modern system failure"
echo "  2. Review logs: kubectl logs -l app=modern-orchestrator"
echo "  3. Update incident ticket"
```

---

## Conclusion

This migration plan provides a **safe, gradual approach** to transitioning from legacy ONAP SO to the modern orchestrator. Key principles:

✅ **Zero Downtime:** Parallel run ensures continuous service
✅ **Gradual Migration:** Phased approach validates at each step
✅ **Full Rollback:** Can revert at any phase
✅ **Risk Mitigation:** Comprehensive testing and validation
✅ **Operational Readiness:** Training and documentation

**Timeline:** 8-12 weeks post-implementation
**Risk:** Medium-High (mitigated with phased approach)
**Confidence:** High (validated at each phase)

**Next Steps:**
1. Review and approve migration plan
2. Begin Phase 0 (pre-migration setup)
3. Execute phases sequentially
4. Monitor and validate continuously

---

**Document Version:** 1.0
**Last Updated:** 2025-01-15
**Owner:** Migration Team
**Status:** Ready for Review