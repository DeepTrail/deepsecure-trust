"""Tests for agent slots and scheduler health endpoints (P-PROV WS-B5, WS-B6).

Validates:
- GET /admin/agent-slots returns slot list with claim status
- GET /admin/health/agents returns scheduler health data
- Both endpoints require admin auth
"""

import json
import pytest
import jwt
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.api.deps import get_db
from app.core.config import settings


SAMPLE_SLOTS = [
    {
        "name": "agent-slot-1",
        "sa_email": "agent-slot-1-sa@deepsecure-saas.iam.gserviceaccount.com",
        "job_name": "agent-slot-1-deepsecure-agent-job",
        "scheduler_name": "trigger-agent-slot-1-deepsecure-agent",
        "schedule": "0 */2 * * *",
    },
    {
        "name": "agent-slot-2",
        "sa_email": "agent-slot-2-sa@deepsecure-saas.iam.gserviceaccount.com",
        "job_name": "agent-slot-2-deepsecure-agent-job",
        "scheduler_name": "trigger-agent-slot-2-deepsecure-agent",
        "schedule": "0 */2 * * *",
    },
]


def _admin_token() -> str:
    return jwt.encode(
        {"sub": "admin@deeptrail.com", "roles": ["admin"], "type": "user"},
        settings.SECRET_KEY,
        algorithm="HS256",
    )


def _user_token() -> str:
    return jwt.encode(
        {"sub": "user@deeptrail.com", "roles": [], "type": "user"},
        settings.SECRET_KEY,
        algorithm="HS256",
    )


class TestListAgentSlots:
    """GET /api/v1/admin/agent-slots."""

    def test_no_auth_returns_error(self, client):
        resp = client.get("/api/v1/admin/agent-slots")
        assert resp.status_code in (401, 422)

    def test_non_admin_returns_403(self, client):
        resp = client.get(
            "/api/v1/admin/agent-slots",
            headers={"Authorization": f"Bearer {_user_token()}"},
        )
        assert resp.status_code == 403

    @patch("app.api.v1.endpoints.admin_fleet.settings")
    def test_returns_slots(self, mock_settings, client, db):
        mock_settings.AGENT_SLOTS_JSON = json.dumps(SAMPLE_SLOTS)
        mock_settings.SECRET_KEY = settings.SECRET_KEY
        mock_settings.GCP_PROJECT = "deepsecure-saas"
        mock_settings.GCP_REGION = "us-central1"

        resp = client.get(
            "/api/v1/admin/agent-slots",
            headers={"Authorization": f"Bearer {_admin_token()}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert data["available"] == 2
        assert len(data["slots"]) == 2

    @patch("app.api.v1.endpoints.admin_fleet.settings")
    def test_claimed_slot_reduces_available(self, mock_settings, client, db):
        mock_settings.AGENT_SLOTS_JSON = json.dumps(SAMPLE_SLOTS)
        mock_settings.SECRET_KEY = settings.SECRET_KEY
        mock_settings.GCP_PROJECT = "deepsecure-saas"
        mock_settings.GCP_REGION = "us-central1"

        from app.models.agent import Agent
        agent = Agent(
            agent_id="claimed-agent-slot-test",
            name="Claimed",
            platform="gcp_workload_identity",
            selector="agent-slot-1-sa@deepsecure-saas.iam.gserviceaccount.com",
        )
        db.add(agent)
        db.commit()

        try:
            resp = client.get(
                "/api/v1/admin/agent-slots",
                headers={"Authorization": f"Bearer {_admin_token()}"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["total"] == 2
            assert data["available"] == 1
            claimed = [s for s in data["slots"] if s["claimed_by"] is not None]
            assert len(claimed) == 1
            assert claimed[0]["claimed_by"] == "claimed-agent-slot-test"
        finally:
            db.query(Agent).filter(Agent.agent_id == "claimed-agent-slot-test").delete()
            db.commit()

    @patch("app.api.v1.endpoints.admin_fleet.settings")
    def test_empty_slots_json(self, mock_settings, client):
        mock_settings.AGENT_SLOTS_JSON = "[]"
        mock_settings.SECRET_KEY = settings.SECRET_KEY

        resp = client.get(
            "/api/v1/admin/agent-slots",
            headers={"Authorization": f"Bearer {_admin_token()}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["available"] == 0


class TestAgentSchedulerHealth:
    """GET /api/v1/admin/health/agents."""

    def test_no_auth_returns_error(self, client):
        resp = client.get("/api/v1/admin/health/agents")
        assert resp.status_code in (401, 422)

    def test_non_admin_returns_403(self, client):
        resp = client.get(
            "/api/v1/admin/health/agents",
            headers={"Authorization": f"Bearer {_user_token()}"},
        )
        assert resp.status_code == 403

    def test_returns_health_when_gcp_unavailable(self, client):
        """When GCP scheduler_v1 is not installed, returns empty but valid response."""
        resp = client.get(
            "/api/v1/admin/health/agents",
            headers={"Authorization": f"Bearer {_admin_token()}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "healthy" in data
        assert "unhealthy" in data
        assert "total" in data
