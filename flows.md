# Modern Infrastructure Orchestrator - System Flows

## Overview

This document describes the major data flows and orchestration patterns in the Modern Infrastructure Orchestrator. Unlike legacy enterprise platforms with multiple abstraction layers, our flows are simple and direct.

**Key Characteristics:**
- **Direct API calls** to OpenStack (no adapter layers)
- **Temporal workflows** for reliability and durability
- **Async/await** for non-blocking I/O
- **Single data store** (PostgreSQL) for state tracking
- **Clean error handling** with automatic retries

---

## Flow Index

1. [Deployment Creation Flow](#1-deployment-creation-flow)
2. [VM and Network Provisioning Flow](#2-vm-and-network-provisioning-flow)
3. [Deployment Status Query Flow](#3-deployment-status-query-flow)
4. [Deployment Deletion Flow](#4-deployment-deletion-flow)
5. [Configuration Management Flow](#5-configuration-management-flow)
6. [Scaling Flow](#6-scaling-flow)
7. [Error Handling and Rollback Flow](#7-error-handling-and-rollback-flow)
8. [Workflow Recovery Flow](#8-workflow-recovery-flow)

---

## 1. Deployment Creation Flow

### Purpose
Create a new infrastructure deployment (VMs + networks) on OpenStack through a single API call.

### Trigger
Client sends `POST /deployments` request.

### Components Involved
- FastAPI Application (API Layer)
- DeploymentService (Business Logic)
- DeploymentRepository (Data Access)
- Temporal Client (Workflow Trigger)
- DeployWorkflow (Orchestration)
- OpenStack Client (Infrastructure)
- PostgreSQL (State Storage)

### Flow Diagram

```
┌────────┐
│ Client │
└───┬────┘
    │
    │ 1. POST /deployments
    │    {name, template, cloud_region, parameters}
    │
    ▼
┌─────────────────────────────────────────────┐
│         FastAPI Application                  │
│  ┌──────────────────────────────────────┐   │
│  │ POST /deployments endpoint           │   │
│  │ - Validate request (Pydantic)        │   │
│  │ - Authenticate (API key)             │   │
│  └──────────────┬───────────────────────┘   │
└─────────────────┼───────────────────────────┘
                  │ 2. Create deployment
                  ▼
┌─────────────────────────────────────────────┐
│         DeploymentService                    │
│  ┌──────────────────────────────────────┐   │
│  │ create_deployment()                  │   │
│  │ - Validate template exists           │   │
│  │ - Merge template + parameters        │   │
│  │ - Create DB record (status: PENDING)│   │
│  │ - Trigger Temporal workflow          │   │
│  │ - Return deployment ID               │   │
│  └──────────────┬───────────────────────┘   │
└─────────────────┼───────────────────────────┘
                  │
     ┌────────────┴────────────┐
     │                         │
     ▼                         ▼
┌─────────────────┐   ┌─────────────────┐
│   PostgreSQL    │   │ Temporal Client │
│                 │   │                 │
│ INSERT INTO     │   │ start_workflow( │
│ deployments     │   │   DeployWorkflow│
│ VALUES (        │   │   deployment_id │
│   id: uuid,     │   │ )               │
│   status: PENDING   │                 │
│ )               │   │                 │
└─────────────────┘   └────────┬────────┘
                              │
                              │ 3. Workflow started
                              │
     ┌────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────┐
│         Temporal Server                      │
│  ┌──────────────────────────────────────┐   │
│  │ DeployWorkflow Instance              │   │
│  │ - Persists workflow state            │   │
│  │ - Schedules activities               │   │
│  │ - Handles retries                    │   │
│  └──────────────────────────────────────┘   │
└─────────────────┬───────────────────────────┘
                  │
                  │ 4. Execute activities (see Flow #2)
                  │
    ┌─────────────┴─────────────┐
    │                           │
    ▼                           ▼
┌──────────────┐      ┌──────────────────┐
│   Return to  │      │ Update deployment│
│   Client:    │      │ status:          │
│             │      │ IN_PROGRESS      │
│ 202 Accepted │      │ → COMPLETED      │
│ {            │      │                  │
│   id: uuid,  │      │ Store resource   │
│   status:    │      │ IDs in DB        │
│   PENDING    │      │                  │
│ }            │      │                  │
└──────────────┘      └──────────────────┘
```

### Data Flow Steps

**Step 1: API Request Reception (0-10ms)**
```http
POST /deployments
X-API-Key: key1

{
  "name": "web-app-prod",
  "template": "web-app-stack",
  "cloud_region": "us-west-1",
  "parameters": {
    "web_count": 2,
    "app_count": 3,
    "db_count": 1
  }
}
```

**Data Transformations:**
- Pydantic validation converts JSON → `CreateDeploymentRequest` schema
- API key extracted from header → authenticated user context

**Step 2: Service Layer Processing (10-50ms)**
- Load template from database (or cache)
- Merge template with parameters:
  ```python
  final_config = {
    "vm_config": {
      "web": {**template.vm_config["web"], "count": 2},
      "app": {**template.vm_config["app"], "count": 3},
      "db": {**template.vm_config["db"], "count": 1}
    },
    "network_config": template.network_config
  }
  ```
- Create deployment record:
  ```sql
  INSERT INTO deployments (id, name, status, template, parameters, cloud_region)
  VALUES (
    'uuid-123',
    'web-app-prod',
    'PENDING',
    '{"vm_config": {...}}',
    '{"web_count": 2}',
    'us-west-1'
  );
  ```

**Step 3: Workflow Triggering (50-100ms)**
- Temporal client starts workflow:
  ```python
  workflow_handle = await client.start_workflow(
      DeployWorkflow.run,
      args=[deployment_id],
      id=f"deploy-{deployment_id}",
      task_queue="deployment"
  )
  ```
- Workflow persisted in Temporal's database
- Temporal worker picks up workflow

**Step 4: Asynchronous Response (100ms total)**
```json
{
  "id": "uuid-123",
  "name": "web-app-prod",
  "status": "PENDING",
  "created_at": "2025-01-15T10:30:00Z"
}
```

**Step 5: Background Workflow Execution (see Flow #2)**
- Network creation → VM creation → Status updates (async)
- Client polls `GET /deployments/{id}` for status

### Key Data Elements

**Input:**
- Deployment name (user-friendly identifier)
- Template name (references deployment_templates table)
- Cloud region (OpenStack region)
- Parameters (override template defaults)

**Output:**
- Deployment ID (UUID)
- Initial status (PENDING)
- Timestamp

**Persisted:**
- Deployment record in PostgreSQL
- Workflow state in Temporal

### Timing
- API response: ~100ms (fast acknowledgment)
- Full deployment: 2-5 minutes (async workflow)

---

## 2. VM and Network Provisioning Flow

### Purpose
Execute the actual infrastructure provisioning on OpenStack (Temporal workflow).

### Trigger
DeployWorkflow started by DeploymentService.

### Components Involved
- Temporal Worker (Activity Executor)
- OpenStack Client (Keystone, Neutron, Nova)
- DeploymentRepository (Status Updates)
- PostgreSQL (State Storage)

### Flow Diagram

```
┌─────────────────────────────────────────────┐
│         Temporal Worker                      │
│  ┌──────────────────────────────────────┐   │
│  │ DeployWorkflow.run(deployment_id)    │   │
│  │                                      │   │
│  │ 1. Load deployment from DB           │   │
│  │ 2. Update status: IN_PROGRESS        │   │
│  │ 3. Execute activities sequentially:  │   │
│  │    ├─ create_network                 │   │
│  │    ├─ create_vm (for each VM)        │   │
│  │    ├─ poll_vm_status (for each VM)   │   │
│  │    └─ update_deployment_status       │   │
│  └──────────────┬───────────────────────┘   │
└─────────────────┼───────────────────────────┘
                  │
                  │ Activity 1: create_network
                  ▼
┌─────────────────────────────────────────────┐
│         create_network Activity              │
│  ┌──────────────────────────────────────┐   │
│  │ 1. Authenticate with Keystone        │   │
│  │ 2. Create network (Neutron)          │   │
│  │ 3. Create subnet                     │   │
│  │ 4. Create router                     │   │
│  │ 5. Attach subnet to router           │   │
│  │ 6. Return network_id                 │   │
│  └──────────────┬───────────────────────┘   │
└─────────────────┼───────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────┐
│         OpenStack Neutron API                │
│                                             │
│  POST /v2.0/networks                        │
│  {                                          │
│    "network": {                             │
│      "name": "web-app-prod-network",        │
│      "admin_state_up": true                 │
│    }                                        │
│  }                                          │
│                                             │
│  Response: {"network": {"id": "net-123"}}   │
│                                             │
│  POST /v2.0/subnets                         │
│  {                                          │
│    "subnet": {                              │
│      "network_id": "net-123",               │
│      "cidr": "10.0.0.0/16",                 │
│      "ip_version": 4                        │
│    }                                        │
│  }                                          │
│                                             │
│  Response: {"subnet": {"id": "subnet-456"}} │
└─────────────────┬───────────────────────────┘
                  │
                  │ network_id = "net-123"
                  │
                  ▼
┌─────────────────────────────────────────────┐
│  Activity 2: create_vm (parallel execution) │
│  ┌──────────────────────────────────────┐   │
│  │ For each VM in deployment:           │   │
│  │                                      │   │
│  │ 1. Prepare boot parameters           │   │
│  │ 2. Create server (Nova)              │   │
│  │ 3. Return vm_id                      │   │
│  └──────────────┬───────────────────────┘   │
└─────────────────┼───────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────┐
│         OpenStack Nova API                   │
│                                             │
│  POST /v2.1/servers                         │
│  {                                          │
│    "server": {                              │
│      "name": "web-app-prod-web-1",          │
│      "flavorRef": "m1.small",               │
│      "imageRef": "ubuntu-22.04-uuid",       │
│      "networks": [{"uuid": "net-123"}],     │
│      "metadata": {                          │
│        "deployment_id": "uuid-123"          │
│      }                                      │
│    }                                        │
│  }                                          │
│                                             │
│  Response: {                                │
│    "server": {                              │
│      "id": "vm-789",                        │
│      "status": "BUILD"                      │
│    }                                        │
│  }                                          │
└─────────────────┬───────────────────────────┘
                  │
                  │ vm_id = "vm-789"
                  │
                  ▼
┌─────────────────────────────────────────────┐
│  Activity 3: poll_vm_status (with retries)  │
│  ┌──────────────────────────────────────┐   │
│  │ Loop until VM is ACTIVE:             │   │
│  │                                      │   │
│  │ 1. GET /servers/{vm_id}              │   │
│  │ 2. Check status                      │   │
│  │ 3. If BUILD: sleep 5s, retry         │   │
│  │ 4. If ACTIVE: return success         │   │
│  │ 5. If ERROR: raise exception         │   │
│  │                                      │   │
│  │ Temporal retries on failure          │   │
│  └──────────────┬───────────────────────┘   │
└─────────────────┼───────────────────────────┘
                  │
                  │ All VMs ACTIVE
                  │
                  ▼
┌─────────────────────────────────────────────┐
│  Activity 4: update_deployment_status        │
│  ┌──────────────────────────────────────┐   │
│  │ UPDATE deployments SET               │   │
│  │   status = 'COMPLETED',              │   │
│  │   resources = '{                     │   │
│  │     "network_id": "net-123",         │   │
│  │     "vm_ids": ["vm-789", "vm-790"]   │   │
│  │   }',                                │   │
│  │   updated_at = NOW()                 │   │
│  │ WHERE id = 'uuid-123';               │   │
│  └──────────────────────────────────────┘   │
└─────────────────────────────────────────────┘
```

### Data Flow Steps

**Activity 1: create_network (10-20s)**

Input:
```python
{
  "deployment_id": "uuid-123",
  "network_config": {
    "cidr": "10.0.0.0/16",
    "subnets": {
      "web": "10.0.1.0/24",
      "app": "10.0.2.0/24"
    }
  }
}
```

OpenStack Neutron API Calls:
1. **Create Network:**
   ```
   POST /v2.0/networks
   → network_id: "net-123"
   ```
2. **Create Subnets:**
   ```
   POST /v2.0/subnets (for each subnet)
   → subnet_ids: ["subnet-456", "subnet-457"]
   ```
3. **Create Router:**
   ```
   POST /v2.0/routers
   → router_id: "router-789"
   ```
4. **Attach Subnets:**
   ```
   PUT /v2.0/routers/{router_id}/add_router_interface
   ```

Output:
```python
{
  "network_id": "net-123",
  "subnet_ids": ["subnet-456", "subnet-457"],
  "router_id": "router-789"
}
```

**Activity 2: create_vm (30-60s per VM, parallel)**

Input (for each VM):
```python
{
  "name": "web-app-prod-web-1",
  "flavor": "m1.small",
  "image": "ubuntu-22.04",
  "network_id": "net-123",
  "subnet": "10.0.1.0/24"
}
```

OpenStack Nova API Call:
```
POST /v2.1/servers
{
  "server": {
    "name": "web-app-prod-web-1",
    "flavorRef": "m1.small",
    "imageRef": "ubuntu-22.04-uuid",
    "networks": [{"uuid": "net-123", "fixed_ip": "10.0.1.10"}]
  }
}
→ vm_id: "vm-789", status: "BUILD"
```

**Activity 3: poll_vm_status (1-3 minutes per VM)**

Polling Loop:
```python
while True:
    response = nova_client.get(f"/servers/{vm_id}")
    status = response["server"]["status"]

    if status == "ACTIVE":
        return {"vm_id": vm_id, "ip": response["server"]["addresses"]}
    elif status == "ERROR":
        raise Exception(f"VM {vm_id} failed to build")
    else:  # BUILD
        await asyncio.sleep(5)
```

**Activity 4: update_deployment_status (100ms)**

Database Update:
```sql
UPDATE deployments SET
  status = 'COMPLETED',
  resources = '{
    "network_id": "net-123",
    "subnet_ids": ["subnet-456", "subnet-457"],
    "router_id": "router-789",
    "vm_ids": ["vm-789", "vm-790", "vm-791"],
    "vm_ips": {
      "vm-789": "10.0.1.10",
      "vm-790": "10.0.1.11",
      "vm-791": "10.0.2.10"
    }
  }',
  updated_at = NOW()
WHERE id = 'uuid-123';
```

### Key Data Elements

**Workflow Input:**
- Deployment ID
- VM configurations (flavor, image, count)
- Network configurations (CIDR, subnets)

**Intermediate Data:**
- Network ID (from Neutron)
- VM IDs (from Nova)
- VM IP addresses (from Nova)

**Workflow Output:**
- Complete resource manifest
- Deployment status (COMPLETED or FAILED)

### Timing
- Network creation: ~10-20s
- VM creation: ~30-60s per VM (parallel)
- Status polling: ~1-3 minutes per VM
- **Total: 2-5 minutes** for typical deployment (3 VMs)

### Error Handling
- **Network creation fails**: Workflow throws exception, no cleanup needed
- **VM creation fails**: Temporal retries with exponential backoff (3 attempts)
- **VM status = ERROR**: Trigger rollback (delete created VMs and network)
- **Activity timeout**: Temporal retries activity (configurable attempts)

---

## 3. Deployment Status Query Flow

### Purpose
Allow clients to poll deployment status and retrieve resource information.

### Trigger
Client sends `GET /deployments/{id}` request.

### Flow Diagram

```
┌────────┐
│ Client │
└───┬────┘
    │
    │ GET /deployments/uuid-123
    │
    ▼
┌─────────────────────────────────────────────┐
│         FastAPI Application                  │
│  ┌──────────────────────────────────────┐   │
│  │ GET /deployments/{id} endpoint       │   │
│  │ - Authenticate (API key)             │   │
│  │ - Validate UUID format               │   │
│  └──────────────┬───────────────────────┘   │
└─────────────────┼───────────────────────────┘
                  │
                  │ deployment_id
                  ▼
┌─────────────────────────────────────────────┐
│         DeploymentService                    │
│  ┌──────────────────────────────────────┐   │
│  │ get_deployment(id)                   │   │
│  │ - Call repository.get_by_id()        │   │
│  │ - Convert model → schema             │   │
│  └──────────────┬───────────────────────┘   │
└─────────────────┼───────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────┐
│         DeploymentRepository                 │
│  ┌──────────────────────────────────────┐   │
│  │ async def get_by_id(id: UUID)        │   │
│  │   SELECT * FROM deployments          │   │
│  │   WHERE id = $1                      │   │
│  └──────────────┬───────────────────────┘   │
└─────────────────┼───────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────┐
│              PostgreSQL                      │
│                                             │
│  SELECT id, name, status, resources,        │
│         created_at, updated_at              │
│  FROM deployments                           │
│  WHERE id = 'uuid-123';                     │
│                                             │
│  Result:                                    │
│  {                                          │
│    id: uuid-123,                            │
│    name: "web-app-prod",                    │
│    status: "COMPLETED",                     │
│    resources: {                             │
│      network_id: "net-123",                 │
│      vm_ids: ["vm-789", "vm-790"]           │
│    }                                        │
│  }                                          │
└─────────────────┬───────────────────────────┘
                  │
                  │ Deployment model
                  │
    ┌─────────────┴─────────────┐
    │                           │
    ▼                           ▼
┌──────────────┐      ┌──────────────────┐
│ Convert to   │      │ If status =      │
│ Pydantic     │      │ IN_PROGRESS:     │
│ schema       │      │                  │
│              │      │ Query Temporal   │
│              │      │ for workflow     │
│              │      │ progress (opt)   │
└──────┬───────┘      └────────┬─────────┘
       │                       │
       └───────────┬───────────┘
                   │
                   ▼
        ┌────────────────────┐
        │ Return to Client:  │
        │                    │
        │ 200 OK             │
        │ {                  │
        │   id: uuid-123,    │
        │   name: "...",     │
        │   status: "...",   │
        │   resources: {...},│
        │   created_at: "..." │
        │ }                  │
        └────────────────────┘
```

### Data Flow Steps

**Step 1: Request (1-5ms)**
```http
GET /deployments/uuid-123
X-API-Key: key1
```

**Step 2: Database Query (5-20ms)**
```sql
SELECT id, name, status, template, parameters, resources,
       cloud_region, created_at, updated_at
FROM deployments
WHERE id = 'uuid-123';
```

**Step 3: Response (total ~20-50ms)**
```json
{
  "id": "uuid-123",
  "name": "web-app-prod",
  "status": "COMPLETED",
  "template": "web-app-stack",
  "parameters": {
    "web_count": 2
  },
  "cloud_region": "us-west-1",
  "resources": {
    "network_id": "net-123",
    "subnet_ids": ["subnet-456", "subnet-457"],
    "vm_ids": ["vm-789", "vm-790"],
    "vm_ips": {
      "vm-789": "10.0.1.10",
      "vm-790": "10.0.1.11"
    }
  },
  "created_at": "2025-01-15T10:30:00Z",
  "updated_at": "2025-01-15T10:35:00Z"
}
```

### Timing
- **Total response time: ~20-50ms** (simple database query)

---

## 4. Deployment Deletion Flow

### Purpose
Clean teardown of all resources (VMs, networks) created by a deployment.

### Trigger
Client sends `DELETE /deployments/{id}` request.

### Flow Diagram

```
┌────────┐
│ Client │
└───┬────┘
    │
    │ DELETE /deployments/uuid-123
    │
    ▼
┌─────────────────────────────────────────────┐
│         FastAPI Application                  │
│  ┌──────────────────────────────────────┐   │
│  │ DELETE /deployments/{id}             │   │
│  │ - Authenticate                       │   │
│  │ - Check deployment exists            │   │
│  │ - Trigger DeleteWorkflow             │   │
│  │ - Return 202 Accepted                │   │
│  └──────────────┬───────────────────────┘   │
└─────────────────┼───────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────┐
│         Temporal Worker                      │
│  ┌──────────────────────────────────────┐   │
│  │ DeleteWorkflow.run(deployment_id)    │   │
│  │                                      │   │
│  │ 1. Update status: DELETING           │   │
│  │ 2. Load resource IDs from DB         │   │
│  │ 3. Execute deletion activities:      │   │
│  │    ├─ delete_vm (for each VM)        │   │
│  │    ├─ wait_vm_deleted (for each)     │   │
│  │    ├─ delete_network                 │   │
│  │    └─ cleanup_resources (orphans)    │   │
│  │ 4. Soft delete deployment record     │   │
│  └──────────────┬───────────────────────┘   │
└─────────────────┼───────────────────────────┘
                  │
                  │ Activity 1: delete_vm
                  ▼
┌─────────────────────────────────────────────┐
│         OpenStack Nova API                   │
│                                             │
│  For each VM ID:                            │
│  DELETE /v2.1/servers/{vm_id}               │
│                                             │
│  Response: 204 No Content                   │
│  (VM deletion initiated)                    │
└─────────────────┬───────────────────────────┘
                  │
                  │ Activity 2: wait_vm_deleted
                  ▼
┌─────────────────────────────────────────────┐
│  Poll until VM is deleted:                  │
│                                             │
│  GET /v2.1/servers/{vm_id}                  │
│  - If 404: VM deleted (success)             │
│  - If 200: VM still exists (retry)          │
│  - Timeout after 5 minutes                  │
└─────────────────┬───────────────────────────┘
                  │
                  │ All VMs deleted
                  │
                  ▼
┌─────────────────────────────────────────────┐
│         OpenStack Neutron API                │
│                                             │
│  DELETE /v2.0/routers/{router_id}           │
│  DELETE /v2.0/subnets/{subnet_id} (each)    │
│  DELETE /v2.0/networks/{network_id}         │
│                                             │
│  Response: 204 No Content (each)            │
└─────────────────┬───────────────────────────┘
                  │
                  │ Activity 4: cleanup_resources
                  ▼
┌─────────────────────────────────────────────┐
│  Check for orphaned resources:              │
│                                             │
│  1. Query OpenStack for resources with      │
│     metadata: {deployment_id: uuid-123}     │
│  2. Delete any found resources              │
│  3. Log cleanup results                     │
└─────────────────┬───────────────────────────┘
                  │
                  │ All resources deleted
                  ▼
┌─────────────────────────────────────────────┐
│              PostgreSQL                      │
│                                             │
│  UPDATE deployments SET                     │
│    status = 'DELETED',                      │
│    deleted_at = NOW(),                      │
│    resources = NULL                         │
│  WHERE id = 'uuid-123';                     │
└─────────────────────────────────────────────┘
```

### Data Flow Steps

**Step 1: API Request**
```http
DELETE /deployments/uuid-123
X-API-Key: key1

Response: 202 Accepted
{
  "id": "uuid-123",
  "status": "DELETING"
}
```

**Step 2: Load Resources**
```sql
SELECT resources FROM deployments WHERE id = 'uuid-123';
→ {
    "network_id": "net-123",
    "vm_ids": ["vm-789", "vm-790"]
  }
```

**Step 3: Delete VMs (parallel)**
```
DELETE /v2.1/servers/vm-789
DELETE /v2.1/servers/vm-790
(Wait for deletion to complete)
```

**Step 4: Delete Network**
```
DELETE /v2.0/networks/net-123
```

**Step 5: Mark Deleted**
```sql
UPDATE deployments SET
  status = 'DELETED',
  deleted_at = NOW(),
  resources = NULL
WHERE id = 'uuid-123';
```

### Timing
- VM deletion: ~30-60s per VM (parallel)
- Network deletion: ~10-20s
- **Total: 1-2 minutes** for typical deployment

### Error Handling
- **VM already deleted**: Continue (idempotent)
- **Network in use**: Retry with backoff
- **Orphaned resources**: Cleanup activity handles them
- **Partial failure**: Workflow state preserved, can be retried

---

## 5. Configuration Management Flow

### Purpose
Apply Ansible playbooks to deployed VMs for post-deployment configuration.

### Trigger
Client sends `POST /deployments/{id}/configure` request.

### Flow Diagram

```
┌────────┐
│ Client │
└───┬────┘
    │
    │ POST /deployments/uuid-123/configure
    │ {playbook, inventory, extra_vars}
    │
    ▼
┌─────────────────────────────────────────────┐
│         FastAPI Application                  │
│  ┌──────────────────────────────────────┐   │
│  │ POST /deployments/{id}/configure     │   │
│  │ - Validate deployment exists         │   │
│  │ - Validate deployment is COMPLETED   │   │
│  │ - Trigger ConfigureWorkflow          │   │
│  └──────────────┬───────────────────────┘   │
└─────────────────┼───────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────┐
│         Temporal Worker                      │
│  ┌──────────────────────────────────────┐   │
│  │ ConfigureWorkflow.run()              │   │
│  │                                      │   │
│  │ 1. Load deployment (get VM IPs)     │   │
│  │ 2. Build Ansible inventory          │   │
│  │ 3. Execute run_ansible activity      │   │
│  │ 4. Update deployment metadata        │   │
│  └──────────────┬───────────────────────┘   │
└─────────────────┼───────────────────────────┘
                  │
                  │ Activity: run_ansible
                  ▼
┌─────────────────────────────────────────────┐
│         AnsibleClient                        │
│  ┌──────────────────────────────────────┐   │
│  │ run_playbook()                       │   │
│  │                                      │   │
│  │ 1. Write inventory file:             │   │
│  │    [web_servers]                     │   │
│  │    10.0.1.10                         │   │
│  │    10.0.1.11                         │   │
│  │                                      │   │
│  │ 2. Execute ansible-playbook:         │   │
│  │    ansible-playbook                  │   │
│  │      -i inventory.ini                │   │
│  │      configure-web.yml               │   │
│  │      --extra-vars '{...}'            │   │
│  │                                      │   │
│  │ 3. Stream output                     │   │
│  │ 4. Return exit code                  │   │
│  └──────────────┬───────────────────────┘   │
└─────────────────┼───────────────────────────┘
                  │
                  │ SSH to VMs
                  ▼
┌─────────────────────────────────────────────┐
│         Deployed VMs                         │
│                                             │
│  10.0.1.10 (web-app-prod-web-1)             │
│  10.0.1.11 (web-app-prod-web-2)             │
│                                             │
│  - Install packages                         │
│  - Configure files                          │
│  - Start services                           │
│  - Run health checks                        │
└─────────────────┬───────────────────────────┘
                  │
                  │ Playbook completed
                  ▼
┌─────────────────────────────────────────────┐
│  Update deployment record:                  │
│                                             │
│  UPDATE deployments SET                     │
│    metadata = metadata || '{                │
│      "configured": true,                    │
│      "playbook": "configure-web.yml",       │
│      "configured_at": "2025-01-15T11:00:00Z"│
│    }'                                       │
│  WHERE id = 'uuid-123';                     │
└─────────────────────────────────────────────┘
```

### Data Flow Steps

**Step 1: API Request**
```http
POST /deployments/uuid-123/configure
X-API-Key: key1

{
  "playbook": "configure-web.yml",
  "inventory": {
    "web_servers": ["10.0.1.10", "10.0.1.11"]
  },
  "extra_vars": {
    "app_port": 8080,
    "environment": "production"
  }
}

Response: 202 Accepted
{
  "deployment_id": "uuid-123",
  "status": "CONFIGURING"
}
```

**Step 2: Build Inventory**
```ini
[web_servers]
10.0.1.10
10.0.1.11

[web_servers:vars]
ansible_user=ubuntu
ansible_ssh_private_key_file=/keys/ansible_rsa
```

**Step 3: Execute Ansible**
```bash
ansible-playbook \
  -i /tmp/inventory-uuid-123.ini \
  playbooks/configure-web.yml \
  --extra-vars '{"app_port": 8080, "environment": "production"}'
```

**Step 4: Ansible Output (streamed)**
```
PLAY [Configure web servers] *******************************************

TASK [Install nginx] ***************************************************
ok: [10.0.1.10]
ok: [10.0.1.11]

TASK [Configure nginx] *************************************************
changed: [10.0.1.10]
changed: [10.0.1.11]

TASK [Start nginx] *****************************************************
ok: [10.0.1.10]
ok: [10.0.1.11]

PLAY RECAP *************************************************************
10.0.1.10: ok=3 changed=1 unreachable=0 failed=0
10.0.1.11: ok=3 changed=1 unreachable=0 failed=0
```

### Timing
- Playbook execution: 1-10 minutes (depends on tasks)
- Typical web server config: ~2-3 minutes

---

## 6. Scaling Flow

### Purpose
Horizontally scale a deployment by adding or removing VMs.

### Trigger
Client sends `POST /deployments/{id}/scale` request.

### Flow Diagram

```
┌────────┐
│ Client │
└───┬────┘
    │
    │ POST /deployments/uuid-123/scale
    │ {target_count: 5, vm_type: "web"}
    │
    ▼
┌─────────────────────────────────────────────┐
│         FastAPI Application                  │
│  ┌──────────────────────────────────────┐   │
│  │ POST /deployments/{id}/scale         │   │
│  │ - Validate deployment exists         │   │
│  │ - Get current VM count               │   │
│  │ - Determine scale direction          │   │
│  │ - Trigger ScaleWorkflow              │   │
│  └──────────────┬───────────────────────┘   │
└─────────────────┼───────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────┐
│         Temporal Worker                      │
│  ┌──────────────────────────────────────┐   │
│  │ ScaleWorkflow.run()                  │   │
│  │                                      │   │
│  │ Current: 2 VMs                       │   │
│  │ Target: 5 VMs                        │   │
│  │ Action: Scale OUT (+3 VMs)           │   │
│  │                                      │   │
│  │ Activities:                          │   │
│  │ ├─ scale_out (create 3 VMs)          │   │
│  │ ├─ poll_vm_status (for each)         │   │
│  │ └─ update_deployment_resources       │   │
│  └──────────────┬───────────────────────┘   │
└─────────────────┼───────────────────────────┘
                  │
                  │ Activity: scale_out
                  ▼
┌─────────────────────────────────────────────┐
│         OpenStack Nova API                   │
│                                             │
│  Create 3 new VMs:                          │
│  POST /v2.1/servers (web-3)                 │
│  POST /v2.1/servers (web-4)                 │
│  POST /v2.1/servers (web-5)                 │
│                                             │
│  Same config as existing VMs:               │
│  - flavor: m1.small                         │
│  - image: ubuntu-22.04                      │
│  - network: net-123                         │
│  - metadata: {deployment_id: uuid-123}      │
└─────────────────┬───────────────────────────┘
                  │
                  │ VMs created
                  ▼
┌─────────────────────────────────────────────┐
│  Wait for all VMs to be ACTIVE              │
│  (parallel polling)                         │
└─────────────────┬───────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────┐
│  Update deployment record:                  │
│                                             │
│  UPDATE deployments SET                     │
│    resources = resources || '{              │
│      "vm_ids": [                            │
│        "vm-789", "vm-790",                  │
│        "vm-999", "vm-1000", "vm-1001"       │
│      ]                                      │
│    }',                                      │
│    metadata = metadata || '{                │
│      "scaled_at": "2025-01-15T12:00:00Z",   │
│      "previous_count": 2,                   │
│      "current_count": 5                     │
│    }'                                       │
│  WHERE id = 'uuid-123';                     │
└─────────────────────────────────────────────┘
```

### Data Flow Steps

**Scale-Out Scenario (2 → 5 VMs)**

Request:
```json
{
  "target_count": 5,
  "vm_type": "web"
}
```

Current state:
```json
{
  "vm_ids": ["vm-789", "vm-790"]
}
```

Scale calculation:
```python
current_count = 2
target_count = 5
delta = target_count - current_count  # +3 (scale out)
```

Create 3 new VMs → Final state:
```json
{
  "vm_ids": ["vm-789", "vm-790", "vm-999", "vm-1000", "vm-1001"]
}
```

**Scale-In Scenario (5 → 2 VMs)**

Request:
```json
{
  "target_count": 2,
  "vm_type": "web"
}
```

Scale calculation:
```python
delta = 2 - 5  # -3 (scale in)
```

Delete 3 VMs (LIFO - last created first):
```
DELETE /v2.1/servers/vm-1001
DELETE /v2.1/servers/vm-1000
DELETE /v2.1/servers/vm-999
```

Final state:
```json
{
  "vm_ids": ["vm-789", "vm-790"]
}
```

### Timing
- Scale-out: ~2-3 minutes per new VM (parallel)
- Scale-in: ~1-2 minutes per removed VM (parallel)

---

## 7. Error Handling and Rollback Flow

### Purpose
Handle failures gracefully and rollback partial deployments.

### Trigger
Any activity failure in a workflow.

### Flow Diagram

```
┌─────────────────────────────────────────────┐
│         DeployWorkflow (Failed)              │
│                                             │
│  ├─ create_network ✓ (net-123)              │
│  ├─ create_vm (vm-789) ✓                    │
│  ├─ create_vm (vm-790) ✓                    │
│  └─ create_vm (vm-791) ✗ FAILED             │
│                                             │
│  Exception: QuotaExceeded                   │
└─────────────────┬───────────────────────────┘
                  │
                  │ Workflow catches exception
                  ▼
┌─────────────────────────────────────────────┐
│         Rollback Logic                       │
│  ┌──────────────────────────────────────┐   │
│  │ 1. Log error details                 │   │
│  │ 2. Collect created resource IDs      │   │
│  │ 3. Execute rollback activities:      │   │
│  │    ├─ delete_vm (vm-790)             │   │
│  │    ├─ delete_vm (vm-789)             │   │
│  │    └─ delete_network (net-123)       │   │
│  │ 4. Update deployment status: FAILED  │   │
│  │ 5. Store error details               │   │
│  └──────────────┬───────────────────────┘   │
└─────────────────┼───────────────────────────┘
                  │
                  │ Rollback complete
                  ▼
┌─────────────────────────────────────────────┐
│  UPDATE deployments SET                     │
│    status = 'FAILED',                       │
│    error = '{                               │
│      "type": "QuotaExceeded",               │
│      "message": "Insufficient quota...",    │
│      "failed_activity": "create_vm",        │
│      "rollback_completed": true             │
│    }',                                      │
│    updated_at = NOW()                       │
│  WHERE id = 'uuid-123';                     │
└─────────────────────────────────────────────┘
```

### Error Scenarios

**1. Transient Errors (Retry)**
- Network timeout → Retry with exponential backoff
- OpenStack API 503 → Retry (max 3 attempts)
- VM status check timeout → Retry

**2. Permanent Errors (Rollback)**
- QuotaExceeded → Rollback, return error
- Invalid flavor → Rollback, return error
- Network creation forbidden → Return error (nothing to rollback)

**3. Partial Failures**
- 2/3 VMs created successfully → Rollback all, report error
- Network created, VM creation fails → Rollback network

### Temporal Retry Policies

```python
@activity.defn
async def create_vm(params):
    # Temporal auto-retries on exception
    pass

# Workflow configures retry
await workflow.execute_activity(
    create_vm,
    args=[params],
    retry_policy=RetryPolicy(
        initial_interval=timedelta(seconds=1),
        maximum_interval=timedelta(seconds=10),
        maximum_attempts=3,
        backoff_coefficient=2.0
    ),
    start_to_close_timeout=timedelta(minutes=5)
)
```

### Timing
- Rollback execution: ~1-2 minutes
- Error logged and deployment marked FAILED

---

## 8. Workflow Recovery Flow

### Purpose
Temporal's automatic workflow recovery on worker crashes or restarts.

### Trigger
Worker process crash during workflow execution.

### Flow Diagram

```
┌─────────────────────────────────────────────┐
│  Workflow State Before Crash                 │
│                                             │
│  DeployWorkflow (IN_PROGRESS)               │
│  ├─ create_network ✓ (completed)            │
│  ├─ create_vm (vm-1) ✓ (completed)          │
│  └─ create_vm (vm-2) → IN PROGRESS          │
│                                             │
│  Worker PID 1234: CRASHED ✗                 │
└─────────────────┬───────────────────────────┘
                  │
                  │ Temporal detects timeout
                  ▼
┌─────────────────────────────────────────────┐
│         Temporal Server                      │
│  ┌──────────────────────────────────────┐   │
│  │ Workflow State Persisted:            │   │
│  │                                      │   │
│  │ - Completed activities cached        │   │
│  │ - Current activity known             │   │
│  │ - Variables preserved                │   │
│  │ - Event history recorded             │   │
│  │                                      │   │
│  │ Action:                              │   │
│  │ - Reschedule workflow on new worker  │   │
│  └──────────────┬───────────────────────┘   │
└─────────────────┼───────────────────────────┘
                  │
                  │ Worker PID 5678 picks up
                  ▼
┌─────────────────────────────────────────────┐
│  New Worker Resumes Workflow                 │
│                                             │
│  1. Replay event history:                   │
│     ✓ create_network (cached, not re-run)   │
│     ✓ create_vm (vm-1) (cached)             │
│                                             │
│  2. Resume from last activity:              │
│     → create_vm (vm-2) [RETRY]              │
│                                             │
│  3. Continue workflow execution             │
└─────────────────┬───────────────────────────┘
                  │
                  │ Workflow continues
                  ▼
┌─────────────────────────────────────────────┐
│  Workflow Completes Successfully            │
│                                             │
│  Final State:                               │
│  ├─ create_network ✓                        │
│  ├─ create_vm (vm-1) ✓                      │
│  ├─ create_vm (vm-2) ✓ (retried)            │
│  └─ update_deployment_status ✓              │
│                                             │
│  Status: COMPLETED                          │
└─────────────────────────────────────────────┘
```

### Key Properties

**Deterministic Replay:**
- Completed activities not re-executed
- Results cached in Temporal's event history
- Workflow resumes from failure point

**No Data Loss:**
- All workflow state persisted
- Activities designed to be idempotent
- Safe to retry any activity

**Automatic Recovery:**
- No manual intervention required
- Worker pool scales independently
- Workflows continue across deployments

### Example Scenario

**T=0s**: Workflow starts, creates network
**T=10s**: Creates VM 1 successfully
**T=15s**: Starts creating VM 2
**T=20s**: Worker crashes (process killed)
**T=25s**: Temporal detects timeout, reschedules
**T=30s**: New worker picks up workflow
**T=30s-35s**: Replay history (instant - cached results)
**T=35s**: Resume VM 2 creation (retries OpenStack call)
**T=50s**: Workflow completes

**No resources lost, no duplicate resources created.**

---

## Summary: Flow Comparison

| Flow | Legacy ONAP | Modern Orchestrator |
|------|-------------|---------------------|
| **Deployment** | Multiple API calls, Complex TOSCA parsing, A&AI updates, SDN-C calls | Single API call → Temporal workflow → Direct OpenStack APIs |
| **Status Query** | Query A&AI + Request DB + Camunda | Single PostgreSQL query (~20ms) |
| **Deletion** | Cascading A&AI deletions, Multiple adapter calls, Complex cleanup | DeleteWorkflow → Direct OpenStack delete → Clean state update |
| **Configuration** | APPC LCM operations, Complex state machines | Ansible playbook execution via ansible-runner |
| **Scaling** | VF module dependencies, OOF placement, Complex orchestration | Add/remove VMs directly, Simple count adjustment |
| **Error Handling** | Manual intervention, Complex rollback BPMNs | Automatic Temporal retries, Clean rollback activities |
| **Recovery** | Manual workflow restart, State corruption risks | Automatic Temporal recovery, Zero data loss |

---

## Key Architectural Decisions

### 1. No Adapter Layers
**Legacy:** BPMN → Adapter → SDN-C/APPC/OpenStack
**Modern:** Workflow → Direct OpenStack API

**Benefit:** 50% fewer network hops, simpler debugging

### 2. Single Data Store
**Legacy:** MariaDB (Request DB) + MariaDB (Catalog DB) + MariaDB (Camunda DB) + A&AI
**Modern:** PostgreSQL (single source of truth)

**Benefit:** No data sync issues, simple queries

### 3. Temporal Workflows
**Legacy:** Camunda BPMN (requires UI designer, XML files)
**Modern:** Python code with decorators

**Benefit:** Easy testing, version control, type safety

### 4. Direct OpenStack APIs
**Legacy:** Heat templates → OpenStack Adapter → Woorea SDK → OpenStack
**Modern:** Python dict → httpx → OpenStack REST API

**Benefit:** Simple, debuggable, no SDK dependency

### 5. Async/Await
**Legacy:** Synchronous Java + Thread pools
**Modern:** Python async/await

**Benefit:** Efficient I/O, high concurrency

---

## Conclusion

The Modern Infrastructure Orchestrator's flows are **simple, direct, and reliable**:

- **Deployment**: One API call → Temporal workflow → Resources created
- **Status**: One database query → Full state returned
- **Deletion**: One API call → Clean teardown
- **Scaling**: Add/remove VMs directly
- **Recovery**: Automatic (Temporal handles it)

**No unnecessary complexity. No multi-layer abstractions. Just clean, maintainable flows.**

**Average deployment: 2-5 minutes vs 10-15 minutes (legacy)**
**Average query: 20ms vs 500ms (legacy)**
**Recovery: Automatic vs Manual (legacy)**