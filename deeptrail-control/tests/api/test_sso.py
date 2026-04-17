"""Tests for SSO (OIDC) endpoints (WS-L2).

Tests the SSO endpoints:
- GET  /api/v1/auth/sso/{idp}/authorize
- GET  /api/v1/auth/sso/{idp}/callback
- POST /api/v1/auth/sso/logout

Test Categories:
- Authorize: URL generation, redirect mode, unknown IdP
- Callback: Success (new/existing user), missing code, invalid state,
            expired state, state replay, IdP error, code exchange failure
- Logout: With valid token, without auth
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import jwt as pyjwt
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.api.v1.endpoints import sso as sso_module
from app.services.idp_service import (
    OIDCClaims,
    OIDCError,
    OIDCTokenInvalidError,
    OIDCTokens,
)


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def clear_pending_sso():
    """Reset pending SSO state between tests."""
    sso_module._pending_sso.clear()
    yield
    sso_module._pending_sso.clear()


@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def mock_provider():
    """Fully mocked OIDCProvider."""
    m = AsyncMock()
    m.get_authorization_url = AsyncMock(
        return_value="https://keycloak:8080/realms/deepsecure/protocol/openid-connect/auth?client_id=deepsecure-control&state=abc"
    )
    m.exchange_code = AsyncMock(
        return_value=OIDCTokens(
            id_token="mock.id.token",
            access_token="mock.access.token",
            refresh_token="mock.refresh.token",
        )
    )
    m.validate_token = AsyncMock(
        return_value=OIDCClaims(
            sub="kc-user-001",
            email="sarah@acme.com",
            name="Sarah Chen",
            groups=["acme-org"],
            roles=["user"],
            issuer="https://keycloak:8080/realms/deepsecure",
        )
    )
    m.get_user_info = AsyncMock()
    m.logout_url = AsyncMock(
        return_value="https://keycloak:8080/realms/deepsecure/protocol/openid-connect/logout"
    )
    return m


@pytest.fixture
def user_token():
    """A valid user session JWT."""
    now = datetime.now(timezone.utc)
    data = {
        "sub": "sarah@acme.com",
        "session_id": "usess-test-001",
        "organization_id": "org-acme-001",
        "exp": now + timedelta(hours=8),
        "iat": now,
        "idp": "keycloak",
    }
    return pyjwt.encode(data, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def _inject_state(idp: str = "keycloak", state: str = "test-state", **overrides):
    """Plant a PendingSSO entry directly."""
    defaults = dict(
        state=state,
        idp=idp,
        redirect_uri="http://localhost:8000/api/v1/auth/sso/keycloak/callback",
    )
    defaults.update(overrides)
    pending = sso_module.PendingSSO(**defaults)
    sso_module._pending_sso[state] = pending
    return pending


# ─────────────────────────────────────────────────────────────────────────────
# Authorize
# ─────────────────────────────────────────────────────────────────────────────


class TestAuthorize:
    def test_authorize_returns_url(self, client, mock_provider):
        with patch.object(sso_module, "create_oidc_provider", return_value=mock_provider):
            resp = client.get("/api/v1/auth/sso/keycloak/authorize")

        assert resp.status_code == 200
        data = resp.json()
        assert "authorization_url" in data
        assert "state" in data
        assert data["expires_in"] == 300
        assert data["authorization_url"].startswith("https://keycloak")

    def test_authorize_stores_state(self, client, mock_provider):
        with patch.object(sso_module, "create_oidc_provider", return_value=mock_provider):
            resp = client.get("/api/v1/auth/sso/keycloak/authorize")

        state = resp.json()["state"]
        assert state in sso_module._pending_sso
        pending = sso_module._pending_sso[state]
        assert pending.idp == "keycloak"

    def test_authorize_redirect_mode(self, client, mock_provider):
        with patch.object(sso_module, "create_oidc_provider", return_value=mock_provider):
            resp = client.get(
                "/api/v1/auth/sso/keycloak/authorize",
                params={"response_mode": "redirect"},
                follow_redirects=False,
            )

        assert resp.status_code == 302
        assert "keycloak" in resp.headers["location"]

    def test_authorize_unknown_idp(self, client):
        resp = client.get("/api/v1/auth/sso/invalid/authorize")
        assert resp.status_code == 400
        assert "Unknown IdP" in resp.json()["detail"]

    def test_authorize_stores_post_login_redirect(self, client, mock_provider):
        with patch.object(sso_module, "create_oidc_provider", return_value=mock_provider):
            resp = client.get(
                "/api/v1/auth/sso/keycloak/authorize",
                params={"post_login_redirect": "http://localhost:9876/done"},
            )
        assert resp.status_code == 200
        state = resp.json()["state"]
        assert sso_module._pending_sso[state].post_login_redirect == "http://localhost:9876/done"

    def test_authorize_no_post_login_redirect(self, client, mock_provider):
        with patch.object(sso_module, "create_oidc_provider", return_value=mock_provider):
            resp = client.get("/api/v1/auth/sso/keycloak/authorize")
        state = resp.json()["state"]
        assert sso_module._pending_sso[state].post_login_redirect is None

    def test_authorize_custom_redirect_uri(self, client, mock_provider):
        with patch.object(sso_module, "create_oidc_provider", return_value=mock_provider):
            resp = client.get(
                "/api/v1/auth/sso/keycloak/authorize",
                params={"redirect_uri": "https://app.example.com/callback"},
            )

        assert resp.status_code == 200
        state = resp.json()["state"]
        assert sso_module._pending_sso[state].redirect_uri == "https://app.example.com/callback"


# ─────────────────────────────────────────────────────────────────────────────
# Callback
# ─────────────────────────────────────────────────────────────────────────────


class TestCallback:
    def test_callback_success(self, client, mock_provider):
        _inject_state()
        with patch.object(sso_module, "create_oidc_provider", return_value=mock_provider):
            resp = client.get(
                "/api/v1/auth/sso/keycloak/callback",
                params={"code": "auth-code-123", "state": "test-state"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert "token" in data
        assert data["idp"] == "keycloak"
        assert data["user"]["email"] == "sarah@acme.com"
        assert data["expires_in"] == 86400

        # Verify the JWT is valid
        decoded = pyjwt.decode(
            data["token"], settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        assert decoded["sub"] == "sarah@acme.com"
        assert "session_id" in decoded
        assert decoded["idp"] == "keycloak"

    def test_callback_state_consumed(self, client, mock_provider):
        """State is one-time use — consumed on first callback."""
        _inject_state()
        with patch.object(sso_module, "create_oidc_provider", return_value=mock_provider):
            resp1 = client.get(
                "/api/v1/auth/sso/keycloak/callback",
                params={"code": "auth-code-123", "state": "test-state"},
            )
        assert resp1.status_code == 200

        # Replay with same state
        resp2 = client.get(
            "/api/v1/auth/sso/keycloak/callback",
            params={"code": "auth-code-456", "state": "test-state"},
        )
        assert resp2.status_code == 400
        assert "Invalid or expired" in resp2.json()["detail"]

    def test_callback_missing_code(self, client):
        _inject_state()
        resp = client.get(
            "/api/v1/auth/sso/keycloak/callback",
            params={"state": "test-state"},
        )
        assert resp.status_code == 400
        assert "Missing authorization code" in resp.json()["detail"]

    def test_callback_invalid_state(self, client):
        resp = client.get(
            "/api/v1/auth/sso/keycloak/callback",
            params={"code": "auth-code-123", "state": "nonexistent"},
        )
        assert resp.status_code == 400
        assert "Invalid or expired" in resp.json()["detail"]

    def test_callback_missing_state(self, client):
        resp = client.get(
            "/api/v1/auth/sso/keycloak/callback",
            params={"code": "auth-code-123"},
        )
        assert resp.status_code == 400
        assert "Missing state" in resp.json()["detail"]

    def test_callback_expired_state(self, client, mock_provider):
        _inject_state(
            created_at=datetime.now(timezone.utc) - timedelta(minutes=10),
            expires_in=300,
        )
        with patch.object(sso_module, "create_oidc_provider", return_value=mock_provider):
            resp = client.get(
                "/api/v1/auth/sso/keycloak/callback",
                params={"code": "auth-code-123", "state": "test-state"},
            )
        assert resp.status_code == 400
        assert "Invalid or expired" in resp.json()["detail"]

    def test_callback_idp_error(self, client):
        resp = client.get(
            "/api/v1/auth/sso/keycloak/callback",
            params={"error": "access_denied", "error_description": "User cancelled"},
        )
        assert resp.status_code == 400
        assert "IdP error" in resp.json()["detail"]
        assert "User cancelled" in resp.json()["detail"]

    def test_callback_idp_error_no_description(self, client):
        resp = client.get(
            "/api/v1/auth/sso/keycloak/callback",
            params={"error": "access_denied"},
        )
        assert resp.status_code == 400
        assert "access_denied" in resp.json()["detail"]

    def test_callback_code_exchange_failure(self, client, mock_provider):
        _inject_state()
        mock_provider.exchange_code = AsyncMock(
            side_effect=OIDCError("exchange failed")
        )
        with patch.object(sso_module, "create_oidc_provider", return_value=mock_provider):
            resp = client.get(
                "/api/v1/auth/sso/keycloak/callback",
                params={"code": "bad-code", "state": "test-state"},
            )
        assert resp.status_code == 500
        assert "Failed to exchange" in resp.json()["detail"]

    def test_callback_token_validation_failure(self, client, mock_provider):
        _inject_state()
        mock_provider.validate_token = AsyncMock(
            side_effect=OIDCTokenInvalidError("signature mismatch")
        )
        with patch.object(sso_module, "create_oidc_provider", return_value=mock_provider):
            resp = client.get(
                "/api/v1/auth/sso/keycloak/callback",
                params={"code": "auth-code-123", "state": "test-state"},
            )
        assert resp.status_code == 401
        assert "ID token validation failed" in resp.json()["detail"]

    def test_callback_new_user_provisioned(self, client, mock_provider):
        """First-time login should show is_new_user=True."""
        _inject_state()
        mock_claims = OIDCClaims(
            sub="brand-new-user",
            email="newuser@acme.com",
            name="New User",
            groups=[],
        )
        mock_provider.validate_token = AsyncMock(return_value=mock_claims)

        with patch.object(sso_module, "create_oidc_provider", return_value=mock_provider):
            resp = client.get(
                "/api/v1/auth/sso/keycloak/callback",
                params={"code": "auth-code-123", "state": "test-state"},
            )
        assert resp.status_code == 200
        assert resp.json()["user"]["is_new_user"] is True

    def test_callback_existing_user_matched(self, client, mock_provider):
        """Second login for same sub should show is_new_user=False."""
        from app.services.idp_service import _provisioned_users

        _provisioned_users["kc-user-001"] = {"user_id": "kc-user-001", "email": "sarah@acme.com"}

        _inject_state()
        with patch.object(sso_module, "create_oidc_provider", return_value=mock_provider):
            resp = client.get(
                "/api/v1/auth/sso/keycloak/callback",
                params={"code": "auth-code-123", "state": "test-state"},
            )
        assert resp.status_code == 200
        assert resp.json()["user"]["is_new_user"] is False

        _provisioned_users.pop("kc-user-001", None)

    def test_callback_redirects_when_post_login_redirect_set(self, client, mock_provider):
        _inject_state(post_login_redirect="http://localhost:9876/done")
        with patch.object(sso_module, "create_oidc_provider", return_value=mock_provider):
            resp = client.get(
                "/api/v1/auth/sso/keycloak/callback",
                params={"code": "auth-code-123", "state": "test-state"},
                follow_redirects=False,
            )
        assert resp.status_code == 302
        location = resp.headers["location"]
        assert location.startswith("http://localhost:9876/done?token=")
        token = location.split("token=")[1]
        decoded = pyjwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert decoded["sub"] == "sarah@acme.com"
        assert decoded["idp"] == "keycloak"

    def test_callback_returns_json_when_no_redirect(self, client, mock_provider):
        _inject_state()
        with patch.object(sso_module, "create_oidc_provider", return_value=mock_provider):
            resp = client.get(
                "/api/v1/auth/sso/keycloak/callback",
                params={"code": "auth-code-123", "state": "test-state"},
            )
        assert resp.status_code == 200
        assert "token" in resp.json()
        assert resp.json()["idp"] == "keycloak"

    def test_callback_idp_mismatch(self, client, mock_provider):
        """State was created for keycloak but callback comes with okta."""
        _inject_state(idp="keycloak")
        with patch.object(sso_module, "create_oidc_provider", return_value=mock_provider):
            resp = client.get(
                "/api/v1/auth/sso/okta/callback",
                params={"code": "auth-code-123", "state": "test-state"},
            )
        # okta provider creation raises NotImplementedError
        assert resp.status_code == 400
        assert "mismatch" in resp.json()["detail"].lower()


# ─────────────────────────────────────────────────────────────────────────────
# Logout
# ─────────────────────────────────────────────────────────────────────────────


class TestLogout:
    def test_logout_with_token(self, client, user_token, mock_provider):
        with patch.object(sso_module, "create_oidc_provider", return_value=mock_provider):
            resp = client.post(
                "/api/v1/auth/sso/logout",
                headers={"Authorization": f"Bearer {user_token}"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert "logout_url" in data
        assert "message" in data
        assert "Session invalidated" in data["message"]

    def test_logout_no_auth(self, client):
        resp = client.post("/api/v1/auth/sso/logout")
        assert resp.status_code == 401

    def test_logout_invalid_token(self, client):
        resp = client.post(
            "/api/v1/auth/sso/logout",
            headers={"Authorization": "Bearer invalid.token.here"},
        )
        assert resp.status_code == 401

    def test_logout_expired_token(self, client):
        now = datetime.now(timezone.utc)
        data = {
            "sub": "sarah@acme.com",
            "session_id": "usess-expired",
            "exp": now - timedelta(hours=1),
            "iat": now - timedelta(hours=9),
        }
        expired_token = pyjwt.encode(data, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        resp = client.post(
            "/api/v1/auth/sso/logout",
            headers={"Authorization": f"Bearer {expired_token}"},
        )
        assert resp.status_code == 401

    def test_logout_with_post_redirect_uri(self, client, user_token, mock_provider):
        with patch.object(sso_module, "create_oidc_provider", return_value=mock_provider):
            resp = client.post(
                "/api/v1/auth/sso/logout",
                headers={"Authorization": f"Bearer {user_token}"},
                json={"post_logout_redirect_uri": "https://app.example.com/logged-out"},
            )
        assert resp.status_code == 200


# ─────────────────────────────────────────────────────────────────────────────
# Schema tests
# ─────────────────────────────────────────────────────────────────────────────


class TestSchemas:
    def test_sso_authorize_response(self):
        from app.schemas.sso import SSOAuthorizeResponse

        r = SSOAuthorizeResponse(
            authorization_url="https://example.com/auth",
            state="abc123",
        )
        assert r.expires_in == 300

    def test_sso_user_info(self):
        from app.schemas.sso import SSOUserInfo

        u = SSOUserInfo(user_id="u1", email="a@b.com")
        assert u.is_new_user is False
        assert u.name is None

    def test_sso_callback_response(self):
        from app.schemas.sso import SSOCallbackResponse, SSOUserInfo

        r = SSOCallbackResponse(
            token="jwt",
            user=SSOUserInfo(user_id="u1", email="a@b.com"),
            expires_in=86400,
            idp="keycloak",
        )
        assert r.idp == "keycloak"

    def test_sso_logout_request_optional(self):
        from app.schemas.sso import SSOLogoutRequest

        r = SSOLogoutRequest()
        assert r.post_logout_redirect_uri is None

    def test_sso_logout_response(self):
        from app.schemas.sso import SSOLogoutResponse

        r = SSOLogoutResponse(message="Done")
        assert r.logout_url is None


# ─────────────────────────────────────────────────────────────────────────────
# PendingSSO state tests
# ─────────────────────────────────────────────────────────────────────────────


class TestPendingSSO:
    def test_not_expired(self):
        p = sso_module.PendingSSO(
            state="s", idp="keycloak", redirect_uri="http://localhost"
        )
        assert p.is_expired is False

    def test_expired(self):
        p = sso_module.PendingSSO(
            state="s",
            idp="keycloak",
            redirect_uri="http://localhost",
            created_at=datetime.now(timezone.utc) - timedelta(minutes=10),
            expires_in=300,
        )
        assert p.is_expired is True

    def test_post_login_redirect_default_none(self):
        p = sso_module.PendingSSO(
            state="s", idp="keycloak", redirect_uri="http://localhost"
        )
        assert p.post_login_redirect is None

    def test_post_login_redirect_set(self):
        p = sso_module.PendingSSO(
            state="s", idp="keycloak", redirect_uri="http://localhost",
            post_login_redirect="http://localhost:9876/done",
        )
        assert p.post_login_redirect == "http://localhost:9876/done"

    def test_cleanup_removes_expired(self):
        sso_module._pending_sso["old"] = sso_module.PendingSSO(
            state="old",
            idp="keycloak",
            redirect_uri="http://localhost",
            created_at=datetime.now(timezone.utc) - timedelta(minutes=10),
        )
        sso_module._pending_sso["new"] = sso_module.PendingSSO(
            state="new",
            idp="keycloak",
            redirect_uri="http://localhost",
        )
        sso_module._cleanup_expired()
        assert "old" not in sso_module._pending_sso
        assert "new" in sso_module._pending_sso
