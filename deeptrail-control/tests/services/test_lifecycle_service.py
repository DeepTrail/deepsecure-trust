"""Unit tests for LifecycleService.

Tests the four-state lifecycle model (registered → delegated → authenticated → active)
using the SQLite test database from conftest.
"""

import pytest
from datetime import datetime, timedelta, timezone

from app.models.agent_session import AgentSession, PartyType
from app.models.delegation import DelegationToken
from app.services.lifecycle_service import (
    ACTIVE,
    AUTHENTICATED,
    DELEGATED,
    LifecycleService,
    REGISTERED,
)


AGENT_ID = "agent-lifecycle-test"
AGENT_ID_2 = "agent-lifecycle-test-2"
DELEGATOR = "test@acme.com"


def _make_delegation(db, agent_id, *, expired=False, revoked=False):
    """Helper to create a DelegationToken row."""
    now = datetime.now(timezone.utc)
    d = DelegationToken(
        agent_id=agent_id,
        delegator=DELEGATOR,
        delegated_permissions=["notion:pages:read"],
        expires_at=now - timedelta(hours=1) if expired else now + timedelta(days=7),
        revoked_at=now if revoked else None,
    )
    db.add(d)
    db.commit()
    db.refresh(d)
    return d


def _make_session(db, agent_id, delegation_id, *, active=True, last_activity_hours_ago=None, source_ip=None):
    """Helper to create an AgentSession row."""
    now = datetime.now(timezone.utc)
    s = AgentSession(
        agent_id=agent_id,
        delegation_id=delegation_id,
        party_type=PartyType.FIRST_PARTY,
        scoped_permissions=["notion:pages:read"],
        owner_email=DELEGATOR,
        is_active=active,
        expires_at=now + timedelta(hours=8),
        source_ip=source_ip,
    )
    if last_activity_hours_ago is not None:
        s.last_activity_at = now - timedelta(hours=last_activity_hours_ago)
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


class TestComputeState:
    """Tests for LifecycleService.compute_state."""

    def test_registered_no_delegation_no_session(self, db):
        svc = LifecycleService(db)
        assert svc.compute_state("nonexistent-agent") == REGISTERED

    def test_delegated_with_active_delegation(self, db):
        _make_delegation(db, AGENT_ID)
        svc = LifecycleService(db)
        assert svc.compute_state(AGENT_ID) == DELEGATED

    def test_registered_with_expired_delegation(self, db):
        _make_delegation(db, "agent-expired-del", expired=True)
        svc = LifecycleService(db)
        assert svc.compute_state("agent-expired-del") == REGISTERED

    def test_registered_with_revoked_delegation(self, db):
        _make_delegation(db, "agent-revoked-del", revoked=True)
        svc = LifecycleService(db)
        assert svc.compute_state("agent-revoked-del") == REGISTERED

    def test_authenticated_with_session(self, db):
        d = _make_delegation(db, "agent-authed")
        _make_session(db, "agent-authed", d.id, last_activity_hours_ago=48)
        svc = LifecycleService(db)
        assert svc.compute_state("agent-authed") == AUTHENTICATED

    def test_active_with_recent_session(self, db):
        d = _make_delegation(db, "agent-active")
        _make_session(db, "agent-active", d.id, last_activity_hours_ago=1)
        svc = LifecycleService(db)
        assert svc.compute_state("agent-active") == ACTIVE

    def test_authenticated_inactive_session(self, db):
        d = _make_delegation(db, "agent-inactive-sess")
        _make_session(db, "agent-inactive-sess", d.id, active=False, last_activity_hours_ago=1)
        svc = LifecycleService(db)
        assert svc.compute_state("agent-inactive-sess") == AUTHENTICATED


class TestComputeStateBulk:
    """Tests for LifecycleService.compute_state_bulk."""

    def test_empty_list(self, db):
        svc = LifecycleService(db)
        assert svc.compute_state_bulk([]) == {}

    def test_mixed_states(self, db):
        d = _make_delegation(db, "bulk-delegated")
        d2 = _make_delegation(db, "bulk-active")
        _make_session(db, "bulk-active", d2.id, last_activity_hours_ago=0.5)

        svc = LifecycleService(db)
        result = svc.compute_state_bulk(["bulk-delegated", "bulk-active", "bulk-unknown"])
        assert result["bulk-delegated"] == DELEGATED
        assert result["bulk-active"] == ACTIVE
        assert result["bulk-unknown"] == REGISTERED


