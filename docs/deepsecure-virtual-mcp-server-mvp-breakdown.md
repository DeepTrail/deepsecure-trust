# Workstream Breakdown for: Virtual MCP Server MVP

> **Generated from:** `docs/design/internal/markdowns/deepsecure-virtual-mcp-server-mvp.md`
>
> **Generated on:** January 2026
>
> **Command:** `/breakdown-design`

---

## Summary

- **Total Workstreams:** 6
- **Total Tasks:** 44
- **Total Batches:** 9
- **Critical Path:** A1 → A5 → A6 → A7 → A8 → C1 → C2 → C3 → C6 → C7 → E3 → F1 → F8
- **Merge Points:** 4
- **Estimated Total Effort:** 8 S, 32 M, 4 L
- **Timeline:** 15 working days (3 weeks)

---

## Workstream A: Control Plane Foundation (PARALLEL with B)

**Service:** `deeptrail-control/`  
**Batches:** 1, 2, 3, 4  
**MVP Steps Covered:** Steps 1-4 (Enterprise Registration → Delegation)

| Task ID | Description | Dependencies | Size | Files | Acceptance Criteria |
|---------|-------------|--------------|------|-------|---------------------|
| **A1** | Define User Session data model | None | S | `models/user_session.py` (create) | Model with session_id, user_id, expires_at fields |
| **A2** | Implement UserSessionService | A1 | M | `services/user_session_service.py` (create) | Create/read/expire sessions work |
| **A3** | Define Connected Services model | A1 | S | `models/connected_service.py` (create) | Store OAuth token refs per user |
| **A4** | Implement OAuth token vault storage | A3 | M | `services/vault_client.py` (create), `services/connected_service.py` (create) | Securely store/retrieve tokens |
| **A5** | Define Delegation Token model | A1 | S | `models/delegation.py` (create) | Model matching Step 4 claims |
| **A6** | Implement DelegationService | A5 | M | `services/delegation_service.py` (create) | Create/validate/revoke delegations |
| **A7** | Define Agent Session model | A5 | S | `models/agent_session.py` (create) | Model matching Step 5 claims |
| **A8** | Implement AgentSessionService | A6, A7 | M | `services/agent_session_service.py` (create) | Challenge/verify/issue JWT |

**Critical Path:** A1 → A5 → A6 → A7 → A8

---

## Workstream B: Gateway MCP Core (PARALLEL with A)

**Service:** `deeptrail-gateway/`  
**Batches:** 1, 2, 3, 4  
**MVP Steps Covered:** Steps 6-7 (Agent Connect → tools/list)

| Task ID | Description | Dependencies | Size | Files | Acceptance Criteria |
|---------|-------------|--------------|------|-------|---------------------|
| **B1** | Implement MCP JSON-RPC 2.0 parser | None | M | `gateway/mcp/protocol.py` (create) | Parse initialize, tools/list, tools/call |
| **B2** | Implement initialize handler | B1 | S | `gateway/mcp/handlers/initialize.py` (create) | Return serverInfo per Step 6 |
| **B3** | Implement MCP Session tracking | B2 | M | `gateway/mcp/session_manager.py` (create) | Track backend connections per agent |
| **B4** | Implement namespace prefixer | B1 | S | `gateway/mcp/namespace.py` (create) | `{backend}.{tool}` pattern works |
| **B5** | Implement tool schema cache | B4 | M | `gateway/mcp/tool_cache.py` (create) | Cache with TTL refresh |
| **B6** | Implement tools/list handler | B3, B5 | M | `gateway/mcp/handlers/tools_list.py` (create) | Return aggregated, filtered tools |
| **B7** | Implement tools/call handler | B3, B4 | M | `gateway/mcp/handlers/tools_call.py` (create) | Route to backend, inject creds |
| **B8** | Implement tool aggregator | B5, B6 | M | `gateway/mcp/aggregator.py` (create) | Combine tools from all backends |

**Critical Path:** B1 → B2 → B3 → B6 → B8

---

## Workstream C: Auth & Permissions (DEPENDS ON A, B)

**Services:** Both `deeptrail-control/` and `deeptrail-gateway/`  
**Batches:** 4, 5, 6  
**Contributes to Merge Point:** MP1  
**MVP Steps Covered:** Steps 5, 8-9 (Agent Auth → Permission Enforcement)

