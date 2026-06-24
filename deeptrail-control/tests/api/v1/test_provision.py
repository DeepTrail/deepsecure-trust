"""Tests for composite provision endpoint (P-PROV WS-C7).

Validates POST /api/v1/admin/agents/provision:
- Admin can provision agent + config + delegation template atomically
- Non-admin gets 403
- Duplicate selector returns 409
- Response includes agent, config, delegation_template, scheduler_resumed
"""

import jwt

from app.core.config import settings
from app.models.agent import Agent
from app.models.delegation_template import DelegationTemplate


def _admin_headers() -> dict:
    token = jwt.encode(
        {"sub": "admin@deeptrail.com", "roles": ["admin"], "type": "user"},
        settings.SECRET_KEY,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _user_headers() -> dict:
    token = jwt.encode(
        {"sub": "employee@deeptrail.com", "roles": [], "type": "user"},
        settings.SECRET_KEY,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


_PROVISION_BODY = {
    "agent": {
        "name": "Test Provision Agent",
        "description": "Provisioned via composite API",
        "platform": "gcp_workload_identity",
        "selector": "test-prov-sa@project.iam.gserviceaccount.com",
    },
    "config": {
        "prompts_per_delegation": 5,
        "max_rounds": 2,
        "interval_seconds": 120,
        "tagged_prompts": [
            {"services": "notion", "prompt": "Search pages"}
        ],
    },
    "delegation_template": {
        "max_permissions": ["notion:pages:read", "notion:pages:search"],
        "default_ttl_days": 14,
        "available_to_roles": ["all"],
    },
}


class TestProvisionEndpoint:
    """POST /api/v1/admin/agents/provision tests."""

    def test_non_admin_forbidden(self, client):
        resp = client.post(
            "/api/v1/admin/agents/provision",
            json=_PROVISION_BODY,
            headers=_user_headers(),
        )
        assert resp.status_code == 403

    def test_no_auth_fails(self, client):
        resp = client.post(
            "/api/v1/admin/agents/provision",
            json=_PROVISION_BODY,
        )
        assert resp.status_code in (401, 422)

    def test_admin_can_provision(self, client, db):
        body = dict(_PROVISION_BODY)
        body["agent"] = {
            **body["agent"],
            "selector": "admin-prov-test@project.iam.gserviceaccount.com",
        }
        resp = client.post(
            "/api/v1/admin/agents/provision",
            json=body,
            headers=_admin_headers(),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "agent" in data
        assert "config" in data
        assert "delegation_template" in data
        assert "scheduler_resumed" in data
        assert data["agent"]["name"] == "Test Provision Agent"
        assert data["agent"]["created_by"] == "admin@deeptrail.com"

        agent = db.query(Agent).filter(
            Agent.selector == "admin-prov-test@project.iam.gserviceaccount.com"
        ).first()
        assert agent is not None
        assert agent.created_by == "admin@deeptrail.com"

    def test_duplicate_selector_409(self, client, db):
        from app.models.agent import Agent
        existing = Agent(
            agent_id="existing-dup-agent",
            name="Existing",
            platform="gcp_workload_identity",
            selector="dup-selector@project.iam.gserviceaccount.com",
        )
        db.add(existing)
        db.commit()

        body = dict(_PROVISION_BODY)
        body["agent"] = {
            **body["agent"],
            "selector": "dup-selector@project.iam.gserviceaccount.com",
        }
        resp = client.post(
            "/api/v1/admin/agents/provision",
            json=body,
            headers=_admin_headers(),
        )
        assert resp.status_code == 409

    def test_provision_creates_delegation_template(self, client, db):
        body = dict(_PROVISION_BODY)
        body["agent"] = {
            **body["agent"],
            "selector": "tmpl-test@project.iam.gserviceaccount.com",
        }
        resp = client.post(
            "/api/v1/admin/agents/provision",
            json=body,
            headers=_admin_headers(),
        )
        assert resp.status_code == 201
        data = resp.json()
        agent_id = data["agent"]["agent_id"]

        template = db.query(DelegationTemplate).filter(
            DelegationTemplate.agent_id == agent_id
        ).first()
        assert template is not None
        assert "notion:pages:read" in template.max_permissions

    def test_provision_sets_config(self, client, db):
        body = dict(_PROVISION_BODY)
        body["agent"] = {
            **body["agent"],
            "selector": "cfg-test@project.iam.gserviceaccount.com",
        }
        resp = client.post(
            "/api/v1/admin/agents/provision",
            json=body,
            headers=_admin_headers(),
        )
        assert resp.status_code == 201
        data = resp.json()
        agent_id = data["agent"]["agent_id"]

        agent = db.query(Agent).filter(Agent.agent_id == agent_id).first()
        assert agent is not None
        config = agent.config or {}
        assert config.get("prompts_per_delegation") == 5
        assert config.get("max_rounds") == 2

    def test_provision_minimal_body(self, client, db):
        """Provision with minimal required fields."""
        body = {
            "agent": {
                "name": "Minimal Agent",
                "selector": "minimal@project.iam.gserviceaccount.com",
            },
            "delegation_template": {
                "max_permissions": ["notion:pages:read"],
            },
        }
        resp = client.post(
            "/api/v1/admin/agents/provision",
            json=body,
            headers=_admin_headers(),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["agent"]["name"] == "Minimal Agent"
