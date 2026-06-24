"""Tests for config endpoint auth enforcement (P-PROV WS-A6).

Validates that:
- GET /agents/{id}/config requires authentication
- GET /agents/{id}/config allows admin or agent-self access
- PUT /agents/{id}/config requires admin role
- Unauthorized requests return 401/403
"""

import pytest
import jwt

from app.core.config import settings


def _make_admin_token(user_id: str = "admin@deeptrail.com") -> str:
    """Create a JWT with admin role."""
    return jwt.encode(
        {"sub": user_id, "roles": ["admin"], "type": "user"},
        settings.SECRET_KEY,
        algorithm="HS256",
    )


def _make_user_token(user_id: str = "employee@deeptrail.com") -> str:
    """Create a JWT without admin role."""
    return jwt.encode(
        {"sub": user_id, "roles": [], "type": "user"},
        settings.SECRET_KEY,
        algorithm="HS256",
    )


def _make_agent_token(agent_id: str) -> str:
    """Create a JWT with type=agent."""
    return jwt.encode(
        {"sub": agent_id, "type": "agent", "agent_id": agent_id},
        settings.SECRET_KEY,
        algorithm="HS256",
    )


class TestGetAgentConfigAuth:
    """GET /api/v1/agents/{agent_id}/config — auth enforcement."""

    def test_no_auth_returns_422_or_401(self, client):
        """Request without Authorization header should fail."""
        resp = client.get("/api/v1/agents/test-agent/config")
        assert resp.status_code in (401, 422)

    def test_invalid_token_returns_401(self, client):
        """Request with garbage token should return 401."""
        resp = client.get(
            "/api/v1/agents/test-agent/config",
            headers={"Authorization": "Bearer invalid_garbage_token"},
        )
        assert resp.status_code == 401

    def test_admin_can_read_config(self, client, db):
        """Admin token should allow reading agent config."""
        from app.models.agent import Agent

        agent = Agent(agent_id="test-admin-read", name="Test Agent", config={})
        db.add(agent)
        db.commit()

        try:
            token = _make_admin_token()
            resp = client.get(
                "/api/v1/agents/test-admin-read/config",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 200
        finally:
            db.query(Agent).filter(Agent.agent_id == "test-admin-read").delete()
            db.commit()

    def test_agent_self_can_read_config(self, client, db):
        """Agent JWT with matching agent_id should allow self-read."""
        from app.models.agent import Agent

        agent = Agent(agent_id="self-reading-agent", name="Self Reader", config={})
        db.add(agent)
        db.commit()

        try:
            token = _make_agent_token("self-reading-agent")
            resp = client.get(
                "/api/v1/agents/self-reading-agent/config",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 200
        finally:
            db.query(Agent).filter(Agent.agent_id == "self-reading-agent").delete()
            db.commit()

    def test_agent_cannot_read_other_agent_config(self, client, db):
        """Agent JWT cannot read another agent's config."""
        from app.models.agent import Agent

        agent = Agent(agent_id="other-agent", name="Other Agent", config={})
        db.add(agent)
        db.commit()

        try:
            token = _make_agent_token("different-agent")
            resp = client.get(
                "/api/v1/agents/other-agent/config",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 403
        finally:
            db.query(Agent).filter(Agent.agent_id == "other-agent").delete()
            db.commit()

    def test_non_admin_user_returns_403(self, client, db):
        """Non-admin user token should return 403."""
        from app.models.agent import Agent

        agent = Agent(agent_id="forbidden-agent", name="Forbidden", config={})
        db.add(agent)
        db.commit()

        try:
            token = _make_user_token()
            resp = client.get(
                "/api/v1/agents/forbidden-agent/config",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 403
        finally:
            db.query(Agent).filter(Agent.agent_id == "forbidden-agent").delete()
            db.commit()


class TestUpdateAgentConfigAuth:
    """PUT /api/v1/agents/{agent_id}/config — admin-only enforcement."""

    def test_no_auth_returns_422_or_401(self, client):
        """Request without Authorization header should fail."""
        resp = client.put(
            "/api/v1/agents/test-agent/config",
            json={"max_rounds": 5},
        )
        assert resp.status_code in (401, 422)

    def test_admin_can_update_config(self, client, db):
        """Admin token should allow updating agent config."""
        from app.models.agent import Agent

        agent = Agent(agent_id="test-admin-update", name="Updatable", config={})
        db.add(agent)
        db.commit()

        try:
            token = _make_admin_token()
            resp = client.put(
                "/api/v1/agents/test-admin-update/config",
                json={"max_rounds": 5},
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 200
            assert resp.json()["max_rounds"] == 5
        finally:
            db.query(Agent).filter(Agent.agent_id == "test-admin-update").delete()
            db.commit()

    def test_agent_self_cannot_update_config(self, client, db):
        """Agent JWT should NOT be able to update config (admin-only)."""
        from app.models.agent import Agent

        agent = Agent(agent_id="no-self-update", name="No Self Update", config={})
        db.add(agent)
        db.commit()

        try:
            token = _make_agent_token("no-self-update")
            resp = client.put(
                "/api/v1/agents/no-self-update/config",
                json={"max_rounds": 5},
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 403
        finally:
            db.query(Agent).filter(Agent.agent_id == "no-self-update").delete()
            db.commit()

    def test_non_admin_user_returns_403(self, client, db):
        """Non-admin user token should return 403 for config update."""
        from app.models.agent import Agent

        agent = Agent(agent_id="no-user-update", name="No User Update", config={})
        db.add(agent)
        db.commit()

        try:
            token = _make_user_token()
            resp = client.put(
                "/api/v1/agents/no-user-update/config",
                json={"max_rounds": 5},
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 403
        finally:
            db.query(Agent).filter(Agent.agent_id == "no-user-update").delete()
            db.commit()
