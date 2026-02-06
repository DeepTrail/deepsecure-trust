# Task: WS-F5 Create Demo 4: Permission Enforcement

---

## Metadata

| Field | Value |
|-------|-------|
| **Status** | `ready` |
| **Design Doc** | [deepsecure-virtual-mcp-server-mvp.md](../../../design/internal/markdowns/deepsecure-virtual-mcp-server-mvp.md) |
| **Workstream** | WS-F: Integration & Demos |
| **Code Dependencies** | C6 (Delegation validator) ✅ |
| **Runtime Dependencies** | Gateway, Control Plane, Mock Backend MCP Servers |
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
| C6 | Delegation validator for permission checking | ✅ |

### Runtime Dependencies (must be deployed for integration testing)

| Service | Endpoint | Required For |
|---------|----------|--------------|
| Gateway | `http://localhost:8002` | Demo entry point |
| Control Plane | `http://localhost:8000` | Delegation info |
| Mock Notion MCP | `http://localhost:9001` | Backend to NOT receive unauthorized calls |

### Development Mode

When runtime dependencies are unavailable:

- [x] **Fallback behavior**: Demo script uses mocked responses
- [x] **Local testing**: Unit tests verify demo script structure
- [x] **Integration testing**: Full demo requires all services

---

## Pre-Conditions

Before starting this task, ensure:

- [x] C6 (Delegation validator) is complete ✅
- [x] Permission checking is working in tools/call

---

## Task Description

Create **Demo 4: Permission Enforcement** - a demonstration script that shows unauthorized tools are blocked at the gateway and NEVER reach the backend.

### Context

From the design doc (Section 5.4):
```python
# Agent tries unauthorized action
try:
    await client.tools_call("notion.create_page", {"title": "test"})
except MCPError as e:
    print(e)
# Output: MCPError(-32001): Permission denied: notion:pages:create not delegated

# Verify: Check Notion audit logs - NO request reached Notion
```

**Success Criteria**: Backend sees ZERO unauthorized requests.

### Technical Notes

The demo should:
1. Show an agent with limited permissions
2. Attempt both authorized and unauthorized actions
3. Prove unauthorized calls are blocked at gateway
4. Verify backend received ZERO unauthorized requests (via mock server logs)

---

## Acceptance Criteria

- [ ] Demo shows authorized tool call succeeds
- [ ] Demo shows unauthorized tool call is blocked
- [ ] Demo proves backend never received unauthorized request
- [ ] Error message clearly indicates permission denied
- [ ] Includes both real and mock modes
- [ ] Backend request log verification
- [ ] No new linting errors introduced

---

## Files to Modify/Create

### Files to Create

- `deeptrail-gateway/demos/demo_04_permission_enforcement.py` - Main demo script

### Files to Modify

- `deeptrail-gateway/demos/README.md` - Add Demo 4 instructions

### Tests to Add

- `deeptrail-gateway/tests/demos/test_demo_04.py` - Demo script validation

---

## Implementation Details

### Demo Script

