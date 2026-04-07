# Task Specification: WS-K7 Create TaskService

> **IMMUTABLE AFTER DESIGN APPROVAL**
>
> This specification defines what implementation MUST match exactly.
> Do not modify without updating the design doc first.
>
> **Source:** `deepsecure-comprehensive-architecture-consolidated.md` Section 14.2 (Task Management Service),
> `WS-K6-spec.md` (Task + ScopedPermission models, Pydantic schemas)
>
> **Token Hierarchy:** TaskService manages Layer 4 (Task Token) lifecycle and JWT issuance

---

## Overview

| Field | Value |
|-------|-------|
| **Task ID** | WS-K7 |
| **Task Name** | Create TaskService |
| **Type** | Service (Business Logic) |
| **Service** | deeptrail-control |
| **Complexity** | M (1-3 hours) |
| **Dependencies** | WS-K6 (Task + ScopedPermission models) |
| **Validates** | Task lifecycle, permission scoping, Task Token JWT issuance |
| **Unblocks** | WS-K8 (Task API endpoints) |

---

## Problem Statement

### Current State

The Task and ScopedPermission models exist (WS-K6) but there is no business logic layer to:
1. Create tasks with permission validation (subset check against delegation)
2. Manage task lifecycle (activate, complete, revoke, timeout)
3. Issue Task Token JWTs (Layer 4 of token hierarchy)
4. Enforce deadline timeouts

### Target State

A `TaskService` provides all CRUD and lifecycle operations for tasks, including permission validation and JWT token issuance.

---

## Component Specification

### Class: `TaskService`

| Field | Value |
|-------|-------|
| **Module** | `deeptrail_control.app.services.task_service` |
| **File** | `deeptrail-control/app/services/task_service.py` |
| **Type** | Class |
| **Pattern** | Constructor takes `db: Session`, methods are synchronous (matching existing service pattern) |

### Constructor

```python
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.task_token import (
    Task,
    ScopedPermission,
    TaskStatus,
    generate_task_id,
    generate_scoped_permission_id,
    TaskCreate,
    TaskResponse,
    TaskTokenResponse,
)

logger = logging.getLogger(__name__)


class TaskServiceError(Exception):
    """Base error for TaskService operations."""
    pass


class TaskNotFoundError(TaskServiceError):
    """Task does not exist."""
    pass


class TaskPermissionError(TaskServiceError):
    """Requested permissions exceed delegation scope."""
    def __init__(self, message: str, invalid_permissions: List[str], allowed_permissions: List[str]):
        super().__init__(message)
        self.invalid_permissions = invalid_permissions
        self.allowed_permissions = allowed_permissions


class TaskLifecycleError(TaskServiceError):
    """Invalid task state transition."""
    pass


class TaskService:
    """Business logic for Task lifecycle and Task Token issuance.

    Manages Layer 4 (Task Token) of the DeepSecure token hierarchy.
    Enforces permission scoping: task permissions ⊆ delegation permissions.
    """

    JWT_ALGORITHM = "HS256"

    def __init__(self, db: Session, jwt_secret: str):
        self._db = db
        self._jwt_secret = jwt_secret
```

### Public Methods

| Method | Arguments | Returns | Description |
|--------|-----------|---------|-------------|
| `create_task` | `agent_id`, `initiated_by`, `task_data: TaskCreate`, `delegation_id` (opt), `delegation_permissions` (opt) | `Task` | Create task with permission validation |
| `get_task` | `task_id`, `agent_id` (opt) | `Task` | Fetch task by ID, optional ownership check |
| `list_tasks` | `agent_id`, `status` (opt), `limit`, `offset` | `List[Task]` | List tasks for an agent |
| `activate_task` | `task_id`, `agent_id` (opt) | `Task` | Transition pending → active |
| `complete_task` | `task_id`, `agent_id` (opt) | `Task` | Transition active → completed |
| `revoke_task` | `task_id`, `agent_id` (opt) | `Task` | Force-revoke a task |
| `issue_task_token` | `task_id`, `agent_id` (opt) | `TaskTokenResponse` | Issue JWT for an active task |
| `check_deadline_timeouts` | — | `int` | Timeout all past-deadline tasks, return count |

