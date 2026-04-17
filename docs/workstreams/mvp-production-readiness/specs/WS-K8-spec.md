# Task Specification: WS-K8 Create Task Endpoints

> **IMMUTABLE AFTER DESIGN APPROVAL**
>
> This specification defines what implementation MUST match exactly.
> Do not modify without updating the design doc first.
>
> **Source:** `deepsecure-comprehensive-architecture-consolidated.md` Section 14.2 (Task Management Service),
> `WS-K6-spec.md` (Pydantic schemas: TaskCreate, TaskResponse, TaskTokenResponse),
> `WS-K7-spec.md` (TaskService business logic)

---

## Overview

| Field | Value |
|-------|-------|
| **Task ID** | WS-K8 |
| **Task Name** | Create Task Endpoints |
| **Type** | API Endpoints |
| **Service** | deeptrail-control |
| **Complexity** | M (1-3 hours) |
| **Dependencies** | WS-K7 (TaskService) |
| **Validates** | Task CRUD via HTTP, Task Token issuance endpoint |
| **Unblocks** | P2 validation (task token generation, scoped calls) |

---

## Problem Statement

### Current State

TaskService (K7) provides business logic for task lifecycle and token issuance, but there are no HTTP endpoints exposing this functionality. The P2 validation criteria require testing task token generation and scoped calls via HTTP.

### Target State

RESTful API endpoints for task management, mounted under `/api/v1/tasks`.

---

## API Contracts

### Endpoint: Create Task

| Field | Value |
|-------|-------|
| **Method** | `POST` |
| **Path** | `/api/v1/tasks` |
| **Auth** | Bearer token (Agent JWT or User JWT) |
| **Purpose** | Create a new task with scoped permissions |

**Request Body:**

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

**Schema:** `TaskCreate` (from K6)

**Response (201):**

