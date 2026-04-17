"""Task management API endpoints (Layer 4 — Task Token).

Provides CRUD, lifecycle transitions, and Task Token JWT issuance.
All business logic is delegated to TaskService (WS-K7).
"""

import logging
from typing import Optional

import jwt as pyjwt
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.api import deps
from app.core.config import settings
from app.models.task_token import TaskCreate, TaskResponse, TaskTokenResponse
from app.schemas.task import TaskListResponse
from app.services.task_service import (
    TaskLifecycleError,
    TaskNotFoundError,
    TaskPermissionError,
    TaskService,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# ============================================================================
# Auth dependency — works with both User JWTs and Agent JWTs
# ============================================================================

_bearer_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


def _get_caller_identity(
    token: str = Depends(_bearer_scheme),
) -> dict:
    """Extract caller identity from a User or Agent JWT.

    User JWT claims:  sub (email), session_id, organization_id
    Agent JWT claims: sub (agent_id), owner (user_id), delegated_permissions
    """
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = pyjwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
            options={"verify_aud": False},
        )
    except pyjwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    sub = payload.get("sub", "unknown")
    owner = payload.get("owner")

    if owner:
        return {
            "agent_id": sub,
            "user_id": owner,
            "delegation_id": payload.get("delegation_id"),
            "delegated_permissions": payload.get("delegated_permissions"),
            "organization_id": payload.get("organization_id"),
        }
    return {
        "agent_id": sub,
        "user_id": sub,
        "delegation_id": None,
        "delegated_permissions": None,
        "organization_id": payload.get("organization_id"),
    }


def _get_service(db: Session = Depends(deps.get_db)) -> TaskService:
    return TaskService(db=db, jwt_secret=settings.SECRET_KEY)


# ============================================================================
# Endpoints
# ============================================================================


@router.post("/", response_model=TaskResponse, status_code=201)
def create_task(
    task_data: TaskCreate,
    identity: dict = Depends(_get_caller_identity),
    service: TaskService = Depends(_get_service),
):
    """Create a new task with scoped permissions."""
    try:
        task = service.create_task(
            agent_id=identity["agent_id"],
            initiated_by=identity["user_id"],
            task_data=task_data,
            delegation_id=identity.get("delegation_id"),
            delegation_permissions=identity.get("delegated_permissions"),
            organization_id=identity.get("organization_id"),
        )
        return _task_to_response(task)
    except TaskPermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "message": str(exc),
                "invalid_permissions": exc.invalid_permissions,
                "allowed_permissions": exc.allowed_permissions,
            },
        )


@router.get("/{task_id}", response_model=TaskResponse)
def get_task(
    task_id: str,
    identity: dict = Depends(_get_caller_identity),
    service: TaskService = Depends(_get_service),
):
    """Retrieve task details."""
    try:
        task = service.get_task(task_id)
        return _task_to_response(task)
    except TaskNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task not found: {task_id}",
        )


@router.get("/", response_model=TaskListResponse)
def list_tasks(
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    identity: dict = Depends(_get_caller_identity),
    service: TaskService = Depends(_get_service),
):
    """List tasks for the authenticated caller."""
    tasks = service.list_tasks(
        agent_id=identity["agent_id"],
        status=status_filter,
        limit=limit,
        offset=offset,
    )
    return TaskListResponse(
        tasks=[_task_to_response_dict(t) for t in tasks],
        total=len(tasks),
        limit=limit,
        offset=offset,
    )


@router.post("/{task_id}/activate", response_model=TaskResponse)
def activate_task(
    task_id: str,
    identity: dict = Depends(_get_caller_identity),
    service: TaskService = Depends(_get_service),
):
    """Transition task from PENDING to ACTIVE."""
    try:
        task = service.activate_task(task_id)
        return _task_to_response(task)
    except TaskNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task not found: {task_id}",
        )
    except TaskLifecycleError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@router.post("/{task_id}/complete", response_model=TaskResponse)
def complete_task(
    task_id: str,
    identity: dict = Depends(_get_caller_identity),
    service: TaskService = Depends(_get_service),
):
    """Complete an active task (auto-revokes permissions if configured)."""
    try:
        task = service.complete_task(task_id)
        return _task_to_response(task)
    except TaskNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task not found: {task_id}",
        )
    except TaskLifecycleError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@router.post("/{task_id}/revoke", response_model=TaskResponse)
def revoke_task(
    task_id: str,
    identity: dict = Depends(_get_caller_identity),
    service: TaskService = Depends(_get_service),
):
    """Force-revoke a task and all its permissions."""
    try:
        task = service.revoke_task(task_id)
        return _task_to_response(task)
    except TaskNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task not found: {task_id}",
        )
    except TaskLifecycleError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@router.post("/{task_id}/token", response_model=TaskTokenResponse)
def issue_task_token(
    task_id: str,
    identity: dict = Depends(_get_caller_identity),
    service: TaskService = Depends(_get_service),
):
    """Issue a JWT Task Token for an active task."""
    try:
        return service.issue_task_token(task_id)
    except TaskNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task not found: {task_id}",
        )
    except TaskLifecycleError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


# ============================================================================
# Helpers
# ============================================================================


def _task_to_response(task) -> TaskResponse:
    """Map a Task ORM object to TaskResponse."""
    return TaskResponse(
        task_id=task.id,
        agent_id=task.agent_id,
        name=task.name,
        status=task.status,
        scoped_permissions=task.scoped_permissions or [],
        deadline=task.deadline,
        auto_revoke_on_complete=task.auto_revoke_on_complete,
        created_at=task.created_at,
        started_at=task.started_at,
        completed_at=task.completed_at,
    )


def _task_to_response_dict(task) -> dict:
    """Map a Task ORM object to a dict for list responses."""
    return {
        "task_id": task.id,
        "agent_id": task.agent_id,
        "name": task.name,
        "status": task.status,
        "scoped_permissions": task.scoped_permissions or [],
        "deadline": task.deadline.isoformat() if task.deadline else None,
        "auto_revoke_on_complete": task.auto_revoke_on_complete,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
    }
