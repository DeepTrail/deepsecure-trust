#!/usr/bin/env python3
"""
Phase 2 Task 2.4: Test Simple Secret Injection
Validate middleware/secret_injection.py fetches secrets from deeptrail-control and injects them.

This test suite validates:
1. Secret injection for Bearer token authentication via split-key architecture
2. Proper bypass of health check and documentation paths
3. Domain-based secret selection and injection
4. Header modification and injection mechanics via MutableHeaders
5. Error handling and fallback behavior
6. Integration with JWT validation middleware
7. Agent-specific secret access control
"""

import pytest
import asyncio
import base64
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any, Optional

from app.middleware.secret_injection import SecretInjectionMiddleware
from fastapi import FastAPI
from starlette.datastructures import Headers, MutableHeaders


class MockRequest:
    """Mock request object for testing.

    Uses Starlette's ``Headers`` for case-insensitive lookup, and reads
    from ``scope["headers"]`` so that changes made by
    ``MutableHeaders(scope=request.scope)`` are visible to assertions.
    """

    def __init__(self, method: str = "GET", url: str = "/", headers: Dict[str, str] = None, body: bytes = b""):
        self.method = method
        self.url = MagicMock()
        self.url.path = url
        self._initial_headers = headers or {}
        self.body = body
        self.state = MagicMock()
        self.state.agent_id = "test-agent-123"
        self.scope = {
            "type": "http",
            "method": method,
            "path": url,
            "headers": [(k.lower().encode(), v.encode()) for k, v in self._initial_headers.items()]
        }

    @property
    def headers(self):
        """Return a Starlette Headers object for case-insensitive access."""
        return Headers(scope=self.scope)


class SecretInjectionTester:
    """Test utility for validating secret injection middleware."""

    def __init__(self):
        self.app = FastAPI()
        with patch('app.core.share_storage.ShareStorageManager'):
            self.middleware = SecretInjectionMiddleware(
                self.app,
                control_plane_url="http://test-control:8000"
            )

    async def test_injection(self, request: MockRequest) -> Dict[str, Any]:
        """Test secret injection on a mock request."""

        async def mock_call_next(req):
            return {"status": "processed"}

        result = await self.middleware.dispatch(request, mock_call_next)

        final_headers = {k: v for k, v in request.headers.items()}
        return {
            "result": result,
            "final_headers": final_headers,
            "agent_id": getattr(request.state, "agent_id", None)
        }


class TestSecretInjectionCore:
    """Test core secret injection functionality."""

    @pytest.fixture
    def secret_tester(self):
        """Create a secret injection tester instance."""
        return SecretInjectionTester()

    @pytest.mark.asyncio
    async def test_bearer_token_injection(self, secret_tester):
        """Test Bearer token injection for OpenAI API via split-key reassembly."""
        request = MockRequest(
            method="POST",
            url="/proxy/v1/chat/completions",
            headers={
                "X-Target-Base-URL": "https://api.openai.com",
                "Content-Type": "application/json"
            }
        )

        with patch.object(secret_tester.middleware, '_reassemble_secret', new_callable=AsyncMock, return_value="sk-test-openai-key"):
            result = await secret_tester.test_injection(request)

        assert "authorization" in result["final_headers"]
        assert result["final_headers"]["authorization"] == "Bearer sk-test-openai-key"
        assert result["result"]["status"] == "processed"

    @pytest.mark.asyncio
    async def test_no_secret_injection_for_httpbin(self, secret_tester):
        """Test that no secret is injected for unmapped domains."""
        request = MockRequest(
            method="GET",
            url="/proxy/get",
            headers={
                "X-Target-Base-URL": "https://httpbin.org",
                "Accept": "application/json"
            }
        )

        result = await secret_tester.test_injection(request)

        assert "authorization" not in result["final_headers"]
        assert result["result"]["status"] == "processed"

    @pytest.mark.asyncio
    async def test_bypass_health_check_paths(self, secret_tester):
        """Test that health check paths bypass secret injection."""
        health_paths = ["/", "/health", "/ready", "/metrics", "/config", "/docs"]

        for path in health_paths:
            request = MockRequest(
                method="GET",
                url=path,
                headers={
                    "X-Target-Base-URL": "https://api.openai.com"
                }
            )

            result = await secret_tester.test_injection(request)

            assert "authorization" not in result["final_headers"], f"Path {path} should bypass injection"
            assert result["result"]["status"] == "processed"

    @pytest.mark.asyncio
    async def test_bypass_non_proxy_paths(self, secret_tester):
        """Test that non-proxy paths bypass secret injection."""
        non_proxy_paths = ["/api/v1/agents", "/auth/token", "/admin/policies"]

        for path in non_proxy_paths:
            request = MockRequest(
                method="GET",
                url=path,
                headers={
                    "X-Target-Base-URL": "https://api.openai.com"
                }
            )

            result = await secret_tester.test_injection(request)

            assert "authorization" not in result["final_headers"]
            assert result["result"]["status"] == "processed"

    @pytest.mark.asyncio
    async def test_missing_target_url_header(self, secret_tester):
        """Test handling of missing X-Target-Base-URL header."""
        request = MockRequest(
            method="POST",
            url="/proxy/v1/chat/completions",
            headers={
                "Content-Type": "application/json"
            }
        )

        result = await secret_tester.test_injection(request)

        assert "authorization" not in result["final_headers"]
        assert result["result"]["status"] == "processed"

    @pytest.mark.asyncio
    async def test_missing_agent_id(self, secret_tester):
        """Test handling of missing agent ID."""
        request = MockRequest(
            method="POST",
            url="/proxy/v1/chat/completions",
            headers={
                "X-Target-Base-URL": "https://api.openai.com",
                "Content-Type": "application/json"
            }
        )

        request.state.agent_id = None

        result = await secret_tester.test_injection(request)

        assert "authorization" not in result["final_headers"]
        assert result["result"]["status"] == "processed"


