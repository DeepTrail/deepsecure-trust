# Task: WS-K7 Create TaskService

## Metadata

| Field | Value |
|-------|-------|
| **Task ID** | WS-K7 |
| **Task Name** | Create TaskService |
| **Workstream** | mvp-production-readiness |
| **Phase** | P2 (Production Hardening) |
| **Batch** | P2-B2 |
| **Status** | `ready` |
| **Dependencies** | WS-K6 (Task + ScopedPermission models — ✅ Complete) |
| **Complexity** | M (1-3 hours) |
| **Service** | deeptrail-control |
| **Validates** | Task lifecycle management, permission scoping (⊆ delegation), Task Token JWT issuance (Layer 4) |

---

## Specification

| Field | Value |
|-------|-------|
| **Spec File** | [WS-K7-spec.md](../specs/WS-K7-spec.md) |
| **Source** | `deepsecure-comprehensive-architecture-consolidated.md` Section 14.2 (Task Management Service), Section 9 (Per-Task Permission Architecture) |
| **K6 Dependency** | [WS-K6-spec.md](../specs/WS-K6-spec.md) — Task, ScopedPermission, TaskStatus, Pydantic schemas, `to_token_claims()` |

### Key Contracts

| Component | Contract |
|-----------|----------|
| **TaskService class** | `__init__(db: Session, jwt_secret: str)` — synchronous methods matching existing service pattern |
| **create_task()** | Validates `requested_permissions ⊆ delegation_permissions`, creates Task + ScopedPermission records |
| **get_task() / list_tasks()** | Query with optional `agent_id` ownership check, status filter, pagination |
| **activate_task()** | `PENDING → ACTIVE` with lifecycle guard |
| **complete_task()** | `ACTIVE → COMPLETED`, auto-revoke permissions if configured |
| **revoke_task()** | Force-revoke non-terminal tasks |
| **issue_task_token()** | Issue JWT (HS256): `task_id`, `agent_id`, `scoped_permissions`, `exp=min(deadline, now+1h)`, `iss=deepsecure-control`, `aud=deepsecure-gateway`, `token_type=task_token` |
| **check_deadline_timeouts()** | Timeout all non-terminal tasks past deadline |
| **Error hierarchy** | `TaskServiceError` → `TaskNotFoundError`, `TaskPermissionError`, `TaskLifecycleError` |

---

## API Contracts

> **Note:** This task implements the service (business logic) layer, not API endpoints.
> API endpoints exposing this service are implemented in WS-K8.
> The `TaskService` provides the business logic that WS-K8 endpoints delegate to.

---

## Pre-Conditions

- [x] WS-K6 complete (Task + ScopedPermission models, Pydantic schemas, `to_token_claims()`, Alembic migration)
- [ ] `deeptrail-control` service compiles and starts
- [ ] K6 models importable: `app.models.task_token` — `Task`, `ScopedPermission`, `TaskStatus`, `TaskCreate`, `TaskResponse`, `TaskTokenResponse`, `generate_task_id`, `generate_scoped_permission_id`
- [ ] Existing service patterns available as reference: `delegation_service.py`, `agent_session_service.py`
- [ ] `pyjwt` package available (already in dependencies)

---

## Task Description

### Objective

Create a `TaskService` class that provides all business logic for task lifecycle management and Task Token JWT issuance. This service manages Layer 4 of the DeepSecure token hierarchy.

### Background

The token hierarchy in DeepSecure follows a strict monotonic attenuation chain:

```
Layer 0: User ID-Token (human identity)
Layer 1: Organization Key (org-scoped credentials)
Layer 2: Agent ID-Token (agent identity, Ed25519)
Layer 3: Delegation Token (user → agent permission grant)
Layer 4: Task Token ← THIS SERVICE
```

WS-K6 created the ORM models (`Task`, `ScopedPermission`) and Pydantic schemas. This task creates the service layer that enforces business rules:

