# Task Specification: WS-K6 Create TaskToken Model

> **IMMUTABLE AFTER DESIGN APPROVAL**
>
> This specification defines what implementation MUST match exactly.
> Do not modify without updating the design doc first.
>
> **Source:** `deepsecure-comprehensive-architecture-consolidated.md` Sections 7, 9, 14.2
> (Layer 4: Task Token, Per-Task Permission Architecture, Task Management Service)
>
> **Token Hierarchy:** Layer 4 of the 6-layer token hierarchy — unique to DeepSecure (not in research paper)

---

## Overview

| Field | Value |
|-------|-------|
| **Task ID** | WS-K6 |
| **Task Name** | Create TaskToken Model |
| **Type** | Data Model (SQLAlchemy) + Alembic Migration |
| **Service** | deeptrail-control |
| **Complexity** | M (1-3 hours) |
| **Dependencies** | MP3.5 (P1.5 complete) |
| **Validates** | Token Layer 4 (per-task scoped permissions), task lifecycle |
| **Unblocks** | WS-K7 (TaskService), WS-K8 (Task API endpoints) |

---

## Problem Statement

### Current State

The Control Plane has no concept of "tasks" — agents operate with session-level permissions (Layer 3: Agent Session JWT). There is no way to:
1. Scope permissions down to a specific task
2. Automatically revoke permissions when a task completes
3. Track per-task usage and audit trails
4. Enforce task deadlines

```
Agent Session JWT (Layer 3)
├── delegated_permissions: ["notion:pages:search", "hubspot:contacts:read", ...]
├── Lifetime: hours-days
└── All permissions available for ALL work ← No task-level scoping
```

### Target State

Tasks become first-class entities with scoped permissions (Layer 4: Task Token). Each task has exactly the permissions needed for that specific work unit.

```
Agent Session JWT (Layer 3)
└── Task Token (Layer 4)  ← NEW
    ├── task_id: "task-outreach-lead-12345"
    ├── scoped_permissions: [
    │     { urn: "hubspot:contacts:read", constraints: { id: "12345" } }
    │   ]
    ├── deadline: "2026-01-15T12:00:00Z"
    └── auto_revoke_on_complete: true
```

---

## Data Model Specification

### Table: `tasks`

| Column | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | `String(64)` | Yes | `task-<uuid>` | Primary key, unique task identifier |
| `agent_id` | `String(64)` | Yes | — | Agent that owns this task (FK intent, not enforced) |
| `delegation_id` | `String(64)` | No | — | Delegation under which the task was created |
| `initiated_by` | `String(255)` | Yes | — | User who initiated/approved the task (audit trail) |
| `name` | `String(255)` | No | — | Human-readable task name |
| `description` | `Text` | No | — | Task description |
| `status` | `String(50)` | Yes | `"pending"` | Task lifecycle status |
| `scoped_permissions` | `JSONB` | Yes | `[]` | List of scoped permission objects |
| `constraints` | `JSONB` | Yes | `{}` | Task-level constraints |
| `deadline` | `DateTime(tz)` | No | — | Task deadline (auto-revoke after) |
| `auto_revoke_on_complete` | `Boolean` | Yes | `True` | Whether to revoke permissions on completion |
| `created_at` | `DateTime(tz)` | Yes | `NOW()` | Creation timestamp |
| `started_at` | `DateTime(tz)` | No | — | When task moved to "active" |
| `completed_at` | `DateTime(tz)` | No | — | When task completed/revoked |
| `usage_summary` | `JSONB` | Yes | `{}` | Aggregated usage counters |

### Table: `scoped_permissions`

| Column | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | `String(64)` | Yes | `sp-<uuid>` | Primary key |
| `task_id` | `String(64)` | Yes | — | FK to `tasks.id` |
| `permission_urn` | `String(512)` | Yes | — | Permission URN (e.g., `hubspot:contacts:read`) |
| `constraints` | `JSONB` | Yes | `{}` | Per-permission constraints |
| `valid_until` | `DateTime(tz)` | Yes | — | Expiry for this specific permission |
| `usage_count` | `Integer` | Yes | `0` | How many times this permission was used |
| `max_usage` | `Integer` | No | — | Maximum allowed uses (null = unlimited) |
| `revoked` | `Boolean` | Yes | `False` | Whether this permission has been revoked |
| `created_at` | `DateTime(tz)` | Yes | `NOW()` | Creation timestamp |