class TestAccessorMethods:
    """Tests for get_last_authenticated_at, get_last_active_at, get_session_count, get_delegation_count."""

    def test_no_sessions_returns_none(self, db):
        svc = LifecycleService(db)
        assert svc.get_last_authenticated_at("no-sessions") is None
        assert svc.get_last_active_at("no-sessions") is None

    def test_session_count_zero(self, db):
        svc = LifecycleService(db)
        assert svc.get_session_count("no-sessions") == 0

    def test_delegation_count_zero(self, db):
        svc = LifecycleService(db)
        assert svc.get_delegation_count("no-delegations") == 0

    def test_session_count_positive(self, db):
        d = _make_delegation(db, "count-agent")
        _make_session(db, "count-agent", d.id)
        _make_session(db, "count-agent", d.id, active=False)
        svc = LifecycleService(db)
        assert svc.get_session_count("count-agent") == 2

    def test_delegation_count_excludes_expired(self, db):
        _make_delegation(db, "del-count-agent")
        _make_delegation(db, "del-count-agent", expired=True)
        _make_delegation(db, "del-count-agent", revoked=True)
        svc = LifecycleService(db)
        assert svc.get_delegation_count("del-count-agent") == 1

    def test_last_authenticated_at_returns_most_recent(self, db):
        d = _make_delegation(db, "auth-at-agent")
        _make_session(db, "auth-at-agent", d.id)
        svc = LifecycleService(db)
        result = svc.get_last_authenticated_at("auth-at-agent")
        assert result is not None

    def test_source_ip_stored(self, db):
        d = _make_delegation(db, "ip-agent")
        s = _make_session(db, "ip-agent", d.id, source_ip="192.168.1.1")
        assert s.source_ip == "192.168.1.1"

    def test_get_last_active_at_returns_most_recent(self, db):
        d = _make_delegation(db, "active-at-agent")
        _make_session(db, "active-at-agent", d.id, last_activity_hours_ago=2)
        _make_session(db, "active-at-agent", d.id, last_activity_hours_ago=0.5)
        svc = LifecycleService(db)
        result = svc.get_last_active_at("active-at-agent")
        assert result is not None
        now = datetime.now(timezone.utc)
        result_aware = result if result.tzinfo else result.replace(tzinfo=timezone.utc)
        age = now - result_aware
        assert age < timedelta(hours=1)


class TestTransitionEdgeCases:
    """Edge cases for lifecycle state transitions."""

    def test_revoked_delegation_with_session_is_authenticated(self, db):
        """Agent was delegated, then delegation revoked, but session exists."""
        d = _make_delegation(db, "edge-revoked-del-with-sess", revoked=True)
        _make_session(db, "edge-revoked-del-with-sess", d.id, last_activity_hours_ago=48)
        svc = LifecycleService(db)
        assert svc.compute_state("edge-revoked-del-with-sess") == AUTHENTICATED

    def test_expired_delegation_with_active_session_is_active(self, db):
        """Delegation expired but active session still within 24h window."""
        d = _make_delegation(db, "edge-expired-del-active-sess", expired=True)
        _make_session(db, "edge-expired-del-active-sess", d.id, last_activity_hours_ago=1)
        svc = LifecycleService(db)
        assert svc.compute_state("edge-expired-del-active-sess") == ACTIVE

    def test_multiple_delegations_one_valid(self, db):
        """Multiple delegations, only one is valid — should be delegated."""
        _make_delegation(db, "edge-multi-del", expired=True)
        _make_delegation(db, "edge-multi-del", revoked=True)
        _make_delegation(db, "edge-multi-del")
        svc = LifecycleService(db)
        assert svc.compute_state("edge-multi-del") == DELEGATED

    def test_session_at_exactly_24h_boundary(self, db):
        """Session with last_activity_at at exactly 24h ago — should NOT be active."""
        d = _make_delegation(db, "edge-24h-boundary")
        _make_session(db, "edge-24h-boundary", d.id, last_activity_hours_ago=24.01)
        svc = LifecycleService(db)
        assert svc.compute_state("edge-24h-boundary") == AUTHENTICATED

    def test_source_ip_ipv6(self, db):
        d = _make_delegation(db, "ipv6-agent")
        s = _make_session(db, "ipv6-agent", d.id, source_ip="2001:db8::1")
        assert s.source_ip == "2001:db8::1"

    def test_source_ip_none_by_default(self, db):
        d = _make_delegation(db, "no-ip-agent")
        s = _make_session(db, "no-ip-agent", d.id)
        assert s.source_ip is None


class TestBulkQueryEfficiency:
    """Verify bulk queries return correct results for various sizes."""

    def test_bulk_single_agent(self, db):
        d = _make_delegation(db, "bulk-single")
        svc = LifecycleService(db)
        result = svc.compute_state_bulk(["bulk-single"])
        assert result == {"bulk-single": DELEGATED}

    def test_bulk_all_four_states(self, db):
        """Each agent in a different state."""
        _make_delegation(db, "bulk4-delegated")
        d2 = _make_delegation(db, "bulk4-authed")
        _make_session(db, "bulk4-authed", d2.id, last_activity_hours_ago=48)
        d3 = _make_delegation(db, "bulk4-active")
        _make_session(db, "bulk4-active", d3.id, last_activity_hours_ago=0.5)

        svc = LifecycleService(db)
        result = svc.compute_state_bulk([
            "bulk4-registered", "bulk4-delegated", "bulk4-authed", "bulk4-active"
        ])
        assert result["bulk4-registered"] == REGISTERED
        assert result["bulk4-delegated"] == DELEGATED
        assert result["bulk4-authed"] == AUTHENTICATED
        assert result["bulk4-active"] == ACTIVE
        assert len(result) == 4