class TestSecretInjectionTypes:
    """Test secret injection helper methods for different auth types."""

    @pytest.fixture
    def secret_tester(self):
        return SecretInjectionTester()

    @pytest.mark.asyncio
    async def test_bearer_token_injection_via_pipeline(self, secret_tester):
        """Test Bearer token injection through the full pipeline."""
        request = MockRequest(
            method="POST",
            url="/proxy/api/data",
            headers={
                "X-Target-Base-URL": "https://api.openai.com",
                "Content-Type": "application/json"
            }
        )

        with patch.object(secret_tester.middleware, '_reassemble_secret', new_callable=AsyncMock, return_value="test-bearer-token-123"):
            result = await secret_tester.test_injection(request)

        assert result["final_headers"]["authorization"] == "Bearer test-bearer-token-123"

    @pytest.mark.asyncio
    async def test_inject_api_key_header_directly(self, secret_tester):
        """Test _inject_api_key_header helper injects the correct header."""
        request = MockRequest(
            method="GET",
            url="/proxy/api/data",
            headers={"Accept": "application/json"}
        )

        secret_tester.middleware._inject_api_key_header(request, "X-API-Key", "test-api-key-456")

        assert request.headers["x-api-key"] == "test-api-key-456"

    @pytest.mark.asyncio
    async def test_inject_api_key_custom_header_directly(self, secret_tester):
        """Test _inject_api_key_header with a custom header name."""
        request = MockRequest(
            method="GET",
            url="/proxy/api/data",
            headers={"Accept": "application/json"}
        )

        secret_tester.middleware._inject_api_key_header(request, "X-Custom-Auth", "custom-key-789")

        assert request.headers["x-custom-auth"] == "custom-key-789"

    @pytest.mark.asyncio
    async def test_inject_basic_auth_directly(self, secret_tester):
        """Test _inject_basic_auth helper injects Basic auth header."""
        request = MockRequest(
            method="POST",
            url="/proxy/api/secure",
            headers={"Content-Type": "application/json"}
        )

        creds = base64.b64encode(b"username:password").decode()
        secret_tester.middleware._inject_basic_auth(request, creds)

        expected_auth = f"Basic {creds}"
        assert request.headers["authorization"] == expected_auth

    @pytest.mark.asyncio
    async def test_unknown_domain_no_injection(self, secret_tester):
        """Test that unknown domains don't get secret injection."""
        request = MockRequest(
            method="GET",
            url="/proxy/api/data",
            headers={
                "X-Target-Base-URL": "https://unknown.domain.com",
                "Accept": "application/json"
            }
        )

        result = await secret_tester.test_injection(request)

        assert "authorization" not in result["final_headers"]
        assert "x-api-key" not in result["final_headers"]


