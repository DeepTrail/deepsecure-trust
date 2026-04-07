"""Tests for TaskService (WS-K7).

Covers:
- create_task: happy path, permission subset check, no delegation check,
  deadline computation, ScopedPermission record creation
- get_task: found, not found, wrong agent
- list_tasks: by agent, by status, pagination
- activate_task: pending → active, non-pending error
- complete_task: active → completed, auto-revoke, non-active error
- revoke_task: force revoke, terminal error
- issue_task_token: valid JWT, non-active error, deadline-bounded exp,
  default TTL, claims correctness
- check_deadline_timeouts: past-deadline, terminal skipped
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import jwt as pyjwt
import pytest

from app.models.task_token import (
    ScopedPermission,
    ScopedPermissionRequest,
    Task,
    TaskCreate,
    TaskStatus,
)
from app.services.task_service import (
    TaskLifecycleError,
    TaskNotFoundError,
    TaskPermissionError,
    TaskService,
    TaskServiceError,
)

JWT_SECRET = "test-secret-key-for-unit-tests"


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_db():
    """Mock SQLAlchemy Session."""
    db = MagicMock()
    db.add = MagicMock()
    db.commit = MagicMock()
    db.refresh = MagicMock()
    return db


@pytest.fixture
def service(mock_db):
    return TaskService(db=mock_db, jwt_secret=JWT_SECRET)


def _make_task_data(
    name="Research lead",
    permissions=None,
    deadline_minutes=None,
    auto_revoke=True,
):
    perms = permissions or [
        ScopedPermissionRequest(
            permission_urn="hubspot:contacts:read",
            constraints={"id": "12345"},
        )
    ]
    return TaskCreate(
        name=name,
        requested_permissions=perms,
        deadline_minutes=deadline_minutes,
        auto_revoke_on_complete=auto_revoke,
    )


def _make_active_task(task_id="task-test-123", agent_id="agent-001", deadline=None):
    task = Task(
        id=task_id,
        agent_id=agent_id,
        initiated_by="user@test.com",
        status=TaskStatus.ACTIVE,
        scoped_permissions=[{"urn": "hubspot:contacts:read"}],
        auto_revoke_on_complete=True,
        deadline=deadline,
    )
    sp = ScopedPermission(
        task_id=task_id,
        permission_urn="hubspot:contacts:read",
        valid_until=datetime.now(timezone.utc) + timedelta(hours=2),
    )
    task.scoped_permission_records = [sp]
    return task


# ─────────────────────────────────────────────────────────────────────────────
# Error Hierarchy
# ─────────────────────────────────────────────────────────────────────────────


class TestErrorHierarchy:
    def test_base_error(self):
        assert issubclass(TaskServiceError, Exception)

    def test_not_found_inherits(self):
        assert issubclass(TaskNotFoundError, TaskServiceError)

    def test_permission_error_inherits(self):
        assert issubclass(TaskPermissionError, TaskServiceError)

    def test_lifecycle_error_inherits(self):
        assert issubclass(TaskLifecycleError, TaskServiceError)

    def test_permission_error_attributes(self):
        err = TaskPermissionError(
            "test",
            invalid_permissions=["a:b:c"],
            allowed_permissions=["x:y:z"],
        )
        assert err.invalid_permissions == ["a:b:c"]
        assert err.allowed_permissions == ["x:y:z"]


# ─────────────────────────────────────────────────────────────────────────────
# create_task
# ─────────────────────────────────────────────────────────────────────────────


class TestCreateTask:
    def test_create_happy_path(self, service, mock_db):
        task_data = _make_task_data()
        task = service.create_task(
            agent_id="agent-sdr-001",
            initiated_by="sarah@acme.com",
            task_data=task_data,
            delegation_permissions=["hubspot:contacts:read", "hubspot:contacts:write"],
        )
        assert task.status == TaskStatus.PENDING
        assert task.agent_id == "agent-sdr-001"
        assert task.initiated_by == "sarah@acme.com"
        assert len(task.scoped_permission_records) == 1
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()

    def test_create_permission_exceeded(self, service):
        task_data = _make_task_data(
            permissions=[ScopedPermissionRequest(permission_urn="slack:messages:send")]
        )
        with pytest.raises(TaskPermissionError) as exc_info:
            service.create_task(
                agent_id="agent-001",
                initiated_by="user@test.com",
                task_data=task_data,
                delegation_permissions=["hubspot:contacts:read"],
            )
        assert "slack:messages:send" in exc_info.value.invalid_permissions
        assert "hubspot:contacts:read" in exc_info.value.allowed_permissions

    def test_create_no_delegation_check(self, service, mock_db):
        task_data = _make_task_data(
            permissions=[ScopedPermissionRequest(permission_urn="anything:goes:here")]
        )
        task = service.create_task(
            agent_id="agent-001",
            initiated_by="user@test.com",
            task_data=task_data,
            delegation_permissions=None,
        )
        assert task.status == TaskStatus.PENDING
        mock_db.add.assert_called_once()

    def test_create_with_deadline(self, service, mock_db):
        task_data = _make_task_data(deadline_minutes=60)
        task = service.create_task(
            agent_id="agent-001",
            initiated_by="user@test.com",
            task_data=task_data,
        )
        assert task.deadline is not None
        expected = datetime.now(timezone.utc) + timedelta(minutes=60)
        assert abs((task.deadline - expected).total_seconds()) < 5

    def test_create_generates_scoped_permission_records(self, service, mock_db):
        task_data = _make_task_data(
            permissions=[
                ScopedPermissionRequest(permission_urn="hubspot:contacts:read"),
                ScopedPermissionRequest(permission_urn="hubspot:contacts:write", max_usage=10),
            ]
        )
        task = service.create_task(
            agent_id="agent-001",
            initiated_by="user@test.com",
            task_data=task_data,
        )
        assert len(task.scoped_permission_records) == 2
        urns = {sp.permission_urn for sp in task.scoped_permission_records}
        assert urns == {"hubspot:contacts:read", "hubspot:contacts:write"}

    def test_create_scoped_permission_max_usage(self, service, mock_db):
        task_data = _make_task_data(
            permissions=[
                ScopedPermissionRequest(permission_urn="hubspot:contacts:read", max_usage=5),
            ]
        )
        task = service.create_task(
            agent_id="agent-001",
            initiated_by="user@test.com",
            task_data=task_data,
        )
        assert task.scoped_permission_records[0].max_usage == 5

    def test_create_with_delegation_id(self, service, mock_db):
        task_data = _make_task_data()
        task = service.create_task(
            agent_id="agent-001",
            initiated_by="user@test.com",
            task_data=task_data,
            delegation_id="del-abc-123",
        )
        assert task.delegation_id == "del-abc-123"


# ─────────────────────────────────────────────────────────────────────────────
# get_task
# ─────────────────────────────────────────────────────────────────────────────


class TestGetTask:
    def test_get_task_found(self, service, mock_db):
        expected_task = Task(id="task-001", agent_id="agent-001", initiated_by="u@t.com")
        mock_db.query.return_value.filter.return_value.first.return_value = expected_task
        result = service.get_task("task-001")
        assert result.id == "task-001"

    def test_get_task_not_found(self, service, mock_db):
        mock_db.query.return_value.filter.return_value.first.return_value = None
        with pytest.raises(TaskNotFoundError, match="Task not found"):
            service.get_task("nonexistent")

    def test_get_task_wrong_agent(self, service, mock_db):
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = None
        with pytest.raises(TaskNotFoundError):
            service.get_task("task-001", agent_id="wrong-agent")


# ─────────────────────────────────────────────────────────────────────────────
# list_tasks
# ─────────────────────────────────────────────────────────────────────────────


class TestListTasks:
    def test_list_by_agent(self, service, mock_db):
        tasks = [Task(id="t1", agent_id="a1", initiated_by="u@t.com")]
        mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.offset.return_value.all.return_value = tasks
        result = service.list_tasks("a1")
        assert len(result) == 1

    def test_list_by_status(self, service, mock_db):
        tasks = [Task(id="t1", agent_id="a1", initiated_by="u@t.com", status=TaskStatus.ACTIVE)]
        mock_db.query.return_value.filter.return_value.filter.return_value.order_by.return_value.limit.return_value.offset.return_value.all.return_value = tasks
        result = service.list_tasks("a1", status=TaskStatus.ACTIVE)
        assert len(result) == 1

    def test_list_pagination(self, service, mock_db):
        mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.offset.return_value.all.return_value = []
        result = service.list_tasks("a1", limit=10, offset=20)
        assert result == []


# ─────────────────────────────────────────────────────────────────────────────
# activate_task
# ─────────────────────────────────────────────────────────────────────────────


class TestActivateTask:
    def test_activate_pending(self, service, mock_db):
        task = Task(id="task-001", agent_id="agent-001", initiated_by="u@t.com", status=TaskStatus.PENDING)
        mock_db.query.return_value.filter.return_value.first.return_value = task

        result = service.activate_task("task-001")
        assert result.status == TaskStatus.ACTIVE
        assert result.started_at is not None
        mock_db.commit.assert_called_once()

    def test_activate_non_pending_raises(self, service, mock_db):
        task = Task(id="task-001", agent_id="agent-001", initiated_by="u@t.com", status=TaskStatus.ACTIVE)
        mock_db.query.return_value.filter.return_value.first.return_value = task

        with pytest.raises(TaskLifecycleError, match="must be PENDING"):
            service.activate_task("task-001")

    def test_activate_completed_raises(self, service, mock_db):
        task = Task(id="task-001", agent_id="agent-001", initiated_by="u@t.com", status=TaskStatus.COMPLETED)
        mock_db.query.return_value.filter.return_value.first.return_value = task

        with pytest.raises(TaskLifecycleError):
            service.activate_task("task-001")


# ─────────────────────────────────────────────────────────────────────────────
# complete_task
# ─────────────────────────────────────────────────────────────────────────────


class TestCompleteTask:
    def test_complete_active(self, service, mock_db):
        task = _make_active_task()
        mock_db.query.return_value.filter.return_value.first.return_value = task

        result = service.complete_task("task-test-123")
        assert result.status == TaskStatus.COMPLETED
        assert result.completed_at is not None
        mock_db.commit.assert_called_once()

    def test_complete_auto_revokes(self, service, mock_db):
        task = _make_active_task()
        task.auto_revoke_on_complete = True
        mock_db.query.return_value.filter.return_value.first.return_value = task

        service.complete_task("task-test-123")
        for sp in task.scoped_permission_records:
            assert sp.revoked is True

    def test_complete_no_auto_revoke(self, service, mock_db):
        task = _make_active_task()
        task.auto_revoke_on_complete = False
        mock_db.query.return_value.filter.return_value.first.return_value = task

        service.complete_task("task-test-123")
        assert task.status == TaskStatus.COMPLETED
        for sp in task.scoped_permission_records:
            assert sp.revoked is False

    def test_complete_non_active_raises(self, service, mock_db):
        task = Task(id="task-001", agent_id="agent-001", initiated_by="u@t.com", status=TaskStatus.PENDING)
        mock_db.query.return_value.filter.return_value.first.return_value = task

        with pytest.raises(TaskLifecycleError, match="must be ACTIVE"):
            service.complete_task("task-001")


# ─────────────────────────────────────────────────────────────────────────────
# revoke_task
# ─────────────────────────────────────────────────────────────────────────────


class TestRevokeTask:
    def test_revoke_active(self, service, mock_db):
        task = _make_active_task()
        mock_db.query.return_value.filter.return_value.first.return_value = task

        result = service.revoke_task("task-test-123")
        assert result.status == TaskStatus.REVOKED
        for sp in task.scoped_permission_records:
            assert sp.revoked is True
        mock_db.commit.assert_called_once()

    def test_revoke_pending(self, service, mock_db):
        task = Task(id="task-001", agent_id="agent-001", initiated_by="u@t.com", status=TaskStatus.PENDING)
        task.scoped_permission_records = []
        mock_db.query.return_value.filter.return_value.first.return_value = task

        result = service.revoke_task("task-001")
        assert result.status == TaskStatus.REVOKED

    def test_revoke_terminal_raises(self, service, mock_db):
        task = Task(id="task-001", agent_id="agent-001", initiated_by="u@t.com", status=TaskStatus.COMPLETED)
        mock_db.query.return_value.filter.return_value.first.return_value = task

        with pytest.raises(TaskLifecycleError, match="already terminal"):
            service.revoke_task("task-001")

    def test_revoke_timed_out_raises(self, service, mock_db):
        task = Task(id="task-001", agent_id="agent-001", initiated_by="u@t.com", status=TaskStatus.TIMED_OUT)
        mock_db.query.return_value.filter.return_value.first.return_value = task

        with pytest.raises(TaskLifecycleError):
            service.revoke_task("task-001")


# ─────────────────────────────────────────────────────────────────────────────
# issue_task_token
# ─────────────────────────────────────────────────────────────────────────────


class TestIssueTaskToken:
    def test_issue_token_active_task(self, service, mock_db):
        task = _make_active_task()
        mock_db.query.return_value.filter.return_value.first.return_value = task

        result = service.issue_task_token("task-test-123")
        assert result.task_id == "task-test-123"
        assert result.task_token is not None
        assert result.expires_at is not None

    def test_issue_token_jwt_claims(self, service, mock_db):
        task = _make_active_task()
        mock_db.query.return_value.filter.return_value.first.return_value = task

        result = service.issue_task_token("task-test-123")
        decoded = pyjwt.decode(
            result.task_token,
            JWT_SECRET,
            algorithms=["HS256"],
            audience="deepsecure-gateway",
        )
        assert decoded["task_id"] == "task-test-123"
        assert decoded["agent_id"] == "agent-001"
        assert decoded["token_type"] == "task_token"
        assert decoded["iss"] == "deepsecure-control"
        assert decoded["aud"] == "deepsecure-gateway"
        assert "exp" in decoded
        assert "scoped_permissions" in decoded

    def test_issue_token_non_active_raises(self, service, mock_db):
        task = Task(id="task-001", agent_id="agent-001", initiated_by="u@t.com", status=TaskStatus.PENDING)
        mock_db.query.return_value.filter.return_value.first.return_value = task

        with pytest.raises(TaskLifecycleError, match="must be ACTIVE"):
            service.issue_task_token("task-001")

    def test_issue_token_completed_raises(self, service, mock_db):
        task = Task(id="task-001", agent_id="agent-001", initiated_by="u@t.com", status=TaskStatus.COMPLETED)
        mock_db.query.return_value.filter.return_value.first.return_value = task

        with pytest.raises(TaskLifecycleError):
            service.issue_task_token("task-001")

    def test_issue_token_respects_deadline(self, service, mock_db):
        deadline = datetime.now(timezone.utc) + timedelta(minutes=15)
        task = _make_active_task(deadline=deadline)
        mock_db.query.return_value.filter.return_value.first.return_value = task

        result = service.issue_task_token("task-test-123")
        assert abs((result.expires_at - deadline).total_seconds()) < 5

    def test_issue_token_default_ttl_no_deadline(self, service, mock_db):
        task = _make_active_task(deadline=None)
        mock_db.query.return_value.filter.return_value.first.return_value = task

        result = service.issue_task_token("task-test-123")
        expected = datetime.now(timezone.utc) + timedelta(hours=1)
        assert abs((result.expires_at - expected).total_seconds()) < 5

    def test_issue_token_deadline_far_uses_default_ttl(self, service, mock_db):
        deadline = datetime.now(timezone.utc) + timedelta(hours=24)
        task = _make_active_task(deadline=deadline)
        mock_db.query.return_value.filter.return_value.first.return_value = task

        result = service.issue_task_token("task-test-123")
        expected_default = datetime.now(timezone.utc) + timedelta(hours=1)
        assert abs((result.expires_at - expected_default).total_seconds()) < 5

    def test_issue_token_scoped_permissions(self, service, mock_db):
        task = _make_active_task()
        mock_db.query.return_value.filter.return_value.first.return_value = task

        result = service.issue_task_token("task-test-123")
        assert "hubspot:contacts:read" in result.scoped_permissions


# ─────────────────────────────────────────────────────────────────────────────
# check_deadline_timeouts
# ─────────────────────────────────────────────────────────────────────────────


class TestCheckDeadlineTimeouts:
    def test_timeout_past_deadline(self, service, mock_db):
        past = datetime.now(timezone.utc) - timedelta(minutes=10)
        task = Task(
            id="task-001",
            agent_id="agent-001",
            initiated_by="u@t.com",
            status=TaskStatus.ACTIVE,
            deadline=past,
        )
        task.scoped_permission_records = []
        mock_db.query.return_value.filter.return_value.all.return_value = [task]

        count = service.check_deadline_timeouts()
        assert count == 1
        assert task.status == TaskStatus.TIMED_OUT
        mock_db.commit.assert_called_once()

    def test_timeout_skips_terminal(self, service, mock_db):
        mock_db.query.return_value.filter.return_value.all.return_value = []
        count = service.check_deadline_timeouts()
        assert count == 0

    def test_timeout_multiple_tasks(self, service, mock_db):
        past = datetime.now(timezone.utc) - timedelta(minutes=5)
        t1 = Task(id="t1", agent_id="a1", initiated_by="u@t.com", status=TaskStatus.ACTIVE, deadline=past)
        t2 = Task(id="t2", agent_id="a2", initiated_by="u@t.com", status=TaskStatus.PENDING, deadline=past)
        t1.scoped_permission_records = []
        t2.scoped_permission_records = []
        mock_db.query.return_value.filter.return_value.all.return_value = [t1, t2]

        count = service.check_deadline_timeouts()
        assert count == 2
        assert t1.status == TaskStatus.TIMED_OUT
        assert t2.status == TaskStatus.TIMED_OUT

    def test_no_commit_when_zero_timeouts(self, service, mock_db):
        mock_db.query.return_value.filter.return_value.all.return_value = []
        service.check_deadline_timeouts()
        mock_db.commit.assert_not_called()


# ─────────────────────────────────────────────────────────────────────────────
# Permission Validation
# ─────────────────────────────────────────────────────────────────────────────


class TestPermissionValidation:
    def test_exact_match_passes(self, service):
        service._validate_permissions_subset(
            ["hubspot:contacts:read"],
            ["hubspot:contacts:read"],
        )

    def test_subset_passes(self, service):
        service._validate_permissions_subset(
            ["hubspot:contacts:read"],
            ["hubspot:contacts:read", "hubspot:contacts:write"],
        )

    def test_superset_fails(self, service):
        with pytest.raises(TaskPermissionError) as exc_info:
            service._validate_permissions_subset(
                ["hubspot:contacts:read", "slack:messages:send"],
                ["hubspot:contacts:read"],
            )
        assert "slack:messages:send" in exc_info.value.invalid_permissions

    def test_disjoint_fails(self, service):
        with pytest.raises(TaskPermissionError) as exc_info:
            service._validate_permissions_subset(
                ["notion:pages:read"],
                ["hubspot:contacts:read"],
            )
        assert "notion:pages:read" in exc_info.value.invalid_permissions

    def test_empty_requested_passes(self, service):
        service._validate_permissions_subset([], ["hubspot:contacts:read"])

    def test_empty_allowed_fails(self, service):
        with pytest.raises(TaskPermissionError):
            service._validate_permissions_subset(["hubspot:contacts:read"], [])


# ─────────────────────────────────────────────────────────────────────────────
# Constructor / Integration
# ─────────────────────────────────────────────────────────────────────────────


class TestConstructor:
    def test_constructor(self, mock_db):
        svc = TaskService(db=mock_db, jwt_secret="s3cret")
        assert svc._db is mock_db
        assert svc._jwt_secret == "s3cret"

    def test_import_path(self):
        from app.services.task_service import TaskService as TS
        assert TS is not None
