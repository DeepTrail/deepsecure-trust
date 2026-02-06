# Task: WS-F8 Create Cross-Service Workflow Demo

---

## Metadata

| Field | Value |
|-------|-------|
| **Status** | `ready` |
| **Design Doc** | [deepsecure-virtual-mcp-server-mvp.md](../../../design/internal/markdowns/deepsecure-virtual-mcp-server-mvp.md) |
| **Workstream** | WS-F: Integration & Demos |
| **Code Dependencies** | D5 (Tool namespace prefixing) ✅, F1 (Sarah's Journey E2E) ✅ |
| **Runtime Dependencies** | Gateway, Control Plane, Mock Notion, Mock Slack, Mock HubSpot |
| **Blocked By** | None |
| **Assigned** | - |
| **Created** | February 6, 2026 |
| **Estimated Complexity** | `L` (4+ hours) |
| **Batch** | 9 |
| **Target Worktree** | `vmcp-gateway` |

---

## Dependencies

### Code Dependencies (must complete before starting)

| Task | What We Need | Status |
|------|--------------|--------|
| D5 | Tool namespace prefixing for cross-backend calls | ✅ |
| F1 | Sarah's Journey E2E as reference pattern | ✅ |

### Runtime Dependencies (must be deployed for integration testing)

| Service | Endpoint | Required For |
|---------|----------|--------------|
| Gateway | `http://localhost:8002` | Demo entry point |
| Control Plane | `http://localhost:8000` | Auth and audit |
| Mock Notion MCP | `http://localhost:9001` | Knowledge base |
| Mock Slack MCP | `http://localhost:9002` | Communication |
| Mock HubSpot MCP | `http://localhost:9003` | CRM data |

### Development Mode

When runtime dependencies are unavailable:

- [x] **Fallback behavior**: Demo uses mocked responses
- [x] **Local testing**: Unit tests verify demo script structure
- [x] **Integration testing**: Full demo requires all services

---

## Pre-Conditions

Before starting this task, ensure:

- [x] D5 (Tool namespace prefixing) is complete ✅
- [x] F1 (Sarah's Journey E2E) is complete ✅
- [x] All 3 mock backends are configured

---

## Task Description

Create a **Cross-Service Workflow Demo** that shows an agent orchestrating actions across multiple backend MCP servers (Notion, Slack, HubSpot) in a realistic business workflow.

### Context

From the design doc (Section 3 - Phase 2):
> **Cross-service workflow** | Agent uses Notion research + HubSpot CRM

This demo shows the "killer feature" of the Virtual MCP Server - an agent seamlessly using tools from multiple backends in a single workflow, with:
- Unified authentication
- Cross-service data flow
- Complete audit trail

### Example Workflow

"Sales Research and Outreach":
1. **Notion**: Search for product information
2. **HubSpot**: Find relevant contacts
3. **Notion**: Get outreach templates
4. **Slack**: Notify SDR team about opportunity
5. **HubSpot**: Update contact status

---

## Acceptance Criteria

- [ ] Demo shows multi-backend workflow (3+ backends)
- [ ] Demo uses namespaced tools (notion.X, slack.Y, hubspot.Z)
- [ ] Demo shows data flowing between backends
- [ ] Demo shows complete audit trail
- [ ] Workflow is realistic business scenario
- [ ] Includes both real and mock modes
- [ ] No new linting errors introduced

---

## Files to Modify/Create

### Files to Create

- `deeptrail-gateway/demos/demo_cross_service_workflow.py` - Main demo script

### Files to Modify

- `deeptrail-gateway/demos/README.md` - Add workflow demo instructions

### Tests to Add

- `deeptrail-gateway/tests/demos/test_demo_cross_service.py` - Demo validation

---

## Implementation Details

### Demo Script

```python
#!/usr/bin/env python3
"""
Cross-Service Workflow Demo

Demonstrates an agent orchestrating actions across multiple
backend MCP servers in a realistic business workflow.

Workflow: "Sales Research and Outreach"
1. Search Notion for product info
2. Find relevant contacts in HubSpot
3. Get outreach templates from Notion
4. Send notification to Slack
5. Update contact status in HubSpot

Usage:
    python demo_cross_service_workflow.py --mock
"""

import asyncio
import argparse
import time
from datetime import datetime
from typing import List, Dict, Any
from dataclasses import dataclass, field


@dataclass
class WorkflowStep:
    """Represents a step in the workflow."""
    step_num: int
    backend: str
    tool: str
    description: str
    arguments: Dict[str, Any]
    result: Dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0
    status: str = "pending"


# Demo configuration
GATEWAY_URL = "http://localhost:8002/mcp"
AGENT_ID = "agent-sdr-001"
USER_EMAIL = "sarah@acme.com"

# Workflow steps
WORKFLOW_STEPS = [
    WorkflowStep(
        step_num=1,
        backend="notion",
        tool="notion.search_pages",
        description="Search for product information",
        arguments={"query": "Enterprise AI Security Features"},
        result={"pages": [{"id": "page-123", "title": "DeepSecure Product Overview"}]}
    ),
    WorkflowStep(
        step_num=2,
        backend="hubspot",
        tool="hubspot.search_contacts",
        description="Find relevant contacts interested in AI security",
        arguments={"query": "AI security", "industry": "fintech"},
        result={"contacts": [
            {"id": "contact-456", "name": "John Smith", "company": "FinBank Inc"},
            {"id": "contact-789", "name": "Jane Doe", "company": "SecureFinance"}
        ]}
    ),
    WorkflowStep(
        step_num=3,
        backend="notion",
        tool="notion.read_page",
        description="Get outreach email template",
        arguments={"page_id": "template-outreach-001"},
        result={"content": "Hi {name}, I noticed {company} is exploring AI security..."}
    ),
    WorkflowStep(
        step_num=4,
        backend="slack",
        tool="slack.send_message",
        description="Notify SDR team about hot leads",
        arguments={
            "channel": "#sdr-team",
            "message": "🎯 Found 2 hot leads for AI Security: John Smith (FinBank), Jane Doe (SecureFinance)"
        },
        result={"message_id": "msg-12345", "timestamp": "2026-02-06T14:30:00Z"}
    ),
    WorkflowStep(
        step_num=5,
        backend="hubspot",
        tool="hubspot.update_contact",
        description="Update contact status to 'Contacted'",
        arguments={"contact_id": "contact-456", "status": "Contacted", "notes": "AI security outreach"},
        result={"success": True, "updated_at": "2026-02-06T14:30:05Z"}
    ),
]


def print_banner():
    """Print demo banner."""
    print("\n" + "=" * 70)
    print(" CROSS-SERVICE WORKFLOW DEMO")
    print("=" * 70)
    print()
    print(" Workflow: Sales Research and Outreach")
    print()
    print(" Backend Services Used:")
    print(" • Notion  - Knowledge base, templates")
    print(" • HubSpot - CRM, contact management")
    print(" • Slack   - Team communication")
    print()
    print(" Value Proposition:")
    print(" • Single agent connection to gateway")
    print(" • Seamless cross-backend data flow")
    print(" • Unified audit trail")
    print()
    print("-" * 70)


def print_section(title: str, icon: str = "📋"):
    """Print section header."""
    print(f"\n{icon} {title}")
    print("-" * 50)


def print_workflow_overview():
    """Print workflow overview."""
    print_section("WORKFLOW OVERVIEW", "📊")
    
    print("\n   " + "=" * 50)
    print("   SALES RESEARCH AND OUTREACH WORKFLOW")
    print("   " + "=" * 50)
    
    for step in WORKFLOW_STEPS:
        backend_icon = {"notion": "📝", "hubspot": "💼", "slack": "💬"}.get(step.backend, "🔧")
        print(f"   {step.step_num}. [{backend_icon} {step.backend.upper()}] {step.description}")
    
    print("   " + "=" * 50)


def execute_step(step: WorkflowStep) -> WorkflowStep:
    """Execute a workflow step (simulated)."""
    start_time = time.time()
    
    # Simulate execution
    import asyncio
    asyncio.get_event_loop().run_until_complete(asyncio.sleep(0.05))
    
    step.duration_ms = (time.time() - start_time) * 1000
    step.status = "success"
    
    return step


def print_step_execution(step: WorkflowStep):
    """Print step execution details."""
    backend_icon = {"notion": "📝", "hubspot": "💼", "slack": "💬"}.get(step.backend, "🔧")
    
    print(f"\n   ─────────────────────────────────────────────────")
    print(f"   STEP {step.step_num}: {step.description}")
    print(f"   ─────────────────────────────────────────────────")
    print(f"   Backend: {backend_icon} {step.backend.upper()}")
    print(f"   Tool:    {step.tool}")
    print(f"   Args:    {step.arguments}")
    print(f"   Duration: {step.duration_ms:.1f}ms")
    print(f"   Status:  ✅ {step.status.upper()}")
    print(f"   Result:  {step.result}")


def print_data_flow():
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


def print_audit_trail():
    """Print the audit trail."""
    print_section("UNIFIED AUDIT TRAIL", "📋")
    
    print(f"\n   Agent: {AGENT_ID}")
    print(f"   On behalf of: {USER_EMAIL}")
    print()
    print("   " + "-" * 60)
    print(f"   {'Timestamp':<12} {'Backend':<10} {'Tool':<25} {'Status':<10}")
    print("   " + "-" * 60)
    
    base_time = datetime.now()
    for i, step in enumerate(WORKFLOW_STEPS):
        ts = f"{14 + i // 60}:{30 + (i % 60) * 5:02d}:{i * 2:02d}"
        print(f"   {ts:<12} {step.backend:<10} {step.tool:<25} {'success':<10}")
    
    print("   " + "-" * 60)
    print()
    print("   All actions logged with:")
    print(f"   • Agent identity: {AGENT_ID}")
    print(f"   • User attribution: {USER_EMAIL}")
    print("   • Delegation reference: del-sarah-sdr-001")
    print("   • Timestamps, arguments, and results")


def print_summary():
    """Print demo summary."""
    total_duration = sum(step.duration_ms for step in WORKFLOW_STEPS)
    backends_used = set(step.backend for step in WORKFLOW_STEPS)
    
    print("\n" + "=" * 70)
    print(" ✅ WORKFLOW COMPLETE")
    print("=" * 70)
    print()
    print(f"   Steps executed:    {len(WORKFLOW_STEPS)}")
    print(f"   Backends used:     {len(backends_used)} ({', '.join(backends_used)})")
    print(f"   Total duration:    {total_duration:.1f}ms")
    print(f"   Agent connections: 1 (gateway only)")
    print()
    print("   KEY VALUE:")
    print("   ┌─────────────────────────────────────────────────────┐")
    print("   │ • Agent code has NO knowledge of backend URLs       │")
    print("   │ • Credentials injected by gateway, invisible        │")
    print("   │ • Complete audit trail across all services          │")
    print("   │ • Permission checks at each step                    │")
    print("   └─────────────────────────────────────────────────────┘")
    print()
    print("   TRADITIONAL APPROACH:")
    print("   • Agent needs 3 API keys (Notion, HubSpot, Slack)")
    print("   • Agent manages 3 separate connections")
    print("   • Audit logs scattered across 3 platforms")
    print("   • Credential rotation = update agent config")
    print()
    print("   DEEPSECURE APPROACH:")
    print("   • Agent has 1 JWT (from delegation)")
    print("   • Agent uses 1 gateway connection")
    print("   • Audit logs centralized")
    print("   • Credential rotation = transparent to agent")
    print()
    print("=" * 70)


async def run_demo(mock_mode: bool = False):
    """Run the demo."""
    print_banner()
    
    if mock_mode:
        print("🎭 Running in MOCK MODE")
    else:
        print("🔌 Running with LIVE SERVICES")
    print("-" * 70)
    
    # Workflow overview
    print_workflow_overview()
    
    # Execute each step
    print_section("WORKFLOW EXECUTION", "⚡")
    
    for step in WORKFLOW_STEPS:
        executed_step = execute_step(step)
        print_step_execution(executed_step)
        await asyncio.sleep(0.2)  # Pause for readability
    
    # Show data flow
    print_data_flow()
    
    # Show audit trail
    print_audit_trail()
    
    # Summary
    print_summary()
    
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Cross-Service Workflow Demo"
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
# tests/demos/test_demo_cross_service.py

import pytest
from demos.demo_cross_service_workflow import (
    WORKFLOW_STEPS,
    WorkflowStep,
    execute_step
)

class TestCrossServiceDemo:
    
    def test_workflow_has_multiple_backends(self):
        """Workflow uses multiple backends."""
        backends = set(step.backend for step in WORKFLOW_STEPS)
        assert len(backends) >= 3
        assert "notion" in backends
        assert "hubspot" in backends
        assert "slack" in backends
    
    def test_workflow_steps_have_required_fields(self):
        """All steps have required fields."""
        for step in WORKFLOW_STEPS:
            assert step.step_num > 0
            assert step.backend is not None
            assert step.tool is not None
            assert step.description is not None
    
    def test_tools_are_namespaced(self):
        """Tools follow namespace.action pattern."""
        for step in WORKFLOW_STEPS:
            assert "." in step.tool
            namespace, action = step.tool.split(".", 1)
            assert namespace == step.backend
    
    def test_execute_step_sets_status(self):
        """Executing step sets success status."""
        step = WorkflowStep(
            step_num=1,
            backend="test",
            tool="test.action",
            description="Test step",
            arguments={}
        )
        
        result = execute_step(step)
        assert result.status == "success"
        assert result.duration_ms > 0
```

---

## Post-Conditions

### Code Complete (enables dependent tasks to start)

- [ ] All acceptance criteria met
- [ ] Unit tests pass locally: `pytest deeptrail-gateway/tests/demos/`
- [ ] Demo runs in mock mode
- [ ] Completion report created

### Integration Complete (validated at merge point)

- [ ] Demo runs with all 3 backend services
- [ ] Complete workflow executes successfully

### Unblocks

| Task | Type | Notes |
|------|------|-------|
| - | - | Demo is final task - MVP COMPLETE! |

---

## References

- Design Doc: [Section 3 - Phase 2](../../../design/internal/markdowns/deepsecure-virtual-mcp-server-mvp.md#3-sarahs-journey-phase-2-adding-hubspot)
- Related Code: F1 (Sarah's Journey E2E test)
- Related Code: D5 (Tool namespace prefixing)

---

## Notes

- This is the "killer demo" showing the power of Virtual MCP Server
- Should be impressive and easy to understand
- Consider adding ASCII art or color output for presentations
- This is the last task - completing it means MVP is done!

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