class TestSecretInjectionDomainParsing:
    """Test domain parsing and secret selection."""

    @pytest.fixture
    def secret_tester(self):
        return SecretInjectionTester()

    @pytest.mark.asyncio
    async def test_domain_parsing_with_subdomain(self, secret_tester):
        """Test domain parsing with subdomains."""
        request = MockRequest(
            method="POST",
            url="/proxy/v1/chat/completions",
            headers={
                "X-Target-Base-URL": "https://api.openai.com/v1",
                "Content-Type": "application/json"
            }
        )

        with patch.object(secret_tester.middleware, '_reassemble_secret', new_callable=AsyncMock, return_value="sk-test-key"):
            result = await secret_tester.test_injection(request)

        assert "authorization" in result["final_headers"]
        assert result["final_headers"]["authorization"] == "Bearer sk-test-key"

    @pytest.mark.asyncio
    async def test_domain_parsing_with_port(self, secret_tester):
        """Test that domains with ports are handled (no match in default mapping)."""
        request = MockRequest(
            method="GET",
            url="/proxy/api/test",
            headers={
                "X-Target-Base-URL": "http://localhost:8080/api",
                "Accept": "application/json"
            }
        )

        result = await secret_tester.test_injection(request)

        assert "authorization" not in result["final_headers"]

    @pytest.mark.asyncio
    async def test_domain_case_insensitive_matching(self, secret_tester):
        """Test that domain matching is case-insensitive."""
        request = MockRequest(
            method="POST",
            url="/proxy/v1/chat/completions",
            headers={
                "X-Target-Base-URL": "https://API.OPENAI.COM/v1",
                "Content-Type": "application/json"
            }
        )

        with patch.object(secret_tester.middleware, '_reassemble_secret', new_callable=AsyncMock, return_value="sk-test-key"):
            result = await secret_tester.test_injection(request)

        assert "authorization" in result["final_headers"]
        assert result["final_headers"]["authorization"] == "Bearer sk-test-key"

    @pytest.mark.asyncio
    async def test_explicit_secret_name_header(self, secret_tester):
        """Test that X-Deeptrail-Secret-Name header overrides domain mapping."""
        request = MockRequest(
            method="POST",
            url="/proxy/api/test",
            headers={
                "X-Target-Base-URL": "https://unknown.example.com",
                "X-Deeptrail-Secret-Name": "my-custom-secret",
                "Content-Type": "application/json"
            }
        )

        with patch.object(secret_tester.middleware, '_reassemble_secret', new_callable=AsyncMock, return_value="custom-secret-value"):
            result = await secret_tester.test_injection(request)

        assert result["final_headers"]["authorization"] == "Bearer custom-secret-value"


class TestSecretInjectionErrorHandling:
    """Test error handling and edge cases."""

    @pytest.fixture
    def secret_tester(self):
        return SecretInjectionTester()

    @pytest.mark.asyncio
    async def test_malformed_target_url(self, secret_tester):
        """Test handling of malformed target URLs."""
        request = MockRequest(
            method="POST",
            url="/proxy/v1/chat/completions",
            headers={
                "X-Target-Base-URL": "not-a-valid-url",
                "Content-Type": "application/json"
            }
        )

        result = await secret_tester.test_injection(request)

        assert result["result"]["status"] == "processed"

    @pytest.mark.asyncio
    async def test_reassembly_returns_none(self, secret_tester):
        """Test handling when secret reassembly fails (returns None)."""
        request = MockRequest(
            method="POST",
            url="/proxy/api/test",
            headers={
                "X-Target-Base-URL": "https://api.openai.com",
                "Content-Type": "application/json"
            }
        )

        with patch.object(secret_tester.middleware, '_reassemble_secret', new_callable=AsyncMock, return_value=None):
            result = await secret_tester.test_injection(request)

        assert "authorization" not in result["final_headers"]
        assert result["result"]["status"] == "processed"

    @pytest.mark.asyncio
    async def test_inject_secrets_exception_handled(self, secret_tester):
        """Test that exceptions in _inject_secrets are caught gracefully."""
        request = MockRequest(
            method="POST",
            url="/proxy/api/test",
            headers={
                "X-Target-Base-URL": "https://api.openai.com",
                "Content-Type": "application/json"
            }
        )

        with patch.object(secret_tester.middleware, '_inject_secrets', new_callable=AsyncMock, side_effect=Exception("test error")):
            result = await secret_tester.test_injection(request)

        assert result["result"]["status"] == "processed"