### Task Status Lifecycle

```
pending ──► active ──► completed
                   ──► revoked
                   ──► timed_out
```

| Status | Description | Transitions To |
|--------|-------------|----------------|
| `pending` | Created but not started | `active` |
| `active` | In progress, permissions active | `completed`, `revoked`, `timed_out` |
| `completed` | Finished normally, permissions revoked | (terminal) |
| `revoked` | Manually revoked by user/system | (terminal) |
| `timed_out` | Deadline passed, auto-revoked | (terminal) |

### Indexes

| Name | Columns | Type | Purpose |
|------|---------|------|---------|
| `ix_task_agent_id` | `agent_id` | B-tree | Lookup tasks by agent |
| `ix_task_status` | `status` | B-tree | Query active/pending tasks |
| `ix_task_agent_status` | `agent_id`, `status` | Composite | Active tasks for an agent |
| `ix_task_deadline` | `deadline` | B-tree | Find tasks past deadline |
| `ix_task_initiated_by` | `initiated_by` | B-tree | Audit: who created this task |
| `ix_scoped_perm_task_id` | `task_id` | B-tree | Permissions for a task |
| `ix_scoped_perm_urn` | `permission_urn` | B-tree | Find tasks with specific permissions |

### Relationships

| Relationship | Target | Type | Description |
|--------------|--------|------|-------------|
| `Task.scoped_permission_records` | `ScopedPermission` | One-to-Many | Task has many scoped permissions |
| `ScopedPermission.task` | `Task` | Many-to-One | Permission belongs to a task |

---

## Component Specification

### Model: `Task`

