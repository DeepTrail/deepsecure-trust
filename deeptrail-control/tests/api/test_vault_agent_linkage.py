"""Tests for GET /vault/user-tokens/agent-linkage (Phase 4: OAuth ↔ Agent Linkage)."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app as fastapi_app
from app.api.deps import get_db, flexible_auth
from app.models.agent import Agent
from app.models.delegation import DelegationToken
from app.models.vault_token import VaultToken


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


def _make_vault_token(db, user_id, service_id):
    t = VaultToken(
        token_ref=f"vault://{_uid()}-{service_id}",
        user_id=user_id,
        service_id=service_id,
        encrypted_data=b"encrypted-placeholder",
    )
    db.add(t)
    db.commit()
    return t


def _make_delegation(db, agent_id, delegator, permissions, *, expired=False, revoked=False):
    now = datetime.now(timezone.utc)
    d = DelegationToken(
        agent_id=agent_id,
        delegator=delegator,
        delegated_permissions=permissions,
        expires_at=now - timedelta(hours=1) if expired else now + timedelta(days=7),
        revoked_at=now if revoked else None,
    )
    db.add(d)
    db.commit()
    return d


# --- 1. Returns linked agents for user's service ---

def test_returns_linked_agents(db):
    user = f"user-{_uid()}@test.com"
    client = _make_client(db, user)
    try:
        agent = _make_agent(db, name="My Agent")
        _make_vault_token(db, user, "notion")
        _make_delegation(db, agent.agent_id, user, ["notion:pages:read"])

        resp = client.get("/api/v1/vault/user-tokens/agent-linkage")
        assert resp.status_code == 200
        data = resp.json()
        assert "notion" in data["linkage"]
        agents = data["linkage"]["notion"]
        assert len(agents) == 1
        assert agents[0]["agent_id"] == agent.agent_id
        assert agents[0]["agent_name"] == "My Agent"
    finally:
        _cleanup()


# --- 2. Multiple agents per service ---

def test_multiple_agents_per_service(db):
    user = f"user-{_uid()}@test.com"
    client = _make_client(db, user)
    try:
        agent_a = _make_agent(db, name="Agent A")
        agent_b = _make_agent(db, name="Agent B")
        _make_vault_token(db, user, "notion")
        _make_delegation(db, agent_a.agent_id, user, ["notion:pages:read"])
        _make_delegation(db, agent_b.agent_id, user, ["notion:pages:write"])

        resp = client.get("/api/v1/vault/user-tokens/agent-linkage")
        agents = resp.json()["linkage"]["notion"]
        agent_ids = {a["agent_id"] for a in agents}
        assert agent_a.agent_id in agent_ids
        assert agent_b.agent_id in agent_ids
        assert len(agents) == 2
    finally:
        _cleanup()


# --- 3. Excludes expired delegations ---

def test_excludes_expired_delegations(db):
    user = f"user-{_uid()}@test.com"
    client = _make_client(db, user)
    try:
        agent = _make_agent(db, name="Expired Agent")
        _make_vault_token(db, user, "slack")
        _make_delegation(db, agent.agent_id, user, ["slack:channels:list"], expired=True)

        resp = client.get("/api/v1/vault/user-tokens/agent-linkage")
        assert resp.json()["linkage"]["slack"] == []
    finally:
        _cleanup()


# --- 4. Excludes revoked delegations ---

def test_excludes_revoked_delegations(db):
    user = f"user-{_uid()}@test.com"
    client = _make_client(db, user)
    try:
        agent = _make_agent(db, name="Revoked Agent")
        _make_vault_token(db, user, "github")
        _make_delegation(db, agent.agent_id, user, ["github:repos:read"], revoked=True)

        resp = client.get("/api/v1/vault/user-tokens/agent-linkage")
        assert resp.json()["linkage"]["github"] == []
    finally:
        _cleanup()


# --- 5. Excludes other users' delegations ---

def test_excludes_other_users_delegations(db):
    user_a = f"alice-{_uid()}@test.com"
    user_b = f"bob-{_uid()}@test.com"

    agent = _make_agent(db, name="Shared Agent")
    _make_vault_token(db, user_a, "notion")
    _make_delegation(db, agent.agent_id, user_b, ["notion:pages:read"])

    client_a = _make_client(db, user_a)
    try:
        resp = client_a.get("/api/v1/vault/user-tokens/agent-linkage")
        assert resp.json()["linkage"]["notion"] == []
    finally:
        _cleanup()


# --- 6. Empty when no vault tokens ---

def test_empty_when_no_vault_tokens(db):
    user = f"loner-{_uid()}@test.com"
    client = _make_client(db, user)
    try:
        resp = client.get("/api/v1/vault/user-tokens/agent-linkage")
        assert resp.status_code == 200
        assert resp.json()["linkage"] == {}
    finally:
        _cleanup()


# --- 7. Empty array when no matching delegations ---

def test_empty_array_when_no_matching_delegations(db):
    user = f"user-{_uid()}@test.com"
    client = _make_client(db, user)
    try:
        _make_vault_token(db, user, "notion")
        agent = _make_agent(db, name="GitHub Only Agent")
        _make_delegation(db, agent.agent_id, user, ["github:repos:read"])

        resp = client.get("/api/v1/vault/user-tokens/agent-linkage")
        assert resp.json()["linkage"]["notion"] == []
    finally:
        _cleanup()


# --- 8. Agent name resolution ---

def test_agent_name_resolution(db):
    user = f"user-{_uid()}@test.com"
    client = _make_client(db, user)
    try:
        agent = _make_agent(db, name="Debugging Agent")
        _make_vault_token(db, user, "slack")
        _make_delegation(db, agent.agent_id, user, ["slack:messages:send"])

        resp = client.get("/api/v1/vault/user-tokens/agent-linkage")
        agents = resp.json()["linkage"]["slack"]
        assert len(agents) == 1
        assert agents[0]["agent_name"] == "Debugging Agent"
    finally:
        _cleanup()
