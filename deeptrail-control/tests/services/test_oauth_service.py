"""Unit tests for OAuthService.

Tests cover:
- Authorization URL generation
- PKCE code generation and validation
- State management (creation, validation, expiration)
- Token exchange
- Token refresh
- Provider configuration
- Error handling
"""

import base64
import hashlib
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.oauth import (
    AuthorizationRequest,
    OAuthProvider,
    TokenExchangeRequest,
    TokenRefreshRequest,
)
from app.services.oauth_service import (
    OAuthConfigError,
    OAuthExchangeError,
    OAuthRefreshError,
    OAuthService,
    OAuthStateError,
    get_oauth_service,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def oauth_service() -> OAuthService:
    """Create an OAuthService for testing."""
    return OAuthService()


@pytest.fixture
def mock_env_vars(monkeypatch):
    """Set up mock environment variables for OAuth config."""
    monkeypatch.setenv("NOTION_CLIENT_ID", "notion_client_id_123")
    monkeypatch.setenv("NOTION_CLIENT_SECRET", "notion_client_secret_456")
    monkeypatch.setenv("SLACK_CLIENT_ID", "slack_client_id_123")
    monkeypatch.setenv("SLACK_CLIENT_SECRET", "slack_client_secret_456")
    monkeypatch.setenv("HUBSPOT_CLIENT_ID", "hubspot_client_id_123")
    monkeypatch.setenv("HUBSPOT_CLIENT_SECRET", "hubspot_client_secret_456")
    monkeypatch.setenv("OAUTH_REDIRECT_BASE_URL", "https://app.example.com")


# ============================================================================
# Authorization URL Generation Tests
# ============================================================================


class TestGetAuthorizationUrl:
    """Tests for get_authorization_url method."""

    @pytest.mark.asyncio
    async def test_generates_notion_url_with_pkce(
        self, oauth_service: OAuthService, mock_env_vars
    ):
        """get_authorization_url should generate Notion URL with PKCE."""
        request = AuthorizationRequest(
            provider=OAuthProvider.NOTION,
            user_id="user-123",
        )

        response = await oauth_service.get_authorization_url(request)

        assert "api.notion.com/v1/oauth/authorize" in response.authorization_url
        assert "code_challenge=" in response.authorization_url
        assert "code_challenge_method=S256" in response.authorization_url
        assert "state=" in response.authorization_url
        assert response.code_verifier is not None
        assert len(response.code_verifier) >= 43

    @pytest.mark.asyncio
    async def test_generates_slack_url_with_pkce(
        self, oauth_service: OAuthService, mock_env_vars
    ):
        """get_authorization_url should generate Slack URL with PKCE."""
        request = AuthorizationRequest(
            provider=OAuthProvider.SLACK,
            user_id="user-123",
        )

        response = await oauth_service.get_authorization_url(request)

        assert "slack.com/oauth/v2/authorize" in response.authorization_url
        assert "code_challenge=" in response.authorization_url
        assert "code_challenge_method=S256" in response.authorization_url
        assert "state=" in response.authorization_url
        assert response.code_verifier is not None

    @pytest.mark.asyncio
    async def test_generates_hubspot_url_with_scopes(
        self, oauth_service: OAuthService, mock_env_vars
    ):
        """get_authorization_url should include scopes for HubSpot."""
        request = AuthorizationRequest(
            provider=OAuthProvider.HUBSPOT,
            user_id="user-123",
        )

        response = await oauth_service.get_authorization_url(request)

        assert "app.hubspot.com/oauth/authorize" in response.authorization_url
        assert "scope=" in response.authorization_url
        assert "state=" in response.authorization_url

    @pytest.mark.asyncio
    async def test_stores_state_for_validation(
        self, oauth_service: OAuthService, mock_env_vars
    ):
        """get_authorization_url should store state for later validation."""
        request = AuthorizationRequest(
            provider=OAuthProvider.NOTION,
            user_id="user-123",
        )

        response = await oauth_service.get_authorization_url(request)

        state = oauth_service.get_pending_state(response.state)
        assert state is not None
        assert state.user_id == "user-123"
        assert state.provider == "notion"

    @pytest.mark.asyncio
    async def test_custom_scopes_override_defaults(
        self, oauth_service: OAuthService, mock_env_vars
    ):
        """get_authorization_url should use custom scopes if provided."""
        request = AuthorizationRequest(
            provider=OAuthProvider.SLACK,
            user_id="user-123",
            requested_scopes=["custom:scope"],
        )

        response = await oauth_service.get_authorization_url(request)

        assert "custom%3Ascope" in response.authorization_url or "custom:scope" in response.authorization_url

    @pytest.mark.asyncio
    async def test_raises_on_missing_config(self, oauth_service: OAuthService):
        """get_authorization_url should raise OAuthConfigError if env vars missing."""
        request = AuthorizationRequest(
            provider=OAuthProvider.NOTION,
            user_id="user-123",
        )

        with pytest.raises(OAuthConfigError) as exc_info:
            await oauth_service.get_authorization_url(request)

        assert "NOTION_CLIENT_ID" in str(exc_info.value)


# ============================================================================
# PKCE Tests
# ============================================================================


class TestPKCEGeneration:
    """Tests for PKCE code generation."""

    def test_generates_valid_verifier_length(self, oauth_service: OAuthService):
        """PKCE verifier should be 43-128 characters (RFC 7636)."""
        verifier, _ = oauth_service._generate_pkce_pair()

        assert len(verifier) >= 43
        assert len(verifier) <= 128

    def test_generates_valid_challenge(self, oauth_service: OAuthService):
        """PKCE challenge should be SHA256 hash of verifier, base64url encoded."""
        verifier, challenge = oauth_service._generate_pkce_pair()

        # Verify the challenge is correct
        expected_bytes = hashlib.sha256(verifier.encode("ascii")).digest()
        expected_challenge = (
            base64.urlsafe_b64encode(expected_bytes).rstrip(b"=").decode("ascii")
        )

        assert challenge == expected_challenge

    def test_generates_unique_pairs(self, oauth_service: OAuthService):
        """Each PKCE pair should be unique."""
        pairs = [oauth_service._generate_pkce_pair() for _ in range(10)]
        verifiers = [pair[0] for pair in pairs]

        assert len(set(verifiers)) == 10  # All unique


# ============================================================================
# State Management Tests
# ============================================================================


class TestStateManagement:
    """Tests for OAuth state management."""

    @pytest.mark.asyncio
    async def test_state_tokens_are_cryptographically_random(
        self, oauth_service: OAuthService, mock_env_vars
    ):
        """State tokens should be cryptographically random (32+ bytes)."""
        request = AuthorizationRequest(
            provider=OAuthProvider.SLACK,
            user_id="user-123",
        )

        responses = [
            await oauth_service.get_authorization_url(request)
            for _ in range(10)
        ]
        states = [r.state for r in responses]

        # All states should be unique
        assert len(set(states)) == 10
        # States should be reasonably long (32 bytes = ~43 chars base64)
        assert all(len(s) >= 40 for s in states)

    @pytest.mark.asyncio
    async def test_state_is_single_use(
        self, oauth_service: OAuthService, mock_env_vars
    ):
        """State tokens should be consumed on validation."""
        request = AuthorizationRequest(
            provider=OAuthProvider.SLACK,
            user_id="user-123",
        )

        response = await oauth_service.get_authorization_url(request)

        # First validation should succeed
        state = await oauth_service._validate_and_consume_state(response.state)
        assert state is not None

        # Second validation should fail
        with pytest.raises(OAuthStateError):
            await oauth_service._validate_and_consume_state(response.state)

    @pytest.mark.asyncio
    async def test_invalid_state_raises_error(self, oauth_service: OAuthService):
        """Invalid state tokens should raise OAuthStateError."""
        with pytest.raises(OAuthStateError):
            await oauth_service._validate_and_consume_state("invalid_state_token")

    @pytest.mark.asyncio
    async def test_expired_state_raises_error(
        self, oauth_service: OAuthService, mock_env_vars, monkeypatch
    ):
        """Expired state tokens should raise OAuthStateError."""
        # Set very short TTL
        monkeypatch.setenv("OAUTH_STATE_TTL_SECONDS", "0")

        request = AuthorizationRequest(
            provider=OAuthProvider.SLACK,
            user_id="user-123",
        )

        response = await oauth_service.get_authorization_url(request)

        # State should be expired immediately
        with pytest.raises(OAuthStateError) as exc_info:
            await oauth_service._validate_and_consume_state(response.state)

        assert "expired" in str(exc_info.value).lower()

    def test_clear_expired_states(self, oauth_service: OAuthService):
        """clear_expired_states should remove expired states."""
        # Manually add expired state
        from app.schemas.oauth import OAuthState
        import secrets

        expired_token = secrets.token_urlsafe(32)
        now = datetime.now(timezone.utc)
        oauth_service._pending_states[expired_token] = OAuthState(
            user_id="user-123",
            provider="test",
            nonce=secrets.token_hex(16),
            created_at=now - timedelta(hours=1),
            expires_at=now - timedelta(minutes=30),
        )

        cleared = oauth_service.clear_expired_states()

        assert cleared == 1
        assert expired_token not in oauth_service._pending_states


# ============================================================================
# Token Exchange Tests
# ============================================================================


class TestExchangeCodeForTokens:
    """Tests for exchange_code_for_tokens method."""

    @pytest.mark.asyncio
    async def test_exchanges_code_successfully(
        self, oauth_service: OAuthService, mock_env_vars
    ):
        """exchange_code_for_tokens should return tokens on success."""
        # First generate a valid state
        auth_request = AuthorizationRequest(
            provider=OAuthProvider.SLACK,
            user_id="user-123",
        )
        auth_response = await oauth_service.get_authorization_url(auth_request)

        # Mock the HTTP response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "slack_access_token",
            "token_type": "Bearer",
            "scope": "chat:write channels:read",
        }

        with patch.object(
            oauth_service, "_get_http_client"
        ) as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_get_client.return_value = mock_client

            exchange_request = TokenExchangeRequest(
                provider=OAuthProvider.SLACK,
                authorization_code="test_code_123",
                state=auth_response.state,
            )

            tokens = await oauth_service.exchange_code_for_tokens(exchange_request)

        assert tokens.access_token == "slack_access_token"
        assert tokens.token_type == "Bearer"

    @pytest.mark.asyncio
    async def test_validates_state_before_exchange(
        self, oauth_service: OAuthService, mock_env_vars
    ):
        """exchange_code_for_tokens should validate state before HTTP request."""
        exchange_request = TokenExchangeRequest(
            provider=OAuthProvider.SLACK,
            authorization_code="test_code_123",
            state="invalid_state",
        )

        with pytest.raises(OAuthStateError):
            await oauth_service.exchange_code_for_tokens(exchange_request)

    @pytest.mark.asyncio
    async def test_raises_on_http_error(
        self, oauth_service: OAuthService, mock_env_vars
    ):
        """exchange_code_for_tokens should raise OAuthExchangeError on HTTP failure."""
        # First generate a valid state
        auth_request = AuthorizationRequest(
            provider=OAuthProvider.SLACK,
            user_id="user-123",
        )
        auth_response = await oauth_service.get_authorization_url(auth_request)

        # Mock failed HTTP response
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "invalid_grant"

        with patch.object(
            oauth_service, "_get_http_client"
        ) as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_get_client.return_value = mock_client

            exchange_request = TokenExchangeRequest(
                provider=OAuthProvider.SLACK,
                authorization_code="invalid_code",
                state=auth_response.state,
            )

            with pytest.raises(OAuthExchangeError):
                await oauth_service.exchange_code_for_tokens(exchange_request)

    @pytest.mark.asyncio
    async def test_includes_pkce_verifier_for_notion(
        self, oauth_service: OAuthService, mock_env_vars
    ):
        """exchange_code_for_tokens should include code_verifier for Notion."""
        # Generate a valid state with PKCE
        auth_request = AuthorizationRequest(
            provider=OAuthProvider.NOTION,
            user_id="user-123",
        )
        auth_response = await oauth_service.get_authorization_url(auth_request)
        assert auth_response.code_verifier is not None

        # Mock the HTTP response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "notion_access_token",
            "token_type": "bearer",
            "bot_id": "bot123",
        }

        with patch.object(
            oauth_service, "_get_http_client"
        ) as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_get_client.return_value = mock_client

            exchange_request = TokenExchangeRequest(
                provider=OAuthProvider.NOTION,
                authorization_code="test_code",
                state=auth_response.state,
                code_verifier=auth_response.code_verifier,
            )

            await oauth_service.exchange_code_for_tokens(exchange_request)

            # Verify code_verifier was included in request
            call_args = mock_client.post.call_args
            assert "code_verifier" in str(call_args)