### Method Contracts

```python
def create_task(
    self,
    agent_id: str,
    initiated_by: str,
    task_data: TaskCreate,
    delegation_id: Optional[str] = None,
    delegation_permissions: Optional[List[str]] = None,
) -> Task:
    """Create a new task with scoped permissions.

    Steps:
        1. Validate requested permissions ⊆ delegation_permissions (if provided)
        2. Create Task record with status=PENDING
        3. Create ScopedPermission records for each requested permission
        4. Commit and return the task

    Args:
        agent_id: Agent that will own this task.
        initiated_by: User who initiated/approved the task.
        task_data: TaskCreate schema with name, permissions, deadline, etc.
        delegation_id: Optional delegation under which this task is created.
        delegation_permissions: List of permission URNs the delegation grants.
            If provided, requested permissions are validated as a subset.

    Returns:
        The created Task with scoped_permission_records populated.

    Raises:
        TaskPermissionError: If requested permissions exceed delegation scope.
    """
    ...


def get_task(self, task_id: str, agent_id: Optional[str] = None) -> Task:
    """Fetch a task by ID.

    Args:
        task_id: The task ID to look up.
        agent_id: If provided, verifies the task belongs to this agent.

    Returns:
        The Task object with scoped_permission_records loaded.

    Raises:
        TaskNotFoundError: If task doesn't exist or agent_id doesn't match.
    """
    ...


def list_tasks(
    self,
    agent_id: str,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> List[Task]:
    """List tasks for an agent, optionally filtered by status.

    Returns:
        List of Task objects, ordered by created_at descending.
    """
    ...


def activate_task(self, task_id: str, agent_id: Optional[str] = None) -> Task:
    """Activate a pending task.

    Raises:
        TaskNotFoundError: If task doesn't exist.
        TaskLifecycleError: If task is not in PENDING status.
    """
    ...


def complete_task(self, task_id: str, agent_id: Optional[str] = None) -> Task:
    """Complete an active task. Auto-revokes permissions if configured.

    Raises:
        TaskNotFoundError: If task doesn't exist.
        TaskLifecycleError: If task is not in ACTIVE status.
    """
    ...


def revoke_task(self, task_id: str, agent_id: Optional[str] = None) -> Task:
    """Force-revoke a task (admin or user action).

    Raises:
        TaskNotFoundError: If task doesn't exist.
        TaskLifecycleError: If task is already in a terminal state.
    """
    ...


def issue_task_token(
    self,
    task_id: str,
    agent_id: Optional[str] = None,
) -> TaskTokenResponse:
    """Issue a JWT Task Token (Layer 4) for an active task.

    The token contains scoped permissions and expires at the task deadline
    or a default TTL (1 hour), whichever is sooner.

    Args:
        task_id: Task to issue a token for.
        agent_id: Optional ownership verification.

    Returns:
        TaskTokenResponse with task_token JWT, expires_at, and permission URNs.

    Raises:
        TaskNotFoundError: If task doesn't exist.
        TaskLifecycleError: If task is not ACTIVE.
    """
    ...


def check_deadline_timeouts(self) -> int:
    """Find all non-terminal tasks past their deadline and timeout them.

    Returns:
        Number of tasks timed out.
    """
    ...
```

### JWT Token Format (Layer 4)

Task Token JWTs are signed with the same secret as Agent Session JWTs (`settings.SECRET_KEY`, HS256).

```python
import jwt

def issue_task_token(self, task_id: str, agent_id: Optional[str] = None) -> TaskTokenResponse:
    task = self.get_task(task_id, agent_id)
    if task.status != TaskStatus.ACTIVE:
        raise TaskLifecycleError(f"Cannot issue token for task in '{task.status}' status")

    claims = task.to_token_claims()

    # Compute expiry: min(deadline, now + 1 hour)
    now = datetime.now(timezone.utc)
    default_exp = now + timedelta(hours=1)
    if task.deadline:
        deadline = task.deadline if task.deadline.tzinfo else task.deadline.replace(tzinfo=timezone.utc)
        expires_at = min(deadline, default_exp)
    else:
        expires_at = default_exp

    claims["exp"] = int(expires_at.timestamp())
    claims["iss"] = "deepsecure-control"
    claims["aud"] = "deepsecure-gateway"
    claims["token_type"] = "task_token"

    token = jwt.encode(claims, self._jwt_secret, algorithm=self.JWT_ALGORITHM)

    return TaskTokenResponse(
        task_id=task.id,
        task_token=token,
        expires_at=expires_at,
        scoped_permissions=task.get_active_permission_urns(),
    )
```

