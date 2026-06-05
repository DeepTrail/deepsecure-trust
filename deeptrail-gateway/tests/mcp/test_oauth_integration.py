"""
OAuth 2.1 integration tests for dual-token detection (WS-C4, C5, C8).

Tests the full middleware stack with both DeepSecure HS256 and OAuth RS256 tokens.
"""

import os
import time
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jose import jwt as jose_jwt
from starlette.testclient import TestClient

from app.middleware.jwt_validation import (
    AgentContext,
    JWTValidationMiddleware,
    JWTValidationError,
)
from app.middleware.oauth_validation import (
    OAuthTokenValidator,
    OAuthTokenClaims,
    OAuthValidationError,
    configure_oauth_validator,
    get_oauth_validator,
)


# ─────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def rsa_keypair():
    private = rsa.generate_private_key(65537, 2048, default_backend())
    return (
        private,
        private.public_key(),
        private.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ),
    )


@pytest.fixture(scope="module")
def jwks_response(rsa_keypair):
    _, pub, _ = rsa_keypair
    import base64

    pub_numbers = pub.public_numbers()

    def _int_to_base64url(n: int) -> str:
        data = n.to_bytes((n.bit_length() + 7) // 8, byteorder="big")
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

    return {
        "keys": [
            {
                "kty": "RSA",
                "use": "sig",
                "alg": "RS256",
                "kid": "test-key-1",
                "n": _int_to_base64url(pub_numbers.n),
                "e": _int_to_base64url(pub_numbers.e),
            }
        ]
    }


@pytest.fixture
def make_oauth_token(rsa_keypair):
    _, _, pem = rsa_keypair

    def _make(claims: dict | None = None):
        now = int(time.time())
        payload = {
            "sub": "oauth-user-42",
            "iss": "http://localhost:8080/realms/mcp",
            "aud": "mcp-gateway",
            "scope": "mcp_tools mcp_resources",
            "preferred_username": "alice",
            "email": "alice@example.com",
            "realm_access": {"roles": ["mcp_user"]},
            "exp": now + 3600,
            "iat": now,
        }
        if claims:
            payload.update(claims)
        return jose_jwt.encode(payload, pem, algorithm="RS256", headers={"kid": "test-key-1"})

    return _make


@pytest.fixture
def make_deepsecure_token():
    from app.core.proxy_config import config

    def _make(claims: dict | None = None):
        now = int(time.time())
        payload = {
            "sub": "agent-007",
            "iss": "deeptrail-control",
            "aud": "deeptrail-gateway",
            "owner": "bob@example.com",
            "delegated_permissions": ["notion:pages:search"],
            "delegation_id": "del-123",
            "session_id": "sess-456",
            "exp": now + 3600,
            "iat": now,
        }
        if claims:
            payload.update(claims)
        return jose_jwt.encode(
            payload, config.security.jwt_secret_key, algorithm="HS256"
        )

    return _make


# ─────────────────────────────────────────────────────────────────────
# Dual-Token Detection
# ─────────────────────────────────────────────────────────────────────


class TestDualTokenDetection:
    """C4: The middleware must route RS256 → OAuth, HS256 → DeepSecure."""

    def test_is_oauth_token_positive(self, make_oauth_token):
        v = OAuthTokenValidator()
        assert v.is_oauth_token(make_oauth_token()) is True

    def test_is_oauth_token_negative(self, make_deepsecure_token):
        v = OAuthTokenValidator()
        assert v.is_oauth_token(make_deepsecure_token()) is False

    def test_scope_to_permissions_mapping(self):
        perms = JWTValidationMiddleware._oauth_scopes_to_permissions(
            ["mcp_tools", "mcp_resources"]
        )
        assert "mcp:tools:list" in perms
        assert "mcp:tools:call" in perms
        assert "mcp:resources:list" in perms
        assert "mcp:resources:read" in perms

    def test_unknown_scopes_ignored(self):
        perms = JWTValidationMiddleware._oauth_scopes_to_permissions(
            ["openid", "profile", "mcp_tools"]
        )
        assert perms == ["mcp:tools:list", "mcp:tools:call"]


# ─────────────────────────────────────────────────────────────────────
# AgentContext from OAuth
# ─────────────────────────────────────────────────────────────────────


class TestOAuthAgentContext:
    """C4: AgentContext built from OAuth claims."""

    @pytest.mark.asyncio
    async def test_oauth_context_fields(self, make_oauth_token, jwks_response):
        validator = OAuthTokenValidator(
            keycloak_url="http://localhost:8080",
            realm="mcp",
            audience="mcp-gateway",
        )
        with patch.object(validator, "fetch_jwks", new_callable=AsyncMock, return_value=jwks_response):
            claims = await validator.validate_token(make_oauth_token())
            assert claims.sub == "oauth-user-42"
            assert claims.preferred_username == "alice"
            assert "mcp_tools" in claims.scopes

    @pytest.mark.asyncio
    async def test_oauth_to_agent_context(self, make_oauth_token, jwks_response):
        """The full pipeline: OAuth token → OAuthTokenClaims → AgentContext."""
        from fastapi import FastAPI, Request
        from starlette.responses import JSONResponse

        validator = OAuthTokenValidator(
            keycloak_url="http://localhost:8080",
            realm="mcp",
            audience="mcp-gateway",
        )
        with patch.object(validator, "fetch_jwks", new_callable=AsyncMock, return_value=jwks_response):
            claims = await validator.validate_token(make_oauth_token())

        perms = JWTValidationMiddleware._oauth_scopes_to_permissions(claims.scopes)
        ctx = AgentContext(
            agent_id=claims.sub,
            owner=claims.preferred_username,
            delegation_id=None,
            session_id=f"oauth-{claims.sub}",
            delegated_permissions=perms,
            token_type="oauth",
            idp_issuer=claims.iss,
        )
        assert ctx.agent_id == "oauth-user-42"
        assert ctx.owner == "alice"
        assert ctx.token_type == "oauth"
        assert ctx.has_permission("mcp:tools:list")
        assert ctx.idp_issuer == "http://localhost:8080/realms/mcp"


# ─────────────────────────────────────────────────────────────────────
# Structured Error Responses (C5)
# ─────────────────────────────────────────────────────────────────────


class TestStructuredErrorResponses:
    """C5: 401/403 responses include resource_metadata."""

    def _make_middleware(self):
        from fastapi import FastAPI
        from starlette.responses import JSONResponse

        app = FastAPI()

        @app.get("/mcp/test")
        async def test_endpoint():
            return JSONResponse({"ok": True})

        middleware = JWTValidationMiddleware(app)
        return middleware

    def test_missing_auth_includes_resource_metadata(self):
        middleware = self._make_middleware()
        client = TestClient(middleware)
        with patch.dict(os.environ, {"GATEWAY_CANONICAL_URL": "https://gw.test.io"}):
            resp = client.get("/mcp/test")
        assert resp.status_code == 401
        body = resp.json()
        assert "resource_metadata" in body
        assert body["resource_metadata"].endswith("/.well-known/oauth-protected-resource")
        assert body["status"] == 401
        assert body["error"] == "missing_authorization"

    def test_invalid_token_includes_resource_metadata(self):
        middleware = self._make_middleware()
        client = TestClient(middleware)
        with patch.dict(os.environ, {"GATEWAY_CANONICAL_URL": "https://gw.test.io"}):
            resp = client.get(
                "/mcp/test", headers={"Authorization": "Bearer invalid.jwt.token"}
            )
        assert resp.status_code == 401
        body = resp.json()
        assert "resource_metadata" in body
        assert body["status"] == 401

    def test_www_authenticate_includes_resource_metadata(self):
        middleware = self._make_middleware()
        client = TestClient(middleware)
        with patch.dict(os.environ, {"GATEWAY_CANONICAL_URL": "https://gw.test.io"}):
            resp = client.get("/mcp/test")
        www_auth = resp.headers.get("WWW-Authenticate", "")
        assert 'resource_metadata="https://gw.test.io/.well-known/oauth-protected-resource"' in www_auth

    def test_error_body_has_required_fields(self):
        middleware = self._make_middleware()
        client = TestClient(middleware)
        with patch.dict(os.environ, {"GATEWAY_CANONICAL_URL": "https://gw.test.io"}):
            resp = client.get("/mcp/test")
        body = resp.json()
        assert "error" in body
        assert "detail" in body
        assert "status" in body
        assert "resource_metadata" in body

    def test_non_protected_path_no_error(self):
        middleware = self._make_middleware()
        client = TestClient(middleware)
        resp = client.get("/health")
        assert resp.status_code == 404 or resp.status_code == 200


# ─────────────────────────────────────────────────────────────────────
# OAuth Token Rejection Scenarios
# ─────────────────────────────────────────────────────────────────────


class TestOAuthTokenRejection:
    """C8: OAuth tokens with wrong aud/iss/exp are correctly rejected."""

    @pytest.mark.asyncio
    async def test_expired_oauth_token(self, make_oauth_token, jwks_response):
        v = OAuthTokenValidator(
            keycloak_url="http://localhost:8080",
            realm="mcp",
            audience="mcp-gateway",
        )
        token = make_oauth_token({"exp": int(time.time()) - 3600})
        with patch.object(v, "fetch_jwks", new_callable=AsyncMock, return_value=jwks_response):
            with pytest.raises(OAuthValidationError):
                await v.validate_token(token)

    @pytest.mark.asyncio
    async def test_wrong_audience_oauth_token(self, make_oauth_token, jwks_response):
        v = OAuthTokenValidator(
            keycloak_url="http://localhost:8080",
            realm="mcp",
            audience="mcp-gateway",
        )
        token = make_oauth_token({"aud": "wrong"})
        with patch.object(v, "fetch_jwks", new_callable=AsyncMock, return_value=jwks_response):
            with pytest.raises(OAuthValidationError):
                await v.validate_token(token)

    @pytest.mark.asyncio
    async def test_wrong_issuer_oauth_token(self, make_oauth_token, jwks_response):
        v = OAuthTokenValidator(
            keycloak_url="http://localhost:8080",
            realm="mcp",
            audience="mcp-gateway",
        )
        token = make_oauth_token({"iss": "http://evil.example.com/realms/mcp"})
        with patch.object(v, "fetch_jwks", new_callable=AsyncMock, return_value=jwks_response):
            with pytest.raises(OAuthValidationError):
                await v.validate_token(token)


# ─────────────────────────────────────────────────────────────────────
# Module-level Configuration
# ─────────────────────────────────────────────────────────────────────


class TestOAuthConfiguration:
    """C3/C8: Module-level validator lifecycle."""

    def test_configure_and_get(self):
        configure_oauth_validator(
            keycloak_url="http://kc:8080",
            realm="test",
            audience="test-aud",
            issuer_url="http://kc:8080",
        )
        v = get_oauth_validator()
        assert v is not None
        assert v.issuer == "http://kc:8080/realms/test"
        assert v._jwks_url == "http://kc:8080/realms/test/protocol/openid-connect/certs"
        assert v.enabled is True
