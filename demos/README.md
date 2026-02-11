# Virtual MCP Server Demos

This directory contains demonstration scripts that showcase the value propositions of the Virtual MCP Server pattern.

## Overview

The Virtual MCP Server Gateway provides a unified interface for AI agents to access multiple backend MCP servers. These demos illustrate the key benefits:

| Demo | Title | Key Value |
|------|-------|-----------|
| **E2E** | **Sarah's Journey** | **Complete 10-step journey with full I/O** |
| 1 | Unified Connection | One gateway, multiple backends |
| 2 | Filtered Visibility | Agents see only delegated tools |
| 3 | Delegation Execution | Agent acts on behalf of user |
| 4 | Permission Enforcement | Unauthorized tools rejected |
| 5 | Unified Audit | All actions logged under agent identity |
| 6 | Fail-Closed Security | Secure handling of failures |

---

## 🌟 Sarah's Journey - Complete E2E Demo (Recommended)

**The definitive demo that shows the complete Virtual MCP Server workflow with full JSON input/output.**

This demo walks through all 10 steps of Sarah's Journey from the MVP design document:

1. Enterprise Registration (pre-seeded)
2. Sarah Authenticates (`POST /api/v1/auth/login`)
3. Sarah Connects Notion & Slack (`POST /api/v1/users/me/services/connect`)
4. Sarah Delegates to Agent (`POST /api/v1/agents/`, `POST /api/v1/auth/delegate`)
5. Agent Authenticates (`POST /api/v1/auth/agent/challenge`, `POST /api/v1/auth/agent/verify`)
6. Agent Connects to Gateway (`POST /mcp` - initialize)
7. Agent Discovers Tools (`POST /mcp` - tools/list)
8. Agent Executes Tool (`POST /mcp` - tools/call)
9. Agent Denied on Non-Delegated Tool (`POST /mcp` - tools/call - permission denied)
10. Sarah Reviews Audit Trail (`GET /api/v1/audit/events`)

### Running the Demo

```bash
# Start services first
docker compose up -d deeptrail-control deeptrail-gateway

# Wait for services to be ready
sleep 5

# Run the complete journey demo
python demos/demo_sarah_journey_e2e.py
```

### Example Output (Summary)

```
╔══════════════════════════════════════════════════════════════════════╗
║           Sarah's Journey - Virtual MCP Server MVP Demo              ║
╚══════════════════════════════════════════════════════════════════════╝

Step 2: Sarah Authenticates
>>> REQUEST
POST http://localhost:8000/api/v1/auth/login
  Body: {"email": "sarah@acme.com", "password": "secure_password"}

<<< RESPONSE (SUCCESS)
  Status: 200
  Body: {"token": "eyJhbGciOiJIUzI1NiIs...", "user": {...}}

✅ Sarah authenticated successfully

...

Step 7: Agent Discovers Tools (Filtered by Delegation)
>>> REQUEST
POST http://localhost:8002/mcp
  Body: {"jsonrpc": "2.0", "method": "tools/list", "id": 2, "params": {}}

<<< RESPONSE (SUCCESS)
  Body: {"result": {"tools": [
    {"name": "notion.search_pages", ...},
    {"name": "slack.search_messages", ...},
    {"name": "slack.list_channels", ...}
  ]}}

✅ Discovered 4 tools (filtered by delegation)

...

╔══════════════════════════════════════════════════════════════════════╗
║              ✅ Sarah's Journey Complete - All 10 Steps Passed!      ║
╚══════════════════════════════════════════════════════════════════════╝

Value Propositions Demonstrated:
  1. ✓ Unified MCP Connection
  2. ✓ Delegation-Based Consent
  3. ✓ Tool Filtering
  4. ✓ Namespace Resolution
  5. ✓ Permission Enforcement
  6. ✓ Audit Trail
  7. ✓ Credential Isolation
```

---

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

## Demo 4: Permission Enforcement

**Value Proposition**: Unauthorized tools are BLOCKED at the gateway and NEVER reach the backend.

### Running the Demo

```bash
# Mock mode (no services required)
python demo_04_permission_enforcement.py --mock

# Live mode
python demo_04_permission_enforcement.py
```

