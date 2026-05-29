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

import os
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import jwt as pyjwt
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.api.v1.endpoints import sso as sso_module
from app.api.v1.endpoints.sso import _decode_jwt_for_refresh
from app.models.pending_oauth_state import PendingOAuthState
from app.services.idp_service import (
    OIDCClaims,
    OIDCError,
    OIDCTokenInvalidError,
    OIDCTokens,
)

_IDP_SESSION_SVC_PATCH = "app.services.idp_session_service.IdPSessionService"
_CREATE_PROVIDER_PATCH = "app.api.v1.endpoints.sso.create_oidc_provider"


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def clear_pending_sso(db):
    """Reset pending SSO state between tests (DB-backed)."""
    db.query(PendingOAuthState).delete()
    db.commit()
    yield
    db.query(PendingOAuthState).delete()
    db.commit()


@pytest.fixture
def client(db):
    """FastAPI test client with DB dependency override."""
    from app.api.deps import get_db

    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    del app.dependency_overrides[get_db]


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


def _inject_state(db, idp: str = "keycloak", state: str = "test-state", **overrides):
    """Plant a PendingOAuthState entry directly into the DB."""
    from app.models.pending_oauth_state import PendingOAuthState, _default_expires_at
    defaults = dict(
        state=state,
        idp=idp,
        redirect_uri="http://localhost:8000/api/v1/auth/sso/keycloak/callback",
        expires_at=_default_expires_at(),
    )
    defaults.update(overrides)
    pending = PendingOAuthState(**defaults)
    db.add(pending)
    db.commit()
    db.refresh(pending)
    return pending


def _get_pending_state(db, state: str):
    """Retrieve a PendingOAuthState from the DB."""
    return db.query(PendingOAuthState).filter(PendingOAuthState.state == state).first()


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
        assert 290 <= data["expires_in"] <= 300
        assert data["authorization_url"].startswith("https://keycloak")

    def test_authorize_stores_state(self, client, mock_provider, db):
        with patch.object(sso_module, "create_oidc_provider", return_value=mock_provider):
            resp = client.get("/api/v1/auth/sso/keycloak/authorize")

        state = resp.json()["state"]
        pending = _get_pending_state(db, state)
        assert pending is not None
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

    def test_authorize_stores_post_login_redirect(self, client, mock_provider, db):
        with patch.object(sso_module, "create_oidc_provider", return_value=mock_provider):
            resp = client.get(
                "/api/v1/auth/sso/keycloak/authorize",
                params={"post_login_redirect": "http://localhost:9876/done"},
            )
        assert resp.status_code == 200
        state = resp.json()["state"]
        assert _get_pending_state(db, state).post_login_redirect == "http://localhost:9876/done"

    def test_authorize_no_post_login_redirect(self, client, mock_provider, db):
        with patch.object(sso_module, "create_oidc_provider", return_value=mock_provider):
            resp = client.get("/api/v1/auth/sso/keycloak/authorize")
        state = resp.json()["state"]
        assert _get_pending_state(db, state).post_login_redirect is None

    def test_authorize_custom_redirect_uri(self, client, mock_provider, db):
        with patch.object(sso_module, "create_oidc_provider", return_value=mock_provider):
            resp = client.get(
                "/api/v1/auth/sso/keycloak/authorize",
                params={"redirect_uri": "https://app.example.com/callback"},
            )

        assert resp.status_code == 200
        state = resp.json()["state"]
        assert _get_pending_state(db, state).redirect_uri == "https://app.example.com/callback"


# ─────────────────────────────────────────────────────────────────────────────
# Callback
# ─────────────────────────────────────────────────────────────────────────────


