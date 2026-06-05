"""Tests for GET /vault/agent-sessions (Phase 3: Vault Tab Clarification)."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app as fastapi_app
from app.api.deps import get_db, flexible_auth
from app.models.agent import Agent
from app.models.agent_session import AgentSession
from app.models.delegation import DelegationToken


def _uid():
    return uuid.uuid4().hex[:12]


def _jwt_override(user_email: str):
    def _override():
        return {"auth_type": "jwt", "claims": {"sub": user_email}}
    return _override


def _make_client(db: Session, user_email: str) -> TestClient:
    def _override_db():
        yield db

    fastapi_app.dependency_overrides[get_db] = _override_db
    fastapi_app.dependency_overrides[flexible_auth] = _jwt_override(user_email)
    return TestClient(fastapi_app)


def _cleanup():
    fastapi_app.dependency_overrides.pop(get_db, None)
    fastapi_app.dependency_overrides.pop(flexible_auth, None)


def _make_agent(db, agent_id=None, name="Test Agent"):
    aid = agent_id or f"agent-{_uid()}"
    a = Agent(agent_id=aid, name=name, public_key=uuid.uuid4().bytes + uuid.uuid4().bytes)
    db.add(a)
    db.commit()
    return a


def _make_delegation(db, agent_id, delegator, permissions=None):
    d = DelegationToken(
        agent_id=agent_id,
        delegator=delegator,
        delegated_permissions=permissions or ["notion:pages:read"],
    )
    db.add(d)
    db.commit()
    return d


def _make_session(db, agent_id, delegation_id, owner_email, *, active=True, minutes_ago=0, perms=None):
    now = datetime.now(timezone.utc)
    s = AgentSession(
        agent_id=agent_id,
        delegation_id=delegation_id,
        owner_email=owner_email,
        scoped_permissions=perms or ["notion:pages:read"],
        is_active=active,
        created_at=now - timedelta(minutes=minutes_ago),
        expires_at=now + timedelta(hours=8) if active else now - timedelta(hours=1),
        last_activity_at=now - timedelta(minutes=max(0, minutes_ago - 5)),
    )
    db.add(s)
    db.commit()
    return s


# --- 1. Returns sessions for user's delegated agents ---

def test_returns_user_sessions(db):
    user = f"user-{_uid()}@test.com"
    client = _make_client(db, user)
    try:
        agent = _make_agent(db, name="My Agent")
        deleg = _make_delegation(db, agent.agent_id, user)
        _make_session(db, agent.agent_id, deleg.id, user)

        resp = client.get("/api/v1/vault/agent-sessions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        s = data["sessions"][0]
        assert s["agent_id"] == agent.agent_id
        assert s["agent_name"] == "My Agent"
        assert s["delegation_id"] == deleg.id
        assert s["status"] in ("active", "expired")
        assert s["permissions_count"] == 1
        assert s["created_at"] is not None
        assert s["expires_at"] is not None
    finally:
        _cleanup()


# --- 2. Excludes other users' sessions ---

def test_excludes_other_user_sessions(db):
    user_a = f"alice-{_uid()}@test.com"
    user_b = f"bob-{_uid()}@test.com"

    agent = _make_agent(db, name="Shared Agent")
    deleg_a = _make_delegation(db, agent.agent_id, user_a, ["notion:pages:read", "slack:channels:list"])
    deleg_b = _make_delegation(db, agent.agent_id, user_b, ["github:repos:read"])
    _make_session(db, agent.agent_id, deleg_a.id, user_a, perms=["notion:pages:read", "slack:channels:list"])
    _make_session(db, agent.agent_id, deleg_b.id, user_b, perms=["github:repos:read"])

    client_a = _make_client(db, user_a)
    try:
        resp_a = client_a.get("/api/v1/vault/agent-sessions")
        data_a = resp_a.json()
        assert data_a["total"] == 1
        assert data_a["sessions"][0]["permissions_count"] == 2
    finally:
        _cleanup()

    client_b = _make_client(db, user_b)
    try:
        resp_b = client_b.get("/api/v1/vault/agent-sessions")
        data_b = resp_b.json()
        assert data_b["total"] == 1
        assert data_b["sessions"][0]["permissions_count"] == 1
    finally:
        _cleanup()


# --- 3. Includes agent name ---

def test_includes_agent_name(db):
    user = f"user-{_uid()}@test.com"
    client = _make_client(db, user)
    try:
        agent = _make_agent(db, name="Debugging Agent")
        deleg = _make_delegation(db, agent.agent_id, user)
        _make_session(db, agent.agent_id, deleg.id, user)

        resp = client.get("/api/v1/vault/agent-sessions")
        s = resp.json()["sessions"][0]
        assert s["agent_name"] == "Debugging Agent"
    finally:
        _cleanup()


# --- 4. Status computation ---

def test_status_active_and_expired(db):
    user = f"user-{_uid()}@test.com"
    client = _make_client(db, user)
    try:
        agent = _make_agent(db, name="Status Agent")
        deleg = _make_delegation(db, agent.agent_id, user)
        _make_session(db, agent.agent_id, deleg.id, user, active=True)
        _make_session(db, agent.agent_id, deleg.id, user, active=False, minutes_ago=120)

        resp = client.get("/api/v1/vault/agent-sessions")
        data = resp.json()
        assert data["total"] == 2
        statuses = {s["status"] for s in data["sessions"]}
        assert "active" in statuses
        assert "expired" in statuses
    finally:
        _cleanup()


# --- 5. Permissions count ---

def test_permissions_count(db):
    user = f"user-{_uid()}@test.com"
    client = _make_client(db, user)
    try:
        agent = _make_agent(db, name="Perms Agent")
        deleg = _make_delegation(db, agent.agent_id, user, ["n:p:r", "s:c:l", "g:r:r"])
        _make_session(db, agent.agent_id, deleg.id, user, perms=["n:p:r", "s:c:l", "g:r:r"])

        resp = client.get("/api/v1/vault/agent-sessions")
        s = resp.json()["sessions"][0]
        assert s["permissions_count"] == 3
    finally:
        _cleanup()


# --- 6. Empty response ---

def test_empty_when_no_delegations(db):
    user = f"loner-{_uid()}@test.com"
    client = _make_client(db, user)
    try:
        resp = client.get("/api/v1/vault/agent-sessions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["sessions"] == []
        assert data["total"] == 0
    finally:
        _cleanup()


# --- 7. Pagination ---

def test_pagination(db):
    user = f"user-{_uid()}@test.com"
    client = _make_client(db, user)
    try:
        agent = _make_agent(db, name="Paging Agent")
        deleg = _make_delegation(db, agent.agent_id, user)
        for i in range(5):
            _make_session(db, agent.agent_id, deleg.id, user, minutes_ago=i * 10)

        resp = client.get("/api/v1/vault/agent-sessions?limit=2&offset=0")
        data = resp.json()
        assert data["total"] == 5
        assert len(data["sessions"]) == 2

        resp2 = client.get("/api/v1/vault/agent-sessions?limit=2&offset=2")
        data2 = resp2.json()
        assert data2["total"] == 5
        assert len(data2["sessions"]) == 2
    finally:
        _cleanup()


# --- 8. Ordering (most recent first) ---

def test_ordering_most_recent_first(db):
    user = f"user-{_uid()}@test.com"
    client = _make_client(db, user)
    try:
        agent = _make_agent(db, name="Order Agent")
        deleg = _make_delegation(db, agent.agent_id, user)
        _make_session(db, agent.agent_id, deleg.id, user, minutes_ago=60)
        _make_session(db, agent.agent_id, deleg.id, user, minutes_ago=5)
        _make_session(db, agent.agent_id, deleg.id, user, minutes_ago=30)

        resp = client.get("/api/v1/vault/agent-sessions")
        sessions = resp.json()["sessions"]
        assert len(sessions) == 3
        activities = [s["last_activity_at"] for s in sessions]
        assert activities == sorted(activities, reverse=True)
    finally:
        _cleanup()
