#!/usr/bin/env python3
"""
Demo 3: Delegation-Based Execution

Demonstrates that an agent uses Sarah's credentials WITHOUT ever 
seeing them. The gateway injects credentials on behalf of the user.

Value Proposition:
- Agent calls tool (no credentials in request)
- Gateway injects Sarah's OAuth token
- Agent receives result (no credentials in response)
- Full audit trail: "agent on behalf of Sarah"

This is the core security model of the Virtual MCP Server:
Zero-knowledge execution where agents never see sensitive credentials.

Usage:
    # With real services
    python demo_03_delegation_execution.py
    
    # With mock mode (no services required)
    python demo_03_delegation_execution.py --mock

Reference:
    Design Doc Section 5.3 - Demo 3: Delegation-Based Execution
"""

import argparse
import asyncio
import json
from dataclasses import dataclass
from datetime import datetime, timezone


# =============================================================================
# Configuration
# =============================================================================


@dataclass
class DemoConfig:
    """Configuration for the delegation execution demo."""
    GATEWAY_URL: str = "http://localhost:8002/mcp"
    AGENT_ID: str = "agent-sdr-001"
    AGENT_NAME: str = "SDR-Assistant"
    USER_EMAIL: str = "sarah@acme.com"
    USER_ID: str = "user-sarah-123"
    DELEGATION_ID: str = "del-sarah-sdr-001"
    CREDENTIAL_REF: str = "vault://sarah-notion-oauth-xyz"
    TOOL_NAME: str = "notion.search_pages"
    BACKEND: str = "notion"


# Global config instance
CONFIG = DemoConfig()


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class DemoResult:
    """Result of running the demo."""
    success: bool
    error: str | None = None


@dataclass
class GatewayStep:
    """A step in the gateway's processing."""
    number: int
    title: str
    details: list[str]


# =============================================================================
# Gateway Processing Steps
# =============================================================================


def get_gateway_steps() -> list[GatewayStep]:
    """Get the list of gateway processing steps."""
    return [
        GatewayStep(
            number=1,
            title="RECEIVE request from agent",
            details=[
                f"POST {CONFIG.GATEWAY_URL} tools/call",
                f"Tool: {CONFIG.TOOL_NAME}",
            ],
        ),
        GatewayStep(
            number=2,
            title="VALIDATE agent session",
            details=[
                f"Agent: {CONFIG.AGENT_ID}",
                f"Delegation: {CONFIG.DELEGATION_ID}",
                f"Acting on behalf of: {CONFIG.USER_EMAIL}",
            ],
        ),
        GatewayStep(
            number=3,
            title="CHECK permission",
            details=[
                "Required: notion:pages:search",
                "Delegation grants: [notion:pages:search, ...] ✓ ALLOWED",
            ],
        ),
        GatewayStep(
            number=4,
            title="LOOKUP credentials (from vault)",
            details=[
                f"Credential ref: {CONFIG.CREDENTIAL_REF}",
                "Retrieved: Bearer eyJhbGc... [REDACTED]",
            ],
        ),
        GatewayStep(
            number=5,
            title="INJECT credentials into backend request",
            details=[
                "POST https://mcp.notion.com/tools/call",
                "Headers:",
                "  Authorization: Bearer eyJhbGc... ← Sarah's token",
                f"  X-DeepSecure-Agent: {CONFIG.AGENT_ID}",
                f"  X-DeepSecure-On-Behalf-Of: {CONFIG.USER_EMAIL}",
            ],
        ),
        GatewayStep(
            number=6,
            title="FORWARD to backend and get result",
            details=[
                "Status: 200 OK",
                'Result: {"pages": [...]}',
            ],
        ),
        GatewayStep(
            number=7,
            title="STRIP any credential echoes from response",
            details=[
                "Ensure no tokens leak back to agent",
                "Sanitize response before returning",
            ],
        ),
        GatewayStep(
            number=8,
            title="LOG audit event",
            details=[
                "{",
                f'  "actor": "{CONFIG.AGENT_ID}",',
                f'  "on_behalf_of": "{CONFIG.USER_EMAIL}",',
                f'  "tool": "{CONFIG.TOOL_NAME}",',
                '  "result": "success"',
                "}",
            ],
        ),
    ]


# =============================================================================
# Display Functions
# =============================================================================


def print_banner() -> None:
    """Print demo banner."""
    print()
    print("=" * 70)
    print("  DEMO 3: DELEGATION-BASED EXECUTION")
    print("=" * 70)
    print()
    print("  Value Proposition:")
    print("  • Agent calls tools WITHOUT knowing credentials")
    print("  • Gateway securely injects user's OAuth tokens")
    print("  • Agent NEVER sees sensitive credential values")
    print("  • Every action attributed: 'agent on behalf of user'")
    print()
    print("-" * 70)


def print_section(title: str, icon: str = "📋") -> None:
    """Print section header."""
    print()
    print(f"{icon} {title}")
    print("-" * 50)


def format_json(data: dict, indent: int = 2) -> str:
    """Format JSON for display."""
    return json.dumps(data, indent=indent)


def print_agent_perspective() -> None:
    """Show what the agent sees and does."""
    print_section("AGENT PERSPECTIVE", "🤖")
    
    print()
    print("   Agent code:")
    print("   " + "-" * 44)
    print("   # Agent makes a simple tool call")
    print("   result = await client.tools_call(")
    print('       "notion.search_pages",')
    print('       {"query": "sales playbook"}')
    print("   )")
    print("   ")
    print("   # Agent sees result")
    print("   print(result)  # Page content, no credentials")
    print("   " + "-" * 44)
    
    print()
    print("   What agent sends to gateway:")
    agent_request = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {
            "name": "notion.search_pages",
            "arguments": {"query": "sales playbook"},
        },
        "id": 1,
    }
    
    # Format with indentation
    formatted = format_json(agent_request)
    for line in formatted.split("\n"):
        print(f"   {line}")
    
    print()
    print("   ⚠️  NOTE: No credentials in request!")
    print("   The agent has no idea what OAuth token is used.")


