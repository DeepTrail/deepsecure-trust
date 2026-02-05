"""
Tests for JWT validation middleware (WS-C3).

Comprehensive tests for the enhanced JWT validation middleware that validates
Agent Session JWTs (Layer 3) issued by the Control Plane.
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from fastapi import FastAPI, Request, Depends
from fastapi.testclient import TestClient
from jose import jwt as jose_jwt

from app.middleware.jwt_validation import (
    AgentContext,
    JWTValidationError,
    JWTValidationMiddleware,
    get_agent_context,
    require_any_permission,
    require_permission,
)


# =============================================================================
# Test Configuration
# =============================================================================

TEST_SECRET = "test-secret-key-for-jwt-validation"
TEST_ALGORITHM = "HS256"


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def valid_layer3_payload():
    """Create a valid Agent Session JWT (Layer 3) payload."""
    now = datetime.now(timezone.utc)
    return {
        "sub": "agent-sdr-001",
        "owner": "sarah@acme.com",
        "idp_issuer": "https://acme.okta.com",
        "party_type": "first_party",
        "delegated_permissions": [
            "notion:pages:search",
            "notion:pages:read",
            "slack:messages:search",
        ],
        "delegation_id": "del-sarah-sdr-001",
        "groups": ["sales"],
        "session_id": "asess-sdr-001-abc123",
        "iss": "deeptrail-control",
        "aud": "deeptrail-gateway",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=8)).timestamp()),
    }


@pytest.fixture
def valid_layer3_token(valid_layer3_payload):
    """Create a valid Layer 3 JWT token."""
    return jose_jwt.encode(valid_layer3_payload, TEST_SECRET, algorithm=TEST_ALGORITHM)


@pytest.fixture
def legacy_payload():
    """Create a legacy JWT payload (without Layer 3 claims)."""
    now = datetime.now(timezone.utc)
    return {
        "sub": "agent-legacy-001",
        "agent_id": "agent-legacy-001",
        "scope": "read write",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=1)).timestamp()),
    }


@pytest.fixture
def legacy_token(legacy_payload):
    """Create a legacy JWT token."""
    return jose_jwt.encode(legacy_payload, TEST_SECRET, algorithm=TEST_ALGORITHM)


def create_test_app():
    """Create a test FastAPI app with endpoints."""
    app = FastAPI()

    @app.get("/health")
    async def health():
        return {"status": "healthy"}

    @app.get("/mcp/tools")
    async def list_tools(request: Request):
        return {
            "agent_id": getattr(request.state, "agent_id", None),
            "permissions": getattr(request.state, "agent_permissions", []),
            "session_id": getattr(request.state, "session_id", None),
        }

    @app.get("/mcp/context")
    async def get_context(request: Request):
        ctx = getattr(request.state, "agent_context", None)
        if ctx:
            return {
                "agent_id": ctx.agent_id,
                "owner": ctx.owner,
                "delegation_id": ctx.delegation_id,
                "session_id": ctx.session_id,
                "permissions_count": len(ctx.delegated_permissions),
                "groups": ctx.groups,
                "party_type": ctx.party_type,
            }
        return {"error": "no context"}

    @app.get("/proxy/test")
    async def proxy_test(request: Request):
        return {"agent_id": getattr(request.state, "agent_id", None)}

    @app.get("/api/v1/tools/list")
    async def api_tools(request: Request):
        return {"agent_id": getattr(request.state, "agent_id", None)}

    @app.get("/other/endpoint")
    async def other_endpoint():
        return {"message": "no auth required"}

    @app.get("/test")
    async def test_endpoint(request: Request):
        ctx = getattr(request.state, "agent_context", None)
        if ctx:
            return {"agent_id": ctx.agent_id}
        return {"error": "no context"}

    return app


@pytest.fixture
def mock_config():
    """Mock the proxy config with test secret."""
    mock = MagicMock()
    mock.security.jwt_secret_key = TEST_SECRET
    mock.security.jwt_algorithm = TEST_ALGORITHM
    mock.security.jwt_access_token_expire_minutes = 30
    return mock


@pytest.fixture
def client(mock_config):
    """
    Create test client with JWT middleware configured with test secret.

    The config patching must happen BEFORE the middleware is instantiated,
    so we patch it, then create the app with middleware.
    """
    with patch("app.middleware.jwt_validation.config", mock_config):
        app = create_test_app()
        app.add_middleware(JWTValidationMiddleware)
        yield TestClient(app)


@pytest.fixture
def app_with_middleware(mock_config):
    """Create FastAPI app with JWT middleware using test credentials."""
    with patch("app.middleware.jwt_validation.config", mock_config):
        app = create_test_app()
        app.add_middleware(JWTValidationMiddleware)
        yield app


# =============================================================================
# AgentContext Tests
# =============================================================================


class TestAgentContext:
    """Tests for AgentContext dataclass."""

    def test_from_jwt_payload(self, valid_layer3_payload):
        """Test creating AgentContext from JWT payload."""
        context = AgentContext.from_jwt_payload(valid_layer3_payload)

        assert context.agent_id == "agent-sdr-001"
        assert context.owner == "sarah@acme.com"
        assert context.delegation_id == "del-sarah-sdr-001"
        assert context.session_id == "asess-sdr-001-abc123"
        assert len(context.delegated_permissions) == 3
        assert context.groups == ["sales"]
        assert context.party_type == "first_party"
        assert context.idp_issuer == "https://acme.okta.com"

    def test_from_jwt_payload_defaults(self):
        """Test AgentContext defaults when claims are missing."""
        payload = {"sub": "agent-001"}

        context = AgentContext.from_jwt_payload(payload)

        assert context.agent_id == "agent-001"
        assert context.owner == ""
        assert context.delegation_id == ""
        assert context.session_id == ""
        assert context.delegated_permissions == []
        assert context.groups == []
        assert context.party_type == "first_party"
        assert context.idp_issuer is None

    def test_has_permission(self, valid_layer3_payload):
        """Test permission checking."""
        context = AgentContext.from_jwt_payload(valid_layer3_payload)

        assert context.has_permission("notion:pages:search") is True
        assert context.has_permission("notion:pages:read") is True
        assert context.has_permission("slack:messages:search") is True
        assert context.has_permission("notion:pages:delete") is False
        assert context.has_permission("hubspot:contacts:read") is False

    def test_has_any_permission(self, valid_layer3_payload):
        """Test checking any of multiple permissions."""
        context = AgentContext.from_jwt_payload(valid_layer3_payload)

        assert context.has_any_permission(["notion:pages:search", "notion:pages:write"])
        assert context.has_any_permission(["notion:pages:read"])
        assert not context.has_any_permission(
            ["hubspot:contacts:read", "hubspot:contacts:write"]
        )
        assert not context.has_any_permission([])

    def test_has_all_permissions(self, valid_layer3_payload):
        """Test checking all of multiple permissions."""
        context = AgentContext.from_jwt_payload(valid_layer3_payload)

        assert context.has_all_permissions(["notion:pages:search", "notion:pages:read"])
        assert context.has_all_permissions(["notion:pages:search"])
        assert not context.has_all_permissions(
            ["notion:pages:search", "notion:pages:delete"]
        )
        assert context.has_all_permissions([])  # Empty list returns True

    def test_empty_permissions(self):
        """Test context with empty permissions."""
        payload = {
            "sub": "agent-001",
            "owner": "user@example.com",
            "delegation_id": "del-001",
            "session_id": "sess-001",
            "delegated_permissions": [],
        }

        context = AgentContext.from_jwt_payload(payload)

        assert context.delegated_permissions == []
        assert context.has_permission("any:permission") is False
        assert context.has_any_permission(["any:permission"]) is False


# =============================================================================
# JWTValidationError Tests
# =============================================================================


class TestJWTValidationError:
    """Tests for JWTValidationError exception."""

    def test_error_with_all_fields(self):
        """Test error with all fields."""
        error = JWTValidationError(
            status_code=401,
            detail="Token expired",
            error_code="token_expired",
            headers={"X-Custom": "value"},
        )

        assert error.status_code == 401
        assert error.detail == "Token expired"
        assert error.error_code == "token_expired"
        assert error.headers == {"X-Custom": "value"}

    def test_error_default_fields(self):
        """Test error with default fields."""
        error = JWTValidationError(
            status_code=401,
            detail="Invalid token",
        )

        assert error.error_code == "jwt_invalid"
        assert error.headers == {}

    def test_error_is_exception(self):
        """Test that error is a proper exception."""
        error = JWTValidationError(status_code=401, detail="Test error")

        with pytest.raises(JWTValidationError) as exc_info:
            raise error

        assert str(exc_info.value) == "Test error"


# =============================================================================
# JWT Validation Tests - Layer 3 Format
# =============================================================================


class TestJWTValidationLayer3:
    """Tests for Layer 3 Agent Session JWT validation."""

    def test_valid_token_accepted(self, client, valid_layer3_token):
        """Test that valid Layer 3 tokens are accepted."""
        response = client.get(
            "/mcp/tools", headers={"Authorization": f"Bearer {valid_layer3_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["agent_id"] == "agent-sdr-001"
        assert "notion:pages:search" in data["permissions"]
        assert data["session_id"] == "asess-sdr-001-abc123"

    def test_agent_context_populated(self, client, valid_layer3_token):
        """Test that AgentContext is populated in request state."""
        response = client.get(
            "/mcp/context", headers={"Authorization": f"Bearer {valid_layer3_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["agent_id"] == "agent-sdr-001"
        assert data["owner"] == "sarah@acme.com"
        assert data["delegation_id"] == "del-sarah-sdr-001"
        assert data["session_id"] == "asess-sdr-001-abc123"
        assert data["permissions_count"] == 3
        assert data["groups"] == ["sales"]
        assert data["party_type"] == "first_party"

    def test_expired_token(self, client, valid_layer3_payload):
        """Test 401 for expired token."""
        valid_layer3_payload["exp"] = (
            datetime.now(timezone.utc) - timedelta(hours=1)
        ).timestamp()
        expired_token = jose_jwt.encode(
            valid_layer3_payload, TEST_SECRET, algorithm=TEST_ALGORITHM
        )

        response = client.get(
            "/mcp/tools", headers={"Authorization": f"Bearer {expired_token}"}
        )

        assert response.status_code == 401
        assert response.json()["error"] == "token_expired"

    def test_invalid_signature(self, client, valid_layer3_payload):
        """Test 401 for invalid signature."""
        bad_token = jose_jwt.encode(
            valid_layer3_payload, "wrong-secret", algorithm=TEST_ALGORITHM
        )

        response = client.get(
            "/mcp/tools", headers={"Authorization": f"Bearer {bad_token}"}
        )

        assert response.status_code == 401
        assert response.json()["error"] == "invalid_signature"

    def test_wrong_issuer(self, client, valid_layer3_payload):
        """Test 401 for wrong issuer."""
        valid_layer3_payload["iss"] = "wrong-issuer"
        bad_token = jose_jwt.encode(
            valid_layer3_payload, TEST_SECRET, algorithm=TEST_ALGORITHM
        )

        response = client.get(
            "/mcp/tools", headers={"Authorization": f"Bearer {bad_token}"}
        )

        assert response.status_code == 401
        # Falls back to legacy mode but still validates

    def test_wrong_audience(self, client, valid_layer3_payload):
        """Test 401 for wrong audience."""
        valid_layer3_payload["aud"] = "wrong-audience"
        bad_token = jose_jwt.encode(
            valid_layer3_payload, TEST_SECRET, algorithm=TEST_ALGORITHM
        )

        response = client.get(
            "/mcp/tools", headers={"Authorization": f"Bearer {bad_token}"}
        )

        assert response.status_code == 401
        # Falls back to legacy mode but still validates

    def test_missing_sub_claim(self, client, valid_layer3_payload):
        """Test 401 for missing sub claim."""
        del valid_layer3_payload["sub"]
        incomplete_token = jose_jwt.encode(
            valid_layer3_payload, TEST_SECRET, algorithm=TEST_ALGORITHM
        )

        response = client.get(
            "/mcp/tools", headers={"Authorization": f"Bearer {incomplete_token}"}
        )

        assert response.status_code == 401
        assert response.json()["error"] == "missing_claims"

    def test_missing_delegation_id(self, client, valid_layer3_payload):
        """Test 401 for missing delegation_id claim."""
        del valid_layer3_payload["delegation_id"]
        incomplete_token = jose_jwt.encode(
            valid_layer3_payload, TEST_SECRET, algorithm=TEST_ALGORITHM
        )

        response = client.get(
            "/mcp/tools", headers={"Authorization": f"Bearer {incomplete_token}"}
        )

        assert response.status_code == 401
        assert response.json()["error"] == "missing_claims"

    def test_invalid_permissions_format(self, client, valid_layer3_payload):
        """Test 401 for invalid permissions format."""
        valid_layer3_payload["delegated_permissions"] = "not-a-list"
        bad_token = jose_jwt.encode(
            valid_layer3_payload, TEST_SECRET, algorithm=TEST_ALGORITHM
        )

        response = client.get(
            "/mcp/tools", headers={"Authorization": f"Bearer {bad_token}"}
        )

        assert response.status_code == 401
        assert response.json()["error"] == "invalid_permissions_format"

    def test_invalid_permission_type(self, client, valid_layer3_payload):
        """Test 401 for invalid permission type in list."""
        valid_layer3_payload["delegated_permissions"] = ["valid:perm", 123, "other:perm"]
        bad_token = jose_jwt.encode(
            valid_layer3_payload, TEST_SECRET, algorithm=TEST_ALGORITHM
        )

        response = client.get(
            "/mcp/tools", headers={"Authorization": f"Bearer {bad_token}"}
        )

        assert response.status_code == 401
        assert response.json()["error"] == "invalid_permission_type"

    def test_future_iat_rejected(self, client, valid_layer3_payload):
        """Test 401 for JWT issued in the future."""
        # More than 60 seconds in the future (beyond clock skew allowance)
        valid_layer3_payload["iat"] = (
            datetime.now(timezone.utc) + timedelta(minutes=5)
        ).timestamp()
        bad_token = jose_jwt.encode(
            valid_layer3_payload, TEST_SECRET, algorithm=TEST_ALGORITHM
        )

        response = client.get(
            "/mcp/tools", headers={"Authorization": f"Bearer {bad_token}"}
        )

        assert response.status_code == 401
        assert response.json()["error"] == "invalid_iat"


# =============================================================================
# JWT Validation Tests - Legacy Format
# =============================================================================


class TestJWTValidationLegacy:
    """Tests for legacy JWT format (backward compatibility)."""

    def test_legacy_token_accepted(self, client, legacy_token):
        """Test that legacy tokens are still accepted."""
        response = client.get(
            "/proxy/test", headers={"Authorization": f"Bearer {legacy_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["agent_id"] == "agent-legacy-001"

    def test_legacy_scope_converted_to_permissions(self, client, legacy_token):
        """Test that legacy 'scope' claim is converted to permissions."""
        response = client.get(
            "/mcp/tools", headers={"Authorization": f"Bearer {legacy_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["agent_id"] == "agent-legacy-001"
        # Legacy scope "read write" should become ["read", "write"]
        assert "read" in data["permissions"]
        assert "write" in data["permissions"]


# =============================================================================
# Authorization Header Tests
# =============================================================================


class TestAuthorizationHeader:
    """Tests for Authorization header parsing."""

    def test_missing_authorization_header(self, client):
        """Test 401 for missing Authorization header."""
        response = client.get("/mcp/tools")

        assert response.status_code == 401
        assert response.json()["error"] == "missing_authorization"
        assert "WWW-Authenticate" in response.headers
        assert response.headers["WWW-Authenticate"] == "Bearer"

    def test_invalid_authorization_format(self, client):
        """Test 401 for invalid Authorization format."""
        response = client.get("/mcp/tools", headers={"Authorization": "InvalidFormat"})

        assert response.status_code == 401
        assert response.json()["error"] == "invalid_header_format"

    def test_basic_auth_rejected(self, client):
        """Test 401 for Basic auth scheme."""
        response = client.get(
            "/mcp/tools", headers={"Authorization": "Basic dXNlcjpwYXNz"}
        )

        assert response.status_code == 401
        assert response.json()["error"] == "invalid_header_format"

    def test_bearer_without_token(self, client):
        """Test 401 for Bearer without token."""
        response = client.get("/mcp/tools", headers={"Authorization": "Bearer"})

        assert response.status_code == 401
        assert response.json()["error"] == "invalid_header_format"

    def test_malformed_jwt(self, client):
        """Test 401 for malformed JWT."""
        response = client.get(
            "/mcp/tools", headers={"Authorization": "Bearer not.a.valid.jwt"}
        )

        assert response.status_code == 401


# =============================================================================
# Path Protection Tests
# =============================================================================


class TestPathProtection:
    """Tests for protected vs bypass paths."""

    def test_health_bypasses_jwt(self, client):
        """Test that /health bypasses JWT validation."""
        response = client.get("/health")

        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_mcp_requires_jwt(self, client):
        """Test that /mcp/* requires JWT."""
        response = client.get("/mcp/tools")

        assert response.status_code == 401

    def test_proxy_requires_jwt(self, client):
        """Test that /proxy/* requires JWT."""
        response = client.get("/proxy/test")

        assert response.status_code == 401

    def test_api_v1_tools_requires_jwt(self, client):
        """Test that /api/v1/tools/* requires JWT."""
        response = client.get("/api/v1/tools/list")

        assert response.status_code == 401

    def test_other_paths_no_jwt(self, client):
        """Test that other paths don't require JWT."""
        response = client.get("/other/endpoint")

        assert response.status_code == 200
        assert response.json()["message"] == "no auth required"

    def test_bypass_paths(self, client):
        """Test configured bypass paths."""
        bypass_paths = ["/", "/health", "/ready", "/metrics", "/docs"]

        for path in bypass_paths:
            response = client.get(path)
            # Should not be 401 (authentication not required)
            # May be 404 if endpoint not defined, but not 401
            assert response.status_code != 401, f"Path {path} should bypass JWT"


# =============================================================================
# Dependency Tests
# =============================================================================


class TestDependencies:
    """Tests for FastAPI dependency functions."""

    def test_get_agent_context_with_valid_context(self, mock_config):
        """Test get_agent_context when context is present."""
        with patch("app.middleware.jwt_validation.config", mock_config):
            app = FastAPI()
            app.add_middleware(JWTValidationMiddleware)

            # Use /mcp/ prefix to ensure JWT validation runs
            @app.get("/mcp/dep-test")
            async def test_endpoint(
                agent: AgentContext = Depends(get_agent_context),
            ):
                return {"agent_id": agent.agent_id}

            client = TestClient(app)

            now = datetime.now(timezone.utc)
            payload = {
                "sub": "agent-test",
                "owner": "test@example.com",
                "delegated_permissions": [],
                "delegation_id": "del-123",
                "session_id": "sess-123",
                "iss": "deeptrail-control",
                "aud": "deeptrail-gateway",
                "iat": int(now.timestamp()),
                "exp": int((now + timedelta(hours=1)).timestamp()),
            }
            token = jose_jwt.encode(payload, TEST_SECRET, algorithm=TEST_ALGORITHM)

            response = client.get(
                "/mcp/dep-test", headers={"Authorization": f"Bearer {token}"}
            )

            assert response.status_code == 200
            assert response.json()["agent_id"] == "agent-test"

    def test_require_permission_granted(self, mock_config):
        """Test require_permission when permission is present."""
        with patch("app.middleware.jwt_validation.config", mock_config):
            app = FastAPI()
            app.add_middleware(JWTValidationMiddleware)

            @app.get("/mcp/perm-test")
            async def test_endpoint(
                agent: AgentContext = Depends(
                    require_permission("notion:pages:read")
                ),
            ):
                return {"agent_id": agent.agent_id}

            client = TestClient(app)

            now = datetime.now(timezone.utc)
            payload = {
                "sub": "agent-test",
                "owner": "test@example.com",
                "delegated_permissions": ["notion:pages:read"],
                "delegation_id": "del-123",
                "session_id": "sess-123",
                "iss": "deeptrail-control",
                "aud": "deeptrail-gateway",
                "iat": int(now.timestamp()),
                "exp": int((now + timedelta(hours=1)).timestamp()),
            }
            token = jose_jwt.encode(payload, TEST_SECRET, algorithm=TEST_ALGORITHM)

            response = client.get(
                "/mcp/perm-test", headers={"Authorization": f"Bearer {token}"}
            )

            assert response.status_code == 200

    def test_require_permission_denied(self, mock_config):
        """Test require_permission when permission is missing."""
        with patch("app.middleware.jwt_validation.config", mock_config):
            app = FastAPI()
            app.add_middleware(JWTValidationMiddleware)

            @app.get("/mcp/perm-denied-test")
            async def test_endpoint(
                agent: AgentContext = Depends(
                    require_permission("notion:pages:delete")
                ),
            ):
                return {"agent_id": agent.agent_id}

            client = TestClient(app)

            now = datetime.now(timezone.utc)
            payload = {
                "sub": "agent-test",
                "owner": "test@example.com",
                "delegated_permissions": ["notion:pages:read"],
                "delegation_id": "del-123",
                "session_id": "sess-123",
                "iss": "deeptrail-control",
                "aud": "deeptrail-gateway",
                "iat": int(now.timestamp()),
                "exp": int((now + timedelta(hours=1)).timestamp()),
            }
            token = jose_jwt.encode(payload, TEST_SECRET, algorithm=TEST_ALGORITHM)

            response = client.get(
                "/mcp/perm-denied-test", headers={"Authorization": f"Bearer {token}"}
            )

            assert response.status_code == 403
            assert "Permission denied" in response.json()["detail"]

    def test_require_any_permission_granted(self, mock_config):
        """Test require_any_permission when one permission is present."""
        with patch("app.middleware.jwt_validation.config", mock_config):
            app = FastAPI()
            app.add_middleware(JWTValidationMiddleware)

            @app.get("/mcp/any-perm-test")
            async def test_endpoint(
                agent: AgentContext = Depends(
                    require_any_permission("notion:pages:read", "notion:pages:search")
                ),
            ):
                return {"agent_id": agent.agent_id}

            client = TestClient(app)

            now = datetime.now(timezone.utc)
            payload = {
                "sub": "agent-test",
                "owner": "test@example.com",
                "delegated_permissions": [
                    "notion:pages:search"
                ],  # Has one of the required
                "delegation_id": "del-123",
                "session_id": "sess-123",
                "iss": "deeptrail-control",
                "aud": "deeptrail-gateway",
                "iat": int(now.timestamp()),
                "exp": int((now + timedelta(hours=1)).timestamp()),
            }
            token = jose_jwt.encode(payload, TEST_SECRET, algorithm=TEST_ALGORITHM)

            response = client.get(
                "/mcp/any-perm-test", headers={"Authorization": f"Bearer {token}"}
            )

            assert response.status_code == 200


# =============================================================================
# Security Tests
# =============================================================================


class TestSecurity:
    """Tests for security properties."""

    def test_fail_closed_on_error(self, client):
        """Test that any validation failure results in denial."""
        # Various ways a token can fail - all should result in 401
        test_cases = [
            ("", "missing header"),
            ("InvalidFormat", "bad format"),
            ("Bearer", "no token"),
            ("Bearer invalid.token.here", "malformed"),
            (f"Basic {jose_jwt.encode({}, TEST_SECRET)}", "wrong scheme"),
        ]

        for auth_value, description in test_cases:
            headers = {"Authorization": auth_value} if auth_value else {}
            response = client.get("/mcp/tools", headers=headers)
            assert response.status_code == 401, f"Failed for: {description}"

    def test_no_token_info_in_error(self, client, valid_layer3_payload):
        """Test that error messages don't leak token information."""
        valid_layer3_payload["exp"] = (
            datetime.now(timezone.utc) - timedelta(hours=1)
        ).timestamp()
        expired_token = jose_jwt.encode(
            valid_layer3_payload, TEST_SECRET, algorithm=TEST_ALGORITHM
        )

        response = client.get(
            "/mcp/tools", headers={"Authorization": f"Bearer {expired_token}"}
        )

        # Error message should not contain the token
        assert expired_token not in response.text
        # Should not contain payload data
        assert "agent-sdr-001" not in response.text
        assert "sarah@acme.com" not in response.text

    def test_www_authenticate_header_on_401(self, client):
        """Test WWW-Authenticate header is present on 401."""
        response = client.get("/mcp/tools")

        assert response.status_code == 401
        assert "WWW-Authenticate" in response.headers
        assert response.headers["WWW-Authenticate"] == "Bearer"
