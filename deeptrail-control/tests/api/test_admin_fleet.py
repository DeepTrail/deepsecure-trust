"""Tests for admin fleet, delegation template, and emergency endpoints (WS-D1→D5)."""

import pytest
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient

from app.main import app as fastapi_app
from app.api.deps import get_db
from app.middleware.admin_auth import require_admin
from app.models.agent import Agent
from app.models.agent_session import AgentSession
from app.models.audit_event import AuditEvent
from app.models.connected_service import ConnectedService
from app.models.delegation import DelegationToken
from app.models.delegation_template import DelegationTemplate
from app.models.user_session import UserSession
from app.models.task_token import Task, TaskStatus


@pytest.fixture()
def client(db):
    def _override_db():
        yield db

    def _override_admin():
        return {"sub": "admin@test.com", "roles": ["admin"]}

    fastapi_app.dependency_overrides[get_db] = _override_db
    fastapi_app.dependency_overrides[require_admin] = _override_admin
    yield TestClient(fastapi_app)
    fastapi_app.dependency_overrides.pop(get_db, None)
    fastapi_app.dependency_overrides.pop(require_admin, None)


import uuid as _uuid


def _create_agent(db, agent_id="test-agent", name="Test Agent", platform=None, selector=None):
    unique_key = _uuid.uuid4().bytes + _uuid.uuid4().bytes
    agent = Agent(agent_id=agent_id, name=name, public_key=unique_key, platform=platform, selector=selector)
    db.add(agent)
    db.commit()
    return agent


