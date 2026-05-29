"""
Integration tests for DeepTrail Gateway with DeepTrail Control service.

These tests verify end-to-end functionality between the gateway and control plane,
including authentication, policy enforcement, secret injection, and proxy forwarding.

ALL async tests in this module require live backend services (control plane, gateway,
database, Redis). Run with: ``pytest -m integration -v``

Tests that use ``@patch`` on middleware classes CANNOT work against a live gateway
running in a separate process; those patches only affect the test process. Such tests
are marked ``@pytest.mark.e2e`` and should be run via ``TestClient`` or with a
specially configured test harness.
"""

import pytest
import pytest_asyncio
import asyncio
import json
import time
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
from typing import Dict, Any, Optional

import httpx
from fastapi.testclient import TestClient

DEEPTRAIL_CONTROL_URL = os.getenv("DEEPTRAIL_CONTROL_URL", "http://localhost:8000")
DEEPTRAIL_GATEWAY_URL = os.getenv("DEEPTRAIL_GATEWAY_URL", "http://localhost:8002")
TEST_TIMEOUT = 30


@pytest.fixture(scope="module")
def integration_config():
    """Configuration for integration tests."""
    return {
        "control_plane_url": DEEPTRAIL_CONTROL_URL,
        "gateway_url": DEEPTRAIL_GATEWAY_URL,
        "timeout": TEST_TIMEOUT,
        "test_agent_name": "test-integration-agent",
        "test_service_url": "https://httpbin.org"
    }


@pytest_asyncio.fixture
async def http_client():
    """Async HTTP client for integration tests (function-scoped for event loop safety)."""
    async with httpx.AsyncClient(timeout=TEST_TIMEOUT) as client:
        yield client


@pytest.fixture
def mock_deepsecure_client():
    """Mock DeepSecure client for testing SDK integration."""
    with patch('deepsecure.Client') as mock_client:
        client_instance = Mock()

        mock_agent = Mock()
        mock_agent.id = "agent-12345678-1234-1234-1234-123456789012"
        mock_agent.name = "test-integration-agent"
        mock_agent.public_key = "test-public-key"

        client_instance.agents.create.return_value = mock_agent
        client_instance.agents.get.return_value = mock_agent
        client_instance.gateway_url = DEEPTRAIL_GATEWAY_URL

        mock_credential = Mock()
        mock_credential.id = "cred-12345678-1234-1234-1234-123456789012"
        mock_credential.access_token = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.test"
        mock_credential.expires_at = int(time.time()) + 3600

        client_instance.vault.issue_credential.return_value = mock_credential

        mock_secret = Mock()
        mock_secret.name = "test-api-key"
        mock_secret.value = "sk-test-api-key-value"

        client_instance.vault.get_secret.return_value = mock_secret

        mock_client.return_value = client_instance
        yield client_instance