| Task ID | Description | Dependencies | Size | Files | Acceptance Criteria |
|---------|-------------|--------------|------|-------|---------------------|
| **C1** | Implement agent challenge endpoint | A8 | M | `deeptrail-control/api/auth/challenge.py` (create) | Return nonce for Ed25519 signing |
| **C2** | Implement agent verify endpoint | C1 | M | `deeptrail-control/api/auth/verify.py` (create) | Validate signature, issue JWT |
| **C3** | Implement JWT validation middleware | C2 | M | `deeptrail-gateway/gateway/middleware/jwt_auth.py` (create) | Validate Agent Session JWT |
| **C4** | Implement tool→permission mapper | B4 | S | `deeptrail-gateway/gateway/mcp/permission_mapper.py` (create) | `notion.search_pages` → `notion:pages:search` |
| **C5** | Implement permission filter | C3, C4 | M | `deeptrail-gateway/gateway/middleware/permission_filter.py` (create) | Filter tools/list by delegation |
| **C6** | Implement delegation validator | C3, A6 | M | `deeptrail-gateway/gateway/middleware/delegation_validator.py` (create) | Check permission on tools/call |
| **C7** | Implement credential injection | C6, A4 | M | `deeptrail-gateway/gateway/middleware/credential_injection.py` (create) | Inject OAuth token from vault |

**Critical Path:** C1 → C2 → C3 → C6 → C7

---

## Workstream D: Backend Connectors (PARALLEL with C after B8)

**Service:** `deeptrail-gateway/`  
**Batches:** 4, 5  
**Depends on Merge Point:** MP2  
**MVP Steps Covered:** Step 8 (Tool Execution)

| Task ID | Description | Dependencies | Size | Files | Acceptance Criteria |
|---------|-------------|--------------|------|-------|---------------------|
| **D1** | Implement backend connection manager | B8 | M | `gateway/backends/connection_manager.py` (create) | Pool connections, health checks |
| **D2** | Implement base MCP client | D1 | M | `gateway/backends/base_mcp_client.py` (create) | Abstract client for backends |
| **D3** | Implement Notion MCP client | D2 | M | `gateway/backends/notion_client.py` (create) | search_pages, read_page, create_page |
| **D4** | Implement Slack MCP client | D2 | M | `gateway/backends/slack_client.py` (create) | search_messages, send_message, list_channels |
| **D5** | Implement HubSpot MCP client | D2 | M | `gateway/backends/hubspot_client.py` (create) | get_contact, update_contact, list_deals |
| **D6** | Implement backend router | D1, B7 | M | `gateway/backends/router.py` (create) | Route by namespace prefix |

**Critical Path:** D1 → D2 → D3/D4/D5 (parallel)

---

## Workstream E: Audit & Security (DEPENDS ON C, D)

**Services:** Both `deeptrail-control/` and `deeptrail-gateway/`  
**Batches:** 1, 7, 8, 9  
**Depends on Merge Point:** MP3  
**MVP Steps Covered:** Steps 9-10 (Permission Denied, Audit Review)

| Task ID | Description | Dependencies | Size | Files | Acceptance Criteria |
|---------|-------------|--------------|------|-------|---------------------|
| **E1** | Define audit event model | None | S | `deeptrail-control/models/audit_event.py` (create) | Fields from Step 8 audit log |
| **E2** | Implement audit logger service | E1 | M | `deeptrail-control/services/audit_logger.py` (create) | Log all tool calls with attribution |
| **E3** | Implement audit middleware | E2, C6 | M | `deeptrail-gateway/gateway/middleware/audit.py` (create) | Log on every tools/call |
| **E4** | Implement fail-closed security | C3 | S | `deeptrail-gateway/gateway/middleware/fail_closed.py` (create) | Deny when control plane unavailable |
| **E5** | Implement constraint checker | C6 | M | `deeptrail-gateway/gateway/middleware/constraints.py` (create) | max_actions_per_day enforcement |
| **E6** | Implement audit query API | E2 | M | `deeptrail-control/api/audit/query.py` (create) | Query by agent_id, user, time range |

**Critical Path:** E1 → E2 → E3

---

## Workstream F: Integration & Demos (DEPENDS ON ALL)

