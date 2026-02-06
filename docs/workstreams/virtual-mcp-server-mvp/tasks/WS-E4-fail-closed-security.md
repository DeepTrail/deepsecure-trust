# Task: WS-E4 Implement Fail-Closed Security

---

## Metadata

| Field | Value |
|-------|-------|
| **Status** | `ready` |
| **Design Doc** | [deepsecure-virtual-mcp-server-mvp.md](../../../design/internal/markdowns/deepsecure-virtual-mcp-server-mvp.md) |
| **Workstream** | WS-E: Audit & Security |
| **Code Dependencies** | C3 (JWT validation middleware) ✅ |
| **Runtime Dependencies** | Control Plane (deeptrail-control) |
| **Blocked By** | None |
| **Assigned** | - |
| **Created** | February 6, 2026 |
| **Estimated Complexity** | `S` (< 1hr) |
| **Batch** | 8 |
| **Target Worktree** | `vmcp-gateway` |

---

## Dependencies

### Code Dependencies (must complete before starting)

| Task | What We Need | Status |
|------|--------------|--------|
| C3 | JWT validation middleware patterns, auth error handling | ✅ |

### Runtime Dependencies (must be deployed for integration testing)

| Service | Endpoint | Required For |
|---------|----------|--------------|
| Control Plane | `http://localhost:8000` | Testing fail-closed behavior when unavailable |

### Development Mode

When runtime dependencies are unavailable:

- [x] **Fallback behavior**: Fail-closed is the default - all requests denied when control plane unreachable
- [x] **Local testing**: Unit tests can mock control plane responses (including timeouts)
- [x] **Integration testing**: Container deployment needed to verify actual network failures

---

## Pre-Conditions

Before starting this task, ensure:

- [x] C3 (JWT validation middleware) is complete ✅
- [x] Gateway middleware pattern is established
- [x] Control plane health check endpoint defined

---

## Task Description

Implement **fail-closed security** in the Gateway to ensure that when the Control Plane is unavailable or unreachable, **all agent requests are denied** rather than allowed.

### Context

From the design doc (Section 1.1):
> **Fail-Closed Security**: Agent denied when gateway can't reach control plane

From Demo 6 (Section 5.6):
```python
# Simulate control plane outage
gateway.control_plane.disconnect()

try:
    await client.tools_call("notion.search_pages", {"query": "test"})
except MCPError as e:
    # Error: Gateway cannot verify agent permissions - access denied
```

This is a critical security feature that prevents unauthorized access when the authorization service is unavailable.

### Technical Notes

The fail-closed pattern should:
1. Apply to all authenticated endpoints (`tools/list`, `tools/call`)
2. Check control plane health before processing requests
3. Return specific error codes indicating the security denial
4. Log security events for monitoring
5. Support configurable timeout for control plane checks

---

## Acceptance Criteria

- [ ] All `tools/call` requests fail if control plane is unreachable
- [ ] All `tools/list` requests fail if control plane is unreachable  
- [ ] Specific error response indicates security denial (not generic error)
- [ ] Control plane health check has configurable timeout (default 5s)
- [ ] Security denial events are logged
- [ ] Circuit breaker pattern implemented to avoid hammering failed control plane
- [ ] Unit tests cover all failure scenarios
- [ ] No new linting errors introduced

---

## Files to Modify/Create

### Files to Create

- `deeptrail-gateway/app/security/fail_closed.py` - Fail-closed security handler

### Files to Modify

- `deeptrail-gateway/app/middleware/__init__.py` - Register fail-closed middleware
- `deeptrail-gateway/app/mcp/handlers/tools_list.py` - Add fail-closed check
- `deeptrail-gateway/app/mcp/handlers/tools_call.py` - Add fail-closed check
- `deeptrail-gateway/app/core/config.py` - Add timeout configuration

### Tests to Add

- `deeptrail-gateway/tests/security/test_fail_closed.py` - Fail-closed unit tests

---

## Implementation Details

### FailClosedSecurityHandler Class

