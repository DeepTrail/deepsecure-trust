"""
Tests for Demo 6: Fail-Closed Security.

Validates that the demo correctly demonstrates:
- Requests succeed when control plane is healthy
- ALL requests are denied when control plane is unavailable
- Fast failure via circuit breaker
- Immediate recovery when control plane is restored
"""

import pytest

from demos.demo_06_fail_closed import (
    CONFIG,
    ControlPlaneStatus,
    DemoConfig,
    DemoResult,
    OutageMetrics,
    RequestResult,
    get_error_code,
    is_request_allowed,
    run_demo,
    simulate_request_healthy,
    simulate_request_unavailable,
)


# =============================================================================
# DemoConfig Tests
# =============================================================================


class TestDemoConfig:
    """Tests for DemoConfig dataclass."""
    
    def test_config_has_gateway_url(self) -> None:
        """Config has a gateway URL."""
        config = DemoConfig()
        assert config.GATEWAY_URL is not None
        assert config.GATEWAY_URL.startswith("http")
    
    def test_config_has_control_plane_url(self) -> None:
        """Config has a control plane URL."""
        config = DemoConfig()
        assert config.CONTROL_PLANE_URL is not None
        assert config.CONTROL_PLANE_URL.startswith("http")
    
    def test_config_has_agent_info(self) -> None:
        """Config has agent information."""
        config = DemoConfig()
        assert config.AGENT_ID is not None
    
    def test_config_has_tool_name(self) -> None:
        """Config has tool name for testing."""
        config = DemoConfig()
        assert config.TOOL_NAME is not None
    
    def test_global_config_exists(self) -> None:
        """Global CONFIG instance exists."""
        assert CONFIG is not None
        assert isinstance(CONFIG, DemoConfig)


# =============================================================================
# ControlPlaneStatus Tests
# =============================================================================


class TestControlPlaneStatus:
    """Tests for ControlPlaneStatus enum."""
    
    def test_healthy_status(self) -> None:
        """HEALTHY status has correct value."""
        assert ControlPlaneStatus.HEALTHY.value == "healthy"
    
    def test_unavailable_status(self) -> None:
        """UNAVAILABLE status has correct value."""
        assert ControlPlaneStatus.UNAVAILABLE.value == "unavailable"
    
    def test_all_statuses_defined(self) -> None:
        """All expected statuses are defined."""
        statuses = [s.value for s in ControlPlaneStatus]
        assert "healthy" in statuses
        assert "unavailable" in statuses


# =============================================================================
# RequestResult Tests
# =============================================================================


class TestRequestResult:
    """Tests for RequestResult dataclass."""
    
    def test_successful_result(self) -> None:
        """RequestResult for successful request."""
        result = RequestResult(
            success=True,
            response='{"data": "test"}',
            error=None,
            latency_ms=100.0,
            control_plane_status=ControlPlaneStatus.HEALTHY,
        )
        assert result.success is True
        assert result.response is not None
        assert result.error is None
        assert result.latency_ms == 100.0
        assert result.control_plane_status == ControlPlaneStatus.HEALTHY
    
    def test_failed_result(self) -> None:
        """RequestResult for failed request."""
        result = RequestResult(
            success=False,
            response=None,
            error="MCPError(-32000): Security denial",
            latency_ms=5.0,
            control_plane_status=ControlPlaneStatus.UNAVAILABLE,
        )
        assert result.success is False
        assert result.response is None
        assert result.error is not None
        assert result.latency_ms == 5.0
        assert result.control_plane_status == ControlPlaneStatus.UNAVAILABLE


# =============================================================================
# DemoResult Tests
# =============================================================================


class TestDemoResult:
    """Tests for DemoResult dataclass."""
    
    def test_successful_demo(self) -> None:
        """DemoResult for successful demo run."""
        result = DemoResult(
            success=True,
            requests_during_healthy=2,
            requests_during_outage=3,
            allowed_during_outage=0,
        )
        assert result.success is True
        assert result.requests_during_healthy == 2
        assert result.requests_during_outage == 3
        assert result.allowed_during_outage == 0
        assert result.error is None
    
    def test_failed_demo(self) -> None:
        """DemoResult for failed demo run."""
        result = DemoResult(
            success=False,
            requests_during_healthy=0,
            requests_during_outage=0,
            allowed_during_outage=0,
            error="Test error",
        )
        assert result.success is False
        assert result.error == "Test error"


# =============================================================================
# OutageMetrics Tests
# =============================================================================


class TestOutageMetrics:
    """Tests for OutageMetrics dataclass."""
    
    def test_security_maintained_when_all_denied(self) -> None:
        """Security maintained when all requests denied."""
        metrics = OutageMetrics(
            total_requests=5,
            denied_requests=5,
            allowed_requests=0,
        )
        assert metrics.security_maintained is True
    
    def test_security_not_maintained_when_allowed(self) -> None:
        """Security NOT maintained when requests allowed."""
        metrics = OutageMetrics(
            total_requests=5,
            denied_requests=4,
            allowed_requests=1,
        )
        assert metrics.security_maintained is False
    
    def test_empty_metrics(self) -> None:
        """Empty metrics shows security maintained."""
        metrics = OutageMetrics(
            total_requests=0,
            denied_requests=0,
            allowed_requests=0,
        )
        assert metrics.security_maintained is True


# =============================================================================
# Request Simulation Tests
# =============================================================================