class TestCallback:
    def test_callback_success(self, client, mock_provider, db):
        _inject_state(db)
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

    def test_callback_state_consumed(self, client, mock_provider, db):
        """State is one-time use — consumed on first callback."""
        _inject_state(db)
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

    def test_callback_missing_code(self, client, db):
        _inject_state(db)
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

    def test_callback_expired_state(self, client, mock_provider, db):
        _inject_state(
            db,
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=5),
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

    def test_callback_code_exchange_failure(self, client, mock_provider, db):
        _inject_state(db)
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

    def test_callback_token_validation_failure(self, client, mock_provider, db):
        _inject_state(db)
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

    def test_callback_new_user_provisioned(self, client, mock_provider, db):
        """First-time login should show is_new_user=True."""
        _inject_state(db)
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

    def test_callback_existing_user_matched(self, client, mock_provider, db):
        """Second login for same sub should show is_new_user=False."""
        from app.services.idp_service import _provisioned_users

        _provisioned_users["kc-user-001"] = {"user_id": "kc-user-001", "email": "sarah@acme.com"}

        _inject_state(db)
        with patch.object(sso_module, "create_oidc_provider", return_value=mock_provider):
            resp = client.get(
                "/api/v1/auth/sso/keycloak/callback",
                params={"code": "auth-code-123", "state": "test-state"},
            )
        assert resp.status_code == 200
        assert resp.json()["user"]["is_new_user"] is False

        _provisioned_users.pop("kc-user-001", None)

    def test_callback_redirects_when_post_login_redirect_set(self, client, mock_provider, db):
        from urllib.parse import parse_qs, urlparse

        _inject_state(db, post_login_redirect="http://localhost:9876/done")
        with patch.object(sso_module, "create_oidc_provider", return_value=mock_provider):
            resp = client.get(
                "/api/v1/auth/sso/keycloak/callback",
                params={"code": "auth-code-123", "state": "test-state"},
                follow_redirects=False,
            )
        assert resp.status_code == 302
        location = resp.headers["location"]
        assert location.startswith("http://localhost:9876/done?")
        parsed = urlparse(location)
        params = parse_qs(parsed.query)
        token = params["token"][0]
        decoded = pyjwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert decoded["sub"] == "sarah@acme.com"
        assert decoded["idp"] == "keycloak"
        assert decoded["groups"] == ["acme-org"]
        assert "user" in decoded["roles"]

    def test_callback_returns_json_when_no_redirect(self, client, mock_provider, db):
        _inject_state(db)
        with patch.object(sso_module, "create_oidc_provider", return_value=mock_provider):
            resp = client.get(
                "/api/v1/auth/sso/keycloak/callback",
                params={"code": "auth-code-123", "state": "test-state"},
            )
        assert resp.status_code == 200
        assert "token" in resp.json()
        assert resp.json()["idp"] == "keycloak"

    def test_callback_idp_mismatch(self, client, mock_provider, db):
        """State was created for keycloak but callback comes with okta."""
        _inject_state(db, idp="keycloak")
        with patch.object(sso_module, "create_oidc_provider", return_value=mock_provider):
            resp = client.get(
                "/api/v1/auth/sso/okta/callback",
                params={"code": "auth-code-123", "state": "test-state"},
            )
        # okta provider creation raises NotImplementedError
        assert resp.status_code == 400
        assert "mismatch" in resp.json()["detail"].lower()


# ─────────────────────────────────────────────────────────────────────────────
# Callback — Groups Integration
# ─────────────────────────────────────────────────────────────────────────────


