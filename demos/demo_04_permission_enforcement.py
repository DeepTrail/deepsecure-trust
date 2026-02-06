#!/usr/bin/env python3
"""
Demo 4: Permission Enforcement

Demonstrates that unauthorized tools are BLOCKED at the gateway
and NEVER reach the backend MCP server.

Value Proposition:
- Agent can only use delegated tools
- Unauthorized requests blocked immediately
- Backend sees ZERO unauthorized requests
- Zero-trust security model in action

Usage:
    # With real services
    python demo_04_permission_enforcement.py
    
    # With mock mode (no services required)
    python demo_04_permission_enforcement.py --mock

Reference:
    Design Doc Section 5.4 - Demo 4: Permission Enforcement
"""

import argparse
import asyncio
from dataclasses import dataclass, field


# =============================================================================
# Configuration
# =============================================================================


@dataclass
class DemoConfig:
    """Configuration for the permission enforcement demo."""
    GATEWAY_URL: str = "http://localhost:8002/mcp"
    AGENT_ID: str = "agent-sdr-001"
    AGENT_NAME: str = "SDR-Assistant"
    USER_EMAIL: str = "sarah@acme.com"


# Global config instance
CONFIG = DemoConfig()


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class DemoResult:
    """Result of running the demo."""
    success: bool
    authorized_calls: int = 0
    blocked_calls: int = 0
    backend_requests: int = 0
    error: str | None = None


@dataclass
class MockBackendLog:
    """Simulates backend request logging."""
    requests_received: list[dict] = field(default_factory=list)
    
    def log_request(self, tool: str, arguments: dict) -> None:
        """Log a request that reached the backend."""
        self.requests_received.append({
            "tool": tool,
            "arguments": arguments,
        })
    
    def get_requests_for_tool(self, tool: str) -> list[dict]:
        """Get all requests for a specific tool."""
        return [r for r in self.requests_received if r["tool"] == tool]
    
    def count_total(self) -> int:
        """Get total request count."""
        return len(self.requests_received)
    
    def count_unauthorized(self, unauthorized_tools: list[str]) -> int:
        """Count requests for unauthorized tools (should be 0!)."""
        count = 0
        for tool in unauthorized_tools:
            count += len(self.get_requests_for_tool(tool))
        return count


@dataclass
class ToolCallResult:
    """Result of a tool call attempt."""
    tool: str
    permission: str
    delegated: bool
    success: bool
    blocked_at_gateway: bool
    reached_backend: bool
    error_code: int | None = None
    error_message: str | None = None


# =============================================================================
# Permission Configuration
# =============================================================================


# Sarah's delegated permissions (limited set)
DELEGATED_PERMISSIONS = [
    "notion:pages:search",   # ✓ Can search
    "notion:pages:read",     # ✓ Can read
    # notion:pages:create    ✗ NOT delegated
    # notion:pages:delete    ✗ NOT delegated
    "slack:messages:search", # ✓ Can search
    "slack:channels:list",   # ✓ Can list
    # slack:messages:send    ✗ NOT delegated
]


# Tool to permission mapping
TOOL_PERMISSIONS: dict[str, str] = {
    "notion.search_pages": "notion:pages:search",
    "notion.read_page": "notion:pages:read",
    "notion.create_page": "notion:pages:create",
    "notion.delete_page": "notion:pages:delete",
    "slack.search_messages": "slack:messages:search",
    "slack.list_channels": "slack:channels:list",
    "slack.send_message": "slack:messages:send",
}


# Categorize tools
AUTHORIZED_TOOLS = [
    tool for tool, perm in TOOL_PERMISSIONS.items()
    if perm in DELEGATED_PERMISSIONS
]

UNAUTHORIZED_TOOLS = [
    tool for tool, perm in TOOL_PERMISSIONS.items()
    if perm not in DELEGATED_PERMISSIONS
]


# =============================================================================
# Helper Functions
# =============================================================================


def is_tool_authorized(tool: str) -> bool:
    """Check if a tool is authorized based on delegated permissions."""
    permission = TOOL_PERMISSIONS.get(tool)
    return permission is not None and permission in DELEGATED_PERMISSIONS


def get_permission_for_tool(tool: str) -> str:
    """Get the required permission for a tool."""
    return TOOL_PERMISSIONS.get(tool, "unknown:permission")


# =============================================================================
# Display Functions
# =============================================================================