# ============================================================================
# Token Refresh Tests
# ============================================================================


class TestRefreshTokens:
    """Tests for refresh_tokens method."""

    @pytest.mark.asyncio
    async def test_refreshes_tokens_successfully(
        self, oauth_service: OAuthService, mock_env_vars
    ):
        """refresh_tokens should return new tokens on success."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "new_access_token",
            "token_type": "Bearer",
            "expires_in": 3600,
            "refresh_token": "new_refresh_token",
        }

        with patch.object(
            oauth_service, "_get_http_client"
        ) as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_get_client.return_value = mock_client

            request = TokenRefreshRequest(
                provider=OAuthProvider.SLACK,
                refresh_token="old_refresh_token",
                user_id="user-123",
            )

            tokens = await oauth_service.refresh_tokens(request)

        assert tokens.access_token == "new_access_token"
        assert tokens.refresh_token == "new_refresh_token"
        assert tokens.expires_in == 3600

    @pytest.mark.asyncio
    async def test_raises_on_revoked_token(
        self, oauth_service: OAuthService, mock_env_vars
    ):
        """refresh_tokens should raise OAuthRefreshError on revoked token."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "invalid_grant"

        with patch.object(
            oauth_service, "_get_http_client"
        ) as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_get_client.return_value = mock_client

            request = TokenRefreshRequest(
                provider=OAuthProvider.SLACK,
                refresh_token="revoked_token",
                user_id="user-123",
            )

            with pytest.raises(OAuthRefreshError):
                await oauth_service.refresh_tokens(request)


