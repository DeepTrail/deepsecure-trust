# Task: WS-F7 Create Demo 6: Fail-Closed Security

---

## Metadata

| Field | Value |
|-------|-------|
| **Status** | `ready` |
| **Design Doc** | [deepsecure-virtual-mcp-server-mvp.md](../../../design/internal/markdowns/deepsecure-virtual-mcp-server-mvp.md) |
| **Workstream** | WS-F: Integration & Demos |
| **Code Dependencies** | E4 (Fail-closed security) ✅ |
| **Runtime Dependencies** | Gateway, Control Plane (to simulate outage) |
| **Blocked By** | None |
| **Assigned** | - |
| **Created** | February 6, 2026 |
| **Estimated Complexity** | `M` (2-4 hours) |
| **Batch** | 9 |
| **Target Worktree** | `vmcp-gateway` |

---

## Dependencies

### Code Dependencies (must complete before starting)

| Task | What We Need | Status |
|------|--------------|--------|
| E4 | Fail-closed security implementation | ✅ |

### Runtime Dependencies (must be deployed for integration testing)

| Service | Endpoint | Required For |
|---------|----------|--------------|
| Gateway | `http://localhost:8002` | Demo entry point |
| Control Plane | `http://localhost:8000` | To simulate outage |

### Development Mode

When runtime dependencies are unavailable:

- [x] **Fallback behavior**: Demo uses mocked responses
- [x] **Local testing**: Unit tests verify demo script structure
- [x] **Integration testing**: Full demo requires services to stop/start

---

## Pre-Conditions

Before starting this task, ensure:

- [x] E4 (Fail-closed security) is complete ✅
- [x] Gateway denies requests when control plane unavailable

---

## Task Description

Create **Demo 6: Fail-Closed Security** - a demonstration script that shows when the Control Plane is unavailable, ALL agent requests are denied.

### Context

From the design doc (Section 5.6):
```python
# Simulate control plane outage
gateway.control_plane.disconnect()

try:
    await client.tools_call("notion.search_pages", {"query": "test"})
except MCPError as e:
    print(e)
# Output: MCPError(-32000): Policy service unavailable - request denied

# When restored:
gateway.control_plane.reconnect()
result = await client.tools_call("notion.search_pages", {"query": "test"})
# Output: Success
```

**Success Criteria**: ZERO requests allowed during control plane outage.

### Technical Notes

The demo should:
1. Show a request succeeding when control plane is healthy
2. Simulate control plane outage (or actually stop it)
3. Show requests being denied during outage
4. Show recovery when control plane is restored

---

## Acceptance Criteria

- [ ] Demo shows request succeeding with healthy control plane
- [ ] Demo simulates/performs control plane outage
- [ ] Demo shows requests denied during outage
- [ ] Demo shows recovery after control plane restored
- [ ] Error message clearly indicates security denial
- [ ] Includes both real and mock modes
- [ ] No new linting errors introduced

---

## Files to Modify/Create

### Files to Create

- `deeptrail-gateway/demos/demo_06_fail_closed.py` - Main demo script

### Files to Modify

- `deeptrail-gateway/demos/README.md` - Add Demo 6 instructions

### Tests to Add

- `deeptrail-gateway/tests/demos/test_demo_06.py` - Demo script validation

---

## Implementation Details

### Demo Script

