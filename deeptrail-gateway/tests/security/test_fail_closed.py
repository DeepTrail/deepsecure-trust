"""
Tests for Fail-Closed Security (WS-E4).

Tests the ControlPlaneHealthChecker and fail-closed enforcement
including circuit breaker behavior.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.security.fail_closed import (
    ControlPlaneHealthChecker,
    FailClosedError,
    HealthCheckResult,
    HealthStatus,
    configure_health_checker,
    enforce_fail_closed,
    get_health_checker,
    reset_health_checker,
)


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def health_checker():
    """Create a health checker with test configuration."""
    return ControlPlaneHealthChecker(
        control_plane_url="http://localhost:8000",
        timeout_seconds=1.0,
        circuit_breaker_threshold=3,
        circuit_breaker_reset_seconds=30.0,
    )


@pytest.fixture
def mock_httpx_client():
    """Create a mock httpx AsyncClient."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    
    return mock_client


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset the singleton health checker before each test."""
    reset_health_checker()
    yield
    reset_health_checker()


# =============================================================================
# HealthCheckResult Tests
# =============================================================================


class TestHealthCheckResult:
    """Tests for HealthCheckResult dataclass."""
    
    def test_healthy_result(self):
        """Test creating a healthy result."""
        result = HealthCheckResult(
            is_healthy=True,
            status=HealthStatus.HEALTHY,
            reason="Control plane responding normally",
            latency_ms=50,
        )
        assert result.is_healthy is True
        assert result.status == HealthStatus.HEALTHY
        assert result.latency_ms == 50
    
    def test_unhealthy_result(self):
        """Test creating an unhealthy result."""
        result = HealthCheckResult(
            is_healthy=False,
            status=HealthStatus.TIMEOUT,
            reason="Timed out",
        )
        assert result.is_healthy is False
        assert result.status == HealthStatus.TIMEOUT
        assert result.latency_ms is None


# =============================================================================
# FailClosedError Tests
# =============================================================================


class TestFailClosedError:
    """Tests for FailClosedError exception."""
    
    def test_error_creation(self):
        """Test creating a FailClosedError."""
        error = FailClosedError("Connection failed")
        assert error.reason == "Connection failed"
        assert error.status == HealthStatus.UNHEALTHY
        assert "Security denial" in str(error)
    
    def test_error_with_status(self):
        """Test creating error with specific status."""
        error = FailClosedError("Circuit open", HealthStatus.CIRCUIT_OPEN)
        assert error.reason == "Circuit open"
        assert error.status == HealthStatus.CIRCUIT_OPEN


# =============================================================================
# ControlPlaneHealthChecker Tests
# =============================================================================


class TestControlPlaneHealthChecker:
    """Tests for ControlPlaneHealthChecker."""
    
    @pytest.mark.asyncio
    async def test_healthy_control_plane(self, health_checker):
        """Control plane responding 200 is healthy."""
        with patch("httpx.AsyncClient") as MockClient:
            mock_response = MagicMock()
            mock_response.status_code = 200
            
            mock_instance = AsyncMock()
            mock_instance.get = AsyncMock(return_value=mock_response)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            MockClient.return_value = mock_instance
            
            result = await health_checker.check_health()
            
            assert result.is_healthy is True
            assert result.status == HealthStatus.HEALTHY
            assert result.latency_ms is not None
    
    @pytest.mark.asyncio
    async def test_unhealthy_status_code(self, health_checker):
        """Non-200 status is unhealthy."""
        with patch("httpx.AsyncClient") as MockClient:
            mock_response = MagicMock()
            mock_response.status_code = 503
            
            mock_instance = AsyncMock()
            mock_instance.get = AsyncMock(return_value=mock_response)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            MockClient.return_value = mock_instance
            
            result = await health_checker.check_health()
            
            assert result.is_healthy is False
            assert result.status == HealthStatus.UNHEALTHY
            assert "503" in result.reason
    
    @pytest.mark.asyncio
    async def test_timeout_is_failure(self, health_checker):
        """Control plane timeout is treated as failure."""
        with patch("httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.get = AsyncMock(side_effect=httpx.TimeoutException(""))
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            MockClient.return_value = mock_instance
            
            result = await health_checker.check_health()
            
            assert result.is_healthy is False
            assert result.status == HealthStatus.TIMEOUT
            assert "timed out" in result.reason.lower()
    
    @pytest.mark.asyncio
    async def test_connection_error_is_failure(self, health_checker):
        """Connection errors are treated as failure."""
        with patch("httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.get = AsyncMock(side_effect=httpx.ConnectError(""))
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            MockClient.return_value = mock_instance
            
            result = await health_checker.check_health()
            
            assert result.is_healthy is False
            assert result.status == HealthStatus.CONNECTION_ERROR
            assert "ConnectError" in result.reason
    
    @pytest.mark.asyncio
    async def test_no_url_configured_is_failure(self):
        """Missing control plane URL is treated as failure."""
        checker = ControlPlaneHealthChecker(control_plane_url=None)
        
        result = await checker.check_health()
        
        assert result.is_healthy is False
        assert result.status == HealthStatus.UNHEALTHY
        assert "not configured" in result.reason


# =============================================================================
# Circuit Breaker Tests
# =============================================================================


class TestCircuitBreaker:
    """Tests for circuit breaker behavior."""
    
    @pytest.mark.asyncio
    async def test_circuit_opens_after_threshold(self, health_checker):
        """Circuit breaker opens after N consecutive failures."""
        with patch("httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.get = AsyncMock(side_effect=httpx.ConnectError(""))
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            MockClient.return_value = mock_instance
            
            # First 3 failures should hit the control plane
            for i in range(3):
                result = await health_checker.check_health()
                assert result.is_healthy is False
                # Status should be CONNECTION_ERROR for first 3
                if i < 2:  # First 2 attempts
                    assert result.status == HealthStatus.CONNECTION_ERROR
            
            # 4th call should be circuit-breaker denied (no HTTP call)
            mock_instance.get.reset_mock()
            result = await health_checker.check_health()
            
            assert result.is_healthy is False
            assert result.status == HealthStatus.CIRCUIT_OPEN
            assert "Circuit breaker open" in result.reason
            mock_instance.get.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_circuit_resets_on_success(self, health_checker):
        """Successful health check resets circuit breaker."""
        # Simulate some failures (but below threshold)
        health_checker._failure_count = 2
        
        with patch("httpx.AsyncClient") as MockClient:
            mock_response = MagicMock()
            mock_response.status_code = 200
            
            mock_instance = AsyncMock()
            mock_instance.get = AsyncMock(return_value=mock_response)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            MockClient.return_value = mock_instance
            
            await health_checker.check_health()
            
            assert health_checker._failure_count == 0
            assert health_checker._circuit_open_until is None
    
    @pytest.mark.asyncio
    async def test_circuit_resets_after_timeout(self, health_checker):
        """Circuit breaker resets after reset timeout."""
        # Open the circuit with a past expiry
        health_checker._failure_count = 5
        health_checker._circuit_open_until = datetime.now(timezone.utc) - timedelta(
            seconds=1
        )
        
        with patch("httpx.AsyncClient") as MockClient:
            mock_response = MagicMock()
            mock_response.status_code = 200
            
            mock_instance = AsyncMock()
            mock_instance.get = AsyncMock(return_value=mock_response)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            MockClient.return_value = mock_instance
            
            # Should allow the check (half-open)
            result = await health_checker.check_health()
            
            assert result.is_healthy is True
            mock_instance.get.assert_called_once()
    
    def test_get_circuit_state(self, health_checker):
        """Test getting circuit breaker state."""
        health_checker._failure_count = 2
        
        state = health_checker.get_circuit_state()
        
        assert state["failure_count"] == 2
        assert state["threshold"] == 3
        assert state["is_open"] is False
        assert state["open_until"] is None


# =============================================================================
# Health Check Caching Tests
# =============================================================================


class TestHealthCheckCaching:
    """Tests for health check result caching."""
    
    @pytest.mark.asyncio
    async def test_caches_successful_check(self, health_checker):
        """Successful health checks are cached briefly."""
        with patch("httpx.AsyncClient") as MockClient:
            mock_response = MagicMock()
            mock_response.status_code = 200
            
            mock_instance = AsyncMock()
            mock_instance.get = AsyncMock(return_value=mock_response)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            MockClient.return_value = mock_instance
            
            # First check
            result1 = await health_checker.check_health()
            assert result1.is_healthy is True
            
            # Second check should be cached
            result2 = await health_checker.check_health()
            assert result2.is_healthy is True
            assert "Cached" in result2.reason
            
            # Only one HTTP call made
            assert mock_instance.get.call_count == 1
    
    @pytest.mark.asyncio
    async def test_cache_expires(self, health_checker):
        """Cache expires after timeout."""
        # Set a past cache time
        health_checker._last_healthy_check = datetime.now(timezone.utc) - timedelta(
            seconds=10
        )
        
        with patch("httpx.AsyncClient") as MockClient:
            mock_response = MagicMock()
            mock_response.status_code = 200
            
            mock_instance = AsyncMock()
            mock_instance.get = AsyncMock(return_value=mock_response)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            MockClient.return_value = mock_instance
            
            result = await health_checker.check_health()
            
            # Should make a new check (not use cache)
            assert result.is_healthy is True
            assert "Cached" not in result.reason
            mock_instance.get.assert_called_once()


# =============================================================================
# Module Configuration Tests
# =============================================================================


class TestModuleConfiguration:
    """Tests for module-level configuration functions."""
    
    def test_get_health_checker_returns_singleton(self):
        """get_health_checker returns the same instance."""
        checker1 = get_health_checker()
        checker2 = get_health_checker()
        
        assert checker1 is checker2
    
    def test_configure_health_checker(self):
        """configure_health_checker sets up the singleton."""
        checker = configure_health_checker(
            control_plane_url="http://custom:9000",
            timeout_seconds=10.0,
            circuit_breaker_threshold=10,
        )
        
        assert checker.control_plane_url == "http://custom:9000"
        assert checker.timeout_seconds == 10.0
        assert checker.circuit_breaker_threshold == 10
        
        # Should be the singleton now
        assert get_health_checker() is checker
    
    def test_reset_health_checker(self):
        """reset_health_checker clears the singleton."""
        configure_health_checker(control_plane_url="http://test:8000")
        checker1 = get_health_checker()
        
        reset_health_checker()
        
        checker2 = get_health_checker()
        assert checker1 is not checker2


# =============================================================================
# Fail-Closed Enforcement Tests
# =============================================================================


class TestFailClosedEnforcement:
    """Tests for the enforce_fail_closed function."""
    
    @pytest.mark.asyncio
    async def test_healthy_does_not_raise(self):
        """Healthy control plane does not raise."""
        checker = MagicMock()
        checker.check_health = AsyncMock(
            return_value=HealthCheckResult(
                is_healthy=True,
                status=HealthStatus.HEALTHY,
                reason="OK",
            )
        )
        
        # Should not raise
        result = await enforce_fail_closed(checker)
        assert result.is_healthy is True
    
    @pytest.mark.asyncio
    async def test_unhealthy_raises_fail_closed(self):
        """Unhealthy control plane raises FailClosedError."""
        checker = MagicMock()
        checker.check_health = AsyncMock(
            return_value=HealthCheckResult(
                is_healthy=False,
                status=HealthStatus.CONNECTION_ERROR,
                reason="Cannot connect",
            )
        )
        
        with pytest.raises(FailClosedError) as exc_info:
            await enforce_fail_closed(checker)
        
        assert exc_info.value.reason == "Cannot connect"
        assert exc_info.value.status == HealthStatus.CONNECTION_ERROR
    
    @pytest.mark.asyncio
    async def test_timeout_raises_fail_closed(self):
        """Timeout raises FailClosedError."""
        checker = MagicMock()
        checker.check_health = AsyncMock(
            return_value=HealthCheckResult(
                is_healthy=False,
                status=HealthStatus.TIMEOUT,
                reason="Timed out",
            )
        )
        
        with pytest.raises(FailClosedError) as exc_info:
            await enforce_fail_closed(checker)
        
        assert exc_info.value.status == HealthStatus.TIMEOUT
    
    @pytest.mark.asyncio
    async def test_circuit_open_raises_fail_closed(self):
        """Open circuit breaker raises FailClosedError."""
        checker = MagicMock()
        checker.check_health = AsyncMock(
            return_value=HealthCheckResult(
                is_healthy=False,
                status=HealthStatus.CIRCUIT_OPEN,
                reason="Circuit open",
            )
        )
        
        with pytest.raises(FailClosedError) as exc_info:
            await enforce_fail_closed(checker)
        
        assert exc_info.value.status == HealthStatus.CIRCUIT_OPEN
    
    @pytest.mark.asyncio
    async def test_uses_singleton_if_not_provided(self):
        """Uses the singleton health checker if none provided."""
        configure_health_checker(control_plane_url=None)
        
        with pytest.raises(FailClosedError) as exc_info:
            await enforce_fail_closed()
        
        assert "not configured" in exc_info.value.reason


# =============================================================================
# Integration-Style Tests
# =============================================================================


class TestIntegrationScenarios:
    """Integration-style tests for realistic scenarios."""
    
    @pytest.mark.asyncio
    async def test_control_plane_outage_scenario(self):
        """Simulates a control plane outage scenario."""
        checker = ControlPlaneHealthChecker(
            control_plane_url="http://localhost:8000",
            timeout_seconds=0.5,
            circuit_breaker_threshold=2,
            circuit_breaker_reset_seconds=60.0,
        )
        
        with patch("httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.get = AsyncMock(side_effect=httpx.ConnectError("Refused"))
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            MockClient.return_value = mock_instance
            
            # First request: fails with connection error
            with pytest.raises(FailClosedError) as exc1:
                await enforce_fail_closed(checker)
            assert exc1.value.status == HealthStatus.CONNECTION_ERROR
            
            # Second request: fails again, opens circuit
            with pytest.raises(FailClosedError):
                await enforce_fail_closed(checker)
            # Third request: circuit is open
            with pytest.raises(FailClosedError) as exc3:
                await enforce_fail_closed(checker)
            assert exc3.value.status == HealthStatus.CIRCUIT_OPEN
            
            # No more HTTP calls after circuit opens
            assert mock_instance.get.call_count == 2
    
    @pytest.mark.asyncio
    async def test_control_plane_recovery_scenario(self):
        """Simulates control plane recovering after outage."""
        checker = ControlPlaneHealthChecker(
            control_plane_url="http://localhost:8000",
            timeout_seconds=1.0,
            circuit_breaker_threshold=2,
            circuit_breaker_reset_seconds=0.1,  # Short for testing
        )
        
        with patch("httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            MockClient.return_value = mock_instance
            
            # Two failures open circuit
            mock_instance.get = AsyncMock(side_effect=httpx.ConnectError(""))
            
            for _ in range(2):
                await checker.check_health()
            
            assert checker._failure_count >= 2
            
            # Wait for circuit reset
            import asyncio
            await asyncio.sleep(0.15)
            
            # Recovery: control plane comes back
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_instance.get = AsyncMock(return_value=mock_response)
            
            # Should be healthy again
            result = await checker.check_health()
            assert result.is_healthy is True
            assert checker._failure_count == 0
    
    @pytest.mark.asyncio
    async def test_flapping_control_plane(self):
        """Simulates control plane that flaps between healthy and unhealthy."""
        checker = ControlPlaneHealthChecker(
            control_plane_url="http://localhost:8000",
            timeout_seconds=1.0,
            circuit_breaker_threshold=3,
        )
        checker._health_cache_seconds = 0  # Disable cache for this test
        
        with patch("httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            MockClient.return_value = mock_instance
            
            # Alternating success/failure
            mock_ok = MagicMock(status_code=200)
            mock_fail = MagicMock(status_code=503)
            
            mock_instance.get = AsyncMock(side_effect=[mock_ok, mock_fail, mock_ok])
            
            # Success
            result1 = await checker.check_health()
            assert result1.is_healthy is True
            
            # Failure
            result2 = await checker.check_health()
            assert result2.is_healthy is False
            assert checker._failure_count == 1  # One failure recorded
            
            # Success again - resets failure count
            result3 = await checker.check_health()
            assert result3.is_healthy is True
            assert checker._failure_count == 0