### What It Demonstrates

1. **Gateway as Security Boundary**: All permission checks happen at gateway
2. **Zero Unauthorized Backend Calls**: Backend never processes blocked requests
3. **Clear Error Messages**: Agent knows exactly which permission is missing
4. **Defense in Depth**: 4 layers of security before forwarding to backend

### Expected Output

```
======================================================================
  DEMO 4: PERMISSION ENFORCEMENT
======================================================================

  Value Proposition:
  • Agent can ONLY call delegated tools
  • Unauthorized requests BLOCKED at gateway
  • Backend receives ZERO unauthorized requests
  • Zero-trust security model in action

----------------------------------------------------------------------
🎭 Running in MOCK MODE (no services required)
----------------------------------------------------------------------

🔐 SARAH'S DELEGATED PERMISSIONS
--------------------------------------------------

   Delegated (agent can use):
   ✓ notion:pages:search
   ✓ notion:pages:read
   ✓ slack:messages:search
   ✓ slack:channels:list

   NOT Delegated (agent cannot use):
   ✗ notion:pages:create
   ✗ notion:pages:delete
   ✗ slack:messages:send

✅ AUTHORIZED CALL: notion.search_pages
--------------------------------------------------

   Agent calls: notion.search_pages
   Required permission: notion:pages:search
   Delegated: ✓ YES

   Gateway processing:
   1. ✓ JWT validated
   2. ✓ Agent session found
   3. ✓ Delegation active
   4. ✓ Permission check: notion:pages:search in delegation
   5. ✓ Request forwarded to Notion backend

   Backend response:
   { "pages": [{"id": "page-123", "title": "Sales Playbook"}] }

   Result: ✅ SUCCESS

🚫 UNAUTHORIZED CALL: notion.create_page
--------------------------------------------------

   Agent calls: notion.create_page
   Required permission: notion:pages:create
   Delegated: ✗ NO

   Gateway processing:
   1. ✓ JWT validated
   2. ✓ Agent session found
   3. ✓ Delegation active
   4. ✗ Permission check: notion:pages:create NOT in delegation
   5. ❌ REQUEST BLOCKED - NOT forwarded to backend

   Error response to agent:
   {
     "error": {
       "code": -32001,
       "message": "Permission denied: notion:pages:create not delegated"
     }
   }

   Result: 🚫 BLOCKED AT GATEWAY

🔍 BACKEND REQUEST LOG VERIFICATION
--------------------------------------------------

   Notion Backend received these requests:
   ----------------------------------------------
   • notion.search_pages - args: {'query': 'sales playbook'}

   Total requests received: 1

   Unauthorized requests received by backend:
   ✅ ZERO - Backend never saw unauthorized requests

🛡️ DEFENSE IN DEPTH
--------------------------------------------------

   ┌─────────────────────────────────────────────────────────┐
   │ Layer 1: JWT validation (is request authentic?)         │
   │ Layer 2: Session check (is agent session valid?)        │
   │ Layer 3: Delegation check (does user consent exist?)    │
   │ Layer 4: Permission check (is action delegated?)        │
   │ ─────────────────────────────────────────────────────── │
   │ Only after ALL checks pass → forward to backend         │
   └─────────────────────────────────────────────────────────┘

======================================================================
  ✅ KEY INSIGHTS
======================================================================

   1. GATEWAY AS SECURITY BOUNDARY
      All permission checks happen at gateway, not backend

   2. ZERO UNAUTHORIZED BACKEND CALLS
      Backend never processes unauthorized requests

   3. CLEAR ERROR MESSAGES
      Agent knows exactly which permission is missing

   4. METRICS
      Authorized calls:        1
      Blocked calls:           2
      Backend requests:        1
      Unauthorized to backend: 0 (enforced)

======================================================================
```

## Demo 5: Unified Audit Trail

**Value Proposition**: Answer "What did agent X do today?" in under 1 second.

### Running the Demo

```bash
# Mock mode (no services required)
python demo_05_unified_audit.py --mock

# Live mode (requires Control Plane with audit API)
python demo_05_unified_audit.py
```

