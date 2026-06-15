"""Tests for Task API endpoints (WS-K8).

Tests the task management endpoints:
- POST   /api/v1/tasks             (create)
- GET    /api/v1/tasks/{task_id}    (get)
- GET    /api/v1/tasks              (list)
- POST   /api/v1/tasks/{id}/activate
- POST   /api/v1/tasks/{id}/complete
- POST   /api/v1/tasks/{id}/revoke
- POST   /api/v1/tasks/{id}/token

Test Categories:
- Auth: 401 on missing/invalid token
- Create: success (201), permission exceeded (403)
- Get: success (200), not found (404)
- List: no filter, status filter, pagination
- Lifecycle: activate/complete/revoke success, lifecycle error (409)
- Token: issue success, not-active error (409)
"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import jwt as pyjwt
import pytest

from app.api.v1.endpoints import tasks as tasks_module
from app.core.config import settings
from app.main import app
from app.services.task_service import (
    TaskLifecycleError,
    TaskNotFoundError,
    TaskPermissionError,
)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _make_user_jwt(**extra_claims) -> str:
    """Create a valid User JWT."""
    payload = {
        "sub": "sarah@acme.com",
        "session_id": "sess-001",
        "exp": int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
        **extra_claims,
    }
    return pyjwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def _make_agent_jwt(**extra_claims) -> str:
    """Create a valid Agent JWT with delegation info."""
    payload = {
        "sub": "agent-sdr-001",
        "owner": "sarah@acme.com",
        "delegation_id": "deleg-001",
        "delegated_permissions": ["notion:pages:search", "notion:pages:read"],
        "exp": int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
        **extra_claims,
    }
    return pyjwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def _make_task_obj(**overrides):
    """Create a mock Task-like object with default attributes."""
    now = datetime.now(timezone.utc)
    defaults = {
        "id": "task-abc-123",
        "agent_id": "agent-sdr-001",
        "name": "Research lead",
        "status": "pending",
        "scoped_permissions": [{"urn": "notion:pages:search", "constraints": {}}],
        "deadline": now + timedelta(hours=1),
        "auto_revoke_on_complete": True,
        "created_at": now,
        "started_at": None,
        "completed_at": None,
        "scoped_permission_records": [],
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


CREATE_BODY = {
    "name": "Research lead 12345",
    "requested_permissions": [
        {"permission_urn": "notion:pages:search", "constraints": {"id": "12345"}}
    ],
    "deadline_minutes": 60,
    "auto_revoke_on_complete": True,
}


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def user_token():
    return _make_user_jwt()


@pytest.fixture
def agent_token():
    return _make_agent_jwt()


@pytest.fixture
def mock_service():
    """Override _get_service dependency to return a mock TaskService."""
    svc = MagicMock()
    original_fn = tasks_module._get_service
    app.dependency_overrides[original_fn] = lambda: svc
    yield svc
    app.dependency_overrides.pop(original_fn, None)


# ─────────────────────────────────────────────────────────────────────────────
# Auth Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestAuth:
    """All endpoints require Bearer token."""

    def test_create_no_token_returns_401(self, client):
        resp = client.post("/api/v1/tasks", json=CREATE_BODY)
        assert resp.status_code == 401

    def test_get_no_token_returns_401(self, client):
        resp = client.get("/api/v1/tasks/task-123")
        assert resp.status_code == 401

    def test_list_no_token_returns_401(self, client):
        resp = client.get("/api/v1/tasks")
        assert resp.status_code == 401

    def test_activate_no_token_returns_401(self, client):
        resp = client.post("/api/v1/tasks/task-123/activate")
        assert resp.status_code == 401

    def test_complete_no_token_returns_401(self, client):
        resp = client.post("/api/v1/tasks/task-123/complete")
        assert resp.status_code == 401

    def test_revoke_no_token_returns_401(self, client):
        resp = client.post("/api/v1/tasks/task-123/revoke")
        assert resp.status_code == 401

    def test_token_no_token_returns_401(self, client):
        resp = client.post("/api/v1/tasks/task-123/token")
        assert resp.status_code == 401

    def test_invalid_jwt_returns_401(self, client):
        resp = client.post(
            "/api/v1/tasks",
            json=CREATE_BODY,
            headers={"Authorization": "Bearer bad.jwt.token"},
        )
        assert resp.status_code == 401


# ─────────────────────────────────────────────────────────────────────────────
# Create Task Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestCreateTask:
    def test_create_success_returns_201(self, client, agent_token, mock_service):
        task_obj = _make_task_obj()
        mock_service.create_task.return_value = task_obj

        resp = client.post(
            "/api/v1/tasks",
            json=CREATE_BODY,
            headers=_auth_header(agent_token),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["task_id"] == "task-abc-123"
        assert data["agent_id"] == "agent-sdr-001"
        assert data["status"] == "pending"

    def test_create_passes_agent_identity(self, client, agent_token, mock_service):
        mock_service.create_task.return_value = _make_task_obj()

        client.post(
            "/api/v1/tasks",
            json=CREATE_BODY,
            headers=_auth_header(agent_token),
        )
        call_args = mock_service.create_task.call_args
        assert call_args.kwargs["agent_id"] == "agent-sdr-001"
        assert call_args.kwargs["initiated_by"] == "sarah@acme.com"
        assert call_args.kwargs["delegation_id"] == "deleg-001"

    def test_create_with_user_jwt(self, client, user_token, mock_service):
        mock_service.create_task.return_value = _make_task_obj(
            agent_id="sarah@acme.com"
        )

        resp = client.post(
            "/api/v1/tasks",
            json=CREATE_BODY,
            headers=_auth_header(user_token),
        )
        assert resp.status_code == 201
        call_args = mock_service.create_task.call_args
        assert call_args.kwargs["agent_id"] == "sarah@acme.com"
        assert call_args.kwargs["delegation_id"] is None
        assert call_args.kwargs["delegation_permissions"] is None

    def test_create_permission_exceeded_returns_403(
        self, client, agent_token, mock_service
    ):
        mock_service.create_task.side_effect = TaskPermissionError(
            "Permissions exceed delegation scope",
            invalid_permissions=["salesforce:leads:write"],
            allowed_permissions=["notion:pages:search"],
        )

        resp = client.post(
            "/api/v1/tasks",
            json={
                "name": "Bad task",
                "requested_permissions": [
                    {"permission_urn": "salesforce:leads:write"}
                ],
            },
            headers=_auth_header(agent_token),
        )
        assert resp.status_code == 403
        detail = resp.json()["detail"]
        assert "invalid_permissions" in detail
        assert "salesforce:leads:write" in detail["invalid_permissions"]
        assert "allowed_permissions" in detail

    def test_create_empty_permissions_returns_422(self, client, agent_token):
        resp = client.post(
            "/api/v1/tasks",
            json={"name": "Bad", "requested_permissions": []},
            headers=_auth_header(agent_token),
        )
        assert resp.status_code == 422


# ─────────────────────────────────────────────────────────────────────────────
# Get Task Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestGetTask:
    def test_get_success(self, client, user_token, mock_service):
        mock_service.get_task.return_value = _make_task_obj()

        resp = client.get(
            "/api/v1/tasks/task-abc-123",
            headers=_auth_header(user_token),
        )
        assert resp.status_code == 200
        assert resp.json()["task_id"] == "task-abc-123"

    def test_get_not_found_returns_404(self, client, user_token, mock_service):
        mock_service.get_task.side_effect = TaskNotFoundError(
            "Task not found: task-nope"
        )

        resp = client.get(
            "/api/v1/tasks/task-nope",
            headers=_auth_header(user_token),
        )
        assert resp.status_code == 404
        assert "task-nope" in resp.json()["detail"]


# ─────────────────────────────────────────────────────────────────────────────
# List Tasks Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestListTasks:
    def test_list_returns_tasks(self, client, user_token, mock_service):
        mock_service.list_tasks.return_value = [_make_task_obj(), _make_task_obj(id="task-xyz")]

        resp = client.get(
            "/api/v1/tasks",
            headers=_auth_header(user_token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert data["limit"] == 50
        assert data["offset"] == 0

    def test_list_with_status_filter(self, client, user_token, mock_service):
        mock_service.list_tasks.return_value = []

        resp = client.get(
            "/api/v1/tasks?status=active",
            headers=_auth_header(user_token),
        )
        assert resp.status_code == 200
        call_args = mock_service.list_tasks.call_args
        assert call_args.kwargs["status"] == "active"

    def test_list_with_pagination(self, client, user_token, mock_service):
        mock_service.list_tasks.return_value = []

        resp = client.get(
            "/api/v1/tasks?limit=10&offset=5",
            headers=_auth_header(user_token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["limit"] == 10
        assert data["offset"] == 5
        call_args = mock_service.list_tasks.call_args
        assert call_args.kwargs["limit"] == 10
        assert call_args.kwargs["offset"] == 5


# ─────────────────────────────────────────────────────────────────────────────
# Activate Task Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestActivateTask:
    def test_activate_success(self, client, user_token, mock_service):
        mock_service.activate_task.return_value = _make_task_obj(
            status="active", started_at=datetime.now(timezone.utc)
        )

        resp = client.post(
            "/api/v1/tasks/task-abc-123/activate",
            headers=_auth_header(user_token),
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "active"
        assert resp.json()["started_at"] is not None

    def test_activate_not_found_returns_404(self, client, user_token, mock_service):
        mock_service.activate_task.side_effect = TaskNotFoundError("Task not found: x")

        resp = client.post(
            "/api/v1/tasks/x/activate",
            headers=_auth_header(user_token),
        )
        assert resp.status_code == 404

    def test_activate_non_pending_returns_409(self, client, user_token, mock_service):
        mock_service.activate_task.side_effect = TaskLifecycleError(
            "Cannot activate task in 'active' status"
        )

        resp = client.post(
            "/api/v1/tasks/task-abc-123/activate",
            headers=_auth_header(user_token),
        )
        assert resp.status_code == 409
        assert "Cannot activate" in resp.json()["detail"]


# ─────────────────────────────────────────────────────────────────────────────
# Complete Task Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestCompleteTask:
    def test_complete_success(self, client, user_token, mock_service):
        mock_service.complete_task.return_value = _make_task_obj(
            status="completed", completed_at=datetime.now(timezone.utc)
        )

        resp = client.post(
            "/api/v1/tasks/task-abc-123/complete",
            headers=_auth_header(user_token),
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"
        assert resp.json()["completed_at"] is not None

    def test_complete_not_found_returns_404(self, client, user_token, mock_service):
        mock_service.complete_task.side_effect = TaskNotFoundError("nope")

        resp = client.post(
            "/api/v1/tasks/x/complete",
            headers=_auth_header(user_token),
        )
        assert resp.status_code == 404

    def test_complete_non_active_returns_409(self, client, user_token, mock_service):
        mock_service.complete_task.side_effect = TaskLifecycleError(
            "Cannot complete task in 'pending' status"
        )

        resp = client.post(
            "/api/v1/tasks/task-abc-123/complete",
            headers=_auth_header(user_token),
        )
        assert resp.status_code == 409


# ─────────────────────────────────────────────────────────────────────────────
# Revoke Task Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestRevokeTask:
    def test_revoke_success(self, client, user_token, mock_service):
        mock_service.revoke_task.return_value = _make_task_obj(status="revoked")

        resp = client.post(
            "/api/v1/tasks/task-abc-123/revoke",
            headers=_auth_header(user_token),
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "revoked"

    def test_revoke_not_found_returns_404(self, client, user_token, mock_service):
        mock_service.revoke_task.side_effect = TaskNotFoundError("nope")

        resp = client.post(
            "/api/v1/tasks/x/revoke",
            headers=_auth_header(user_token),
        )
        assert resp.status_code == 404

    def test_revoke_terminal_returns_409(self, client, user_token, mock_service):
        mock_service.revoke_task.side_effect = TaskLifecycleError(
            "Cannot revoke task in 'completed' status"
        )

        resp = client.post(
            "/api/v1/tasks/task-abc-123/revoke",
            headers=_auth_header(user_token),
        )
        assert resp.status_code == 409


# ─────────────────────────────────────────────────────────────────────────────
# Issue Task Token Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestIssueTaskToken:
    def test_issue_token_success(self, client, user_token, mock_service):
        from app.models.task_token import TaskTokenResponse

        mock_service.issue_task_token.return_value = TaskTokenResponse(
            task_id="task-abc-123",
            task_token="eyJhbGciOiJIUzI1NiJ9.test",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            scoped_permissions=["notion:pages:search"],
        )

        resp = client.post(
            "/api/v1/tasks/task-abc-123/token",
            headers=_auth_header(user_token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["task_id"] == "task-abc-123"
        assert data["task_token"].startswith("eyJ")
        assert "notion:pages:search" in data["scoped_permissions"]
        assert "expires_at" in data

    def test_issue_token_not_found_returns_404(self, client, user_token, mock_service):
        mock_service.issue_task_token.side_effect = TaskNotFoundError("nope")

        resp = client.post(
            "/api/v1/tasks/x/token",
            headers=_auth_header(user_token),
        )
        assert resp.status_code == 404

    def test_issue_token_not_active_returns_409(self, client, user_token, mock_service):
        mock_service.issue_task_token.side_effect = TaskLifecycleError(
            "Cannot issue token for task in 'pending' status"
        )

        resp = client.post(
            "/api/v1/tasks/task-abc-123/token",
            headers=_auth_header(user_token),
        )
        assert resp.status_code == 409
        assert "Cannot issue token" in resp.json()["detail"]


# ─────────────────────────────────────────────────────────────────────────────
# Error Response Detail Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestErrorResponseDetails:
    """Verify error responses contain expected structure without leaking internals."""

    def test_403_includes_permission_lists(self, client, agent_token, mock_service):
        mock_service.create_task.side_effect = TaskPermissionError(
            "exceeded",
            invalid_permissions=["bad:perm"],
            allowed_permissions=["good:perm"],
        )

        resp = client.post(
            "/api/v1/tasks",
            json=CREATE_BODY,
            headers=_auth_header(agent_token),
        )
        detail = resp.json()["detail"]
        assert detail["invalid_permissions"] == ["bad:perm"]
        assert detail["allowed_permissions"] == ["good:perm"]
        assert "message" in detail

    def test_404_includes_task_id(self, client, user_token, mock_service):
        mock_service.get_task.side_effect = TaskNotFoundError("Task not found: task-xyz")

        resp = client.get(
            "/api/v1/tasks/task-xyz",
            headers=_auth_header(user_token),
        )
        assert resp.status_code == 404
        assert "task-xyz" in resp.json()["detail"]

    def test_409_includes_lifecycle_message(self, client, user_token, mock_service):
        mock_service.activate_task.side_effect = TaskLifecycleError(
            "Cannot activate task in 'completed' status"
        )

        resp = client.post(
            "/api/v1/tasks/task-abc-123/activate",
            headers=_auth_header(user_token),
        )
        assert resp.status_code == 409
        assert "Cannot activate" in resp.json()["detail"]