# ============================================================================
# Provider Configuration Tests
# ============================================================================


class TestGetProviderConfig:
    """Tests for get_provider_config method."""

    def test_returns_notion_config(self, oauth_service: OAuthService, mock_env_vars):
        """get_provider_config should return Notion configuration."""
        config = oauth_service.get_provider_config(OAuthProvider.NOTION)

        assert config.provider == OAuthProvider.NOTION
        assert config.client_id == "notion_client_id_123"
        assert config.uses_pkce is True
        assert "api.notion.com" in config.authorization_url

    def test_returns_slack_config(self, oauth_service: OAuthService, mock_env_vars):
        """get_provider_config should return Slack configuration."""
        config = oauth_service.get_provider_config(OAuthProvider.SLACK)

        assert config.provider == OAuthProvider.SLACK
        assert config.client_id == "slack_client_id_123"
        assert config.uses_pkce is True
        assert "slack.com" in config.authorization_url

    def test_returns_hubspot_config(self, oauth_service: OAuthService, mock_env_vars):
        """get_provider_config should return HubSpot configuration."""
        config = oauth_service.get_provider_config(OAuthProvider.HUBSPOT)

        assert config.provider == OAuthProvider.HUBSPOT
        assert config.client_id == "hubspot_client_id_123"
        assert config.uses_pkce is False
        assert "hubspot.com" in config.authorization_url

    def test_raises_on_missing_client_id(self, oauth_service: OAuthService, monkeypatch):
        """get_provider_config should raise OAuthConfigError if client_id missing."""
        monkeypatch.setenv("NOTION_CLIENT_SECRET", "secret")
        monkeypatch.setenv("OAUTH_REDIRECT_BASE_URL", "https://app.example.com")

        with pytest.raises(OAuthConfigError) as exc_info:
            oauth_service.get_provider_config(OAuthProvider.NOTION)

        assert "NOTION_CLIENT_ID" in str(exc_info.value)

    def test_raises_on_missing_redirect_url(
        self, oauth_service: OAuthService, monkeypatch
    ):
        """get_provider_config should raise OAuthConfigError if redirect URL missing."""
        monkeypatch.setenv("NOTION_CLIENT_ID", "client_id")
        monkeypatch.setenv("NOTION_CLIENT_SECRET", "secret")

        with pytest.raises(OAuthConfigError) as exc_info:
            oauth_service.get_provider_config(OAuthProvider.NOTION)

        assert "OAUTH_REDIRECT_BASE_URL" in str(exc_info.value)

    def test_builds_correct_redirect_uri(
        self, oauth_service: OAuthService, mock_env_vars
    ):
        """get_provider_config should build correct redirect URI."""
        config = oauth_service.get_provider_config(OAuthProvider.NOTION)

        assert config.redirect_uri == "https://app.example.com/api/v1/oauth/notion/callback"