```python
#!/usr/bin/env python3
"""
Demo 4: Permission Enforcement

Demonstrates that unauthorized tools are BLOCKED at the gateway
and NEVER reach the backend MCP server.

Value Proposition:
- Agent can only use delegated tools
- Unauthorized requests blocked immediately
- Backend sees ZERO unauthorized requests
- Zero-trust security model

Usage:
    python demo_04_permission_enforcement.py --mock
"""

import asyncio
import argparse
from typing import Dict, List, Any
from dataclasses import dataclass, field


@dataclass
class MockBackendLog:
    """Simulates backend request logging."""
    requests_received: List[Dict[str, Any]] = field(default_factory=list)
    
    def log_request(self, tool: str, arguments: Dict):
        self.requests_received.append({
            "tool": tool,
            "arguments": arguments
        })
    
    def get_requests_for_tool(self, tool: str) -> List[Dict]:
        return [r for r in self.requests_received if r["tool"] == tool]


# Demo configuration
GATEWAY_URL = "http://localhost:8002/mcp"
AGENT_ID = "agent-sdr-001"

# Sarah's delegated permissions (limited set)
DELEGATED_PERMISSIONS = [
    "notion:pages:search",   # ✓ Can search
    "notion:pages:read",     # ✓ Can read
    # notion:pages:create    ✗ NOT delegated
    # notion:pages:delete    ✗ NOT delegated
    "slack:messages:search", # ✓ Can search
    "slack:channels:list",   # ✓ Can list
]

# Tool to permission mapping
TOOL_PERMISSIONS = {
    "notion.search_pages": "notion:pages:search",
    "notion.read_page": "notion:pages:read",
    "notion.create_page": "notion:pages:create",
    "notion.delete_page": "notion:pages:delete",
    "slack.search_messages": "slack:messages:search",
    "slack.list_channels": "slack:channels:list",
    "slack.send_message": "slack:messages:send",
}


def print_banner():
    """Print demo banner."""
    print("\n" + "=" * 70)
    print(" DEMO 4: PERMISSION ENFORCEMENT")
    print("=" * 70)
    print()
    print(" Value Proposition:")
    print(" • Agent can ONLY call delegated tools")
    print(" • Unauthorized requests BLOCKED at gateway")
    print(" • Backend receives ZERO unauthorized requests")
    print(" • Zero-trust security model in action")
    print()
    print("-" * 70)


def print_section(title: str, icon: str = "📋"):
    """Print section header."""
    print(f"\n{icon} {title}")
    print("-" * 50)


def print_permissions():
    """Print Sarah's delegated permissions."""
    print_section("SARAH'S DELEGATED PERMISSIONS", "🔐")
    
    print("\n   Delegated (agent can use):")
    for perm in DELEGATED_PERMISSIONS:
        print(f"   ✓ {perm}")
    
    print("\n   NOT Delegated (agent cannot use):")
    not_delegated = [
        "notion:pages:create",
        "notion:pages:delete",
        "slack:messages:send",
    ]
    for perm in not_delegated:
        print(f"   ✗ {perm}")


def simulate_authorized_call(backend_log: MockBackendLog):
    """Simulate an authorized tool call."""
    print_section("AUTHORIZED CALL: notion.search_pages", "✅")
    
    tool = "notion.search_pages"
    permission = TOOL_PERMISSIONS[tool]
    
    print(f"\n   Agent calls: {tool}")
    print(f"   Required permission: {permission}")
    print(f"   Delegated: {'✓ YES' if permission in DELEGATED_PERMISSIONS else '✗ NO'}")
    
    print("\n   Gateway processing:")
    print("   1. ✓ JWT validated")
    print("   2. ✓ Agent session found")
    print("   3. ✓ Delegation active")
    print(f"   4. ✓ Permission check: {permission} in delegation")
    print("   5. ✓ Request forwarded to Notion backend")
    
    # Log to backend
    backend_log.log_request(tool, {"query": "sales playbook"})
    
    print("\n   Backend response:")
    print("   { \"pages\": [{\"id\": \"page-123\", \"title\": \"Sales Playbook\"}] }")
    
    print("\n   Result: ✅ SUCCESS")


def simulate_unauthorized_call(backend_log: MockBackendLog):
    """Simulate an unauthorized tool call."""
    print_section("UNAUTHORIZED CALL: notion.create_page", "🚫")
    
    tool = "notion.create_page"
    permission = TOOL_PERMISSIONS[tool]
    
    print(f"\n   Agent calls: {tool}")
    print(f"   Required permission: {permission}")
    print(f"   Delegated: {'✓ YES' if permission in DELEGATED_PERMISSIONS else '✗ NO'}")
    
    print("\n   Gateway processing:")
    print("   1. ✓ JWT validated")
    print("   2. ✓ Agent session found")
    print("   3. ✓ Delegation active")
    print(f"   4. ✗ Permission check: {permission} NOT in delegation")
    print("   5. ❌ REQUEST BLOCKED - NOT forwarded to backend")
    
    # NOT logged to backend - request never reaches it
    # backend_log.log_request(tool, ...)  # This line intentionally not called
    
    print("\n   Error response to agent:")
    print("   {")
    print('     "error": {')
    print('       "code": -32001,')
    print(f'       "message": "Permission denied: {permission} not delegated"')
    print("     }")
    print("   }")
    
    print("\n   Result: 🚫 BLOCKED AT GATEWAY")


def verify_backend_logs(backend_log: MockBackendLog):
    """Verify what the backend actually received."""
    print_section("BACKEND REQUEST LOG VERIFICATION", "🔍")
    
    print("\n   Notion Backend received these requests:")
    print("-" * 50)
    
    all_requests = backend_log.requests_received
    
    if all_requests:
        for req in all_requests:
            print(f"   • {req['tool']} - args: {req['arguments']}")
    else:
        print("   (no requests)")
    
    print()
    
    # Check for unauthorized requests
    unauthorized_tools = ["notion.create_page", "notion.delete_page"]
    unauthorized_received = []
    
    for tool in unauthorized_tools:
        reqs = backend_log.get_requests_for_tool(tool)
        if reqs:
            unauthorized_received.extend(reqs)
    
    print("   Unauthorized requests received by backend:")
    if unauthorized_received:
        for req in unauthorized_received:
            print(f"   ⚠️  {req['tool']} - SECURITY VIOLATION!")
    else:
        print("   ✅ ZERO - Backend never saw unauthorized requests")


def print_summary():
    """Print demo summary."""
    print("\n" + "=" * 70)
    print(" ✅ KEY INSIGHTS")
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
    print("   4. DEFENSE IN DEPTH")
    print("      ┌─────────────────────────────────────────────────────┐")
    print("      │ Layer 1: JWT validation (is request authentic?)     │")
    print("      │ Layer 2: Session check (is agent session valid?)    │")
    print("      │ Layer 3: Delegation check (does user consent?)      │")
    print("      │ Layer 4: Permission check (is action delegated?)    │")
    print("      │ ───────────────────────────────────────────────── │")
    print("      │ Only after ALL checks pass → forward to backend    │")
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
    
    # Create mock backend log to track requests
    backend_log = MockBackendLog()
    
    # Show permissions
    print_permissions()
    
    # Simulate authorized call
    simulate_authorized_call(backend_log)
    
    # Simulate unauthorized call
    simulate_unauthorized_call(backend_log)
    
    # Verify backend logs
    verify_backend_logs(backend_log)
    
    # Summary
    print_summary()
    
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Demo 4: Permission Enforcement"
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
# tests/demos/test_demo_04.py

import pytest
from demos.demo_04_permission_enforcement import (
    MockBackendLog,
    DELEGATED_PERMISSIONS,
    TOOL_PERMISSIONS
)

class TestDemo04:
    
    def test_mock_backend_log_records_requests(self):
        """Backend log records requests correctly."""
        log = MockBackendLog()
        log.log_request("notion.search_pages", {"query": "test"})
        
        assert len(log.requests_received) == 1
        assert log.requests_received[0]["tool"] == "notion.search_pages"
    
    def test_mock_backend_log_filters_by_tool(self):
        """Backend log filters by tool name."""
        log = MockBackendLog()
        log.log_request("notion.search_pages", {})
        log.log_request("slack.list_channels", {})
        
        notion_reqs = log.get_requests_for_tool("notion.search_pages")
        assert len(notion_reqs) == 1
    
    def test_authorized_tools_have_permissions(self):
        """Authorized tools map to delegated permissions."""
        authorized_tools = ["notion.search_pages", "notion.read_page"]
        
        for tool in authorized_tools:
            permission = TOOL_PERMISSIONS[tool]
            assert permission in DELEGATED_PERMISSIONS
    
    def test_unauthorized_tools_lack_permissions(self):
        """Unauthorized tools map to non-delegated permissions."""
        unauthorized_tools = ["notion.create_page", "notion.delete_page"]
        
        for tool in unauthorized_tools:
            permission = TOOL_PERMISSIONS[tool]
            assert permission not in DELEGATED_PERMISSIONS
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
- [ ] Backend logs confirm zero unauthorized requests

### Unblocks

| Task | Type | Notes |
|------|------|-------|
| - | - | Demo is leaf task |

---

## References

- Design Doc: [Section 5.4 - Demo 4: Permission Enforcement](../../../design/internal/markdowns/deepsecure-virtual-mcp-server-mvp.md#54-demo-4-permission-enforcement)
- Related Code: `deeptrail-gateway/app/middleware/delegation.py`

---

## Notes

- This demo proves the zero-trust model works
- Backend receiving zero unauthorized requests is the key metric
- Consider adding a real backend request counter for live demos

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