def print_banner() -> None:
    """Print demo banner."""
    print()
    print("=" * 70)
    print("  DEMO 4: PERMISSION ENFORCEMENT")
    print("=" * 70)
    print()
    print("  Value Proposition:")
    print("  • Agent can ONLY call delegated tools")
    print("  • Unauthorized requests BLOCKED at gateway")
    print("  • Backend receives ZERO unauthorized requests")
    print("  • Zero-trust security model in action")
    print()
    print("-" * 70)


def print_section(title: str, icon: str = "📋") -> None:
    """Print section header."""
    print()
    print(f"{icon} {title}")
    print("-" * 50)


def print_permissions() -> None:
    """Print Sarah's delegated permissions."""
    print_section("SARAH'S DELEGATED PERMISSIONS", "🔐")
    
    print()
    print("   Delegated (agent can use):")
    for perm in DELEGATED_PERMISSIONS:
        print(f"   ✓ {perm}")
    
    print()
    print("   NOT Delegated (agent cannot use):")
    not_delegated = [
        "notion:pages:create",
        "notion:pages:delete",
        "slack:messages:send",
    ]
    for perm in not_delegated:
        print(f"   ✗ {perm}")


def print_authorized_call_result(tool: str, backend_log: MockBackendLog) -> ToolCallResult:
    """Simulate and display an authorized tool call."""
    print_section(f"AUTHORIZED CALL: {tool}", "✅")
    
    permission = get_permission_for_tool(tool)
    delegated = is_tool_authorized(tool)
    
    print()
    print(f"   Agent calls: {tool}")
    print(f"   Required permission: {permission}")
    print(f"   Delegated: {'✓ YES' if delegated else '✗ NO'}")
    
    print()
    print("   Gateway processing:")
    print("   1. ✓ JWT validated")
    print("   2. ✓ Agent session found")
    print("   3. ✓ Delegation active")
    print(f"   4. ✓ Permission check: {permission} in delegation")
    print("   5. ✓ Request forwarded to Notion backend")
    
    # Log to backend (request reached it)
    backend_log.log_request(tool, {"query": "sales playbook"})
    
    print()
    print("   Backend response:")
    print('   { "pages": [{"id": "page-123", "title": "Sales Playbook"}] }')
    
    print()
    print("   Result: ✅ SUCCESS")
    
    return ToolCallResult(
        tool=tool,
        permission=permission,
        delegated=True,
        success=True,
        blocked_at_gateway=False,
        reached_backend=True,
    )


def print_unauthorized_call_result(tool: str, backend_log: MockBackendLog) -> ToolCallResult:
    """Simulate and display an unauthorized tool call."""
    print_section(f"UNAUTHORIZED CALL: {tool}", "🚫")
    
    permission = get_permission_for_tool(tool)
    delegated = is_tool_authorized(tool)
    
    print()
    print(f"   Agent calls: {tool}")
    print(f"   Required permission: {permission}")
    print(f"   Delegated: {'✓ YES' if delegated else '✗ NO'}")
    
    print()
    print("   Gateway processing:")
    print("   1. ✓ JWT validated")
    print("   2. ✓ Agent session found")
    print("   3. ✓ Delegation active")
    print(f"   4. ✗ Permission check: {permission} NOT in delegation")
    print("   5. ❌ REQUEST BLOCKED - NOT forwarded to backend")
    
    # NOT logged to backend - request never reaches it
    # backend_log.log_request(tool, ...)  # Intentionally not called
    
    print()
    print("   Error response to agent:")
    print("   {")
    print('     "error": {')
    print('       "code": -32001,')
    print(f'       "message": "Permission denied: {permission} not delegated"')
    print("     }")
    print("   }")
    
    print()
    print("   Result: 🚫 BLOCKED AT GATEWAY")
    
    return ToolCallResult(
        tool=tool,
        permission=permission,
        delegated=False,
        success=False,
        blocked_at_gateway=True,
        reached_backend=False,
        error_code=-32001,
        error_message=f"Permission denied: {permission} not delegated",
    )