**Locations:** `tests/`, `examples/`  
**Batches:** 7, 8, 9  
**Depends on Merge Point:** MP4  
**MVP Steps Covered:** Section 5 (Proof of Value Demos)

| Task ID | Description | Dependencies | Size | Files | Acceptance Criteria |
|---------|-------------|--------------|------|-------|---------------------|
| **F1** | Create Sarah's Journey E2E test | All | L | `tests/e2e/test_sarah_journey.py` (create) | Steps 1-10 automated |
| **F2** | Create Demo 1: Unified Connection | B6, D3, D4 | M | `examples/demo_01_unified_connection.py` (create) | Agent sees tools from 2 backends |
| **F3** | Create Demo 2: Filtered Visibility | C5 | M | `examples/demo_02_filtered_visibility.py` (create) | 90%+ tool reduction |
| **F4** | Create Demo 3: Delegation Execution | C7 | M | `examples/demo_03_delegation_execution.py` (create) | Agent never sees OAuth tokens |
| **F5** | Create Demo 4: Permission Enforcement | C6 | M | `examples/demo_04_permission_enforcement.py` (create) | Unauthorized blocked at gateway |
| **F6** | Create Demo 5: Unified Audit | E6 | M | `examples/demo_05_unified_audit.py` (create) | Query in <1 second |
| **F7** | Create Demo 6: Fail-Closed | E4 | M | `examples/demo_06_fail_closed.py` (create) | Zero requests during outage |
| **F8** | Create cross-service workflow demo | D5, F1 | L | `examples/demo_07_cross_service.py` (create) | Notion → HubSpot flow |

**Critical Path:** F1 → F8

---

## Batch Execution Model

| Batch | Tasks (Parallel) | Depends On | Blocking For | Duration |
|-------|------------------|------------|--------------|----------|
| **1** | A1, B1, E1 | None | Batch 2 | 1-2 days |
| **2** | A2, A3, A5, B2, B4 | Batch 1 | Batch 3 | 1-2 days |
| **3** | A4, A6, B3, B5 | Batch 2 | Batch 4 | 1 day |
| **4** | A7, A8, B6, B7, B8, C1, C2, D1, D2 | Batch 3 | Batch 5, **MP1** | 1-2 days |
| **5** | C3, C4, D3, D4, D5, D6 | Batch 4, MP1 | Batch 6, **MP2** | 1-2 days |
| **6** | C5, C6, C7 | Batch 5, MP2 | Batch 7, **MP3** | 1 day |
| **7** | E2, E3, F1 | Batch 6, MP3 | Batch 8 | 1-2 days |
| **8** | E4, E5, F2, F3, F4 | Batch 7 | Batch 9, **MP4** | 1-2 days |
| **9** | E6, F5, F6, F7, F8 | Batch 8, MP4 | Done | 1 day |

---

## Merge Points

| Point | Converging Tasks | Enables | Git Action |
|-------|------------------|---------|------------|
| **MP1** | A8 + B3 | C1 (agent auth) | Merge feature/vmcp-control + feature/vmcp-gateway to main |
| **MP2** | B8 + C3 | D1 (backend manager) | Continue on main or create feature/vmcp-backends |
| **MP3** | C7 + D6 | E3 (audit middleware) | Merge all backend work |
| **MP4** | E3 + all backends | F1 (E2E test) | Final merge before integration testing |

---

## Critical Path Analysis

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        DUAL-TRACK CRITICAL PATH                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  PRIMARY (Control Plane → Auth → Integration):                              │
│  ──────────────────────────────────────────────                              │
│  A1 → A5 → A6 → A7 → A8 → C1 → C2 → C3 → C6 → C7 → E3 → F1 → F8            │
│  │                                                                │          │
│  └──────────── 15 days minimum ───────────────────────────────────┘          │
│                                                                              │
│  SECONDARY (Gateway → Backends):                                             │
│  ───────────────────────────────                                             │
│  B1 → B2 → B3 → B6 → B8 → D1 → D2 → D3/D4/D5 → D6                          │
│  │                                              │                            │
│  └──────────── 12 days (3 days float) ─────────┘                            │
│                                                                              │
│  CONVERGENCE POINTS:                                                         │
│  • MP1 (Day 6): Control meets Gateway                                        │
│  • MP2 (Day 8): Auth meets Backends                                          │
│  • MP3 (Day 10): All middleware complete                                     │
│  • MP4 (Day 12): Ready for E2E                                               │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Acceptance Mapping