```python
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    Boolean, Column, DateTime, Index, Integer,
    String, Text, func,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy import JSON
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship

from app.db.base import Base


class TaskStatus:
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    REVOKED = "revoked"
    TIMED_OUT = "timed_out"

    TERMINAL = {COMPLETED, REVOKED, TIMED_OUT}
    ACTIVE_STATES = {PENDING, ACTIVE}


def generate_task_id() -> str:
    return f"task-{uuid.uuid4()}"


def generate_scoped_permission_id() -> str:
    return f"sp-{uuid.uuid4()}"


class Task(Base):
    """Represents a scoped unit of work for an agent (Token Layer 4).

    Tasks are the atomic unit of agent work. Each task has exactly the
    permissions needed for that specific work unit, enforcing least privilege.

    Architecture reference:
        Layer 4: Task Token (DeepSecure UNIQUE - not in research paper)
        Claims: task_id, agent_id, scoped_permissions, deadline, auto_revoke_on_complete

    Example:
        Agent SDR-001 creates a task to research a lead:
        - task_id: "task-outreach-lead-12345"
        - agent_id: "agent-sdr-001"
        - scoped_permissions: [
            { urn: "hubspot:contacts:read", constraints: { id: "12345" } }
          ]
        - deadline: 1 hour
        - auto_revoke_on_complete: true
    """

    __tablename__ = "tasks"

    id = Column(
        String(64),
        primary_key=True,
        default=generate_task_id,
        comment="Unique task identifier (e.g., task-<uuid>)",
    )

    agent_id = Column(
        String(64),
        nullable=False,
        index=True,
        comment="Agent that owns this task",
    )

    delegation_id = Column(
        String(64),
        nullable=True,
        comment="Delegation under which this task was created",
    )

    initiated_by = Column(
        String(255),
        nullable=False,
        comment="User who initiated/approved this task (for audit)",
    )

    name = Column(
        String(255),
        nullable=True,
        comment="Human-readable task name",
    )

    description = Column(
        Text,
        nullable=True,
        comment="Task description",
    )

    status = Column(
        String(50),
        nullable=False,
        default=TaskStatus.PENDING,
        index=True,
        comment="Task lifecycle status: pending, active, completed, revoked, timed_out",
    )

    scoped_permissions = Column(
        JSON().with_variant(postgresql.JSONB(), "postgresql"),
        nullable=False,
        default=list,
        comment="Scoped permissions for this task (list of {urn, constraints})",
    )

    constraints = Column(
        JSON().with_variant(postgresql.JSONB(), "postgresql"),
        nullable=False,
        default=dict,
        comment="Task-level constraints (rate limits, max tokens, etc.)",
    )

    deadline = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Task deadline (auto-revoke after this time)",
    )

    auto_revoke_on_complete = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether to revoke all scoped permissions on task completion",
    )

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
        comment="When the task was created",
    )

    started_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="When the task moved to active status",
    )

    completed_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="When the task completed, was revoked, or timed out",
    )

    usage_summary = Column(
        JSON().with_variant(postgresql.JSONB(), "postgresql"),
        nullable=False,
        default=dict,
        comment="Aggregated usage counters for audit",
    )

    __table_args__ = (
        Index("ix_task_agent_status", "agent_id", "status"),
        Index("ix_task_deadline", "deadline"),
        Index("ix_task_initiated_by", "initiated_by"),
    )

    # Relationships
    scoped_permission_records = relationship(
        "ScopedPermission",
        back_populates="task",
        cascade="all, delete-orphan",
    )

    # --- Hybrid properties ---

    def _ensure_tz(self, dt: Optional[datetime]) -> Optional[datetime]:
        if dt is None:
            return None
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt

    @hybrid_property
    def is_active(self) -> bool:
        return self.status == TaskStatus.ACTIVE

    @hybrid_property
    def is_terminal(self) -> bool:
        return self.status in TaskStatus.TERMINAL

    @hybrid_property
    def is_past_deadline(self) -> bool:
        if self.deadline is None:
            return False
        deadline = self._ensure_tz(self.deadline)
        return datetime.now(timezone.utc) >= deadline

    # --- Business methods ---

    def activate(self) -> None:
        if self.status != TaskStatus.PENDING:
            raise ValueError(f"Cannot activate task in '{self.status}' status")
        self.status = TaskStatus.ACTIVE
        self.started_at = datetime.now(timezone.utc)

    def complete(self) -> None:
        if self.status != TaskStatus.ACTIVE:
            raise ValueError(f"Cannot complete task in '{self.status}' status")
        self.status = TaskStatus.COMPLETED
        self.completed_at = datetime.now(timezone.utc)
        if self.auto_revoke_on_complete:
            self._revoke_all_permissions()

    def revoke(self) -> None:
        if self.status in TaskStatus.TERMINAL:
            raise ValueError(f"Cannot revoke task in '{self.status}' status")
        self.status = TaskStatus.REVOKED
        self.completed_at = datetime.now(timezone.utc)
        self._revoke_all_permissions()

    def timeout(self) -> None:
        if self.status in TaskStatus.TERMINAL:
            return  # Idempotent for already-terminal tasks
        self.status = TaskStatus.TIMED_OUT
        self.completed_at = datetime.now(timezone.utc)
        self._revoke_all_permissions()

    def _revoke_all_permissions(self) -> None:
        for sp in self.scoped_permission_records:
            sp.revoked = True

    def has_scoped_permission(self, permission_urn: str) -> bool:
        for perm in (self.scoped_permissions or []):
            if perm.get("urn") == permission_urn:
                return True
        return False

    def get_active_permission_urns(self) -> List[str]:
        return [
            sp.permission_urn
            for sp in self.scoped_permission_records
            if not sp.revoked and not sp.is_expired
        ]

    def to_token_claims(self) -> Dict[str, Any]:
        """Serialize to JWT-compatible claims for Task Token (Layer 4)."""
        created_at = self._ensure_tz(self.created_at)
        deadline = self._ensure_tz(self.deadline)

        return {
            "task_id": self.id,
            "agent_id": self.agent_id,
            "scoped_permissions": self.scoped_permissions or [],
            "deadline": deadline.isoformat() if deadline else None,
            "auto_revoke_on_complete": self.auto_revoke_on_complete,
            "iat": int(created_at.timestamp()) if created_at else None,
        }

    def __repr__(self) -> str:
        return (
            f"<Task(id='{self.id}', agent='{self.agent_id}', "
            f"status='{self.status}', permissions={len(self.scoped_permissions or [])})>"
        )


class ScopedPermission(Base):
    """Individual scoped permission record for a task.

    Tracks usage and enforces per-permission constraints and limits.
    """

    __tablename__ = "scoped_permissions"

    id = Column(
        String(64),
        primary_key=True,
        default=generate_scoped_permission_id,
        comment="Unique scoped permission identifier",
    )

    task_id = Column(
        String(64),
        nullable=False,
        index=True,
        comment="Task this permission belongs to",
    )

    permission_urn = Column(
        String(512),
        nullable=False,
        index=True,
        comment="Permission URN (e.g., hubspot:contacts:read)",
    )

    constraints = Column(
        JSON().with_variant(postgresql.JSONB(), "postgresql"),
        nullable=False,
        default=dict,
        comment="Per-permission constraints (e.g., {id: '12345'})",
    )

    valid_until = Column(
        DateTime(timezone=True),
        nullable=False,
        comment="Expiry for this specific permission grant",
    )

    usage_count = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of times this permission was used",
    )

    max_usage = Column(
        Integer,
        nullable=True,
        comment="Maximum allowed uses (null = unlimited)",
    )

    revoked = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether this permission has been revoked",
    )

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
        comment="When this permission was granted",
    )

    __table_args__ = (
        Index("ix_scoped_perm_task_urn", "task_id", "permission_urn"),
    )

    # Relationships
    task = relationship(
        "Task",
        back_populates="scoped_permission_records",
    )

    def _ensure_tz(self, dt: Optional[datetime]) -> Optional[datetime]:
        if dt is None:
            return None
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt

    @hybrid_property
    def is_expired(self) -> bool:
        valid_until = self._ensure_tz(self.valid_until)
        return datetime.now(timezone.utc) >= valid_until

    @hybrid_property
    def is_exhausted(self) -> bool:
        if self.max_usage is None:
            return False
        return self.usage_count >= self.max_usage

    @hybrid_property
    def is_usable(self) -> bool:
        return not self.revoked and not self.is_expired and not self.is_exhausted

    def increment_usage(self) -> bool:
        """Increment usage counter. Returns False if exhausted."""
        if not self.is_usable:
            return False
        self.usage_count += 1
        return True

    def __repr__(self) -> str:
        status = "usable" if self.is_usable else "unusable"
        return (
            f"<ScopedPermission(id='{self.id}', urn='{self.permission_urn}', "
            f"usage={self.usage_count}/{self.max_usage or '∞'}, status='{status}')>"
        )
```