### What It Demonstrates

1. **Instant Audit Queries**: Sub-second response for compliance queries
2. **Centralized Logging**: All agent activity in one place
3. **Rich Filtering**: Filter by agent, user, tool, status, time
4. **Compliance Ready**: Complete audit trail for incident investigation

### Query Capabilities

```
GET /api/v1/audit/events
    ?agent_id=agent-sdr-001     # Filter by agent
    &user_id=sarah@acme.com     # Filter by delegating user
    &tool=notion.search_pages   # Filter by tool
    &status=denied              # Filter by status
    &start_time=2026-02-06      # Time range
```

### Expected Output

```
======================================================================
  DEMO 5: UNIFIED AUDIT TRAIL
======================================================================

  Value Proposition:
  • Answer 'What did agent X do?' in < 1 second
  • All agent activity logged in one place
  • Filter by agent, user, tool, status, time
  • Complete audit trail for compliance

----------------------------------------------------------------------
🎭 Running in MOCK MODE (no services required)
----------------------------------------------------------------------

🔍 AUDIT QUERY
--------------------------------------------------

   Question: 'What did agent agent-sdr-001 do today?'

   API Request:
   GET http://localhost:8000/api/v1/audit/events
       ?agent_id=agent-sdr-001
       &start_time=2026-02-05T...

📊 QUERY RESULTS (8 events)
--------------------------------------------------

   Query completed in: 52.3ms
   ✓ Under 1 second threshold!

   ----------------------------------------------------------------------
   Timestamp    Tool                         Status     Duration   Backend   
   ----------------------------------------------------------------------
   10:15:32     notion.search_pages          ✓ success  145ms      notion    
   10:16:45     notion.read_page             ✓ success  89ms       notion    
   10:17:12     notion.create_page           ✗ denied   12ms       notion    
   11:45:00     slack.search_messages        ✓ success  234ms      slack     
   12:00:00     slack.list_channels          ✓ success  67ms       slack     
   13:45:00     hubspot.search_contacts      ✓ success  178ms      hubspot   
   14:00:00     hubspot.update_contact       ✓ success  156ms      hubspot   
   14:15:00     notion.search_pages          ✓ success  112ms      notion    
   ----------------------------------------------------------------------
   Agent: agent-sdr-001
   On behalf of: sarah@acme.com

📈 AUDIT SUMMARY
--------------------------------------------------

   Total Events: 8

   By Status:
   ✓ Success: 7
   ✗ Denied:  1
   ⚠ Error:   0

   By Tool:
   • notion.search_pages: 2
   • slack.search_messages: 1
   • hubspot.search_contacts: 1
   ...

⚖️ COMPARISON: Traditional vs DeepSecure
--------------------------------------------------

   ┌─────────────────────────────────────────────────────────────────┐
   │                    TRADITIONAL APPROACH                         │
   │  To answer "What did agent X do today?":                        │
   │  1. Check Notion audit logs              → 30 min               │
   │  2. Check Slack audit logs               → 30 min               │
   │  3. Check HubSpot audit logs             → 30 min               │
   │  4. Cross-reference agent identity       → 60 min               │
   │  5. Correlate timestamps                 → 60 min               │
   │  6. Compile report                       → 60 min               │
   │  Total time: ~4 HOURS                                           │
   └─────────────────────────────────────────────────────────────────┘
   
   ┌─────────────────────────────────────────────────────────────────┐
   │                    DEEPSECURE APPROACH                          │
   │  GET /api/v1/audit/events?agent_id=agent-sdr-001                │
   │  Total time: < 1 SECOND                                         │
   └─────────────────────────────────────────────────────────────────┘

======================================================================
  ✅ KEY INSIGHTS
======================================================================

   Query time:    52.3ms
   Events found:  8

   ✓ SUCCESS: Query completed in under 1 second!

   Traditional approach: ~4 hours
   DeepSecure approach:  52ms

   Speedup: 276,923x faster

======================================================================
```

## Demo 6: Fail-Closed Security

**Value Proposition**: When the Control Plane is unavailable, ALL requests are DENIED.

### Running the Demo

