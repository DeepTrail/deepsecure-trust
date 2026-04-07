"""Unit tests for Task Token (Layer 4) and ScopedPermission models."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.models.task_token import (
    ScopedPermission,
    ScopedPermissionRequest,
    Task,
    TaskCreate,
    TaskResponse,
    TaskStatus,
    TaskTokenResponse,
    generate_scoped_permission_id,
    generate_task_id,
)


# ============================================================================
# ID Generation
# ============================================================================


class TestIdGeneration:
    def test_generate_task_id_format(self):
        tid = generate_task_id()
        assert tid.startswith("task-")
        assert len(tid) > 10

    def test_generate_task_id_uniqueness(self):
        ids = [generate_task_id() for _ in range(100)]
        assert len(set(ids)) == 100

    def test_generate_task_id_contains_uuid(self):
        tid = generate_task_id()
        uuid_part = tid.replace("task-", "")
        uuid.UUID(uuid_part)

    def test_generate_scoped_permission_id_format(self):
        sp_id = generate_scoped_permission_id()
        assert sp_id.startswith("sp-")
        assert len(sp_id) > 5

    def test_generate_scoped_permission_id_uniqueness(self):
        ids = [generate_scoped_permission_id() for _ in range(100)]
        assert len(set(ids)) == 100

    def test_generate_scoped_permission_id_contains_uuid(self):
        sp_id = generate_scoped_permission_id()
        uuid_part = sp_id.replace("sp-", "")
        uuid.UUID(uuid_part)


# ============================================================================
# TaskStatus
# ============================================================================


class TestTaskStatus:
    def test_status_values(self):
        assert TaskStatus.PENDING == "pending"
        assert TaskStatus.ACTIVE == "active"
        assert TaskStatus.COMPLETED == "completed"
        assert TaskStatus.REVOKED == "revoked"
        assert TaskStatus.TIMED_OUT == "timed_out"

    def test_terminal_states(self):
        assert TaskStatus.TERMINAL == {"completed", "revoked", "timed_out"}

    def test_active_states(self):
        assert TaskStatus.ACTIVE_STATES == {"pending", "active"}


# ============================================================================
# Task Model
# ============================================================================


class TestTaskModel:
    def _make_task(self, **overrides):
        defaults = {
            "agent_id": "agent-sdr-001",
            "initiated_by": "sarah@acme.com",
            "scoped_permissions": [
                {"urn": "hubspot:contacts:read", "constraints": {"id": "12345"}}
            ],
        }
        defaults.update(overrides)
        return Task(**defaults)

    def test_create_with_defaults(self):
        task = self._make_task()
        assert task.status == TaskStatus.PENDING
        assert task.auto_revoke_on_complete is True
        assert task.scoped_permissions is not None
        assert len(task.scoped_permissions) == 1
        assert task.constraints == {}
        assert task.usage_summary == {}
        assert task.id.startswith("task-")
        assert task.created_at is not None

    def test_tablename(self):
        assert Task.__tablename__ == "tasks"

    def test_agent_id_required(self):
        task = self._make_task()
        assert task.agent_id == "agent-sdr-001"

    def test_initiated_by_required(self):
        task = self._make_task()
        assert task.initiated_by == "sarah@acme.com"

    def test_optional_fields(self):
        task = self._make_task(
            name="Research lead 12345",
            description="Look up contact details",
            delegation_id="del-abc123",
        )
        assert task.name == "Research lead 12345"
        assert task.description == "Look up contact details"
        assert task.delegation_id == "del-abc123"

    # --- Hybrid properties ---

    def test_is_active_when_active(self):
        task = self._make_task(status=TaskStatus.ACTIVE)
        assert task.is_active is True

    def test_is_active_when_pending(self):
        task = self._make_task(status=TaskStatus.PENDING)
        assert task.is_active is False

    def test_is_terminal_completed(self):
        task = self._make_task(status=TaskStatus.COMPLETED)
        assert task.is_terminal is True

    def test_is_terminal_revoked(self):
        task = self._make_task(status=TaskStatus.REVOKED)
        assert task.is_terminal is True

    def test_is_terminal_timed_out(self):
        task = self._make_task(status=TaskStatus.TIMED_OUT)
        assert task.is_terminal is True

    def test_is_terminal_pending(self):
        task = self._make_task(status=TaskStatus.PENDING)
        assert task.is_terminal is False

    def test_is_terminal_active(self):
        task = self._make_task(status=TaskStatus.ACTIVE)
        assert task.is_terminal is False

    def test_is_past_deadline_with_past_deadline(self):
        task = self._make_task(
            deadline=datetime.now(timezone.utc) - timedelta(hours=1)
        )
        assert task.is_past_deadline is True

    def test_is_past_deadline_with_future_deadline(self):
        task = self._make_task(
            deadline=datetime.now(timezone.utc) + timedelta(hours=1)
        )
        assert task.is_past_deadline is False

    def test_is_past_deadline_no_deadline(self):
        task = self._make_task(deadline=None)
        assert task.is_past_deadline is False

    def test_is_past_deadline_naive_datetime(self):
        """Naive datetimes should be treated as UTC."""
        task = self._make_task(
            deadline=datetime.now() - timedelta(hours=1)
        )
        assert task.is_past_deadline is True

    # --- Lifecycle methods ---

    def test_activate_from_pending(self):
        task = self._make_task()
        task.activate()
        assert task.status == TaskStatus.ACTIVE
        assert task.started_at is not None

    def test_cannot_activate_active_task(self):
        task = self._make_task(status=TaskStatus.ACTIVE)
        with pytest.raises(ValueError, match="Cannot activate"):
            task.activate()

    def test_cannot_activate_completed_task(self):
        task = self._make_task(status=TaskStatus.COMPLETED)
        with pytest.raises(ValueError, match="Cannot activate"):
            task.activate()

    def test_complete_from_active(self):
        task = self._make_task(status=TaskStatus.ACTIVE)
        task.scoped_permission_records = []
        task.complete()
        assert task.status == TaskStatus.COMPLETED
        assert task.completed_at is not None

    def test_cannot_complete_pending_task(self):
        task = self._make_task(status=TaskStatus.PENDING)
        with pytest.raises(ValueError, match="Cannot complete"):
            task.complete()

    def test_cannot_complete_revoked_task(self):
        task = self._make_task(status=TaskStatus.REVOKED)
        with pytest.raises(ValueError, match="Cannot complete"):
            task.complete()

    def test_auto_revoke_on_complete(self):
        task = self._make_task(
            status=TaskStatus.ACTIVE,
            auto_revoke_on_complete=True,
        )
        sp = ScopedPermission(
            task_id="task-001",
            permission_urn="hubspot:contacts:read",
            valid_until=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        task.scoped_permission_records = [sp]
        task.complete()
        assert task.status == TaskStatus.COMPLETED
        assert sp.revoked is True

    def test_no_auto_revoke_when_disabled(self):
        task = self._make_task(
            status=TaskStatus.ACTIVE,
            auto_revoke_on_complete=False,
        )
        sp = ScopedPermission(
            task_id="task-001",
            permission_urn="hubspot:contacts:read",
            valid_until=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        task.scoped_permission_records = [sp]
        task.complete()
        assert task.status == TaskStatus.COMPLETED
        assert sp.revoked is False

    def test_revoke_from_pending(self):
        task = self._make_task(status=TaskStatus.PENDING)
        sp = ScopedPermission(
            task_id="task-001",
            permission_urn="test:perm",
            valid_until=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        task.scoped_permission_records = [sp]
        task.revoke()
        assert task.status == TaskStatus.REVOKED
        assert task.completed_at is not None
        assert sp.revoked is True

    def test_revoke_from_active(self):
        task = self._make_task(status=TaskStatus.ACTIVE)
        task.scoped_permission_records = []
        task.revoke()
        assert task.status == TaskStatus.REVOKED

    def test_cannot_revoke_completed_task(self):
        task = self._make_task(status=TaskStatus.COMPLETED)
        with pytest.raises(ValueError, match="Cannot revoke"):
            task.revoke()

    def test_cannot_revoke_already_revoked(self):
        task = self._make_task(status=TaskStatus.REVOKED)
        with pytest.raises(ValueError, match="Cannot revoke"):
            task.revoke()

    def test_timeout_from_active(self):
        task = self._make_task(status=TaskStatus.ACTIVE)
        sp = ScopedPermission(
            task_id="task-001",
            permission_urn="test:perm",
            valid_until=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        task.scoped_permission_records = [sp]
        task.timeout()
        assert task.status == TaskStatus.TIMED_OUT
        assert task.completed_at is not None
        assert sp.revoked is True

    def test_timeout_from_pending(self):
        task = self._make_task(status=TaskStatus.PENDING)
        task.scoped_permission_records = []
        task.timeout()
        assert task.status == TaskStatus.TIMED_OUT

    def test_timeout_idempotent_on_completed(self):
        task = self._make_task(status=TaskStatus.COMPLETED)
        task.timeout()
        assert task.status == TaskStatus.COMPLETED

    def test_timeout_idempotent_on_revoked(self):
        task = self._make_task(status=TaskStatus.REVOKED)
        task.timeout()
        assert task.status == TaskStatus.REVOKED

    def test_timeout_idempotent_on_timed_out(self):
        task = self._make_task(status=TaskStatus.TIMED_OUT)
        task.timeout()
        assert task.status == TaskStatus.TIMED_OUT

    # --- Permission methods ---

    def test_has_scoped_permission_found(self):
        task = self._make_task(
            scoped_permissions=[
                {"urn": "hubspot:contacts:read"},
                {"urn": "notion:pages:search"},
            ]
        )
        assert task.has_scoped_permission("hubspot:contacts:read") is True

    def test_has_scoped_permission_not_found(self):
        task = self._make_task(
            scoped_permissions=[{"urn": "hubspot:contacts:read"}]
        )
        assert task.has_scoped_permission("slack:messages:send") is False

    def test_has_scoped_permission_empty_list(self):
        task = self._make_task(scoped_permissions=[])
        assert task.has_scoped_permission("any:perm") is False

    def test_has_scoped_permission_none(self):
        task = self._make_task(scoped_permissions=None)
        assert task.has_scoped_permission("any:perm") is False

    def test_get_active_permission_urns(self):
        task = self._make_task(status=TaskStatus.ACTIVE)
        sp_active = ScopedPermission(
            task_id="task-001",
            permission_urn="hubspot:contacts:read",
            valid_until=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        sp_revoked = ScopedPermission(
            task_id="task-001",
            permission_urn="notion:pages:search",
            valid_until=datetime.now(timezone.utc) + timedelta(hours=1),
            revoked=True,
        )
        sp_expired = ScopedPermission(
            task_id="task-001",
            permission_urn="slack:messages:send",
            valid_until=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        task.scoped_permission_records = [sp_active, sp_revoked, sp_expired]
        urns = task.get_active_permission_urns()
        assert urns == ["hubspot:contacts:read"]

    # --- JWT serialization ---

    def test_to_token_claims(self):
        task = self._make_task(
            id="task-test-123",
            auto_revoke_on_complete=True,
            created_at=datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
            deadline=datetime(2026, 1, 15, 13, 0, 0, tzinfo=timezone.utc),
        )
        claims = task.to_token_claims()
        assert claims["task_id"] == "task-test-123"
        assert claims["agent_id"] == "agent-sdr-001"
        assert len(claims["scoped_permissions"]) == 1
        assert claims["auto_revoke_on_complete"] is True
        assert claims["deadline"] == "2026-01-15T13:00:00+00:00"
        assert isinstance(claims["iat"], int)

    def test_to_token_claims_no_deadline(self):
        task = self._make_task(
            id="task-no-dl",
            deadline=None,
            created_at=datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
        )
        claims = task.to_token_claims()
        assert claims["deadline"] is None

    def test_to_token_claims_no_created_at(self):
        task = self._make_task(id="task-no-ca", created_at=None)
        claims = task.to_token_claims()
        assert claims["iat"] is None

    # --- __repr__ ---

    def test_repr(self):
        task = self._make_task(id="task-repr-test")
        r = repr(task)
        assert "task-repr-test" in r
        assert "agent-sdr-001" in r


# ============================================================================
# ScopedPermission Model
# ============================================================================


class TestScopedPermission:
    def _make_sp(self, **overrides):
        defaults = {
            "task_id": "task-001",
            "permission_urn": "hubspot:contacts:read",
            "valid_until": datetime.now(timezone.utc) + timedelta(hours=1),
        }
        defaults.update(overrides)
        return ScopedPermission(**defaults)

    def test_create_with_defaults(self):
        sp = self._make_sp()
        assert sp.usage_count == 0
        assert sp.max_usage is None
        assert sp.revoked is False

    def test_tablename(self):
        assert ScopedPermission.__tablename__ == "scoped_permissions"

    # --- Hybrid properties ---

    def test_is_usable_when_valid(self):
        sp = self._make_sp()
        assert sp.is_usable is True

    def test_not_usable_when_revoked(self):
        sp = self._make_sp(revoked=True)
        assert sp.is_usable is False

    def test_not_usable_when_expired(self):
        sp = self._make_sp(
            valid_until=datetime.now(timezone.utc) - timedelta(hours=1)
        )
        assert sp.is_usable is False

    def test_not_usable_when_exhausted(self):
        sp = self._make_sp(max_usage=5, usage_count=5)
        assert sp.is_usable is False

    def test_is_expired_true(self):
        sp = self._make_sp(
            valid_until=datetime.now(timezone.utc) - timedelta(hours=1)
        )
        assert sp.is_expired is True

    def test_is_expired_false(self):
        sp = self._make_sp(
            valid_until=datetime.now(timezone.utc) + timedelta(hours=1)
        )
        assert sp.is_expired is False

    def test_is_exhausted_true(self):
        sp = self._make_sp(max_usage=3, usage_count=3)
        assert sp.is_exhausted is True

    def test_is_exhausted_false(self):
        sp = self._make_sp(max_usage=3, usage_count=1)
        assert sp.is_exhausted is False

    def test_is_exhausted_unlimited(self):
        sp = self._make_sp(max_usage=None, usage_count=999)
        assert sp.is_exhausted is False

    def test_is_expired_naive_datetime(self):
        """Naive datetimes should be treated as UTC."""
        sp = self._make_sp(
            valid_until=datetime.now() - timedelta(hours=1)
        )
        assert sp.is_expired is True

    # --- increment_usage ---

    def test_increment_usage_success(self):
        sp = self._make_sp(max_usage=5, usage_count=0)
        result = sp.increment_usage()
        assert result is True
        assert sp.usage_count == 1

    def test_increment_usage_unlimited(self):
        sp = self._make_sp(max_usage=None, usage_count=100)
        result = sp.increment_usage()
        assert result is True
        assert sp.usage_count == 101

    def test_increment_usage_at_max(self):
        sp = self._make_sp(max_usage=1, usage_count=1)
        result = sp.increment_usage()
        assert result is False
        assert sp.usage_count == 1  # Unchanged

    def test_increment_usage_revoked(self):
        sp = self._make_sp(revoked=True)
        result = sp.increment_usage()
        assert result is False

    def test_increment_usage_expired(self):
        sp = self._make_sp(
            valid_until=datetime.now(timezone.utc) - timedelta(hours=1)
        )
        result = sp.increment_usage()
        assert result is False

    def test_increment_multiple_times(self):
        sp = self._make_sp(max_usage=3, usage_count=0)
        assert sp.increment_usage() is True
        assert sp.increment_usage() is True
        assert sp.increment_usage() is True
        assert sp.increment_usage() is False
        assert sp.usage_count == 3

    # --- __repr__ ---

    def test_repr_usable(self):
        sp = self._make_sp()
        r = repr(sp)
        assert "hubspot:contacts:read" in r
        assert "usable" in r

    def test_repr_unusable(self):
        sp = self._make_sp(revoked=True)
        r = repr(sp)
        assert "unusable" in r


# ============================================================================
# Pydantic Schemas
# ============================================================================


class TestScopedPermissionRequest:
    def test_valid(self):
        spr = ScopedPermissionRequest(
            permission_urn="hubspot:contacts:read",
            constraints={"id": "12345"},
            max_usage=10,
        )
        assert spr.permission_urn == "hubspot:contacts:read"
        assert spr.constraints == {"id": "12345"}
        assert spr.max_usage == 10

    def test_defaults(self):
        spr = ScopedPermissionRequest(permission_urn="test:perm")
        assert spr.constraints == {}
        assert spr.max_usage is None

    def test_requires_permission_urn(self):
        with pytest.raises(Exception):
            ScopedPermissionRequest()


class TestTaskCreate:
    def test_valid_minimal(self):
        tc = TaskCreate(
            requested_permissions=[
                ScopedPermissionRequest(permission_urn="test:perm")
            ]
        )
        assert len(tc.requested_permissions) == 1
        assert tc.name is None
        assert tc.deadline_minutes is None
        assert tc.auto_revoke_on_complete is True

    def test_valid_full(self):
        tc = TaskCreate(
            name="Research lead 12345",
            description="Look up contact details",
            requested_permissions=[
                ScopedPermissionRequest(
                    permission_urn="hubspot:contacts:read",
                    constraints={"id": "12345"},
                    max_usage=10,
                )
            ],
            deadline_minutes=60,
            auto_revoke_on_complete=True,
        )
        assert tc.name == "Research lead 12345"
        assert tc.deadline_minutes == 60

    def test_rejects_empty_permissions(self):
        with pytest.raises(Exception):
            TaskCreate(
                name="bad task",
                requested_permissions=[],
            )

    def test_deadline_min_value(self):
        with pytest.raises(Exception):
            TaskCreate(
                requested_permissions=[
                    ScopedPermissionRequest(permission_urn="test:perm")
                ],
                deadline_minutes=0,
            )

    def test_deadline_max_value(self):
        with pytest.raises(Exception):
            TaskCreate(
                requested_permissions=[
                    ScopedPermissionRequest(permission_urn="test:perm")
                ],
                deadline_minutes=1441,
            )

    def test_deadline_boundary_valid_1(self):
        tc = TaskCreate(
            requested_permissions=[
                ScopedPermissionRequest(permission_urn="test:perm")
            ],
            deadline_minutes=1,
        )
        assert tc.deadline_minutes == 1

    def test_deadline_boundary_valid_1440(self):
        tc = TaskCreate(
            requested_permissions=[
                ScopedPermissionRequest(permission_urn="test:perm")
            ],
            deadline_minutes=1440,
        )
        assert tc.deadline_minutes == 1440


class TestTaskResponse:
    def test_from_attributes(self):
        assert TaskResponse.model_config.get("from_attributes") is True

    def test_construct(self):
        tr = TaskResponse(
            task_id="task-001",
            agent_id="agent-001",
            name="Test Task",
            status="active",
            scoped_permissions=[{"urn": "test:perm"}],
            deadline=datetime(2026, 1, 15, 13, 0, 0, tzinfo=timezone.utc),
            auto_revoke_on_complete=True,
            created_at=datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
            started_at=datetime(2026, 1, 15, 12, 1, 0, tzinfo=timezone.utc),
            completed_at=None,
        )
        assert tr.task_id == "task-001"
        assert tr.status == "active"

    def test_optional_fields_default_none(self):
        tr = TaskResponse(
            task_id="task-001",
            agent_id="agent-001",
            status="pending",
            scoped_permissions=[],
            auto_revoke_on_complete=True,
            created_at=datetime.now(timezone.utc),
        )
        assert tr.name is None
        assert tr.deadline is None
        assert tr.started_at is None
        assert tr.completed_at is None


class TestTaskTokenResponse:
    def test_construct(self):
        ttr = TaskTokenResponse(
            task_id="task-001",
            task_token="eyJhbGciOiJIUzI1NiJ9...",
            expires_at=datetime(2026, 1, 15, 13, 0, 0, tzinfo=timezone.utc),
            scoped_permissions=["hubspot:contacts:read"],
        )
        assert ttr.task_id == "task-001"
        assert len(ttr.scoped_permissions) == 1
