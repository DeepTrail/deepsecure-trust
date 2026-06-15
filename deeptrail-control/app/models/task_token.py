"""SQLAlchemy models for Task Token (Layer 4) and Scoped Permissions.

Layer 4 of the 6-layer token hierarchy provides per-task scoped permissions.
Each task narrows an agent's permissions to exactly what's needed for a
specific work unit, with automatic revocation on completion and deadline
enforcement.

Architecture reference:
    Section 7: Complete Six-Layer Token Hierarchy (Layer 4: Task Token)
    Section 9: Per-Task Permission Architecture
    Section 14.2: Task Management Service
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy import JSON
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship

from app.db.base import Base


# ============================================================================
# Constants
# ============================================================================


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


# ============================================================================
# SQLAlchemy Models
# ============================================================================


def _ensure_tz(dt: Optional[datetime]) -> Optional[datetime]:
    """Ensure a datetime is timezone-aware (default UTC)."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class Task(Base):
    """Represents a scoped unit of work for an agent (Token Layer 4).

    Tasks are the atomic unit of agent work. Each task has exactly the
    permissions needed for that specific work unit, enforcing least privilege.

    Architecture reference:
        Layer 4: Task Token (DeepSecure UNIQUE - not in research paper)
        Claims: task_id, agent_id, scoped_permissions, deadline, auto_revoke_on_complete
    """

    __tablename__ = "tasks"

    id = Column(
        String(64),
        primary_key=True,
        default=generate_task_id,
    )
    agent_id = Column(String(64), nullable=False, index=True)
    delegation_id = Column(String(64), nullable=True)
    organization_id = Column(String(64), nullable=True, index=True)
    initiated_by = Column(String(255), nullable=False)
    name = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    status = Column(
        String(50),
        nullable=False,
        default=TaskStatus.PENDING,
        index=True,
    )
    scoped_permissions = Column(
        JSON().with_variant(postgresql.JSONB(), "postgresql"),
        nullable=False,
        default=list,
    )
    constraints = Column(
        JSON().with_variant(postgresql.JSONB(), "postgresql"),
        nullable=False,
        default=dict,
    )
    deadline = Column(DateTime(timezone=True), nullable=True)
    auto_revoke_on_complete = Column(Boolean, nullable=False, default=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    usage_summary = Column(
        JSON().with_variant(postgresql.JSONB(), "postgresql"),
        nullable=False,
        default=dict,
    )

    __table_args__ = (
        Index("ix_task_agent_status", "agent_id", "status"),
        Index("ix_task_deadline", "deadline"),
        Index("ix_task_initiated_by", "initiated_by"),
    )

    scoped_permission_records = relationship(
        "ScopedPermission",
        back_populates="task",
        cascade="all, delete-orphan",
    )

    def __init__(self, **kwargs):
        kwargs.setdefault("id", generate_task_id())
        kwargs.setdefault("status", TaskStatus.PENDING)
        kwargs.setdefault("scoped_permissions", [])
        kwargs.setdefault("constraints", {})
        kwargs.setdefault("auto_revoke_on_complete", True)
        kwargs.setdefault("created_at", datetime.now(timezone.utc))
        kwargs.setdefault("usage_summary", {})
        super().__init__(**kwargs)

    # --- Hybrid properties ---

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
        deadline = _ensure_tz(self.deadline)
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
        created_at = _ensure_tz(self.created_at)
        deadline = _ensure_tz(self.deadline)
        return {
            "task_id": self.id,
            "agent_id": self.agent_id,
            "owner": self.initiated_by,
            "scoped_permissions": self.scoped_permissions or [],
            "deadline": deadline.isoformat() if deadline else None,
            "auto_revoke_on_complete": self.auto_revoke_on_complete,
            "organization_id": self.organization_id,
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
    )
    task_id = Column(
        String(64),
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    permission_urn = Column(String(512), nullable=False, index=True)
    constraints = Column(
        JSON().with_variant(postgresql.JSONB(), "postgresql"),
        nullable=False,
        default=dict,
    )
    valid_until = Column(DateTime(timezone=True), nullable=False)
    usage_count = Column(Integer, nullable=False, default=0)
    max_usage = Column(Integer, nullable=True)
    revoked = Column(Boolean, nullable=False, default=False)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_scoped_perm_task_urn", "task_id", "permission_urn"),
    )

    task = relationship(
        "Task",
        back_populates="scoped_permission_records",
    )

    def __init__(self, **kwargs):
        kwargs.setdefault("id", generate_scoped_permission_id())
        kwargs.setdefault("constraints", {})
        kwargs.setdefault("usage_count", 0)
        kwargs.setdefault("revoked", False)
        kwargs.setdefault("created_at", datetime.now(timezone.utc))
        super().__init__(**kwargs)

    @hybrid_property
    def is_expired(self) -> bool:
        valid_until = _ensure_tz(self.valid_until)
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


# ============================================================================
# Pydantic Schemas (API Layer)
# ============================================================================


class ScopedPermissionRequest(BaseModel):
    """Request schema for a single scoped permission."""

    permission_urn: str = Field(..., description="Permission URN (e.g., notion:pages:search)")
    constraints: Dict[str, Any] = Field(default_factory=dict, description="Per-permission constraints")
    max_usage: Optional[int] = Field(None, description="Max usage count (null = unlimited)")


class TaskCreate(BaseModel):
    """Request schema for creating a task."""

    name: Optional[str] = Field(None, description="Human-readable task name")
    description: Optional[str] = Field(None, description="Task description")
    requested_permissions: Optional[List[ScopedPermissionRequest]] = Field(
        default=None, description="Permissions requested for this task"
    )

    @field_validator("requested_permissions")
    @classmethod
    def validate_permissions_not_empty(cls, v):
        if v is not None and len(v) == 0:
            raise ValueError("requested_permissions must not be empty if provided")
        return v

    deadline_minutes: Optional[int] = Field(
        None,
        ge=1,
        le=1440,
        description="Task deadline in minutes from now (max 24 hours)",
    )
    auto_revoke_on_complete: bool = Field(True, description="Auto-revoke on completion")


class TaskResponse(BaseModel):
    """Response schema for a task."""

    task_id: str
    agent_id: str
    name: Optional[str] = None
    status: str
    scoped_permissions: List[Dict[str, Any]]
    deadline: Optional[datetime] = None
    auto_revoke_on_complete: bool
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class TaskTokenResponse(BaseModel):
    """Response when a task token is issued."""

    task_id: str
    task_token: str
    expires_at: datetime
    scoped_permissions: List[str]