### Permission Validation

```python
def _validate_permissions_subset(
    self,
    requested: List[str],
    allowed: List[str],
) -> None:
    """Ensure requested permission URNs are a subset of allowed."""
    requested_set = set(requested)
    allowed_set = set(allowed)
    invalid = requested_set - allowed_set
    if invalid:
        raise TaskPermissionError(
            f"Requested permissions exceed delegation scope: {invalid}",
            invalid_permissions=sorted(invalid),
            allowed_permissions=sorted(allowed_set),
        )
```

### Create Task Implementation

```python
def create_task(
    self,
    agent_id: str,
    initiated_by: str,
    task_data: TaskCreate,
    delegation_id: Optional[str] = None,
    delegation_permissions: Optional[List[str]] = None,
) -> Task:
    requested_urns = [p.permission_urn for p in task_data.requested_permissions]

    if delegation_permissions is not None:
        self._validate_permissions_subset(requested_urns, delegation_permissions)

    now = datetime.now(timezone.utc)
    deadline = None
    if task_data.deadline_minutes:
        deadline = now + timedelta(minutes=task_data.deadline_minutes)

    task = Task(
        id=generate_task_id(),
        agent_id=agent_id,
        initiated_by=initiated_by,
        delegation_id=delegation_id,
        name=task_data.name,
        description=task_data.description,
        scoped_permissions=[
            {"urn": p.permission_urn, "constraints": p.constraints}
            for p in task_data.requested_permissions
        ],
        deadline=deadline,
        auto_revoke_on_complete=task_data.auto_revoke_on_complete,
    )

    # Create ScopedPermission records
    perm_valid_until = deadline or (now + timedelta(hours=24))
    for p in task_data.requested_permissions:
        sp = ScopedPermission(
            id=generate_scoped_permission_id(),
            task_id=task.id,
            permission_urn=p.permission_urn,
            constraints=p.constraints,
            valid_until=perm_valid_until,
            max_usage=p.max_usage,
        )
        task.scoped_permission_records.append(sp)

    self._db.add(task)
    self._db.commit()
    self._db.refresh(task)

    logger.info(
        "Task created",
        extra={
            "task_id": task.id,
            "agent_id": agent_id,
            "permissions": len(requested_urns),
            "deadline": deadline.isoformat() if deadline else None,
        },
    )
    return task
```

---

## API Contracts

> **Note:** This task creates the service layer, not API endpoints.
> API endpoints are implemented in WS-K8.
> The service provides the business logic that endpoints delegate to.

---

## File Location Rules

| Artifact | Correct Location |
|----------|------------------|
| TaskService | `deeptrail-control/app/services/task_service.py` |
| Unit tests | `deeptrail-control/tests/services/test_task_service.py` |

---

## Technical Requirements

### Framework-Specific

| Requirement | Pattern | Why |
|-------------|---------|-----|
| Synchronous methods | `def method(self)` | Matches existing service pattern (DelegationService, AgentSessionService) |
| Constructor | `def __init__(self, db: Session, jwt_secret: str)` | SQLAlchemy Session injection |
| Error hierarchy | `TaskServiceError` base, specific subclasses | Domain errors, not HTTP errors |
| Permission validation | Subset check (set operations) | Monotonic attenuation: task ⊆ delegation |
| JWT signing | `jwt.encode(..., HS256)` | Matches agent session JWT pattern |

### Dependencies

| Dependency | Version | Purpose |
|------------|---------|---------|
| `sqlalchemy` | existing | DB access |
| `pyjwt` | existing | Task Token JWT signing |
| K6 models | WS-K6 | `Task`, `ScopedPermission`, `TaskStatus`, schemas |

### Existing Code Relationship