def print_gateway_perspective() -> None:
    """Show what the gateway does behind the scenes."""
    print_section("GATEWAY PERSPECTIVE (behind the scenes)", "🔐")
    
    steps = get_gateway_steps()
    
    for step in steps:
        print()
        print(f"   {step.number}. {step.title}")
        for detail in step.details:
            print(f"      {detail}")


def print_agent_receives() -> None:
    """Show what the agent receives."""
    print_section("WHAT AGENT RECEIVES", "📨")
    
    response = {
        "jsonrpc": "2.0",
        "result": {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps({
                        "pages": [
                            {"id": "page-123", "title": "Sales Playbook Q1"},
                            {"id": "page-456", "title": "Outreach Templates"},
                        ],
                    }),
                },
            ],
        },
        "id": 1,
    }
    
    print()
    print("   Response to agent:")
    formatted = format_json(response)
    for line in formatted.split("\n"):
        print(f"   {line}")
    
    print()
    print("   ✓ Contains: search results (page content)")
    print("   ✗ Does NOT contain:")
    print("     • Sarah's OAuth token")
    print("     • Vault reference")
    print("     • Backend URL")
    print("     • Any authentication headers")


def print_audit_trail() -> None:
    """Show the audit trail."""
    print_section("AUDIT TRAIL", "📋")
    
    audit_event = {
        "event_id": "evt-abc123",
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
        "event_type": "tools_call",
        "actor": {
            "type": "agent",
            "id": CONFIG.AGENT_ID,
            "name": CONFIG.AGENT_NAME,
        },
        "on_behalf_of": {
            "type": "user",
            "email": CONFIG.USER_EMAIL,
            "delegation_id": CONFIG.DELEGATION_ID,
        },
        "action": {
            "tool": CONFIG.TOOL_NAME,
            "backend": CONFIG.BACKEND,
            "arguments": {"query": "sales playbook"},
        },
        "result": {
            "status": "success",
            "duration_ms": 145,
        },
    }
    
    print()
    print("   Audit event recorded:")
    formatted = format_json(audit_event)
    for line in formatted.split("\n"):
        print(f"   {line}")
    
    print()
    print("   Later, Sarah can ask:")
    print('   "What did my agent do today?"')
    print()
    print("   And see:")
    print(f"   • {CONFIG.AGENT_NAME} searched Notion for 'sales playbook'")
    print(f"   • Acting as: {CONFIG.USER_EMAIL}")
    print("   • Result: Found 2 pages")


def print_security_comparison() -> None:
    """Print security model comparison."""
    print_section("SECURITY COMPARISON", "🔒")
    
    print()
    print("   Traditional API Key Approach:")
    print("   ┌────────────────────────────────────────────────────────────┐")
    print("   │  Agent has API key → Agent can do ANYTHING                 │")
    print("   │  • No visibility into what agent does                      │")
    print("   │  • No way to limit scope                                   │")
    print("   │  • If agent is compromised, full access is lost            │")
    print("   └────────────────────────────────────────────────────────────┘")
    
    print()
    print("   DeepSecure Delegation Approach:")
    print("   ┌────────────────────────────────────────────────────────────┐")
    print("   │  Agent has delegation → Agent can do ONLY what's allowed   │")
    print("   │  • Full audit trail of every action                        │")
    print("   │  • Scope limited to delegated permissions                  │")
    print("   │  • Credentials never exposed to agent                      │")
    print("   └────────────────────────────────────────────────────────────┘")


def print_summary() -> None:
    """Print demo summary."""
    print()
    print("=" * 70)
    print("  ✅ KEY INSIGHTS")
    print("=" * 70)
    print()
    print("   1. ZERO-KNOWLEDGE EXECUTION")
    print("      Agent executes tools without knowing credentials")
    print()
    print("   2. CREDENTIAL ISOLATION")
    print("      OAuth tokens stay in vault, never sent to agent")
    print()
    print("   3. FULL ATTRIBUTION")
    print("      Every action logged as 'agent on behalf of user'")
    print()
    print("   4. DEFENSE IN DEPTH")
    print("      Even if agent is compromised, credentials are safe")
    print()
    print("=" * 70)
    print()


# =============================================================================
# Main Demo Function
# =============================================================================


async def run_demo(mock_mode: bool = False) -> DemoResult:
    """
    Run the delegation execution demo.
    
    Args:
        mock_mode: If True, run in mock mode (always used for this demo)
        
    Returns:
        DemoResult with success status
    """
    print_banner()
    
    if mock_mode:
        print("🎭 Running in MOCK MODE (no services required)")
    else:
        print("🔌 Running with LIVE SERVICES (mock data for demo)")
    print("-" * 70)
    
    try:
        # Demo sections
        print_agent_perspective()
        print_gateway_perspective()
        print_agent_receives()
        print_audit_trail()
        print_security_comparison()
        print_summary()
        
        return DemoResult(success=True)
        
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
        description="Demo 3: Delegation-Based Execution - "
                    "Zero-knowledge credential injection",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Run with mock data
    python demo_03_delegation_execution.py --mock
    
    # Run demo
    python demo_03_delegation_execution.py
        """,
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Run in mock mode (default behavior for this demo)",
    )
    args = parser.parse_args()
    
    result = asyncio.run(run_demo(mock_mode=args.mock))
    
    return 0 if result.success else 1


if __name__ == "__main__":
    exit(main())