### Pydantic Schemas (API Layer)

These schemas are used by the API endpoints (WS-K8) but should be defined alongside the model for consistency.

```python
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ScopedPermissionRequest(BaseModel):
    """Request schema for a single scoped permission."""
    permission_urn: str = Field(..., description="Permission URN (e.g., hubspot:contacts:read)")
    constraints: Dict[str, Any] = Field(default_factory=dict, description="Per-permission constraints")
    max_usage: Optional[int] = Field(None, description="Max usage count (null = unlimited)")


class TaskCreate(BaseModel):
    """Request schema for creating a task."""
    name: Optional[str] = Field(None, description="Human-readable task name")
    description: Optional[str] = Field(None, description="Task description")
    requested_permissions: List[ScopedPermissionRequest] = Field(
        ..., min_length=1, description="Permissions requested for this task"
    )
    deadline_minutes: Optional[int] = Field(
        None, ge=1, le=1440,
        description="Task deadline in minutes from now (max 24 hours)"
    )
    auto_revoke_on_complete: bool = Field(True, description="Auto-revoke on completion")


class TaskResponse(BaseModel):
    """Response schema for a task."""
    task_id: str
    agent_id: str
    name: Optional[str]
    status: str
    scoped_permissions: List[Dict[str, Any]]
    deadline: Optional[datetime]
    auto_revoke_on_complete: bool
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


class TaskTokenResponse(BaseModel):
    """Response when a task token is issued."""
    task_id: str
    task_token: str
    expires_at: datetime
    scoped_permissions: List[str]
```