| Existing Module | Relationship | Notes |
|-----------------|-------------|-------|
| `delegation_service.py` | Pattern reference | Permission validation, subset checks, error handling |
| `agent_session_service.py` | Pattern reference | JWT issuance (`_generate_jwt` pattern) |
| `task_token.py` (K6) | Direct dependency | Models, schemas, `to_token_claims()` |

---

## Test Cases

### Unit Tests

| Test Case | Method | Expected | Notes |
|-----------|--------|----------|-------|
| Create task with valid permissions | `create_task()` | Task created, status=PENDING | Happy path |
| Create task permission subset check | `create_task()` | `TaskPermissionError` | Requested > delegation |
| Create task no delegation check | `create_task()` | Task created | `delegation_permissions=None` skips check |
| Create task with deadline | `create_task()` | `deadline` set correctly | Minutes → datetime |
| Create task generates ScopedPermission records | `create_task()` | N records match N requested | Relationship populated |
| Get task by ID | `get_task()` | Returns task | Happy path |
| Get task not found | `get_task()` | `TaskNotFoundError` | Invalid ID |
| Get task wrong agent | `get_task()` | `TaskNotFoundError` | Ownership check |
| List tasks by agent | `list_tasks()` | Filtered list | Ordered by created_at desc |
| List tasks by status | `list_tasks()` | Filtered by status | Status filter |
| Activate task | `activate_task()` | status=ACTIVE, started_at set | pending → active |
| Activate non-pending | `activate_task()` | `TaskLifecycleError` | Invalid transition |
| Complete task | `complete_task()` | status=COMPLETED, perms revoked | active → completed |
| Complete non-active | `complete_task()` | `TaskLifecycleError` | Invalid transition |
| Revoke task | `revoke_task()` | status=REVOKED, perms revoked | Force revoke |
| Revoke terminal | `revoke_task()` | `TaskLifecycleError` | Already terminal |
| Issue task token | `issue_task_token()` | Valid JWT, correct claims | Active task |
| Issue token non-active | `issue_task_token()` | `TaskLifecycleError` | Not active |
| Issue token respects deadline | `issue_task_token()` | `exp` = min(deadline, now+1h) | Deadline sooner |
| Issue token default TTL | `issue_task_token()` | `exp` = now+1h | No deadline |
| Token claims match model | `issue_task_token()` | `task_id`, `agent_id`, `scoped_permissions` | JWT decode check |
| Token has correct `iss` and `aud` | `issue_task_token()` | `iss=deepsecure-control`, `aud=deepsecure-gateway` | Standard claims |
| Check deadline timeouts | `check_deadline_timeouts()` | Past-deadline tasks timed out | Count returned |
| Timeout skips terminal tasks | `check_deadline_timeouts()` | Already-terminal unchanged | Idempotent |

### Test Code Example

