"""Tests for prompt CRUD endpoints with delegation-based RBAC (P-PROV WS-C8).

Validates:
- GET /agents/{id}/prompts — requires delegation or admin
- POST /agents/{id}/prompts — validates service tags against delegation
- DELETE /agents/{id}/prompts/{index} — only author or admin
- Non-delegated users get 403
"""

import jwt
from datetime import datetime, timedelta, timezone

from app.core.config import settings
from app.models.agent import Agent
from app.models.delegation import DelegationToken


def _admin_headers() -> dict:
    token = jwt.encode(
        {"sub": "admin@deeptrail.com", "roles": ["admin"], "type": "user"},
        settings.SECRET_KEY,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _user_headers(email: str = "employee@deeptrail.com") -> dict:
    token = jwt.encode(
        {"sub": email, "roles": [], "type": "user"},
        settings.SECRET_KEY,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _create_agent_with_delegation(db, agent_id: str, delegator: str, permissions: list[str]):
    """Helper to create an agent + active delegation for testing."""
    agent = db.query(Agent).filter(Agent.agent_id == agent_id).first()
    if not agent:
        agent = Agent(
            agent_id=agent_id,
            name=f"Test Agent {agent_id}",
            config={"tagged_prompts": []},
        )
        db.add(agent)
        db.flush()

    delegation = DelegationToken(
        agent_id=agent_id,
        delegator=delegator,
        delegated_permissions=permissions,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    db.add(delegation)
    db.commit()
    return agent, delegation


class TestGetPrompts:
    """GET /api/v1/agents/{id}/prompts tests."""

    def test_admin_can_list_prompts(self, client, db):
        agent = Agent(
            agent_id="prompt-list-admin",
            name="Test",
            config={"tagged_prompts": [
                {"services": "notion", "prompt": "Search", "added_by": "admin@deeptrail.com"}
            ]},
        )
        db.add(agent)
        db.commit()

        resp = client.get(
            "/api/v1/agents/prompt-list-admin/prompts",
            headers=_admin_headers(),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1

    def test_delegated_user_can_list_prompts(self, client, db):
        _create_agent_with_delegation(
            db, "prompt-list-deleg", "sarah@deeptrail.com",
            ["notion:pages:read"],
        )
        resp = client.get(
            "/api/v1/agents/prompt-list-deleg/prompts",
            headers=_user_headers("sarah@deeptrail.com"),
        )
        assert resp.status_code == 200

    def test_non_delegated_user_forbidden(self, client, db):
        agent = Agent(agent_id="prompt-list-noauth", name="Test", config={})
        db.add(agent)
        db.commit()

        resp = client.get(
            "/api/v1/agents/prompt-list-noauth/prompts",
            headers=_user_headers("outsider@deeptrail.com"),
        )
        assert resp.status_code == 403

    def test_agent_not_found(self, client):
        resp = client.get(
            "/api/v1/agents/nonexistent-agent-prompts/prompts",
            headers=_admin_headers(),
        )
        assert resp.status_code == 404


class TestAddPrompt:
    """POST /api/v1/agents/{id}/prompts tests."""

    def test_delegated_user_can_add_prompt(self, client, db):
        _create_agent_with_delegation(
            db, "prompt-add-ok", "sarah@deeptrail.com",
            ["notion:pages:read", "notion:pages:search"],
        )
        resp = client.post(
            "/api/v1/agents/prompt-add-ok/prompts",
            json={"services": "notion", "prompt": "Search pages updated today"},
            headers=_user_headers("sarah@deeptrail.com"),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["added_by"] == "sarah@deeptrail.com"
        assert data["services"] == "notion"
        assert "index" in data

    def test_service_not_in_delegation_returns_422(self, client, db):
        _create_agent_with_delegation(
            db, "prompt-add-bad-svc", "bob@deeptrail.com",
            ["notion:pages:read"],
        )
        resp = client.post(
            "/api/v1/agents/prompt-add-bad-svc/prompts",
            json={"services": "github", "prompt": "List repos"},
            headers=_user_headers("bob@deeptrail.com"),
        )
        assert resp.status_code == 422
        assert "github" in resp.json()["detail"]

    def test_admin_can_add_any_service(self, client, db):
        agent = Agent(
            agent_id="prompt-add-admin",
            name="Test",
            config={"tagged_prompts": []},
        )
        db.add(agent)
        db.commit()

        resp = client.post(
            "/api/v1/agents/prompt-add-admin/prompts",
            json={"services": "github,slack", "prompt": "Cross-service prompt"},
            headers=_admin_headers(),
        )
        assert resp.status_code == 201

    def test_non_delegated_user_forbidden(self, client, db):
        agent = Agent(
            agent_id="prompt-add-noauth",
            name="Test",
            config={"tagged_prompts": []},
        )
        db.add(agent)
        db.commit()

        resp = client.post(
            "/api/v1/agents/prompt-add-noauth/prompts",
            json={"services": "notion", "prompt": "Denied"},
            headers=_user_headers("outsider@deeptrail.com"),
        )
        assert resp.status_code == 403


class TestDeletePrompt:
    """DELETE /api/v1/agents/{id}/prompts/{index} tests."""

    def test_author_can_delete_own_prompt(self, client, db):
        agent = Agent(
            agent_id="prompt-del-author",
            name="Test",
            config={"tagged_prompts": [
                {"services": "notion", "prompt": "Search", "added_by": "sarah@deeptrail.com"},
            ]},
        )
        db.add(agent)
        db.commit()

        _create_agent_with_delegation(
            db, "prompt-del-author", "sarah@deeptrail.com",
            ["notion:pages:read"],
        )
        resp = client.delete(
            "/api/v1/agents/prompt-del-author/prompts/0",
            headers=_user_headers("sarah@deeptrail.com"),
        )
        assert resp.status_code == 204

    def test_non_author_forbidden(self, client, db):
        agent = Agent(
            agent_id="prompt-del-other",
            name="Test",
            config={"tagged_prompts": [
                {"services": "notion", "prompt": "Search", "added_by": "sarah@deeptrail.com"},
            ]},
        )
        db.add(agent)
        db.commit()

        _create_agent_with_delegation(
            db, "prompt-del-other", "bob@deeptrail.com",
            ["notion:pages:read"],
        )
        resp = client.delete(
            "/api/v1/agents/prompt-del-other/prompts/0",
            headers=_user_headers("bob@deeptrail.com"),
        )
        assert resp.status_code == 403

    def test_admin_can_delete_any_prompt(self, client, db):
        agent = Agent(
            agent_id="prompt-del-admin",
            name="Test",
            config={"tagged_prompts": [
                {"services": "notion", "prompt": "Search", "added_by": "sarah@deeptrail.com"},
            ]},
        )
        db.add(agent)
        db.commit()

        resp = client.delete(
            "/api/v1/agents/prompt-del-admin/prompts/0",
            headers=_admin_headers(),
        )
        assert resp.status_code == 204

    def test_invalid_index_404(self, client, db):
        agent = Agent(
            agent_id="prompt-del-idx",
            name="Test",
            config={"tagged_prompts": []},
        )
        db.add(agent)
        db.commit()

        resp = client.delete(
            "/api/v1/agents/prompt-del-idx/prompts/99",
            headers=_admin_headers(),
        )
        assert resp.status_code == 404