```bash
# Mock mode (no services required)
python demo_06_fail_closed.py --mock

# Live mode (will simulate control plane outage)
python demo_06_fail_closed.py
```

### What It Demonstrates

1. **Fail-Closed by Design**: Gateway denies ALL requests when policy service is unavailable
2. **No Backdoor for Attackers**: Cannot bypass security by causing outage
3. **Circuit Breaker**: Fast failure (~5ms) instead of slow timeout
4. **Immediate Recovery**: Requests succeed as soon as control plane is healthy

### Expected Output

```
======================================================================
  DEMO 6: FAIL-CLOSED SECURITY
======================================================================

  Value Proposition:
  • When policy service is down → ALL requests DENIED
  • No 'fail-open' backdoor for attackers
  • Security failure mode prioritizes safety
  • Immediate recovery when service restored

----------------------------------------------------------------------
🎭 Running in MOCK MODE (no services required)
----------------------------------------------------------------------

🟢 PHASE 1: CONTROL PLANE HEALTHY
--------------------------------------------------
   Control Plane Status: 🟢 HEALTHY
   URL: http://localhost:8000
   Health Check: ✓ 200 OK

   Agent makes request:
   ----------------------------------------
   Tool: notion.search_pages
   Args: {'query': 'sales playbook'}
   Latency: 145.3ms

   Result: ✅ SUCCESS
   Response: {"pages": [{"id": "page-123", "title": "Sales Playbook"}]}

   → Request succeeds because gateway can verify permissions

🔴 PHASE 2: CONTROL PLANE OUTAGE
--------------------------------------------------

   ⚡ SIMULATING CONTROL PLANE OUTAGE...
   (In reality: docker stop deeptrail-control)

   Control Plane Status: 🔴 UNAVAILABLE
   URL: http://localhost:8000
   Health Check: ✗ Connection refused

   Agent tries to make requests during outage:

   Attempt 1:
   Tool: notion.search_pages
   Result: 🚫 DENIED
   Error: MCPError(-32000): Security denial - policy service unavailable

   Attempt 2:
   Tool: notion.search_pages
   Result: 🚫 DENIED
   Error: MCPError(-32000): Security denial - policy service unavailable

   ==================================================
   SECURITY BEHAVIOR: FAIL-CLOSED
   ==================================================
   • Total requests attempted: 3
   • Requests denied: 3
   • Requests allowed: 0

   ✅ SECURITY MAINTAINED: 0 requests allowed during outage
   ==================================================

🟢 PHASE 3: CONTROL PLANE RESTORED
--------------------------------------------------

   🔄 CONTROL PLANE COMING BACK ONLINE...
   (In reality: docker start deeptrail-control)

   Control Plane Status: 🟢 HEALTHY
   URL: http://localhost:8000
   Health Check: ✓ 200 OK

   Agent makes request after recovery:
   ----------------------------------------
   Tool: notion.search_pages
   Args: {'query': 'sales playbook'}
   Latency: 145.3ms

   Result: ✅ SUCCESS
   Response: {"pages": [{"id": "page-123", "title": "Sales Playbook"}]}

   → Requests succeed again immediately

⚖️ COMPARISON: Security Failure Modes
--------------------------------------------------

   ┌─────────────────────────────────────────────────────────────────┐
   │                     FAIL-OPEN (DANGEROUS)                       │
   ├─────────────────────────────────────────────────────────────────┤
   │  When policy service is unavailable:                           │
   │  → "Just let the request through, we'll log it later"          │
   │  RISK: Attacker can cause outage and bypass all checks.        │
   └─────────────────────────────────────────────────────────────────┘
   
   ┌─────────────────────────────────────────────────────────────────┐
   │                     FAIL-CLOSED (DEEPSECURE)                    │
   ├─────────────────────────────────────────────────────────────────┤
   │  When policy service is unavailable:                           │
   │  → DENY ALL REQUESTS                                           │
   │  WHY: Cannot verify permissions, so cannot allow action.       │
   └─────────────────────────────────────────────────────────────────┘

======================================================================
  ✅ KEY INSIGHTS
======================================================================

   1. FAIL-CLOSED BY DESIGN
   2. NO BACKDOOR FOR ATTACKERS
   3. CIRCUIT BREAKER (fast failure)
   4. IMMEDIATE RECOVERY

   DURING OUTAGE:
   ┌─────────────────────────────────────────────────┐
   │  Requests allowed:  0                           │
   │  Security:          ✓ MAINTAINED                │
   │  Availability:      ✗ DEGRADED (by design)      │
   └─────────────────────────────────────────────────┘

======================================================================
```

