# Task: WS-K6 Create TaskToken Model

## Metadata

| Field | Value |
|-------|-------|
| **Task ID** | WS-K6 |
| **Task Name** | Create TaskToken Model |
| **Workstream** | mvp-production-readiness |
| **Phase** | P2 (Production Hardening) |
| **Batch** | P2-B1 |
| **Status** | `ready` |
| **Dependencies** | MP3.5 (P1.5 complete — ✅ reached Feb 23, 2026) |
| **Complexity** | M (1-3 hours) |
| **Service** | deeptrail-control |
| **Validates** | Token Layer 4 (per-task scoped permissions), task lifecycle management |

---

## Specification

| Field | Value |
|-------|-------|
| **Spec File** | [WS-K6-spec.md](../specs/WS-K6-spec.md) |
| **Source** | `deepsecure-comprehensive-architecture-consolidated.md` Sections 7, 9, 14.2 (Layer 4: Task Token, Per-Task Permission Architecture, Task Management Service) |
| **Token Hierarchy** | Layer 4 of the 6-layer token hierarchy — unique to DeepSecure (not in research paper) |

### Key Contracts

| Component | Contract |
|-----------|----------|
| **Task** | SQLAlchemy model: `tasks` table — 14 columns including JSONB `scoped_permissions`, `constraints`, `usage_summary` |
| **ScopedPermission** | SQLAlchemy model: `scoped_permissions` table — FK to `tasks.id`, usage tracking, expiry, revocation |
| **TaskStatus** | Constants class: `PENDING`, `ACTIVE`, `COMPLETED`, `REVOKED`, `TIMED_OUT` + `TERMINAL` and `ACTIVE_STATES` sets |
| **ID Generation** | `generate_task_id()` → `task-<uuid>`, `generate_scoped_permission_id()` → `sp-<uuid>` |
| **Lifecycle Methods** | `activate()`, `complete()`, `revoke()`, `timeout()` with state guards |
| **Hybrid Properties** | `is_active`, `is_terminal`, `is_past_deadline` (Task); `is_expired`, `is_exhausted`, `is_usable` (ScopedPermission) |
| **JWT Serialization** | `to_token_claims()` → `{task_id, agent_id, scoped_permissions, deadline, auto_revoke_on_complete, iat}` |
| **Auto-revoke** | `complete()` with `auto_revoke_on_complete=True` sets all `ScopedPermission.revoked=True` |
| **Pydantic Schemas** | `ScopedPermissionRequest`, `TaskCreate` (min 1 perm, deadline 1–1440 min), `TaskResponse`, `TaskTokenResponse` |
| **Alembic Migration** | Creates `tasks` + `scoped_permissions` tables with 7 indexes |

---

## API Contracts

> **Note:** This task creates the data model and Pydantic schemas, not API endpoints.
> API endpoints are implemented in WS-K8.
> The model provides `to_token_claims()` for JWT serialization used by WS-K7 (TaskService).

### Future Endpoint Reference (WS-K8)

| Method | Path | Purpose | Schema |
|--------|------|---------|--------|
| `POST` | `/api/v1/tasks` | Create a task | `TaskCreate` → `TaskResponse` |
| `GET` | `/api/v1/tasks/{task_id}` | Get task details | → `TaskResponse` |
| `POST` | `/api/v1/tasks/{task_id}/complete` | Complete a task | → `TaskResponse` |
| `POST` | `/api/v1/tasks/{task_id}/revoke` | Revoke a task | → `TaskResponse` |

---

## Pre-Conditions

- [x] MP3.5 reached (P1.5 integration bugs fixed — Feb 23, 2026)
- [ ] `deeptrail-control` service compiles and starts
- [ ] `app/db/base.py` contains `Base` declarative base for SQLAlchemy
- [ ] `app/models/` directory exists with established patterns (`delegation.py`, `agent_session.py`)
- [ ] Alembic is configured (`migrations/` directory with `env.py`)

---

## Task Description

### Objective

Create the `Task` and `ScopedPermission` SQLAlchemy ORM models representing Layer 4 of the DeepSecure token hierarchy (Task Token), along with Pydantic API schemas and an Alembic migration to create the database tables.

### Background

