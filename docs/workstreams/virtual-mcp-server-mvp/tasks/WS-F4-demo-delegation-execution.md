# Task: WS-F4 Create Demo 3: Delegation-Based Execution

---

## Metadata

| Field | Value |
|-------|-------|
| **Status** | `ready` |
| **Design Doc** | [deepsecure-virtual-mcp-server-mvp.md](../../../design/internal/markdowns/deepsecure-virtual-mcp-server-mvp.md) |
| **Workstream** | WS-F: Integration & Demos |
| **Code Dependencies** | C7 (Credential injection) ✅ |
| **Runtime Dependencies** | Gateway, Control Plane, Mock Backend MCP Servers |
| **Blocked By** | None |
| **Assigned** | - |
| **Created** | February 6, 2026 |
| **Estimated Complexity** | `M` (2-4 hours) |
| **Batch** | 8 |
| **Target Worktree** | `vmcp-gateway` |

---

## Dependencies

### Code Dependencies (must complete before starting)

| Task | What We Need | Status |
|------|--------------|--------|
| C7 | Credential injection into backend requests | ✅ |

### Runtime Dependencies (must be deployed for integration testing)

| Service | Endpoint | Required For |
|---------|----------|--------------|
| Gateway | `http://localhost:8002` | Demo entry point |
| Control Plane | `http://localhost:8000` | Credential vault |
| Mock Notion MCP | `http://localhost:9001` | Tool execution |

### Development Mode

When runtime dependencies are unavailable:

- [x] **Fallback behavior**: Demo script uses mocked responses
- [x] **Local testing**: Unit tests verify demo script structure
- [x] **Integration testing**: Full demo requires all services

---

## Pre-Conditions

Before starting this task, ensure:

- [x] C7 (Credential injection) is complete ✅
- [x] Credential injection working in tools/call

---

## Task Description

Create **Demo 3: Delegation-Based Execution** - a demonstration script that shows an agent using Sarah's credentials WITHOUT ever seeing them.

### Context

From the design doc (Section 5.3):
```
# Agent calls tool
result = await client.tools_call("notion.search_pages", {"query": "test"})

# In gateway logs:
INFO: Executing notion.search_pages
INFO: Credentials: Using vault://sarah-notion-oauth-xyz
INFO: Agent agent-sdr-001 NEVER sees credential value
INFO: Request forwarded to Notion with Sarah's token
INFO: Action attributed to: agent-sdr-001 on behalf of sarah@acme.com
```

**Success Criteria**: Agent never receives OAuth tokens in response.

### Technical Notes

The demo should:
1. Show the agent making a tool call
2. Display what the gateway is doing behind the scenes
3. Prove that credentials never appear in agent-visible data
4. Show the audit attribution

---

## Acceptance Criteria

- [ ] Demo shows agent making tool call
- [ ] Demo shows credential injection happening (from gateway perspective)
- [ ] Demo proves agent never receives credentials in response
- [ ] Demo shows audit attribution (agent on behalf of user)
- [ ] Includes both real and mock modes
- [ ] Clear side-by-side view of agent vs. gateway perspective
- [ ] No new linting errors introduced

---

## Files to Modify/Create

### Files to Create

- `deeptrail-gateway/demos/demo_03_delegation_execution.py` - Main demo script

### Files to Modify

- `deeptrail-gateway/demos/README.md` - Add Demo 3 instructions

### Tests to Add

- `deeptrail-gateway/tests/demos/test_demo_03.py` - Demo script validation

---

## Implementation Details

### Demo Script