```python
import pytest
import jwt
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from app.services.task_service import (
    TaskService,
    TaskNotFoundError,
    TaskPermissionError,
    TaskLifecycleError,
)
from app.models.task_token import (
    Task,
    ScopedPermission,
    TaskStatus,
    TaskCreate,
    ScopedPermissionRequest,
)


class TestTaskServiceCreate:
    def setup_method(self):
        self.db = MagicMock()
        self.service = TaskService(db=self.db, jwt_secret="test-secret")

    def test_create_task_happy_path(self):
        task_data = TaskCreate(
            name="Research lead",
            requested_permissions=[
                ScopedPermissionRequest(
                    permission_urn="hubspot:contacts:read",
                    constraints={"id": "12345"},
                )
            ],
            deadline_minutes=60,
        )
        task = self.service.create_task(
            agent_id="agent-sdr-001",
            initiated_by="sarah@acme.com",
            task_data=task_data,
            delegation_permissions=["hubspot:contacts:read", "hubspot:contacts:write"],
        )
        assert task.status == TaskStatus.PENDING
        assert task.agent_id == "agent-sdr-001"
        assert len(task.scoped_permission_records) == 1

    def test_create_task_permission_exceeded(self):
        task_data = TaskCreate(
            requested_permissions=[
                ScopedPermissionRequest(permission_urn="slack:messages:send"),
            ],
        )
        with pytest.raises(TaskPermissionError) as exc_info:
            self.service.create_task(
                agent_id="agent-001",
                initiated_by="user@test.com",
                task_data=task_data,
                delegation_permissions=["hubspot:contacts:read"],
            )
        assert "slack:messages:send" in exc_info.value.invalid_permissions


class TestTaskServiceToken:
    def test_issue_task_token(self):
        db = MagicMock()
        service = TaskService(db=db, jwt_secret="test-secret")

        task = Task(
            id="task-test-123",
            agent_id="agent-001",
            initiated_by="user@test.com",
            status=TaskStatus.ACTIVE,
            scoped_permissions=[{"urn": "hubspot:contacts:read"}],
            auto_revoke_on_complete=True,
        )
        sp = ScopedPermission(
            task_id="task-test-123",
            permission_urn="hubspot:contacts:read",
            valid_until=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        task.scoped_permission_records = [sp]

        db.query.return_value.filter.return_value.first.return_value = task

        result = service.issue_task_token("task-test-123")
        assert result.task_id == "task-test-123"
        assert result.task_token is not None

        decoded = jwt.decode(result.task_token, "test-secret", algorithms=["HS256"], audience="deepsecure-gateway")
        assert decoded["task_id"] == "task-test-123"
        assert decoded["agent_id"] == "agent-001"
        assert decoded["token_type"] == "task_token"
        assert decoded["iss"] == "deepsecure-control"
```

---

## Contract Verification Checklist

- [ ] `TaskService` class in `deeptrail-control/app/services/task_service.py`
- [ ] Constructor: `__init__(self, db: Session, jwt_secret: str)`
- [ ] `create_task()` validates permissions ⊆ delegation (when delegation_permissions provided)
- [ ] `create_task()` persists Task + ScopedPermission records
- [ ] `get_task()` with optional agent_id ownership check
- [ ] `list_tasks()` with status filter, pagination (limit/offset)
- [ ] `activate_task()` transitions pending → active with guards
- [ ] `complete_task()` transitions active → completed, auto-revokes permissions
- [ ] `revoke_task()` force-revokes non-terminal tasks
- [ ] `issue_task_token()` returns JWT with `task_id`, `agent_id`, `scoped_permissions`, `exp`, `iss`, `aud`, `token_type`
- [ ] Token `exp` = min(deadline, now+1h)
- [ ] `check_deadline_timeouts()` finds and timeouts past-deadline tasks
- [ ] Error hierarchy: `TaskServiceError`, `TaskNotFoundError`, `TaskPermissionError`, `TaskLifecycleError`
- [ ] `TaskPermissionError` includes `invalid_permissions` and `allowed_permissions`
- [ ] All operations are logged with structured data (task_id, agent_id, action)
- [ ] All unit tests pass

---

## Security Considerations

| Aspect | Status | Notes |
|--------|--------|-------|
| Permission attenuation | Enforced | task_permissions ⊆ delegation_permissions (monotonic) |
| JWT signing | Same key as agent JWTs | HS256 with `settings.SECRET_KEY` |
| Token expiry | Bounded | min(deadline, 1 hour) — never longer than deadline |
| Lifecycle guards | Enforced | ValueError on invalid transitions (from K6 model) |
| Audit trail | Built-in | `initiated_by`, `created_at`, `completed_at`, logging |
| Ownership checks | Optional | `agent_id` param for multi-tenant safety |

---

## References

- **K6 Spec:** [WS-K6-spec.md](./WS-K6-spec.md) — Task + ScopedPermission models, Pydantic schemas, `to_token_claims()`
- **Architecture:** `deepsecure-comprehensive-architecture-consolidated.md` Section 14.2 (Task Management Service), Section 9 (Per-Task Permission Architecture)
- **Pattern Reference:** `deeptrail-control/app/services/delegation_service.py` — permission validation, error handling
- **JWT Pattern:** `deeptrail-control/app/services/agent_session_service.py` — `_generate_jwt`, HS256 signing
- **Upstream Dependencies:** WS-K6 (Task model)
- **Downstream Dependents:** WS-K8 (Task API endpoints)