```python
# deeptrail-gateway/app/security/fail_closed.py

import asyncio
import httpx
from datetime import datetime, timedelta
from typing import Optional

class ControlPlaneHealthChecker:
    """Checks control plane health with circuit breaker pattern."""
    
    def __init__(
        self,
        control_plane_url: str,
        timeout_seconds: float = 5.0,
        circuit_breaker_threshold: int = 5,
        circuit_breaker_reset_seconds: float = 30.0
    ):
        self.control_plane_url = control_plane_url
        self.timeout = timeout_seconds
        self.failure_count = 0
        self.circuit_breaker_threshold = circuit_breaker_threshold
        self.circuit_breaker_reset_seconds = circuit_breaker_reset_seconds
        self.circuit_open_until: Optional[datetime] = None
    
    async def is_healthy(self) -> tuple[bool, str]:
        """
        Check if control plane is healthy.
        
        Returns:
            tuple[bool, str]: (is_healthy, reason)
        """
        # Circuit breaker: if open, fail immediately
        if self._is_circuit_open():
            return False, "circuit_breaker_open"
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.control_plane_url}/health",
                    timeout=self.timeout
                )
                if response.status_code == 200:
                    self._reset_circuit()
                    return True, "healthy"
                else:
                    self._record_failure()
                    return False, f"unhealthy_status_{response.status_code}"
        except (httpx.TimeoutException, httpx.ConnectError) as e:
            self._record_failure()
            return False, f"connection_failed: {type(e).__name__}"
    
    def _is_circuit_open(self) -> bool:
        if self.circuit_open_until is None:
            return False
        if datetime.utcnow() >= self.circuit_open_until:
            # Reset circuit to half-open (allow one attempt)
            self.circuit_open_until = None
            return False
        return True
    
    def _record_failure(self):
        self.failure_count += 1
        if self.failure_count >= self.circuit_breaker_threshold:
            self.circuit_open_until = datetime.utcnow() + timedelta(
                seconds=self.circuit_breaker_reset_seconds
            )
    
    def _reset_circuit(self):
        self.failure_count = 0
        self.circuit_open_until = None


class FailClosedError(Exception):
    """Raised when fail-closed security denies a request."""
    
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(f"Security denial: {reason}")


async def enforce_fail_closed(
    health_checker: ControlPlaneHealthChecker,
    logger: "AuditLogger"
) -> None:
    """
    Enforce fail-closed security. Raises FailClosedError if control plane unavailable.
    
    Args:
        health_checker: Control plane health checker
        logger: Audit logger for security events
    
    Raises:
        FailClosedError: If control plane is unavailable
    """
    is_healthy, reason = await health_checker.is_healthy()
    
    if not is_healthy:
        # Log security denial event
        await logger.log_security_denial(
            event_type="fail_closed_denial",
            reason=reason
        )
        raise FailClosedError(reason)
```

### Integration with MCP Handlers

```python
# In tools_call.py and tools_list.py handlers:

async def handle_tools_call(request: MCPRequest, ...):
    # First check: fail-closed security
    try:
        await enforce_fail_closed(health_checker, audit_logger)
    except FailClosedError as e:
        return MCPErrorResponse(
            code=-32001,  # Custom error code
            message="Security denial: Cannot verify permissions",
            data={"reason": e.reason}
        )
    
    # Continue with normal request processing...
```

### Configuration

```python
# In app/core/config.py

class GatewaySettings(BaseSettings):
    # ... existing settings ...
    
    # Fail-closed security settings
    control_plane_health_timeout: float = 5.0
    circuit_breaker_threshold: int = 5
    circuit_breaker_reset_seconds: float = 30.0
```

---

## Test Cases

### Unit Tests

