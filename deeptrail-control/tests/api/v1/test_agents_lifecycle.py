"""Integration tests for lifecycle fields on agent endpoints.

Tests that GET /agents/ and GET /agents/{id} return lifecycle_state
and related fields after LifecycleService injection (WS-A4).
"""

import base64
import os
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.agent_session import AgentSession, PartyType
from app.models.delegation import DelegationToken

API = settings.API_V1_STR


def _unique_key_b64() -> str:
    return base64.b64encode(os.urandom(32)).decode()


def _register_agent(client: TestClient, agent_id: str) -> dict:
    resp = client.post(
        f"{API}/agents/",
        json={"agent_id": agent_id, "public_key": _unique_key_b64()},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _seed_delegation(db: Session, agent_id: str, *, expired=False, revoked=False):
    now = datetime.now(timezone.utc)
    d = DelegationToken(
        agent_id=agent_id,
        delegator="lifecycle-test@acme.com",
        delegated_permissions=["notion:pages:read"],
        expires_at=now - timedelta(hours=1) if expired else now + timedelta(days=7),
        revoked_at=now if revoked else None,
    )
    db.add(d)
    db.commit()
    db.refresh(d)
    return d


def _seed_session(db: Session, agent_id: str, delegation_id: str, *, hours_ago=1):
    now = datetime.now(timezone.utc)
    s = AgentSession(
        agent_id=agent_id,
        delegation_id=delegation_id,
        party_type=PartyType.FIRST_PARTY,
        scoped_permissions=["notion:pages:read"],
        owner_email="lifecycle-test@acme.com",
        is_active=True,
        expires_at=now + timedelta(hours=8),
        last_activity_at=now - timedelta(hours=hours_ago),
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


class TestAgentDetailLifecycle:
    """GET /agents/{agent_id} returns lifecycle fields."""

    def test_registered_agent_has_lifecycle_state(self, client: TestClient, db: Session):
        _register_agent(client, "lc-detail-registered")
        resp = client.get(f"{API}/agents/lc-detail-registered")
        assert resp.status_code == 200
        data = resp.json()
        assert data["lifecycle_state"] == "registered"
        assert data["session_count"] == 0
        assert data["delegation_count"] == 0
        assert data["last_authenticated_at"] is None

    def test_delegated_agent_has_lifecycle_state(self, client: TestClient, db: Session):
        _register_agent(client, "lc-detail-delegated")
        _seed_delegation(db, "lc-detail-delegated")
        resp = client.get(f"{API}/agents/lc-detail-delegated")
        assert resp.status_code == 200
        data = resp.json()
        assert data["lifecycle_state"] == "delegated"
        assert data["delegation_count"] == 1

    def test_active_agent_has_lifecycle_state(self, client: TestClient, db: Session):
        _register_agent(client, "lc-detail-active")
        d = _seed_delegation(db, "lc-detail-active")
        _seed_session(db, "lc-detail-active", d.id, hours_ago=0.5)
        resp = client.get(f"{API}/agents/lc-detail-active")
        assert resp.status_code == 200
        data = resp.json()
        assert data["lifecycle_state"] == "active"
        assert data["session_count"] == 1
        assert data["last_authenticated_at"] is not None
        assert data["last_active_at"] is not None


class TestAgentListLifecycle:
    """GET /agents/ returns lifecycle_state for each agent."""

    def test_list_includes_lifecycle_state(self, client: TestClient, db: Session):
        _register_agent(client, "lc-list-a")
        _register_agent(client, "lc-list-b")
        _seed_delegation(db, "lc-list-b")

        resp = client.get(f"{API}/agents/")
        assert resp.status_code == 200
        data = resp.json()
        agents_by_id = {a["agent_id"]: a for a in data["agents"]}

        if "lc-list-a" in agents_by_id:
            assert agents_by_id["lc-list-a"]["lifecycle_state"] == "registered"
        if "lc-list-b" in agents_by_id:
            assert agents_by_id["lc-list-b"]["lifecycle_state"] == "delegated"

    def test_list_all_agents_have_lifecycle_state_field(self, client: TestClient, db: Session):
        _register_agent(client, "lc-list-field-check")
        resp = client.get(f"{API}/agents/")
        assert resp.status_code == 200
        for agent in resp.json()["agents"]:
            assert "lifecycle_state" in agent
