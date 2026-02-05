"""Tests for agent authentication endpoints.

Tests the POST /api/v1/auth/agent/challenge endpoint which generates
cryptographic challenges for Ed25519-based agent authentication.
"""

import base64
from unittest.mock import MagicMock

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient

from app.api.v1.endpoints.agent_auth import get_agent_session_service
from app.main import app
from app.services.agent_session_service import (
    AgentNotFoundError,
    ChallengeExpiredError,
    InvalidSignatureError,
    NoDelegationError,
)


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def ed25519_keypair():
    """Generate Ed25519 keypair for testing."""
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    public_bytes = public_key.public_bytes_raw()
    public_b64 = base64.urlsafe_b64encode(public_bytes).decode()
    return private_key, public_b64


@pytest.fixture
def mock_agent_session_service():
    """Create a mock AgentSessionService."""
    mock_service = MagicMock()
    mock_service.CHALLENGE_TTL_SECONDS = 300
    mock_service.SESSION_TTL_HOURS = 8
    return mock_service


@pytest.fixture
def mock_auth_result():
    """Create a mock AuthenticationResult."""
    mock_session = MagicMock()
    mock_session.id = "asess-test-abc123"

    mock_result = MagicMock()
    mock_result.session = mock_session
    mock_result.token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test-token"
    mock_result.expires_in = 28800  # 8 hours in seconds
    return mock_result


@pytest.fixture
def client_with_mock_service(db, mock_agent_session_service):
    """Client with mocked AgentSessionService dependency."""
    from app.api.deps import get_db

    def override_get_db():
        try:
            yield db
        finally:
            pass

    def override_agent_session_service():
        return mock_agent_session_service

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_agent_session_service] = override_agent_session_service

    with TestClient(app) as c:
        yield c

    del app.dependency_overrides[get_db]
    del app.dependency_overrides[get_agent_session_service]


