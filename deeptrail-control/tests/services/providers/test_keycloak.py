"""Unit tests for KeycloakProvider.

All HTTP calls are mocked via httpx mocking — no real Keycloak needed.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.services.idp_service import (
    OIDCClaims,
    OIDCError,
    OIDCProviderUnavailableError,
    OIDCTokenInvalidError,
    OIDCTokens,
    UserInfo,
)
from app.services.providers.keycloak import KeycloakProvider

ISSUER = "http://localhost:8080/realms/deepsecure"
CLIENT_ID = "deepsecure-control"
CLIENT_SECRET = "control-secret"


@pytest.fixture
def provider() -> KeycloakProvider:
    return KeycloakProvider(
        issuer_url=ISSUER,
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        realm="deepsecure",
    )


# ============================================================================
# Authorization URL
# ============================================================================


class TestGetAuthorizationUrl:
    @pytest.mark.asyncio
    async def test_includes_required_params(self, provider: KeycloakProvider):
        url = await provider.get_authorization_url(
            state="random-state",
            redirect_uri="http://localhost:8000/callback",
        )
        assert "response_type=code" in url
        assert f"client_id={CLIENT_ID}" in url
        assert "state=random-state" in url
        assert "scope=openid+profile+email" in url or "scope=openid" in url
        assert url.startswith(f"{ISSUER}/protocol/openid-connect/auth?")

    @pytest.mark.asyncio
    async def test_custom_scopes(self, provider: KeycloakProvider):
        url = await provider.get_authorization_url(
            state="s",
            redirect_uri="http://localhost:8000/cb",
            scopes=["openid", "groups"],
        )
        assert "scope=openid+groups" in url or "scope=openid" in url


# ============================================================================
# Code Exchange
# ============================================================================


class TestExchangeCode:
    @pytest.mark.asyncio
    async def test_returns_tokens(self, provider: KeycloakProvider):
        mock_response = httpx.Response(
            200,
            json={
                "id_token": "id-jwt",
                "access_token": "access-jwt",
                "refresh_token": "refresh-jwt",
                "token_type": "Bearer",
            },
            request=httpx.Request("POST", provider._token_endpoint),
        )
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response):
            tokens = await provider.exchange_code("auth-code", "http://localhost/cb")
        assert isinstance(tokens, OIDCTokens)
        assert tokens.id_token == "id-jwt"
        assert tokens.access_token == "access-jwt"
        assert tokens.refresh_token == "refresh-jwt"

    @pytest.mark.asyncio
    async def test_handles_400_error(self, provider: KeycloakProvider):
        mock_response = httpx.Response(
            400,
            json={"error": "invalid_grant"},
            request=httpx.Request("POST", provider._token_endpoint),
        )
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response):
            with pytest.raises(OIDCError, match="Token exchange failed"):
                await provider.exchange_code("bad-code", "http://localhost/cb")

    @pytest.mark.asyncio
    async def test_handles_network_error(self, provider: KeycloakProvider):
        with patch(
            "httpx.AsyncClient.post",
            new_callable=AsyncMock,
            side_effect=httpx.ConnectError("Connection refused"),
        ):
            with pytest.raises(OIDCProviderUnavailableError, match="unreachable"):
                await provider.exchange_code("code", "http://localhost/cb")


# ============================================================================
# Token Validation
# ============================================================================


MOCK_JWKS = {
    "keys": [
        {
            "kty": "RSA",
            "kid": "test-key-1",
            "use": "sig",
            "n": "test",
            "e": "AQAB",
        }
    ]
}


class TestValidateToken:
    @pytest.mark.asyncio
    async def test_extracts_claims(self, provider: KeycloakProvider):
        decoded_claims = {
            "sub": "user-123",
            "email": "sarah@acme.com",
            "email_verified": True,
            "name": "Sarah Chen",
            "given_name": "Sarah",
            "family_name": "Chen",
            "groups": ["acme-org"],
            "realm_access": {"roles": ["user"]},
            "iss": ISSUER,
            "aud": CLIENT_ID,
        }
        with patch.object(provider, "_get_jwks", new_callable=AsyncMock, return_value=MOCK_JWKS):
            with patch("app.services.providers.keycloak.jwt.decode", return_value=decoded_claims):
                claims = await provider.validate_token("valid-jwt")

        assert isinstance(claims, OIDCClaims)
        assert claims.sub == "user-123"
        assert claims.email == "sarah@acme.com"
        assert claims.email_verified is True
        assert claims.name == "Sarah Chen"
        assert claims.groups == ["acme-org"]
        assert claims.roles == ["user"]
        assert claims.issuer == ISSUER

    @pytest.mark.asyncio
    async def test_rejects_invalid_signature(self, provider: KeycloakProvider):
        from jose import JWTError

        with patch.object(provider, "_get_jwks", new_callable=AsyncMock, return_value=MOCK_JWKS):
            with patch(
                "app.services.providers.keycloak.jwt.decode",
                side_effect=JWTError("Signature verification failed"),
            ):
                with pytest.raises(OIDCTokenInvalidError, match="validation failed"):
                    await provider.validate_token("tampered-jwt")

    @pytest.mark.asyncio
    async def test_rejects_expired_token(self, provider: KeycloakProvider):
        from jose import ExpiredSignatureError

        with patch.object(provider, "_get_jwks", new_callable=AsyncMock, return_value=MOCK_JWKS):
            with patch(
                "app.services.providers.keycloak.jwt.decode",
                side_effect=ExpiredSignatureError("Token expired"),
            ):
                with pytest.raises(OIDCTokenInvalidError):
                    await provider.validate_token("expired-jwt")


# ============================================================================
# JWKS Caching
# ============================================================================


class TestJWKSCaching:
    @pytest.mark.asyncio
    async def test_caches_jwks(self, provider: KeycloakProvider):
        mock_response = httpx.Response(
            200,
            json=MOCK_JWKS,
            request=httpx.Request("GET", provider._jwks_uri),
        )
        call_count = 0

        async def counting_get(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return mock_response

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, side_effect=counting_get):
            first = await provider._get_jwks()
            second = await provider._get_jwks()

        assert first == MOCK_JWKS
        assert second == MOCK_JWKS
        assert call_count == 1  # Only one HTTP request

    @pytest.mark.asyncio
    async def test_jwks_unavailable(self, provider: KeycloakProvider):
        with patch(
            "httpx.AsyncClient.get",
            new_callable=AsyncMock,
            side_effect=httpx.ConnectError("Connection refused"),
        ):
            with pytest.raises(OIDCProviderUnavailableError, match="unreachable"):
                await provider._get_jwks()

    @pytest.mark.asyncio
    async def test_jwks_non_200(self, provider: KeycloakProvider):
        mock_response = httpx.Response(
            500,
            request=httpx.Request("GET", provider._jwks_uri),
        )
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response):
            with pytest.raises(OIDCProviderUnavailableError, match="JWKS fetch failed"):
                await provider._get_jwks()


# ============================================================================
# User Info
# ============================================================================


class TestGetUserInfo:
    @pytest.mark.asyncio
    async def test_returns_user_info(self, provider: KeycloakProvider):
        mock_response = httpx.Response(
            200,
            json={
                "sub": "user-123",
                "email": "sarah@acme.com",
                "name": "Sarah Chen",
                "groups": ["acme-org"],
                "realm_access": {"roles": ["user"]},
            },
            request=httpx.Request("GET", provider._userinfo_endpoint),
        )
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response):
            info = await provider.get_user_info("valid-access-token")

        assert isinstance(info, UserInfo)
        assert info.sub == "user-123"
        assert info.email == "sarah@acme.com"
        assert info.name == "Sarah Chen"

    @pytest.mark.asyncio
    async def test_handles_failure(self, provider: KeycloakProvider):
        mock_response = httpx.Response(
            401,
            json={"error": "invalid_token"},
            request=httpx.Request("GET", provider._userinfo_endpoint),
        )
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response):
            with pytest.raises(OIDCError, match="Userinfo request failed"):
                await provider.get_user_info("bad-token")


# ============================================================================
# Refresh Token
# ============================================================================


class TestRefreshToken:
    @pytest.mark.asyncio
    async def test_returns_new_tokens(self, provider: KeycloakProvider):
        mock_response = httpx.Response(
            200,
            json={
                "id_token": "new-id-jwt",
                "access_token": "new-access-jwt",
                "refresh_token": "new-refresh-jwt",
                "token_type": "Bearer",
            },
            request=httpx.Request("POST", provider._token_endpoint),
        )
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response):
            tokens = await provider.refresh_token("old-refresh-token")

        assert isinstance(tokens, OIDCTokens)
        assert tokens.access_token == "new-access-jwt"
        assert tokens.refresh_token == "new-refresh-jwt"

    @pytest.mark.asyncio
    async def test_handles_failure(self, provider: KeycloakProvider):
        mock_response = httpx.Response(
            400,
            json={"error": "invalid_grant"},
            request=httpx.Request("POST", provider._token_endpoint),
        )
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response):
            with pytest.raises(OIDCError, match="Token refresh failed"):
                await provider.refresh_token("revoked-token")


# ============================================================================
# Logout URL
# ============================================================================


class TestLogoutUrl:
    @pytest.mark.asyncio
    async def test_includes_id_token_hint(self, provider: KeycloakProvider):
        url = await provider.logout_url(id_token_hint="my-id-token")
        assert "id_token_hint=my-id-token" in url
        assert url.startswith(f"{ISSUER}/protocol/openid-connect/logout?")

    @pytest.mark.asyncio
    async def test_includes_post_logout_redirect(self, provider: KeycloakProvider):
        url = await provider.logout_url(
            post_logout_redirect_uri="http://localhost:8000/logged-out"
        )
        assert "post_logout_redirect_uri=" in url

    @pytest.mark.asyncio
    async def test_no_params(self, provider: KeycloakProvider):
        url = await provider.logout_url()
        assert url == f"{ISSUER}/protocol/openid-connect/logout"
        assert "?" not in url

    @pytest.mark.asyncio
    async def test_both_params(self, provider: KeycloakProvider):
        url = await provider.logout_url(
            id_token_hint="hint",
            post_logout_redirect_uri="http://example.com/out",
        )
        assert "id_token_hint=hint" in url
        assert "post_logout_redirect_uri=" in url


# ============================================================================
# Construction
# ============================================================================


class TestKeycloakProviderInit:
    def test_endpoints_derived_from_issuer(self):
        p = KeycloakProvider(
            issuer_url="http://kc.test:9090/realms/myrealm",
            client_id="test",
        )
        assert p._auth_endpoint == "http://kc.test:9090/realms/myrealm/protocol/openid-connect/auth"
        assert p._token_endpoint == "http://kc.test:9090/realms/myrealm/protocol/openid-connect/token"
        assert p._userinfo_endpoint == "http://kc.test:9090/realms/myrealm/protocol/openid-connect/userinfo"
        assert p._jwks_uri == "http://kc.test:9090/realms/myrealm/protocol/openid-connect/certs"
        assert p._logout_endpoint == "http://kc.test:9090/realms/myrealm/protocol/openid-connect/logout"

    def test_trailing_slash_stripped(self):
        p = KeycloakProvider(
            issuer_url="http://kc.test:9090/realms/myrealm/",
            client_id="test",
        )
        assert p._issuer_url == "http://kc.test:9090/realms/myrealm"

    def test_browser_url_splits_endpoints(self):
        """Browser-facing endpoints use browser_url; backend endpoints use issuer_url."""
        p = KeycloakProvider(
            issuer_url="http://keycloak:8080/realms/deepsecure",
            client_id="test",
            browser_url="http://localhost:8080/realms/deepsecure",
        )
        assert p._auth_endpoint == "http://localhost:8080/realms/deepsecure/protocol/openid-connect/auth"
        assert p._logout_endpoint == "http://localhost:8080/realms/deepsecure/protocol/openid-connect/logout"
        assert p._token_endpoint == "http://keycloak:8080/realms/deepsecure/protocol/openid-connect/token"
        assert p._userinfo_endpoint == "http://keycloak:8080/realms/deepsecure/protocol/openid-connect/userinfo"
        assert p._jwks_uri == "http://keycloak:8080/realms/deepsecure/protocol/openid-connect/certs"

    def test_browser_url_none_uses_issuer_for_all(self):
        """When browser_url is None, all endpoints use issuer_url."""
        p = KeycloakProvider(
            issuer_url="http://localhost:8080/realms/deepsecure",
            client_id="test",
            browser_url=None,
        )
        assert p._auth_endpoint == "http://localhost:8080/realms/deepsecure/protocol/openid-connect/auth"
        assert p._token_endpoint == "http://localhost:8080/realms/deepsecure/protocol/openid-connect/token"