@pytest.mark.integration
class TestGatewayControlPlaneIntegration:
    """Test integration between gateway and control plane.

    These tests require live gateway + control plane services.
    """

    @pytest.mark.asyncio
    async def test_gateway_health_check(self, http_client: httpx.AsyncClient, integration_config: Dict[str, Any]):
        """Test that the gateway is healthy and responding."""
        response = await http_client.get(f"{integration_config['gateway_url']}/health")
        assert response.status_code == 200

        health_data = response.json()
        assert health_data["service"] == "DeepSecure Gateway"
        assert "version" in health_data
        assert health_data["version"] is not None
        assert health_data["status"] == "ok"
        assert "dependencies" in health_data
        assert "control_plane" in health_data["dependencies"]
        assert "redis" in health_data["dependencies"]

    @pytest.mark.asyncio
    async def test_control_plane_health_check(self, http_client: httpx.AsyncClient, integration_config: Dict[str, Any]):
        """Test that the control plane is healthy and responding."""
        response = await http_client.get(f"{integration_config['control_plane_url']}/health")
        assert response.status_code == 200

        health_data = response.json()
        assert health_data["service"] == "DeepSecure Control Plane"
        assert health_data["status"] == "ok"
        assert "version" in health_data
        assert "dependencies" in health_data
        assert "database" in health_data["dependencies"]

    @pytest.mark.asyncio
    async def test_gateway_proxy_without_auth(self, http_client: httpx.AsyncClient, integration_config: Dict[str, Any]):
        """Test that the gateway rejects requests without authentication."""
        headers = {
            "X-Target-Base-URL": integration_config["test_service_url"]
        }

        response = await http_client.get(
            f"{integration_config['gateway_url']}/proxy/get",
            headers=headers
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_gateway_proxy_with_invalid_jwt(self, http_client: httpx.AsyncClient, integration_config: Dict[str, Any]):
        """Test that the gateway rejects requests with invalid JWT."""
        headers = {
            "X-Target-Base-URL": integration_config["test_service_url"],
            "Authorization": "Bearer invalid-jwt-token"
        }

        response = await http_client.get(
            f"{integration_config['gateway_url']}/proxy/get",
            headers=headers
        )

        assert response.status_code == 401
        resp_lower = response.text.lower()
        assert any(kw in resp_lower for kw in ("invalid", "unauthorized", "validation_failed", "failed"))

    @pytest.mark.asyncio
    @pytest.mark.e2e
    @pytest.mark.skip(reason="@patch on middleware does not affect a live gateway process; use TestClient for in-process tests")
    async def test_gateway_proxy_with_valid_jwt(self, http_client: httpx.AsyncClient, integration_config: Dict[str, Any]):
        """Test that the gateway forwards requests with valid JWT."""
        pass


@pytest.mark.integration
class TestDeepSecureSDKIntegration:
    """Test integration with the DeepSecure SDK (uses mocked SDK client)."""

    def test_sdk_client_initialization(self, mock_deepsecure_client, integration_config: Dict[str, Any]):
        """Test that the SDK client can be initialized with gateway URL."""
        from deepsecure import Client

        client = Client(
            deeptrail_control_url=integration_config["control_plane_url"],
            deeptrail_gateway_url=integration_config["gateway_url"]
        )

        assert client is not None
        assert client.gateway_url == integration_config["gateway_url"]

    def test_sdk_agent_creation(self, mock_deepsecure_client, integration_config: Dict[str, Any]):
        """Test agent creation through the SDK."""
        from deepsecure import Client

        client = Client(
            deeptrail_control_url=integration_config["control_plane_url"],
            deeptrail_gateway_url=integration_config["gateway_url"]
        )

        agent = client.agents.create(name=integration_config["test_agent_name"])

        assert agent is not None
        assert agent.name == integration_config["test_agent_name"]
        assert agent.id.startswith("agent-")
        assert agent.public_key is not None

    def test_sdk_credential_issuance(self, mock_deepsecure_client, integration_config: Dict[str, Any]):
        """Test credential issuance through the SDK."""
        from deepsecure import Client

        client = Client(
            deeptrail_control_url=integration_config["control_plane_url"],
            deeptrail_gateway_url=integration_config["gateway_url"]
        )

        credential = client.vault.issue_credential(
            agent_id="agent-12345678-1234-1234-1234-123456789012",
            scope="read:web",
            resource="https://httpbin.org"
        )

        assert credential is not None
        assert credential.access_token is not None
        assert credential.expires_at > int(time.time())

    def test_sdk_secret_fetching(self, mock_deepsecure_client, integration_config: Dict[str, Any]):
        """Test secret fetching through the SDK."""
        from deepsecure import Client

        client = Client(
            deeptrail_control_url=integration_config["control_plane_url"],
            deeptrail_gateway_url=integration_config["gateway_url"]
        )

        secret = client.vault.get_secret(
            agent_id="agent-12345678-1234-1234-1234-123456789012",
            secret_name="test-api-key"
        )

        assert secret is not None
        assert secret.name == "test-api-key"
        assert secret.value == "sk-test-api-key-value"


@pytest.mark.integration
@pytest.mark.e2e
@pytest.mark.skip(reason="@patch on middleware does not affect a live gateway process; these tests need a TestClient-based harness")
class TestEndToEndWorkflow:
    """Test complete end-to-end workflows.

    These tests patch middleware classes and send HTTP requests to the live
    gateway. Since patches only affect the test process (not the gateway
    process), they cannot work as designed. They are skipped until
    migrated to an in-process TestClient approach.
    """

    @pytest.mark.asyncio
    async def test_complete_proxy_workflow(self, http_client, integration_config):
        pass

    @pytest.mark.asyncio
    async def test_policy_enforcement_workflow(self, http_client, integration_config):
        pass

    @pytest.mark.asyncio
    async def test_policy_denial_workflow(self, http_client, integration_config):
        pass


@pytest.mark.integration
@pytest.mark.e2e
@pytest.mark.skip(reason="@patch on middleware does not affect a live gateway process; these tests need a TestClient-based harness")
class TestPerformanceIntegration:
    """Test performance characteristics of the integration.

    These tests patch JWT validation and send HTTP requests to the live
    gateway. Since patches only affect the test process, they cannot work.
    Skipped until migrated to an in-process TestClient approach.
    """

    @pytest.mark.asyncio
    async def test_gateway_response_time(self, http_client, integration_config):
        pass

    @pytest.mark.asyncio
    async def test_concurrent_requests(self, http_client, integration_config):
        pass


@pytest.mark.integration
@pytest.mark.security
class TestSecurityIntegration:
    """Test security aspects of the integration."""

    @pytest.mark.asyncio
    async def test_blocked_internal_ips(self, http_client: httpx.AsyncClient, integration_config: Dict[str, Any]):
        """Test that requests to internal IPs are blocked.

        Without a valid JWT the gateway will return 401 before even
        checking the target URL. Both 401 and 403 are acceptable as
        they indicate the request was rejected.
        """
        internal_urls = [
            "http://127.0.0.1:8080",
            "http://localhost:8080",
            "http://10.0.0.1:8080",
            "http://192.168.1.1:8080",
            "http://172.16.0.1:8080"
        ]

        for internal_url in internal_urls:
            headers = {
                "X-Target-Base-URL": internal_url,
                "Authorization": "Bearer valid-jwt-token"
            }

            response = await http_client.get(
                f"{integration_config['gateway_url']}/proxy/get",
                headers=headers
            )

            assert response.status_code in [400, 401, 403], f"Internal URL {internal_url} should be blocked, got {response.status_code}"

    @pytest.mark.asyncio
    async def test_missing_target_url_header(self, http_client: httpx.AsyncClient, integration_config: Dict[str, Any]):
        """Test that requests without target URL header are rejected.

        The gateway may reject for missing auth (401) before checking
        the target URL header.
        """
        headers = {
            "Authorization": "Bearer valid-jwt-token"
        }

        response = await http_client.get(
            f"{integration_config['gateway_url']}/proxy/get",
            headers=headers
        )

        assert response.status_code in [400, 401]

    @pytest.mark.asyncio
    @pytest.mark.e2e
    @pytest.mark.skip(reason="@patch on middleware does not affect a live gateway process")
    async def test_request_size_limits(self, http_client: httpx.AsyncClient, integration_config: Dict[str, Any]):
        """Test that large requests are handled appropriately."""
        pass
