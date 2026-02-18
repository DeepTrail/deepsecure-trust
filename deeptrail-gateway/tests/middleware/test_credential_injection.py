"""
Tests for WS-C7: Credential Injection.

Tests the CredentialInjector class which retrieves OAuth tokens from the vault
and injects them into backend requests, ensuring agents never see credentials.

Key test areas:
- Successful credential injection
- Fail-closed behavior (no credential, token not found)
- Token expiration and refresh
- Security: tokens never exposed or logged
- Caching behavior
- Backend-specific header formatting
"""

import logging
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.middleware.credential_injection import (
    CredentialInjector,
    InjectionError,
    InjectionResult,
    configure_credential_injector,
    get_credential_injector,
    inject_credentials,
    reset_credential_injector,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def injector() -> CredentialInjector:
    """Create a CredentialInjector for testing (MVP mode)."""
    return CredentialInjector()


@pytest.fixture
def injector_with_vault() -> CredentialInjector:
    """Create a CredentialInjector with Control Plane configured."""
    return CredentialInjector(
        control_plane_url="http://localhost:8000",
        cache_ttl_seconds=60,
    )


@pytest.fixture
def mock_token_data() -> dict:
    """Mock token data returned from vault."""
    return {
        "access_token": "test_secret_token_value_12345",
        "token_type": "Bearer",
        "expires_in": 3600,
    }


@pytest.fixture
def expired_token_data() -> dict:
    """Mock expired token data."""
    return {
        "access_token": "expired_token",
        "token_type": "Bearer",
        "expires_at": time.time() - 100,  # Already expired
        "refresh_token": "refresh_token_value",
    }


@pytest.fixture(autouse=True)
def reset_injector():
    """Reset the singleton injector before each test."""
    reset_credential_injector()
    yield
    reset_credential_injector()


# =============================================================================
# Test: InjectionResult
# =============================================================================


class TestInjectionResult:
    """Tests for InjectionResult dataclass."""

    def test_ok_creates_success_result(self):
        """InjectionResult.ok should create successful result."""
        headers = {"Authorization": "Bearer token123"}
        result = InjectionResult.ok(headers)
        
        assert result.success is True
        assert result.headers == headers
        assert result.error is None
        assert result.error_message is None

    def test_fail_creates_failure_result(self):
        """InjectionResult.fail should create failed result."""
        result = InjectionResult.fail(
            InjectionError.TOKEN_NOT_FOUND,
            "Credential not found",
        )
        
        assert result.success is False
        assert result.headers is None
        assert result.error == InjectionError.TOKEN_NOT_FOUND
        assert result.error_message == "Credential not found"


# =============================================================================
# Test: InjectionError Enum
# =============================================================================


class TestInjectionError:
    """Tests for InjectionError enum."""

    def test_injection_errors_have_values(self):
        """All injection errors should have string values."""
        assert InjectionError.NO_CREDENTIAL_REF.value == "no_credential_ref"
        assert InjectionError.TOKEN_NOT_FOUND.value == "token_not_found"
        assert InjectionError.TOKEN_EXPIRED.value == "token_expired"
        assert InjectionError.REFRESH_FAILED.value == "refresh_failed"
        assert InjectionError.VAULT_ERROR.value == "vault_error"
        assert InjectionError.INJECTION_ERROR.value == "injection_error"


# =============================================================================
# Test: Basic Credential Injection
# =============================================================================


class TestBasicInjection:
    """Tests for basic credential injection."""

    @pytest.mark.asyncio
    async def test_inject_returns_headers(self, injector, mock_token_data):
        """C7: Should return authorization headers."""
        injector._fetch_from_vault = AsyncMock(return_value=mock_token_data)
        
        result = await injector.inject_credentials(
            credential_ref="vault://test-notion-abc123",
            backend_id="notion",
        )
        
        assert result.success is True
        assert result.headers is not None
        assert "Authorization" in result.headers

    @pytest.mark.asyncio
    async def test_inject_formats_bearer_token(self, injector, mock_token_data):
        """C7: Should format Bearer token correctly."""
        injector._fetch_from_vault = AsyncMock(return_value=mock_token_data)
        
        result = await injector.inject_credentials(
            credential_ref="vault://test-notion-abc123",
            backend_id="notion",
        )
        
        assert result.headers["Authorization"] == "Bearer test_secret_token_value_12345"

    @pytest.mark.asyncio
    async def test_mvp_mode_returns_mock_token(self, injector):
        """C7 MVP: Should return mock token when no Control Plane."""
        result = await injector.inject_credentials(
            credential_ref="vault://sarah-notion-abc123",
            backend_id="notion",
        )
        
        assert result.success is True
        assert "Authorization" in result.headers
        assert result.headers["Authorization"].startswith("Bearer ")


# =============================================================================
# Test: Fail-Closed Behavior
# =============================================================================


class TestFailClosed:
    """Tests for fail-closed security behavior."""

    @pytest.mark.asyncio
    async def test_fails_without_credential_ref(self, injector):
        """C7 Fail-closed: Should fail if no credential_ref."""
        result = await injector.inject_credentials(
            credential_ref=None,
            backend_id="notion",
        )
        
        assert result.success is False
        assert result.error == InjectionError.NO_CREDENTIAL_REF
        assert "No credential" in result.error_message

    @pytest.mark.asyncio
    async def test_fails_with_empty_credential_ref(self, injector):
        """C7 Fail-closed: Should fail if credential_ref is empty."""
        result = await injector.inject_credentials(
            credential_ref="",
            backend_id="notion",
        )
        
        assert result.success is False
        assert result.error == InjectionError.NO_CREDENTIAL_REF

    @pytest.mark.asyncio
    async def test_fails_if_token_not_found(self, injector):
        """C7 Fail-closed: Should fail if token not in vault."""
        injector._fetch_from_vault = AsyncMock(return_value=None)
        
        result = await injector.inject_credentials(
            credential_ref="vault://nonexistent-ref",
            backend_id="notion",
        )
        
        assert result.success is False
        assert result.error == InjectionError.TOKEN_NOT_FOUND
        assert "re-authorize" in result.error_message

    @pytest.mark.asyncio
    async def test_fails_on_vault_error(self, injector_with_vault):
        """C7 Fail-closed: Should fail on vault error."""
        with patch.object(
            injector_with_vault, "_fetch_from_vault", return_value=None
        ):
            result = await injector_with_vault.inject_credentials(
                credential_ref="vault://error-ref",
                backend_id="notion",
            )
            
            assert result.success is False
            assert result.error == InjectionError.TOKEN_NOT_FOUND


# =============================================================================
# Test: Token Expiration and Refresh
# =============================================================================


class TestTokenExpiration:
    """Tests for token expiration detection and refresh."""

    def test_detects_expired_token(self, injector):
        """C7: Should detect expired tokens."""
        expired_token = {
            "access_token": "old_token",
            "expires_at": time.time() - 100,
        }
        
        assert injector._is_token_expired(expired_token) is True

    def test_detects_valid_token(self, injector):
        """C7: Should recognize valid tokens."""
        valid_token = {
            "access_token": "new_token",
            "expires_at": time.time() + 3600,
        }
        
        assert injector._is_token_expired(valid_token) is False

    def test_considers_buffer_for_expiration(self, injector):
        """C7: Should consider 5-minute buffer for expiration."""
        almost_expired = {
            "access_token": "almost_expired",
            "expires_at": time.time() + 60,  # Only 1 minute left
        }
        
        # Should be considered expired (within 5-minute buffer)
        assert injector._is_token_expired(almost_expired) is True

    def test_token_without_expiry_is_valid(self, injector):
        """C7: Token without expiry info should be considered valid."""
        no_expiry_token = {
            "access_token": "token_no_expiry",
        }
        
        assert injector._is_token_expired(no_expiry_token) is False

    @pytest.mark.asyncio
    async def test_refresh_fails_without_refresh_token(self, injector):
        """C7: Refresh should fail without refresh_token."""
        token_data = {
            "access_token": "expired",
            # No refresh_token
        }
        
        result = await injector._refresh_token("ref", token_data)
        
        assert result is None

    @pytest.mark.asyncio
    async def test_refresh_returns_none_in_mvp(self, injector):
        """C7 MVP: Refresh not implemented in MVP mode."""
        token_data = {
            "access_token": "expired",
            "refresh_token": "refresh_me",
        }
        
        result = await injector._refresh_token("ref", token_data)
        
        assert result is None


# =============================================================================
# Test: Security - Token Not Exposed
# =============================================================================


class TestSecurityNoTokenExposure:
    """Tests to ensure tokens are never exposed."""

    @pytest.mark.asyncio
    async def test_headers_contain_token_but_result_safe(self, injector):
        """C7 Security: Headers contain token but InjectionResult doesn't expose raw token."""
        token_data = {
            "access_token": "SECRET_TOKEN_ABC123",
            "token_type": "Bearer",
        }
        injector._fetch_from_vault = AsyncMock(return_value=token_data)
        
        result = await injector.inject_credentials(
            credential_ref="vault://test-ref",
            backend_id="notion",
        )
        
        # Headers should contain the token (for backend use)
        assert "SECRET_TOKEN_ABC123" in result.headers["Authorization"]
        
        # But InjectionResult itself doesn't have a .token field
        assert not hasattr(result, "token")
        assert not hasattr(result, "access_token")

    @pytest.mark.asyncio
    async def test_error_message_no_token_info(self, injector):
        """C7 Security: Error messages should not contain token details."""
        injector._fetch_from_vault = AsyncMock(return_value=None)
        
        result = await injector.inject_credentials(
            credential_ref="vault://sarah-secret-token-xyz789",
            backend_id="notion",
        )
        
        assert result.success is False
        # Error message should be user-friendly
        error_msg = result.error_message.lower()
        assert "xyz789" not in error_msg
        assert "secret" not in error_msg


# =============================================================================
# Test: Security - No Token in Logs
# =============================================================================


class TestSecurityNoTokenInLogs:
    """Tests to ensure tokens never appear in logs."""

    @pytest.mark.asyncio
    async def test_no_token_in_success_logs(self, injector, mock_token_data, caplog):
        """C7 Security: Token values should not appear in success logs."""
        injector._fetch_from_vault = AsyncMock(return_value=mock_token_data)
        
        with caplog.at_level(logging.DEBUG):
            await injector.inject_credentials(
                credential_ref="vault://test-ref",
                backend_id="notion",
            )
        
        log_text = caplog.text
        # The actual token value should never appear in logs
        assert "test_secret_token_value_12345" not in log_text

    @pytest.mark.asyncio
    async def test_no_token_in_failure_logs(self, injector, caplog):
        """C7 Security: Token values should not appear in failure logs."""
        token_data = {
            "access_token": "SUPER_SECRET_TOKEN_XYZ",
            "token_type": "Bearer",
            "expires_at": time.time() - 100,  # Expired
        }
        injector._fetch_from_vault = AsyncMock(return_value=token_data)
        # Mock refresh to fail
        injector._refresh_token = AsyncMock(return_value=None)
        
        with caplog.at_level(logging.DEBUG):
            await injector.inject_credentials(
                credential_ref="vault://test-ref",
                backend_id="notion",
            )
        
        log_text = caplog.text
        assert "SUPER_SECRET_TOKEN_XYZ" not in log_text

    @pytest.mark.asyncio
    async def test_credential_ref_partially_logged(self, injector, mock_token_data, caplog):
        """C7 Security: Only partial credential_ref should be logged."""
        injector._fetch_from_vault = AsyncMock(return_value=mock_token_data)
        
        with caplog.at_level(logging.DEBUG):
            await injector.inject_credentials(
                credential_ref="vault://sarah-super-secret-long-credential-ref-abc123xyz",
                backend_id="notion",
            )
        
        log_text = caplog.text
        # Full credential ref should not appear
        assert "sarah-super-secret-long-credential-ref-abc123xyz" not in log_text


# =============================================================================
# Test: Caching
# =============================================================================


class TestCaching:
    """Tests for token caching behavior."""

    @pytest.mark.asyncio
    async def test_caches_token(self, injector, mock_token_data):
        """C7: Should cache token after first fetch."""
        injector._fetch_from_vault = AsyncMock(return_value=mock_token_data)
        
        # First call
        await injector.inject_credentials(
            credential_ref="vault://test-ref",
            backend_id="notion",
        )
        
        # Second call should use cache
        await injector.inject_credentials(
            credential_ref="vault://test-ref",
            backend_id="notion",
        )
        
        # Should only fetch once
        assert injector._fetch_from_vault.call_count == 1

    @pytest.mark.asyncio
    async def test_cache_expires(self, mock_token_data):
        """C7: Cache should expire after TTL."""
        injector = CredentialInjector(cache_ttl_seconds=1)
        injector._fetch_from_vault = AsyncMock(return_value=mock_token_data)
        
        # First call
        await injector.inject_credentials(
            credential_ref="vault://test-ref",
            backend_id="notion",
        )
        
        # Wait for cache to expire
        import asyncio
        await asyncio.sleep(1.1)
        
        # Second call should fetch again
        await injector.inject_credentials(
            credential_ref="vault://test-ref",
            backend_id="notion",
        )
        
        assert injector._fetch_from_vault.call_count == 2

    def test_clear_cache(self, injector):
        """C7: Should be able to clear cache."""
        injector._token_cache["vault://test-ref"] = ({"token": "abc"}, time.time())
        
        assert len(injector._token_cache) == 1
        
        injector.clear_cache()
        
        assert len(injector._token_cache) == 0

    def test_invalidate_credential(self, injector):
        """C7: Should be able to invalidate specific credential."""
        injector._token_cache["vault://ref-1"] = ({"token": "a"}, time.time())
        injector._token_cache["vault://ref-2"] = ({"token": "b"}, time.time())
        
        injector.invalidate_credential("vault://ref-1")
        
        assert "vault://ref-1" not in injector._token_cache
        assert "vault://ref-2" in injector._token_cache

    def test_get_cache_stats(self, injector):
        """C7: Should return cache statistics."""
        injector._token_cache["vault://ref-1"] = ({"token": "a"}, time.time())
        injector._token_cache["vault://ref-2"] = ({"token": "b"}, time.time())
        
        stats = injector.get_cache_stats()
        
        assert stats["cached_credentials"] == 2
        assert stats["cache_ttl_seconds"] == 60


# =============================================================================
# Test: Backend-Specific Headers
# =============================================================================


class TestBackendSpecificHeaders:
    """Tests for backend-specific header formatting."""

    def test_notion_uses_bearer(self, injector, mock_token_data):
        """C7: Notion should use Bearer token."""
        headers = injector._format_auth_headers(mock_token_data, "notion")
        
        assert headers["Authorization"].startswith("Bearer ")

    def test_slack_uses_bearer(self, injector, mock_token_data):
        """C7: Slack should use Bearer token."""
        headers = injector._format_auth_headers(mock_token_data, "slack")
        
        assert headers["Authorization"].startswith("Bearer ")

    def test_hubspot_uses_bearer(self, injector, mock_token_data):
        """C7: HubSpot should use Bearer token."""
        headers = injector._format_auth_headers(mock_token_data, "hubspot")
        
        assert headers["Authorization"].startswith("Bearer ")

    def test_api_key_backend_uses_x_api_key(self, injector):
        """C7: API key backends should use X-API-Key header."""
        token_data = {"access_token": "api_key_123"}
        
        headers = injector._format_auth_headers(token_data, "sendgrid")
        
        assert "X-API-Key" in headers
        assert headers["X-API-Key"] == "api_key_123"

    def test_unknown_backend_uses_bearer(self, injector, mock_token_data):
        """C7: Unknown backends should default to Bearer."""
        headers = injector._format_auth_headers(mock_token_data, "unknown_backend")
        
        assert headers["Authorization"].startswith("Bearer ")

    def test_respects_token_type(self, injector):
        """C7: Should respect token_type from token data."""
        token_data = {
            "access_token": "token123",
            "token_type": "Basic",
        }
        
        headers = injector._format_auth_headers(token_data, "notion")
        
        assert headers["Authorization"] == "Basic token123"


# =============================================================================
# Test: Module-Level Configuration
# =============================================================================


class TestModuleConfiguration:
    """Tests for module-level configuration functions."""

    def test_get_credential_injector_creates_default(self):
        """C7: Should create default injector if not configured."""
        injector = get_credential_injector()
        
        assert injector is not None
        assert injector.control_plane_url is None

    def test_configure_credential_injector(self):
        """C7: Should configure injector with custom settings."""
        injector = configure_credential_injector(
            control_plane_url="http://custom:8000",
            cache_ttl_seconds=120,
        )
        
        assert injector.control_plane_url == "http://custom:8000"
        assert injector.cache_ttl_seconds == 120
        
        # Should return same instance on subsequent get
        assert get_credential_injector() is injector

    @pytest.mark.asyncio
    async def test_convenience_inject_credentials(self):
        """C7: Convenience function should work."""
        result = await inject_credentials(
            credential_ref="vault://test-ref",
            backend_id="notion",
        )
        
        # MVP mode returns success with mock token
        assert result.success is True


# =============================================================================
# Test: Edge Cases
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_multiple_backends_sequentially(self, injector, mock_token_data):
        """C7: Should handle multiple backends sequentially."""
        injector._fetch_from_vault = AsyncMock(return_value=mock_token_data)
        
        result1 = await injector.inject_credentials(
            credential_ref="vault://ref-notion",
            backend_id="notion",
        )
        
        result2 = await injector.inject_credentials(
            credential_ref="vault://ref-slack",
            backend_id="slack",
        )
        
        assert result1.success is True
        assert result2.success is True

    @pytest.mark.asyncio
    async def test_empty_access_token_in_token_data(self, injector):
        """C7: Should handle empty access_token gracefully."""
        token_data = {
            "access_token": "",
            "token_type": "Bearer",
        }
        injector._fetch_from_vault = AsyncMock(return_value=token_data)
        
        result = await injector.inject_credentials(
            credential_ref="vault://test-ref",
            backend_id="notion",
        )
        
        # Should still return headers (backend will reject empty token)
        assert result.success is True
        assert result.headers["Authorization"] == "Bearer "

    @pytest.mark.asyncio
    async def test_missing_token_type_defaults_to_bearer(self, injector):
        """C7: Should default to Bearer if token_type missing."""
        token_data = {
            "access_token": "token123",
            # No token_type
        }
        injector._fetch_from_vault = AsyncMock(return_value=token_data)
        
        result = await injector.inject_credentials(
            credential_ref="vault://test-ref",
            backend_id="notion",
        )
        
        assert result.headers["Authorization"] == "Bearer token123"

    @pytest.mark.asyncio
    async def test_very_long_credential_ref(self, injector, mock_token_data):
        """C7: Should handle very long credential refs."""
        injector._fetch_from_vault = AsyncMock(return_value=mock_token_data)
        
        long_ref = "vault://" + "a" * 500
        
        result = await injector.inject_credentials(
            credential_ref=long_ref,
            backend_id="notion",
        )
        
        assert result.success is True

    def test_format_headers_with_special_characters(self, injector):
        """C7: Should handle tokens with special characters."""
        token_data = {
            "access_token": "token+with/special=chars&here",
            "token_type": "Bearer",
        }
        
        headers = injector._format_auth_headers(token_data, "notion")

        assert headers["Authorization"] == "Bearer token+with/special=chars&here"


# =============================================================================
# Test: Real Vault Fetch (WS-H1)
# =============================================================================


class TestRealVaultFetch:
    """Tests for real Control Plane E2 API integration (WS-H1)."""

    @pytest.fixture
    def injector_with_vault(self) -> CredentialInjector:
        """Create a CredentialInjector with Control Plane configured."""
        return CredentialInjector(
            control_plane_url="http://localhost:8000",
            cache_ttl_seconds=60,
            internal_api_token="gateway-internal-secret-token",
        )

    @pytest.mark.asyncio
    async def test_fetch_calls_correct_url(self, injector_with_vault):
        """H1: Should call /api/v1/vault/tokens/{service_id} not {credential_ref}."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "real_token",
            "token_type": "bearer",
            "expires_in": 3600,
        }

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.middleware.credential_injection.httpx.AsyncClient", return_value=mock_client):
            result = await injector_with_vault._fetch_from_vault(
                credential_ref="vault://sarah-notion-abc123",
                backend_id="notion",
                agent_jwt_token="jwt-token-xyz",
            )

        assert result is not None
        assert result["access_token"] == "real_token"
        # Verify URL uses backend_id, not credential_ref
        call_args = mock_client.get.call_args
        url = call_args[0][0] if call_args[0] else call_args[1].get("url", "")
        assert "/api/v1/vault/tokens/notion" in url
        assert "vault://sarah-notion-abc123" not in url

    @pytest.mark.asyncio
    async def test_fetch_sends_agent_jwt(self, injector_with_vault):
        """H1: Should send Authorization: Bearer <agent_jwt> header."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_token": "tok", "token_type": "bearer"}

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.middleware.credential_injection.httpx.AsyncClient", return_value=mock_client):
            await injector_with_vault._fetch_from_vault(
                credential_ref="vault://ref",
                backend_id="notion",
                agent_jwt_token="my-agent-jwt-123",
            )

        call_kwargs = mock_client.get.call_args[1]
        assert call_kwargs["headers"]["Authorization"] == "Bearer my-agent-jwt-123"

    @pytest.mark.asyncio
    async def test_fetch_returns_none_without_jwt(self, injector_with_vault):
        """H1: Should return None if no agent JWT provided."""
        result = await injector_with_vault._fetch_from_vault(
            credential_ref="vault://ref",
            backend_id="notion",
            agent_jwt_token=None,
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_fetch_handles_403_forbidden(self, injector_with_vault):
        """H1: Should return None on 403 (service not delegated)."""
        mock_response = MagicMock()
        mock_response.status_code = 403

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.middleware.credential_injection.httpx.AsyncClient", return_value=mock_client):
            result = await injector_with_vault._fetch_from_vault(
                credential_ref="vault://ref",
                backend_id="notion",
                agent_jwt_token="jwt",
            )

        assert result is None

    @pytest.mark.asyncio
    async def test_fetch_handles_404_not_found(self, injector_with_vault):
        """H1: Should return None on 404 (service not connected)."""
        mock_response = MagicMock()
        mock_response.status_code = 404

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.middleware.credential_injection.httpx.AsyncClient", return_value=mock_client):
            result = await injector_with_vault._fetch_from_vault(
                credential_ref="vault://ref",
                backend_id="notion",
                agent_jwt_token="jwt",
            )

        assert result is None

    @pytest.mark.asyncio
    async def test_fetch_handles_timeout(self, injector_with_vault):
        """H1: Should return None on timeout."""
        import httpx

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.middleware.credential_injection.httpx.AsyncClient", return_value=mock_client):
            result = await injector_with_vault._fetch_from_vault(
                credential_ref="vault://ref",
                backend_id="notion",
                agent_jwt_token="jwt",
            )

        assert result is None

    @pytest.mark.asyncio
    async def test_mvp_mode_still_returns_mock(self):
        """H1: MVP mock path should still work when control_plane_url is None."""
        injector = CredentialInjector()  # No control_plane_url
        result = await injector._fetch_from_vault(
            credential_ref="vault://ref",
            backend_id="notion",
            agent_jwt_token="jwt",
        )
        assert result is not None
        assert result["access_token"] == "mock_access_token_never_exposed_to_agent"

    @pytest.mark.asyncio
    async def test_inject_credentials_threads_jwt_to_fetch(self, injector_with_vault):
        """H1: inject_credentials should thread agent_jwt to _fetch_from_vault."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "real_token",
            "token_type": "Bearer",
            "expires_in": 3600,
        }

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.middleware.credential_injection.httpx.AsyncClient", return_value=mock_client):
            result = await injector_with_vault.inject_credentials(
                credential_ref="vault://sarah-notion-abc123",
                backend_id="notion",
                agent_jwt_token="threaded-jwt",
            )

        assert result.success is True
        assert "Authorization" in result.headers
        # Verify JWT was threaded to the HTTP call
        call_kwargs = mock_client.get.call_args[1]
        assert call_kwargs["headers"]["Authorization"] == "Bearer threaded-jwt"


# =============================================================================
# Test: Real Token Refresh (WS-H2)
# =============================================================================


class TestRealTokenRefresh:
    """Tests for real Control Plane E3 API integration (WS-H2)."""

    @pytest.fixture
    def injector_with_vault_and_token(self) -> CredentialInjector:
        """Create injector with Control Plane and internal token configured."""
        return CredentialInjector(
            control_plane_url="http://localhost:8000",
            cache_ttl_seconds=60,
            internal_api_token="gateway-internal-secret-token",
        )

    @pytest.mark.asyncio
    async def test_refresh_calls_correct_url(self, injector_with_vault_and_token):
        """H2: Should call /api/v1/vault/tokens/{service_id}/refresh."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "new_token",
            "token_type": "bearer",
            "refreshed": True,
            "message": "Token refreshed",
        }

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        token_data = {"access_token": "old", "refresh_token": "refresh_me"}

        with patch("app.middleware.credential_injection.httpx.AsyncClient", return_value=mock_client):
            result = await injector_with_vault_and_token._refresh_token(
                credential_ref="vault://ref",
                token_data=token_data,
                backend_id="notion",
                user_id="sarah@acme.com",
            )

        assert result is not None
        assert result["access_token"] == "new_token"
        call_args = mock_client.post.call_args
        url = call_args[0][0] if call_args[0] else call_args[1].get("url", "")
        assert "/api/v1/vault/tokens/notion/refresh" in url

    @pytest.mark.asyncio
    async def test_refresh_sends_internal_token(self, injector_with_vault_and_token):
        """H2: Should send Authorization: Bearer <internal-token>."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_token": "new", "refreshed": True}

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        token_data = {"access_token": "old", "refresh_token": "refresh_me"}

        with patch("app.middleware.credential_injection.httpx.AsyncClient", return_value=mock_client):
            await injector_with_vault_and_token._refresh_token(
                "ref", token_data, "notion", "sarah@acme.com"
            )

        call_kwargs = mock_client.post.call_args[1]
        assert call_kwargs["headers"]["Authorization"] == "Bearer gateway-internal-secret-token"

    @pytest.mark.asyncio
    async def test_refresh_sends_x_user_id(self, injector_with_vault_and_token):
        """H2: Should send X-User-ID header."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_token": "new", "refreshed": True}

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        token_data = {"access_token": "old", "refresh_token": "refresh_me"}

        with patch("app.middleware.credential_injection.httpx.AsyncClient", return_value=mock_client):
            await injector_with_vault_and_token._refresh_token(
                "ref", token_data, "notion", "sarah@acme.com"
            )

        call_kwargs = mock_client.post.call_args[1]
        assert call_kwargs["headers"]["X-User-ID"] == "sarah@acme.com"

    @pytest.mark.asyncio
    async def test_refresh_sends_force_false_body(self, injector_with_vault_and_token):
        """H2: Should send {"force": false} body."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_token": "new", "refreshed": True}

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        token_data = {"access_token": "old", "refresh_token": "refresh_me"}

        with patch("app.middleware.credential_injection.httpx.AsyncClient", return_value=mock_client):
            await injector_with_vault_and_token._refresh_token(
                "ref", token_data, "notion", "sarah@acme.com"
            )

        call_kwargs = mock_client.post.call_args[1]
        assert call_kwargs["json"] == {"force": False}

    @pytest.mark.asyncio
    async def test_refresh_returns_none_without_internal_token(self):
        """H2: Should return None if no internal_api_token configured."""
        injector = CredentialInjector(
            control_plane_url="http://localhost:8000",
            # No internal_api_token
        )
        token_data = {"access_token": "expired", "refresh_token": "refresh_me"}
        result = await injector._refresh_token("ref", token_data, "notion", "sarah@acme.com")
        assert result is None

    @pytest.mark.asyncio
    async def test_refresh_returns_none_without_user_id(self, injector_with_vault_and_token):
        """H2: Should return None if no user_id provided."""
        token_data = {"access_token": "expired", "refresh_token": "refresh_me"}
        result = await injector_with_vault_and_token._refresh_token(
            "ref", token_data, "notion", None
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_refresh_handles_400(self, injector_with_vault_and_token):
        """H2: Should return None on 400 (no refresh token on server)."""
        mock_response = MagicMock()
        mock_response.status_code = 400

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        token_data = {"access_token": "old", "refresh_token": "refresh_me"}

        with patch("app.middleware.credential_injection.httpx.AsyncClient", return_value=mock_client):
            result = await injector_with_vault_and_token._refresh_token(
                "ref", token_data, "notion", "sarah@acme.com"
            )

        assert result is None

    @pytest.mark.asyncio
    async def test_refresh_handles_502(self, injector_with_vault_and_token):
        """H2: Should return None on 502 (provider error)."""
        mock_response = MagicMock()
        mock_response.status_code = 502

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        token_data = {"access_token": "old", "refresh_token": "refresh_me"}

        with patch("app.middleware.credential_injection.httpx.AsyncClient", return_value=mock_client):
            result = await injector_with_vault_and_token._refresh_token(
                "ref", token_data, "notion", "sarah@acme.com"
            )

        assert result is None

    @pytest.mark.asyncio
    async def test_refresh_invalidates_cache(self, injector_with_vault_and_token):
        """H2: Should invalidate cached credential_ref after successful refresh."""
        # Pre-populate cache
        injector_with_vault_and_token._token_cache["vault://ref"] = (
            {"access_token": "old"}, time.time()
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_token": "new", "refreshed": True}

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        token_data = {"access_token": "old", "refresh_token": "refresh_me"}

        with patch("app.middleware.credential_injection.httpx.AsyncClient", return_value=mock_client):
            await injector_with_vault_and_token._refresh_token(
                "vault://ref", token_data, "notion", "sarah@acme.com"
            )

        assert "vault://ref" not in injector_with_vault_and_token._token_cache

    @pytest.mark.asyncio
    async def test_refresh_mvp_mode_returns_none(self):
        """H2: MVP mode should still return None for refresh."""
        injector = CredentialInjector()  # No control_plane_url
        token_data = {"access_token": "old", "refresh_token": "refresh_me"}
        result = await injector._refresh_token("ref", token_data, "notion", "sarah@acme.com")
        assert result is None
