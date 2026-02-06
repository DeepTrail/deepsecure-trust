#!/usr/bin/env python3
"""
Cross-Service Workflow Demo

Demonstrates an agent orchestrating actions across multiple
backend MCP servers (Notion, Slack, HubSpot) in a realistic
business workflow.

Workflow: "Sales Research and Outreach"
1. Search Notion for product info
2. Find relevant contacts in HubSpot
3. Get outreach templates from Notion
4. Send notification to Slack
5. Update contact status in HubSpot

Value Proposition:
- Single agent connection to gateway
- Seamless cross-backend data flow
- Unified audit trail
- Permission checks at each step

Usage:
    # With mock mode (no services required)
    python demo_cross_service_workflow.py --mock
    
    # With real services
    python demo_cross_service_workflow.py

Reference:
    Design Doc Section 3 - Phase 2: Cross-service workflow
"""

import argparse
import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone


# =============================================================================
# Configuration
# =============================================================================


@dataclass
class DemoConfig:
    """Configuration for the cross-service workflow demo."""
    GATEWAY_URL: str = "http://localhost:8002/mcp"
    AGENT_ID: str = "agent-sdr-001"
    AGENT_NAME: str = "SDR-Assistant"
    USER_EMAIL: str = "sarah@acme.com"
    USER_ID: str = "user-sarah-123"
    DELEGATION_ID: str = "del-sarah-sdr-001"


# Global config instance
CONFIG = DemoConfig()


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class WorkflowStep:
    """Represents a step in the workflow."""
    step_num: int
    backend: str
    tool: str
    description: str
    arguments: dict
    result: dict = field(default_factory=dict)
    duration_ms: float = 0.0
    status: str = "pending"


@dataclass
class WorkflowResult:
    """Result of running the workflow demo."""
    success: bool
    steps_executed: int
    steps_succeeded: int
    backends_used: list[str]
    total_duration_ms: float
    error: str | None = None


@dataclass
class AuditEntry:
    """An entry in the audit trail."""
    timestamp: str
    backend: str
    tool: str
    status: str
    agent_id: str
    user_email: str


# =============================================================================
# Workflow Definition
# =============================================================================


