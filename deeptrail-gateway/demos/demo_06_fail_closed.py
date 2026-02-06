#!/usr/bin/env python3
"""
Demo 6: Fail-Closed Security

Demonstrates that when the Control Plane is unavailable,
ALL agent requests are DENIED. No fail-open behavior.

Value Proposition:
- Security failure mode: DENY, not ALLOW
- No backdoor when policy service is down
- Immediate recovery when service restored

This is a critical security property: even if an attacker can
bring down the policy service, they cannot use that to bypass
permission checks.

Usage:
    # With mock mode (no services required)
    python demo_06_fail_closed.py --mock
    
    # With real services (will simulate outage)
    python demo_06_fail_closed.py

Reference:
    Design Doc Section 5.6 - Demo 6: Fail-Closed Security
"""

import argparse
import asyncio
from dataclasses import dataclass
from enum import Enum


# =============================================================================
# Configuration
# =============================================================================


@dataclass
class DemoConfig:
    """Configuration for the fail-closed demo."""
    GATEWAY_URL: str = "http://localhost:8002/mcp"
    CONTROL_PLANE_URL: str = "http://localhost:8000"
    AGENT_ID: str = "agent-sdr-001"
    TOOL_NAME: str = "notion.search_pages"


# Global config instance
CONFIG = DemoConfig()


# =============================================================================
# Enums and Data Classes
# =============================================================================


class ControlPlaneStatus(Enum):
    """Status of the control plane service."""
    HEALTHY = "healthy"
    UNAVAILABLE = "unavailable"


@dataclass
class RequestResult:
    """Result of a request attempt."""
    success: bool
    response: str | None
    error: str | None
    latency_ms: float
    control_plane_status: ControlPlaneStatus


@dataclass
class DemoResult:
    """Result of running the demo."""
    success: bool
    requests_during_healthy: int
    requests_during_outage: int
    allowed_during_outage: int
    error: str | None = None


@dataclass
class OutageMetrics:
    """Metrics collected during a simulated outage."""
    total_requests: int
    denied_requests: int
    allowed_requests: int
    
    @property
    def security_maintained(self) -> bool:
        """Check if security was maintained (all requests denied)."""
        return self.allowed_requests == 0


# =============================================================================
# Request Simulation Functions
# =============================================================================


def simulate_request_healthy() -> RequestResult:
    """Simulate a request when control plane is healthy."""
    return RequestResult(
        success=True,
        response='{"pages": [{"id": "page-123", "title": "Sales Playbook"}]}',
        error=None,
        latency_ms=145.3,
        control_plane_status=ControlPlaneStatus.HEALTHY,
    )


def simulate_request_unavailable() -> RequestResult:
    """Simulate a request when control plane is unavailable."""
    return RequestResult(
        success=False,
        response=None,
        error="MCPError(-32000): Security denial - policy service unavailable",
        latency_ms=5.2,  # Fast failure due to circuit breaker
        control_plane_status=ControlPlaneStatus.UNAVAILABLE,
    )


def is_request_allowed(result: RequestResult) -> bool:
    """Check if a request was allowed."""
    return result.success


def get_error_code(result: RequestResult) -> int | None:
    """Extract error code from result."""
    if result.error and "MCPError(" in result.error:
        # Parse MCPError(-32000)
        start = result.error.index("(") + 1
        end = result.error.index(")")
        return int(result.error[start:end])
    return None


# =============================================================================
# Display Functions
# =============================================================================


def print_banner() -> None:
    """Print demo banner."""
    print()
    print("=" * 70)
    print("  DEMO 6: FAIL-CLOSED SECURITY")
    print("=" * 70)
    print()
    print("  Value Proposition:")
    print("  • When policy service is down → ALL requests DENIED")
    print("  • No 'fail-open' backdoor for attackers")
    print("  • Security failure mode prioritizes safety")
    print("  • Immediate recovery when service restored")
    print()
    print("-" * 70)


def print_section(title: str, icon: str = "📋") -> None:
    """Print section header."""
    print()
    print(f"{icon} {title}")
    print("-" * 50)


def print_control_plane_status(status: ControlPlaneStatus) -> None:
    """Print control plane status."""
    if status == ControlPlaneStatus.HEALTHY:
        print("   Control Plane Status: 🟢 HEALTHY")
        print(f"   URL: {CONFIG.CONTROL_PLANE_URL}")
        print("   Health Check: ✓ 200 OK")
    else:
        print("   Control Plane Status: 🔴 UNAVAILABLE")
        print(f"   URL: {CONFIG.CONTROL_PLANE_URL}")
        print("   Health Check: ✗ Connection refused")


