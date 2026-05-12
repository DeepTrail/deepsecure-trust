"""Integration tests for GET /agents/{agent_id}/sessions endpoint (WS-A9).

Tests the sessions listing endpoint added in WS-A5, including
active_only filter, ordering, and source_ip visibility.
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
DELEGATOR = "sessions-test@acme.com"


def _unique_key_b64() -> str:
    return base64.b64encode(os.urandom(32)).decode()


def _register_agent(client: TestClient, agent_id: str):
    resp = client.post(
        f"{API}/agents/",
        json={"agent_id": agent_id, "public_key": _unique_key_b64()},
    )
    assert resp.status_code == 201, resp.text


def _seed_delegation(db: Session, agent_id: str):
    now = datetime.now(timezone.utc)
    d = DelegationToken(
        agent_id=agent_id,
        delegator=DELEGATOR,
        delegated_permissions=["notion:pages:read"],
        expires_at=now + timedelta(days=7),
    )
    db.add(d)
    db.commit()
    db.refresh(d)
    return d


def _seed_session(db: Session, agent_id: str, delegation_id: str, *,
                  active=True, source_ip=None, hours_ago=0):
    now = datetime.now(timezone.utc)
    s = AgentSession(
        agent_id=agent_id,
        delegation_id=delegation_id,
        party_type=PartyType.FIRST_PARTY,
        scoped_permissions=["notion:pages:read"],
        owner_email=DELEGATOR,
        is_active=active,
        expires_at=now + timedelta(hours=8),
        created_at=now - timedelta(hours=hours_ago),
        source_ip=source_ip,
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


class TestSessionsEndpoint:
    """Tests for GET /agents/{agent_id}/sessions."""

    def test_no_sessions_returns_empty(self, client: TestClient, db: Session):
        _register_agent(client, "sess-empty")
        resp = client.get(f"{API}/agents/sess-empty/sessions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["sessions"] == []
        assert data["total"] == 0

    def test_returns_sessions_for_agent(self, client: TestClient, db: Session):
        _register_agent(client, "sess-has-data")
        d = _seed_delegation(db, "sess-has-data")
        _seed_session(db, "sess-has-data", d.id, source_ip="10.0.0.1")

        resp = client.get(f"{API}/agents/sess-has-data/sessions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        session = data["sessions"][0]
        assert session["agent_id"] == "sess-has-data"
        assert session["is_active"] is True
        assert session["source_ip"] == "10.0.0.1"
        assert "session_id" in session
        assert "created_at" in session

    def test_active_only_filter(self, client: TestClient, db: Session):
        _register_agent(client, "sess-filter")
        d = _seed_delegation(db, "sess-filter")
        _seed_session(db, "sess-filter", d.id, active=True)
        _seed_session(db, "sess-filter", d.id, active=False)

        resp_all = client.get(f"{API}/agents/sess-filter/sessions")
        assert resp_all.json()["total"] == 2

        resp_active = client.get(f"{API}/agents/sess-filter/sessions?active_only=true")
        assert resp_active.json()["total"] == 1
        assert resp_active.json()["sessions"][0]["is_active"] is True

    def test_sessions_ordered_by_most_recent(self, client: TestClient, db: Session):
        _register_agent(client, "sess-order")
        d = _seed_delegation(db, "sess-order")
        _seed_session(db, "sess-order", d.id, source_ip="old", hours_ago=5)
        _seed_session(db, "sess-order", d.id, source_ip="new", hours_ago=0)

        resp = client.get(f"{API}/agents/sess-order/sessions")
        sessions = resp.json()["sessions"]
        assert len(sessions) == 2
        assert sessions[0]["source_ip"] == "new"
        assert sessions[1]["source_ip"] == "old"

    def test_agent_not_found_returns_404(self, client: TestClient, db: Session):
        resp = client.get(f"{API}/agents/nonexistent-sess-agent/sessions")
        assert resp.status_code == 404

    def test_source_ip_null_when_not_set(self, client: TestClient, db: Session):
        _register_agent(client, "sess-no-ip")
        d = _seed_delegation(db, "sess-no-ip")
        _seed_session(db, "sess-no-ip", d.id)

        resp = client.get(f"{API}/agents/sess-no-ip/sessions")
        session = resp.json()["sessions"][0]
        assert session["source_ip"] is None

    def test_does_not_leak_other_agents_sessions(self, client: TestClient, db: Session):
        _register_agent(client, "sess-agent-a")
        _register_agent(client, "sess-agent-b")
        d_a = _seed_delegation(db, "sess-agent-a")
        d_b = _seed_delegation(db, "sess-agent-b")
        _seed_session(db, "sess-agent-a", d_a.id)
        _seed_session(db, "sess-agent-b", d_b.id)

        resp = client.get(f"{API}/agents/sess-agent-a/sessions")
        data = resp.json()
        assert data["total"] == 1
        assert data["sessions"][0]["agent_id"] == "sess-agent-a"