def _create_delegation(db, agent_id="test-agent", delegator="user@test.com", permissions=None):
    d = DelegationToken(
        agent_id=agent_id,
        delegator=delegator,
        delegated_permissions=permissions or ["notion:pages:read"],
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


# --- P1: Fleet Enrichment ---


def test_fleet_platform_selector_auth_method(client, db):
    """Test platform, selector, and auth_method appear in fleet response."""
    _create_agent(db, "plat-agent", "Platform Agent", platform="gcp", selector="sa@proj.iam.gserviceaccount.com")
    resp = client.get("/api/v1/admin/agents")
    assert resp.status_code == 200
    agents = resp.json()["agents"]
    agent = next(a for a in agents if a["agent_id"] == "plat-agent")
    assert agent["platform"] == "gcp"
    assert agent["selector"] == "sa@proj.iam.gserviceaccount.com"
    assert agent["auth_method"] == "workload_identity"


def test_fleet_ed25519_auth_method(client, db):
    """Agent without platform should have auth_method=ed25519."""
    _create_agent(db, "ed-agent", "Ed25519 Agent")
    resp = client.get("/api/v1/admin/agents")
    agents = resp.json()["agents"]
    agent = next(a for a in agents if a["agent_id"] == "ed-agent")
    assert agent["auth_method"] == "ed25519"
    assert agent["platform"] is None


def test_fleet_delegators_with_connected_services(client, db):
    """Test delegators[] includes connected_services from ConnectedService table."""
    _create_agent(db, "del-svc-agent")
    _create_delegation(db, "del-svc-agent", "alice@test.com", ["notion:pages:read", "slack:messages:list"])

    cs = ConnectedService(
        user_id="alice@test.com",
        service_id="notion",
        service_name="Notion",
        oauth_token_ref="vault://alice-notion-test",
        scopes_granted=["read_content", "search"],
    )
    db.add(cs)
    db.commit()

    resp = client.get("/api/v1/admin/agents")
    agents = resp.json()["agents"]
    agent = next(a for a in agents if a["agent_id"] == "del-svc-agent")

    assert len(agent["delegators"]) == 1
    delegator = agent["delegators"][0]
    assert delegator["email"] == "alice@test.com"
    assert delegator["delegation_count"] == 1
    assert len(delegator["connected_services"]) == 1
    svc = delegator["connected_services"][0]
    assert svc["service_id"] == "notion"
    assert svc["display_name"] == "Notion"
    assert svc["status"] == "connected"
    assert "read_content" in svc["scopes_granted"]


def test_fleet_enriched_sessions(client, db):
    """Test sessions include delegator, delegation_id, tool_calls, status."""
    _create_agent(db, "sess-agent")
    d = _create_delegation(db, "sess-agent", "bob@test.com")
    s = AgentSession(agent_id="sess-agent", delegation_id=d.id, owner_email="bob@test.com")
    db.add(s)
    db.commit()

    evt = AuditEvent(
        event_type="mcp_tool_call",
        agent_id="sess-agent",
        on_behalf_of="bob@test.com",
        agent_session_id=s.id,
        tool="notion.search_pages",
        success=True,
    )
    db.add(evt)
    db.commit()

    resp = client.get("/api/v1/admin/agents")
    agents = resp.json()["agents"]
    agent = next(a for a in agents if a["agent_id"] == "sess-agent")

    assert len(agent["sessions"]) >= 1
    session = next(sess for sess in agent["sessions"] if sess["session_id"] == s.id)
    assert session["delegator"] == "bob@test.com"
    assert session["delegation_id"] == d.id
    assert session["tool_calls"] == 1
    assert session["status"] == "active"


def test_fleet_delegation_services(client, db):
    """Test services[] on delegations are extracted from permission prefixes."""
    _create_agent(db, "svc-del-agent")
    _create_delegation(
        db, "svc-del-agent", "carol@test.com",
        ["notion:pages:read", "slack:messages:list", "github:repos:read"],
    )

    resp = client.get("/api/v1/admin/agents")
    agents = resp.json()["agents"]
    agent = next(a for a in agents if a["agent_id"] == "svc-del-agent")

    delegation = agent["delegations"][0]
    assert sorted(delegation["services"]) == ["github", "notion", "slack"]


def test_session_events_endpoint(client, db):
    """Test GET /agents/{id}/sessions/{sid}/events returns tool call events."""
    _create_agent(db, "evt-agent")
    d = _create_delegation(db, "evt-agent")
    s = AgentSession(agent_id="evt-agent", delegation_id=d.id, owner_email="user@test.com")
    db.add(s)
    db.commit()

    for i in range(3):
        db.add(AuditEvent(
            event_type="mcp_tool_call",
            agent_id="evt-agent",
            on_behalf_of="user@test.com",
            agent_session_id=s.id,
            tool=f"notion.tool_{i}",
            success=True,
            result_summary=f"Result {i}",
        ))
    db.commit()

    resp = client.get(f"/api/v1/admin/agents/evt-agent/sessions/{s.id}/events")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3
    assert len(data["events"]) == 3
    assert data["events"][0]["tool"] == "notion.tool_0"
    assert data["events"][0]["event_type"] == "mcp_tool_call"
    assert data["events"][0]["success"] is True


def test_session_events_empty(client, db):
    """Test session events for non-existent session returns empty, not 404."""
    _create_agent(db, "empty-evt-agent")

    resp = client.get("/api/v1/admin/agents/empty-evt-agent/sessions/nonexistent/events")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["events"] == []


# --- P2: Identity Stack ---


def test_identity_stack_returns_5_layers(client, db):
    """Response has exactly 5 layers in order."""
    _create_agent(db, "is-5layer")
    resp = client.get("/api/v1/admin/agents/is-5layer/identity-stack")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["layers"]) == 5
    types = [l["type"] for l in data["layers"]]
    assert types == ["User ID-Token", "User Session", "Delegation", "Agent Session", "Task Token"]


def test_identity_stack_user_id_token_always_empty(client, db):
    """User ID-Token layer is always count=0, items=[], with description."""
    _create_agent(db, "is-idtok")
    resp = client.get("/api/v1/admin/agents/is-idtok/identity-stack")
    layer = resp.json()["layers"][0]
    assert layer["type"] == "User ID-Token"
    assert layer["count"] == 0
    assert layer["active"] == 0
    assert layer["items"] == []
    assert len(layer["description"]) > 0


def test_identity_stack_user_session_layer(client, db):
    """User sessions for delegating users appear in the user session layer."""
    _create_agent(db, "is-usess")
    _create_delegation(db, "is-usess", "carol@test.com")

    us = UserSession(
        user_id="carol@test.com",
        idp_issuer="https://accounts.google.com",
    )
    db.add(us)
    db.commit()

    resp = client.get("/api/v1/admin/agents/is-usess/identity-stack")
    layer = resp.json()["layers"][1]
    assert layer["type"] == "User Session"
    assert layer["count"] >= 1
    item = next(i for i in layer["items"] if i["user"] == "carol@test.com")
    assert item["status"] == "active"
    assert item["idp"] is not None


