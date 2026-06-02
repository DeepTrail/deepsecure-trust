"""Tests for admin fleet, delegation template, and emergency endpoints (WS-D1→D5)."""

import pytest
from fastapi.testclient import TestClient

from app.main import app as fastapi_app
from app.api.deps import get_db
from app.middleware.admin_auth import require_admin
from app.models.agent import Agent
from app.models.agent_session import AgentSession
from app.models.delegation import DelegationToken
from app.models.delegation_template import DelegationTemplate


@pytest.fixture()
def client(db):
    def _override_db():
        yield db

    def _override_admin():
        return {"sub": "admin@test.com", "roles": ["admin"]}

    fastapi_app.dependency_overrides[get_db] = _override_db
    fastapi_app.dependency_overrides[require_admin] = _override_admin
    yield TestClient(fastapi_app)
    fastapi_app.dependency_overrides.clear()


import uuid as _uuid


def _create_agent(db, agent_id="test-agent", name="Test Agent"):
    unique_key = _uuid.uuid4().bytes + _uuid.uuid4().bytes  # 32 unique bytes
    agent = Agent(agent_id=agent_id, name=name, public_key=unique_key)
    db.add(agent)
    db.commit()
    return agent


def _create_delegation(db, agent_id="test-agent", delegator="user@test.com"):
    d = DelegationToken(
        agent_id=agent_id,
        delegator=delegator,
        delegated_permissions=["notion:pages:read"],
    )
    db.add(d)
    db.commit()
    return d


# --- D1: Fleet API ---


def test_list_agents(client, db):
    _create_agent(db, "fleet-a1", "Agent 1")
    _create_agent(db, "fleet-a2", "Agent 2")
    resp = client.get("/api/v1/admin/agents")
    assert resp.status_code == 200
    data = resp.json()
    agent_ids = [a["agent_id"] for a in data["agents"]]
    assert "fleet-a1" in agent_ids
    assert "fleet-a2" in agent_ids
    assert data["total"] == len(data["agents"])


# --- D2: Suspend Agent ---


def test_suspend_agent(client, db):
    _create_agent(db, "susp-agent")
    d = _create_delegation(db, "susp-agent")
    session = AgentSession(agent_id="susp-agent", delegation_id=d.id, owner_email="user@test.com")
    db.add(session)
    db.commit()

    resp = client.post("/api/v1/admin/agents/susp-agent/suspend")
    assert resp.status_code == 200
    data = resp.json()
    assert data["action"] == "suspend_agent"
    assert data["affected_count"] >= 1


# --- D3: Delegation Templates ---


def test_create_template(client):
    resp = client.post("/api/v1/admin/delegation-templates", json={
        "agent_id": "tmpl-agent",
        "max_permissions": ["notion:pages:read", "notion:pages:write"],
        "blocked_permissions": ["notion:admin:*"],
        "default_ttl_days": 14,
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["agent_id"] == "tmpl-agent"
    assert len(data["max_permissions"]) == 2


def test_list_templates(client):
    client.post("/api/v1/admin/delegation-templates", json={
        "agent_id": "list-t1", "max_permissions": ["a:b:c"],
    })
    resp = client.get("/api/v1/admin/delegation-templates")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["templates"]) >= 1


def test_update_template(client):
    create_resp = client.post("/api/v1/admin/delegation-templates", json={
        "agent_id": "upd-tmpl", "max_permissions": ["a:b:c"],
    })
    tid = create_resp.json()["id"]
    resp = client.patch(f"/api/v1/admin/delegation-templates/{tid}", json={
        "default_ttl_days": 30,
    })
    assert resp.status_code == 200
    assert resp.json()["default_ttl_days"] == 30


def test_delete_template(client):
    create_resp = client.post("/api/v1/admin/delegation-templates", json={
        "agent_id": "del-tmpl", "max_permissions": ["a:b:c"],
    })
    tid = create_resp.json()["id"]
    resp = client.delete(f"/api/v1/admin/delegation-templates/{tid}")
    assert resp.status_code == 204


# --- D4: Delegation Management ---


def test_list_delegations(client, db):
    _create_agent(db, "del-agent")
    _create_delegation(db, "del-agent", "alice@test.com")
    _create_delegation(db, "del-agent", "bob@test.com")
    resp = client.get("/api/v1/admin/delegations")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["delegations"]) >= 2


def test_create_delegation_admin(client, db):
    _create_agent(db, "adm-del-agent")
    resp = client.post("/api/v1/admin/delegations", json={
        "agent_id": "adm-del-agent",
        "delegator": "carol@test.com",
        "delegated_permissions": ["slack:messages:read"],
    })
    assert resp.status_code == 201
    assert resp.json()["source"] == "admin"


def test_revoke_delegation_admin(client, db):
    _create_agent(db, "rev-agent")
    d = _create_delegation(db, "rev-agent", "dave@test.com")
    resp = client.delete(f"/api/v1/admin/delegations/{d.id}")
    assert resp.status_code == 204


# --- D5: Emergency ---


def test_emergency_suspend_all(client, db):
    _create_agent(db, "em-e1")
    d = _create_delegation(db, "em-e1")
    s = AgentSession(agent_id="em-e1", delegation_id=d.id, owner_email="u@t.com")
    db.add(s)
    db.commit()
    resp = client.post("/api/v1/admin/emergency/suspend-all")
    assert resp.status_code == 200
    assert resp.json()["action"] == "suspend_all"


def test_emergency_disable_delegations(client, db):
    _create_agent(db, "em-e2")
    _create_delegation(db, "em-e2")
    resp = client.post("/api/v1/admin/emergency/disable-delegations")
    assert resp.status_code == 200
    assert resp.json()["action"] == "disable_delegations"


def test_emergency_lockdown(client, db):
    _create_agent(db, "em-e3")
    d = _create_delegation(db, "em-e3")
    s = AgentSession(agent_id="em-e3", delegation_id=d.id, owner_email="u@t.com")
    db.add(s)
    db.commit()
    resp = client.post("/api/v1/admin/emergency/lockdown")
    assert resp.status_code == 200
    assert resp.json()["action"] == "lockdown"