---

## Database Migration

### Alembic Migration

Create migration file: `deeptrail-control/migrations/versions/xxx_create_task_tables.py`

```python
"""Create tasks and scoped_permissions tables

Revision ID: xxx
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


def upgrade() -> None:
    op.create_table(
        "tasks",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("agent_id", sa.String(64), nullable=False),
        sa.Column("delegation_id", sa.String(64), nullable=True),
        sa.Column("initiated_by", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("scoped_permissions", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("constraints", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("auto_revoke_on_complete", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("usage_summary", postgresql.JSONB(), nullable=False, server_default="{}"),
    )
    op.create_index("ix_task_agent_id", "tasks", ["agent_id"])
    op.create_index("ix_task_status", "tasks", ["status"])
    op.create_index("ix_task_agent_status", "tasks", ["agent_id", "status"])
    op.create_index("ix_task_deadline", "tasks", ["deadline"])
    op.create_index("ix_task_initiated_by", "tasks", ["initiated_by"])

    op.create_table(
        "scoped_permissions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("task_id", sa.String(64), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("permission_urn", sa.String(512), nullable=False),
        sa.Column("constraints", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("usage_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_usage", sa.Integer(), nullable=True),
        sa.Column("revoked", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_scoped_perm_task_id", "scoped_permissions", ["task_id"])
    op.create_index("ix_scoped_perm_urn", "scoped_permissions", ["permission_urn"])
    op.create_index("ix_scoped_perm_task_urn", "scoped_permissions", ["task_id", "permission_urn"])


def downgrade() -> None:
    op.drop_table("scoped_permissions")
    op.drop_table("tasks")
```

---

## API Contracts

> **Note:** This task creates the data model and schemas. API endpoints are in WS-K8.
> The model provides `to_token_claims()` for JWT serialization used by WS-K7 (TaskService).

### Future Endpoint Reference (WS-K8)

| Method | Path | Purpose | Uses |
|--------|------|---------|------|
| `POST` | `/api/v1/tasks` | Create a task | `TaskCreate`, `TaskResponse` |
| `GET` | `/api/v1/tasks/{task_id}` | Get task details | `TaskResponse` |
| `POST` | `/api/v1/tasks/{task_id}/complete` | Complete a task | `TaskResponse` |
| `POST` | `/api/v1/tasks/{task_id}/revoke` | Revoke a task | `TaskResponse` |

---

## File Location Rules

| Artifact | Correct Location |
|----------|------------------|
| SQLAlchemy model | `deeptrail-control/app/models/task_token.py` |
| Pydantic schemas | `deeptrail-control/app/models/task_token.py` (same file) |
| Model exports | `deeptrail-control/app/models/__init__.py` (update) |
| Migration | `deeptrail-control/migrations/versions/xxx_create_task_tables.py` |
| Unit tests | `deeptrail-control/tests/models/test_task_token.py` |

---

## Technical Requirements

### Framework-Specific

| Requirement | Pattern | Why |
|-------------|---------|-----|
| SQLAlchemy ORM | Inherit `Base` from `app.db.base` | Project convention |
| JSONB columns | `JSON().with_variant(postgresql.JSONB(), "postgresql")` | Cross-DB compat (PostgreSQL + SQLite) |
| Timezone-aware datetimes | `DateTime(timezone=True)` + `_ensure_tz()` helper | Consistent UTC handling |
| Hybrid properties | `@hybrid_property` for computed state | Works in both Python and SQL contexts |
| ID generation | `f"task-{uuid.uuid4()}"` pattern | Matches delegation ID pattern |