```json
{
  "task_id": "task-550e8400-e29b-41d4-a716-446655440000",
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

**Schema:** `TaskResponse` (from K6)

**Error Responses:**

| Status | Condition | Response |
|--------|-----------|----------|
| 400 | Empty `requested_permissions` | `{"detail": "At least 1 permission required"}` |
| 400 | `deadline_minutes` out of range | `{"detail": "Deadline must be 1-1440 minutes"}` |
| 403 | Requested permissions exceed delegation | `{"detail": "Permissions exceed delegation scope", "invalid_permissions": [...], "allowed_permissions": [...]}` |
| 401 | Missing or invalid token | `{"detail": "Not authenticated"}` |

---

### Endpoint: Get Task

| Field | Value |
|-------|-------|
| **Method** | `GET` |
| **Path** | `/api/v1/tasks/{task_id}` |
| **Auth** | Bearer token (Agent JWT or User JWT) |
| **Purpose** | Retrieve task details |

**Response (200):** `TaskResponse`

**Error Responses:**

| Status | Condition | Response |
|--------|-----------|----------|
| 404 | Task not found | `{"detail": "Task not found: {task_id}"}` |
| 401 | Missing or invalid token | `{"detail": "Not authenticated"}` |

---

### Endpoint: List Tasks

| Field | Value |
|-------|-------|
| **Method** | `GET` |
| **Path** | `/api/v1/tasks` |
| **Auth** | Bearer token (Agent JWT or User JWT) |
| **Purpose** | List tasks for the authenticated agent/user |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `status` | `str` | No | — | Filter by status (pending, active, completed, revoked, timed_out) |
| `limit` | `int` | No | 50 | Max results (1-100) |
| `offset` | `int` | No | 0 | Pagination offset |

**Response (200):**

```json
{
  "tasks": [ /* TaskResponse objects */ ],
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

**Response (200):** `TaskResponse` (with `status: "active"`, `started_at` set)

**Error Responses:**

| Status | Condition | Response |
|--------|-----------|----------|
| 404 | Task not found | `{"detail": "Task not found: {task_id}"}` |
| 409 | Invalid state transition | `{"detail": "Cannot activate task in '{status}' status"}` |

---

### Endpoint: Complete Task

| Field | Value |
|-------|-------|
| **Method** | `POST` |
| **Path** | `/api/v1/tasks/{task_id}/complete` |
| **Auth** | Bearer token |
| **Purpose** | Complete a task (auto-revokes permissions if configured) |

**Response (200):** `TaskResponse` (with `status: "completed"`, `completed_at` set)

**Error Responses:**

| Status | Condition | Response |
|--------|-----------|----------|
| 404 | Task not found | `{"detail": "Task not found: {task_id}"}` |
| 409 | Invalid state transition | `{"detail": "Cannot complete task in '{status}' status"}` |

---

### Endpoint: Revoke Task

| Field | Value |
|-------|-------|
| **Method** | `POST` |
| **Path** | `/api/v1/tasks/{task_id}/revoke` |
| **Auth** | Bearer token |
| **Purpose** | Force-revoke a task and all its permissions |

**Response (200):** `TaskResponse` (with `status: "revoked"`)

**Error Responses:**

| Status | Condition | Response |
|--------|-----------|----------|
| 404 | Task not found | `{"detail": "Task not found: {task_id}"}` |
| 409 | Already in terminal state | `{"detail": "Cannot revoke task in '{status}' status"}` |

---

### Endpoint: Issue Task Token

| Field | Value |
|-------|-------|
| **Method** | `POST` |
| **Path** | `/api/v1/tasks/{task_id}/token` |
| **Auth** | Bearer token |
| **Purpose** | Issue a JWT Task Token for an active task |

**Response (200):**

```json
{
  "task_id": "task-550e8400-e29b-41d4-a716-446655440000",
  "task_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "expires_at": "2026-04-07T15:00:00+00:00",
  "scoped_permissions": ["hubspot:contacts:read"]
}
```

**Schema:** `TaskTokenResponse` (from K6)

**Error Responses:**

| Status | Condition | Response |
|--------|-----------|----------|
| 404 | Task not found | `{"detail": "Task not found: {task_id}"}` |
| 409 | Task not active | `{"detail": "Cannot issue token for task in '{status}' status"}` |

---

## Component Specification

### Router Structure

```python
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.config import settings
from app.api import deps
from app.models.task_token import TaskCreate, TaskResponse, TaskTokenResponse
from app.services.task_service import (
    TaskService,
    TaskNotFoundError,
    TaskPermissionError,
    TaskLifecycleError,
)

router = APIRouter()


@router.post("/", response_model=TaskResponse, status_code=201)
def create_task(
    task_data: TaskCreate,
    db: Session = Depends(deps.get_db),
    # current_user or agent identity from JWT
):
    """Create a new task with scoped permissions."""
    service = TaskService(db=db, jwt_secret=settings.SECRET_KEY)
    try:
        task = service.create_task(
            agent_id=current_identity.agent_id,
            initiated_by=current_identity.user_id,
            task_data=task_data,
            delegation_id=current_identity.delegation_id,
            delegation_permissions=current_identity.delegated_permissions,
        )
        return task
    except TaskPermissionError as e:
        raise HTTPException(
            status_code=403,
            detail={
                "message": str(e),
                "invalid_permissions": e.invalid_permissions,
                "allowed_permissions": e.allowed_permissions,
            },
        )


@router.get("/{task_id}", response_model=TaskResponse)
def get_task(
    task_id: str,
    db: Session = Depends(deps.get_db),
):
    """Get task details."""
    service = TaskService(db=db, jwt_secret=settings.SECRET_KEY)
    try:
        return service.get_task(task_id)
    except TaskNotFoundError:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")


@router.post("/{task_id}/activate", response_model=TaskResponse)
def activate_task(task_id: str, db: Session = Depends(deps.get_db)):
    """Activate a pending task."""
    service = TaskService(db=db, jwt_secret=settings.SECRET_KEY)
    try:
        return service.activate_task(task_id)
    except TaskNotFoundError:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")
    except TaskLifecycleError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/{task_id}/complete", response_model=TaskResponse)
def complete_task(task_id: str, db: Session = Depends(deps.get_db)):
    """Complete an active task."""
    service = TaskService(db=db, jwt_secret=settings.SECRET_KEY)
    try:
        return service.complete_task(task_id)
    except TaskNotFoundError:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")
    except TaskLifecycleError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/{task_id}/revoke", response_model=TaskResponse)
def revoke_task(task_id: str, db: Session = Depends(deps.get_db)):
    """Revoke a task."""
    service = TaskService(db=db, jwt_secret=settings.SECRET_KEY)
    try:
        return service.revoke_task(task_id)
    except TaskNotFoundError:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")
    except TaskLifecycleError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/{task_id}/token", response_model=TaskTokenResponse)
def issue_task_token(task_id: str, db: Session = Depends(deps.get_db)):
    """Issue a JWT Task Token for an active task."""
    service = TaskService(db=db, jwt_secret=settings.SECRET_KEY)
    try:
        return service.issue_task_token(task_id)
    except TaskNotFoundError:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")
    except TaskLifecycleError as e:
        raise HTTPException(status_code=409, detail=str(e))
```

### Router Wiring

Add to `deeptrail-control/app/api/v1/api.py`:

```python
from app.api.v1.endpoints import tasks
api_router.include_router(tasks.router, prefix="/tasks", tags=["tasks"])
```

---

## File Location Rules

| Artifact | Correct Location |
|----------|------------------|
| Task endpoints | `deeptrail-control/app/api/v1/endpoints/tasks.py` |
| List response schema | `deeptrail-control/app/schemas/task.py` (optional — `TaskListResponse`) |
| Router wiring | `deeptrail-control/app/api/v1/api.py` (modify) |
| Unit tests | `deeptrail-control/tests/api/test_tasks.py` |

---

## Technical Requirements

### Framework-Specific

| Requirement | Pattern | Why |
|-------------|---------|-----|
| Sync endpoints | `def endpoint()` | TaskService is synchronous |
| Dependency injection | `Depends(deps.get_db)` | Standard project pattern |
| Error mapping | Service errors → HTTPException | Clean separation |
| Status codes | 201 for create, 200 for others, 409 for lifecycle errors | RESTful conventions |

### Dependencies

| Dependency | Version | Purpose |
|------------|---------|---------|
| `fastapi` | existing | API framework |
| K6 schemas | WS-K6 | `TaskCreate`, `TaskResponse`, `TaskTokenResponse` |
| K7 service | WS-K7 | `TaskService`, error classes |

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
| Activate task | POST | `/api/v1/tasks/{id}/activate` | 200 | status → active |
| Activate non-pending | POST | `/api/v1/tasks/{id}/activate` | 409 | Lifecycle error |
| Complete task | POST | `/api/v1/tasks/{id}/complete` | 200 | status → completed |
| Complete non-active | POST | `/api/v1/tasks/{id}/complete` | 409 | Lifecycle error |
| Revoke task | POST | `/api/v1/tasks/{id}/revoke` | 200 | status → revoked |
| Revoke terminal | POST | `/api/v1/tasks/{id}/revoke` | 409 | Already terminal |
| Issue task token | POST | `/api/v1/tasks/{id}/token` | 200 | Returns TaskTokenResponse |
| Issue token non-active | POST | `/api/v1/tasks/{id}/token` | 409 | Task not active |
| Unauthorized | POST | `/api/v1/tasks` | 401 | Missing token |

---

## Contract Verification Checklist

- [ ] Router mounted at `/tasks` prefix in `api.py`
- [ ] `POST /` creates task, returns 201
- [ ] `GET /{task_id}` returns task or 404
- [ ] `GET /` lists tasks with optional `status`, `limit`, `offset`
- [ ] `POST /{task_id}/activate` transitions pending → active or 409
- [ ] `POST /{task_id}/complete` transitions active → completed or 409
- [ ] `POST /{task_id}/revoke` revokes non-terminal or 409
- [ ] `POST /{task_id}/token` issues JWT or 409 if not active
- [ ] `TaskPermissionError` → 403 with `invalid_permissions` detail
- [ ] `TaskNotFoundError` → 404
- [ ] `TaskLifecycleError` → 409
- [ ] All endpoints require Bearer auth
- [ ] All unit tests pass

---

## References

- **K6 Spec:** [WS-K6-spec.md](./WS-K6-spec.md) — Pydantic schemas (TaskCreate, TaskResponse, TaskTokenResponse)
- **K7 Spec:** [WS-K7-spec.md](./WS-K7-spec.md) — TaskService business logic and error classes
- **Architecture:** `deepsecure-comprehensive-architecture-consolidated.md` Section 14.2
- **Endpoint Pattern:** `deeptrail-control/app/api/v1/endpoints/agents.py` — router, deps, HTTPException
- **Router Wiring:** `deeptrail-control/app/api/v1/api.py`
- **Upstream Dependencies:** WS-K7 (TaskService)
- **Downstream Dependents:** P2 validation (task token generation + scoped calls)
