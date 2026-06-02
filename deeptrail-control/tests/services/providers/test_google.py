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

    @pytest.mark.asyncio
    async def test_fetch_groups_false_no_directory_scope(self, provider: GoogleProvider):
        url = await provider.get_authorization_url(
            state="s",
            redirect_uri="http://localhost:8000/cb",
        )
        assert "admin.directory" not in url

    @pytest.mark.asyncio
    async def test_fetch_groups_true_adds_directory_scope(self, provider: GoogleProvider):
        url = await provider.get_authorization_url(
            state="s",
            redirect_uri="http://localhost:8000/cb",
            fetch_groups=True,
        )
        assert "admin.directory.group.readonly" in url

    @pytest.mark.asyncio
    async def test_fetch_groups_with_custom_scopes(self, provider: GoogleProvider):
        url = await provider.get_authorization_url(
            state="s",
            redirect_uri="http://localhost:8000/cb",
            scopes=["openid", "email"],
            fetch_groups=True,
        )
        assert "admin.directory.group.readonly" in url
        assert "openid" in url

    @pytest.mark.asyncio
    async def test_fetch_groups_no_duplicate_when_scope_present(self, provider: GoogleProvider):
        directory_scope = "https://www.googleapis.com/auth/admin.directory.group.readonly"
        url = await provider.get_authorization_url(
            state="s",
            redirect_uri="http://localhost:8000/cb",
            scopes=["openid", "email", directory_scope],
            fetch_groups=True,
        )
        scope_param = [p for p in url.split("&") if p.startswith("scope=")][0]
        scope_value = scope_param.split("=", 1)[1]
        count = scope_value.count("admin.directory.group.readonly")
        assert count == 1

    @pytest.mark.asyncio
    async def test_does_not_mutate_input_scopes(self, provider: GoogleProvider):
        original = ["openid", "email"]
        original_copy = original.copy()
        await provider.get_authorization_url(
            state="s",
            redirect_uri="http://localhost:8000/cb",
            scopes=original,
            fetch_groups=True,
        )
        assert original == original_copy


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


# ============================================================================
# Fetch User Groups
# ============================================================================

_DIRECTORY_API_URL = "https://admin.googleapis.com/admin/directory/v1/groups"