def test_identity_stack_delegation_layer(client, db):
    """Delegation layer shows active and expired delegations with correct counts."""
    _create_agent(db, "is-del")
    _create_delegation(db, "is-del", "dave@test.com", ["notion:pages:read", "slack:messages:list"])

    expired_del = DelegationToken(
        agent_id="is-del",
        delegator="dave@test.com",
        delegated_permissions=["notion:pages:read"],
    )
    expired_del.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
    db.add(expired_del)
    db.commit()

    resp = client.get("/api/v1/admin/agents/is-del/identity-stack")
    layer = resp.json()["layers"][2]
    assert layer["type"] == "Delegation"
    assert layer["count"] == 2
    assert layer["active"] == 1
    active_item = next(i for i in layer["items"] if i["status"] == "active")
    assert active_item["delegator"] == "dave@test.com"
    assert active_item["permissions_count"] == 2
    assert sorted(active_item["services"]) == ["notion", "slack"]


def test_identity_stack_agent_session_layer(client, db):
    """Agent session layer shows sessions with correct status and fields."""
    _create_agent(db, "is-asess")
    d = _create_delegation(db, "is-asess", "eve@test.com")

    s1 = AgentSession(agent_id="is-asess", delegation_id=d.id, owner_email="eve@test.com")
    s2 = AgentSession(agent_id="is-asess", delegation_id=d.id, owner_email="eve@test.com")
    s2.is_active = False
    db.add_all([s1, s2])
    db.commit()

    resp = client.get("/api/v1/admin/agents/is-asess/identity-stack")
    layer = resp.json()["layers"][3]
    assert layer["type"] == "Agent Session"
    assert layer["count"] == 2
    assert layer["active"] >= 1
    item = next(i for i in layer["items"] if i["session_id"] == s1.id)
    assert item["delegator"] == "eve@test.com"
    assert item["delegation_id"] == d.id


def test_identity_stack_task_token_empty(client, db):
    """Task token layer is empty when no tasks exist."""
    _create_agent(db, "is-notask")
    resp = client.get("/api/v1/admin/agents/is-notask/identity-stack")
    layer = resp.json()["layers"][4]
    assert layer["type"] == "Task Token"
    assert layer["count"] == 0
    assert layer["items"] == []


def test_identity_stack_task_token_with_tasks(client, db):
    """Task token layer shows tasks when they exist."""
    _create_agent(db, "is-task")
    d = _create_delegation(db, "is-task", "frank@test.com")

    task = Task(
        agent_id="is-task",
        delegation_id=d.id,
        initiated_by="frank@test.com",
        name="Test Task",
        status=TaskStatus.ACTIVE,
        scoped_permissions=["notion:pages:read"],
    )
    db.add(task)
    db.commit()

    resp = client.get("/api/v1/admin/agents/is-task/identity-stack")
    layer = resp.json()["layers"][4]
    assert layer["type"] == "Task Token"
    assert layer["count"] == 1
    assert layer["active"] == 1
    assert layer["items"][0]["task_status"] == "active"


def test_identity_stack_session_pagination(client, db):
    """Sessions are paginated — count reflects total but items limited to session_limit."""
    _create_agent(db, "is-page")
    d = _create_delegation(db, "is-page", "gina@test.com")

    for _ in range(15):
        db.add(AgentSession(agent_id="is-page", delegation_id=d.id, owner_email="gina@test.com"))
    db.commit()

    resp = client.get("/api/v1/admin/agents/is-page/identity-stack")
    layer = resp.json()["layers"][3]
    assert layer["count"] == 15
    assert len(layer["items"]) == 10  # default limit


def test_identity_stack_services_extraction(client, db):
    """Delegation services are correctly extracted from permission prefixes."""
    _create_agent(db, "is-svc")
    _create_delegation(db, "is-svc", "hank@test.com", ["notion:pages:read", "slack:channels:list"])

    resp = client.get("/api/v1/admin/agents/is-svc/identity-stack")
    layer = resp.json()["layers"][2]
    item = layer["items"][0]
    assert sorted(item["services"]) == ["notion", "slack"]


def test_identity_stack_no_layer_numbering(client, db):
    """No L0/L1/L2/L3/L4/L5 layer numbering in the response."""
    _create_agent(db, "is-nonum")
    resp = client.get("/api/v1/admin/agents/is-nonum/identity-stack")
    raw = resp.text
    for label in ["L0", "L1", "L2", "L3", "L4", "L5"]:
        assert label not in raw or label in "ACTIVE_STATES"
