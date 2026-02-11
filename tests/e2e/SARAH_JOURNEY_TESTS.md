# Sarah's Journey E2E Test Suite

**File:** `tests/e2e/test_sarah_journey.py`

## Overview

This test suite validates the complete 10-step user journey from the design document ([deepsecure-virtual-mcp-server-mvp.md](../../docs/design/internal/markdowns/deepsecure-virtual-mcp-server-mvp.md), Section 2: Sarah's Journey).

**This is the ultimate MVP validation test.** If these tests pass, the Virtual MCP Server works as designed.

---

## The 10 Steps

| Step | Name | What Happens | Key Validation |
|------|------|--------------|----------------|
| 1 | Enterprise Registration | Organization, user, agent pre-seeded | Infrastructure exists |
| 2 | Sarah Authenticates | Sarah logs into DeepTrail console | Human auth works |
| 3 | Sarah Connects Services | Sarah connects Notion & Slack via OAuth | OAuth integration works |
| 4 | Sarah Delegates to Agent | Sarah grants limited permissions to agent | Delegation flow works |
| 5 | Agent Authenticates | Agent proves identity via challenge-response | Cryptographic auth works |
| 6 | Agent Connects to Gateway | Agent establishes MCP session | Unified endpoint works |
| 7 | Agent Discovers Tools | Agent sees only delegated tools | Filtering works |
| 8 | Agent Executes Tool | Agent calls delegated tool successfully | Execution works |
| 9 | Agent Denied | Agent blocked from non-delegated tool | Permission enforcement works |
| 10 | Sarah Reviews Audit | Sarah sees all agent actions | Audit trail works |

---

## Complete Test Listing

### Step 1: Enterprise Registration (3 tests)

| Test | Description | Demo Value |
|------|-------------|------------|
| `test_organization_configured` | Verifies "Acme Corp" (org-acme-001) is pre-configured | **Enterprise onboarding** - Organizations can be registered in the system |
| `test_user_exists` | Verifies Sarah (sarah@acme.com) exists as a user | **User management** - Users belong to organizations |
| `test_agent_defined` | Verifies SDR-Assistant (agent-sdr-001) is defined | **Agent registry** - AI agents are tracked entities |

### Step 2: Sarah Authenticates (1 test)

| Test | Description | Demo Value |
|------|-------------|------------|
| `test_sarah_can_authenticate` | Sarah logs in with email/password and receives JWT | **Human authentication** - Users authenticate via standard login flow |

**API Endpoint:** `POST /api/v1/auth/login`

### Step 3: Sarah Connects Services (2 tests)

| Test | Description | Demo Value |
|------|-------------|------------|
| `test_connect_notion` | Sarah connects Notion via OAuth token | **OAuth integration** - Users link external services to their account |
| `test_connect_slack` | Sarah connects Slack via OAuth token | **Multi-service support** - Users can connect multiple services |

**API Endpoint:** `POST /api/v1/users/me/services/connect`

### Step 4: Sarah Delegates to Agent (2 tests)

| Test | Description | Demo Value |
|------|-------------|------------|
| `test_register_agent` | Agent is registered with Ed25519 public key | **Cryptographic identity** - Agents have verifiable identities |
| `test_create_delegation` | Delegation created with limited permissions (e.g., `notion:pages:search` but NOT `notion:pages:create`) | **Monotonic attenuation** - Delegation cannot grant more than user has |

**API Endpoints:**
- `POST /api/v1/agents/` - Register agent (note trailing slash)
- `POST /api/v1/auth/delegate` - Create delegation

### Step 5: Agent Authenticates (2 tests)

| Test | Description | Demo Value |
|------|-------------|------------|
| `test_request_challenge` | Agent receives a challenge nonce | **Challenge-response auth** - Cryptographic agent authentication |
| `test_verify_signature` | Agent signs challenge with Ed25519 key, receives JWT | **Zero-knowledge proof** - Agent proves identity without sharing secrets |

**API Endpoints:**
- `POST /api/v1/auth/agent/challenge` - Request challenge
- `POST /api/v1/auth/agent/verify` - Verify signature

### Step 6: Agent Connects to Gateway (1 test)

| Test | Description | Demo Value |
|------|-------------|------------|
| `test_mcp_initialize` | Agent establishes MCP session with Gateway | **Unified endpoint** - One connection for all backend services |

**API Endpoint:** `POST /mcp` (with `initialize` method)

### Step 7: Agent Discovers Tools (2 tests)

| Test | Description | Demo Value |
|------|-------------|------------|
| `test_tools_list_returns_filtered_tools` | Agent sees only delegated tools, hidden tools NOT visible | **Filtered visibility** - 90%+ attack surface reduction |
| `test_tool_count_is_limited` | Tool count ≤ 15 (not 20+ from all backends) | **Least privilege** - Agent sees minimum required tools |

**API Endpoint:** `POST /mcp` (with `tools/list` method)

### Step 8: Agent Executes Tool (2 tests)

| Test | Description | Demo Value |
|------|-------------|------------|
| `test_delegated_tool_call_succeeds` | `notion.search_pages` call succeeds with results | **Seamless execution** - Delegated tools work transparently |
| `test_credentials_not_exposed` | Response doesn't contain "access_token", "oauth", "bearer" | **Zero credential exposure** - Agent never sees OAuth tokens |

**API Endpoint:** `POST /mcp` (with `tools/call` method)

### Step 9: Agent Denied (1 test)

| Test | Description | Demo Value |
|------|-------------|------------|
| `test_non_delegated_tool_denied` | `notion.create_page` call returns permission denied error (code -32001) | **Permission enforcement** - Unauthorized actions blocked at gateway |

**API Endpoint:** `POST /mcp` (with `tools/call` method)

### Step 10: Sarah Reviews Audit (2 tests)

| Test | Description | Demo Value |
|------|-------------|------------|
| `test_audit_trail_available` | Audit events queryable by agent_id | **Unified audit** - Single source of truth for all agent actions |
| `test_audit_has_attribution` | Events have `agent_id`, `timestamp` | **Full attribution** - Who did what, when, on whose behalf |

**API Endpoint:** `GET /api/v1/audit/events`

### Complete Journey (1 test)

| Test | Description | Demo Value |
|------|-------------|------------|
| `test_complete_sarah_journey` | Runs all 10 steps in sequence as single integration test | **End-to-end validation** - The ultimate MVP proof point |

### Unit/Mock Tests (4 tests)

| Test | Description | Demo Value |
|------|-------------|------------|
| `test_scenario_has_valid_permissions` | Verifies 4+ delegated permissions configured | Test infrastructure validation |
| `test_scenario_services_configured` | Verifies Notion + Slack in scenario | Test infrastructure validation |
| `test_agent_keypair_generation` | Verifies Ed25519 keypair is valid (64 hex chars) | Cryptographic primitives work |
| `test_mcp_request_formats` | Verifies MCP JSON-RPC request helpers | Protocol compliance |

---

## Summary by Demo Capability

| Demo Capability | Tests | Key Proof Point |
|-----------------|-------|-----------------|
| **Unified MCP Connection** | Step 6, Step 7 | Agent connects once, sees tools from multiple backends |
| **Filtered Tool Visibility** | Step 7 (both tests) | 90%+ tool reduction - agent sees only 4 of 37 tools |
| **Delegation-Based Execution** | Step 4, Step 8 | Sarah consents once, agent uses her credentials safely |
| **Permission Enforcement** | Step 9 | Unauthorized requests blocked at gateway |
| **Zero Credential Exposure** | Step 8 (`credentials_not_exposed`) | Agent NEVER sees OAuth tokens |
| **Unified Audit Trail** | Step 10 (both tests) | Query all agent actions from one API |
| **Cryptographic Identity** | Step 4 (`register_agent`), Step 5 | Ed25519 challenge-response authentication |

---

## Test → Demo Mapping

This table maps each test to the corresponding demo that showcases the same capability:

| Test Class | Tests | Related Demo | Demo File |
|------------|-------|--------------|-----------|
| `TestStep01EnterpriseRegistration` | 3 | - | (Pre-requisite) |
| `TestStep02SarahAuthenticates` | 1 | - | (Pre-requisite) |
| `TestStep03SarahConnectsServices` | 2 | - | (Pre-requisite) |
| `TestStep04SarahDelegates` | 2 | Demo 3: Delegation Execution | `demo_03_delegation_execution.py` |
| `TestStep05AgentAuthenticates` | 2 | - | (Part of Demo 3) |
| `TestStep06AgentConnectsToGateway` | 1 | Demo 1: Unified Connection | `demo_01_unified_connection.py` |
| `TestStep07AgentDiscoversTools` | 2 | Demo 2: Filtered Visibility | `demo_02_filtered_visibility.py` |
| `TestStep08AgentExecutesTool` | 2 | Demo 3: Delegation Execution | `demo_03_delegation_execution.py` |
| `TestStep09AgentDenied` | 1 | Demo 4: Permission Enforcement | `demo_04_permission_enforcement.py` |
| `TestStep10SarahReviewsAudit` | 2 | Demo 5: Unified Audit | `demo_05_unified_audit.py` |
| `TestCompleteJourney` | 1 | All demos combined | - |

---

## Test Count Summary

| Category | Count |
|----------|-------|
| Step 1: Enterprise Registration | 3 |
| Step 2: Sarah Authenticates | 1 |
| Step 3: Sarah Connects Services | 2 |
| Step 4: Sarah Delegates | 2 |
| Step 5: Agent Authenticates | 2 |
| Step 6: Agent Connects | 1 |
| Step 7: Agent Discovers Tools | 2 |
| Step 8: Agent Executes Tool | 2 |
| Step 9: Agent Denied | 1 |
| Step 10: Sarah Reviews Audit | 2 |
| Complete Journey | 1 |
| Unit/Mock Tests | 4 |
| **Total** | **23** |

---

## Related Files

| File | Purpose |
|------|---------|
| `test_sarah_journey.py` | Main test file with all test classes |
| `test_fixtures.py` | Test data fixtures (SarahJourneyScenario, mock data) |
| `conftest.py` | Pytest configuration, fixtures (clients, tokens, keypairs) |
| `README.md` | How to run the tests (this guide's companion) |