The Control Plane currently has no concept of "tasks." Agents operate with session-level permissions (Layer 3: Agent Session JWT) where all delegated permissions are available for all work. This violates the principle of least privilege — an agent researching a single lead shouldn't have the same permissions as one doing a bulk export.

The architecture defines a 6-layer token hierarchy where Layer 4 (Task Token) provides per-task scoped permissions:

```
Layer 1: Platform Root Key
Layer 2: Organization Admin Token
Layer 3: Agent Session JWT  ← current maximum granularity
Layer 4: Task Token          ← THIS TASK (WS-K6)
Layer 5: Tool Call Token
Layer 6: Secret Access Token
```

Each task narrows the agent's permissions to exactly what's needed for a specific work unit, with automatic revocation on completion and deadline enforcement.

**Pattern reference:** The existing `delegation.py` model serves as the implementation template — same ORM style, JSONB column usage, hybrid properties, and ID generation patterns.

### What to Implement

#### 1. SQLAlchemy Models (`task_token.py`)

**Task model** — 14 columns:
- Identity: `id` (String, `task-<uuid>`), `agent_id`, `delegation_id`, `initiated_by`
- Descriptive: `name`, `description`
- State: `status` (pending/active/completed/revoked/timed_out)
- Permissions: `scoped_permissions` (JSONB list), `constraints` (JSONB dict)
- Lifecycle: `deadline`, `auto_revoke_on_complete`, `created_at`, `started_at`, `completed_at`
- Audit: `usage_summary` (JSONB dict)

Business methods:
- `activate()` — pending → active, sets `started_at`
- `complete()` — active → completed, sets `completed_at`, auto-revokes permissions
- `revoke()` — pending/active → revoked, revokes all permissions
- `timeout()` — non-terminal → timed_out (idempotent on terminal states)
- `_revoke_all_permissions()` — cascades revocation to all ScopedPermission records
- `has_scoped_permission(urn)` — checks JSONB `scoped_permissions`
- `get_active_permission_urns()` — returns URNs of usable ScopedPermission records
- `to_token_claims()` — serializes to Layer 4 JWT claims

Hybrid properties: `is_active`, `is_terminal`, `is_past_deadline`

**ScopedPermission model** — 8 columns:
- Identity: `id` (String, `sp-<uuid>`), `task_id` (FK)
- Permission: `permission_urn`, `constraints` (JSONB)
- Lifecycle: `valid_until`, `revoked`, `created_at`
- Usage: `usage_count`, `max_usage`

Business methods:
- `increment_usage()` — increments counter, returns False if exhausted

Hybrid properties: `is_expired`, `is_exhausted`, `is_usable`

**Indexes** — 7 total:
- Tasks: `ix_task_agent_id`, `ix_task_status`, `ix_task_agent_status` (composite), `ix_task_deadline`, `ix_task_initiated_by`
- ScopedPermissions: `ix_scoped_perm_task_id`, `ix_scoped_perm_urn`, `ix_scoped_perm_task_urn` (composite)

**Relationships:**
- `Task.scoped_permission_records` → One-to-Many → `ScopedPermission`
- `ScopedPermission.task` → Many-to-One → `Task`

#### 2. Pydantic Schemas (same file)

- `ScopedPermissionRequest` — request body for a single scoped permission
- `TaskCreate` — create task request (min 1 permission, deadline 1–1440 min)
- `TaskResponse` — task read response (with `from_attributes = True`)
- `TaskTokenResponse` — token issuance response

#### 3. Alembic Migration

Create migration file `xxx_create_task_tables.py`:
- `upgrade()`: Create `tasks` table, create `scoped_permissions` table with FK, create all indexes
- `downgrade()`: Drop `scoped_permissions`, drop `tasks`

#### 4. Model Exports

Update `app/models/__init__.py` to export `Task`, `ScopedPermission`, `TaskStatus`, ID generators, and Pydantic schemas.

---

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `deeptrail-control/app/models/task_token.py` | Create | `Task` + `ScopedPermission` ORM models, `TaskStatus`, ID generators, Pydantic schemas |
| `deeptrail-control/app/models/__init__.py` | Modify | Export Task, ScopedPermission, TaskStatus, schemas |
| `deeptrail-control/migrations/versions/xxx_create_task_tables.py` | Create | Alembic migration for `tasks` + `scoped_permissions` tables |
| `deeptrail-control/tests/models/test_task_token.py` | Create | Unit tests for models, lifecycle, hybrid properties, schemas |