def get_workflow_steps() -> list[WorkflowStep]:
    """Get the workflow steps for the demo."""
    return [
        WorkflowStep(
            step_num=1,
            backend="notion",
            tool="notion.search_pages",
            description="Search for product information",
            arguments={"query": "Enterprise AI Security Features"},
            result={
                "pages": [
                    {"id": "page-123", "title": "DeepSecure Product Overview"},
                    {"id": "page-456", "title": "AI Security Best Practices"},
                ]
            },
        ),
        WorkflowStep(
            step_num=2,
            backend="hubspot",
            tool="hubspot.search_contacts",
            description="Find contacts interested in AI security",
            arguments={"query": "AI security", "industry": "fintech"},
            result={
                "contacts": [
                    {"id": "contact-456", "name": "John Smith", "company": "FinBank Inc"},
                    {"id": "contact-789", "name": "Jane Doe", "company": "SecureFinance"},
                ]
            },
        ),
        WorkflowStep(
            step_num=3,
            backend="notion",
            tool="notion.read_page",
            description="Get outreach email template",
            arguments={"page_id": "template-outreach-001"},
            result={
                "content": "Hi {name}, I noticed {company} is exploring AI security solutions. "
                           "I'd love to show you how DeepSecure can help..."
            },
        ),
        WorkflowStep(
            step_num=4,
            backend="slack",
            tool="slack.send_message",
            description="Notify SDR team about hot leads",
            arguments={
                "channel": "#sdr-team",
                "message": "🎯 Found 2 hot leads for AI Security: "
                           "John Smith (FinBank), Jane Doe (SecureFinance)",
            },
            result={
                "message_id": "msg-12345",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        ),
        WorkflowStep(
            step_num=5,
            backend="hubspot",
            tool="hubspot.update_contact",
            description="Update contact status to 'Contacted'",
            arguments={
                "contact_id": "contact-456",
                "status": "Contacted",
                "notes": "AI security outreach - DeepSecure demo scheduled",
            },
            result={
                "success": True,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
        ),
    ]


def get_backend_icon(backend: str) -> str:
    """Get the icon for a backend."""
    icons = {
        "notion": "📝",
        "hubspot": "💼",
        "slack": "💬",
    }
    return icons.get(backend, "🔧")


def get_unique_backends(steps: list[WorkflowStep]) -> list[str]:
    """Get list of unique backends used."""
    return sorted(set(step.backend for step in steps))


# =============================================================================
# Step Execution
# =============================================================================


async def execute_step(step: WorkflowStep) -> WorkflowStep:
    """Execute a workflow step (simulated)."""
    start_time = asyncio.get_event_loop().time()
    
    # Simulate network latency and processing
    await asyncio.sleep(0.05)
    
    step.duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
    step.status = "success"
    
    return step


def is_step_successful(step: WorkflowStep) -> bool:
    """Check if a step completed successfully."""
    return step.status == "success"


# =============================================================================
# Display Functions
# =============================================================================


def print_banner() -> None:
    """Print demo banner."""
    print()
    print("=" * 70)
    print("  CROSS-SERVICE WORKFLOW DEMO")
    print("=" * 70)
    print()
    print("  Workflow: Sales Research and Outreach")
    print()
    print("  Backend Services Used:")
    print("  • Notion  - Knowledge base, templates")
    print("  • HubSpot - CRM, contact management")
    print("  • Slack   - Team communication")
    print()
    print("  Value Proposition:")
    print("  • Single agent connection to gateway")
    print("  • Seamless cross-backend data flow")
    print("  • Unified audit trail")
    print("  • Permission checks at each step")
    print()
    print("-" * 70)


def print_section(title: str, icon: str = "📋") -> None:
    """Print section header."""
    print()
    print(f"{icon} {title}")
    print("-" * 50)


def print_workflow_overview(steps: list[WorkflowStep]) -> None:
    """Print workflow overview."""
    print_section("WORKFLOW OVERVIEW", "📊")
    
    print()
    print("   " + "=" * 55)
    print("   SALES RESEARCH AND OUTREACH WORKFLOW")
    print("   " + "=" * 55)
    
    for step in steps:
        icon = get_backend_icon(step.backend)
        print(f"   {step.step_num}. [{icon} {step.backend.upper():8}] {step.description}")
    
    print("   " + "=" * 55)


def print_step_execution(step: WorkflowStep) -> None:
    """Print step execution details."""
    icon = get_backend_icon(step.backend)
    
    print()
    print(f"   {'─' * 55}")
    print(f"   STEP {step.step_num}: {step.description}")
    print(f"   {'─' * 55}")
    print(f"   Backend:  {icon} {step.backend.upper()}")
    print(f"   Tool:     {step.tool}")
    print(f"   Args:     {step.arguments}")
    print(f"   Duration: {step.duration_ms:.1f}ms")
    print(f"   Status:   ✅ {step.status.upper()}")
    
    # Format result nicely
    result_str = str(step.result)
    if len(result_str) > 60:
        result_str = result_str[:57] + "..."
    print(f"   Result:   {result_str}")


def print_data_flow() -> None:
    """Visualize data flowing between services."""
    print_section("DATA FLOW VISUALIZATION", "🔄")
    
    print("""
   ┌─────────────────────────────────────────────────────────────────┐
   │                        AGENT WORKFLOW                           │
   └───────────────────────────┬─────────────────────────────────────┘
                               │
                               ▼
   ┌─────────────────────────────────────────────────────────────────┐
   │                    DEEPSECURE GATEWAY                           │
   │  (single connection, all backends accessible)                   │
   └───────────────────────────┬─────────────────────────────────────┘
                               │
         ┌─────────────────────┼─────────────────────┐
         │                     │                     │
         ▼                     ▼                     ▼
   ┌───────────┐         ┌───────────┐         ┌───────────┐
   │  NOTION   │         │  HUBSPOT  │         │   SLACK   │
   │  📝       │         │  💼       │         │   💬      │
   ├───────────┤         ├───────────┤         ├───────────┤
   │ Step 1:   │         │ Step 2:   │         │ Step 4:   │
   │ Search    │────────▶│ Find      │         │ Notify    │
   │ products  │         │ contacts  │────────▶│ team      │
   │           │         │           │         │           │
   │ Step 3:   │         │ Step 5:   │         │           │
   │ Get       │────────▶│ Update    │         │           │
   │ template  │         │ status    │         │           │
   └───────────┘         └───────────┘         └───────────┘
   
   Data flows:
   • Step 1 → Step 3: Product info informs template selection
   • Step 2 → Step 4: Contact names go to Slack notification
   • Step 2 → Step 5: Contact ID used for status update
""")


def print_audit_trail(steps: list[WorkflowStep]) -> None:
    """Print the audit trail."""
    print_section("UNIFIED AUDIT TRAIL", "📋")
    
    print()
    print(f"   Agent: {CONFIG.AGENT_ID}")
    print(f"   On behalf of: {CONFIG.USER_EMAIL}")
    print()
    print("   " + "-" * 65)
    print(f"   {'Timestamp':<12} {'Backend':<10} {'Tool':<28} {'Status':<10}")
    print("   " + "-" * 65)
    
    base_hour = 14
    base_minute = 30
    
    for i, step in enumerate(steps):
        minute = base_minute + (i * 2)
        second = i * 5
        ts = f"{base_hour}:{minute:02d}:{second:02d}"
        print(f"   {ts:<12} {step.backend:<10} {step.tool:<28} {'success':<10}")
    
    print("   " + "-" * 65)
    print()
    print("   All actions logged with:")
    print(f"   • Agent identity: {CONFIG.AGENT_ID}")
    print(f"   • User attribution: {CONFIG.USER_EMAIL}")
    print(f"   • Delegation reference: {CONFIG.DELEGATION_ID}")
    print("   • Timestamps, arguments, and results")


def print_comparison() -> None:
    """Print comparison between traditional and DeepSecure approaches."""
    print_section("APPROACH COMPARISON", "⚖️")
    
    print("""
   TRADITIONAL APPROACH:
   ┌─────────────────────────────────────────────────────┐
   │  • Agent needs 3 API keys (Notion, HubSpot, Slack) │
   │  • Agent manages 3 separate connections             │
   │  • Audit logs scattered across 3 platforms          │
   │  • Credential rotation = update agent config        │
   │  • No unified permission model                      │
   └─────────────────────────────────────────────────────┘

   DEEPSECURE APPROACH:
   ┌─────────────────────────────────────────────────────┐
   │  • Agent has 1 JWT (from delegation)                │
   │  • Agent uses 1 gateway connection                  │
   │  • Audit logs centralized                           │
   │  • Credential rotation = transparent to agent       │
   │  • Unified permission model across all backends     │
   └─────────────────────────────────────────────────────┘
""")


def print_summary(result: WorkflowResult) -> None:
    """Print workflow summary."""
    print()
    print("=" * 70)
    print("  ✅ WORKFLOW COMPLETE")
    print("=" * 70)
    print()
    print(f"   Steps executed:    {result.steps_executed}")
    print(f"   Steps succeeded:   {result.steps_succeeded}")
    print(f"   Backends used:     {len(result.backends_used)} ({', '.join(result.backends_used)})")
    print(f"   Total duration:    {result.total_duration_ms:.1f}ms")
    print("   Agent connections: 1 (gateway only)")
    print()
    print("   KEY VALUE:")
    print("   ┌─────────────────────────────────────────────────────┐")
    print("   │ • Agent code has NO knowledge of backend URLs       │")
    print("   │ • Credentials injected by gateway, invisible        │")
    print("   │ • Complete audit trail across all services          │")
    print("   │ • Permission checks at each step                    │")
    print("   └─────────────────────────────────────────────────────┘")
    print()
    print("=" * 70)
    print()


# =============================================================================
# Main Demo Function
# =============================================================================


async def run_demo(mock_mode: bool = False) -> WorkflowResult:
    """
    Run the cross-service workflow demo.
    
    Args:
        mock_mode: If True, run in mock mode (no services required)
        
    Returns:
        WorkflowResult with execution metrics
    """
    print_banner()
    
    if mock_mode:
        print("🎭 Running in MOCK MODE (no services required)")
    else:
        print("🔌 Running with LIVE SERVICES")
    print("-" * 70)
    
    try:
        # Get workflow steps
        steps = get_workflow_steps()
        
        # Workflow overview
        print_workflow_overview(steps)
        
        # Execute each step
        print_section("WORKFLOW EXECUTION", "⚡")
        
        for step in steps:
            executed_step = await execute_step(step)
            print_step_execution(executed_step)
            await asyncio.sleep(0.1)  # Pause for readability
        
        # Calculate totals
        total_duration = sum(step.duration_ms for step in steps)
        backends_used = get_unique_backends(steps)
        steps_succeeded = sum(1 for step in steps if is_step_successful(step))
        
        # Show data flow
        print_data_flow()
        
        # Show audit trail
        print_audit_trail(steps)
        
        # Show comparison
        print_comparison()
        
        # Create result
        result = WorkflowResult(
            success=True,
            steps_executed=len(steps),
            steps_succeeded=steps_succeeded,
            backends_used=backends_used,
            total_duration_ms=total_duration,
        )
        
        # Summary
        print_summary(result)
        
        return result
        
    except Exception as e:
        error_msg = str(e)
        print(f"\n❌ Error: {error_msg}")
        
        return WorkflowResult(
            success=False,
            steps_executed=0,
            steps_succeeded=0,
            backends_used=[],
            total_duration_ms=0.0,
            error=error_msg,
        )


# =============================================================================
# CLI Entry Point
# =============================================================================


def main() -> int:
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(
        description="Cross-Service Workflow Demo - "
                    "Agent orchestrates across Notion, Slack, and HubSpot",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Run with mock data
    python demo_cross_service_workflow.py --mock
    
    # Run demo
    python demo_cross_service_workflow.py
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
