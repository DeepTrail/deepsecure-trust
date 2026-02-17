# MVP Production Readiness: Workstream Overview

> **Purpose:** Convert Virtual MCP Server MVP from mock implementations to production-ready deployment  
> **Source Design:** `plans/mvp_production_readiness.plan.md`  
> **Breakdown:** `docs/mvp-production-readiness-breakdown.md`

---

## Executive Summary

This workstream converts the existing MVP implementation, which uses mocks and stubs, into a production-ready deployment with:

- **Real user authentication** (login endpoint)
- **Real OAuth service connections** (Notion, Slack, HubSpot)
- **Real backend API calls** (translating MCP tools to REST APIs)
- **Production security features** (IdP integration, PII masking, prompt injection detection)

---

## Workstream Structure

```
docs/workstreams/mvp-production-readiness/
├── WORKSTREAM.md          # This file
├── STATUS.md              # Current progress
├── tasks/                 # Individual task specifications
│   ├── WS-A1-user-auth-schemas.md
│   ├── WS-A2-user-auth-service.md
│   └── ...
└── reports/               # Completion reports
    └── ...
```

---

## Phases Overview

### Phase 0: Enable E2E Tests (Immediate)

**Goal:** Make `demos/demo_sarah_journey_e2e.py` pass all 10 steps

| Workstream | Tasks | Service | Description |
|------------|-------|---------|-------------|
| WS-A | 3 | Control | User authentication (login endpoint) |
| WS-B | 3 | Control | Service connection endpoint |
| WS-C | 3 | Control | Agent registration & delegation fixes |
| WS-D | 2 | E2E | Test validation |

### Phase 1: Real Backend Integration

**Goal:** Replace mock implementations with real OAuth and API calls

| Workstream | Tasks | Service | Description |
|------------|-------|---------|-------------|
| WS-E | 3 | Control | Vault & credential storage |
| WS-F | 3 | Control | OAuth flows (authorize, callback, refresh) |
| WS-G | 4 | Gateway | Real backend REST API calls |
| WS-H | 2 | Gateway | Credential injection from vault |

### Phase 2: Production Hardening

**Goal:** Enterprise-ready security and compliance features

| Workstream | Tasks | Service | Description |
|------------|-------|---------|-------------|
| WS-I | 2 | Control | Enterprise IdP (Okta/Entra ID) |
| WS-J | 3 | Gateway | Security hardening (PII, prompt injection) |
| WS-K | 3 | Control | Task Token system (per-task permissions) |

---

## Key Decisions

### Backend Integration Approach

**Decision:** Implement direct REST API calls (Option B)

**Rationale:**
- Notion, Slack, HubSpot don't have official MCP servers
- Gateway can still aggregate and filter tools
- Security properties preserved
- Easier to demo with real data

### OAuth Token Storage

**Decision:** Store encrypted OAuth tokens in Control Plane vault

**Rationale:**
- Centralized credential management
- Gateway retrieves tokens just-in-time
- Agent never sees OAuth tokens
- Supports token refresh

---

## Critical Path

```
P0: A1 → A2 → A3 → C3 → D1 → D2 → [MP1]
P1: E1 → E2 → H1 → H2 → [MP3]
P2: I1 → I2 (parallel with J*, K*)
```

**Estimated Total:** 23-35 hours

---

## Validation Criteria

### P0 Complete (MP1)

```bash
# Both commands should pass
python demos/demo_sarah_journey_e2e.py
python demos/demo_sarah_journey_interactive.py --auto
```

### P1 Complete (MP3)

- Real OAuth tokens stored and retrieved
- Real API calls to Notion/Slack/HubSpot
- Token refresh working

### P2 Complete

- Enterprise SSO login via Okta/Entra ID
- PII filtering active in responses
- Per-task permissions enforced

---

## Related Documents

- [Breakdown](../../mvp-production-readiness-breakdown.md) - Detailed task breakdown
- [Status](./STATUS.md) - Current progress
- [Plan](../../../plans/mvp_production_readiness.plan.md) - Original plan
- [Coverage Matrix](../virtual-mcp-server-mvp/MVP_COVERAGE_MATRIX.md) - What MVP covers
- [Architecture Analysis](../virtual-mcp-server-mvp/MVP_ARCHITECTURE_ANALYSIS.md) - Architecture gaps
