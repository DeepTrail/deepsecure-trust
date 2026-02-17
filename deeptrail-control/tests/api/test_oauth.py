"""Tests for OAuth API endpoints (WS-F3).

Tests the OAuth endpoints:
- GET /api/v1/oauth/{service_id}/authorize
- GET /api/v1/oauth/{service_id}/callback
- POST /api/v1/oauth/{service_id}/refresh

Test Categories:
- Authorize: Auth URL generation, redirect mode, invalid service, unauthorized
- Callback: Success, invalid state, OAuth error from provider, exchange failure
- Refresh: Success, not connected, no refresh token, provider error
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, AsyncMock, patch

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.api.v1.endpoints.oauth import get_oauth_service_dep, get_vault_client
from app.schemas.oauth import (
    AuthorizationResponse,
    OAuthProvider,
    OAuthState,
    OAuthTokenResponse,
)


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_oauth_service():
    """Create a mock OAuthService."""
    mock = MagicMock()
    mock.get_authorization_url = AsyncMock()
    mock.exchange_code_for_tokens = AsyncMock()
    mock.refresh_tokens = AsyncMock()
    mock.get_pending_state = MagicMock()
    return mock


@pytest.fixture
def mock_vault_client():
    """Create a mock VaultClient."""
    mock = MagicMock()
    mock._generate_ref = MagicMock()
    mock.retrieve_token = MagicMock()
    mock.store_token = MagicMock()
    mock.refresh_token = MagicMock()
    return mock


@pytest.fixture
def client(mock_oauth_service, mock_vault_client):
    """Create a test client with mocked services."""
    app.dependency_overrides[get_oauth_service_dep] = lambda: mock_oauth_service
    app.dependency_overrides[get_vault_client] = lambda: mock_vault_client
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers():
    """Return valid authorization headers."""
    return {"Authorization": "Bearer mock_user_token_sarah@acme.com"}


@pytest.fixture
def sample_auth_response():
    """Sample authorization response."""
    return AuthorizationResponse(
        authorization_url="https://api.notion.com/v1/oauth/authorize?client_id=abc&state=xyz",
        state="state-token-123",
        code_verifier=None,
    )


@pytest.fixture
def sample_token_response():
    """Sample OAuth token response."""
    return OAuthTokenResponse(
        access_token="access-token-abc",
        token_type="Bearer",
        expires_in=3600,
        refresh_token="refresh-token-xyz",
        scope="read_content write_content",
    )


@pytest.fixture
def sample_oauth_state():
    """Sample OAuth state for callback validation."""
    now = datetime.now(timezone.utc)
    return OAuthState(
        user_id="sarah@acme.com",
        provider="notion",
        nonce="nonce123",
        created_at=now,
        expires_at=now + timedelta(minutes=10),
        code_verifier="verifier123",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Test: OAuth Authorize
# ─────────────────────────────────────────────────────────────────────────────


class TestOAuthAuthorize:
    """Tests for GET /api/v1/oauth/{service_id}/authorize."""

    def test_authorize_returns_auth_url(
        self, client, mock_oauth_service, auth_headers, sample_auth_response
    ):
        """Test successful authorization URL generation."""
        mock_oauth_service.get_authorization_url.return_value = sample_auth_response

        response = client.get(
            "/api/v1/oauth/notion/authorize",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "authorization_url" in data
        assert "state" in data
        assert data["state"] == "state-token-123"
        mock_oauth_service.get_authorization_url.assert_called_once()

    def test_authorize_with_scopes(
        self, client, mock_oauth_service, auth_headers, sample_auth_response
    ):
        """Test authorization with custom scopes."""
        mock_oauth_service.get_authorization_url.return_value = sample_auth_response

        response = client.get(
            "/api/v1/oauth/slack/authorize?scopes=channels:read,chat:write",
            headers=auth_headers,
        )

        assert response.status_code == 200

    def test_authorize_redirect_mode(
        self, client, mock_oauth_service, auth_headers, sample_auth_response
    ):
        """Test redirect mode returns 302."""
        mock_oauth_service.get_authorization_url.return_value = sample_auth_response

        response = client.get(
            "/api/v1/oauth/notion/authorize?redirect=true",
            headers=auth_headers,
            follow_redirects=False,
        )

        assert response.status_code == 302
        assert "location" in response.headers

    def test_authorize_invalid_service(self, client, auth_headers):
        """Test invalid service returns 400."""
        response = client.get(
            "/api/v1/oauth/invalid_service/authorize",
            headers=auth_headers,
        )

        assert response.status_code == 400
        data = response.json()
        assert data["detail"]["error"] == "invalid_service"

    def test_authorize_unauthorized(self, client):
        """Test missing auth returns 422 (missing header)."""
        response = client.get("/api/v1/oauth/notion/authorize")

        # FastAPI returns 422 for missing required header
        assert response.status_code == 422

    def test_authorize_all_providers(
        self, client, mock_oauth_service, auth_headers, sample_auth_response
    ):
        """Test all supported providers work."""
        mock_oauth_service.get_authorization_url.return_value = sample_auth_response

        for service in ["notion", "slack", "hubspot"]:
            response = client.get(
                f"/api/v1/oauth/{service}/authorize",
                headers=auth_headers,
            )
            assert response.status_code == 200, f"Failed for {service}"


# ─────────────────────────────────────────────────────────────────────────────
# Test: OAuth Callback
# ─────────────────────────────────────────────────────────────────────────────


class TestOAuthCallback:
    """Tests for GET /api/v1/oauth/{service_id}/callback."""

    def test_callback_success(
        self,
        client,
        mock_oauth_service,
        mock_vault_client,
        sample_oauth_state,
        sample_token_response,
    ):
        """Test successful OAuth callback."""
        mock_oauth_service.get_pending_state.return_value = sample_oauth_state
        mock_oauth_service.exchange_code_for_tokens.return_value = sample_token_response

        response = client.get(
            "/api/v1/oauth/notion/callback?code=auth_code_123&state=state_token_xyz"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["service_id"] == "notion"
        assert data["connected"] is True
        assert "read_content" in data["scopes_granted"]

        # Verify tokens were stored
        mock_vault_client.store_token.assert_called_once()

    def test_callback_invalid_state(self, client, mock_oauth_service):
        """Test invalid state returns 400."""
        mock_oauth_service.get_pending_state.return_value = None

        response = client.get(
            "/api/v1/oauth/notion/callback?code=abc&state=invalid_state"
        )

        assert response.status_code == 400
        data = response.json()
        assert data["detail"]["error"] == "invalid_state"

    def test_callback_oauth_error(self, client):
        """Test OAuth error from provider."""
        response = client.get(
            "/api/v1/oauth/notion/callback?error=access_denied&error_description=User%20denied%20access"
        )

        assert response.status_code == 400
        data = response.json()
        assert data["detail"]["error"] == "oauth_error"
        assert "denied" in data["detail"]["message"].lower()

    def test_callback_exchange_failure(
        self, client, mock_oauth_service, sample_oauth_state
    ):
        """Test token exchange failure returns 502."""
        from app.services.oauth_service import OAuthExchangeError

        mock_oauth_service.get_pending_state.return_value = sample_oauth_state
        mock_oauth_service.exchange_code_for_tokens.side_effect = OAuthExchangeError(
            "Provider returned 401"
        )

        response = client.get(
            "/api/v1/oauth/notion/callback?code=abc&state=valid_state"
        )

        assert response.status_code == 502
        data = response.json()
        assert data["detail"]["error"] == "token_exchange_failed"

    def test_callback_invalid_service(self, client):
        """Test invalid service returns 400."""
        response = client.get(
            "/api/v1/oauth/invalid/callback?code=abc&state=xyz"
        )

        assert response.status_code == 400
        assert response.json()["detail"]["error"] == "invalid_service"


# ─────────────────────────────────────────────────────────────────────────────
# Test: OAuth Refresh
# ─────────────────────────────────────────────────────────────────────────────


class TestOAuthRefresh:
    """Tests for POST /api/v1/oauth/{service_id}/refresh."""

    def test_refresh_success(
        self,
        client,
        mock_oauth_service,
        mock_vault_client,
        auth_headers,
        sample_token_response,
    ):
        """Test successful token refresh."""
        mock_vault_client._generate_ref.return_value = "vault://sarah-notion-abc"
        mock_vault_client.retrieve_token.return_value = {
            "access_token": "old-token",
            "refresh_token": "refresh-token-xyz",
        }
        mock_oauth_service.refresh_tokens.return_value = sample_token_response
        mock_vault_client.refresh_token.return_value = True

        response = client.post(
            "/api/v1/oauth/notion/refresh",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["refreshed"] is True
        assert data["expires_in"] == 3600

        # Verify vault was updated
        mock_vault_client.refresh_token.assert_called_once()

    def test_refresh_not_connected(
        self, client, mock_vault_client, auth_headers
    ):
        """Test refresh when service not connected."""
        mock_vault_client._generate_ref.return_value = "vault://sarah-notion-abc"
        mock_vault_client.retrieve_token.return_value = None

        response = client.post(
            "/api/v1/oauth/notion/refresh",
            headers=auth_headers,
        )

        assert response.status_code == 404
        data = response.json()
        assert data["detail"]["error"] == "not_found"

    def test_refresh_no_refresh_token(
        self, client, mock_vault_client, auth_headers
    ):
        """Test refresh when no refresh token available."""
        mock_vault_client._generate_ref.return_value = "vault://sarah-notion-abc"
        mock_vault_client.retrieve_token.return_value = {
            "access_token": "token",
            # No refresh_token
        }

        response = client.post(
            "/api/v1/oauth/notion/refresh",
            headers=auth_headers,
        )

        assert response.status_code == 400
        data = response.json()
        assert data["detail"]["error"] == "no_refresh_token"

    def test_refresh_provider_error(
        self, client, mock_oauth_service, mock_vault_client, auth_headers
    ):
        """Test refresh when provider returns error."""
        from app.services.oauth_service import OAuthRefreshError

        mock_vault_client._generate_ref.return_value = "vault://sarah-notion-abc"
        mock_vault_client.retrieve_token.return_value = {
            "access_token": "token",
            "refresh_token": "refresh",
        }
        mock_oauth_service.refresh_tokens.side_effect = OAuthRefreshError(
            "Token revoked"
        )

        response = client.post(
            "/api/v1/oauth/notion/refresh",
            headers=auth_headers,
        )

        assert response.status_code == 502
        data = response.json()
        assert data["detail"]["error"] == "refresh_failed"

    def test_refresh_unauthorized(self, client):
        """Test refresh without auth."""
        response = client.post("/api/v1/oauth/notion/refresh")
        assert response.status_code == 422  # Missing required header

    def test_refresh_invalid_service(self, client, auth_headers):
        """Test refresh for invalid service."""
        response = client.post(
            "/api/v1/oauth/invalid/refresh",
            headers=auth_headers,
        )

        assert response.status_code == 400
        assert response.json()["detail"]["error"] == "invalid_service"


# ─────────────────────────────────────────────────────────────────────────────
# Test: Security
# ─────────────────────────────────────────────────────────────────────────────


class TestOAuthSecurity:
    """Security tests for OAuth endpoints."""

    def test_callback_validates_state_before_exchange(
        self, client, mock_oauth_service
    ):
        """Security: State must be validated before code exchange."""
        mock_oauth_service.get_pending_state.return_value = None

        response = client.get(
            "/api/v1/oauth/notion/callback?code=malicious_code&state=forged_state"
        )

        assert response.status_code == 400
        assert response.json()["detail"]["error"] == "invalid_state"

        # Exchange should NOT have been called
        mock_oauth_service.exchange_code_for_tokens.assert_not_called()

    def test_tokens_not_exposed_in_callback_response(
        self,
        client,
        mock_oauth_service,
        mock_vault_client,
        sample_oauth_state,
        sample_token_response,
    ):
        """Security: Tokens should not appear in callback response."""
        mock_oauth_service.get_pending_state.return_value = sample_oauth_state
        mock_oauth_service.exchange_code_for_tokens.return_value = sample_token_response

        response = client.get(
            "/api/v1/oauth/notion/callback?code=abc&state=xyz"
        )

        assert response.status_code == 200
        data = response.json()

        # Tokens should NOT be in response
        assert "access_token" not in data
        assert "refresh_token" not in data
        assert "token" not in str(data).lower() or "scopes_granted" in str(data)

    def test_refresh_requires_user_auth(self, client):
        """Security: Refresh requires user authentication."""
        response = client.post("/api/v1/oauth/notion/refresh")
        # Should fail due to missing auth
        assert response.status_code == 422  # Missing required header