---

## Acceptance Criteria

### Functional

- [ ] `Task` model inherits `Base` from `app.db.base` and maps to `tasks` table
- [ ] `ScopedPermission` model inherits `Base` and maps to `scoped_permissions` table
- [ ] All 14 Task columns match spec (names, types, nullability, defaults)
- [ ] All 8 ScopedPermission columns match spec
- [ ] `TaskStatus` constants: `PENDING`, `ACTIVE`, `COMPLETED`, `REVOKED`, `TIMED_OUT`
- [ ] `TaskStatus.TERMINAL` and `ACTIVE_STATES` sets defined correctly
- [ ] ID generation: `generate_task_id()` → `task-<uuid>`, `generate_scoped_permission_id()` → `sp-<uuid>`
- [ ] Lifecycle methods work: `activate()`, `complete()`, `revoke()`, `timeout()`
- [ ] Invalid transitions raise `ValueError` (e.g., activate non-pending, complete non-active, revoke terminal)
- [ ] `timeout()` is idempotent on terminal states (no error)
- [ ] `auto_revoke_on_complete` cascades: `complete()` sets all `ScopedPermission.revoked=True`
- [ ] Hybrid properties: `is_active`, `is_terminal`, `is_past_deadline` on Task
- [ ] Hybrid properties: `is_expired`, `is_exhausted`, `is_usable` on ScopedPermission
- [ ] `to_token_claims()` produces correct Layer 4 JWT claims dict
- [ ] `has_scoped_permission(urn)` performs JSONB lookup
- [ ] `get_active_permission_urns()` returns only usable permission URNs
- [ ] `ScopedPermission.increment_usage()` increments counter and respects `max_usage`
- [ ] JSONB columns use `JSON().with_variant(postgresql.JSONB(), "postgresql")` for cross-DB compatibility
- [ ] Timezone-aware datetimes with `_ensure_tz()` helper
- [ ] One-to-Many relationship: `Task.scoped_permission_records` with `cascade="all, delete-orphan"`

### Schema Validation

- [ ] `TaskCreate` validates: `min_length=1` on `requested_permissions`, `deadline_minutes` range `1–1440`
- [ ] `TaskCreate` rejects empty permissions list (Pydantic ValidationError)
- [ ] `TaskResponse` uses `from_attributes = True` for ORM serialization
- [ ] `ScopedPermissionRequest` requires `permission_urn` field

### Database/Migration

- [ ] Alembic migration creates `tasks` table with all columns
- [ ] Alembic migration creates `scoped_permissions` table with FK to `tasks.id` (CASCADE delete)
- [ ] 7 indexes created: 5 on tasks, 2+1 composite on scoped_permissions
- [ ] `downgrade()` drops both tables cleanly
- [ ] Migration applies successfully: `alembic upgrade head`

### Integration

- [ ] Models exported from `app/models/__init__.py`
- [ ] Model imports work: `from app.models.task_token import Task, ScopedPermission, TaskStatus`
- [ ] No regression in existing models (delegation, agent_session, vault_token)

---

## Test Cases

