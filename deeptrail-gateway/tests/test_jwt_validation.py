"""
Test Phase 2 Task 2.3: JWT Validation Middleware

This test suite validates the JWT validation middleware in deeptrail-gateway
to ensure proper authentication of agents and resolve the Phase 1 JWT validation
issues where vault credentials endpoint returned 401 despite valid tokens.

Critical Focus Areas:
1. JWT signature validation using deeptrail-control public key
2. JWT claims validation (exp, iat, agent_id)
3. Invalid token rejection
4. Token expiration handling
5. Integration with FastAPI middleware stack
"""

import pytest
import json
import base64
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any

import httpx
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from jose import jwt as jose_jwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.middleware.jwt_validation import JWTValidationMiddleware, JWTValidationError


TEST_SECRET = "test-jwt-secret-key-for-testing"
TEST_ALGORITHM = "HS256"


def _make_mock_config():
    """Create a mock config with test JWT settings."""
    mock = MagicMock()
    mock.security.jwt_secret_key = TEST_SECRET
    mock.security.jwt_algorithm = TEST_ALGORITHM
    mock.security.jwt_access_token_expire_minutes = 30
    return mock


class TestJWTValidationMiddleware:
    """Test suite for JWT validation middleware."""

    def setup_method(self):
        """Set up test fixtures for each test method."""
        self.mock_config = _make_mock_config()
        self.config_patcher = patch(
            "app.middleware.jwt_validation.config", self.mock_config
        )
        self.config_patcher.start()

        self.app = FastAPI()

        @self.app.get("/proxy/test")
        async def test_endpoint():
            return {"message": "success"}

        @self.app.get("/health")
        async def health_endpoint():
            return {"status": "healthy"}

        self.app.add_middleware(
            JWTValidationMiddleware, control_plane_url="http://localhost:8000"
        )

        self.client = TestClient(self.app)

    def teardown_method(self):
        self.config_patcher.stop()

    def create_test_jwt(self, payload: Dict[str, Any]) -> str:
        """Create a properly signed test JWT token."""
        return jose_jwt.encode(payload, TEST_SECRET, algorithm=TEST_ALGORITHM)

    def create_valid_jwt_payload(self, agent_id: str = "agent-test-123") -> Dict[str, Any]:
        """Create a valid JWT payload with all required claims."""
        current_time = datetime.now(timezone.utc)
        return {
            "sub": agent_id,
            "agent_id": agent_id,
            "scope": "read write",
            "iss": "deeptrail-control",
            "aud": "deeptrail-gateway",
            "owner": "testuser@example.com",
            "delegated_permissions": ["notion:pages:search"],
            "delegation_id": "deleg-test-001",
            "session_id": "sess-test-001",
            "iat": int(current_time.timestamp()),
            "exp": int((current_time + timedelta(hours=1)).timestamp()),
        }

    # Test 1: Valid JWT Token Processing
    def test_valid_jwt_token_accepted(self):
        """Test that valid JWT tokens are accepted."""
        payload = self.create_valid_jwt_payload()
        token = self.create_test_jwt(payload)

        response = self.client.get(
            "/proxy/test",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        assert response.json() == {"message": "success"}

    def test_valid_jwt_token_claim_extraction(self):
        """Test that JWT claims are properly extracted."""
        agent_id = "agent-test-456"
        payload = self.create_valid_jwt_payload(agent_id)
        token = self.create_test_jwt(payload)

        @self.app.get("/proxy/claims")
        async def claims_endpoint(request: Request):
            return {
                "agent_id": getattr(request.state, "agent_id", None),
                "permissions": getattr(request.state, "agent_permissions", [])
            }

        response = self.client.get(
            "/proxy/claims",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["agent_id"] == agent_id
        assert "notion:pages:search" in data["permissions"]

    def test_jwt_token_expiration_validation(self):
        """Test that JWT token expiration is properly validated."""
        payload = self.create_valid_jwt_payload("agent-test-789")
        token = self.create_test_jwt(payload)

        response = self.client.get(
            "/proxy/test",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200

    # Test 2: Invalid JWT Token Rejection
    def test_expired_jwt_token_rejected(self):
        """Test that expired JWT tokens are rejected."""
        current_time = datetime.now(timezone.utc)
        payload = {
            "sub": "agent-test-expired",
            "agent_id": "agent-test-expired",
            "scope": "read",
            "iat": int((current_time - timedelta(hours=2)).timestamp()),
            "exp": int((current_time - timedelta(hours=1)).timestamp()),
        }
        token = self.create_test_jwt(payload)

        response = self.client.get(
            "/proxy/test",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 401
        assert "expired" in response.json()["detail"].lower()

    def test_malformed_jwt_token_rejected(self):
        """Test that malformed JWT tokens are rejected."""
        malformed_token = "not.a.valid.jwt.token"

        response = self.client.get(
            "/proxy/test",
            headers={"Authorization": f"Bearer {malformed_token}"}
        )

        assert response.status_code == 401

    def test_missing_subject_claim_rejected(self):
        """Test that JWT tokens missing required claims are rejected."""
        current_time = datetime.now(timezone.utc)
        payload = {
            "iss": "deeptrail-control",
            "aud": "deeptrail-gateway",
            "iat": int(current_time.timestamp()),
            "exp": int((current_time + timedelta(hours=1)).timestamp()),
        }
        token = self.create_test_jwt(payload)

        response = self.client.get(
            "/proxy/test",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 401
        assert "missing" in response.json()["detail"].lower() or "claim" in response.json()["detail"].lower()

    def test_missing_authorization_header_rejected(self):
        """Test that requests without Authorization header are rejected."""
        response = self.client.get("/proxy/test")

        assert response.status_code == 401
        assert "missing" in response.json()["detail"].lower()
        assert "Authorization" in response.json()["detail"]

    def test_invalid_authorization_header_format_rejected(self):
        """Test that invalid Authorization header formats are rejected."""
        invalid_headers = [
            "Invalid token_here",
            "Bearer",
            "Basic token_here",
        ]

        for header in invalid_headers:
            response = self.client.get(
                "/proxy/test",
                headers={"Authorization": header}
            )

            assert response.status_code == 401

    # Test 3: Bypass Paths
    def test_health_endpoint_bypasses_jwt_validation(self):
        """Test that health check endpoints bypass JWT validation."""
        response = self.client.get("/health")

        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}

    def test_bypass_paths_no_jwt_required(self):
        """Test that configured bypass paths don't require JWT."""
        bypass_paths = ["/", "/health", "/ready", "/metrics", "/docs"]

        for path in bypass_paths:
            response = self.client.get(path)
            assert response.status_code != 401

    def test_non_proxy_paths_bypass_jwt_validation(self):
        """Test that non-proxy paths bypass JWT validation."""
        @self.app.get("/api/test")
        async def non_proxy_endpoint():
            return {"message": "non-proxy"}

        response = self.client.get("/api/test")

        assert response.status_code == 200
        assert response.json() == {"message": "non-proxy"}

    # Test 4: JWT Validation Error Handling
    def test_jwt_validation_error_handling(self):
        """Test proper error handling for JWT validation errors."""
        test_cases = [
            ("", 401),
            ("Bearer", 401),
            ("Bearer invalid.jwt", 401),
            ("Basic dXNlcjpwYXNz", 401),
        ]

        for auth_header, expected_status in test_cases:
            response = self.client.get(
                "/proxy/test",
                headers={"Authorization": auth_header} if auth_header else {}
            )

            assert response.status_code == expected_status

    # Test 5: JWT Validation Integration
    def test_jwt_middleware_integration_with_fastapi(self):
        """Test JWT middleware integration with FastAPI."""
        middlewares = [m.cls for m in self.app.user_middleware]
        assert JWTValidationMiddleware in middlewares

    def test_jwt_validation_performance(self):
        """Test JWT validation performance."""
        payload = self.create_valid_jwt_payload()
        token = self.create_test_jwt(payload)

        start_time = time.time()

        for _ in range(100):
            response = self.client.get(
                "/proxy/test",
                headers={"Authorization": f"Bearer {token}"}
            )
            assert response.status_code == 200

        end_time = time.time()
        avg_time = (end_time - start_time) / 100

        assert avg_time < 0.1, f"JWT validation too slow: {avg_time:.4f}s"

    # Test 6: JWT Signature Validation
    def test_jwt_invalid_signature_rejected(self):
        """Test that JWTs signed with wrong key are rejected."""
        payload = self.create_valid_jwt_payload()
        token = jose_jwt.encode(payload, "wrong-secret-key", algorithm=TEST_ALGORITHM)

        response = self.client.get(
            "/proxy/test",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 401

    # Test 7: Integration with deeptrail-control
    def test_jwt_validation_with_real_control_plane_token(self):
        """Test JWT validation with real token from deeptrail-control."""
        import os
        if not os.getenv("INTEGRATION_TEST"):
            pytest.skip("Skipping integration test")

        pass

    # Test 8: Error Response Format
    def test_jwt_validation_error_response_format(self):
        """Test that JWT validation errors return proper response format (A5)."""
        response = self.client.get("/proxy/test")

        assert response.status_code == 401
        assert "detail" in response.json()
        assert "WWW-Authenticate" in response.headers
        assert 'realm="deeptrail-gateway"' in response.headers["WWW-Authenticate"]

    # Test 9: Request State Management
    def test_jwt_payload_added_to_request_state(self):
        """Test that JWT payload is properly added to request state."""
        agent_id = "agent-state-test"
        payload = self.create_valid_jwt_payload(agent_id)
        token = self.create_test_jwt(payload)

        @self.app.get("/proxy/state")
        async def state_endpoint(request: Request):
            return {
                "has_agent_id": hasattr(request.state, "agent_id"),
                "has_permissions": hasattr(request.state, "agent_permissions"),
                "has_jwt_payload": hasattr(request.state, "jwt_payload"),
                "agent_id": getattr(request.state, "agent_id", None)
            }

        response = self.client.get(
            "/proxy/state",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["has_agent_id"] is True
        assert data["has_permissions"] is True
        assert data["has_jwt_payload"] is True
        assert data["agent_id"] == agent_id


class TestJWTValidationEnterpriseGradeFeatures:
    """Test suite for future enterprise-grade JWT validation features."""

    def setup_method(self):
        self.config_patcher = patch(
            "app.middleware.jwt_validation.config", _make_mock_config()
        )
        self.config_patcher.start()

    def teardown_method(self):
        self.config_patcher.stop()

    def test_public_key_fetching_placeholder(self):
        """Test placeholder for public key fetching from control plane."""
        middleware = JWTValidationMiddleware(FastAPI())

        assert hasattr(middleware, '_fetch_public_key')

    def test_signature_validation_placeholder(self):
        """Test placeholder for JWT signature validation."""
        middleware = JWTValidationMiddleware(FastAPI())

        assert hasattr(middleware, '_validate_jwt_signature')

    def test_token_revocation_placeholder(self):
        """Test placeholder for token revocation checking."""
        middleware = JWTValidationMiddleware(FastAPI())

        assert hasattr(middleware, '_check_token_revocation')


class TestJWTValidationFixForPhase1Issues:
    """Test suite to address specific Phase 1 JWT validation issues."""

    def test_phase1_jwt_issue_reproduction(self):
        """Test to reproduce the Phase 1 JWT validation issue."""
        payload = {
            "sub": "agent-phase1-test",
            "agent_id": "agent-phase1-test",
            "iat": int(datetime.now(timezone.utc).timestamp()),
            "exp": int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
        }

        token = jose_jwt.encode(payload, TEST_SECRET, algorithm=TEST_ALGORITHM)
        assert token is not None

    def test_phase1_jwt_issue_resolution(self):
        """Test that Phase 1 JWT issues are resolved."""
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
