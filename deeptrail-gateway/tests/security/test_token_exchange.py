"""
Tests for TokenExchangeClient (WS-J6).

Covers:
- RFC 8693 parameter construction
- Audience mapping and fallback
- Scope handling
- Token exchange success/failure/unavailable
- Cache hit/miss/expiry/force-refresh/TTL-buffer
- ExchangedToken.is_expired property
- Disabled client
- Module accessor lifecycle
- Security: no secrets in safe outputs
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import httpx

from app.security.token_exchange import (
    ExchangedToken,
    TokenExchangeClient,
    TokenExchangeConfig,
    TokenExchangeDeniedError,
    TokenExchangeError,
    TokenExchangeGrantType,
    TokenExchangeUnavailableError,
    configure_token_exchange_client,
    get_token_exchange_client,
    reset_token_exchange_client,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(autouse=True)
def _reset_global_client():
    """Reset the global exchange client singleton."""
    reset_token_exchange_client()
    yield
    reset_token_exchange_client()


@pytest.fixture
def config() -> TokenExchangeConfig:
    return TokenExchangeConfig(
        keycloak_url="http://keycloak:8080",
        realm="deepsecure",
        client_id="gateway",
        client_secret="secret",
        audience_map={"hubspot": "hubspot-api", "notion": "notion-api"},
    )


@pytest.fixture
def client(config: TokenExchangeConfig) -> TokenExchangeClient:
    return TokenExchangeClient(config=config)


# =============================================================================
# Token Endpoint URL
# =============================================================================


class TestTokenEndpoint:
    def test_constructs_correct_url(self, client: TokenExchangeClient):
        assert client.token_endpoint == (
            "http://keycloak:8080/realms/deepsecure/protocol/openid-connect/token"
        )

    def test_custom_realm(self):
        c = TokenExchangeClient(config=TokenExchangeConfig(
            keycloak_url="https://kc.example.com",
            realm="custom",
        ))
        assert c.token_endpoint == (
            "https://kc.example.com/realms/custom/protocol/openid-connect/token"
        )


# =============================================================================
# Build Exchange Params (RFC 8693)
# =============================================================================


class TestBuildExchangeParams:
    def test_correct_rfc8693_params(self, client: TokenExchangeClient):
        params = client._build_exchange_params(
            subject_token="jwt-token",
            backend_id="hubspot",
            scopes=["contacts:read"],
        )
        assert params["grant_type"] == TokenExchangeGrantType.TOKEN_EXCHANGE.value
        assert params["client_id"] == "gateway"
        assert params["client_secret"] == "secret"
        assert params["subject_token"] == "jwt-token"
        assert params["subject_token_type"] == "urn:ietf:params:oauth:token-type:access_token"
        assert params["requested_token_type"] == "urn:ietf:params:oauth:token-type:access_token"
        assert params["audience"] == "hubspot-api"
        assert params["scope"] == "contacts:read"

    def test_audience_map_fallback(self, client: TokenExchangeClient):
        params = client._build_exchange_params(
            subject_token="jwt-token",
            backend_id="unknown-backend",
        )
        assert params["audience"] == "unknown-backend"

    def test_no_scope_param_when_none(self, client: TokenExchangeClient):
        params = client._build_exchange_params(
            subject_token="jwt-token",
            backend_id="hubspot",
        )
        assert "scope" not in params

    def test_multiple_scopes_space_separated(self, client: TokenExchangeClient):
        params = client._build_exchange_params(
            subject_token="jwt",
            backend_id="hubspot",
            scopes=["contacts:read", "deals:write"],
        )
        assert params["scope"] == "contacts:read deals:write"


# =============================================================================
# Exchange Token (with mocked HTTP)
# =============================================================================


class TestExchangeToken:
    @pytest.mark.asyncio
    async def test_success(self, client: TokenExchangeClient):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "backend-token-abc",
            "token_type": "Bearer",
            "expires_in": 300,
            "scope": "contacts:read",
        }

        mock_http = AsyncMock()
        mock_http.post = AsyncMock(return_value=mock_response)
        client._http_client = mock_http

        token = await client.exchange_token("agent-jwt", "hubspot")
        assert token.access_token == "backend-token-abc"
        assert token.token_type == "Bearer"
        assert token.expires_in == 300
        assert token.scope == "contacts:read"

    @pytest.mark.asyncio
    async def test_denied_invalid_grant(self, client: TokenExchangeClient):
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = {
            "error": "invalid_grant",
            "error_description": "token is not active",
        }

        mock_http = AsyncMock()
        mock_http.post = AsyncMock(return_value=mock_response)
        client._http_client = mock_http

        with pytest.raises(TokenExchangeDeniedError) as exc_info:
            await client.exchange_token("bad-jwt", "hubspot")
        assert exc_info.value.error_code == "invalid_grant"

    @pytest.mark.asyncio
    async def test_denied_unauthorized_client(self, client: TokenExchangeClient):
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = {
            "error": "unauthorized_client",
            "error_description": "client not allowed",
        }

        mock_http = AsyncMock()
        mock_http.post = AsyncMock(return_value=mock_response)
        client._http_client = mock_http

        with pytest.raises(TokenExchangeDeniedError) as exc_info:
            await client.exchange_token("jwt", "hubspot")
        assert exc_info.value.error_code == "unauthorized_client"

    @pytest.mark.asyncio
    async def test_unavailable_connect_error(self, client: TokenExchangeClient):
        mock_http = AsyncMock()
        mock_http.post = AsyncMock(side_effect=httpx.ConnectError("refused"))
        client._http_client = mock_http

        with pytest.raises(TokenExchangeUnavailableError):
            await client.exchange_token("jwt", "hubspot")

    @pytest.mark.asyncio
    async def test_unavailable_timeout(self, client: TokenExchangeClient):
        mock_http = AsyncMock()
        mock_http.post = AsyncMock(side_effect=httpx.ConnectTimeout("timed out"))
        client._http_client = mock_http

        with pytest.raises(TokenExchangeUnavailableError):
            await client.exchange_token("jwt", "hubspot")

    @pytest.mark.asyncio
    async def test_unknown_error_code(self, client: TokenExchangeClient):
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = {
            "error": "server_error",
            "error_description": "internal",
        }

        mock_http = AsyncMock()
        mock_http.post = AsyncMock(return_value=mock_response)
        client._http_client = mock_http

        with pytest.raises(TokenExchangeError) as exc_info:
            await client.exchange_token("jwt", "hubspot")
        assert exc_info.value.error_code == "server_error"


# =============================================================================
# Cache Behavior
# =============================================================================


class TestCaching:
    def test_cache_key_deterministic(self, client: TokenExchangeClient):
        key1 = client._cache_key("token-a", "hubspot")
        key2 = client._cache_key("token-a", "hubspot")
        assert key1 == key2

    def test_cache_key_varies_by_backend(self, client: TokenExchangeClient):
        key1 = client._cache_key("token-a", "hubspot")
        key2 = client._cache_key("token-a", "notion")
        assert key1 != key2

    def test_cache_key_varies_by_token(self, client: TokenExchangeClient):
        key1 = client._cache_key("token-a", "hubspot")
        key2 = client._cache_key("token-b", "hubspot")
        assert key1 != key2

    def test_cache_key_uses_hash_not_token(self, client: TokenExchangeClient):
        key = client._cache_key("my-secret-jwt", "hubspot")
        assert "my-secret-jwt" not in key

    @pytest.mark.asyncio
    async def test_cache_hit(self, client: TokenExchangeClient):
        cached_token = ExchangedToken(
            access_token="cached-abc",
            expires_in=200,
            issued_at=datetime.now(timezone.utc),
        )
        cache_key = client._cache_key("agent-jwt", "hubspot")
        client._cache[cache_key] = cached_token

        token = await client.get_backend_token("agent-jwt", "hubspot")
        assert token.access_token == "cached-abc"

    @pytest.mark.asyncio
    async def test_cache_miss_performs_exchange(self, client: TokenExchangeClient):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "fresh-token",
            "token_type": "Bearer",
            "expires_in": 300,
        }
        mock_http = AsyncMock()
        mock_http.post = AsyncMock(return_value=mock_response)
        client._http_client = mock_http

        token = await client.get_backend_token("agent-jwt", "hubspot")
        assert token.access_token == "fresh-token"
        mock_http.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_cache_expired_performs_exchange(self, client: TokenExchangeClient):
        expired_token = ExchangedToken(
            access_token="old-token",
            expires_in=1,
            issued_at=datetime.now(timezone.utc) - timedelta(seconds=60),
        )
        cache_key = client._cache_key("agent-jwt", "hubspot")
        client._cache[cache_key] = expired_token

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "new-token",
            "token_type": "Bearer",
            "expires_in": 300,
        }
        mock_http = AsyncMock()
        mock_http.post = AsyncMock(return_value=mock_response)
        client._http_client = mock_http

        token = await client.get_backend_token("agent-jwt", "hubspot")
        assert token.access_token == "new-token"
        mock_http.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_force_refresh_bypasses_cache(self, client: TokenExchangeClient):
        cached_token = ExchangedToken(
            access_token="cached-valid",
            expires_in=200,
            issued_at=datetime.now(timezone.utc),
        )
        cache_key = client._cache_key("agent-jwt", "hubspot")
        client._cache[cache_key] = cached_token

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "forced-fresh",
            "token_type": "Bearer",
            "expires_in": 300,
        }
        mock_http = AsyncMock()
        mock_http.post = AsyncMock(return_value=mock_response)
        client._http_client = mock_http

        token = await client.get_backend_token(
            "agent-jwt", "hubspot", force_refresh=True
        )
        assert token.access_token == "forced-fresh"
        mock_http.post.assert_called_once()

    def test_put_cache_reduces_ttl_by_buffer(self, client: TokenExchangeClient):
        token = ExchangedToken(
            access_token="x",
            expires_in=300,
            issued_at=datetime.now(timezone.utc),
        )
        client._put_cache("key:hub", token)
        assert token.expires_in == 300 - client._config.cache_ttl_buffer_seconds

    def test_put_cache_clamps_to_zero(self):
        config = TokenExchangeConfig(cache_ttl_buffer_seconds=500)
        c = TokenExchangeClient(config=config)
        token = ExchangedToken(access_token="x", expires_in=100)
        c._put_cache("key:hub", token)
        assert token.expires_in == 0


# =============================================================================
# ExchangedToken.is_expired
# =============================================================================


class TestExchangedTokenExpiry:
    def test_not_expired(self):
        token = ExchangedToken(
            access_token="x",
            expires_in=300,
            issued_at=datetime.now(timezone.utc),
        )
        assert not token.is_expired

    def test_expired(self):
        token = ExchangedToken(
            access_token="x",
            expires_in=1,
            issued_at=datetime.now(timezone.utc) - timedelta(seconds=10),
        )
        assert token.is_expired

    def test_zero_expires_in_is_expired(self):
        token = ExchangedToken(access_token="x", expires_in=0)
        assert token.is_expired

    def test_negative_expires_in_is_expired(self):
        token = ExchangedToken(access_token="x", expires_in=-1)
        assert token.is_expired


# =============================================================================
# Disabled Client
# =============================================================================


class TestDisabledClient:
    @pytest.mark.asyncio
    async def test_disabled_raises_error(self):
        c = TokenExchangeClient(config=TokenExchangeConfig(enabled=False))
        with pytest.raises(TokenExchangeError) as exc_info:
            await c.get_backend_token("jwt", "hubspot")
        assert exc_info.value.error_code == "disabled"


# =============================================================================
# Module Accessor Pattern
# =============================================================================


class TestModuleAccessors:
    def test_lifecycle(self, config: TokenExchangeConfig):
        assert get_token_exchange_client() is None

        client = configure_token_exchange_client(config)
        assert get_token_exchange_client() is client
        assert client.config.enabled is True

        reset_token_exchange_client()
        assert get_token_exchange_client() is None

    def test_configure_with_default_config(self):
        client = configure_token_exchange_client()
        assert client.config.realm == "deepsecure"

    def test_configure_disabled(self):
        config = TokenExchangeConfig(enabled=False)
        client = configure_token_exchange_client(config)
        assert client.config.enabled is False


# =============================================================================
# Security
# =============================================================================


class TestSecurity:
    def test_cache_key_hides_token(self, client: TokenExchangeClient):
        key = client._cache_key("super-secret-agent-jwt-abc123", "hubspot")
        assert "super-secret" not in key
        assert "abc123" not in key
        assert ":" in key  # format: hash:backend

    def test_error_does_not_leak_keycloak_secrets(self):
        err = TokenExchangeDeniedError(
            "denied",
            error_code="invalid_grant",
            details={"backend_id": "hubspot"},
        )
        assert "secret" not in str(err)

    @pytest.mark.asyncio
    async def test_http_client_uses_configured_timeout(self, config: TokenExchangeConfig):
        config.request_timeout_seconds = 5
        c = TokenExchangeClient(config=config)
        http = c._get_http_client()
        assert http.timeout.connect == 5
        await http.aclose()