### Dependencies

| Dependency | Version | Purpose |
|------------|---------|---------|
| `sqlalchemy` | existing | ORM models |
| `alembic` | existing | Database migrations |
| `pydantic` | existing | API schemas |

### Existing Code Relationship

| Existing Module | Relationship | Notes |
|-----------------|-------------|-------|
| `delegation.py` | Pattern reference | Follow same ORM style, JSONB usage, hybrid properties |
| `agent_session.py` | Sibling | Task exists within an agent session context |
| `vault_token.py` | Pattern reference | Similar encrypted storage patterns |
| `models/__init__.py` | Update | Add Task, ScopedPermission to exports |

---

## Test Cases

### Unit Tests

| Test Case | Method | Expected | Notes |
|-----------|--------|----------|-------|
| Create task with defaults | `Task()` | Default status "pending", auto_revoke True | Constructor |
| Generate task ID | `generate_task_id()` | Format `task-<uuid>` | ID pattern |
| Task status lifecycle: activate | `task.activate()` | Status → "active", started_at set | State transition |
| Task status lifecycle: complete | `task.complete()` | Status → "completed", completed_at set | Terminal state |
| Task status lifecycle: revoke | `task.revoke()` | Status → "revoked", all perms revoked | Manual revoke |
| Task status lifecycle: timeout | `task.timeout()` | Status → "timed_out", all perms revoked | Deadline exceeded |
| Cannot activate non-pending task | `task.activate()` | Raises `ValueError` | Guard |
| Cannot complete non-active task | `task.complete()` | Raises `ValueError` | Guard |
| Cannot revoke terminal task | `task.revoke()` | Raises `ValueError` | Guard |
| Timeout idempotent on terminal | `task.timeout()` | No error | Graceful |
| is_active property | `task.is_active` | True when active, False otherwise | Hybrid |
| is_terminal property | `task.is_terminal` | True for completed/revoked/timed_out | Hybrid |
| is_past_deadline | `task.is_past_deadline` | True when now > deadline | Timezone-aware |
| is_past_deadline no deadline | `task.is_past_deadline` | False | Null deadline |
| has_scoped_permission | `task.has_scoped_permission("x:y:z")` | True/False | JSONB lookup |
| to_token_claims | `task.to_token_claims()` | Dict with Layer 4 claims | JWT serialization |
| Auto-revoke permissions on complete | `task.complete()` | All ScopedPermissions revoked | Cascade |
| ScopedPermission is_usable | `sp.is_usable` | True when not revoked/expired/exhausted | Composite check |
| ScopedPermission increment_usage | `sp.increment_usage()` | Counter incremented | Returns True |
| ScopedPermission exhausted | `sp.increment_usage()` at max | Returns False | Max reached |
| ScopedPermission is_expired | `sp.is_expired` | True when past valid_until | Timezone-aware |
| TaskCreate schema validation | `TaskCreate(...)` | Validates min_length, deadline range | Pydantic |
| TaskCreate rejects empty permissions | `TaskCreate(requested_permissions=[])` | ValidationError | min_length=1 |
| TaskResponse from_attributes | `TaskResponse.model_validate(task)` | Serializes correctly | ORM mode |

### Database Tests

| Test Case | Setup | Expected | Notes |
|-----------|-------|----------|-------|
| Create task in DB | Session.add + commit | Task persisted with all columns | PostgreSQL |
| JSONB scoped_permissions | Store list of dicts | Retrieved correctly | Cross-DB |
| Cascade delete | Delete task | ScopedPermissions deleted | FK cascade |
| Index performance | Query by agent_id + status | Uses composite index | Explain plan |

### Test Code Example