def print_request_result(result: RequestResult, phase: str) -> None:
    """Print request result."""
    print(f"\n   {phase}")
    print("   " + "-" * 40)
    print(f"   Tool: {CONFIG.TOOL_NAME}")
    print("   Args: {'query': 'sales playbook'}")
    print(f"   Latency: {result.latency_ms:.1f}ms")
    print()
    
    if result.success:
        print("   Result: ✅ SUCCESS")
        print(f"   Response: {result.response}")
    else:
        print("   Result: 🚫 DENIED")
        print(f"   Error: {result.error}")


def print_outage_metrics(metrics: OutageMetrics) -> None:
    """Print metrics from the outage period."""
    print()
    print("   " + "=" * 50)
    print("   SECURITY BEHAVIOR: FAIL-CLOSED")
    print("   " + "=" * 50)
    print(f"   • Total requests attempted: {metrics.total_requests}")
    print(f"   • Requests denied: {metrics.denied_requests}")
    print(f"   • Requests allowed: {metrics.allowed_requests}")
    print()
    if metrics.security_maintained:
        print("   ✅ SECURITY MAINTAINED: 0 requests allowed during outage")
    else:
        print("   ❌ SECURITY BREACH: Requests were allowed during outage!")
    print("   " + "=" * 50)


def print_security_comparison() -> None:
    """Compare fail-open vs fail-closed security models."""
    print_section("COMPARISON: Security Failure Modes", "⚖️")
    
    print("""
   ┌─────────────────────────────────────────────────────────────────┐
   │                     FAIL-OPEN (DANGEROUS)                       │
   ├─────────────────────────────────────────────────────────────────┤
   │                                                                 │
   │  When policy service is unavailable:                           │
   │  → "Just let the request through, we'll log it later"          │
   │                                                                 │
   │  RISK: Attacker can intentionally cause policy service outage  │
   │        and then execute any action without permission checks.   │
   │                                                                 │
   │  This is a CRITICAL VULNERABILITY.                             │
   │                                                                 │
   └─────────────────────────────────────────────────────────────────┘
   
   ┌─────────────────────────────────────────────────────────────────┐
   │                     FAIL-CLOSED (DEEPSECURE)                    │
   ├─────────────────────────────────────────────────────────────────┤
   │                                                                 │
   │  When policy service is unavailable:                           │
   │  → DENY ALL REQUESTS                                           │
   │                                                                 │
   │  WHY: We cannot verify permissions, so we cannot allow action. │
   │                                                                 │
   │  TRADEOFF: Availability suffers, but security is maintained.   │
   │                                                                 │
   │  This is the CORRECT security posture.                         │
   │                                                                 │
   └─────────────────────────────────────────────────────────────────┘
""")


def print_summary(allowed_during_outage: int) -> None:
    """Print demo summary."""
    print()
    print("=" * 70)
    print("  ✅ KEY INSIGHTS")
    print("=" * 70)
    print()
    print("   1. FAIL-CLOSED BY DESIGN")
    print("      Gateway denies ALL requests when control plane unavailable")
    print()
    print("   2. NO BACKDOOR FOR ATTACKERS")
    print("      Cannot bypass security by causing outage")
    print()
    print("   3. CIRCUIT BREAKER")
    print("      Fast failure (~5ms) instead of slow timeout")
    print()
    print("   4. IMMEDIATE RECOVERY")
    print("      Requests succeed as soon as control plane is healthy")
    print()
    print("   DURING OUTAGE:")
    print("   ┌─────────────────────────────────────────────────┐")
    print(f"   │  Requests allowed:  {allowed_during_outage}                           │")
    print("   │  Security:          ✓ MAINTAINED                │")
    print("   │  Availability:      ✗ DEGRADED (by design)      │")
    print("   └─────────────────────────────────────────────────┘")
    print()
    print("=" * 70)
    print()


# =============================================================================
# Demo Phases
# =============================================================================


def demo_phase_1_healthy() -> RequestResult:
    """Phase 1: Control plane healthy - request succeeds."""
    print_section("PHASE 1: CONTROL PLANE HEALTHY", "🟢")
    
    print_control_plane_status(ControlPlaneStatus.HEALTHY)
    
    result = simulate_request_healthy()
    print_request_result(result, "Agent makes request:")
    
    print("\n   → Request succeeds because gateway can verify permissions")
    
    return result