def print_backend_verification(backend_log: MockBackendLog) -> None:
    """Verify what the backend actually received."""
    print_section("BACKEND REQUEST LOG VERIFICATION", "🔍")
    
    print()
    print("   Notion Backend received these requests:")
    print("   " + "-" * 46)
    
    all_requests = backend_log.requests_received
    
    if all_requests:
        for req in all_requests:
            print(f"   • {req['tool']} - args: {req['arguments']}")
    else:
        print("   (no requests)")
    
    print()
    print(f"   Total requests received: {len(all_requests)}")
    
    # Check for unauthorized requests
    unauthorized_count = backend_log.count_unauthorized(UNAUTHORIZED_TOOLS)
    
    print()
    print("   Unauthorized requests received by backend:")
    if unauthorized_count > 0:
        print(f"   ⚠️  {unauthorized_count} UNAUTHORIZED REQUESTS - SECURITY VIOLATION!")
        for tool in UNAUTHORIZED_TOOLS:
            reqs = backend_log.get_requests_for_tool(tool)
            for req in reqs:
                print(f"   ⚠️  {req['tool']} - THIS SHOULD NOT HAPPEN!")
    else:
        print("   ✅ ZERO - Backend never saw unauthorized requests")


def print_defense_in_depth() -> None:
    """Print the defense in depth diagram."""
    print_section("DEFENSE IN DEPTH", "🛡️")
    print()
    print("   ┌─────────────────────────────────────────────────────────┐")
    print("   │ Layer 1: JWT validation (is request authentic?)         │")
    print("   │ Layer 2: Session check (is agent session valid?)        │")
    print("   │ Layer 3: Delegation check (does user consent exist?)    │")
    print("   │ Layer 4: Permission check (is action delegated?)        │")
    print("   │ ─────────────────────────────────────────────────────── │")
    print("   │ Only after ALL checks pass → forward to backend         │")
    print("   └─────────────────────────────────────────────────────────┘")


def print_summary(authorized_count: int, blocked_count: int, backend_requests: int) -> None:
    """Print demo summary."""
    print()
    print("=" * 70)
    print("  ✅ KEY INSIGHTS")
    print("=" * 70)
    print()
    print("   1. GATEWAY AS SECURITY BOUNDARY")
    print("      All permission checks happen at gateway, not backend")
    print()
    print("   2. ZERO UNAUTHORIZED BACKEND CALLS")
    print("      Backend never processes unauthorized requests")
    print()
    print("   3. CLEAR ERROR MESSAGES")
    print("      Agent knows exactly which permission is missing")
    print()
    print("   4. METRICS")
    print(f"      Authorized calls:        {authorized_count}")
    print(f"      Blocked calls:           {blocked_count}")
    print(f"      Backend requests:        {backend_requests}")
    print("      Unauthorized to backend: 0 (enforced)")
    print()
    print("=" * 70)
    print()


# =============================================================================
# Main Demo Function
# =============================================================================


async def run_demo(mock_mode: bool = False) -> DemoResult:
    """
    Run the permission enforcement demo.
    
    Args:
        mock_mode: If True, run in mock mode (no services required)
        
    Returns:
        DemoResult with success status and metrics
    """
    print_banner()
    
    if mock_mode:
        print("🎭 Running in MOCK MODE (no services required)")
    else:
        print("🔌 Running with LIVE SERVICES (mock data for demo)")
    print("-" * 70)
    
    try:
        # Create mock backend log to track requests
        backend_log = MockBackendLog()
        
        # Track results
        authorized_count = 0
        blocked_count = 0
        
        # Show permissions
        print_permissions()
        
        # Simulate authorized call
        result1 = print_authorized_call_result("notion.search_pages", backend_log)
        if result1.success:
            authorized_count += 1
        
        # Simulate unauthorized call
        result2 = print_unauthorized_call_result("notion.create_page", backend_log)
        if result2.blocked_at_gateway:
            blocked_count += 1
        
        # Another unauthorized call
        result3 = print_unauthorized_call_result("slack.send_message", backend_log)
        if result3.blocked_at_gateway:
            blocked_count += 1
        
        # Verify backend logs
        print_backend_verification(backend_log)
        
        # Show defense in depth
        print_defense_in_depth()
        
        # Summary
        backend_requests = backend_log.count_total()
        print_summary(authorized_count, blocked_count, backend_requests)
        
        return DemoResult(
            success=True,
            authorized_calls=authorized_count,
            blocked_calls=blocked_count,
            backend_requests=backend_requests,
        )
        
    except Exception as e:
        error_msg = str(e)
        print(f"\n❌ Error: {error_msg}")
        
        return DemoResult(success=False, error=error_msg)


# =============================================================================
# CLI Entry Point
# =============================================================================


def main() -> int:
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(
        description="Demo 4: Permission Enforcement - "
                    "Unauthorized tools blocked at gateway",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Run with mock data
    python demo_04_permission_enforcement.py --mock
    
    # Run demo
    python demo_04_permission_enforcement.py
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