```python
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

Usage:
    python demo_03_delegation_execution.py --mock
"""

import asyncio
import argparse
import json
from datetime import datetime, timezone
from typing import Dict, Any, Optional


class DemoConfig:
    GATEWAY_URL = "http://localhost:8002/mcp"
    AGENT_ID = "agent-sdr-001"
    AGENT_NAME = "SDR-Assistant"
    USER_EMAIL = "sarah@acme.com"
    DELEGATION_ID = "del-sarah-sdr-001"


def print_banner():
    """Print demo banner."""
    print("\n" + "=" * 70)
    print(" DEMO 3: DELEGATION-BASED EXECUTION")
    print("=" * 70)
    print()
    print(" Value Proposition:")
    print(" • Agent calls tools WITHOUT knowing credentials")
    print(" • Gateway securely injects user's OAuth tokens")
    print(" • Agent NEVER sees sensitive credential values")
    print(" • Every action attributed: 'agent on behalf of user'")
    print()
    print("-" * 70)


def print_section(title: str, icon: str = "📋"):
    """Print section header."""
    print(f"\n{icon} {title}")
    print("-" * 50)


def format_json(data: Dict[str, Any], indent: int = 4) -> str:
    """Format JSON with optional credential redaction."""
    return json.dumps(data, indent=indent)


def demo_agent_perspective():
    """Show what the agent sees and does."""
    print_section("AGENT PERSPECTIVE", "🤖")
    
    print("\n   Agent code:")
    print("   " + "-" * 40)
    print("""   # Agent makes a simple tool call
   result = await client.tools_call(
       "notion.search_pages",
       {"query": "sales playbook"}
   )
   
   # Agent sees result
   print(result)  # Page content, no credentials""")
    print("   " + "-" * 40)
    
    print("\n   What agent sends to gateway:")
    agent_request = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {
            "name": "notion.search_pages",
            "arguments": {"query": "sales playbook"}
        },
        "id": 1
    }
    print(f"   {format_json(agent_request)}")
    
    print("\n   ⚠️  NOTE: No credentials in request!")
    print("   The agent has no idea what OAuth token is used.")


def demo_gateway_perspective():
    """Show what the gateway does behind the scenes."""
    print_section("GATEWAY PERSPECTIVE (behind the scenes)", "🔐")
    
    steps = [
        ("1. RECEIVE request from agent",
         "   POST /mcp tools/call notion.search_pages"),
        
        ("2. VALIDATE agent session",
         f"   Agent: {DemoConfig.AGENT_ID}\n"
         f"   Delegation: {DemoConfig.DELEGATION_ID}\n"
         f"   Acting on behalf of: {DemoConfig.USER_EMAIL}"),
        
        ("3. CHECK permission",
         "   Required: notion:pages:search\n"
         "   Delegation grants: [notion:pages:search, ...] ✓ ALLOWED"),
        
        ("4. LOOKUP credentials (from vault)",
         "   Credential ref: vault://sarah-notion-oauth-xyz\n"
         "   Retrieved: Bearer eyJhbGc... [REDACTED]"),
        
        ("5. INJECT credentials into backend request",
         "   POST https://mcp.notion.com/tools/call\n"
         "   Headers:\n"
         "     Authorization: Bearer eyJhbGc... ← Sarah's token\n"
         "     X-DeepSecure-Agent: agent-sdr-001\n"
         "     X-DeepSecure-On-Behalf-Of: sarah@acme.com"),
        
        ("6. FORWARD to backend and get result",
         "   Status: 200 OK\n"
         "   Result: {pages: [...]}"),
        
        ("7. STRIP any credential echoes from response",
         "   Ensure no tokens leak back to agent"),
        
        ("8. LOG audit event",
         f"   {{\"actor\": \"{DemoConfig.AGENT_ID}\",\n"
         f"    \"on_behalf_of\": \"{DemoConfig.USER_EMAIL}\",\n"
         "    \"tool\": \"notion.search_pages\",\n"
         "    \"result\": \"success\"}}")
    ]
    
    for step_title, step_detail in steps:
        print(f"\n   {step_title}")
        for line in step_detail.split('\n'):
            print(f"      {line}")


def demo_agent_receives():
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
                            {"id": "page-456", "title": "Outreach Templates"}
                        ]
                    })
                }
            ]
        },
        "id": 1
    }
    
    print("\n   Response to agent:")
    print(f"   {format_json(response)}")
    
    print("\n   ✓ Contains: search results (page content)")
    print("   ✗ Does NOT contain:")
    print("     • Sarah's OAuth token")
    print("     • Vault reference")
    print("     • Backend URL")
    print("     • Any authentication headers")


def demo_audit_trail():
    """Show the audit trail."""
    print_section("AUDIT TRAIL", "📋")
    
    audit_event = {
        "event_id": "evt-abc123",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": "tools_call",
        "actor": {
            "type": "agent",
            "id": DemoConfig.AGENT_ID,
            "name": DemoConfig.AGENT_NAME
        },
        "on_behalf_of": {
            "type": "user",
            "email": DemoConfig.USER_EMAIL,
            "delegation_id": DemoConfig.DELEGATION_ID
        },
        "action": {
            "tool": "notion.search_pages",
            "backend": "notion",
            "arguments": {"query": "sales playbook"}
        },
        "result": {
            "status": "success",
            "duration_ms": 145
        }
    }
    
    print("\n   Audit event recorded:")
    print(f"   {format_json(audit_event)}")
    
    print("\n   Later, Sarah can ask:")
    print('   "What did my agent do today?"')
    print()
    print("   And see:")
    print(f"   • {DemoConfig.AGENT_NAME} searched Notion for 'sales playbook'")
    print(f"   • Acting as: {DemoConfig.USER_EMAIL}")
    print(f"   • Result: Found 2 pages")


def print_summary():
    """Print demo summary."""
    print("\n" + "=" * 70)
    print(" ✅ KEY INSIGHTS")
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
    print("   4. SECURITY COMPARISON")
    print("      ┌─────────────────────────────────────────────────────┐")
    print("      │ Traditional:  Agent has API key → Can do anything  │")
    print("      │ DeepSecure:   Agent has delegation → Bounded scope │")
    print("      └─────────────────────────────────────────────────────┘")
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
    
    # Demo sections
    demo_agent_perspective()
    demo_gateway_perspective()
    demo_agent_receives()
    demo_audit_trail()
    print_summary()
    
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Demo 3: Delegation-Based Execution"
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
# tests/demos/test_demo_03.py

import pytest
from demos.demo_03_delegation_execution import DemoConfig

class TestDemo03:
    
    def test_config_has_agent_id(self):
        """Config has agent ID."""
        assert DemoConfig.AGENT_ID == "agent-sdr-001"
    
    def test_config_has_user_email(self):
        """Config has user email."""
        assert DemoConfig.USER_EMAIL == "sarah@acme.com"
    
    def test_config_has_delegation_id(self):
        """Config has delegation ID."""
        assert DemoConfig.DELEGATION_ID == "del-sarah-sdr-001"
    
    def test_demo_runs_without_error(self):
        """Demo script runs without errors."""
        import asyncio
        from demos.demo_03_delegation_execution import run_demo
        
        # Should not raise
        exit_code = asyncio.run(run_demo(mock_mode=True))
        assert exit_code == 0
```

---

## Post-Conditions

### Code Complete (enables dependent tasks to start)

- [ ] All acceptance criteria met
- [ ] Unit tests pass locally: `pytest deeptrail-gateway/tests/demos/`
- [ ] Demo runs in mock mode
- [ ] Completion report created

### Integration Complete (validated at merge point)

- [ ] Demo runs with live services
- [ ] Gateway logs match expected output

### Unblocks

| Task | Type | Notes |
|------|------|-------|
| - | - | Demo is leaf task |

---

## References

- Design Doc: [Section 5.3 - Demo 3: Delegation-Based Execution](../../../design/internal/markdowns/deepsecure-virtual-mcp-server-mvp.md#53-demo-3-delegation-based-execution)
- Related Code: `deeptrail-gateway/app/middleware/credential_injection.py`

---

## Notes

- This demo is critical for explaining the core security model
- The side-by-side agent vs. gateway view is key to understanding
- Consider adding diagram or animation in presentation version

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
