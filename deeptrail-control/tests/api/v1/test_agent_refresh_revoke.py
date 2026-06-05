"""
Tests for agent session refresh (D4) and revocation (D5) endpoints.
"""

import os
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock

import jwt as pyjwt
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.jwt_signing import reset_jwt_signing_service


@pytest.fixture(autouse=True)
def _reset():
    reset_jwt_signing_service()
    yield
    reset_jwt_signing_service()


@pytest.fixture
def client():
    with patch.dict(os.environ, {"JWT_ALGORITHM": "HS256"}, clear=False):
        reset_jwt_signing_service()
        from app.main import app
        return TestClient(app)


def _make_agent_jwt(
    sub: str = "agent-test",
    session_id: str = "sess-123",
    extra: dict | None = None,
    expired: bool = False,
):
    now = datetime.now(timezone.utc)
    payload = {
        "sub": sub,
        "iss": "deeptrail-control",
        "aud": "deeptrail-gateway",
        "owner": "test@example.com",
        "delegated_permissions": ["notion:pages:search"],
        "delegation_id": "del-abc",
        "session_id": session_id,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=-30 if expired else 480)).timestamp()),
    }
    if extra:
        payload.update(extra)
    return pyjwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


# ─────────────────────────────────────────────────────────────────────
# D4: Agent Refresh
# ─────────────────────────────────────────────────────────────────────


class TestAgentRefresh:
    def test_refresh_valid_token(self, client):
        token = _make_agent_jwt()
        resp = client.post(
            "/api/v1/auth/agent/refresh",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "access_token" in body
        assert body["session_id"] == "sess-123"
        assert body["expires_in"] == 28800

    def test_refresh_recently_expired_token(self, client):
        token = _make_agent_jwt(expired=True)
        resp = client.post(
            "/api/v1/auth/agent/refresh",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200

    def test_refresh_missing_auth(self, client):
        resp = client.post("/api/v1/auth/agent/refresh")
        assert resp.status_code == 401

    def test_refresh_invalid_token(self, client):
        resp = client.post(
            "/api/v1/auth/agent/refresh",
            headers={"Authorization": "Bearer invalid.jwt.token"},
        )
        assert resp.status_code == 401

    def test_refresh_preserves_claims(self, client):
        token = _make_agent_jwt(
            sub="agent-x",
            extra={"owner": "alice@x.com", "delegated_permissions": ["slack:msg:send"]},
        )
        resp = client.post(
            "/api/v1/auth/agent/refresh",
            headers={"Authorization": f"Bearer {token}"},
        )
        new_token = resp.json()["access_token"]

        from app.core.jwt_signing import get_jwt_signing_service
        svc = get_jwt_signing_service()
        decoded = pyjwt.decode(
            new_token,
            svc.get_verification_key(),
            algorithms=[svc.algorithm, "HS256"],
            options={"verify_aud": False},
        )
        assert decoded["sub"] == "agent-x"
        assert decoded["owner"] == "alice@x.com"
        assert "slack:msg:send" in decoded["delegated_permissions"]


# ─────────────────────────────────────────────────────────────────────
# D5: Agent Revocation
# ─────────────────────────────────────────────────────────────────────


class TestAgentRevoke:
    def test_revoke_missing_auth(self, client):
        resp = client.post(
            "/api/v1/auth/agent/revoke",
            json={"session_id": "sess-123"},
        )
        assert resp.status_code == 401

    def test_revoke_invalid_token(self, client):
        resp = client.post(
            "/api/v1/auth/agent/revoke",
            json={"session_id": "sess-123"},
            headers={"Authorization": "Bearer bad"},
        )
        assert resp.status_code == 401

    def test_revoke_session_not_found(self, client):
        token = _make_agent_jwt()
        resp = client.post(
            "/api/v1/auth/agent/revoke",
            json={"session_id": "nonexistent-session"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404

    def test_revoke_request_requires_session_id(self, client):
        token = _make_agent_jwt()
        resp = client.post(
            "/api/v1/auth/agent/revoke",
            json={},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 422