1. **Permission scoping**: Requested task permissions must be a subset of the delegation's permissions (monotonic attenuation)
2. **Lifecycle management**: Tasks follow `PENDING → ACTIVE → COMPLETED` with guards preventing invalid transitions
3. **JWT issuance**: Active tasks can produce Task Token JWTs carrying scoped permissions with bounded expiry
4. **Deadline enforcement**: Past-deadline tasks are automatically timed out

Existing services (`DelegationService`, `AgentSessionService`) establish the pattern: synchronous methods, `Session` injection, domain-specific error classes, structured logging.

### What to Implement

#### 1. Error Classes

In `deeptrail-control/app/services/task_service.py`:

- **`TaskServiceError(Exception)`**: Base error
- **`TaskNotFoundError(TaskServiceError)`**: Task does not exist or agent mismatch
- **`TaskPermissionError(TaskServiceError)`**: With `invalid_permissions: List[str]` and `allowed_permissions: List[str]` attributes
- **`TaskLifecycleError(TaskServiceError)`**: Invalid state transition

#### 2. TaskService Class

Constructor: `def __init__(self, db: Session, jwt_secret: str)`

**`create_task(agent_id, initiated_by, task_data: TaskCreate, delegation_id=None, delegation_permissions=None) -> Task`:**
- Validate `requested_permissions ⊆ delegation_permissions` via `_validate_permissions_subset()` (only if `delegation_permissions` is provided)
- Create `Task` record with `status=PENDING`, `deadline = now + deadline_minutes`
- Create `ScopedPermission` records for each requested permission with `valid_until = deadline or now+24h`
- Commit and refresh, return Task

**`get_task(task_id, agent_id=None) -> Task`:**
- Query by `task_id`; if `agent_id` provided, filter by `agent_id` too
- Raise `TaskNotFoundError` if not found

**`list_tasks(agent_id, status=None, limit=50, offset=0) -> List[Task]`:**
- Filter by `agent_id`, optionally by `status`
- Order by `created_at` descending
- Apply `limit` and `offset`

**`activate_task(task_id, agent_id=None) -> Task`:**
- Get task, verify `status == PENDING`, call `task.activate()` (K6 lifecycle method), commit

**`complete_task(task_id, agent_id=None) -> Task`:**
- Get task, verify `status == ACTIVE`, call `task.complete()`, if `auto_revoke_on_complete`, revoke all permissions, commit

**`revoke_task(task_id, agent_id=None) -> Task`:**
- Get task, verify not terminal, call `task.revoke()`, revoke all permissions, commit

**`issue_task_token(task_id, agent_id=None) -> TaskTokenResponse`:**
- Get task, verify `status == ACTIVE`
- Build claims via `task.to_token_claims()` (from K6)
- Set `exp = min(deadline, now+1h)`, `iss = "deepsecure-control"`, `aud = "deepsecure-gateway"`, `token_type = "task_token"`
- Sign JWT with `jwt.encode(claims, self._jwt_secret, algorithm="HS256")`
- Return `TaskTokenResponse(task_id, task_token, expires_at, scoped_permissions)`

**`check_deadline_timeouts() -> int`:**
- Query all non-terminal tasks where `deadline < now`
- Call `task.timeout()` on each (K6 lifecycle method)
- Commit, return count

#### 3. Private Helper

**`_validate_permissions_subset(requested: List[str], allowed: List[str])`:**
- Compute `set(requested) - set(allowed)` → invalid
- If invalid non-empty, raise `TaskPermissionError` with `invalid_permissions` and `allowed_permissions`

---

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `deeptrail-control/app/services/task_service.py` | Create | TaskService class, error classes, permission validation, lifecycle management, JWT issuance |
| `deeptrail-control/tests/services/test_task_service.py` | Create | Unit tests (22+ test cases) |

---

## Acceptance Criteria

### Functional