# ─────────────────────────────────────────────────────────────────────────────
# Challenge Endpoint Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestAgentChallenge:
    """Tests for POST /api/v1/auth/agent/challenge"""

    def test_create_challenge_success(
        self, client_with_mock_service, mock_agent_session_service, ed25519_keypair
    ):
        """Test successful challenge creation for registered agent."""
        mock_agent_session_service.create_challenge.return_value = (
            "dGVzdC1jaGFsbGVuZ2UtYWJjMTIz"
        )

        response = client_with_mock_service.post(
            "/api/v1/auth/agent/challenge", json={"agent_id": "agent-sdr-001"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "challenge" in data
        assert data["challenge"] == "dGVzdC1jaGFsbGVuZ2UtYWJjMTIz"
        assert data["expires_in"] == 300

    def test_create_challenge_agent_not_found(
        self, client_with_mock_service, mock_agent_session_service
    ):
        """Test 404 error for unknown agent."""
        mock_agent_session_service.create_challenge.side_effect = AgentNotFoundError(
            "Agent 'unknown-agent' not found in registry"
        )

        response = client_with_mock_service.post(
            "/api/v1/auth/agent/challenge", json={"agent_id": "unknown-agent"}
        )

        assert response.status_code == 404
        data = response.json()
        assert data["detail"]["error"] == "agent_not_found"
        assert "unknown-agent" in data["detail"]["message"]

    def test_challenge_format_valid_base64url(
        self, client_with_mock_service, mock_agent_session_service
    ):
        """Test challenge is valid base64url-encoded 256-bit nonce."""
        # Generate a proper 256-bit challenge
        challenge_bytes = b"x" * 32  # 256-bit
        challenge_b64 = base64.urlsafe_b64encode(challenge_bytes).decode()

        mock_agent_session_service.create_challenge.return_value = challenge_b64

        response = client_with_mock_service.post(
            "/api/v1/auth/agent/challenge", json={"agent_id": "agent-sdr-001"}
        )

        assert response.status_code == 200
        challenge = response.json()["challenge"]

        # Verify it's valid base64url that decodes to 32 bytes
        decoded = base64.urlsafe_b64decode(challenge)
        assert len(decoded) == 32  # 256 bits

    def test_challenge_missing_agent_id(self, client):
        """Test validation error for missing agent_id in request."""
        response = client.post("/api/v1/auth/agent/challenge", json={})

        assert response.status_code == 422  # Validation error

    def test_challenge_empty_agent_id(self, client):
        """Test validation error for empty agent_id."""
        response = client.post("/api/v1/auth/agent/challenge", json={"agent_id": ""})

        assert response.status_code == 422  # Validation error

    def test_challenge_agent_id_too_long(self, client):
        """Test validation error for agent_id exceeding max length."""
        long_agent_id = "a" * 129  # Exceeds 128 character limit

        response = client.post(
            "/api/v1/auth/agent/challenge", json={"agent_id": long_agent_id}
        )

        assert response.status_code == 422  # Validation error

    def test_challenge_response_includes_expires_in(
        self, client_with_mock_service, mock_agent_session_service
    ):
        """Test response includes expires_in field with correct TTL."""
        mock_agent_session_service.create_challenge.return_value = "test-challenge"

        response = client_with_mock_service.post(
            "/api/v1/auth/agent/challenge", json={"agent_id": "agent-sdr-001"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "expires_in" in data
        assert data["expires_in"] == 300  # 5 minutes

    def test_challenge_custom_ttl(
        self, client_with_mock_service, mock_agent_session_service
    ):
        """Test response uses service's configured TTL."""
        mock_agent_session_service.create_challenge.return_value = "test-challenge"
        mock_agent_session_service.CHALLENGE_TTL_SECONDS = 600  # Custom 10 minute TTL

        response = client_with_mock_service.post(
            "/api/v1/auth/agent/challenge", json={"agent_id": "agent-sdr-001"}
        )

        assert response.status_code == 200
        assert response.json()["expires_in"] == 600


# ─────────────────────────────────────────────────────────────────────────────
# OpenAPI Documentation Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestOpenAPIDocumentation:
    """Test OpenAPI documentation is generated correctly."""

    def test_openapi_includes_agent_auth_endpoint(self, client):
        """Test OpenAPI schema includes agent auth challenge endpoint."""
        response = client.get("/openapi.json")

        assert response.status_code == 200
        schema = response.json()

        # Check endpoint is documented
        assert "/api/v1/auth/agent/challenge" in schema["paths"]

    def test_openapi_challenge_has_post_method(self, client):
        """Test challenge endpoint has POST method documented."""
        response = client.get("/openapi.json")

        assert response.status_code == 200
        schema = response.json()

        challenge_path = schema["paths"]["/api/v1/auth/agent/challenge"]
        assert "post" in challenge_path

    def test_openapi_challenge_has_request_body(self, client):
        """Test challenge endpoint documents request body."""
        response = client.get("/openapi.json")

        assert response.status_code == 200
        schema = response.json()

        challenge_path = schema["paths"]["/api/v1/auth/agent/challenge"]
        assert "requestBody" in challenge_path["post"]

    def test_openapi_challenge_has_responses(self, client):
        """Test challenge endpoint documents responses."""
        response = client.get("/openapi.json")

        assert response.status_code == 200
        schema = response.json()

        challenge_path = schema["paths"]["/api/v1/auth/agent/challenge"]
        responses = challenge_path["post"]["responses"]

        # Should have 200 and 404 documented
        assert "200" in responses
        assert "404" in responses

    def test_openapi_agent_auth_tag(self, client):
        """Test agent auth endpoint has correct tag."""
        response = client.get("/openapi.json")

        assert response.status_code == 200
        schema = response.json()

        challenge_path = schema["paths"]["/api/v1/auth/agent/challenge"]
        assert "agent-auth" in challenge_path["post"]["tags"]


# ─────────────────────────────────────────────────────────────────────────────
# Integration with AgentSessionService Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestServiceIntegration:
    """Test endpoint integration with AgentSessionService."""

    def test_service_create_challenge_called(
        self, client_with_mock_service, mock_agent_session_service
    ):
        """Test endpoint calls service.create_challenge with agent_id."""
        mock_agent_session_service.create_challenge.return_value = "test-challenge"

        client_with_mock_service.post(
            "/api/v1/auth/agent/challenge", json={"agent_id": "agent-sdr-001"}
        )

        mock_agent_session_service.create_challenge.assert_called_once_with(
            "agent-sdr-001"
        )

    def test_service_exception_handling(
        self, client_with_mock_service, mock_agent_session_service
    ):
        """Test endpoint handles service exceptions gracefully."""
        mock_agent_session_service.create_challenge.side_effect = AgentNotFoundError(
            "Test error message"
        )

        response = client_with_mock_service.post(
            "/api/v1/auth/agent/challenge", json={"agent_id": "test-agent"}
        )

        # Should return 404, not 500
        assert response.status_code == 404
        assert "agent_not_found" in response.json()["detail"]["error"]


# ─────────────────────────────────────────────────────────────────────────────
# Verify Endpoint Tests (C2)
# ─────────────────────────────────────────────────────────────────────────────


class TestAgentVerify:
    """Tests for POST /api/v1/auth/agent/verify"""

    def test_verify_success(
        self,
        client_with_mock_service,
        mock_agent_session_service,
        mock_auth_result,
        ed25519_keypair,
    ):
        """Test successful signature verification and JWT issuance."""
        private_key, _ = ed25519_keypair

        # Create a challenge and sign it
        challenge = base64.urlsafe_b64encode(b"x" * 32).decode()
        signature_bytes = private_key.sign(challenge.encode("utf-8"))
        signature = base64.urlsafe_b64encode(signature_bytes).decode()

        mock_agent_session_service.verify_and_create_session.return_value = (
            mock_auth_result
        )

        response = client_with_mock_service.post(
            "/api/v1/auth/agent/verify",
            json={
                "agent_id": "agent-sdr-001",
                "challenge": challenge,
                "signature": signature,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "Bearer"
        assert data["expires_in"] == 28800  # 8 hours in seconds
        assert data["session_id"] == "asess-test-abc123"

    def test_verify_invalid_signature(
        self, client_with_mock_service, mock_agent_session_service
    ):
        """Test 400 for invalid signature."""
        mock_agent_session_service.verify_and_create_session.side_effect = (
            InvalidSignatureError("Signature verification failed")
        )

        response = client_with_mock_service.post(
            "/api/v1/auth/agent/verify",
            json={
                "agent_id": "agent-sdr-001",
                "challenge": "test-challenge",
                "signature": "invalid-signature",
            },
        )

        assert response.status_code == 400
        data = response.json()
        assert data["detail"]["error"] == "invalid_signature"

    def test_verify_challenge_expired(
        self, client_with_mock_service, mock_agent_session_service
    ):
        """Test 400 for expired challenge."""
        mock_agent_session_service.verify_and_create_session.side_effect = (
            ChallengeExpiredError("Challenge has expired")
        )

        response = client_with_mock_service.post(
            "/api/v1/auth/agent/verify",
            json={
                "agent_id": "agent-sdr-001",
                "challenge": "expired-challenge",
                "signature": "some-signature",
            },
        )

        assert response.status_code == 400
        data = response.json()
        assert data["detail"]["error"] == "challenge_expired"

    def test_verify_no_delegation(
        self, client_with_mock_service, mock_agent_session_service
    ):
        """Test 403 when agent has no valid delegation."""
        mock_agent_session_service.verify_and_create_session.side_effect = (
            NoDelegationError("No valid delegation found for agent")
        )

        response = client_with_mock_service.post(
            "/api/v1/auth/agent/verify",
            json={
                "agent_id": "agent-sdr-001",
                "challenge": "test-challenge",
                "signature": "valid-signature",
            },
        )

        assert response.status_code == 403
        data = response.json()
        assert data["detail"]["error"] == "no_delegation"

    def test_verify_agent_not_found(
        self, client_with_mock_service, mock_agent_session_service
    ):
        """Test 404 for unknown agent."""
        mock_agent_session_service.verify_and_create_session.side_effect = (
            AgentNotFoundError("Agent 'unknown-agent' not found")
        )

        response = client_with_mock_service.post(
            "/api/v1/auth/agent/verify",
            json={
                "agent_id": "unknown-agent",
                "challenge": "test-challenge",
                "signature": "some-signature",
            },
        )

        assert response.status_code == 404
        data = response.json()
        assert data["detail"]["error"] == "agent_not_found"

    def test_verify_with_specific_delegation(
        self,
        client_with_mock_service,
        mock_agent_session_service,
        mock_auth_result,
        ed25519_keypair,
    ):
        """Test verification with specific delegation_id."""
        private_key, _ = ed25519_keypair
        challenge = base64.urlsafe_b64encode(b"y" * 32).decode()
        signature_bytes = private_key.sign(challenge.encode("utf-8"))
        signature = base64.urlsafe_b64encode(signature_bytes).decode()

        mock_agent_session_service.verify_and_create_session.return_value = (
            mock_auth_result
        )

        response = client_with_mock_service.post(
            "/api/v1/auth/agent/verify",
            json={
                "agent_id": "agent-sdr-001",
                "challenge": challenge,
                "signature": signature,
                "delegation_id": "del-sarah-sdr-001",
            },
        )

        assert response.status_code == 200
        # Verify delegation_id was passed to service
        mock_agent_session_service.verify_and_create_session.assert_called_once_with(
            agent_id="agent-sdr-001",
            challenge=challenge,
            signature=signature,
            delegation_id="del-sarah-sdr-001",
        )

    def test_verify_missing_required_fields(self, client):
        """Test validation error for missing fields."""
        response = client.post(
            "/api/v1/auth/agent/verify",
            json={"agent_id": "agent-sdr-001"},  # Missing challenge and signature
        )

        assert response.status_code == 422  # Validation error

    def test_verify_service_called_correctly(
        self,
        client_with_mock_service,
        mock_agent_session_service,
        mock_auth_result,
    ):
        """Test that verify endpoint calls service with correct parameters."""
        mock_agent_session_service.verify_and_create_session.return_value = (
            mock_auth_result
        )

        client_with_mock_service.post(
            "/api/v1/auth/agent/verify",
            json={
                "agent_id": "agent-test-001",
                "challenge": "test-challenge-123",
                "signature": "test-signature-456",
            },
        )

        mock_agent_session_service.verify_and_create_session.assert_called_once_with(
            agent_id="agent-test-001",
            challenge="test-challenge-123",
            signature="test-signature-456",
            delegation_id=None,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Full Auth Flow Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestFullAuthFlow:
    """Integration test for complete auth flow (challenge + verify)."""

    def test_full_auth_flow(
        self,
        client_with_mock_service,
        mock_agent_session_service,
        mock_auth_result,
        ed25519_keypair,
    ):
        """Test complete challenge-response flow."""
        private_key, _ = ed25519_keypair
        agent_id = "agent-sdr-001"

        # Setup mock service to return a challenge
        stored_challenge = base64.urlsafe_b64encode(b"z" * 32).decode()
        mock_agent_session_service.create_challenge.return_value = stored_challenge
        mock_agent_session_service.verify_and_create_session.return_value = (
            mock_auth_result
        )

        # Step 1: Request challenge
        challenge_response = client_with_mock_service.post(
            "/api/v1/auth/agent/challenge", json={"agent_id": agent_id}
        )
        assert challenge_response.status_code == 200
        challenge = challenge_response.json()["challenge"]

        # Step 2: Sign challenge
        signature_bytes = private_key.sign(challenge.encode("utf-8"))
        signature = base64.urlsafe_b64encode(signature_bytes).decode()

        # Step 3: Verify and get JWT
        verify_response = client_with_mock_service.post(
            "/api/v1/auth/agent/verify",
            json={
                "agent_id": agent_id,
                "challenge": challenge,
                "signature": signature,
            },
        )

        assert verify_response.status_code == 200
        data = verify_response.json()
        assert "access_token" in data
        assert data["session_id"] == "asess-test-abc123"


# ─────────────────────────────────────────────────────────────────────────────
# Verify OpenAPI Documentation Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestVerifyOpenAPI:
    """Test OpenAPI documentation for verify endpoint."""

    def test_openapi_includes_verify(self, client):
        """Test OpenAPI schema includes verify endpoint."""
        response = client.get("/openapi.json")

        assert response.status_code == 200
        schema = response.json()

        # Check verify endpoint is documented
        assert "/api/v1/auth/agent/verify" in schema["paths"]

    def test_openapi_verify_has_post_method(self, client):
        """Test verify endpoint has POST method documented."""
        response = client.get("/openapi.json")

        assert response.status_code == 200
        schema = response.json()

        verify_path = schema["paths"]["/api/v1/auth/agent/verify"]
        assert "post" in verify_path

    def test_openapi_verify_has_responses(self, client):
        """Test verify endpoint documents all response codes."""
        response = client.get("/openapi.json")

        assert response.status_code == 200
        schema = response.json()

        verify_path = schema["paths"]["/api/v1/auth/agent/verify"]
        responses = verify_path["post"]["responses"]

        # Should have 200, 400, 403, 404 documented
        assert "200" in responses
        assert "400" in responses
        assert "403" in responses
        assert "404" in responses

    def test_openapi_verify_has_agent_auth_tag(self, client):
        """Test verify endpoint has correct tag."""
        response = client.get("/openapi.json")

        assert response.status_code == 200
        schema = response.json()

        verify_path = schema["paths"]["/api/v1/auth/agent/verify"]
        assert "agent-auth" in verify_path["post"]["tags"]