class TestRequestSimulation:
    """Tests for request simulation functions."""
    
    def test_healthy_request_succeeds(self) -> None:
        """Request succeeds when control plane healthy."""
        result = simulate_request_healthy()
        
        assert result.success is True
        assert result.error is None
        assert result.response is not None
        assert result.control_plane_status == ControlPlaneStatus.HEALTHY
    
    def test_unavailable_request_fails(self) -> None:
        """Request fails when control plane unavailable."""
        result = simulate_request_unavailable()
        
        assert result.success is False
        assert result.error is not None
        assert result.response is None
        assert result.control_plane_status == ControlPlaneStatus.UNAVAILABLE
    
    def test_unavailable_error_contains_security_denial(self) -> None:
        """Error message indicates security denial."""
        result = simulate_request_unavailable()
        
        assert "Security denial" in result.error
        assert "policy service unavailable" in result.error
    
    def test_unavailable_fails_fast(self) -> None:
        """Circuit breaker makes failure fast."""
        result = simulate_request_unavailable()
        
        # Should fail fast due to circuit breaker
        # Much less than typical timeout (30s)
        assert result.latency_ms < 100
    
    def test_healthy_latency_normal(self) -> None:
        """Healthy requests have normal latency."""
        result = simulate_request_healthy()
        
        # Normal latency for backend call
        assert result.latency_ms > 0
        assert result.latency_ms < 1000  # Less than 1 second


# =============================================================================
# Helper Function Tests
# =============================================================================


class TestHelperFunctions:
    """Tests for helper functions."""
    
    def test_is_request_allowed_true(self) -> None:
        """is_request_allowed returns True for successful requests."""
        result = simulate_request_healthy()
        assert is_request_allowed(result) is True
    
    def test_is_request_allowed_false(self) -> None:
        """is_request_allowed returns False for denied requests."""
        result = simulate_request_unavailable()
        assert is_request_allowed(result) is False
    
    def test_get_error_code_extracts_code(self) -> None:
        """get_error_code extracts error code from message."""
        result = simulate_request_unavailable()
        code = get_error_code(result)
        
        assert code == -32000
    
    def test_get_error_code_returns_none_for_success(self) -> None:
        """get_error_code returns None for successful requests."""
        result = simulate_request_healthy()
        code = get_error_code(result)
        
        assert code is None


# =============================================================================
# Demo Execution Tests
# =============================================================================


class TestDemoExecution:
    """Tests for demo execution."""
    
    @pytest.mark.asyncio
    async def test_demo_runs_in_mock_mode(self) -> None:
        """Demo runs successfully in mock mode."""
        result = await run_demo(mock_mode=True)
        assert result.success is True
        assert result.error is None
    
    @pytest.mark.asyncio
    async def test_demo_returns_correct_metrics(self) -> None:
        """Demo returns correct metrics."""
        result = await run_demo(mock_mode=True)
        
        # Should have requests during healthy and outage phases
        assert result.requests_during_healthy >= 1
        assert result.requests_during_outage >= 1
    
    @pytest.mark.asyncio
    async def test_zero_allowed_during_outage(self) -> None:
        """No requests allowed during simulated outage."""
        result = await run_demo(mock_mode=True)
        
        # The key metric: ZERO requests allowed during outage
        assert result.allowed_during_outage == 0


# =============================================================================
# Security Property Tests
# =============================================================================


class TestSecurityProperties:
    """Tests verifying security properties of fail-closed behavior."""
    
    def test_unavailable_never_allows(self) -> None:
        """Unavailable control plane NEVER allows requests."""
        # Run multiple simulations
        for _ in range(10):
            result = simulate_request_unavailable()
            assert result.success is False
    
    def test_error_code_is_security_denial(self) -> None:
        """Error code indicates security denial (-32000)."""
        result = simulate_request_unavailable()
        code = get_error_code(result)
        
        # -32000 is the security denial error code
        assert code == -32000
    
    def test_fast_failure_prevents_timeout_exhaustion(self) -> None:
        """Fast failure prevents timeout exhaustion attacks."""
        result = simulate_request_unavailable()
        
        # Circuit breaker should make failure fast
        # This prevents attackers from exhausting resources via slow timeouts
        assert result.latency_ms < 50  # Much faster than any timeout


# =============================================================================
# Value Proposition Tests
# =============================================================================


class TestValueProposition:
    """Tests verifying the demo's value proposition."""
    
    def test_fail_closed_not_fail_open(self) -> None:
        """System fails closed, not open."""
        # When control plane is unavailable
        result = simulate_request_unavailable()
        
        # Request must be DENIED, not allowed
        assert result.success is False
        assert "Security denial" in result.error
    
    def test_no_backdoor_during_outage(self) -> None:
        """No backdoor allows requests during outage."""
        # Multiple attempts should all fail
        results = [simulate_request_unavailable() for _ in range(5)]
        
        # ALL must be denied
        allowed = sum(1 for r in results if r.success)
        assert allowed == 0
    
    def test_immediate_recovery(self) -> None:
        """Requests succeed immediately after recovery."""
        # During outage - denied
        unavailable_result = simulate_request_unavailable()
        assert unavailable_result.success is False
        
        # After recovery - succeeds immediately
        healthy_result = simulate_request_healthy()
        assert healthy_result.success is True
    
    @pytest.mark.asyncio
    async def test_security_maintained_in_full_demo(self) -> None:
        """Security is maintained throughout full demo."""
        result = await run_demo(mock_mode=True)
        
        # The critical assertion
        assert result.allowed_during_outage == 0
        assert result.success is True
