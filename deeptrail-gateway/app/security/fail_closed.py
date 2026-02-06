"""
Fail-Closed Security for the Gateway.

Ensures that when the Control Plane is unavailable or unreachable,
ALL agent requests are denied rather than allowed.

This implements:
- Demo 6: Fail-Closed Security
- Section 1.1 Design Doc requirement

Security Principle:
- When in doubt, deny. If we can't verify permissions, deny access.
- This prevents unauthorized access when authorization service is down.

Features:
- Control Plane health check with configurable timeout
- Circuit breaker pattern to avoid overwhelming failing services
- Detailed error messages for debugging
- Security denial audit logging

Usage:
    from app.security.fail_closed import (
        get_health_checker,
        enforce_fail_closed,
        FailClosedError,
    )
    
    # In handler:
    try:
        await enforce_fail_closed()
    except FailClosedError as e:
        return MCPError(-32001, f"Security denial: {e.reason}")
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

import httpx

logger = logging.getLogger(__name__)


# =============================================================================
# Enums and Data Classes
# =============================================================================


class HealthStatus(str, Enum):
    """Control Plane health status."""
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    TIMEOUT = "timeout"
    CONNECTION_ERROR = "connection_error"
    CIRCUIT_OPEN = "circuit_breaker_open"


@dataclass
class HealthCheckResult:
    """
    Result of a health check.
    
    Attributes:
        is_healthy: Whether the control plane is healthy
        status: Detailed status code
        reason: Human-readable reason
        latency_ms: Check latency in milliseconds (if completed)
    """
    is_healthy: bool
    status: HealthStatus
    reason: str
    latency_ms: int | None = None


# =============================================================================
# Exceptions
# =============================================================================


class FailClosedError(Exception):
    """
    Raised when fail-closed security denies a request.
    
    This exception indicates that the Control Plane is unavailable
    and requests must be denied for security.
    
    Attributes:
        reason: Why the request was denied
        status: Health status that caused the denial
    """
    
    def __init__(self, reason: str, status: HealthStatus = HealthStatus.UNHEALTHY):
        self.reason = reason
        self.status = status
        super().__init__(f"Security denial: {reason}")


# =============================================================================
# ControlPlaneHealthChecker
# =============================================================================


class ControlPlaneHealthChecker:
    """
    Checks Control Plane health with circuit breaker pattern.
    
    The circuit breaker prevents overwhelming a struggling Control Plane
    by temporarily "opening" the circuit after N consecutive failures.
    
    States:
    - CLOSED: Normal operation, health checks executed
    - OPEN: Failures exceeded threshold, instant denial without check
    - HALF-OPEN: After reset timeout, allow one check to test recovery
    
    Example:
        >>> checker = ControlPlaneHealthChecker(
        ...     control_plane_url="http://localhost:8000",
        ...     timeout_seconds=5.0,
        ... )
        >>> result = await checker.check_health()
        >>> if not result.is_healthy:
        ...     raise FailClosedError(result.reason)
    """
    
    def __init__(
        self,
        control_plane_url: str | None = None,
        timeout_seconds: float = 5.0,
        circuit_breaker_threshold: int = 5,
        circuit_breaker_reset_seconds: float = 30.0,
    ):
        """
        Initialize the health checker.
        
        Args:
            control_plane_url: URL to Control Plane (e.g., http://localhost:8000)
            timeout_seconds: Timeout for health check requests
            circuit_breaker_threshold: Failures before circuit opens
            circuit_breaker_reset_seconds: Seconds before trying again
        """
        self.control_plane_url = control_plane_url
        self.timeout_seconds = timeout_seconds
        self.circuit_breaker_threshold = circuit_breaker_threshold
        self.circuit_breaker_reset_seconds = circuit_breaker_reset_seconds
        
        # Circuit breaker state
        self._failure_count = 0
        self._circuit_open_until: datetime | None = None
        
        # Last successful check (for caching)
        self._last_healthy_check: datetime | None = None
        self._health_cache_seconds: float = 1.0  # Cache success for 1 second
    
    async def check_health(self) -> HealthCheckResult:
        """
        Check if Control Plane is healthy.
        
        Returns:
            HealthCheckResult with status and details
        """
        # If no URL configured, assume unhealthy (fail-closed)
        if not self.control_plane_url:
            return HealthCheckResult(
                is_healthy=False,
                status=HealthStatus.UNHEALTHY,
                reason="Control plane URL not configured",
            )
        
        # Circuit breaker: if open, fail immediately
        if self._is_circuit_open():
            return HealthCheckResult(
                is_healthy=False,
                status=HealthStatus.CIRCUIT_OPEN,
                reason="Circuit breaker open - too many recent failures",
            )
        
        # Check if we have a recent successful check (cache)
        if self._is_cache_valid():
            return HealthCheckResult(
                is_healthy=True,
                status=HealthStatus.HEALTHY,
                reason="Cached health check",
            )
        
        # Perform actual health check
        return await self._perform_health_check()
    
    async def _perform_health_check(self) -> HealthCheckResult:
        """Perform the actual HTTP health check."""
        start_time = datetime.now(timezone.utc)
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.control_plane_url}/health",
                    timeout=self.timeout_seconds,
                )
                
                latency_ms = int(
                    (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
                )
                
                if response.status_code == 200:
                    self._reset_circuit()
                    self._last_healthy_check = datetime.now(timezone.utc)
                    return HealthCheckResult(
                        is_healthy=True,
                        status=HealthStatus.HEALTHY,
                        reason="Control plane responding normally",
                        latency_ms=latency_ms,
                    )
                else:
                    self._record_failure()
                    return HealthCheckResult(
                        is_healthy=False,
                        status=HealthStatus.UNHEALTHY,
                        reason=f"Control plane returned status {response.status_code}",
                        latency_ms=latency_ms,
                    )
                    
        except httpx.TimeoutException:
            self._record_failure()
            return HealthCheckResult(
                is_healthy=False,
                status=HealthStatus.TIMEOUT,
                reason=f"Control plane health check timed out after {self.timeout_seconds}s",
            )
            
        except httpx.ConnectError as e:
            self._record_failure()
            return HealthCheckResult(
                is_healthy=False,
                status=HealthStatus.CONNECTION_ERROR,
                reason=f"Cannot connect to control plane: {type(e).__name__}",
            )
            
        except Exception as e:
            self._record_failure()
            logger.error("Unexpected health check error: %s", e)
            return HealthCheckResult(
                is_healthy=False,
                status=HealthStatus.UNHEALTHY,
                reason=f"Health check failed: {type(e).__name__}",
            )
    
    def _is_circuit_open(self) -> bool:
        """Check if circuit breaker is open."""
        if self._circuit_open_until is None:
            return False
        
        if datetime.now(timezone.utc) >= self._circuit_open_until:
            # Reset to half-open (allow one attempt)
            self._circuit_open_until = None
            return False
        
        return True
    
    def _is_cache_valid(self) -> bool:
        """Check if cached health check is still valid."""
        if self._last_healthy_check is None:
            return False
        
        cache_expiry = self._last_healthy_check + timedelta(
            seconds=self._health_cache_seconds
        )
        return datetime.now(timezone.utc) < cache_expiry
    
    def _record_failure(self) -> None:
        """Record a health check failure."""
        self._failure_count += 1
        logger.warning(
            "Control plane health check failed (%d/%d)",
            self._failure_count,
            self.circuit_breaker_threshold,
        )
        
        if self._failure_count >= self.circuit_breaker_threshold:
            self._circuit_open_until = datetime.now(timezone.utc) + timedelta(
                seconds=self.circuit_breaker_reset_seconds
            )
            logger.warning(
                "Circuit breaker opened - will retry in %.1fs",
                self.circuit_breaker_reset_seconds,
            )
    
    def _reset_circuit(self) -> None:
        """Reset circuit breaker after successful check."""
        if self._failure_count > 0:
            logger.info("Circuit breaker reset - control plane healthy")
        self._failure_count = 0
        self._circuit_open_until = None
    
    def get_circuit_state(self) -> dict[str, Any]:
        """Get current circuit breaker state for debugging."""
        return {
            "failure_count": self._failure_count,
            "threshold": self.circuit_breaker_threshold,
            "is_open": self._is_circuit_open(),
            "open_until": self._circuit_open_until.isoformat() if self._circuit_open_until else None,
        }


# =============================================================================
# Module-Level Configuration
# =============================================================================


# Singleton instance
_health_checker: ControlPlaneHealthChecker | None = None


def get_health_checker() -> ControlPlaneHealthChecker:
    """
    Get the configured health checker instance.
    
    Returns the singleton, creating with defaults if not configured.
    
    Returns:
        ControlPlaneHealthChecker instance
    """
    global _health_checker
    if _health_checker is None:
        _health_checker = ControlPlaneHealthChecker()
    return _health_checker


def configure_health_checker(
    control_plane_url: str | None = None,
    timeout_seconds: float = 5.0,
    circuit_breaker_threshold: int = 5,
    circuit_breaker_reset_seconds: float = 30.0,
) -> ControlPlaneHealthChecker:
    """
    Configure and return the health checker.
    
    Args:
        control_plane_url: URL to Control Plane
        timeout_seconds: Timeout for health checks
        circuit_breaker_threshold: Failures before circuit opens
        circuit_breaker_reset_seconds: Reset timeout
        
    Returns:
        Configured ControlPlaneHealthChecker instance
    """
    global _health_checker
    _health_checker = ControlPlaneHealthChecker(
        control_plane_url=control_plane_url,
        timeout_seconds=timeout_seconds,
        circuit_breaker_threshold=circuit_breaker_threshold,
        circuit_breaker_reset_seconds=circuit_breaker_reset_seconds,
    )
    logger.info(
        "Health checker configured: url=%s, timeout=%.1fs, threshold=%d",
        control_plane_url or "None",
        timeout_seconds,
        circuit_breaker_threshold,
    )
    return _health_checker


def reset_health_checker() -> None:
    """Reset the health checker (for testing)."""
    global _health_checker
    _health_checker = None


# =============================================================================
# Enforcement Function
# =============================================================================


async def enforce_fail_closed(
    health_checker: ControlPlaneHealthChecker | None = None,
) -> HealthCheckResult:
    """
    Enforce fail-closed security.
    
    Checks Control Plane health and raises FailClosedError if unavailable.
    This should be called at the start of any protected handler.
    
    Args:
        health_checker: Optional health checker (uses singleton if not provided)
        
    Returns:
        HealthCheckResult if healthy
        
    Raises:
        FailClosedError: If Control Plane is unavailable
    
    Example:
        >>> try:
        ...     await enforce_fail_closed()
        ... except FailClosedError as e:
        ...     return MCPError(-32001, f"Security denial: {e.reason}")
    """
    checker = health_checker or get_health_checker()
    result = await checker.check_health()
    
    if not result.is_healthy:
        logger.warning(
            "FAIL-CLOSED: Denying request - %s (%s)",
            result.reason,
            result.status.value,
        )
        raise FailClosedError(result.reason, result.status)
    
    return result