```python
import pytest
from datetime import datetime, timedelta, timezone

from app.models.task_token import (
    Task,
    ScopedPermission,
    TaskStatus,
    generate_task_id,
    generate_scoped_permission_id,
)


class TestTask:
    def test_create_with_defaults(self):
        task = Task(
            agent_id="agent-sdr-001",
            initiated_by="sarah@acme.com",
            scoped_permissions=[
                {"urn": "hubspot:contacts:read", "constraints": {"id": "12345"}}
            ],
        )
        assert task.status == TaskStatus.PENDING
        assert task.auto_revoke_on_complete is True
        assert task.scoped_permissions is not None
        assert len(task.scoped_permissions) == 1

    def test_generate_task_id_format(self):
        tid = generate_task_id()
        assert tid.startswith("task-")
        assert len(tid) > 10

    def test_activate_from_pending(self):
        task = Task(
            agent_id="agent-001",
            initiated_by="user@test.com",
            scoped_permissions=[],
        )
        task.activate()
        assert task.status == TaskStatus.ACTIVE
        assert task.started_at is not None

    def test_cannot_activate_active_task(self):
        task = Task(
            agent_id="agent-001",
            initiated_by="user@test.com",
            scoped_permissions=[],
            status=TaskStatus.ACTIVE,
        )
        with pytest.raises(ValueError, match="Cannot activate"):
            task.activate()

    def test_complete_revokes_permissions(self):
        task = Task(
            agent_id="agent-001",
            initiated_by="user@test.com",
            scoped_permissions=[{"urn": "test:perm"}],
            status=TaskStatus.ACTIVE,
            auto_revoke_on_complete=True,
        )
        sp = ScopedPermission(
            task_id=task.id,
            permission_urn="test:perm",
            valid_until=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        task.scoped_permission_records = [sp]
        task.complete()
        assert task.status == TaskStatus.COMPLETED
        assert sp.revoked is True

    def test_is_past_deadline(self):
        task = Task(
            agent_id="agent-001",
            initiated_by="user@test.com",
            scoped_permissions=[],
            deadline=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        assert task.is_past_deadline is True

    def test_no_deadline_not_past(self):
        task = Task(
            agent_id="agent-001",
            initiated_by="user@test.com",
            scoped_permissions=[],
            deadline=None,
        )
        assert task.is_past_deadline is False

    def test_to_token_claims(self):
        task = Task(
            id="task-test-123",
            agent_id="agent-sdr-001",
            initiated_by="sarah@acme.com",
            scoped_permissions=[
                {"urn": "hubspot:contacts:read", "constraints": {"id": "12345"}}
            ],
            auto_revoke_on_complete=True,
        )
        claims = task.to_token_claims()
        assert claims["task_id"] == "task-test-123"
        assert claims["agent_id"] == "agent-sdr-001"
        assert len(claims["scoped_permissions"]) == 1
        assert claims["auto_revoke_on_complete"] is True

    def test_timeout_idempotent_on_terminal(self):
        task = Task(
            agent_id="agent-001",
            initiated_by="user@test.com",
            scoped_permissions=[],
            status=TaskStatus.COMPLETED,
        )
        task.timeout()  # Should not raise
        assert task.status == TaskStatus.COMPLETED  # Unchanged


class TestScopedPermission:
    def test_is_usable_when_valid(self):
        sp = ScopedPermission(
            task_id="task-001",
            permission_urn="notion:pages:search",
            valid_until=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        assert sp.is_usable is True

    def test_not_usable_when_revoked(self):
        sp = ScopedPermission(
            task_id="task-001",
            permission_urn="notion:pages:search",
            valid_until=datetime.now(timezone.utc) + timedelta(hours=1),
            revoked=True,
        )
        assert sp.is_usable is False

    def test_not_usable_when_expired(self):
        sp = ScopedPermission(
            task_id="task-001",
            permission_urn="notion:pages:search",
            valid_until=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        assert sp.is_usable is False

    def test_increment_usage(self):
        sp = ScopedPermission(
            task_id="task-001",
            permission_urn="test:perm",
            valid_until=datetime.now(timezone.utc) + timedelta(hours=1),
            max_usage=5,
            usage_count=0,
        )
        assert sp.increment_usage() is True
        assert sp.usage_count == 1

    def test_increment_usage_exhausted(self):
        sp = ScopedPermission(
            task_id="task-001",
            permission_urn="test:perm",
            valid_until=datetime.now(timezone.utc) + timedelta(hours=1),
            max_usage=1,
            usage_count=1,
        )
        assert sp.increment_usage() is False
```

