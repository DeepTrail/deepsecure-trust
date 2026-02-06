# Virtual MCP Server Demos

This directory contains demonstration scripts that showcase the value propositions of the Virtual MCP Server pattern.

## Overview

The Virtual MCP Server Gateway provides a unified interface for AI agents to access multiple backend MCP servers. These demos illustrate the key benefits:

| Demo | Title | Key Value |
|------|-------|-----------|
| 1 | Unified Connection | One gateway, multiple backends |
| 2 | Filtered Visibility | Agents see only delegated tools |
| 3 | Delegation Execution | Agent acts on behalf of user |
| 4 | Permission Enforcement | Unauthorized tools rejected |
| 5 | Unified Audit | All actions logged under agent identity |
| 6 | Fail-Closed Security | Secure handling of failures |

## Prerequisites

### For Mock Mode (No Services Required)

```bash
# Just run any demo with --mock flag
python demo_01_unified_connection.py --mock
```

### For Live Mode (All Services Required)

```bash
# Start all services
docker compose up -d

# Verify services are running
curl http://localhost:8000/health  # Control Plane
curl http://localhost:8002/health  # Gateway
```

## Demo 1: Unified MCP Connection

**Value Proposition**: Agent connects to ONE endpoint and sees tools from MULTIPLE backends.

### Running the Demo

```bash
# Mock mode (no services required)
python demo_01_unified_connection.py --mock

# Live mode
python demo_01_unified_connection.py

# Custom gateway
python demo_01_unified_connection.py --gateway http://custom-gateway:8002/mcp
```

### What It Demonstrates

1. **Single Connection Point**: Agent connects to one gateway URL
2. **Multiple Backends**: Tools from Notion, Slack, HubSpot are visible
3. **Hidden Complexity**: Agent code has NO awareness of backend URLs

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
🎭 Running in MOCK MODE (no services required)
----------------------------------------------------------------------

📡 CONNECTION ESTABLISHED
----------------------------------------
   Gateway URL:    http://localhost:8002/mcp
   Initialize:     23.5ms
   tools/list:     45.2ms
   Total time:     68.7ms

🔧 TOOLS DISCOVERED
----------------------------------------
   Total tools:      6
   Backend servers:  3
   Backends:         hubspot, notion, slack

   Tool list:
   • notion.search_pages              [Notion] Search pages in your w...
   • notion.read_page                 [Notion] Read page content by ID
   • slack.search_messages            [Slack] Search messages in chan...
   • slack.list_channels              [Slack] List accessible channels
   • hubspot.search_contacts          [HubSpot] Search contacts in CRM
   • hubspot.list_deals               [HubSpot] List deals from CRM

======================================================================
  ✅ KEY INSIGHT
======================================================================

   Connected to: 1 server (gateway)
   Can access:   6 tools from 3 backends

   Agent code contains:
   ✓ Gateway URL:  http://localhost:8002/mcp
   ✗ Hubspot URL:   (hidden from agent)
   ✗ Notion URL:   (hidden from agent)
   ✗ Slack URL:    (hidden from agent)

   The agent has NO awareness of individual backend URLs!

======================================================================
```

## Demo 2: Filtered Tool Visibility

**Value Proposition**: Agents see ONLY the tools delegated to them, not all backend tools.

### Running the Demo

```bash
# Mock mode (no services required)
python demo_02_filtered_visibility.py --mock

# Live mode (uses same mock data for visualization)
python demo_02_filtered_visibility.py
```

### What It Demonstrates

1. **Backend Catalogs**: Shows all 37 tools offered by Notion (15) and Slack (22)
2. **Permission Filtering**: Only 4 tools are visible based on Sarah's delegation
3. **Attack Surface Reduction**: 89%+ reduction in accessible functionality

### Expected Output

```
======================================================================
  DEMO 2: FILTERED TOOL VISIBILITY
======================================================================

  Value Proposition:
  • Backends offer MANY tools (dangerous capabilities)
  • Agent sees ONLY delegated tools (safe subset)
  • Massive reduction in attack surface

----------------------------------------------------------------------
🎭 Running in MOCK MODE (no services required)
----------------------------------------------------------------------

📦 ALL TOOLS OFFERED BY BACKENDS
--------------------------------------------------

   Notion MCP Server (15 tools):
   • notion.search_pages             → notion:pages:search
   • notion.read_page                → notion:pages:read
   ... (13 more tools)

   Slack MCP Server (22 tools):
   • slack.search_messages           → slack:messages:search
   • slack.list_channels             → slack:channels:list
   ... (20 more tools)

   TOTAL: 37 tools available across all backends

🔐 SARAH'S DELEGATED PERMISSIONS
--------------------------------------------------
   Sarah delegated these permissions to her agent:

   ✓ notion:pages:search
   ✓ notion:pages:read
   ✓ slack:messages:search
   ✓ slack:channels:list

   Total delegated: 4 permissions

