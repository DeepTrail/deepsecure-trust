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

## Specifications

### Batch P1-B1 (Foundation Services)

| Task ID | Spec | Ticket | Status | Report |
|---------|------|--------|--------|--------|
| WS-E1 | [WS-E1-spec.md](./specs/WS-E1-spec.md) | [WS-E1-enhance-vault-client.md](./tasks/WS-E1-enhance-vault-client.md) | ✅ Complete | [Report](./reports/WS-E1-completion.md) |
| WS-F1 | [WS-F1-spec.md](./specs/WS-F1-spec.md) | [WS-F1-create-oauth-service.md](./tasks/WS-F1-create-oauth-service.md) | ✅ Complete | [Report](./reports/WS-F1-completion.md) |
| WS-G1 | [WS-G1-spec.md](./specs/WS-G1-spec.md) | [WS-G1-add-backend-configuration.md](./tasks/WS-G1-add-backend-configuration.md) | ✅ Complete | [Report](./reports/WS-G1-completion.md) |

### Batch P1-B2 (API Endpoints & Backend Integrations) ✅ COMPLETE

| Task ID | Spec | Ticket | Status | Report |
|---------|------|--------|--------|--------|
| WS-E2 | [WS-E2-spec.md](./specs/WS-E2-spec.md) | [WS-E2-vault-token-retrieval-endpoint.md](./tasks/WS-E2-vault-token-retrieval-endpoint.md) | ✅ Complete | [Report](./reports/WS-E2-completion.md) |
| WS-E3 | [WS-E3-spec.md](./specs/WS-E3-spec.md) | [WS-E3-vault-token-refresh-endpoint.md](./tasks/WS-E3-vault-token-refresh-endpoint.md) | ✅ Complete | [Report](./reports/WS-E3-completion.md) |
| WS-F2 | [WS-F2-spec.md](./specs/WS-F2-spec.md) | [WS-F2-create-oauth-config.md](./tasks/WS-F2-create-oauth-config.md) | ✅ Complete | [Report](./reports/WS-F2-completion.md) |
| WS-F3 | [WS-F3-spec.md](./specs/WS-F3-spec.md) | [WS-F3-create-oauth-endpoints.md](./tasks/WS-F3-create-oauth-endpoints.md) | ✅ Complete | [Report](./reports/WS-F3-completion.md) |
| WS-G2 | [WS-G2-spec.md](./specs/WS-G2-spec.md) | [WS-G2-notion-rest-api-calls.md](./tasks/WS-G2-notion-rest-api-calls.md) | ✅ Complete | [Report](./reports/WS-G2-completion.md) |
| WS-G3 | [WS-G3-spec.md](./specs/WS-G3-spec.md) | [WS-G3-slack-rest-api-calls.md](./tasks/WS-G3-slack-rest-api-calls.md) | ✅ Complete | [Report](./reports/WS-G3-completion.md) |
| WS-G4 | [WS-G4-spec.md](./specs/WS-G4-spec.md) | [WS-G4-hubspot-rest-api-calls.md](./tasks/WS-G4-hubspot-rest-api-calls.md) | ✅ Complete | [Report](./reports/WS-G4-completion.md) |

---

## Related Documents

- [Breakdown](../../mvp-production-readiness-breakdown.md) - Detailed task breakdown
- [Status](./STATUS.md) - Current progress
- [Plan](../../../plans/mvp_production_readiness.plan.md) - Original plan
- [Coverage Matrix](../virtual-mcp-server-mvp/MVP_COVERAGE_MATRIX.md) - What MVP covers
- [Architecture Analysis](../virtual-mcp-server-mvp/MVP_ARCHITECTURE_ANALYSIS.md) - Architecture gaps
