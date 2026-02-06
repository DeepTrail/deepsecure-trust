# Task: WS-F2 Create Demo 1: Unified MCP Connection

---

## Metadata

| Field | Value |
|-------|-------|
| **Status** | `ready` |
| **Design Doc** | [deepsecure-virtual-mcp-server-mvp.md](../../../design/internal/markdowns/deepsecure-virtual-mcp-server-mvp.md) |
| **Workstream** | WS-F: Integration & Demos |
| **Code Dependencies** | B6 (MCP initialize handler) ✅, D3 (Backend discovery) ✅, D4 (Backend connection pool) ✅ |
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
| B6 | MCP initialize handler for session setup | ✅ |
| D3 | Backend discovery for listing available backends | ✅ |
| D4 | Backend connection pool for tool aggregation | ✅ |

### Runtime Dependencies (must be deployed for integration testing)

| Service | Endpoint | Required For |
|---------|----------|--------------|
| Gateway | `http://localhost:8002` | Demo entry point |
| Control Plane | `http://localhost:8000` | Authentication |
| Mock Notion MCP | `http://localhost:9001` | Backend tools |
| Mock Slack MCP | `http://localhost:9002` | Backend tools |

### Development Mode

When runtime dependencies are unavailable:

- [x] **Fallback behavior**: Demo script can use mocked responses for documentation
- [x] **Local testing**: Unit tests verify demo script structure
- [x] **Integration testing**: Full demo requires all services deployed

---

## Pre-Conditions

Before starting this task, ensure:

- [x] B6, D3, D4 are complete ✅
- [x] Gateway can connect to multiple backends
- [x] Tool aggregation working

---

## Task Description

Create **Demo 1: Unified MCP Connection** - a demonstration script that shows an agent connecting to ONE gateway endpoint and seeing tools from MULTIPLE backend MCP servers.

### Context

From the design doc (Section 5.1):
```python
# Demo script
from mcp_client import MCPClient

client = MCPClient("https://gateway.deeptrail.io/mcp")
client.authenticate(agent_session_jwt)
await client.initialize()

tools = await client.tools_list()
print(f"Connected to 1 server, can access {len(tools)} tools from 2 backends")
# Output: Connected to 1 server, can access 4 tools from 2 backends
```

**Success Criteria**: Agent code has NO awareness of Notion or Slack URLs.

### Technical Notes

The demo should:
1. Be a standalone Python script that can be run independently
2. Include clear console output showing the value proposition
3. Work with the real gateway when deployed
4. Include mock mode for documentation/testing without services

---

## Acceptance Criteria

- [ ] Demo script connects to single gateway endpoint
- [ ] Demo displays tools from multiple backends
- [ ] Demo output clearly shows "1 connection, N tools from M backends"
- [ ] Agent code has no hardcoded backend URLs
- [ ] Demo includes both real and mock modes
- [ ] Demo includes timing/latency measurements
- [ ] README with instructions to run the demo
- [ ] No new linting errors introduced

---

## Files to Modify/Create

### Files to Create

- `deeptrail-gateway/demos/demo_01_unified_connection.py` - Main demo script
- `deeptrail-gateway/demos/__init__.py` - Demo package init
- `deeptrail-gateway/demos/README.md` - Demo instructions

### Files to Modify

- None (new demo directory)

### Tests to Add

- `deeptrail-gateway/tests/demos/test_demo_01.py` - Demo script validation tests

---

## Implementation Details

### Demo Script