- [ ] `create_task()` creates Task + ScopedPermission records with `status=PENDING`
- [ ] `create_task()` validates `requested ⊆ delegation` when `delegation_permissions` provided
- [ ] `create_task()` skips validation when `delegation_permissions` is `None`
- [ ] `create_task()` correctly computes `deadline` from `deadline_minutes`
- [ ] `get_task()` returns task by ID with loaded `scoped_permission_records`
- [ ] `get_task()` raises `TaskNotFoundError` for invalid ID or wrong `agent_id`
- [ ] `list_tasks()` filters by `agent_id`, optional `status`, ordered by `created_at` desc
- [ ] `list_tasks()` respects `limit` and `offset` pagination
- [ ] `activate_task()` transitions `PENDING → ACTIVE` and sets `started_at`
- [ ] `activate_task()` raises `TaskLifecycleError` for non-PENDING task
- [ ] `complete_task()` transitions `ACTIVE → COMPLETED` and sets `completed_at`
- [ ] `complete_task()` auto-revokes permissions when `auto_revoke_on_complete=True`
- [ ] `complete_task()` raises `TaskLifecycleError` for non-ACTIVE task
- [ ] `revoke_task()` transitions non-terminal → `REVOKED`
- [ ] `revoke_task()` raises `TaskLifecycleError` for terminal tasks
- [ ] `issue_task_token()` returns valid JWT with correct claims
- [ ] Token `exp = min(deadline, now+1h)` — never exceeds deadline
- [ ] Token includes `iss`, `aud`, `token_type`, `task_id`, `agent_id`, `scoped_permissions`
- [ ] `issue_task_token()` raises `TaskLifecycleError` for non-ACTIVE task
- [ ] `check_deadline_timeouts()` timeouts past-deadline non-terminal tasks
- [ ] `check_deadline_timeouts()` skips already-terminal tasks

### Security

- [ ] Permission attenuation enforced: `task_permissions ⊆ delegation_permissions` (monotonic)
- [ ] JWT secrets not logged
- [ ] Token expiry bounded — never longer than task deadline
- [ ] Ownership checks prevent cross-agent access when `agent_id` provided

### Integration

- [ ] TaskService constructor matches existing service pattern (`db: Session`)
- [ ] Error hierarchy doesn't collide with existing service errors
- [ ] K6 model imports work (`Task`, `ScopedPermission`, `TaskStatus`, schemas)
- [ ] JWT can be decoded by gateway using same secret + HS256 algorithm
- [ ] Service is importable: `from app.services.task_service import TaskService`

---

## Test Cases

| Test Case | Method | Expected | Notes |
|-----------|--------|----------|-------|
| Create task happy path | `create_task()` | Task created, status=PENDING | With valid permissions |
| Create task permission subset check | `create_task()` | `TaskPermissionError` | Requested > delegation |
| Create task no delegation check | `create_task()` | Task created | `delegation_permissions=None` |
| Create task with deadline | `create_task()` | deadline set correctly | Minutes → datetime |
| Create task generates ScopedPermission records | `create_task()` | N records = N requested | Relationship populated |
| Get task by ID | `get_task()` | Returns task | Happy path |
| Get task not found | `get_task()` | `TaskNotFoundError` | Invalid ID |
| Get task wrong agent | `get_task()` | `TaskNotFoundError` | Ownership check |
| List tasks by agent | `list_tasks()` | Filtered list | Ordered by created_at desc |
| List tasks by status | `list_tasks()` | Filtered | Status filter |
| Activate pending task | `activate_task()` | status=ACTIVE | pending → active |
| Activate non-pending | `activate_task()` | `TaskLifecycleError` | Invalid transition |
| Complete active task | `complete_task()` | status=COMPLETED | active → completed |
| Complete with auto-revoke | `complete_task()` | Permissions revoked | `auto_revoke_on_complete=True` |
| Complete non-active | `complete_task()` | `TaskLifecycleError` | Invalid transition |
| Revoke task | `revoke_task()` | status=REVOKED | Force revoke |
| Revoke terminal task | `revoke_task()` | `TaskLifecycleError` | Already terminal |
| Issue task token | `issue_task_token()` | Valid JWT | Active task |
| Issue token non-active | `issue_task_token()` | `TaskLifecycleError` | Not active |
| Issue token respects deadline | `issue_task_token()` | `exp` = min(deadline, now+1h) | Deadline sooner |
| Issue token default TTL | `issue_task_token()` | `exp` = now+1h | No deadline |
| Token claims correctness | `issue_task_token()` | Decode: `task_id`, `agent_id`, `iss`, `aud`, `token_type` | JWT decode |
| Check deadline timeouts | `check_deadline_timeouts()` | Past-deadline tasks timed out | Count returned |
| Timeout skips terminal | `check_deadline_timeouts()` | Terminal unchanged | Idempotent |