```python
#!/usr/bin/env python3
"""
Demo 6: Fail-Closed Security

Demonstrates that when the Control Plane is unavailable,
ALL agent requests are DENIED. No fail-open behavior.

Value Proposition:
- Security failure mode: DENY, not ALLOW
- No backdoor when policy service is down
- Immediate recovery when service restored

Usage:
    python demo_06_fail_closed.py --mock
"""

import asyncio
import argparse
import time
from enum import Enum
from typing import Optional
from dataclasses import dataclass


class ControlPlaneStatus(Enum):
    HEALTHY = "healthy"
    UNAVAILABLE = "unavailable"


@dataclass
class RequestResult:
    success: bool
    response: Optional[str]
    error: Optional[str]
    latency_ms: float


# Demo configuration
GATEWAY_URL = "http://localhost:8002/mcp"
CONTROL_PLANE_URL = "http://localhost:8000"


def print_banner():
    """Print demo banner."""
    print("\n" + "=" * 70)
    print(" DEMO 6: FAIL-CLOSED SECURITY")
    print("=" * 70)
    print()
    print(" Value Proposition:")
    print(" • When policy service is down → ALL requests DENIED")
    print(" • No 'fail-open' backdoor for attackers")
    print(" • Security failure mode prioritizes safety")
    print(" • Immediate recovery when service restored")
    print()
    print("-" * 70)


def print_section(title: str, icon: str = "📋"):
    """Print section header."""
    print(f"\n{icon} {title}")
    print("-" * 50)


def print_control_plane_status(status: ControlPlaneStatus):
    """Print control plane status."""
    if status == ControlPlaneStatus.HEALTHY:
        print("   Control Plane Status: 🟢 HEALTHY")
        print(f"   URL: {CONTROL_PLANE_URL}")
        print("   Health Check: ✓ 200 OK")
    else:
        print("   Control Plane Status: 🔴 UNAVAILABLE")
        print(f"   URL: {CONTROL_PLANE_URL}")
        print("   Health Check: ✗ Connection refused")


def simulate_request_healthy() -> RequestResult:
    """Simulate request when control plane is healthy."""
    return RequestResult(
        success=True,
        response='{"pages": [{"id": "page-123", "title": "Sales Playbook"}]}',
        error=None,
        latency_ms=145.3
    )


def simulate_request_unavailable() -> RequestResult:
    """Simulate request when control plane is unavailable."""
    return RequestResult(
        success=False,
        response=None,
        error="MCPError(-32000): Security denial - policy service unavailable",
        latency_ms=5.2  # Fast failure due to circuit breaker
    )


def print_request_result(result: RequestResult, phase: str):
    """Print request result."""
    print(f"\n   {phase}")
    print("   " + "-" * 40)
    print(f"   Tool: notion.search_pages")
    print(f"   Args: {{'query': 'sales playbook'}}")
    print(f"   Latency: {result.latency_ms:.1f}ms")
    print()
    
    if result.success:
        print(f"   Result: ✅ SUCCESS")
        print(f"   Response: {result.response}")
    else:
        print(f"   Result: 🚫 DENIED")
        print(f"   Error: {result.error}")


def demo_phase_1_healthy():
    """Phase 1: Control plane healthy."""
    print_section("PHASE 1: CONTROL PLANE HEALTHY", "🟢")
    
    print_control_plane_status(ControlPlaneStatus.HEALTHY)
    
    result = simulate_request_healthy()
    print_request_result(result, "Agent makes request:")
    
    print("\n   → Request succeeds because gateway can verify permissions")


def demo_phase_2_outage():
    """Phase 2: Control plane outage."""
    print_section("PHASE 2: CONTROL PLANE OUTAGE", "🔴")
    
    print("\n   ⚡ SIMULATING CONTROL PLANE OUTAGE...")
    print("   (In reality: docker stop deeptrail-control)")
    print()
    
    print_control_plane_status(ControlPlaneStatus.UNAVAILABLE)
    
    print("\n   Agent tries to make requests during outage:")
    
    for i in range(3):
        result = simulate_request_unavailable()
        print(f"\n   Attempt {i+1}:")
        print(f"   Tool: notion.search_pages")
        print(f"   Result: 🚫 DENIED")
        print(f"   Error: {result.error}")
    
    print("\n   " + "=" * 50)
    print("   SECURITY BEHAVIOR: FAIL-CLOSED")
    print("   " + "=" * 50)
    print("   • 0 requests allowed during outage")
    print("   • Agent cannot bypass security checks")
    print("   • Circuit breaker prevents request storms")
    print("   " + "=" * 50)


def demo_phase_3_recovery():
    """Phase 3: Control plane restored."""
    print_section("PHASE 3: CONTROL PLANE RESTORED", "🟢")
    
    print("\n   🔄 CONTROL PLANE COMING BACK ONLINE...")
    print("   (In reality: docker start deeptrail-control)")
    print()
    
    print_control_plane_status(ControlPlaneStatus.HEALTHY)
    
    result = simulate_request_healthy()
    print_request_result(result, "Agent makes request after recovery:")
    
    print("\n   → Requests succeed again immediately")


def compare_security_models():
    """Compare fail-open vs fail-closed."""
    print_section("COMPARISON: Security Failure Modes", "⚖️")
    
    print("""
   ┌─────────────────────────────────────────────────────────────────┐
   │                     FAIL-OPEN (DANGEROUS)                       │
   ├─────────────────────────────────────────────────────────────────┤
   │                                                                  │
   │  When policy service is unavailable:                            │
   │  → "Just let the request through, we'll log it later"          │
   │                                                                  │
   │  RISK: Attacker can intentionally cause policy service outage  │
   │        and then execute any action without permission checks.   │
   │                                                                  │
   │  This is a CRITICAL VULNERABILITY.                              │
   │                                                                  │
   └─────────────────────────────────────────────────────────────────┘
   
   ┌─────────────────────────────────────────────────────────────────┐
   │                     FAIL-CLOSED (DEEPSECURE)                    │
   ├─────────────────────────────────────────────────────────────────┤
   │                                                                  │
   │  When policy service is unavailable:                            │
   │  → DENY ALL REQUESTS                                            │
   │                                                                  │
   │  WHY: We cannot verify permissions, so we cannot allow action.  │
   │                                                                  │
   │  TRADEOFF: Availability suffers, but security is maintained.    │
   │                                                                  │
   │  This is the CORRECT security posture.                          │
   │                                                                  │
   └─────────────────────────────────────────────────────────────────┘
""")


def print_summary():
    """Print demo summary."""
    print("\n" + "=" * 70)
    print(" ✅ KEY INSIGHTS")
    print("=" * 70)
    print()
    print("   1. FAIL-CLOSED BY DESIGN")
    print("      Gateway denies ALL requests when control plane unavailable")
    print()
    print("   2. NO BACKDOOR FOR ATTACKERS")
    print("      Cannot bypass security by causing outage")
    print()
    print("   3. CIRCUIT BREAKER")
    print("      Fast failure (5ms) instead of slow timeout")
    print()
    print("   4. IMMEDIATE RECOVERY")
    print("      Requests succeed as soon as control plane is healthy")
    print()
    print("   DURING OUTAGE:")
    print("   ┌─────────────────────────────────────────────────┐")
    print("   │  Requests allowed:  0                           │")
    print("   │  Security:          ✓ MAINTAINED                │")
    print("   │  Availability:      ✗ DEGRADED (by design)      │")
    print("   └─────────────────────────────────────────────────┘")
    print()
    print("=" * 70)


async def run_demo(mock_mode: bool = False):
    """Run the demo."""
    print_banner()
    
    if mock_mode:
        print("🎭 Running in MOCK MODE")
    else:
        print("🔌 Running with LIVE SERVICES")
        print("⚠️  This demo will stop/start the control plane!")
    print("-" * 70)
    
    # Phase 1: Healthy
    demo_phase_1_healthy()
    
    # Pause for effect
    await asyncio.sleep(1)
    
    # Phase 2: Outage
    demo_phase_2_outage()
    
    # Pause for effect
    await asyncio.sleep(1)
    
    # Phase 3: Recovery
    demo_phase_3_recovery()
    
    # Comparison
    compare_security_models()
    
    # Summary
    print_summary()
    
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Demo 6: Fail-Closed Security"
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Run in mock mode"
    )
    args = parser.parse_args()
    
    exit_code = asyncio.run(run_demo(mock_mode=args.mock))
    exit(exit_code)


if __name__ == "__main__":
    main()
```