| Test Case | Method | Module | Expected | Notes |
|-----------|--------|--------|----------|-------|
| Create task with defaults | `Task()` | `test_task_token.py` | status="pending", auto_revoke=True | Constructor |
| generate_task_id format | `generate_task_id()` | `test_task_token.py` | Starts with "task-", len > 10 | ID pattern |
| generate_scoped_permission_id | `generate_scoped_permission_id()` | `test_task_token.py` | Starts with "sp-" | ID pattern |
| Activate from pending | `task.activate()` | `test_task_token.py` | status=ACTIVE, started_at set | Valid transition |
| Cannot activate active task | `task.activate()` | `test_task_token.py` | Raises `ValueError` | Guard clause |
| Complete from active | `task.complete()` | `test_task_token.py` | status=COMPLETED, completed_at set | Valid transition |
| Cannot complete pending task | `task.complete()` | `test_task_token.py` | Raises `ValueError` | Guard clause |
| Revoke from active | `task.revoke()` | `test_task_token.py` | status=REVOKED, all perms revoked | Valid transition |
| Cannot revoke terminal | `task.revoke()` | `test_task_token.py` | Raises `ValueError` | Guard clause |
| Timeout from active | `task.timeout()` | `test_task_token.py` | status=TIMED_OUT, perms revoked | Deadline exceeded |
| Timeout idempotent terminal | `task.timeout()` | `test_task_token.py` | No error, status unchanged | Graceful |
| is_active property | `task.is_active` | `test_task_token.py` | True when ACTIVE | Hybrid property |
| is_terminal property | `task.is_terminal` | `test_task_token.py` | True for COMPLETED/REVOKED/TIMED_OUT | Hybrid property |
| is_past_deadline with past | `task.is_past_deadline` | `test_task_token.py` | True | Timezone-aware |
| is_past_deadline no deadline | `task.is_past_deadline` | `test_task_token.py` | False | Null deadline |
| has_scoped_permission found | `task.has_scoped_permission()` | `test_task_token.py` | True | JSONB lookup |
| has_scoped_permission missing | `task.has_scoped_permission()` | `test_task_token.py` | False | Not in list |
| to_token_claims | `task.to_token_claims()` | `test_task_token.py` | Correct JWT claims dict | Serialization |
| Auto-revoke on complete | `task.complete()` | `test_task_token.py` | ScopedPermission.revoked=True | Cascade |
| SP is_usable valid | `sp.is_usable` | `test_task_token.py` | True | Not revoked/expired/exhausted |
| SP not usable revoked | `sp.is_usable` | `test_task_token.py` | False | Revoked |
| SP not usable expired | `sp.is_usable` | `test_task_token.py` | False | Past valid_until |
| SP increment_usage | `sp.increment_usage()` | `test_task_token.py` | True, count+1 | Counter |
| SP increment exhausted | `sp.increment_usage()` | `test_task_token.py` | False | At max_usage |
| TaskCreate validation | `TaskCreate(...)` | `test_task_token.py` | Valid model | Pydantic |
| TaskCreate empty perms | `TaskCreate(requested_permissions=[])` | `test_task_token.py` | ValidationError | min_length=1 |
| TaskResponse from_attributes | `TaskResponse.model_validate()` | `test_task_token.py` | Serializes correctly | ORM mode |

---

## Post-Conditions

After this task is complete:

- [ ] `tasks` and `scoped_permissions` tables exist in the database
- [ ] WS-K7 (TaskService) can proceed — has `Task` and `ScopedPermission` models to operate on
- [ ] WS-K8 (Task API endpoints) can proceed — has Pydantic schemas for request/response
- [ ] Token Layer 4 data model is in place for the per-task permission architecture
- [ ] Auto-revocation logic is model-level, no external dependencies

---

## Validation

### Unit Tests

```bash
cd /Users/imaxxs/repositories/mvp-prod-control/deeptrail-control

# Run task token model tests
pytest tests/models/test_task_token.py -v

# Run all model tests to check no regression
pytest tests/models/ -v
```

### Migration Test

```bash
cd /Users/imaxxs/repositories/mvp-prod-control/deeptrail-control

# Generate migration (verify it matches spec)
alembic revision --autogenerate -m "create task tables"

# Apply migration
alembic upgrade head

# Verify tables exist
docker compose exec db psql -U deepsecure_user -d deeptrail_controldb -c "\dt tasks"
docker compose exec db psql -U deepsecure_user -d deeptrail_controldb -c "\dt scoped_permissions"

# Verify indexes
docker compose exec db psql -U deepsecure_user -d deeptrail_controldb -c "\di ix_task_*"
docker compose exec db psql -U deepsecure_user -d deeptrail_controldb -c "\di ix_scoped_perm_*"

# Verify FK constraint
docker compose exec db psql -U deepsecure_user -d deeptrail_controldb -c "
SELECT conname, conrelid::regclass, confrelid::regclass
FROM pg_constraint
WHERE conrelid = 'scoped_permissions'::regclass AND contype = 'f';
"
# Expected: FK from scoped_permissions.task_id → tasks.id
```

### Manual Verification