---

## Contract Verification Checklist

Before marking implementation complete, verify:

- [ ] `Task` model exists in `deeptrail-control/app/models/task_token.py` inheriting `Base`
- [ ] `ScopedPermission` model exists with FK to `tasks.id`
- [ ] All columns match spec (names, types, nullability, defaults)
- [ ] Task status lifecycle works: `activate()`, `complete()`, `revoke()`, `timeout()`
- [ ] Invalid transitions raise `ValueError` (guard clauses)
- [ ] `auto_revoke_on_complete` cascades to `ScopedPermission.revoked`
- [ ] Hybrid properties work: `is_active`, `is_terminal`, `is_past_deadline`
- [ ] `to_token_claims()` produces Layer 4 JWT claims
- [ ] `ScopedPermission.is_usable` checks revoked, expired, and exhausted
- [ ] `ScopedPermission.increment_usage()` respects max_usage
- [ ] Pydantic schemas: `TaskCreate`, `TaskResponse`, `TaskTokenResponse`
- [ ] `TaskCreate` validates min 1 permission and deadline range
- [ ] Alembic migration creates both tables with all indexes
- [ ] Model exports added to `app/models/__init__.py`
- [ ] All unit tests pass
- [ ] JSONB columns work with both PostgreSQL and SQLite (test uses `JSON()` variant)

---

## Security Considerations

| Aspect | Status | Notes |
|--------|--------|-------|
| Scoped permissions principle | Enforced | Permissions ⊂ delegation permissions (validated by TaskService in WS-K7) |
| Auto-revocation | Implemented | `complete()` and `timeout()` revoke all scoped permissions |
| Deadline enforcement | Model-level | `is_past_deadline` property; actual timeout requires cron/scheduler (WS-K7) |
| Audit trail | Built-in | `initiated_by`, `usage_summary`, `created_at`, `completed_at` |
| Terminal state immutability | Enforced | `ValueError` on invalid state transitions |

---

## Validation Commands

### Unit Tests

```bash
cd deeptrail-control
pytest tests/models/test_task_token.py -v
```

### Migration Test

```bash
cd deeptrail-control

# Generate migration (verify it matches spec)
alembic revision --autogenerate -m "create task tables"

# Apply migration
alembic upgrade head

# Verify tables exist
docker compose exec db psql -U deepsecure_user -d deeptrail_controldb -c "\dt tasks"
docker compose exec db psql -U deepsecure_user -d deeptrail_controldb -c "\dt scoped_permissions"

# Verify indexes
docker compose exec db psql -U deepsecure_user -d deeptrail_controldb -c "\di ix_task_*"
```

### Manual Verification

```bash
# Verify model imports work
cd deeptrail-control
python -c "from app.models.task_token import Task, ScopedPermission, TaskStatus; print('OK')"

# Verify schema validation
python -c "
from app.models.task_token import TaskCreate
t = TaskCreate(
    name='test',
    requested_permissions=[{'permission_urn': 'test:perm', 'constraints': {}}],
    deadline_minutes=60
)
print(f'Task: {t.name}, permissions: {len(t.requested_permissions)}')
"
```

---

## References

- **Architecture:** `deepsecure-comprehensive-architecture-consolidated.md`
  - Section 7: Complete Six-Layer Token Hierarchy (Layer 4: Task Token)
  - Section 9: Per-Task Permission Architecture
  - Section 14.2: Task Management Service
  - Database schemas for `tasks` and `scoped_permissions`
- **Token Claims:** `task_id`, `agent_id`, `scoped_permissions`, `deadline`, `auto_revoke_on_complete`
- **Model Pattern:** `deeptrail-control/app/models/delegation.py` (DelegationToken)
- **Upstream Dependencies:** MP3.5 (P1.5 complete)
- **Downstream Dependents:** WS-K7 (TaskService uses Task model), WS-K8 (Task endpoints use schemas)