### Demo → Task Matrix

| Demo | Success Criteria | Validating Tasks |
|------|------------------|------------------|
| **Demo 1**: Unified Connection | Agent connects to ONE endpoint, sees tools from 2 backends | F2, B6, D3, D4 |
| **Demo 2**: Filtered Visibility | 90%+ tool reduction (4 of 37 tools visible) | F3, C5 |
| **Demo 3**: Delegation Execution | Agent never sees OAuth tokens | F4, C7 |
| **Demo 4**: Permission Enforcement | Zero unauthorized requests reach backend | F5, C6 |
| **Demo 5**: Unified Audit | Query "what did agent X do?" in <1 second | F6, E6 |
| **Demo 6**: Fail-Closed | Zero requests during control plane outage | F7, E4 |

### Sarah's Journey Step → Task Matrix

| Step | Description | Implementing Tasks |
|------|-------------|-------------------|
| **Step 1** | Enterprise Registration | A1 (MVP: hardcoded) |
| **Step 2** | Sarah Authenticates | A2 |
| **Step 3** | Sarah Connects Services | A3, A4 |
| **Step 4** | Sarah Delegates to Agent | A5, A6 |
| **Step 5** | Agent Authenticates | A7, A8, C1, C2 |
| **Step 6** | Agent Connects to Virtual MCP | B2, B3, C3 |
| **Step 7** | Agent Discovers Tools | B6, B8, C5 |
| **Step 8** | Agent Executes Task | B7, C6, C7, D3-D6 |
| **Step 9** | Agent Denied (unauthorized) | C6, E3 |
| **Step 10** | Sarah Reviews Audit | E6 |

---

## Dependency Graph

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         TASK DEPENDENCY GRAPH                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   WS-A (Control)                      WS-B (Gateway)                         │
│   ══════════════                      ══════════════                         │
│        A1 ────────────┐                    B1 ────────────┐                 │
│         │             │                     │             │                 │
│    ┌────┼────┐        │                ┌────┴────┐        │                 │
│    ▼    ▼    ▼        │                ▼         ▼        │                 │
│   A2   A3   A5        │               B2        B4        │                 │
│         │    │        │                │         │        │                 │
│         ▼    ▼        │                ▼         ▼        │                 │
│        A4   A6        │               B3        B5        │                 │
│              │        │                │         │        │                 │
│              ▼        │                └────┬────┘        │                 │
│             A7        │                     ▼             │                 │
│              │        │               B6 ──► B8           │                 │
│              ▼        │                │     │            │                 │
│             A8 ───────┼────────────────┼─────┼────────────┤                 │
│                       │                │     │            │                 │
│                       ▼                ▼     ▼            ▼                 │
│                      MP1 ════════════════════════════════╗                  │
│                                                          ║                  │
│   WS-C (Auth)                         WS-D (Backends)    ║                  │
│   ═══════════                         ═══════════════    ║                  │
│        C1 ◄──────────────────────────────────────────────╝                  │
│         │                                  D1 ◄── B8                        │
│         ▼                                   │                               │
│        C2 ──────┐                           ▼                               │
│         │       │                          D2                               │
│         ▼       ▼                      ┌───┼───┐                           │
│   C3 ──► C4    A6                      ▼   ▼   ▼                           │
│    │     │      │                     D3  D4  D5                           │
│    └──┬──┘      │                      │   │   │                           │
│       ▼         │                      └───┼───┘                           │
│      C5         │                          ▼                               │
│       │         │                         D6 ◄── B7                        │
│       ▼         │                          │                               │
│      C6 ◄───────┘                          │                               │
│       │                                    │                               │
│       ▼                                    │                               │
│      C7 ───────────────────────────────────┼───────────┐                   │
│                                            │           │                   │
│                                            ▼           ▼                   │
│                                           MP3 ═══════════                  │
│                                                        ║                   │
│   WS-E (Audit)                        WS-F (Demos)     ║                   │
│   ════════════                        ════════════     ║                   │
│        E1                                              ║                   │
│         │                                  F1 ◄════════╝                   │
│         ▼                                   │                               │
│        E2 ──────┐                           ▼                               │
│         │       │                     ┌─────┼─────┐                        │
│         ▼       ▼                     ▼     ▼     ▼                        │
│        E3 ◄─── C6               F2  F3  F4  F5                             │
│         │                        │   │   │   │                             │
│    ┌────┴────┐                   └───┼───┼───┘                             │
│    ▼         ▼                       │   │                                 │
│   E4        E5                       ▼   ▼                                 │
│    │         │                  F6  F7  F8                                 │
│    └────┬────┘                                                             │
│         ▼                                                                   │
│        E6                                                                   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Recommended Execution Setup