class TestFetchUserGroups:
    @pytest.mark.asyncio
    async def test_returns_group_emails(self, provider: GoogleProvider):
        mock_response = httpx.Response(
            200,
            json={
                "kind": "admin#directory#groups",
                "groups": [
                    {"email": "engineering@acme.com", "name": "Engineering", "id": "g1"},
                    {"email": "all@acme.com", "name": "All Company", "id": "g2"},
                ],
            },
            request=httpx.Request("GET", _DIRECTORY_API_URL),
        )
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response):
            groups = await provider.fetch_user_groups("valid-token", "sarah@acme.com")

        assert groups == ["engineering@acme.com", "all@acme.com"]

    @pytest.mark.asyncio
    async def test_empty_groups_list(self, provider: GoogleProvider):
        mock_response = httpx.Response(
            200,
            json={"kind": "admin#directory#groups", "groups": []},
            request=httpx.Request("GET", _DIRECTORY_API_URL),
        )
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response):
            groups = await provider.fetch_user_groups("valid-token", "user@acme.com")

        assert groups == []

    @pytest.mark.asyncio
    async def test_no_groups_key(self, provider: GoogleProvider):
        mock_response = httpx.Response(
            200,
            json={"kind": "admin#directory#groups"},
            request=httpx.Request("GET", _DIRECTORY_API_URL),
        )
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response):
            groups = await provider.fetch_user_groups("valid-token", "user@acme.com")

        assert groups == []

    @pytest.mark.asyncio
    async def test_http_403_returns_empty(self, provider: GoogleProvider):
        mock_response = httpx.Response(
            403,
            text="Insufficient privileges",
            request=httpx.Request("GET", _DIRECTORY_API_URL),
        )
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response):
            groups = await provider.fetch_user_groups("token", "user@acme.com")

        assert groups == []

    @pytest.mark.asyncio
    async def test_http_404_returns_empty(self, provider: GoogleProvider):
        mock_response = httpx.Response(
            404,
            text="User not found",
            request=httpx.Request("GET", _DIRECTORY_API_URL),
        )
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response):
            groups = await provider.fetch_user_groups("token", "unknown@acme.com")

        assert groups == []

    @pytest.mark.asyncio
    async def test_http_500_returns_empty(self, provider: GoogleProvider):
        mock_response = httpx.Response(
            500,
            text="Internal Server Error",
            request=httpx.Request("GET", _DIRECTORY_API_URL),
        )
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response):
            groups = await provider.fetch_user_groups("token", "user@acme.com")

        assert groups == []

    @pytest.mark.asyncio
    async def test_timeout_returns_empty(self, provider: GoogleProvider):
        with patch(
            "httpx.AsyncClient.get",
            new_callable=AsyncMock,
            side_effect=httpx.TimeoutException("timed out"),
        ):
            groups = await provider.fetch_user_groups("token", "user@acme.com")

        assert groups == []

    @pytest.mark.asyncio
    async def test_connect_error_returns_empty(self, provider: GoogleProvider):
        with patch(
            "httpx.AsyncClient.get",
            new_callable=AsyncMock,
            side_effect=httpx.ConnectError("Connection refused"),
        ):
            groups = await provider.fetch_user_groups("token", "user@acme.com")

        assert groups == []

    @pytest.mark.asyncio
    async def test_malformed_json_returns_empty(self, provider: GoogleProvider):
        mock_response = httpx.Response(
            200,
            text="not json",
            request=httpx.Request("GET", _DIRECTORY_API_URL),
        )
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response):
            groups = await provider.fetch_user_groups("token", "user@acme.com")

        assert groups == []

    @pytest.mark.asyncio
    async def test_passes_correct_params(self, provider: GoogleProvider):
        mock_response = httpx.Response(
            200,
            json={"groups": []},
            request=httpx.Request("GET", _DIRECTORY_API_URL),
        )
        with patch("app.services.providers.google.fetch_workspace_user_info", new_callable=AsyncMock, return_value=None), \
             patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response) as mock_get:
            await provider.fetch_user_groups("my-access-token", "alice@acme.com")

        assert mock_get.call_count >= 1
        groups_call = mock_get.call_args_list[0]
        assert groups_call.kwargs["params"] == {"userKey": "alice@acme.com"}
        assert groups_call.kwargs["headers"] == {"Authorization": "Bearer my-access-token"}
        assert groups_call.kwargs["timeout"] == 10.0
        assert "admin.googleapis.com/admin/directory/v1/groups" in str(groups_call.args[0])

    @pytest.mark.asyncio
    async def test_missing_email_key_in_group_entry(self, provider: GoogleProvider):
        """Group entries missing the 'email' key are handled gracefully."""
        mock_response = httpx.Response(
            200,
            json={
                "groups": [
                    {"name": "No Email Group", "id": "g1"},
                    {"email": "valid@acme.com", "name": "Valid", "id": "g2"},
                ],
            },
            request=httpx.Request("GET", _DIRECTORY_API_URL),
        )
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response):
            groups = await provider.fetch_user_groups("token", "user@acme.com")

        assert groups == []

    @pytest.mark.asyncio
    async def test_no_credentials_in_warning_logs(self, provider: GoogleProvider, caplog):
        mock_response = httpx.Response(
            403,
            text="Forbidden",
            request=httpx.Request("GET", _DIRECTORY_API_URL),
        )
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response):
            await provider.fetch_user_groups("secret-token-123", "user@acme.com")

        for record in caplog.records:
            assert "secret-token-123" not in record.message