---

## Post-Conditions

After this task is complete:

- [ ] WS-K8 (Task API endpoints) can be implemented — endpoints delegate to `TaskService`
- [ ] Task lifecycle management available: create → activate → complete/revoke/timeout
- [ ] Permission scoping enforced at service layer (subset validation)
- [ ] Task Token JWTs can be issued for active tasks
- [ ] Deadline enforcement mechanism available via `check_deadline_timeouts()`

---

## Validation

### Unit Tests

```bash
cd /Users/imaxxs/repositories/mvp-prod-control/deeptrail-control

# Run TaskService tests
pytest tests/services/test_task_service.py -v

# Run K6 model tests (dependency check)
pytest tests/models/test_task_token.py -v

# Run all service tests (regression check)
pytest tests/services/ -v
```

### Manual Verification

```bash
# 1. Verify import works
cd /Users/imaxxs/repositories/mvp-prod-control/deeptrail-control
python -c "
from app.services.task_service import (
    TaskService,
    TaskServiceError,
    TaskNotFoundError,
    TaskPermissionError,
    TaskLifecycleError,
)
print('TaskService imported successfully')
print('Methods:', [m for m in dir(TaskService) if not m.startswith('_')])
"
# Expected: TaskService imported, methods listed

# 2. Verify K6 model dependency is accessible
python -c "
from app.models.task_token import Task, ScopedPermission, TaskStatus, TaskCreate, TaskTokenResponse
print('K6 models imported successfully')
print('TaskStatus values:', [s.value for s in TaskStatus])
"
# Expected: Models imported, statuses listed

# 3. Verify JWT signing works
python -c "
import jwt
from datetime import datetime, timezone, timedelta
claims = {
    'task_id': 'task-test',
    'agent_id': 'agent-test',
    'token_type': 'task_token',
    'iss': 'deepsecure-control',
    'aud': 'deepsecure-gateway',
    'exp': int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
}
token = jwt.encode(claims, 'test-secret', algorithm='HS256')
decoded = jwt.decode(token, 'test-secret', algorithms=['HS256'], audience='deepsecure-gateway')
print('JWT round-trip OK:', decoded['task_id'], decoded['token_type'])
"
# Expected: JWT round-trip OK: task-test task_token

# 4. Verify permission subset validation logic
python -c "
requested = {'hubspot:contacts:read', 'slack:messages:send'}
allowed = {'hubspot:contacts:read', 'hubspot:contacts:write'}
invalid = requested - allowed
print('Invalid:', sorted(invalid))
assert invalid == {'slack:messages:send'}, 'Subset check works'
print('Permission subset validation logic verified')
"
# Expected: Invalid: ['slack:messages:send']
```

---

## References

- **Spec:** [WS-K7-spec.md](../specs/WS-K7-spec.md) — full method contracts, JWT format, permission validation, test code
- **K6 Spec:** [WS-K6-spec.md](../specs/WS-K6-spec.md) — Task, ScopedPermission models, `to_token_claims()`, Pydantic schemas
- **Architecture:** `deepsecure-comprehensive-architecture-consolidated.md` Section 14.2, Section 9
- **Pattern Reference:** `deeptrail-control/app/services/delegation_service.py` — permission validation, error handling
- **JWT Pattern:** `deeptrail-control/app/services/agent_session_service.py` — JWT issuance, HS256 signing
- **Upstream:** WS-K6 (✅ Complete)
- **Downstream:** WS-K8 (Task API endpoints — depends on TaskService)

---

## Execution

```bash
# Run in mvp-prod-control worktree:
cd /Users/imaxxs/repositories/mvp-prod-control

# Execute the task
/execute-task WS-K7 mvp-production-readiness

# After completion
/complete-task WS-K7 mvp-production-readiness
```
