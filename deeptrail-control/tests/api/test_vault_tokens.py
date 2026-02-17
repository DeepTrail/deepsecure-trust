"""Tests for vault token endpoints (WS-E2, WS-E3).

Tests:
- GET /api/v1/vault/tokens/{service_id} - Token retrieval
- POST /api/v1/vault/tokens/{service_id}/refresh - Token refresh

Test Cases for GET (WS-E2):
- Happy path: Valid JWT, connected service
- Unauthorized: Missing/invalid JWT (401)
- Forbidden: Service not in delegated_permissions (403)
- Not found: Service not connected (404)

Test Cases for POST (WS-E3):
- Happy path: Expired token, successful refresh
- Token still valid: Returns existing token (refreshed=False)
- Force refresh: Refreshes even if not expired (refreshed=True)
- Missing X-User-ID: Returns 422
- Invalid internal token: Returns 401
- Service not connected: Returns 404
- No refresh token: Returns 400
- Provider error: Returns 502
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, AsyncMock, patch

from fastapi.testclient import TestClient
import jwt

# Get the settings and app
from app.core.config import settings
from app.main import app
from app.api.v1.endpoints.vault import get_vault_client, get_oauth_service_dep
from app.schemas.oauth import OAuthTokenResponse


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_vault_client():
    """Create a mock VaultClient."""
    mock = MagicMock()
    return mock


@pytest.fixture
def client(mock_vault_client):
    """Create a test client with mocked VaultClient."""
    # Use FastAPI dependency override to inject mock
    app.dependency_overrides[get_vault_client] = lambda: mock_vault_client
    yield TestClient(app)
    # Clean up after test
    app.dependency_overrides.clear()


@pytest.fixture
def valid_agent_jwt():
    """Generate a valid agent JWT for testing."""
    now = datetime.now(timezone.utc)
    payload = {
        "iss": "deeptrail-control",
        "aud": "deeptrail-gateway",
        "sub": "agent-test-001",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=8)).timestamp()),
        "session_id": "test-session-123",
        "owner": "sarah@acme.com",
        "delegated_permissions": ["notion:read", "notion:write", "slack:read"],
        "delegation_id": "test-delegation-001",
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


@pytest.fixture
def expired_agent_jwt():
    """Generate an expired agent JWT."""
    now = datetime.now(timezone.utc)
    payload = {
        "iss": "deeptrail-control",
        "sub": "agent-test-001",
        "iat": int((now - timedelta(hours=10)).timestamp()),
        "exp": int((now - timedelta(hours=2)).timestamp()),  # Expired 2 hours ago
        "owner": "sarah@acme.com",
        "delegated_permissions": ["notion:read"],
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


@pytest.fixture
def jwt_without_owner():
    """Generate a JWT missing the owner claim."""
    now = datetime.now(timezone.utc)
    payload = {
        "iss": "deeptrail-control",
        "sub": "agent-test-001",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=8)).timestamp()),
        "delegated_permissions": ["notion:read"],
        # Missing 'owner' field
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


@pytest.fixture
def sample_token_data():
    """Sample OAuth token data as stored in vault."""
    return {
        "access_token": "xoxb-notion-token-abc123",
        "token_type": "bearer",
        "expires_in": 3600,
        "scope": "read write",
        "refresh_token": "refresh-secret-xyz",  # Should NOT be returned
    }


# ─────────────────────────────────────────────────────────────────────────────
# Test: Happy Path (200)
# ─────────────────────────────────────────────────────────────────────────────


class TestGetTokenHappyPath:
    """Test successful token retrieval."""

    def test_returns_token_for_delegated_service(
        self, client, mock_vault_client, valid_agent_jwt, sample_token_data
    ):
        """Should return token when service is delegated and connected."""
        # Setup mock
        mock_vault_client._generate_ref.return_value = "sarah-notion-ref"
        mock_vault_client.retrieve_token.return_value = sample_token_data

        response = client.get(
            "/api/v1/vault/tokens/notion",
            headers={"Authorization": f"Bearer {valid_agent_jwt}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["access_token"] == "xoxb-notion-token-abc123"
        assert data["token_type"] == "bearer"
        assert data["expires_in"] == 3600
        assert data["scope"] == "read write"

    def test_does_not_return_refresh_token(
        self, client, mock_vault_client, valid_agent_jwt, sample_token_data
    ):
        """Security: refresh_token should never be in response."""
        mock_vault_client._generate_ref.return_value = "sarah-notion-ref"
        mock_vault_client.retrieve_token.return_value = sample_token_data

        response = client.get(
            "/api/v1/vault/tokens/notion",
            headers={"Authorization": f"Bearer {valid_agent_jwt}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "refresh_token" not in data

    def test_handles_scope_as_list(self, client, mock_vault_client, valid_agent_jwt):
        """Should convert scope list to space-separated string."""
        token_data = {
            "access_token": "test-token",
            "token_type": "bearer",
            "scope": ["read_content", "write_content", "search"],
        }
        mock_vault_client._generate_ref.return_value = "ref"
        mock_vault_client.retrieve_token.return_value = token_data

        response = client.get(
            "/api/v1/vault/tokens/notion",
            headers={"Authorization": f"Bearer {valid_agent_jwt}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["scope"] == "read_content write_content search"

    def test_handles_missing_optional_fields(
        self, client, mock_vault_client, valid_agent_jwt
    ):
        """Should work when optional fields are missing."""
        token_data = {
            "access_token": "minimal-token",
            # No token_type, expires_in, or scope
        }
        mock_vault_client._generate_ref.return_value = "ref"
        mock_vault_client.retrieve_token.return_value = token_data

        response = client.get(
            "/api/v1/vault/tokens/notion",
            headers={"Authorization": f"Bearer {valid_agent_jwt}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["access_token"] == "minimal-token"
        assert data["token_type"] == "bearer"  # Default
        assert data["expires_in"] is None
        assert data["scope"] is None


# ─────────────────────────────────────────────────────────────────────────────
# Test: Unauthorized (401)
# ─────────────────────────────────────────────────────────────────────────────


class TestGetTokenUnauthorized:
    """Test 401 responses for authentication failures."""

    def test_missing_authorization_header(self, client, mock_vault_client):
        """Should return 401 when Authorization header is missing."""
        response = client.get("/api/v1/vault/tokens/notion")

        assert response.status_code == 401
        data = response.json()
        assert data["detail"]["error"] == "unauthorized"

    def test_invalid_jwt_format(self, client, mock_vault_client):
        """Should return 401 for malformed JWT."""
        response = client.get(
            "/api/v1/vault/tokens/notion",
            headers={"Authorization": "Bearer not-a-valid-jwt"},
        )

        assert response.status_code == 401
        data = response.json()
        assert data["detail"]["error"] == "unauthorized"

    def test_expired_jwt(self, client, mock_vault_client, expired_agent_jwt):
        """Should return 401 for expired JWT."""
        response = client.get(
            "/api/v1/vault/tokens/notion",
            headers={"Authorization": f"Bearer {expired_agent_jwt}"},
        )

        assert response.status_code == 401
        data = response.json()
        assert data["detail"]["error"] == "unauthorized"

    def test_jwt_missing_owner_claim(self, client, mock_vault_client, jwt_without_owner):
        """Should return 401 when JWT is missing user identity."""
        response = client.get(
            "/api/v1/vault/tokens/notion",
            headers={"Authorization": f"Bearer {jwt_without_owner}"},
        )

        assert response.status_code == 401
        data = response.json()
        assert data["detail"]["error"] == "unauthorized"


# ─────────────────────────────────────────────────────────────────────────────
# Test: Forbidden (403)
# ─────────────────────────────────────────────────────────────────────────────


class TestGetTokenForbidden:
    """Test 403 responses when service not delegated."""

    def test_service_not_in_delegated_permissions(
        self, client, mock_vault_client, valid_agent_jwt
    ):
        """Should return 403 when service is not in delegated_permissions."""
        # hubspot is NOT in valid_agent_jwt's delegated_permissions
        response = client.get(
            "/api/v1/vault/tokens/hubspot",
            headers={"Authorization": f"Bearer {valid_agent_jwt}"},
        )

        assert response.status_code == 403
        data = response.json()
        assert data["detail"]["error"] == "forbidden"
        assert data["detail"]["message"] == "Service not delegated"

    def test_partial_match_does_not_grant_access(self, client, mock_vault_client):
        """Should not match 'notion' for 'notionv2' service."""
        now = datetime.now(timezone.utc)
        payload = {
            "iss": "deeptrail-control",
            "sub": "agent-test",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(hours=1)).timestamp()),
            "owner": "user@example.com",
            "delegated_permissions": ["notion:read"],
        }
        token = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")

        response = client.get(
            "/api/v1/vault/tokens/notionv2",  # Not "notion"
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 403

    def test_empty_permissions_returns_403(self, client, mock_vault_client):
        """Should return 403 when delegated_permissions is empty."""
        now = datetime.now(timezone.utc)
        payload = {
            "iss": "deeptrail-control",
            "sub": "agent-test",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(hours=1)).timestamp()),
            "owner": "user@example.com",
            "delegated_permissions": [],  # Empty
        }
        token = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")

        response = client.get(
            "/api/v1/vault/tokens/notion",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 403


# ─────────────────────────────────────────────────────────────────────────────
# Test: Not Found (404)
# ─────────────────────────────────────────────────────────────────────────────


class TestGetTokenNotFound:
    """Test 404 responses when service not connected."""

    def test_service_not_connected(
        self, client, mock_vault_client, valid_agent_jwt
    ):
        """Should return 404 when user has not connected the service."""
        mock_vault_client._generate_ref.return_value = "sarah-notion-ref"
        mock_vault_client.retrieve_token.return_value = None  # Not connected

        response = client.get(
            "/api/v1/vault/tokens/notion",
            headers={"Authorization": f"Bearer {valid_agent_jwt}"},
        )

        assert response.status_code == 404
        data = response.json()
        assert data["detail"]["error"] == "not_found"
        assert data["detail"]["message"] == "Service not connected"

    def test_token_data_missing_access_token(
        self, client, mock_vault_client, valid_agent_jwt
    ):
        """Should return 404 when token data is corrupt (no access_token)."""
        mock_vault_client._generate_ref.return_value = "ref"
        mock_vault_client.retrieve_token.return_value = {
            "token_type": "bearer",
            # Missing access_token
        }

        response = client.get(
            "/api/v1/vault/tokens/notion",
            headers={"Authorization": f"Bearer {valid_agent_jwt}"},
        )

        assert response.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# Test: Permission Matching
# ─────────────────────────────────────────────────────────────────────────────


class TestPermissionMatching:
    """Test permission matching logic."""

    def test_exact_service_match(self, client, mock_vault_client, sample_token_data):
        """Should match when permission is exact service name."""
        now = datetime.now(timezone.utc)
        payload = {
            "iss": "deeptrail-control",
            "sub": "agent-test",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(hours=1)).timestamp()),
            "owner": "user@example.com",
            "delegated_permissions": ["notion"],  # Exact match
        }
        token = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")

        mock_vault_client._generate_ref.return_value = "ref"
        mock_vault_client.retrieve_token.return_value = sample_token_data

        response = client.get(
            "/api/v1/vault/tokens/notion",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200

    def test_service_prefix_match(self, client, mock_vault_client, sample_token_data):
        """Should match when permission starts with service:."""
        now = datetime.now(timezone.utc)
        payload = {
            "iss": "deeptrail-control",
            "sub": "agent-test",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(hours=1)).timestamp()),
            "owner": "user@example.com",
            "delegated_permissions": ["slack:channels:read"],  # Prefix match
        }
        token = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")

        mock_vault_client._generate_ref.return_value = "ref"
        mock_vault_client.retrieve_token.return_value = sample_token_data

        response = client.get(
            "/api/v1/vault/tokens/slack",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200

    def test_multiple_permissions_for_same_service(
        self, client, mock_vault_client, sample_token_data
    ):
        """Should work when user has multiple permissions for service."""
        now = datetime.now(timezone.utc)
        payload = {
            "iss": "deeptrail-control",
            "sub": "agent-test",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(hours=1)).timestamp()),
            "owner": "user@example.com",
            "delegated_permissions": [
                "hubspot:contacts:read",
                "hubspot:contacts:write",
                "hubspot:deals:read",
            ],
        }
        token = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")

        mock_vault_client._generate_ref.return_value = "ref"
        mock_vault_client.retrieve_token.return_value = sample_token_data

        response = client.get(
            "/api/v1/vault/tokens/hubspot",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200


# ─────────────────────────────────────────────────────────────────────────────
# Test: Token Refresh Endpoint (WS-E3)
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_oauth_service():
    """Create a mock OAuthService."""
    mock = MagicMock()
    mock.refresh_tokens = AsyncMock()
    return mock


@pytest.fixture
def client_with_oauth(mock_vault_client, mock_oauth_service):
    """Create a test client with mocked VaultClient and OAuthService."""
    app.dependency_overrides[get_vault_client] = lambda: mock_vault_client
    app.dependency_overrides[get_oauth_service_dep] = lambda: mock_oauth_service
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def valid_internal_token():
    """Return the valid internal API token for testing."""
    return settings.GATEWAY_INTERNAL_API_TOKEN


@pytest.fixture
def sample_token_data_with_refresh():
    """Sample OAuth token data with refresh token and metadata."""
    return {
        "access_token": "old-access-token-123",
        "token_type": "bearer",
        "refresh_token": "refresh-secret-xyz",
        "metadata": {
            "created_at": "2026-02-16T12:00:00+00:00",
            "expires_at": "2026-02-16T11:00:00+00:00",  # Already expired
            "last_used_at": None,
            "refresh_count": 0,
        },
    }


@pytest.fixture
def sample_token_data_valid():
    """Sample OAuth token data that is still valid."""
    future = datetime.now(timezone.utc) + timedelta(hours=1)
    return {
        "access_token": "valid-access-token-456",
        "token_type": "bearer",
        "refresh_token": "refresh-secret-xyz",
        "metadata": {
            "created_at": "2026-02-16T12:00:00+00:00",
            "expires_at": future.isoformat(),
            "last_used_at": None,
            "refresh_count": 0,
        },
    }


class TestRefreshTokenHappyPath:
    """Test successful token refresh scenarios."""

    def test_refresh_expired_token(
        self,
        client_with_oauth,
        mock_vault_client,
        mock_oauth_service,
        valid_internal_token,
        sample_token_data_with_refresh,
    ):
        """Should refresh token when expired."""
        # Setup mocks
        mock_vault_client._generate_ref.return_value = "sarah-notion-ref"
        mock_vault_client.retrieve_token.return_value = sample_token_data_with_refresh
        mock_vault_client.is_token_expired.return_value = True
        mock_vault_client.refresh_token.return_value = True

        mock_oauth_service.refresh_tokens.return_value = OAuthTokenResponse(
            access_token="new-access-token-789",
            token_type="bearer",
            expires_in=3600,
            refresh_token="new-refresh-token-abc",
        )

        response = client_with_oauth.post(
            "/api/v1/vault/tokens/notion/refresh",
            headers={
                "Authorization": f"Bearer {valid_internal_token}",
                "X-User-ID": "sarah@acme.com",
            },
            json={"force": False},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["access_token"] == "new-access-token-789"
        assert data["refreshed"] is True
        assert data["message"] == "Token refreshed"
        assert data["expires_in"] == 3600

    def test_force_refresh_valid_token(
        self,
        client_with_oauth,
        mock_vault_client,
        mock_oauth_service,
        valid_internal_token,
        sample_token_data_valid,
    ):
        """Should refresh token when force=True even if not expired."""
        # Setup mocks
        mock_vault_client._generate_ref.return_value = "sarah-notion-ref"
        mock_vault_client.retrieve_token.return_value = sample_token_data_valid
        mock_vault_client.is_token_expired.return_value = False  # Not expired
        mock_vault_client.refresh_token.return_value = True

        mock_oauth_service.refresh_tokens.return_value = OAuthTokenResponse(
            access_token="forced-new-token",
            token_type="bearer",
            expires_in=3600,
        )

        response = client_with_oauth.post(
            "/api/v1/vault/tokens/notion/refresh",
            headers={
                "Authorization": f"Bearer {valid_internal_token}",
                "X-User-ID": "sarah@acme.com",
            },
            json={"force": True},  # Force refresh
        )

        assert response.status_code == 200
        data = response.json()
        assert data["access_token"] == "forced-new-token"
        assert data["refreshed"] is True

    def test_skip_refresh_if_not_expired(
        self,
        client_with_oauth,
        mock_vault_client,
        mock_oauth_service,
        valid_internal_token,
        sample_token_data_valid,
    ):
        """Should return existing token if not expired and force=False."""
        # Setup mocks
        mock_vault_client._generate_ref.return_value = "sarah-notion-ref"
        mock_vault_client.retrieve_token.return_value = sample_token_data_valid
        mock_vault_client.is_token_expired.return_value = False  # Not expired

        response = client_with_oauth.post(
            "/api/v1/vault/tokens/notion/refresh",
            headers={
                "Authorization": f"Bearer {valid_internal_token}",
                "X-User-ID": "sarah@acme.com",
            },
            json={"force": False},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["access_token"] == "valid-access-token-456"
        assert data["refreshed"] is False
        assert data["message"] == "Token still valid"
        # OAuth service should NOT have been called
        mock_oauth_service.refresh_tokens.assert_not_called()


class TestRefreshTokenUnauthorized:
    """Test 401 responses for authentication failures."""

    def test_missing_internal_token(self, client_with_oauth, mock_vault_client):
        """Should return 401 when Authorization header is missing."""
        response = client_with_oauth.post(
            "/api/v1/vault/tokens/notion/refresh",
            headers={"X-User-ID": "sarah@acme.com"},
            json={"force": False},
        )

        assert response.status_code == 401
        data = response.json()
        assert data["detail"]["error"] == "unauthorized"

    def test_invalid_internal_token(self, client_with_oauth, mock_vault_client):
        """Should return 401 for invalid internal token."""
        response = client_with_oauth.post(
            "/api/v1/vault/tokens/notion/refresh",
            headers={
                "Authorization": "Bearer wrong-token",
                "X-User-ID": "sarah@acme.com",
            },
            json={"force": False},
        )

        assert response.status_code == 401
        data = response.json()
        assert data["detail"]["error"] == "unauthorized"


class TestRefreshTokenValidation:
    """Test validation error responses."""

    def test_missing_x_user_id_header(
        self, client_with_oauth, mock_vault_client, valid_internal_token
    ):
        """Should return 422 when X-User-ID header is missing."""
        response = client_with_oauth.post(
            "/api/v1/vault/tokens/notion/refresh",
            headers={"Authorization": f"Bearer {valid_internal_token}"},
            json={"force": False},
        )

        assert response.status_code == 422  # FastAPI validation error


class TestRefreshTokenNotFound:
    """Test 404 responses when service not connected."""

    def test_service_not_connected(
        self, client_with_oauth, mock_vault_client, valid_internal_token
    ):
        """Should return 404 when service not connected."""
        mock_vault_client._generate_ref.return_value = "sarah-notion-ref"
        mock_vault_client.retrieve_token.return_value = None  # Not connected

        response = client_with_oauth.post(
            "/api/v1/vault/tokens/notion/refresh",
            headers={
                "Authorization": f"Bearer {valid_internal_token}",
                "X-User-ID": "sarah@acme.com",
            },
            json={"force": False},
        )

        assert response.status_code == 404
        data = response.json()
        assert data["detail"]["error"] == "not_found"


class TestRefreshTokenNoRefreshToken:
    """Test 400 responses when no refresh token available."""

    def test_no_refresh_token(
        self, client_with_oauth, mock_vault_client, valid_internal_token
    ):
        """Should return 400 when service has no refresh token."""
        token_data = {
            "access_token": "test-token",
            "token_type": "bearer",
            # No refresh_token
        }
        mock_vault_client._generate_ref.return_value = "sarah-notion-ref"
        mock_vault_client.retrieve_token.return_value = token_data

        response = client_with_oauth.post(
            "/api/v1/vault/tokens/notion/refresh",
            headers={
                "Authorization": f"Bearer {valid_internal_token}",
                "X-User-ID": "sarah@acme.com",
            },
            json={"force": False},
        )

        assert response.status_code == 400
        data = response.json()
        assert data["detail"]["error"] == "no_refresh_token"


class TestRefreshTokenProviderError:
    """Test 502 responses when OAuth provider fails."""

    def test_oauth_provider_error(
        self,
        client_with_oauth,
        mock_vault_client,
        mock_oauth_service,
        valid_internal_token,
        sample_token_data_with_refresh,
    ):
        """Should return 502 when OAuth provider fails."""
        from app.services.oauth_service import OAuthRefreshError

        mock_vault_client._generate_ref.return_value = "sarah-notion-ref"
        mock_vault_client.retrieve_token.return_value = sample_token_data_with_refresh
        mock_vault_client.is_token_expired.return_value = True

        mock_oauth_service.refresh_tokens.side_effect = OAuthRefreshError(
            "Provider returned 401"
        )

        response = client_with_oauth.post(
            "/api/v1/vault/tokens/notion/refresh",
            headers={
                "Authorization": f"Bearer {valid_internal_token}",
                "X-User-ID": "sarah@acme.com",
            },
            json={"force": True},
        )

        assert response.status_code == 502
        data = response.json()
        assert data["detail"]["error"] == "provider_error"


class TestRefreshTokenDoesNotExposeRefreshToken:
    """Security tests for refresh endpoint."""

    def test_response_does_not_include_refresh_token(
        self,
        client_with_oauth,
        mock_vault_client,
        mock_oauth_service,
        valid_internal_token,
        sample_token_data_with_refresh,
    ):
        """Security: refresh_token should never be in response."""
        mock_vault_client._generate_ref.return_value = "sarah-notion-ref"
        mock_vault_client.retrieve_token.return_value = sample_token_data_with_refresh
        mock_vault_client.is_token_expired.return_value = True
        mock_vault_client.refresh_token.return_value = True

        mock_oauth_service.refresh_tokens.return_value = OAuthTokenResponse(
            access_token="new-token",
            token_type="bearer",
            expires_in=3600,
            refresh_token="new-refresh-token",  # This should NOT be returned
        )

        response = client_with_oauth.post(
            "/api/v1/vault/tokens/notion/refresh",
            headers={
                "Authorization": f"Bearer {valid_internal_token}",
                "X-User-ID": "sarah@acme.com",
            },
            json={"force": True},
        )

        assert response.status_code == 200
        data = response.json()
        assert "refresh_token" not in data
