# Task: WS-K8 Create Task Endpoints

## Metadata

| Field | Value |
|-------|-------|
| **Task ID** | WS-K8 |
| **Task Name** | Create Task Endpoints |
| **Workstream** | mvp-production-readiness |
| **Phase** | P2 (Production Hardening) |
| **Batch** | P2-B2 |
| **Status** | `pending` |
| **Dependencies** | WS-K7 (TaskService — ⏳ Not yet complete) |
| **Complexity** | M (1-3 hours) |
| **Service** | deeptrail-control |
| **Validates** | Task CRUD via HTTP, Task Token issuance endpoint, P2 validation criteria |

---

## Specification

| Field | Value |
|-------|-------|
| **Spec File** | [WS-K8-spec.md](../specs/WS-K8-spec.md) |
| **Source** | `deepsecure-comprehensive-architecture-consolidated.md` Section 14.2 (Task Management Service) |
| **K6 Dependency** | [WS-K6-spec.md](../specs/WS-K6-spec.md) — Pydantic schemas: `TaskCreate`, `TaskResponse`, `TaskTokenResponse` |
| **K7 Dependency** | [WS-K7-spec.md](../specs/WS-K7-spec.md) — `TaskService`, `TaskNotFoundError`, `TaskPermissionError`, `TaskLifecycleError` |

### Key Contracts

| Component | Contract |
|-----------|----------|
| **Router prefix** | `/tasks` in `api.py` → endpoints at `/api/v1/tasks/...` |
| **POST `/`** | Create task → 201 `TaskResponse` or 403 (permission exceeded) |
| **GET `/{task_id}`** | Get task → 200 `TaskResponse` or 404 |
| **GET `/`** | List tasks → 200 with `tasks[]`, `total`, `limit`, `offset` |
| **POST `/{task_id}/activate`** | Pending → Active → 200 or 409 |
| **POST `/{task_id}/complete`** | Active → Completed → 200 or 409 |
| **POST `/{task_id}/revoke`** | Non-terminal → Revoked → 200 or 409 |
| **POST `/{task_id}/token`** | Issue JWT → 200 `TaskTokenResponse` or 409 |
| **Error mapping** | `TaskNotFoundError` → 404, `TaskPermissionError` → 403, `TaskLifecycleError` → 409 |

---

## API Contracts

### Endpoint: Create Task

| Field | Value |
|-------|-------|
| **Method** | `POST` |
| **Path** | `/api/v1/tasks` |
| **Auth** | Bearer token (Agent JWT or User JWT) |
| **Purpose** | Create a new task with scoped permissions |

**Request Body (`TaskCreate`):**

```json
{
  "name": "Research lead 12345",
  "description": "Look up contact details for lead 12345",
  "requested_permissions": [
    {
      "permission_urn": "hubspot:contacts:read",
      "constraints": { "id": "12345" },
      "max_usage": 10
    }
  ],
  "deadline_minutes": 60,
  "auto_revoke_on_complete": true
}
```

**Response (201):** `TaskResponse`

```json
{
  "task_id": "task-550e8400-...",
  "agent_id": "agent-sdr-001",
  "name": "Research lead 12345",
  "status": "pending",
  "scoped_permissions": [
    { "urn": "hubspot:contacts:read", "constraints": { "id": "12345" } }
  ],
  "deadline": "2026-04-07T15:00:00+00:00",
  "auto_revoke_on_complete": true,
  "created_at": "2026-04-07T14:00:00+00:00",
  "started_at": null,
  "completed_at": null
}
```

**Errors:** 400 (empty permissions / invalid deadline), 401 (unauthenticated), 403 (permissions exceed delegation)

---

### Endpoint: Get Task

| Field | Value |
|-------|-------|
| **Method** | `GET` |
| **Path** | `/api/v1/tasks/{task_id}` |
| **Auth** | Bearer token |
| **Purpose** | Retrieve task details |

**Response (200):** `TaskResponse`

**Errors:** 401, 404

---

### Endpoint: List Tasks

| Field | Value |
|-------|-------|
| **Method** | `GET` |
| **Path** | `/api/v1/tasks` |
| **Auth** | Bearer token |
| **Purpose** | List tasks for the authenticated agent/user |

**Query Parameters:** `status` (optional), `limit` (default 50, max 100), `offset` (default 0)

**Response (200):**

```json
{
  "tasks": [ /* TaskResponse[] */ ],
  "total": 15,
  "limit": 50,
  "offset": 0
}
```

---

### Endpoint: Activate Task

| Field | Value |
|-------|-------|
| **Method** | `POST` |
| **Path** | `/api/v1/tasks/{task_id}/activate` |
| **Auth** | Bearer token |
| **Purpose** | Transition task from pending to active |