class TestCallbackGroups:
    """Tests for group-fetching + policy-resolution paths in sso_callback.

    Covers the WS-A4 integration: GoogleProvider.fetch_user_groups() →
    GroupPolicyMapper.resolve() → JWT groups/roles claims.
    """

    def _make_google_provider_mock(self, *, groups=None, fetch_raises=False):
        """Build a mock that quacks like GoogleProvider (with fetch_user_groups).

        Uses spec=GoogleProvider so isinstance() checks pass in sso_callback.
        """
        from app.services.providers.google import GoogleProvider

        m = AsyncMock(spec=GoogleProvider)
        m.get_authorization_url = AsyncMock(return_value="https://accounts.google.com/o/oauth2/v2/auth?state=abc")
        m.exchange_code = AsyncMock(
            return_value=OIDCTokens(
                id_token="mock.id.token",
                access_token="mock.access.token",
                refresh_token="mock.refresh.token",
            )
        )
        m.validate_token = AsyncMock(
            return_value=OIDCClaims(
                sub="google-user-001",
                email="sarah@acme.com",
                name="Sarah Chen",
                groups=[],
                roles=[],
                issuer="https://accounts.google.com",
            )
        )
        if fetch_raises:
            m.fetch_user_groups = AsyncMock(side_effect=Exception("Directory API down"))
        else:
            m.fetch_user_groups = AsyncMock(return_value=groups or [])
        m.logout_url = AsyncMock(return_value="https://myaccount.google.com")
        return m

    @pytest.fixture(autouse=True)
    def reset_group_mapper(self):
        """Reset the cached _group_mapper singleton between tests."""
        sso_module._group_mapper = None
        yield
        sso_module._group_mapper = None

    def _google_callback(self, client, mock_provider, db, *, fetch_groups=True, extra_patches=None):
        """Helper: run a Google SSO callback with given mocks."""
        _inject_state(db, idp="google", redirect_uri="http://localhost:8000/api/v1/auth/sso/google/callback")
        env_val = "true" if fetch_groups else "false"
        patches = [
            patch.object(sso_module, "create_oidc_provider", return_value=mock_provider),
            patch.dict(os.environ, {"IDP_FETCH_GROUPS": env_val}),
        ]
        if extra_patches:
            patches.extend(extra_patches)

        import contextlib
        with contextlib.ExitStack() as stack:
            for p in patches:
                stack.enter_context(p)
            return client.get(
                "/api/v1/auth/sso/google/callback",
                params={"code": "auth-code", "state": "test-state"},
            )

    def test_google_callback_populates_jwt_groups(self, client, db):
        """Google callback with fetch_groups=True populates JWT groups claim."""
        mock_prov = self._make_google_provider_mock(
            groups=["engineering@acme.com", "all@acme.com"],
        )
        resp = self._google_callback(client, mock_prov, db)

        assert resp.status_code == 200
        decoded = pyjwt.decode(resp.json()["token"], settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert "engineering@acme.com" in decoded["groups"]
        assert "all@acme.com" in decoded["groups"]

    def test_google_callback_policy_roles_in_jwt(self, client, db):
        """GroupPolicyMapper.resolve() merges roles into JWT roles claim."""
        mock_prov = self._make_google_provider_mock(groups=["engineering@acme.com"])

        from app.services.group_policy import GroupPolicyMapper, GroupPolicy
        mapper = GroupPolicyMapper([
            GroupPolicy(group="engineering@acme.com", role="engineer", default_permissions=["github:repos:read"]),
        ])

        resp = self._google_callback(client, mock_prov, db, extra_patches=[
            patch.object(sso_module, "_get_group_policy_mapper", return_value=mapper),
        ])

        assert resp.status_code == 200
        decoded = pyjwt.decode(resp.json()["token"], settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert "engineer" in decoded["roles"]

    def test_group_fetch_failure_is_fail_open(self, client, db):
        """Group fetch failure: callback succeeds with groups=[]."""
        mock_prov = self._make_google_provider_mock(fetch_raises=True)
        resp = self._google_callback(client, mock_prov, db)

        assert resp.status_code == 200
        decoded = pyjwt.decode(resp.json()["token"], settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert decoded["groups"] == []

    def test_fetch_groups_false_skips_directory_call(self, client, db):
        """fetch_groups=False: fetch_user_groups is NOT called."""
        mock_prov = self._make_google_provider_mock(groups=["should-not-appear@acme.com"])
        resp = self._google_callback(client, mock_prov, db, fetch_groups=False)

        assert resp.status_code == 200
        mock_prov.fetch_user_groups.assert_not_called()

    def test_keycloak_preserves_groups_from_id_token(self, client, mock_provider, db):
        """Keycloak callback preserves groups from ID token claims."""
        mock_provider.validate_token = AsyncMock(
            return_value=OIDCClaims(
                sub="kc-user-001",
                email="sarah@acme.com",
                name="Sarah Chen",
                groups=["acme-org", "admin-org"],
                roles=["user"],
                issuer="https://keycloak:8080/realms/deepsecure",
            )
        )
        _inject_state(db, idp="keycloak")

        with patch.object(sso_module, "create_oidc_provider", return_value=mock_provider):
            resp = client.get(
                "/api/v1/auth/sso/keycloak/callback",
                params={"code": "auth-code", "state": "test-state"},
            )

        assert resp.status_code == 200
        decoded = pyjwt.decode(resp.json()["token"], settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert "acme-org" in decoded["groups"]
        assert "admin-org" in decoded["groups"]

    def test_missing_yaml_uses_empty_mapper(self, client, db):
        """Missing group_policies.yaml: no crash, no extra roles added."""
        mock_prov = self._make_google_provider_mock(groups=["unknown-group@acme.com"])

        resp = self._google_callback(client, mock_prov, db, extra_patches=[
            patch("pathlib.Path.exists", return_value=False),
        ])

        assert resp.status_code == 200
        decoded = pyjwt.decode(resp.json()["token"], settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert "unknown-group@acme.com" in decoded["groups"]

    def test_role_deduplication(self, client, db):
        """Duplicate roles from legacy map + policy mapper are deduplicated."""
        mock_prov = self._make_google_provider_mock(groups=["acme-org"])
        mock_prov.validate_token = AsyncMock(
            return_value=OIDCClaims(
                sub="google-user-001",
                email="sarah@acme.com",
                groups=[],
                roles=["user"],
                issuer="https://accounts.google.com",
            )
        )

        from app.services.group_policy import GroupPolicyMapper, GroupPolicy
        mapper = GroupPolicyMapper([
            GroupPolicy(group="acme-org", role="user", default_permissions=[]),
        ])

        resp = self._google_callback(client, mock_prov, db, extra_patches=[
            patch.object(sso_module, "_get_group_policy_mapper", return_value=mapper),
        ])

        assert resp.status_code == 200
        decoded = pyjwt.decode(resp.json()["token"], settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert decoded["roles"].count("user") == 1

    def test_multiple_group_policies_merge(self, client, db):
        """Multiple matched groups: all policy roles and permissions merged."""
        mock_prov = self._make_google_provider_mock(
            groups=["engineering@acme.com", "security@acme.com"],
        )

        from app.services.group_policy import GroupPolicyMapper, GroupPolicy
        mapper = GroupPolicyMapper([
            GroupPolicy(group="engineering@acme.com", role="engineer", default_permissions=["github:repos:read"]),
            GroupPolicy(group="security@acme.com", role="security-analyst", default_permissions=["vault:secrets:read"]),
        ])

        resp = self._google_callback(client, mock_prov, db, extra_patches=[
            patch.object(sso_module, "_get_group_policy_mapper", return_value=mapper),
        ])

        assert resp.status_code == 200
        decoded = pyjwt.decode(resp.json()["token"], settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert "engineer" in decoded["roles"]
        assert "security-analyst" in decoded["roles"]

    def test_policy_default_permissions_set(self, client, db):
        """Policy default_permissions are set on user data (verified via roles)."""
        mock_prov = self._make_google_provider_mock(groups=["engineering@acme.com"])

        from app.services.group_policy import GroupPolicyMapper, GroupPolicy
        mapper = GroupPolicyMapper([
            GroupPolicy(group="engineering@acme.com", role="engineer", default_permissions=["github:repos:read", "jira:issues:read"]),
        ])

        resp = self._google_callback(client, mock_prov, db, extra_patches=[
            patch.object(sso_module, "_get_group_policy_mapper", return_value=mapper),
        ])

        assert resp.status_code == 200
        decoded = pyjwt.decode(resp.json()["token"], settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert "engineer" in decoded["roles"]


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


class TestPendingOAuthState:
    def test_not_expired(self, db):
        p = _inject_state(db, state="not-expired")
        assert p.is_expired is False

    def test_expired(self, db):
        p = _inject_state(
            db,
            state="expired-state",
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=5),
        )
        assert p.is_expired is True

    def test_post_login_redirect_default_none(self, db):
        p = _inject_state(db, state="no-redirect")
        assert p.post_login_redirect is None

    def test_post_login_redirect_set(self, db):
        p = _inject_state(
            db,
            state="with-redirect",
            post_login_redirect="http://localhost:9876/done",
        )
        assert p.post_login_redirect == "http://localhost:9876/done"

    def test_cleanup_removes_expired(self, db):
        _inject_state(
            db,
            state="old",
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=10),
        )
        _inject_state(db, state="new")
        sso_module._cleanup_expired(db)
        assert _get_pending_state(db, "old") is None
        assert _get_pending_state(db, "new") is not None


# ─────────────────────────────────────────────────────────────────────────────
# Refresh — helpers
# ─────────────────────────────────────────────────────────────────────────────


def _refresh_jwt(
    sub: str = "user@acme.com",
    session_id: str = "usess-oldoldoldold0001",
    idp: str = "google",
    groups: list | None = None,
    roles: list | None = None,
    organization_id: str | None = "org-acme",
    exp_delta: timedelta | None = None,
    include_exp: bool = True,
) -> str:
    """Create a signed session JWT for refresh testing."""
    now = datetime.now(timezone.utc)
    payload: dict = {
        "sub": sub,
        "session_id": session_id,
        "idp": idp,
        "groups": groups or [],
        "roles": roles or [],
        "organization_id": organization_id,
        "iat": now,
    }
    if include_exp:
        payload["exp"] = now + (exp_delta if exp_delta is not None else timedelta(hours=24))
    return pyjwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def _mock_session_svc(
    session_exists: bool = True,
    refresh_token: str | None = "stored-refresh-token",
    store_raises: bool = False,
    revoke_raises: bool = False,
):
    svc = MagicMock()
    svc.get_by_session.return_value = MagicMock() if session_exists else None
    if session_exists and refresh_token:
        svc.get_decrypted_tokens.return_value = {
            "access_token": "old-access",
            "refresh_token": refresh_token,
        }
    elif session_exists:
        svc.get_decrypted_tokens.return_value = {
            "access_token": "old-access",
            "refresh_token": None,
        }
    else:
        svc.get_decrypted_tokens.return_value = None
    svc.store.side_effect = Exception("DB write") if store_raises else None
    if not store_raises:
        svc.store.return_value = MagicMock()
    svc.revoke.side_effect = Exception("DB revoke") if revoke_raises else None
    if not revoke_raises:
        svc.revoke.return_value = True
    return svc


def _mock_refresh_provider(
    refresh_ok: bool = True,
    new_id_token: str = "new-id",
    new_access: str = "new-access",
    new_refresh: str | None = "new-refresh",
    refresh_error: Exception | None = None,
):
    prov = AsyncMock()
    if refresh_ok:
        prov.refresh_token.return_value = OIDCTokens(
            id_token=new_id_token,
            access_token=new_access,
            refresh_token=new_refresh,
        )
    else:
        prov.refresh_token.side_effect = refresh_error or OIDCError(
            "Token refresh failed: 400", error_code="refresh_failed"
        )
    prov.validate_token.return_value = OIDCClaims(
        sub="user@acme.com", email="user@acme.com", email_verified=True,
    )
    return prov


# ─────────────────────────────────────────────────────────────────────────────
# TestDecodeJwtForRefresh — unit tests for the helper function
# ─────────────────────────────────────────────────────────────────────────────


class TestDecodeJwtForRefresh:
    """Direct tests for ``_decode_jwt_for_refresh()`` (module-level helper)."""

    def test_valid_non_expired_jwt(self):
        token = _refresh_jwt()
        claims = _decode_jwt_for_refresh(f"Bearer {token}")
        assert claims["sub"] == "user@acme.com"
        assert claims["session_id"] == "usess-oldoldoldold0001"

    def test_expired_within_grace_30min(self):
        token = _refresh_jwt(exp_delta=timedelta(minutes=-30))
        claims = _decode_jwt_for_refresh(f"Bearer {token}")
        assert claims["sub"] == "user@acme.com"

    def test_expired_within_grace_59min(self):
        token = _refresh_jwt(exp_delta=timedelta(minutes=-59))
        claims = _decode_jwt_for_refresh(f"Bearer {token}")
        assert claims["sub"] == "user@acme.com"

    def test_expired_beyond_grace_2h(self):
        token = _refresh_jwt(exp_delta=timedelta(hours=-2))
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            _decode_jwt_for_refresh(f"Bearer {token}")
        assert exc_info.value.status_code == 401
        assert "grace window" in exc_info.value.detail

    def test_none_authorization(self):
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            _decode_jwt_for_refresh(None)
        assert exc_info.value.status_code == 401

    def test_empty_authorization(self):
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            _decode_jwt_for_refresh("")
        assert exc_info.value.status_code == 401

    def test_wrong_prefix(self):
        from fastapi import HTTPException

        token = _refresh_jwt()
        with pytest.raises(HTTPException) as exc_info:
            _decode_jwt_for_refresh(f"Token {token}")
        assert exc_info.value.status_code == 401

    def test_malformed_jwt(self):
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            _decode_jwt_for_refresh("Bearer not.a.jwt")
        assert exc_info.value.status_code == 401

    def test_wrong_signing_key(self):
        from fastapi import HTTPException

        payload = {
            "sub": "user@acme.com",
            "session_id": "usess-123",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        }
        token = pyjwt.encode(payload, "wrong-key", algorithm="HS256")
        with pytest.raises(HTTPException) as exc_info:
            _decode_jwt_for_refresh(f"Bearer {token}")
        assert exc_info.value.status_code == 401

    def test_jwt_without_exp_claim(self):
        token = _refresh_jwt(include_exp=False)
        claims = _decode_jwt_for_refresh(f"Bearer {token}")
        assert claims["sub"] == "user@acme.com"


# ─────────────────────────────────────────────────────────────────────────────
# TestRefresh — endpoint tests via TestClient
# ─────────────────────────────────────────────────────────────────────────────


class TestRefresh:
    """Tests for ``POST /api/v1/auth/sso/refresh`` endpoint."""

    # --- Happy path (7) ---

    def test_valid_jwt_returns_200(self, client):
        token = _refresh_jwt()
        svc = _mock_session_svc()
        prov = _mock_refresh_provider()
        with patch(_IDP_SESSION_SVC_PATCH, return_value=svc), \
             patch(_CREATE_PROVIDER_PATCH, return_value=prov):
            resp = client.post("/api/v1/auth/sso/refresh", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert "token" in data
        assert "expires_in" in data
        assert "idp" in data
        assert "refreshed_at" in data

    def test_new_session_id_differs(self, client):
        token = _refresh_jwt(session_id="usess-original-sess")
        svc = _mock_session_svc()
        prov = _mock_refresh_provider()
        with patch(_IDP_SESSION_SVC_PATCH, return_value=svc), \
             patch(_CREATE_PROVIDER_PATCH, return_value=prov):
            resp = client.post("/api/v1/auth/sso/refresh", headers={"Authorization": f"Bearer {token}"})
        new_claims = pyjwt.decode(resp.json()["token"], settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert new_claims["session_id"] != "usess-original-sess"
        assert new_claims["session_id"].startswith("usess-")

    def test_preserves_sub_groups_roles_org_idp(self, client):
        token = _refresh_jwt(
            sub="sarah@acme.com",
            groups=["eng@acme.com"], roles=["engineer"],
            organization_id="org-acme", idp="google",
        )
        svc = _mock_session_svc()
        prov = _mock_refresh_provider()
        with patch(_IDP_SESSION_SVC_PATCH, return_value=svc), \
             patch(_CREATE_PROVIDER_PATCH, return_value=prov):
            resp = client.post("/api/v1/auth/sso/refresh", headers={"Authorization": f"Bearer {token}"})
        c = pyjwt.decode(resp.json()["token"], settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert c["groups"] == ["eng@acme.com"]
        assert c["roles"] == ["engineer"]
        assert c["organization_id"] == "org-acme"
        assert c["idp"] == "google"

    def test_fresh_exp_and_iat(self, client):
        token = _refresh_jwt()
        svc = _mock_session_svc()
        prov = _mock_refresh_provider()
        before = datetime.now(timezone.utc)
        with patch(_IDP_SESSION_SVC_PATCH, return_value=svc), \
             patch(_CREATE_PROVIDER_PATCH, return_value=prov):
            resp = client.post("/api/v1/auth/sso/refresh", headers={"Authorization": f"Bearer {token}"})
        c = pyjwt.decode(resp.json()["token"], settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        exp = datetime.fromtimestamp(c["exp"], tz=timezone.utc)
        iat = datetime.fromtimestamp(c["iat"], tz=timezone.utc)
        assert exp > before + timedelta(hours=23)
        assert iat >= before - timedelta(seconds=5)

    def test_expires_in_is_86400(self, client):
        token = _refresh_jwt()
        svc = _mock_session_svc()
        prov = _mock_refresh_provider()
        with patch(_IDP_SESSION_SVC_PATCH, return_value=svc), \
             patch(_CREATE_PROVIDER_PATCH, return_value=prov):
            resp = client.post("/api/v1/auth/sso/refresh", headers={"Authorization": f"Bearer {token}"})
        assert resp.json()["expires_in"] == 86400

    def test_idp_field_matches_input(self, client):
        token = _refresh_jwt(idp="google")
        svc = _mock_session_svc()
        prov = _mock_refresh_provider()
        with patch(_IDP_SESSION_SVC_PATCH, return_value=svc), \
             patch(_CREATE_PROVIDER_PATCH, return_value=prov):
            resp = client.post("/api/v1/auth/sso/refresh", headers={"Authorization": f"Bearer {token}"})
        assert resp.json()["idp"] == "google"

    def test_refreshed_at_is_iso_8601(self, client):
        token = _refresh_jwt()
        svc = _mock_session_svc()
        prov = _mock_refresh_provider()
        with patch(_IDP_SESSION_SVC_PATCH, return_value=svc), \
             patch(_CREATE_PROVIDER_PATCH, return_value=prov):
            resp = client.post("/api/v1/auth/sso/refresh", headers={"Authorization": f"Bearer {token}"})
        ts = resp.json()["refreshed_at"]
        parsed = datetime.fromisoformat(ts)
        assert parsed.year >= 2026

    # --- Grace window (2) ---

    def test_expired_within_grace_returns_200(self, client):
        token = _refresh_jwt(exp_delta=timedelta(minutes=-30))
        svc = _mock_session_svc()
        prov = _mock_refresh_provider()
        with patch(_IDP_SESSION_SVC_PATCH, return_value=svc), \
             patch(_CREATE_PROVIDER_PATCH, return_value=prov):
            resp = client.post("/api/v1/auth/sso/refresh", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    def test_expired_beyond_grace_returns_401(self, client):
        token = _refresh_jwt(exp_delta=timedelta(hours=-2))
        resp = client.post("/api/v1/auth/sso/refresh", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 401

    # --- Error paths (5) ---

    def test_missing_auth_header_returns_401(self, client):
        resp = client.post("/api/v1/auth/sso/refresh")
        assert resp.status_code == 401

    def test_garbage_jwt_returns_401(self, client):
        resp = client.post("/api/v1/auth/sso/refresh", headers={"Authorization": "Bearer garbage.token.here"})
        assert resp.status_code == 401

    def test_no_stored_session_returns_404(self, client):
        token = _refresh_jwt()
        svc = _mock_session_svc(session_exists=False)
        with patch(_IDP_SESSION_SVC_PATCH, return_value=svc):
            resp = client.post("/api/v1/auth/sso/refresh", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 404
        assert "No refresh session" in resp.json()["detail"]

    def test_no_refresh_token_returns_404(self, client):
        token = _refresh_jwt()
        svc = _mock_session_svc(refresh_token=None)
        with patch(_IDP_SESSION_SVC_PATCH, return_value=svc):
            resp = client.post("/api/v1/auth/sso/refresh", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 404
        assert "No refresh token" in resp.json()["detail"]

    def test_idp_refresh_failure_returns_502(self, client):
        token = _refresh_jwt()
        svc = _mock_session_svc()
        prov = _mock_refresh_provider(refresh_ok=False)
        with patch(_IDP_SESSION_SVC_PATCH, return_value=svc), \
             patch(_CREATE_PROVIDER_PATCH, return_value=prov):
            resp = client.post("/api/v1/auth/sso/refresh", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 502
        assert "IdP refresh failed" in resp.json()["detail"]

    # --- Session lifecycle (3) ---

    def test_old_session_revoked_after_refresh(self, client):
        token = _refresh_jwt(session_id="usess-revoke-me")
        svc = _mock_session_svc()
        prov = _mock_refresh_provider()
        with patch(_IDP_SESSION_SVC_PATCH, return_value=svc), \
             patch(_CREATE_PROVIDER_PATCH, return_value=prov):
            resp = client.post("/api/v1/auth/sso/refresh", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        svc.revoke.assert_called_once_with("usess-revoke-me")

    def test_new_session_stored_after_refresh(self, client):
        token = _refresh_jwt()
        svc = _mock_session_svc()
        prov = _mock_refresh_provider()
        with patch(_IDP_SESSION_SVC_PATCH, return_value=svc), \
             patch(_CREATE_PROVIDER_PATCH, return_value=prov):
            resp = client.post("/api/v1/auth/sso/refresh", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        svc.store.assert_called_once()
        kwargs = svc.store.call_args.kwargs
        assert kwargs["session_id"].startswith("usess-")
        assert kwargs["session_id"] != "usess-oldoldoldold0001"

    def test_works_with_keycloak_idp(self, client):
        token = _refresh_jwt(idp="keycloak")
        svc = _mock_session_svc()
        prov = _mock_refresh_provider()
        with patch(_IDP_SESSION_SVC_PATCH, return_value=svc), \
             patch(_CREATE_PROVIDER_PATCH, return_value=prov):
            resp = client.post("/api/v1/auth/sso/refresh", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json()["idp"] == "keycloak"