# ============================================================================
# Security Tests
# ============================================================================


class TestSecurityProperties:
    """Tests for security properties."""

    def test_no_secrets_in_state(self, oauth_service: OAuthService, mock_env_vars):
        """State tokens should not contain sensitive data."""
        from app.schemas.oauth import OAuthState
        import secrets

        state = OAuthState(
            user_id="user-123",
            provider="notion",
            nonce=secrets.token_hex(16),
            created_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
        )

        # State should not contain secrets
        assert "client_secret" not in str(state)
        assert "access_token" not in str(state)

    def test_config_reads_from_environment(
        self, oauth_service: OAuthService, mock_env_vars, monkeypatch
    ):
        """Client secrets should only come from environment variables."""
        # Change the env var value
        monkeypatch.setenv("NOTION_CLIENT_SECRET", "new_secret_value")

        config = oauth_service.get_provider_config(OAuthProvider.NOTION)

        assert config.client_secret == "new_secret_value"


# ============================================================================
# Service Factory Tests
# ============================================================================


class TestServiceFactory:
    """Tests for get_oauth_service factory function."""

    def test_returns_singleton(self):
        """get_oauth_service should return the same instance."""
        # Clear global state
        import app.services.oauth_service as module
        module._oauth_service = None

        service1 = get_oauth_service()
        service2 = get_oauth_service()

        assert service1 is service2

        # Clean up
        module._oauth_service = None