👁️  TOOLS VISIBLE TO AGENT (after filtering)
--------------------------------------------------

   Agent's tools/list response:
   ✓ notion.search_pages             (allowed: notion:pages:search)
   ✓ notion.read_page                (allowed: notion:pages:read)
   ✓ slack.search_messages           (allowed: slack:messages:search)
   ✓ slack.list_channels             (allowed: slack:channels:list)

   VISIBLE: 4 tools

======================================================================
  ✅ FILTERING SUMMARY
======================================================================

   Backends offer:     37 tools
   Agent sees:          4 tools
   Hidden from agent:  33 tools

   📉 Attack surface reduction: 89.2%

   ┌─────────────────────────────────────────────────────────────┐
   │  KEY INSIGHT                                                │
   │                                                             │
   │  The agent CANNOT discover or call hidden tools.            │
   │  They simply don't exist from the agent's perspective.      │
   └─────────────────────────────────────────────────────────────┘

======================================================================
```

## Demo 3: Delegation-Based Execution

**Value Proposition**: Agent uses Sarah's credentials WITHOUT ever seeing them.

### Running the Demo

```bash
# Mock mode (no services required)
python demo_03_delegation_execution.py --mock

# Live mode
python demo_03_delegation_execution.py
```

### What It Demonstrates

1. **Zero-Knowledge Execution**: Agent calls tools without knowing credentials
2. **Credential Injection**: Gateway securely injects OAuth tokens
3. **Full Attribution**: Every action logged as "agent on behalf of user"
4. **Defense in Depth**: Credentials never exposed to potentially compromised agent

### Expected Output

```
======================================================================
  DEMO 3: DELEGATION-BASED EXECUTION
======================================================================

  Value Proposition:
  • Agent calls tools WITHOUT knowing credentials
  • Gateway securely injects user's OAuth tokens
  • Agent NEVER sees sensitive credential values
  • Every action attributed: 'agent on behalf of user'

----------------------------------------------------------------------
🎭 Running in MOCK MODE (no services required)
----------------------------------------------------------------------

🤖 AGENT PERSPECTIVE
--------------------------------------------------

   Agent code:
   --------------------------------------------
   # Agent makes a simple tool call
   result = await client.tools_call(
       "notion.search_pages",
       {"query": "sales playbook"}
   )
   
   # Agent sees result
   print(result)  # Page content, no credentials
   --------------------------------------------

   ⚠️  NOTE: No credentials in request!
   The agent has no idea what OAuth token is used.

🔐 GATEWAY PERSPECTIVE (behind the scenes)
--------------------------------------------------

   1. RECEIVE request from agent
   2. VALIDATE agent session
   3. CHECK permission
   4. LOOKUP credentials (from vault)
   5. INJECT credentials into backend request
   6. FORWARD to backend and get result
   7. STRIP any credential echoes from response
   8. LOG audit event

📨 WHAT AGENT RECEIVES
--------------------------------------------------

   ✓ Contains: search results (page content)
   ✗ Does NOT contain:
     • Sarah's OAuth token
     • Vault reference
     • Backend URL
     • Any authentication headers

======================================================================
  ✅ KEY INSIGHTS
======================================================================

   1. ZERO-KNOWLEDGE EXECUTION
   2. CREDENTIAL ISOLATION
   3. FULL ATTRIBUTION
   4. DEFENSE IN DEPTH

======================================================================
```

## Running All Demos

```bash
# Run all demos in mock mode
for demo in demo_*.py; do
    echo "Running $demo..."
    python "$demo" --mock
    echo
done
```

## Demo Structure

Each demo follows a consistent pattern:

```python
# 1. Import and configure
from demos.demo_XX_name import run_demo

# 2. Run in mock mode
result = await run_demo(mock_mode=True)

# 3. Check result
assert result.success
print(f"Tools: {len(result.tools)}")
```

## Development

### Adding a New Demo

1. Create `demo_NN_name.py` following the existing pattern
2. Add MockClient class for testing without services
3. Add tests in `tests/demos/test_demo_NN.py`
4. Update this README

### Testing Demos

```bash
# Run all demo tests
pytest tests/demos/ -v

# Run specific demo tests
pytest tests/demos/test_demo_01.py -v
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        AI Agent                                 │
│                  (Demo Client)                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ ONE connection
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Virtual MCP Gateway                          │
│                 http://localhost:8002/mcp                       │
└─────────────────────────────────────────────────────────────────┘
                              │
          ┌───────────────────┼───────────────────┐
          │                   │                   │
          ▼                   ▼                   ▼
    ┌──────────┐        ┌──────────┐        ┌──────────┐
    │  Notion  │        │  Slack   │        │ HubSpot  │
    │   MCP    │        │   MCP    │        │   MCP    │
    └──────────┘        └──────────┘        └──────────┘

       Agent sees: notion.*, slack.*, hubspot.* tools
       Agent knows: Only gateway URL
```

---

*These demos are part of the Virtual MCP Server MVP implementation.*