```python
#!/usr/bin/env python3
"""
Demo 1: Unified MCP Connection

Demonstrates that an agent connects to ONE gateway endpoint and 
sees tools from MULTIPLE backend MCP servers.

Value Proposition:
- Agent connects to single endpoint (gateway)
- Agent sees tools from Notion, Slack, etc.
- Agent code has NO awareness of backend URLs

Usage:
    # With real services
    python demo_01_unified_connection.py
    
    # With mock mode (no services required)
    python demo_01_unified_connection.py --mock
"""

import asyncio
import argparse
import time
from typing import Optional

# Demo configuration
GATEWAY_URL = "http://localhost:8002/mcp"
CONTROL_PLANE_URL = "http://localhost:8000"


class MCPDemoClient:
    """Simplified MCP client for demos."""
    
    def __init__(self, gateway_url: str, session_token: Optional[str] = None):
        self.gateway_url = gateway_url
        self.session_token = session_token
        self.tools = []
        self.backends = set()
    
    async def connect(self):
        """Connect to the gateway and fetch tools."""
        import httpx
        
        headers = {}
        if self.session_token:
            headers["Authorization"] = f"Bearer {self.session_token}"
        
        async with httpx.AsyncClient() as client:
            # Initialize connection
            start = time.time()
            response = await client.post(
                f"{self.gateway_url}",
                json={
                    "jsonrpc": "2.0",
                    "method": "initialize",
                    "params": {"capabilities": {}},
                    "id": 1
                },
                headers=headers
            )
            init_time = time.time() - start
            
            if response.status_code != 200:
                raise Exception(f"Initialize failed: {response.text}")
            
            # Get tools list
            start = time.time()
            response = await client.post(
                f"{self.gateway_url}",
                json={
                    "jsonrpc": "2.0",
                    "method": "tools/list",
                    "params": {},
                    "id": 2
                },
                headers=headers
            )
            list_time = time.time() - start
            
            if response.status_code != 200:
                raise Exception(f"tools/list failed: {response.text}")
            
            result = response.json()
            self.tools = result.get("result", {}).get("tools", [])
            
            # Extract backend namespaces
            for tool in self.tools:
                name = tool.get("name", "")
                if "." in name:
                    self.backends.add(name.split(".")[0])
            
            return {
                "init_time_ms": init_time * 1000,
                "list_time_ms": list_time * 1000
            }


class MockMCPDemoClient:
    """Mock client for demo without services."""
    
    def __init__(self, gateway_url: str, session_token: Optional[str] = None):
        self.gateway_url = gateway_url
        self.tools = [
            {"name": "notion.search_pages", "description": "Search Notion pages"},
            {"name": "notion.read_page", "description": "Read a Notion page"},
            {"name": "slack.search_messages", "description": "Search Slack messages"},
            {"name": "slack.list_channels", "description": "List Slack channels"},
        ]
        self.backends = {"notion", "slack"}
    
    async def connect(self):
        """Simulate connection."""
        await asyncio.sleep(0.05)  # Simulate latency
        return {
            "init_time_ms": 23.5,
            "list_time_ms": 45.2
        }


def print_banner():
    """Print demo banner."""
    print("\n" + "=" * 70)
    print(" DEMO 1: UNIFIED MCP CONNECTION")
    print("=" * 70)
    print()
    print(" Value Proposition:")
    print(" • Agent connects to ONE endpoint")
    print(" • Agent sees tools from MULTIPLE backends")
    print(" • Agent code has NO awareness of backend URLs")
    print()
    print("-" * 70)


def print_connection_info(client, timings):
    """Print connection information."""
    print("\n📡 CONNECTION ESTABLISHED")
    print("-" * 40)
    print(f"   Gateway URL: {client.gateway_url}")
    print(f"   Initialize:  {timings['init_time_ms']:.1f}ms")
    print(f"   tools/list:  {timings['list_time_ms']:.1f}ms")


def print_tools_summary(client):
    """Print tools summary."""
    print("\n🔧 TOOLS DISCOVERED")
    print("-" * 40)
    print(f"   Total tools:     {len(client.tools)}")
    print(f"   Backend servers: {len(client.backends)}")
    print(f"   Backends:        {', '.join(sorted(client.backends))}")
    
    print("\n   Tool list:")
    for tool in client.tools:
        name = tool.get("name", "unknown")
        desc = tool.get("description", "")[:40]
        print(f"   • {name:<30} {desc}")


def print_value_proposition(client):
    """Print the key value proposition."""
    print("\n" + "=" * 70)
    print(" ✅ KEY INSIGHT")
    print("=" * 70)
    print()
    print(f"   Connected to: 1 server (gateway)")
    print(f"   Can access:   {len(client.tools)} tools from {len(client.backends)} backends")
    print()
    print("   Agent code contains:")
    print(f"   ✓ Gateway URL:  {client.gateway_url}")
    print("   ✗ Notion URL:   (hidden)")
    print("   ✗ Slack URL:    (hidden)")
    print()
    print("   The agent has NO awareness of individual backend URLs!")
    print()
    print("=" * 70)


async def run_demo(mock_mode: bool = False):
    """Run the demo."""
    print_banner()
    
    if mock_mode:
        print("🎭 Running in MOCK MODE (no services required)")
        print("-" * 70)
        client = MockMCPDemoClient(GATEWAY_URL)
    else:
        print("🔌 Connecting to live services...")
        print("-" * 70)
        client = MCPDemoClient(GATEWAY_URL)
    
    try:
        timings = await client.connect()
        print_connection_info(client, timings)
        print_tools_summary(client)
        print_value_proposition(client)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\n   To run without services, use: --mock")
        return 1
    
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Demo 1: Unified MCP Connection"
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Run in mock mode without services"
    )
    parser.add_argument(
        "--gateway",
        default=GATEWAY_URL,
        help=f"Gateway URL (default: {GATEWAY_URL})"
    )
    args = parser.parse_args()
    
    global GATEWAY_URL
    GATEWAY_URL = args.gateway
    
    exit_code = asyncio.run(run_demo(mock_mode=args.mock))
    exit(exit_code)


if __name__ == "__main__":
    main()
```