**Response (200):** `TaskResponse` with `status: "active"`, `started_at` set

**Errors:** 404, 409 (invalid state transition)

---

### Endpoint: Complete Task

| Field | Value |
|-------|-------|
| **Method** | `POST` |
| **Path** | `/api/v1/tasks/{task_id}/complete` |
| **Auth** | Bearer token |
| **Purpose** | Complete a task (auto-revokes permissions if configured) |

**Response (200):** `TaskResponse` with `status: "completed"`, `completed_at` set

**Errors:** 404, 409

---

### Endpoint: Revoke Task

| Field | Value |
|-------|-------|
| **Method** | `POST` |
| **Path** | `/api/v1/tasks/{task_id}/revoke` |
| **Auth** | Bearer token |
| **Purpose** | Force-revoke a task and all its permissions |

**Response (200):** `TaskResponse` with `status: "revoked"`

**Errors:** 404, 409 (already terminal)

---

### Endpoint: Issue Task Token

| Field | Value |
|-------|-------|
| **Method** | `POST` |
| **Path** | `/api/v1/tasks/{task_id}/token` |
| **Auth** | Bearer token |
| **Purpose** | Issue a JWT Task Token for an active task |

**Response (200):** `TaskTokenResponse`

```json
{
  "task_id": "task-550e8400-...",
  "task_token": "eyJhbGciOiJIUzI1NiJ9...",
  "expires_at": "2026-04-07T15:00:00+00:00",
  "scoped_permissions": ["hubspot:contacts:read"]
}
```

**Errors:** 404, 409 (task not active)

---

## Pre-Conditions

- [x] WS-K6 complete (Task + ScopedPermission models, Pydantic schemas)
- [ ] WS-K7 complete (TaskService — business logic, error classes)
- [ ] `deeptrail-control` service compiles and starts
- [ ] `app/api/v1/api.py` router wiring available
- [ ] `app/api/deps.py` provides `get_db` and auth dependencies
- [ ] Existing endpoint patterns available: `agents.py`, `auth.py`

---

## Task Description

### Objective

Create RESTful API endpoints under `/api/v1/tasks` that expose `TaskService` (K7) functionality via HTTP, following the existing FastAPI patterns in the control plane. These endpoints enable task CRUD, lifecycle management, and Task Token JWT issuance.

### Background

The token hierarchy management in DeepSecure requires HTTP interfaces for:

1. **Agent/user interaction**: Agents create tasks before performing scoped operations
2. **Lifecycle transitions**: Tasks follow `PENDING → ACTIVE → COMPLETED` via explicit API calls
3. **Token issuance**: Active tasks produce Task Token JWTs used by the gateway for permission-scoped backend access
4. **P2 validation**: The production readiness criteria include testing task token generation and scoped calls via HTTP

The endpoints are thin HTTP wrappers around `TaskService` — they validate auth, extract identity, delegate to the service, and map errors to HTTP status codes. This follows the same pattern as `agents.py` and `auth.py`.

### What to Implement

#### 1. Task Router (`app/api/v1/endpoints/tasks.py`)

**7 endpoints**, all synchronous (matching TaskService):

**`POST /` — Create Task:**
- Extract agent identity from Bearer token via dependency
- Call `service.create_task(agent_id, initiated_by, task_data, delegation_id, delegation_permissions)`
- Map `TaskPermissionError` → 403 with `invalid_permissions` and `allowed_permissions`
- Return 201 `TaskResponse`

**`GET /{task_id}` — Get Task:**
- Call `service.get_task(task_id)`
- Map `TaskNotFoundError` → 404
- Return 200 `TaskResponse`

**`GET /` — List Tasks:**
- Accept `status`, `limit`, `offset` query params
- Call `service.list_tasks(agent_id, status, limit, offset)`
- Return 200 with `tasks[]`, `total`, `limit`, `offset`

**`POST /{task_id}/activate` — Activate Task:**
- Call `service.activate_task(task_id)`
- Map `TaskNotFoundError` → 404, `TaskLifecycleError` → 409

**`POST /{task_id}/complete` — Complete Task:**
- Call `service.complete_task(task_id)`
- Map errors same as activate

**`POST /{task_id}/revoke` — Revoke Task:**
- Call `service.revoke_task(task_id)`
- Map errors same as activate

**`POST /{task_id}/token` — Issue Task Token:**
- Call `service.issue_task_token(task_id)`
- Map `TaskNotFoundError` → 404, `TaskLifecycleError` → 409
- Return 200 `TaskTokenResponse`