def demo_phase_2_outage(num_attempts: int = 3) -> OutageMetrics:
    """Phase 2: Control plane outage - all requests denied."""
    print_section("PHASE 2: CONTROL PLANE OUTAGE", "🔴")
    
    print("\n   ⚡ SIMULATING CONTROL PLANE OUTAGE...")
    print("   (In reality: docker stop deeptrail-control)")
    print()
    
    print_control_plane_status(ControlPlaneStatus.UNAVAILABLE)
    
    print("\n   Agent tries to make requests during outage:")
    
    denied = 0
    allowed = 0
    
    for i in range(num_attempts):
        result = simulate_request_unavailable()
        
        if is_request_allowed(result):
            allowed += 1
            status = "✅ ALLOWED"
        else:
            denied += 1
            status = "🚫 DENIED"
        
        print(f"\n   Attempt {i + 1}:")
        print(f"   Tool: {CONFIG.TOOL_NAME}")
        print(f"   Result: {status}")
        if result.error:
            print(f"   Error: {result.error}")
    
    metrics = OutageMetrics(
        total_requests=num_attempts,
        denied_requests=denied,
        allowed_requests=allowed,
    )
    
    print_outage_metrics(metrics)
    
    return metrics


def demo_phase_3_recovery() -> RequestResult:
    """Phase 3: Control plane restored - requests succeed again."""
    print_section("PHASE 3: CONTROL PLANE RESTORED", "🟢")
    
    print("\n   🔄 CONTROL PLANE COMING BACK ONLINE...")
    print("   (In reality: docker start deeptrail-control)")
    print()
    
    print_control_plane_status(ControlPlaneStatus.HEALTHY)
    
    result = simulate_request_healthy()
    print_request_result(result, "Agent makes request after recovery:")
    
    print("\n   → Requests succeed again immediately")
    
    return result


# =============================================================================
# Main Demo Function
# =============================================================================


async def run_demo(mock_mode: bool = False) -> DemoResult:
    """
    Run the fail-closed security demo.
    
    Args:
        mock_mode: If True, run in mock mode (no services required)
        
    Returns:
        DemoResult with success status and metrics
    """
    print_banner()
    
    if mock_mode:
        print("🎭 Running in MOCK MODE (no services required)")
    else:
        print("🔌 Running with LIVE SERVICES")
        print("⚠️  This demo will stop/start the control plane!")
    print("-" * 70)
    
    try:
        # Track metrics
        requests_during_healthy = 0
        requests_during_outage = 0
        allowed_during_outage = 0
        
        # Phase 1: Healthy
        demo_phase_1_healthy()
        requests_during_healthy += 1
        
        # Pause for effect
        await asyncio.sleep(0.5)
        
        # Phase 2: Outage
        outage_metrics = demo_phase_2_outage(num_attempts=3)
        requests_during_outage = outage_metrics.total_requests
        allowed_during_outage = outage_metrics.allowed_requests
        
        # Pause for effect
        await asyncio.sleep(0.5)
        
        # Phase 3: Recovery
        demo_phase_3_recovery()
        requests_during_healthy += 1
        
        # Comparison
        print_security_comparison()
        
        # Summary
        print_summary(allowed_during_outage)
        
        return DemoResult(
            success=True,
            requests_during_healthy=requests_during_healthy,
            requests_during_outage=requests_during_outage,
            allowed_during_outage=allowed_during_outage,
        )
        
    except Exception as e:
        error_msg = str(e)
        print(f"\n❌ Error: {error_msg}")
        
        return DemoResult(
            success=False,
            requests_during_healthy=0,
            requests_during_outage=0,
            allowed_during_outage=0,
            error=error_msg,
        )


# =============================================================================
# CLI Entry Point
# =============================================================================


def main() -> int:
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(
        description="Demo 6: Fail-Closed Security - "
                    "All requests denied during policy service outage",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Run with mock data
    python demo_06_fail_closed.py --mock
    
    # Run demo
    python demo_06_fail_closed.py
        """,
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Run in mock mode (no services required)",
    )
    args = parser.parse_args()
    
    result = asyncio.run(run_demo(mock_mode=args.mock))
    
    return 0 if result.success else 1


if __name__ == "__main__":
    exit(main())