### Demo README

```markdown
# Virtual MCP Server Demos

This directory contains demonstration scripts that showcase the 
value propositions of the Virtual MCP Server pattern.

## Demo 1: Unified MCP Connection

Shows that an agent connects to ONE gateway and sees tools from 
MULTIPLE backends.

### Running the Demo

**With Mock Mode (no services required):**
```bash
python demo_01_unified_connection.py --mock
```

**With Live Services:**
```bash
# Start services first
docker compose up -d

# Run demo
python demo_01_unified_connection.py
```

### Expected Output

```
======================================================================
 DEMO 1: UNIFIED MCP CONNECTION
======================================================================

 Value Proposition:
 • Agent connects to ONE endpoint
 • Agent sees tools from MULTIPLE backends
 • Agent code has NO awareness of backend URLs

----------------------------------------------------------------------

📡 CONNECTION ESTABLISHED
----------------------------------------
   Gateway URL: http://localhost:8002/mcp
   Initialize:  23.5ms
   tools/list:  45.2ms

🔧 TOOLS DISCOVERED
----------------------------------------
   Total tools:     4
   Backend servers: 2
   Backends:        notion, slack

   Tool list:
   • notion.search_pages              Search Notion pages
   • notion.read_page                 Read a Notion page
   • slack.search_messages            Search Slack messages
   • slack.list_channels              List Slack channels

======================================================================
 ✅ KEY INSIGHT
======================================================================

   Connected to: 1 server (gateway)
   Can access:   4 tools from 2 backends

   Agent code contains:
   ✓ Gateway URL:  http://localhost:8002/mcp
   ✗ Notion URL:   (hidden)
   ✗ Slack URL:    (hidden)

   The agent has NO awareness of individual backend URLs!

======================================================================
```
```

---

## Test Cases

### Unit Tests

```python
# tests/demos/test_demo_01.py

import pytest
import asyncio
from demos.demo_01_unified_connection import MockMCPDemoClient

class TestDemo01:
    
    @pytest.mark.asyncio
    async def test_mock_client_returns_tools(self):
        """Mock client returns expected tools."""
        client = MockMCPDemoClient("http://test:8002/mcp")
        await client.connect()
        
        assert len(client.tools) == 4
        assert len(client.backends) == 2
        assert "notion" in client.backends
        assert "slack" in client.backends
    
    @pytest.mark.asyncio
    async def test_mock_client_returns_timings(self):
        """Mock client returns timing info."""
        client = MockMCPDemoClient("http://test:8002/mcp")
        timings = await client.connect()
        
        assert "init_time_ms" in timings
        assert "list_time_ms" in timings
        assert timings["init_time_ms"] > 0
        assert timings["list_time_ms"] > 0
    
    def test_tools_have_correct_namespace_format(self):
        """Tools follow namespace.action format."""
        client = MockMCPDemoClient("http://test:8002/mcp")
        
        for tool in client.tools:
            name = tool["name"]
            assert "." in name, f"Tool {name} should have namespace prefix"
            namespace, action = name.split(".", 1)
            assert namespace in ["notion", "slack"]
            assert len(action) > 0
```

---

## Post-Conditions

### Code Complete (enables dependent tasks to start)

- [ ] All acceptance criteria met
- [ ] Unit tests pass locally: `pytest deeptrail-gateway/tests/demos/`
- [ ] Demo runs in mock mode
- [ ] Linting passes: `ruff check deeptrail-gateway/`
- [ ] Completion report created

### Integration Complete (validated at merge point)

- [ ] Demo runs with live services
- [ ] Output matches expected format
- [ ] Timings are reasonable (<500ms)

### Unblocks

| Task | Type | Notes |
|------|------|-------|
| - | - | Demo is leaf task |

---

## References

- Design Doc: [Section 5.1 - Demo 1: Unified MCP Connection](../../../design/internal/markdowns/deepsecure-virtual-mcp-server-mvp.md#51-demo-1-unified-mcp-connection)
- Related Code: `deeptrail-gateway/app/mcp/handlers/tools_list.py`

---

## Notes

- Demo should be visually appealing with clear formatting
- Consider adding color output for terminals that support it
- Demo will be used in presentations/documentation

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
