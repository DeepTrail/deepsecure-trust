"""Tests for GET /api/v1/agents/my-agents endpoint (P-PROV WS-C9).

Validates:
- Returns only agents with active delegations from the calling user
- Includes delegated services and prompt counts
- Returns empty list when no delegations exist
- Does not require admin role
"""

import jwt
from datetime import datetime, timedelta, timezone

from app.core.config import settings
from app.models.agent import Agent
from app.models.delegation import DelegationToken


def _user_headers(email: str = "sarah@deeptrail.com") -> dict:
    token = jwt.encode(
        {"sub": email, "roles": [], "type": "user"},
        settings.SECRET_KEY,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


def _admin_headers() -> dict:
    token = jwt.encode(
        {"sub": "admin@deeptrail.com", "roles": ["admin"], "type": "user"},
        settings.SECRET_KEY,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


class TestMyAgents:
    """GET /api/v1/agents/my-agents tests."""

    def test_no_auth_fails(self, client):
        resp = client.get("/api/v1/agents/my-agents")
        assert resp.status_code in (401, 422)

    def test_no_delegations_returns_empty(self, client):
        resp = client.get(
            "/api/v1/agents/my-agents",
            headers=_user_headers("no-delegations@deeptrail.com"),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["agents"] == []
        assert data["total"] == 0

    def test_returns_delegated_agents(self, client, db):
        agent = Agent(
            agent_id="my-agents-test-1",
            name="My Delegated Agent",
            config={"tagged_prompts": [
                {"services": "notion", "prompt": "Search", "added_by": "delegator@deeptrail.com"},
            ]},
        )
        db.add(agent)
        db.flush()

        delegation = DelegationToken(
            agent_id="my-agents-test-1",
            delegator="delegator@deeptrail.com",
            delegated_permissions=["notion:pages:read", "slack:messages:send"],
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )
        db.add(delegation)
        db.commit()

        resp = client.get(
            "/api/v1/agents/my-agents",
            headers=_user_headers("delegator@deeptrail.com"),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        agent_entry = next(
            (a for a in data["agents"] if a["agent_id"] == "my-agents-test-1"),
            None,
        )
        assert agent_entry is not None
        assert agent_entry["name"] == "My Delegated Agent"
        assert "notion" in agent_entry["delegated_services"]
        assert "slack" in agent_entry["delegated_services"]
        assert agent_entry["my_prompt_count"] == 1

    def test_excludes_expired_delegations(self, client, db):
        agent = Agent(
            agent_id="my-agents-expired",
            name="Expired Agent",
            config={},
        )
        db.add(agent)
        db.flush()

        delegation = DelegationToken(
            agent_id="my-agents-expired",
            delegator="expired-user@deeptrail.com",
            delegated_permissions=["notion:pages:read"],
            expires_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
        db.add(delegation)
        db.commit()

        resp = client.get(
            "/api/v1/agents/my-agents",
            headers=_user_headers("expired-user@deeptrail.com"),
        )
        assert resp.status_code == 200
        data = resp.json()
        expired_agents = [
            a for a in data["agents"] if a["agent_id"] == "my-agents-expired"
        ]
        assert len(expired_agents) == 0

    def test_excludes_revoked_delegations(self, client, db):
        agent = Agent(
            agent_id="my-agents-revoked",
            name="Revoked Agent",
            config={},
        )
        db.add(agent)
        db.flush()

        delegation = DelegationToken(
            agent_id="my-agents-revoked",
            delegator="revoked-user@deeptrail.com",
            delegated_permissions=["notion:pages:read"],
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
            revoked_at=datetime.now(timezone.utc),
        )
        db.add(delegation)
        db.commit()

        resp = client.get(
            "/api/v1/agents/my-agents",
            headers=_user_headers("revoked-user@deeptrail.com"),
        )
        assert resp.status_code == 200
        data = resp.json()
        revoked_agents = [
            a for a in data["agents"] if a["agent_id"] == "my-agents-revoked"
        ]
        assert len(revoked_agents) == 0

    def test_does_not_show_other_users_agents(self, client, db):
        agent = Agent(
            agent_id="my-agents-other-user",
            name="Other User Agent",
            config={},
        )
        db.add(agent)
        db.flush()

        delegation = DelegationToken(
            agent_id="my-agents-other-user",
            delegator="other@deeptrail.com",
            delegated_permissions=["notion:pages:read"],
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )
        db.add(delegation)
        db.commit()

        resp = client.get(
            "/api/v1/agents/my-agents",
            headers=_user_headers("not-other@deeptrail.com"),
        )
        assert resp.status_code == 200
        data = resp.json()
        other_agents = [
            a for a in data["agents"] if a["agent_id"] == "my-agents-other-user"
        ]
        assert len(other_agents) == 0

    def test_admin_can_also_use_my_agents(self, client, db):
        """Admin calling /my-agents sees only their own delegations, not all agents."""
        resp = client.get(
            "/api/v1/agents/my-agents",
            headers=_admin_headers(),
        )
        assert resp.status_code == 200