## Cross-Service Workflow Demo

**Value Proposition**: Agent orchestrates actions across multiple backends in a single workflow.

### Running the Demo

```bash
# Mock mode (no services required)
python demo_cross_service_workflow.py --mock

# Live mode (requires all backend services)
python demo_cross_service_workflow.py
```

### What It Demonstrates

1. **Multi-Backend Workflow**: Uses Notion, HubSpot, and Slack in one flow
2. **Namespaced Tools**: Tools like `notion.search_pages`, `hubspot.search_contacts`
3. **Cross-Service Data Flow**: Data flows between services seamlessly
4. **Unified Audit Trail**: All actions logged with agent and user attribution

### Workflow Steps

```
1. [NOTION]  Search for product information
2. [HUBSPOT] Find contacts interested in AI security
3. [NOTION]  Get outreach email template
4. [SLACK]   Notify SDR team about hot leads
5. [HUBSPOT] Update contact status to 'Contacted'
```

### Expected Output

```
======================================================================
  CROSS-SERVICE WORKFLOW DEMO
======================================================================

  Workflow: Sales Research and Outreach

  Backend Services Used:
  • Notion  - Knowledge base, templates
  • HubSpot - CRM, contact management
  • Slack   - Team communication

  Value Proposition:
  • Single agent connection to gateway
  • Seamless cross-backend data flow
  • Unified audit trail
  • Permission checks at each step

----------------------------------------------------------------------
🎭 Running in MOCK MODE (no services required)
----------------------------------------------------------------------

📊 WORKFLOW OVERVIEW
--------------------------------------------------

   =======================================================
   SALES RESEARCH AND OUTREACH WORKFLOW
   =======================================================
   1. [📝 NOTION  ] Search for product information
   2. [💼 HUBSPOT ] Find contacts interested in AI security
   3. [📝 NOTION  ] Get outreach email template
   4. [💬 SLACK   ] Notify SDR team about hot leads
   5. [💼 HUBSPOT ] Update contact status to 'Contacted'
   =======================================================

⚡ WORKFLOW EXECUTION
--------------------------------------------------

   ───────────────────────────────────────────────────────
   STEP 1: Search for product information
   ───────────────────────────────────────────────────────
   Backend:  📝 NOTION
   Tool:     notion.search_pages
   Status:   ✅ SUCCESS

   ... (4 more steps) ...

🔄 DATA FLOW VISUALIZATION
--------------------------------------------------

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
   └───────────┘         └───────────┘         └───────────┘

📋 UNIFIED AUDIT TRAIL
--------------------------------------------------

   Agent: agent-sdr-001
   On behalf of: sarah@acme.com

   Timestamp    Backend    Tool                         Status    
   -----------------------------------------------------------------
   14:30:00     notion     notion.search_pages          success   
   14:32:05     hubspot    hubspot.search_contacts      success   
   14:34:10     notion     notion.read_page             success   
   14:36:15     slack      slack.send_message           success   
   14:38:20     hubspot    hubspot.update_contact       success   
   -----------------------------------------------------------------

======================================================================
  ✅ WORKFLOW COMPLETE
======================================================================

   Steps executed:    5
   Steps succeeded:   5
   Backends used:     3 (hubspot, notion, slack)
   Total duration:    250.0ms
   Agent connections: 1 (gateway only)

   KEY VALUE:
   ┌─────────────────────────────────────────────────────┐
   │ • Agent code has NO knowledge of backend URLs       │
   │ • Credentials injected by gateway, invisible        │
   │ • Complete audit trail across all services          │
   │ • Permission checks at each step                    │
   └─────────────────────────────────────────────────────┘

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
