"""Unit tests for GoogleProvider.

All HTTP calls are mocked via httpx mocking — no real Google needed.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest
from jose import JWTError

from app.services.idp_service import (
    OIDCClaims,
    OIDCError,
    OIDCProviderUnavailableError,
    OIDCTokenInvalidError,
    OIDCTokens,
    UserInfo,
)
from app.services.providers.google import GoogleProvider

ISSUER = "https://accounts.google.com"
CLIENT_ID = "google-client-id.apps.googleusercontent.com"
CLIENT_SECRET = "google-client-secret"


@pytest.fixture
def provider() -> GoogleProvider:
    return GoogleProvider(
        issuer_url=ISSUER,
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        hd="acme.com",
    )


@pytest.fixture
def provider_no_hd() -> GoogleProvider:
    return GoogleProvider(
        issuer_url=ISSUER,
        client_id=CLIENT_ID,
    )


# ============================================================================
# Construction
# ============================================================================


class TestGoogleProviderInit:
    def test_stores_attributes(self):
        p = GoogleProvider(
            issuer_url=ISSUER,
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            hd="acme.com",
        )
        assert p._issuer_url == ISSUER
        assert p._client_id == CLIENT_ID
        assert p._client_secret == CLIENT_SECRET
        assert p._hd == "acme.com"

    def test_hardcoded_endpoints(self):
        p = GoogleProvider(issuer_url=ISSUER, client_id=CLIENT_ID)
        assert p._auth_endpoint == "https://accounts.google.com/o/oauth2/v2/auth"
        assert p._token_endpoint == "https://oauth2.googleapis.com/token"
        assert p._jwks_uri == "https://www.googleapis.com/oauth2/v3/certs"
        assert p._userinfo_endpoint == "https://openidconnect.googleapis.com/v1/userinfo"

    def test_trailing_slash_stripped(self):
        p = GoogleProvider(issuer_url="https://accounts.google.com/", client_id="test")
        assert p._issuer_url == "https://accounts.google.com"

    def test_hd_defaults_to_none(self):
        p = GoogleProvider(issuer_url=ISSUER, client_id=CLIENT_ID)
        assert p._hd is None

    def test_jwks_cache_starts_empty(self):
        p = GoogleProvider(issuer_url=ISSUER, client_id=CLIENT_ID)
        assert p._jwks_cache is None


# ============================================================================
# Authorization URL
# ============================================================================


class TestGetAuthorizationUrl:
    @pytest.mark.asyncio
    async def test_includes_required_params(self, provider: GoogleProvider):
        url = await provider.get_authorization_url(
            state="random-state",
            redirect_uri="http://localhost:8000/callback",
        )
        assert "response_type=code" in url
        assert f"client_id={CLIENT_ID}" in url
        assert "state=random-state" in url
        assert "scope=openid+profile+email" in url or "scope=openid" in url
        assert url.startswith("https://accounts.google.com/o/oauth2/v2/auth?")

    @pytest.mark.asyncio
    async def test_includes_hd_when_set(self, provider: GoogleProvider):
        url = await provider.get_authorization_url(
            state="s",
            redirect_uri="http://localhost:8000/cb",
        )
        assert "hd=acme.com" in url

    @pytest.mark.asyncio
    async def test_excludes_hd_when_not_set(self, provider_no_hd: GoogleProvider):
        url = await provider_no_hd.get_authorization_url(
            state="s",
            redirect_uri="http://localhost:8000/cb",
        )
        assert "hd=" not in url

    @pytest.mark.asyncio
    async def test_includes_pkce_params(self, provider: GoogleProvider):
        url = await provider.get_authorization_url(
            state="s",
            redirect_uri="http://localhost:8000/cb",
            code_challenge="challenge-hash",
            code_challenge_method="S256",
        )
        assert "code_challenge=challenge-hash" in url
        assert "code_challenge_method=S256" in url

    @pytest.mark.asyncio
    async def test_custom_scopes(self, provider: GoogleProvider):
        url = await provider.get_authorization_url(
            state="s",
            redirect_uri="http://localhost:8000/cb",
            scopes=["openid", "email"],
        )
        assert "scope=openid+email" in url or "scope=openid" in url


# ============================================================================
# Code Exchange
# ============================================================================


class TestExchangeCode:
    @pytest.mark.asyncio
    async def test_returns_tokens(self, provider: GoogleProvider):
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
    async def test_handles_400_error(self, provider: GoogleProvider):
        mock_response = httpx.Response(
            400,
            json={"error": "invalid_grant"},
            request=httpx.Request("POST", provider._token_endpoint),
        )
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response):
            with pytest.raises(OIDCError, match="Token exchange failed"):
                await provider.exchange_code("bad-code", "http://localhost/cb")

    @pytest.mark.asyncio
    async def test_handles_network_error(self, provider: GoogleProvider):
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
    async def test_extracts_claims(self, provider: GoogleProvider):
        decoded_claims = {
            "sub": "google-user-123",
            "email": "sarah@acme.com",
            "email_verified": True,
            "name": "Sarah Chen",
            "given_name": "Sarah",
            "family_name": "Chen",
            "hd": "acme.com",
            "iss": ISSUER,
            "aud": CLIENT_ID,
        }
        with patch.object(provider, "_get_jwks", new_callable=AsyncMock, return_value=MOCK_JWKS):
            with patch("app.services.providers.google.jwt.decode", return_value=decoded_claims):
                claims = await provider.validate_token("valid-jwt")

        assert isinstance(claims, OIDCClaims)
        assert claims.sub == "google-user-123"
        assert claims.email == "sarah@acme.com"
        assert claims.email_verified is True
        assert claims.name == "Sarah Chen"
        assert claims.given_name == "Sarah"
        assert claims.family_name == "Chen"
        assert claims.issuer == ISSUER

    @pytest.mark.asyncio
    async def test_no_groups_or_roles(self, provider: GoogleProvider):
        decoded_claims = {
            "sub": "user-1",
            "email": "user@acme.com",
            "hd": "acme.com",
            "iss": ISSUER,
            "aud": CLIENT_ID,
        }
        with patch.object(provider, "_get_jwks", new_callable=AsyncMock, return_value=MOCK_JWKS):
            with patch("app.services.providers.google.jwt.decode", return_value=decoded_claims):
                claims = await provider.validate_token("valid-jwt")

        assert claims.groups is None
        assert claims.roles is None

    @pytest.mark.asyncio
    async def test_stores_raw_claims_with_hd(self, provider: GoogleProvider):
        decoded_claims = {
            "sub": "user-1",
            "email": "user@acme.com",
            "hd": "acme.com",
            "iss": ISSUER,
            "aud": CLIENT_ID,
        }
        with patch.object(provider, "_get_jwks", new_callable=AsyncMock, return_value=MOCK_JWKS):
            with patch("app.services.providers.google.jwt.decode", return_value=decoded_claims):
                claims = await provider.validate_token("valid-jwt")

        assert claims.raw_claims is not None
        assert claims.raw_claims["hd"] == "acme.com"

    @pytest.mark.asyncio
    async def test_rejects_invalid_signature(self, provider: GoogleProvider):
        with patch.object(provider, "_get_jwks", new_callable=AsyncMock, return_value=MOCK_JWKS):
            with patch(
                "app.services.providers.google.jwt.decode",
                side_effect=JWTError("Signature verification failed"),
            ):
                with pytest.raises(OIDCTokenInvalidError, match="validation failed"):
                    await provider.validate_token("tampered-jwt")


# ============================================================================
# JWKS Caching
# ============================================================================


class TestJWKSCaching:
    @pytest.mark.asyncio
    async def test_caches_jwks(self, provider: GoogleProvider):
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
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_jwks_unavailable(self, provider: GoogleProvider):
        with patch(
            "httpx.AsyncClient.get",
            new_callable=AsyncMock,
            side_effect=httpx.ConnectError("Connection refused"),
        ):
            with pytest.raises(OIDCProviderUnavailableError, match="unreachable"):
                await provider._get_jwks()

    @pytest.mark.asyncio
    async def test_jwks_non_200(self, provider: GoogleProvider):
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
    async def test_returns_user_info(self, provider: GoogleProvider):
        mock_response = httpx.Response(
            200,
            json={
                "sub": "google-user-123",
                "email": "sarah@acme.com",
                "name": "Sarah Chen",
            },
            request=httpx.Request("GET", provider._userinfo_endpoint),
        )
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response):
            info = await provider.get_user_info("valid-access-token")

        assert isinstance(info, UserInfo)
        assert info.sub == "google-user-123"
        assert info.email == "sarah@acme.com"
        assert info.name == "Sarah Chen"

    @pytest.mark.asyncio
    async def test_handles_failure(self, provider: GoogleProvider):
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
    async def test_returns_new_tokens(self, provider: GoogleProvider):
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
    async def test_handles_failure(self, provider: GoogleProvider):
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
    async def test_returns_google_account_url(self, provider: GoogleProvider):
        url = await provider.logout_url()
        assert url == "https://myaccount.google.com"

    @pytest.mark.asyncio
    async def test_ignores_id_token_hint(self, provider: GoogleProvider):
        url = await provider.logout_url(id_token_hint="my-id-token")
        assert url == "https://myaccount.google.com"

    @pytest.mark.asyncio
    async def test_ignores_post_logout_redirect(self, provider: GoogleProvider):
        url = await provider.logout_url(
            post_logout_redirect_uri="http://localhost:8000/logged-out"
        )
        assert url == "https://myaccount.google.com"

    @pytest.mark.asyncio
    async def test_ignores_both_params(self, provider: GoogleProvider):
        url = await provider.logout_url(
            id_token_hint="hint",
            post_logout_redirect_uri="http://example.com/out",
        )
        assert url == "https://myaccount.google.com"