### Parallel Worktree Setup (2-3 worktrees)

```bash
# From main repo
cd /Users/imaxxs/repositories/deepsecure-mvp
git worktree add ../vmcp-control -b feature/vmcp-control dev
git worktree add ../vmcp-gateway -b feature/vmcp-gateway dev

# Copy .cursor/commands to worktrees (required for /execute-task to work)
cp -r .cursor ../vmcp-control/
cp -r .cursor ../vmcp-gateway/
```

### Batch 1-4 Execution (Days 1-6)

**Terminal 1 (vmcp-control):** A1 → A2, A3, A5 → A4, A6 → A7, A8

**Terminal 2 (vmcp-gateway):** B1 → B2, B4 → B3, B5 → B6, B7, B8

### MP1: Merge Point (Day 6)

```bash
cd /Users/imaxxs/repositories/deepsecure-mvp
git merge feature/vmcp-control feature/vmcp-gateway
```

### Batch 5-6 Execution (Days 7-10)

**Terminal 1:** C1 → C2 → C3, C4 → C5 → C6 → C7

**Terminal 2:** D1 → D2 → D3, D4, D5 → D6

### MP3: Merge Point (Day 10)

### Batch 7-9 Execution (Days 11-15)

**Sequential:** E2, E3 → E4, E5, F1 → E6, F2-F8

---

## File Checklist

### New Files to Create

```
deeptrail-control/
├── models/
│   ├── user_session.py          ← A1
│   ├── connected_service.py     ← A3
│   ├── delegation.py            ← A5
│   ├── agent_session.py         ← A7
│   └── audit_event.py           ← E1
├── services/
│   ├── user_session_service.py  ← A2
│   ├── vault_client.py          ← A4
│   ├── connected_service.py     ← A4
│   ├── delegation_service.py    ← A6
│   ├── agent_session_service.py ← A8
│   └── audit_logger.py          ← E2
└── api/
    ├── auth/
    │   ├── challenge.py         ← C1
    │   └── verify.py            ← C2
    └── audit/
        └── query.py             ← E6

deeptrail-gateway/
├── gateway/
│   ├── mcp/
│   │   ├── protocol.py          ← B1
│   │   ├── session_manager.py   ← B3
│   │   ├── namespace.py         ← B4
│   │   ├── tool_cache.py        ← B5
│   │   ├── aggregator.py        ← B8
│   │   ├── permission_mapper.py ← C4
│   │   └── handlers/
│   │       ├── initialize.py    ← B2
│   │       ├── tools_list.py    ← B6
│   │       └── tools_call.py    ← B7
│   ├── middleware/
│   │   ├── jwt_auth.py          ← C3
│   │   ├── permission_filter.py ← C5
│   │   ├── delegation_validator.py ← C6
│   │   ├── credential_injection.py ← C7
│   │   ├── audit.py             ← E3
│   │   ├── fail_closed.py       ← E4
│   │   └── constraints.py       ← E5
│   └── backends/
│       ├── connection_manager.py ← D1
│       ├── base_mcp_client.py   ← D2
│       ├── notion_client.py     ← D3
│       ├── slack_client.py      ← D4
│       ├── hubspot_client.py    ← D5
│       └── router.py            ← D6

tests/
└── e2e/
    └── test_sarah_journey.py    ← F1

examples/
├── demo_01_unified_connection.py  ← F2
├── demo_02_filtered_visibility.py ← F3
├── demo_03_delegation_execution.py ← F4
├── demo_04_permission_enforcement.py ← F5
├── demo_05_unified_audit.py       ← F6
├── demo_06_fail_closed.py         ← F7
└── demo_07_cross_service.py       ← F8
```

---

*Document Version: 1.0 | Generated: January 2026 | Source: `/breakdown-design` command*