```python
# tests/security/test_fail_closed.py

import pytest
from unittest.mock import AsyncMock, patch
from app.security.fail_closed import (
    ControlPlaneHealthChecker,
    FailClosedError,
    enforce_fail_closed
)

class TestControlPlaneHealthChecker:
    
    @pytest.fixture
    def checker(self):
        return ControlPlaneHealthChecker(
            control_plane_url="http://localhost:8000",
            timeout_seconds=1.0,
            circuit_breaker_threshold=3
        )
    
    @pytest.mark.asyncio
    async def test_healthy_control_plane(self, checker):
        """Control plane responding 200 is healthy."""
        with patch("httpx.AsyncClient.get") as mock_get:
            mock_get.return_value.status_code = 200
            is_healthy, reason = await checker.is_healthy()
            assert is_healthy is True
            assert reason == "healthy"
    
    @pytest.mark.asyncio
    async def test_timeout_triggers_failure(self, checker):
        """Control plane timeout is treated as failure."""
        with patch("httpx.AsyncClient.get") as mock_get:
            mock_get.side_effect = httpx.TimeoutException("")
            is_healthy, reason = await checker.is_healthy()
            assert is_healthy is False
            assert "TimeoutException" in reason
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_opens_after_threshold(self, checker):
        """Circuit breaker opens after N consecutive failures."""
        with patch("httpx.AsyncClient.get") as mock_get:
            mock_get.side_effect = httpx.ConnectError("")
            
            # First 3 failures should hit the control plane
            for _ in range(3):
                await checker.is_healthy()
            
            # 4th call should be circuit-breaker denied (no HTTP call)
            mock_get.reset_mock()
            is_healthy, reason = await checker.is_healthy()
            assert is_healthy is False
            assert reason == "circuit_breaker_open"
            mock_get.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_resets_on_success(self, checker):
        """Successful health check resets circuit breaker."""
        # Simulate some failures
        checker.failure_count = 2
        
        with patch("httpx.AsyncClient.get") as mock_get:
            mock_get.return_value.status_code = 200
            await checker.is_healthy()
            
            assert checker.failure_count == 0


class TestFailClosedEnforcement:
    
    @pytest.mark.asyncio
    async def test_healthy_control_plane_allows_request(self):
        """Healthy control plane does not raise."""
        checker = AsyncMock()
        checker.is_healthy.return_value = (True, "healthy")
        logger = AsyncMock()
        
        # Should not raise
        await enforce_fail_closed(checker, logger)
        logger.log_security_denial.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_unhealthy_control_plane_denies_request(self):
        """Unhealthy control plane raises FailClosedError."""
        checker = AsyncMock()
        checker.is_healthy.return_value = (False, "connection_failed")
        logger = AsyncMock()
        
        with pytest.raises(FailClosedError) as exc_info:
            await enforce_fail_closed(checker, logger)
        
        assert exc_info.value.reason == "connection_failed"
        logger.log_security_denial.assert_called_once()
```

---

## Post-Conditions

### Code Complete (enables dependent tasks to start)

- [ ] All acceptance criteria met
- [ ] Unit tests pass locally: `pytest deeptrail-gateway/tests/security/`
- [ ] Linting passes: `ruff check deeptrail-gateway/`
- [ ] Type checking passes: `mypy deeptrail-gateway/`
- [ ] Completion report created

### Integration Complete (validated at merge point)

- [ ] Integration tests pass with control plane container stopped
- [ ] Verify requests denied with proper error when control plane down
- [ ] Verify circuit breaker prevents request storms

### Unblocks

| Task | Type | Notes |
|------|------|-------|
| F7 | Code dependency satisfied | Demo 6: Fail-Closed can proceed |

---

## References

- Design Doc: [Section 1.1 - Fail-Closed Security](../../../design/internal/markdowns/deepsecure-virtual-mcp-server-mvp.md#11-what-were-proving)
- Design Doc: [Section 5.6 - Demo 6: Fail-Closed Security](../../../design/internal/markdowns/deepsecure-virtual-mcp-server-mvp.md#56-demo-6-fail-closed-security)
- Related Code: `deeptrail-gateway/app/middleware/` (middleware patterns)
- Related Code: `deeptrail-gateway/app/mcp/handlers/` (handlers to modify)

---

## Notes

- This is a security-critical feature - fail-closed means DENY by default
- Circuit breaker is important to avoid overwhelming a struggling control plane
- Consider adding metrics/monitoring for security denials in production

---

## Execution Log

### Progress Updates

| Date | Update |
|------|--------|
| - | - |

### Blockers Encountered

| Date | Blocker | Resolution |
|------|---------|------------|
| - | - | - |
