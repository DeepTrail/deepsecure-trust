"""Tests for POST /api/v1/auth/sso/refresh endpoint (WS-B4).

Covers:
- Happy path: valid JWT + stored refresh token → 200 with new session
- Grace window: expired JWT within 1h → 200, beyond 1h → 401
- Auth errors: missing header, malformed JWT, missing session_id → 401
- Session errors: no stored session → 404, no refresh token → 404
- Provider errors: IdP refresh failure → 502
- Security: new session_id minted, old session revoked, no IdP tokens in response
- Claim preservation: groups, roles, organization_id, idp, sub carried forward
- ID token validation: updated claims when new ID token is present
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import jwt as pyjwt
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.api.v1.endpoints.sso import REFRESH_GRACE_WINDOW_SECONDS
from app.services.idp_service import OIDCClaims, OIDCError, OIDCTokens

# IdPSessionService is imported locally inside sso_refresh(), so we patch
# the service module, not the endpoint module.
_IDP_SESSION_SVC_PATCH = "app.services.idp_session_service.IdPSessionService"
_CREATE_PROVIDER_PATCH = "app.api.v1.endpoints.sso.create_oidc_provider"


@pytest.fixture
def client():
    return TestClient(app)


def _make_jwt(
    sub: str = "user@acme.com",
    session_id: str = "usess-oldoldoldold0001",
    idp: str = "google",
    groups: list | None = None,
    roles: list | None = None,
    organization_id: str | None = "org-acme",
    exp_delta: timedelta | None = None,
) -> str:
    """Create a signed session JWT for testing."""
    now = datetime.now(timezone.utc)
    exp = now + (exp_delta if exp_delta is not None else timedelta(hours=24))
    payload = {
        "sub": sub,
        "session_id": session_id,
        "idp": idp,
        "groups": groups or [],
        "roles": roles or [],
        "organization_id": organization_id,
        "exp": exp,
        "iat": now,
    }
    return pyjwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def _mock_idp_session_service(
    session_exists: bool = True,
    refresh_token: str | None = "stored-refresh-token",
    store_raises: bool = False,
    revoke_raises: bool = False,
):
    """Return a mock IdPSessionService with configurable behavior."""
    svc = MagicMock()
    if session_exists:
        svc.get_by_session.return_value = MagicMock()
    else:
        svc.get_by_session.return_value = None

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

    if store_raises:
        svc.store.side_effect = Exception("DB write failed")
    else:
        svc.store.return_value = MagicMock()

    if revoke_raises:
        svc.revoke.side_effect = Exception("DB revoke failed")
    else:
        svc.revoke.return_value = True

    return svc


def _mock_provider(
    refresh_success: bool = True,
    new_id_token: str = "new-id-token",
    new_access_token: str = "new-access-token",
    new_refresh_token: str | None = "new-refresh-token",
    refresh_error: Exception | None = None,
    validate_token_result: OIDCClaims | None = None,
    validate_raises: bool = False,
):
    """Return a mock OIDC provider with configurable refresh behavior."""
    provider = AsyncMock()
    if refresh_success:
        provider.refresh_token.return_value = OIDCTokens(
            id_token=new_id_token,
            access_token=new_access_token,
            refresh_token=new_refresh_token,
        )
    else:
        provider.refresh_token.side_effect = refresh_error or OIDCError(
            "Token refresh failed: 400", error_code="refresh_failed"
        )

    if validate_token_result:
        provider.validate_token.return_value = validate_token_result
    elif validate_raises:
        provider.validate_token.side_effect = Exception("validation error")
    else:
        provider.validate_token.return_value = OIDCClaims(
            sub="user@acme.com",
            email="user@acme.com",
            email_verified=True,
        )

    return provider


def _post_refresh(client, token: str | None = None, header_value: str | None = None):
    """Call POST /api/v1/auth/sso/refresh with the given auth."""
    headers = {}
    if header_value is not None:
        headers["Authorization"] = header_value
    elif token is not None:
        headers["Authorization"] = f"Bearer {token}"
    return client.post("/api/v1/auth/sso/refresh", headers=headers)


# ============================================================================
# Happy path
# ============================================================================


class TestRefreshHappyPath:
    def test_valid_jwt_returns_200(self, client):
        token = _make_jwt()
        svc = _mock_idp_session_service()
        prov = _mock_provider()

        with (
            patch(_IDP_SESSION_SVC_PATCH, return_value=svc),
            patch(_CREATE_PROVIDER_PATCH, return_value=prov),
        ):
            resp = _post_refresh(client, token)

        assert resp.status_code == 200
        data = resp.json()
        assert "token" in data
        assert data["expires_in"] == 86400
        assert data["idp"] == "google"
        assert "refreshed_at" in data

    def test_new_jwt_has_different_session_id(self, client):
        token = _make_jwt(session_id="usess-original")
        svc = _mock_idp_session_service()
        prov = _mock_provider()

        with (
            patch(_IDP_SESSION_SVC_PATCH, return_value=svc),
            patch(_CREATE_PROVIDER_PATCH, return_value=prov),
        ):
            resp = _post_refresh(client, token)

        new_jwt = resp.json()["token"]
        claims = pyjwt.decode(new_jwt, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert claims["session_id"] != "usess-original"
        assert claims["session_id"].startswith("usess-")

    def test_preserves_groups_roles_org_idp(self, client):
        token = _make_jwt(
            groups=["eng@acme.com", "all@acme.com"],
            roles=["engineer", "user"],
            organization_id="org-123",
            idp="google",
        )
        svc = _mock_idp_session_service()
        prov = _mock_provider()

        with (
            patch(_IDP_SESSION_SVC_PATCH, return_value=svc),
            patch(_CREATE_PROVIDER_PATCH, return_value=prov),
        ):
            resp = _post_refresh(client, token)

        new_jwt = resp.json()["token"]
        claims = pyjwt.decode(new_jwt, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert claims["groups"] == ["eng@acme.com", "all@acme.com"]
        assert claims["roles"] == ["engineer", "user"]
        assert claims["organization_id"] == "org-123"
        assert claims["idp"] == "google"

    def test_new_jwt_has_fresh_exp(self, client):
        token = _make_jwt()
        svc = _mock_idp_session_service()
        prov = _mock_provider()

        before = datetime.now(timezone.utc)
        with (
            patch(_IDP_SESSION_SVC_PATCH, return_value=svc),
            patch(_CREATE_PROVIDER_PATCH, return_value=prov),
        ):
            resp = _post_refresh(client, token)

        new_jwt = resp.json()["token"]
        claims = pyjwt.decode(new_jwt, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        exp = datetime.fromtimestamp(claims["exp"], tz=timezone.utc)
        assert exp > before + timedelta(hours=23)

    def test_works_with_keycloak_idp(self, client):
        token = _make_jwt(idp="keycloak")
        svc = _mock_idp_session_service()
        prov = _mock_provider()

        with (
            patch(_IDP_SESSION_SVC_PATCH, return_value=svc),
            patch(_CREATE_PROVIDER_PATCH, return_value=prov),
        ):
            resp = _post_refresh(client, token)

        assert resp.status_code == 200
        assert resp.json()["idp"] == "keycloak"


# ============================================================================
# Grace window
# ============================================================================


class TestRefreshGraceWindow:
    def test_expired_within_grace_returns_200(self, client):
        token = _make_jwt(exp_delta=timedelta(minutes=-30))
        svc = _mock_idp_session_service()
        prov = _mock_provider()

        with (
            patch(_IDP_SESSION_SVC_PATCH, return_value=svc),
            patch(_CREATE_PROVIDER_PATCH, return_value=prov),
        ):
            resp = _post_refresh(client, token)

        assert resp.status_code == 200

    def test_expired_beyond_grace_returns_401(self, client):
        token = _make_jwt(exp_delta=timedelta(hours=-2))
        resp = _post_refresh(client, token)
        assert resp.status_code == 401
        assert "grace window" in resp.json()["detail"]

    def test_expired_at_exact_boundary_returns_401(self, client):
        token = _make_jwt(
            exp_delta=timedelta(seconds=-(REFRESH_GRACE_WINDOW_SECONDS + 60))
        )
        resp = _post_refresh(client, token)
        assert resp.status_code == 401


# ============================================================================
# Auth errors (401)
# ============================================================================


class TestRefreshAuthErrors:
    def test_missing_authorization_header(self, client):
        resp = client.post("/api/v1/auth/sso/refresh")
        assert resp.status_code == 401
        assert "Missing or invalid" in resp.json()["detail"]

    def test_non_bearer_authorization(self, client):
        resp = _post_refresh(client, header_value="Basic dXNlcjpwYXNz")
        assert resp.status_code == 401

    def test_malformed_jwt(self, client):
        resp = _post_refresh(client, header_value="Bearer not.a.valid.jwt")
        assert resp.status_code == 401

    def test_jwt_signed_with_wrong_key(self, client):
        payload = {
            "sub": "user@acme.com",
            "session_id": "usess-123",
            "idp": "google",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        }
        token = pyjwt.encode(payload, "wrong-secret-key", algorithm="HS256")
        resp = _post_refresh(client, token)
        assert resp.status_code == 401

    def test_jwt_missing_session_id(self, client):
        now = datetime.now(timezone.utc)
        payload = {
            "sub": "user@acme.com",
            "idp": "google",
            "exp": now + timedelta(hours=1),
            "iat": now,
        }
        token = pyjwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        resp = _post_refresh(client, token)
        assert resp.status_code == 401
        assert "session_id" in resp.json()["detail"]


# ============================================================================
# Session errors (404)
# ============================================================================


class TestRefreshSessionErrors:
    def test_no_stored_idp_session(self, client):
        token = _make_jwt()
        svc = _mock_idp_session_service(session_exists=False)

        with patch(_IDP_SESSION_SVC_PATCH, return_value=svc):
            resp = _post_refresh(client, token)

        assert resp.status_code == 404
        assert "No refresh session" in resp.json()["detail"]

    def test_no_refresh_token_in_stored_session(self, client):
        token = _make_jwt()
        svc = _mock_idp_session_service(refresh_token=None)

        with patch(_IDP_SESSION_SVC_PATCH, return_value=svc):
            resp = _post_refresh(client, token)

        assert resp.status_code == 404
        assert "No refresh token" in resp.json()["detail"]


# ============================================================================
# Provider errors (502)
# ============================================================================


class TestRefreshProviderErrors:
    def test_idp_refresh_oidc_error(self, client):
        token = _make_jwt()
        svc = _mock_idp_session_service()
        prov = _mock_provider(
            refresh_success=False,
            refresh_error=OIDCError("Token refresh failed: 400", error_code="refresh_failed"),
        )

        with (
            patch(_IDP_SESSION_SVC_PATCH, return_value=svc),
            patch(_CREATE_PROVIDER_PATCH, return_value=prov),
        ):
            resp = _post_refresh(client, token)

        assert resp.status_code == 502
        assert "IdP refresh failed" in resp.json()["detail"]

    def test_idp_refresh_network_error(self, client):
        import httpx

        token = _make_jwt()
        svc = _mock_idp_session_service()
        prov = _mock_provider(
            refresh_success=False,
            refresh_error=httpx.ConnectError("Connection refused"),
        )

        with (
            patch(_IDP_SESSION_SVC_PATCH, return_value=svc),
            patch(_CREATE_PROVIDER_PATCH, return_value=prov),
        ):
            resp = _post_refresh(client, token)

        assert resp.status_code == 502


# ============================================================================
# Security: session rotation + no token leaks
# ============================================================================


class TestRefreshSecurity:
    def test_old_session_revoked(self, client):
        token = _make_jwt(session_id="usess-old-session-id")
        svc = _mock_idp_session_service()
        prov = _mock_provider()

        with (
            patch(_IDP_SESSION_SVC_PATCH, return_value=svc),
            patch(_CREATE_PROVIDER_PATCH, return_value=prov),
        ):
            resp = _post_refresh(client, token)

        assert resp.status_code == 200
        svc.revoke.assert_called_once_with("usess-old-session-id")

    def test_new_session_stored(self, client):
        token = _make_jwt()
        svc = _mock_idp_session_service()
        prov = _mock_provider()

        with (
            patch(_IDP_SESSION_SVC_PATCH, return_value=svc),
            patch(_CREATE_PROVIDER_PATCH, return_value=prov),
        ):
            resp = _post_refresh(client, token)

        assert resp.status_code == 200
        svc.store.assert_called_once()
        store_kwargs = svc.store.call_args.kwargs
        assert store_kwargs["session_id"].startswith("usess-")
        assert store_kwargs["session_id"] != "usess-oldoldoldold0001"
        assert store_kwargs["idp"] == "google"

    def test_no_idp_tokens_in_response(self, client):
        token = _make_jwt()
        svc = _mock_idp_session_service()
        prov = _mock_provider()

        with (
            patch(_IDP_SESSION_SVC_PATCH, return_value=svc),
            patch(_CREATE_PROVIDER_PATCH, return_value=prov),
        ):
            resp = _post_refresh(client, token)

        data = resp.json()
        body_str = str(data)
        assert "new-access-token" not in body_str
        assert "new-refresh-token" not in body_str
        assert "stored-refresh-token" not in body_str

    def test_refresh_token_rotation(self, client):
        token = _make_jwt()
        svc = _mock_idp_session_service()
        prov = _mock_provider(new_refresh_token="rotated-refresh-token")

        with (
            patch(_IDP_SESSION_SVC_PATCH, return_value=svc),
            patch(_CREATE_PROVIDER_PATCH, return_value=prov),
        ):
            resp = _post_refresh(client, token)

        assert resp.status_code == 200
        stored_tokens = svc.store.call_args.kwargs["tokens"]
        assert stored_tokens.refresh_token == "rotated-refresh-token"


# ============================================================================
# Fail-open: store/revoke failures don't block JWT issuance
# ============================================================================


class TestRefreshFailOpen:
    def test_store_failure_still_returns_jwt(self, client):
        token = _make_jwt()
        svc = _mock_idp_session_service(store_raises=True)
        prov = _mock_provider()

        with (
            patch(_IDP_SESSION_SVC_PATCH, return_value=svc),
            patch(_CREATE_PROVIDER_PATCH, return_value=prov),
        ):
            resp = _post_refresh(client, token)

        assert resp.status_code == 200
        assert "token" in resp.json()

    def test_revoke_failure_still_returns_jwt(self, client):
        token = _make_jwt()
        svc = _mock_idp_session_service(revoke_raises=True)
        prov = _mock_provider()

        with (
            patch(_IDP_SESSION_SVC_PATCH, return_value=svc),
            patch(_CREATE_PROVIDER_PATCH, return_value=prov),
        ):
            resp = _post_refresh(client, token)

        assert resp.status_code == 200


# ============================================================================
# ID token validation on refresh
# ============================================================================


class TestRefreshIdTokenValidation:
    def test_updated_email_from_new_id_token(self, client):
        token = _make_jwt(sub="old@acme.com")
        svc = _mock_idp_session_service()
        validated_claims = OIDCClaims(
            sub="new-sub",
            email="new@acme.com",
            email_verified=True,
        )
        prov = _mock_provider(validate_token_result=validated_claims)

        with (
            patch(_IDP_SESSION_SVC_PATCH, return_value=svc),
            patch(_CREATE_PROVIDER_PATCH, return_value=prov),
        ):
            resp = _post_refresh(client, token)

        new_jwt = resp.json()["token"]
        claims = pyjwt.decode(new_jwt, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert claims["sub"] == "new@acme.com"

    def test_validation_failure_falls_back_to_old_claims(self, client):
        token = _make_jwt(sub="original@acme.com")
        svc = _mock_idp_session_service()
        prov = _mock_provider(validate_raises=True)

        with (
            patch(_IDP_SESSION_SVC_PATCH, return_value=svc),
            patch(_CREATE_PROVIDER_PATCH, return_value=prov),
        ):
            resp = _post_refresh(client, token)

        new_jwt = resp.json()["token"]
        claims = pyjwt.decode(new_jwt, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert claims["sub"] == "original@acme.com"

    def test_no_id_token_uses_old_claims(self, client):
        token = _make_jwt(sub="user@acme.com", groups=["eng@acme.com"])
        svc = _mock_idp_session_service()
        prov = _mock_provider(new_id_token="")

        with (
            patch(_IDP_SESSION_SVC_PATCH, return_value=svc),
            patch(_CREATE_PROVIDER_PATCH, return_value=prov),
        ):
            resp = _post_refresh(client, token)

        new_jwt = resp.json()["token"]
        claims = pyjwt.decode(new_jwt, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert claims["sub"] == "user@acme.com"
        assert claims["groups"] == ["eng@acme.com"]
