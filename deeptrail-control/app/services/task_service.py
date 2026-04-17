"""TaskService — business logic for Task lifecycle and Task Token JWT issuance.

Manages Layer 4 (Task Token) of the DeepSecure token hierarchy:
    Layer 0: User ID-Token
    Layer 1: Organization Key
    Layer 2: Agent ID-Token (Ed25519)
    Layer 3: Delegation Token
    Layer 4: Task Token  ← THIS SERVICE

Enforces monotonic attenuation: task permissions ⊆ delegation permissions.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import jwt as pyjwt
from sqlalchemy.orm import Session

from app.models.task_token import (
    ScopedPermission,
    Task,
    TaskCreate,
    TaskStatus,
    TaskTokenResponse,
    generate_scoped_permission_id,
    generate_task_id,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Error Hierarchy
# ============================================================================


class TaskServiceError(Exception):
    """Base error for TaskService operations."""

    pass


class TaskNotFoundError(TaskServiceError):
    """Task does not exist or agent ownership mismatch."""

    pass


class TaskPermissionError(TaskServiceError):
    """Requested permissions exceed delegation scope."""

    def __init__(
        self,
        message: str,
        invalid_permissions: List[str],
        allowed_permissions: List[str],
    ):
        super().__init__(message)
        self.invalid_permissions = invalid_permissions
        self.allowed_permissions = allowed_permissions


class TaskLifecycleError(TaskServiceError):
    """Invalid task state transition."""

    pass


# ============================================================================
# TaskService
# ============================================================================


class TaskService:
    """Business logic for Task lifecycle and Task Token issuance.

    Manages Layer 4 (Task Token) of the DeepSecure token hierarchy.
    Enforces permission scoping: task permissions ⊆ delegation permissions.
    """

    JWT_ALGORITHM = "HS256"
    DEFAULT_TOKEN_TTL_HOURS = 1

    def __init__(self, db: Session, jwt_secret: str):
        self._db = db
        self._jwt_secret = jwt_secret

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create_task(
        self,
        agent_id: str,
        initiated_by: str,
        task_data: TaskCreate,
        delegation_id: Optional[str] = None,
        delegation_permissions: Optional[List[str]] = None,
        organization_id: Optional[str] = None,
    ) -> Task:
        """Create a new task with scoped permissions.

        Validates requested permissions ⊆ delegation_permissions (if provided),
        then persists Task + ScopedPermission records.

        Raises:
            TaskPermissionError: If requested permissions exceed delegation scope.
        """
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
            organization_id=organization_id,
            name=task_data.name,
            description=task_data.description,
            scoped_permissions=[
                {"urn": p.permission_urn, "constraints": p.constraints}
                for p in task_data.requested_permissions
            ],
            deadline=deadline,
            auto_revoke_on_complete=task_data.auto_revoke_on_complete,
        )

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
            "Task created: task_id=%s agent_id=%s permissions=%d deadline=%s",
            task.id,
            agent_id,
            len(requested_urns),
            deadline.isoformat() if deadline else None,
        )
        return task

    def get_task(self, task_id: str, agent_id: Optional[str] = None) -> Task:
        """Fetch a task by ID with optional ownership check.

        Raises:
            TaskNotFoundError: If task doesn't exist or agent_id doesn't match.
        """
        query = self._db.query(Task).filter(Task.id == task_id)
        if agent_id is not None:
            query = query.filter(Task.agent_id == agent_id)
        task = query.first()
        if task is None:
            raise TaskNotFoundError(f"Task not found: {task_id}")
        return task

    def list_tasks(
        self,
        agent_id: str,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Task]:
        """List tasks for an agent, optionally filtered by status."""
        query = self._db.query(Task).filter(Task.agent_id == agent_id)
        if status is not None:
            query = query.filter(Task.status == status)
        return (
            query.order_by(Task.created_at.desc())
            .limit(limit)
            .offset(offset)
            .all()
        )

    def activate_task(self, task_id: str, agent_id: Optional[str] = None) -> Task:
        """Transition a task from PENDING to ACTIVE.

        Raises:
            TaskNotFoundError: If task doesn't exist.
            TaskLifecycleError: If task is not in PENDING status.
        """
        task = self.get_task(task_id, agent_id)
        if task.status != TaskStatus.PENDING:
            raise TaskLifecycleError(
                f"Cannot activate task in '{task.status}' status (must be PENDING)"
            )
        task.activate()
        self._db.commit()
        logger.info("Task activated: task_id=%s", task_id)
        return task

    def complete_task(self, task_id: str, agent_id: Optional[str] = None) -> Task:
        """Transition a task from ACTIVE to COMPLETED.

        Auto-revokes permissions when auto_revoke_on_complete is True.

        Raises:
            TaskNotFoundError: If task doesn't exist.
            TaskLifecycleError: If task is not in ACTIVE status.
        """
        task = self.get_task(task_id, agent_id)
        if task.status != TaskStatus.ACTIVE:
            raise TaskLifecycleError(
                f"Cannot complete task in '{task.status}' status (must be ACTIVE)"
            )
        task.complete()
        self._db.commit()
        logger.info("Task completed: task_id=%s auto_revoked=%s", task_id, task.auto_revoke_on_complete)
        return task

    def revoke_task(self, task_id: str, agent_id: Optional[str] = None) -> Task:
        """Force-revoke a non-terminal task.

        Raises:
            TaskNotFoundError: If task doesn't exist.
            TaskLifecycleError: If task is already in a terminal state.
        """
        task = self.get_task(task_id, agent_id)
        if task.is_terminal:
            raise TaskLifecycleError(
                f"Cannot revoke task in '{task.status}' status (already terminal)"
            )
        task.revoke()
        self._db.commit()
        logger.info("Task revoked: task_id=%s", task_id)
        return task

    def issue_task_token(
        self,
        task_id: str,
        agent_id: Optional[str] = None,
    ) -> TaskTokenResponse:
        """Issue a JWT Task Token (Layer 4) for an active task.

        Token exp = min(deadline, now + 1h). Never exceeds task deadline.

        Raises:
            TaskNotFoundError: If task doesn't exist.
            TaskLifecycleError: If task is not ACTIVE.
        """
        task = self.get_task(task_id, agent_id)
        if task.status != TaskStatus.ACTIVE:
            raise TaskLifecycleError(
                f"Cannot issue token for task in '{task.status}' status (must be ACTIVE)"
            )

        claims = task.to_token_claims()

        now = datetime.now(timezone.utc)
        default_exp = now + timedelta(hours=self.DEFAULT_TOKEN_TTL_HOURS)
        if task.deadline:
            deadline = task.deadline if task.deadline.tzinfo else task.deadline.replace(tzinfo=timezone.utc)
            expires_at = min(deadline, default_exp)
        else:
            expires_at = default_exp

        claims["exp"] = int(expires_at.timestamp())
        claims["iss"] = "deeptrail-control"
        claims["aud"] = "deeptrail-gateway"
        claims["token_type"] = "task_token"

        token = pyjwt.encode(claims, self._jwt_secret, algorithm=self.JWT_ALGORITHM)

        logger.info("Task token issued: task_id=%s expires=%s", task_id, expires_at.isoformat())

        return TaskTokenResponse(
            task_id=task.id,
            task_token=token,
            expires_at=expires_at,
            scoped_permissions=task.get_active_permission_urns(),
        )

    def check_deadline_timeouts(self) -> int:
        """Find all non-terminal tasks past their deadline and time them out.

        Returns:
            Number of tasks timed out.
        """
        now = datetime.now(timezone.utc)
        tasks = (
            self._db.query(Task)
            .filter(
                Task.deadline.isnot(None),
                Task.deadline < now,
                Task.status.notin_(list(TaskStatus.TERMINAL)),
            )
            .all()
        )
        count = 0
        for task in tasks:
            task.timeout()
            count += 1
            logger.info("Task timed out: task_id=%s deadline=%s", task.id, task.deadline)

        if count > 0:
            self._db.commit()

        return count

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _validate_permissions_subset(
        self,
        requested: List[str],
        allowed: List[str],
    ) -> None:
        """Ensure requested permission URNs are a subset of allowed (monotonic attenuation)."""
        requested_set = set(requested)
        allowed_set = set(allowed)
        invalid = requested_set - allowed_set
        if invalid:
            raise TaskPermissionError(
                f"Requested permissions exceed delegation scope: {sorted(invalid)}",
                invalid_permissions=sorted(invalid),
                allowed_permissions=sorted(allowed_set),
            )