# ============================================================================
# Token Response Normalization Tests
# ============================================================================


class TestTokenResponseNormalization:
    """Tests for _normalize_token_response method."""

    def test_normalizes_standard_response(self, oauth_service: OAuthService):
        """Should normalize standard OAuth response."""
        data = {
            "access_token": "token123",
            "token_type": "Bearer",
            "expires_in": 3600,
            "refresh_token": "refresh123",
            "scope": "read write",
        }

        result = oauth_service._normalize_token_response(OAuthProvider.HUBSPOT, data)

        assert result.access_token == "token123"
        assert result.token_type == "Bearer"
        assert result.expires_in == 3600
        assert result.refresh_token == "refresh123"
        assert result.scope == "read write"

    def test_normalizes_slack_nested_response(self, oauth_service: OAuthService):
        """Should normalize Slack's nested response, preferring authed_user token."""
        data = {
            "ok": True,
            "access_token": "bot_token",
            "authed_user": {
                "access_token": "user_token",
            },
            "token_type": "bearer",
            "scope": "chat:write",
        }

        result = oauth_service._normalize_token_response(OAuthProvider.SLACK, data)

        # authed_user.access_token is preferred over top-level token
        assert result.access_token == "user_token"

    def test_handles_missing_optional_fields(self, oauth_service: OAuthService):
        """Should handle missing optional fields gracefully."""
        data = {
            "access_token": "token123",
        }

        result = oauth_service._normalize_token_response(OAuthProvider.NOTION, data)

        assert result.access_token == "token123"
        assert result.token_type == "Bearer"
        assert result.expires_in is None
        assert result.refresh_token is None
        assert result.scope == "read_content update_content insert_content"