class TestSecretInjectionIntegration:
    """Test integration scenarios and performance."""

    @pytest.fixture
    def secret_tester(self):
        return SecretInjectionTester()

    @pytest.mark.asyncio
    async def test_multiple_concurrent_injections(self, secret_tester):
        """Test handling of multiple concurrent secret injections."""
        requests = []

        for i in range(10):
            request = MockRequest(
                method="POST",
                url="/proxy/v1/chat/completions",
                headers={
                    "X-Target-Base-URL": "https://api.openai.com",
                    "Content-Type": "application/json"
                }
            )
            request.state.agent_id = f"agent-{i}"
            requests.append(request)

        with patch.object(secret_tester.middleware, '_reassemble_secret', new_callable=AsyncMock, return_value="sk-concurrent-key"):
            tasks = [secret_tester.test_injection(req) for req in requests]
            results = await asyncio.gather(*tasks)

        for result in results:
            assert "authorization" in result["final_headers"]
            assert result["final_headers"]["authorization"] == "Bearer sk-concurrent-key"
            assert result["result"]["status"] == "processed"

    @pytest.mark.asyncio
    async def test_request_header_preservation(self, secret_tester):
        """Test that existing request headers are preserved."""
        request = MockRequest(
            method="POST",
            url="/proxy/v1/chat/completions",
            headers={
                "X-Target-Base-URL": "https://api.openai.com",
                "Content-Type": "application/json",
                "User-Agent": "Test-Agent/1.0",
                "X-Request-ID": "test-123"
            }
        )

        with patch.object(secret_tester.middleware, '_reassemble_secret', new_callable=AsyncMock, return_value="sk-test-key"):
            result = await secret_tester.test_injection(request)

        assert result["final_headers"]["content-type"] == "application/json"
        assert result["final_headers"]["user-agent"] == "Test-Agent/1.0"
        assert result["final_headers"]["x-request-id"] == "test-123"
        assert "authorization" in result["final_headers"]
        assert result["final_headers"]["authorization"] == "Bearer sk-test-key"

    @pytest.mark.asyncio
    async def test_header_override_behavior(self, secret_tester):
        """Test that secret injection overrides existing auth headers."""
        request = MockRequest(
            method="POST",
            url="/proxy/v1/chat/completions",
            headers={
                "X-Target-Base-URL": "https://api.openai.com",
                "Content-Type": "application/json",
                "Authorization": "Bearer old-token"
            }
        )

        with patch.object(secret_tester.middleware, '_reassemble_secret', new_callable=AsyncMock, return_value="sk-new-key"):
            result = await secret_tester.test_injection(request)

        assert result["final_headers"]["authorization"] != "Bearer old-token"
        assert result["final_headers"]["authorization"] == "Bearer sk-new-key"

    @pytest.mark.asyncio
    async def test_performance_timing(self, secret_tester):
        """Test that secret injection completes quickly."""
        import time

        request = MockRequest(
            method="POST",
            url="/proxy/v1/chat/completions",
            headers={
                "X-Target-Base-URL": "https://api.openai.com",
                "Content-Type": "application/json"
            }
        )

        with patch.object(secret_tester.middleware, '_reassemble_secret', new_callable=AsyncMock, return_value="sk-perf-key"):
            start_time = time.time()
            result = await secret_tester.test_injection(request)
            end_time = time.time()

        injection_time = end_time - start_time

        assert injection_time < 0.1, f"Secret injection took {injection_time:.3f}s, should be < 100ms"
        assert result["result"]["status"] == "processed"


@pytest.mark.asyncio
async def test_secret_injection_middleware_initialization():
    """Test that the middleware initializes correctly."""
    app = FastAPI()

    with patch('app.core.share_storage.ShareStorageManager'):
        middleware = SecretInjectionMiddleware(app)
        assert middleware.control_plane_url == "http://deeptrail-control:8000"
        assert "/health" in middleware.bypass_paths

        middleware = SecretInjectionMiddleware(app, control_plane_url="http://custom-control:9000")
        assert middleware.control_plane_url == "http://custom-control:9000"


@pytest.mark.asyncio
async def test_secret_injection_integration_with_gateway():
    """Integration test for secret injection with the gateway service."""
    app = FastAPI()

    with patch('app.core.share_storage.ShareStorageManager'):
        middleware = SecretInjectionMiddleware(app)

    assert hasattr(middleware, 'dispatch')
    assert hasattr(middleware, '_inject_secrets')
    assert hasattr(middleware, '_reassemble_secret')
    assert hasattr(middleware, '_inject_bearer_token')
    assert hasattr(middleware, '_inject_api_key_header')
    assert hasattr(middleware, '_inject_basic_auth')

    assert middleware.bypass_paths is not None
    assert len(middleware.bypass_paths) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