```bash
cd /Users/imaxxs/repositories/mvp-prod-control/deeptrail-control

# 1. Verify model imports
python -c "
from app.models.task_token import Task, ScopedPermission, TaskStatus
from app.models.task_token import generate_task_id, generate_scoped_permission_id
print(f'Task ID: {generate_task_id()}')
print(f'SP ID: {generate_scoped_permission_id()}')
print(f'Terminal states: {TaskStatus.TERMINAL}')
print('OK')
"
# Expected: task-<uuid>, sp-<uuid>, set of terminal states

# 2. Verify schema validation
python -c "
from app.models.task_token import TaskCreate, ScopedPermissionRequest
t = TaskCreate(
    name='Research lead 12345',
    requested_permissions=[
        ScopedPermissionRequest(
            permission_urn='hubspot:contacts:read',
            constraints={'id': '12345'},
            max_usage=10,
        )
    ],
    deadline_minutes=60,
    auto_revoke_on_complete=True,
)
print(f'Task: {t.name}')
print(f'Permissions: {len(t.requested_permissions)}')
print(f'Deadline: {t.deadline_minutes} min')
print('OK')
"
# Expected: Task name, 1 permission, 60 min deadline

# 3. Verify empty permissions rejected
python -c "
from app.models.task_token import TaskCreate
try:
    TaskCreate(name='bad', requested_permissions=[])
    print('FAIL: should have raised')
except Exception as e:
    print(f'OK: {type(e).__name__}')
"
# Expected: OK: ValidationError

# 4. Verify lifecycle methods
python -c "
from app.models.task_token import Task, ScopedPermission, TaskStatus
from datetime import datetime, timedelta, timezone

task = Task(
    agent_id='agent-001',
    initiated_by='user@test.com',
    scoped_permissions=[{'urn': 'test:perm'}],
)
print(f'Created: status={task.status}')

task.activate()
print(f'Activated: status={task.status}, started_at={task.started_at is not None}')

sp = ScopedPermission(
    task_id='task-001',
    permission_urn='test:perm',
    valid_until=datetime.now(timezone.utc) + timedelta(hours=1),
)
task.scoped_permission_records = [sp]
task.complete()
print(f'Completed: status={task.status}, perm_revoked={sp.revoked}')
print('OK')
"
# Expected: pending → active → completed, permission revoked

# 5. Verify to_token_claims
python -c "
from app.models.task_token import Task
task = Task(
    id='task-test-123',
    agent_id='agent-sdr-001',
    initiated_by='sarah@acme.com',
    scoped_permissions=[
        {'urn': 'hubspot:contacts:read', 'constraints': {'id': '12345'}}
    ],
    auto_revoke_on_complete=True,
)
claims = task.to_token_claims()
print(f'Claims: task_id={claims[\"task_id\"]}, agent_id={claims[\"agent_id\"]}')
print(f'Permissions: {len(claims[\"scoped_permissions\"])}')
print(f'Auto-revoke: {claims[\"auto_revoke_on_complete\"]}')
print('OK')
"
# Expected: Correct Layer 4 claims
```

---

## References

- **Spec:** [WS-K6-spec.md](../specs/WS-K6-spec.md) — full model definition, migration SQL, test code
- **Architecture:** `deepsecure-comprehensive-architecture-consolidated.md`
  - Section 7: Complete Six-Layer Token Hierarchy (Layer 4: Task Token)
  - Section 9: Per-Task Permission Architecture
  - Section 14.2: Task Management Service
- **Token Claims:** `task_id`, `agent_id`, `scoped_permissions`, `deadline`, `auto_revoke_on_complete`, `iat`
- **Model Pattern:** `deeptrail-control/app/models/delegation.py` (same ORM style, JSONB, hybrid properties, ID generation)
- **Sibling Models:** `deeptrail-control/app/models/agent_session.py`, `deeptrail-control/app/models/vault_token.py`
- **DB Base:** `deeptrail-control/app/db/base.py` — `Base` declarative base
- **Upstream Dependencies:** MP3.5 (✅ reached Feb 23, 2026)
- **Downstream Dependents:** WS-K7 (TaskService), WS-K8 (Task API endpoints)

---

## Execution

```bash
# Run in mvp-prod-control worktree:
cd /Users/imaxxs/repositories/mvp-prod-control

# Execute the task
/execute-task WS-K6 mvp-production-readiness

# After completion
/complete-task WS-K6 mvp-production-readiness
```