---

## Test Cases

### Unit Tests

```python
# tests/demos/test_demo_06.py

import pytest
from demos.demo_06_fail_closed import (
    ControlPlaneStatus,
    simulate_request_healthy,
    simulate_request_unavailable
)

class TestDemo06:
    
    def test_healthy_request_succeeds(self):
        """Request succeeds when control plane healthy."""
        result = simulate_request_healthy()
        assert result.success is True
        assert result.error is None
        assert result.response is not None
    
    def test_unavailable_request_fails(self):
        """Request fails when control plane unavailable."""
        result = simulate_request_unavailable()
        assert result.success is False
        assert result.error is not None
        assert "Security denial" in result.error
    
    def test_unavailable_fails_fast(self):
        """Circuit breaker makes failure fast."""
        result = simulate_request_unavailable()
        # Should fail fast due to circuit breaker
        assert result.latency_ms < 100  # Much less than timeout
    
    def test_control_plane_statuses(self):
        """Control plane status enum works."""
        assert ControlPlaneStatus.HEALTHY.value == "healthy"
        assert ControlPlaneStatus.UNAVAILABLE.value == "unavailable"
```

---

## Post-Conditions

### Code Complete (enables dependent tasks to start)

- [ ] All acceptance criteria met
- [ ] Unit tests pass locally: `pytest deeptrail-gateway/tests/demos/`
- [ ] Demo runs in mock mode
- [ ] Completion report created

### Integration Complete (validated at merge point)

- [ ] Demo runs with actual container stop/start
- [ ] Zero requests allowed during outage verified

### Unblocks

| Task | Type | Notes |
|------|------|-------|
| - | - | Demo is leaf task |

---

## References

- Design Doc: [Section 5.6 - Demo 6: Fail-Closed Security](../../../design/internal/markdowns/deepsecure-virtual-mcp-server-mvp.md#56-demo-6-fail-closed-security)
- Related Code: `deeptrail-gateway/app/security/fail_closed.py` (E4)

---

## Notes

- Live demo requires stopping/starting Docker containers
- Mock mode simulates the behavior safely
- The fail-closed vs fail-open comparison is key messaging

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