#### 2. Optional List Response Schema

If needed, create `app/schemas/task.py` with `TaskListResponse`:

```python
class TaskListResponse(BaseModel):
    tasks: List[TaskResponse]
    total: int
    limit: int
    offset: int
```

#### 3. Router Wiring

In `app/api/v1/api.py`:

```python
from app.api.v1.endpoints import tasks
api_router.include_router(tasks.router, prefix="/tasks", tags=["tasks"])
```

---

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `deeptrail-control/app/api/v1/endpoints/tasks.py` | Create | Task router: 7 endpoints (create, get, list, activate, complete, revoke, token) |
| `deeptrail-control/app/schemas/task.py` | Create (optional) | `TaskListResponse` for list endpoint |
| `deeptrail-control/app/api/v1/api.py` | Modify | Add `include_router(tasks.router, prefix="/tasks", tags=["tasks"])` |
| `deeptrail-control/tests/api/test_tasks.py` | Create | Unit tests (16+ test cases) |

---

## Acceptance Criteria

### Functional

- [ ] `POST /api/v1/tasks` creates task, returns 201 with `TaskResponse`
- [ ] `GET /api/v1/tasks/{task_id}` returns task, or 404 if not found
- [ ] `GET /api/v1/tasks` lists tasks with optional `status`, `limit`, `offset`
- [ ] `POST /api/v1/tasks/{task_id}/activate` transitions PENDING → ACTIVE, or 409
- [ ] `POST /api/v1/tasks/{task_id}/complete` transitions ACTIVE → COMPLETED, or 409
- [ ] `POST /api/v1/tasks/{task_id}/revoke` revokes non-terminal task, or 409
- [ ] `POST /api/v1/tasks/{task_id}/token` issues JWT for active task, or 409
- [ ] Create with permissions exceeding delegation returns 403 with `invalid_permissions` detail
- [ ] List endpoint respects pagination (`limit`, `offset`) and returns `total`

### Security

- [ ] All endpoints require Bearer token authentication
- [ ] Unauthenticated requests return 401
- [ ] 403 on permission violation includes `invalid_permissions` and `allowed_permissions` (no secrets)
- [ ] No internal service details leaked in error responses

### Integration

- [ ] Router mounted at `/tasks` prefix in `api.py`
- [ ] Endpoints delegate to `TaskService` (K7) — no business logic in endpoints
- [ ] Service errors mapped: `TaskNotFoundError` → 404, `TaskPermissionError` → 403, `TaskLifecycleError` → 409
- [ ] Existing endpoints unaffected (no regression)
- [ ] Endpoints appear in OpenAPI schema (`/docs`)

---

## Test Cases

| Test Case | Method | Endpoint | Expected Status | Notes |
|-----------|--------|----------|-----------------|-------|
| Create task | POST | `/api/v1/tasks` | 201 | Returns TaskResponse |
| Create with invalid permissions | POST | `/api/v1/tasks` | 403 | Permissions exceed delegation |
| Create with empty permissions | POST | `/api/v1/tasks` | 400/422 | Pydantic validation |
| Get task | GET | `/api/v1/tasks/{id}` | 200 | Returns TaskResponse |
| Get task not found | GET | `/api/v1/tasks/{id}` | 404 | Task doesn't exist |
| List tasks | GET | `/api/v1/tasks` | 200 | Returns task list |
| List with status filter | GET | `/api/v1/tasks?status=active` | 200 | Filtered results |
| List with pagination | GET | `/api/v1/tasks?limit=10&offset=5` | 200 | Paginated |
| Activate task | POST | `/api/v1/tasks/{id}/activate` | 200 | status → active |
| Activate non-pending | POST | `/api/v1/tasks/{id}/activate` | 409 | Lifecycle error |
| Complete task | POST | `/api/v1/tasks/{id}/complete` | 200 | status → completed |
| Complete non-active | POST | `/api/v1/tasks/{id}/complete` | 409 | Lifecycle error |
| Revoke task | POST | `/api/v1/tasks/{id}/revoke` | 200 | status → revoked |
| Revoke terminal | POST | `/api/v1/tasks/{id}/revoke` | 409 | Already terminal |
| Issue task token | POST | `/api/v1/tasks/{id}/token` | 200 | Returns TaskTokenResponse |
| Issue token non-active | POST | `/api/v1/tasks/{id}/token` | 409 | Task not active |
| Unauthorized request | POST | `/api/v1/tasks` | 401 | Missing token |

---

## Post-Conditions

After this task is complete:

- [ ] Task management accessible via HTTP API
- [ ] P2 validation criteria for task token generation can be executed
- [ ] End-to-end flow: User creates task → Agent activates → Issues token → Uses in gateway
- [ ] OpenAPI documentation includes `/tasks` endpoints
- [ ] All P2-B2 tasks complete (L2, J6, K7, K8) — enables MP4 merge point consideration

---

## Validation

### Unit Tests

```bash
cd /Users/imaxxs/repositories/mvp-prod-control/deeptrail-control

# Run task endpoint tests
pytest tests/api/test_tasks.py -v

# Run K7 service tests (dependency check)
pytest tests/services/test_task_service.py -v

# Run all API tests (regression check)
pytest tests/api/ -v
```

### Manual Verification

```bash
# 1. Start services
cd /Users/imaxxs/repositories/deepsecure-mvp
docker compose up -d
sleep 15

# 2. Get a user token
USER_TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"sarah@acme.com","password":"test_password"}' | jq -r '.token')

# 3. Verify task endpoints appear in OpenAPI
curl -s http://localhost:8000/openapi.json | jq '.paths | keys | map(select(startswith("/api/v1/tasks")))'
# Expected: ["/api/v1/tasks", "/api/v1/tasks/{task_id}", "/api/v1/tasks/{task_id}/activate", ...]

# 4. Create a task
TASK_RESP=$(curl -s -X POST http://localhost:8000/api/v1/tasks \
  -H "Authorization: Bearer $USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Research lead 12345",
    "requested_permissions": [
      {"permission_urn": "hubspot:contacts:read", "constraints": {"id": "12345"}}
    ],
    "deadline_minutes": 60,
    "auto_revoke_on_complete": true
  }')
TASK_ID=$(echo "$TASK_RESP" | jq -r '.task_id')
echo "Created task: $TASK_ID"
echo "$TASK_RESP" | jq '.status'
# Expected: "pending"

# 5. Get task
curl -s http://localhost:8000/api/v1/tasks/$TASK_ID \
  -H "Authorization: Bearer $USER_TOKEN" | jq '.status'
# Expected: "pending"

# 6. List tasks
curl -s "http://localhost:8000/api/v1/tasks?status=pending" \
  -H "Authorization: Bearer $USER_TOKEN" | jq '.total'
# Expected: ≥ 1

# 7. Activate task
curl -s -X POST http://localhost:8000/api/v1/tasks/$TASK_ID/activate \
  -H "Authorization: Bearer $USER_TOKEN" | jq '.status'
# Expected: "active"

# 8. Issue task token
TOKEN_RESP=$(curl -s -X POST http://localhost:8000/api/v1/tasks/$TASK_ID/token \
  -H "Authorization: Bearer $USER_TOKEN")
echo "$TOKEN_RESP" | jq '.task_token' | head -c 50
# Expected: JWT string starting with "eyJ..."
echo "$TOKEN_RESP" | jq '.scoped_permissions'
# Expected: ["hubspot:contacts:read"]

# 9. Complete task
curl -s -X POST http://localhost:8000/api/v1/tasks/$TASK_ID/complete \
  -H "Authorization: Bearer $USER_TOKEN" | jq '.status'
# Expected: "completed"

# 10. Try to activate again (should fail)
curl -s -o /dev/null -w "%{http_code}" -X POST \
  http://localhost:8000/api/v1/tasks/$TASK_ID/activate \
  -H "Authorization: Bearer $USER_TOKEN"
# Expected: 409

# 11. Test unauthorized
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/v1/tasks
# Expected: 401
```

---

## References

- **Spec:** [WS-K8-spec.md](../specs/WS-K8-spec.md) — full endpoint contracts, router structure, error mapping
- **K6 Spec:** [WS-K6-spec.md](../specs/WS-K6-spec.md) — `TaskCreate`, `TaskResponse`, `TaskTokenResponse` schemas
- **K7 Spec:** [WS-K7-spec.md](../specs/WS-K7-spec.md) — `TaskService`, error classes
- **Architecture:** `deepsecure-comprehensive-architecture-consolidated.md` Section 14.2
- **Endpoint Pattern:** `deeptrail-control/app/api/v1/endpoints/agents.py` — router, deps, HTTPException mapping
- **Router Wiring:** `deeptrail-control/app/api/v1/api.py` — `include_router` pattern
- **Upstream:** WS-K7 (TaskService — must be complete first)
- **Downstream:** P2 validation (task token generation, scoped calls)

---

## Execution

```bash
# Run in mvp-prod-control worktree:
cd /Users/imaxxs/repositories/mvp-prod-control

# Execute the task (after WS-K7 is complete)
/execute-task WS-K8 mvp-production-readiness

# After completion
/complete-task WS-K8 mvp-production-readiness
```
