# Workstream Breakdown: MVP Production Readiness

> **Design Source:** `plans/mvp_production_readiness.plan.md`  
> **Created:** February 2026  
> **Purpose:** Convert Virtual MCP Server MVP from mock implementations to production-ready deployment

---

## Summary

| Metric | Value |
|--------|-------|
| **Total Workstreams** | 8 |
| **Total Tasks** | 32 |
| **Total Batches** | 7 |
| **Critical Path** | A1 → A2 → A3 → D1 → D2 (P0), then E1 → E2 → G1 → G3 → H1 (P1) |
| **Merge Points** | 3 (MP1: P0 complete, MP2: P1 Vault ready, MP3: P1 complete) |
| **Estimated Total Effort** | 12S + 14M + 6L |

### Phase Distribution

| Phase | Priority | Tasks | Focus |
|-------|----------|-------|-------|
| **P0** | Immediate | 10 | Enable E2E tests to pass |
| **P1** | Short-term | 14 | Real OAuth and backend integration |
| **P2** | Medium-term | 8 | Production hardening |

---

## Parallelization Decision

**Recommended Setup:** 2 worktrees based on service boundaries

| Worktree | Service | Workstreams | Branch Pattern |
|----------|---------|-------------|----------------|
| `mvp-prod-control` | deeptrail-control | A, B, C, E, F, I | `feature/mvp-prod-control` |
| `mvp-prod-gateway` | deeptrail-gateway | G, H, J, K | `feature/mvp-prod-gateway` |

**Rationale:**
- P0 is entirely Control Plane (single worktree sufficient)
- P1 has clear split: Control Plane (vault, OAuth) vs Gateway (backends, credential injection)
- P2 can be parallelized across both services
- Enables 2 parallel Claude instances for P1/P2

**Tradeoff:**

| Option | Decision | Why |
|--------|----------|-----|
| Git Worktrees | ✅ Chosen | Disk efficient, shared config |
| Multiple Clones | ❌ | Overkill for 2 services |
| Single Worktree | ⚠️ OK for P0 | P0 is Control Plane only |

**Setup Commands:**

```bash
# From main repo (for P1+)
git worktree add ../mvp-prod-control -b feature/mvp-prod-control dev
git worktree add ../mvp-prod-gateway -b feature/mvp-prod-gateway dev
```

---

## Phase 0: Enable E2E Tests

### Workstream A: User Authentication (Control Plane)

**Status:** PARALLEL with B, C  
**Service:** `deeptrail-control`

| Task ID | Description | Dependencies | Complexity | Files | Acceptance Criteria |
|---------|-------------|--------------|------------|-------|---------------------|
| WS-A1 | Create user auth schemas | None | S | `app/schemas/user_auth.py` (create) | Request/response Pydantic models for login |
| WS-A2 | Create UserAuthService | WS-A1 | M | `app/services/user_auth_service.py` (create) | Service handles login, creates UserSession, returns JWT |
| WS-A3 | Create login endpoint | WS-A2 | S | `app/api/v1/endpoints/user_auth.py` (create) | POST `/api/v1/auth/login` returns `{token, user}` |

### Workstream B: Service Connection (Control Plane)

**Status:** PARALLEL with A, C  
**Service:** `deeptrail-control`

| Task ID | Description | Dependencies | Complexity | Files | Acceptance Criteria |
|---------|-------------|--------------|------------|-------|---------------------|
| WS-B1 | Create service connection schemas | None | S | `app/schemas/user_services.py` (create) | Request/response models for connect endpoint |
| WS-B2 | Extend ConnectedServiceService | WS-B1 | S | `app/services/connected_service_service.py` (modify) | Add `connect_service()` method that stores OAuth tokens |
| WS-B3 | Create service connection endpoint | WS-B2 | M | `app/api/v1/endpoints/user_services.py` (create) | POST `/api/v1/users/me/services/connect` stores token |

### Workstream C: Agent & Delegation Fixes (Control Plane)

**Status:** PARALLEL with A, B  
**Service:** `deeptrail-control`

| Task ID | Description | Dependencies | Complexity | Files | Acceptance Criteria |
|---------|-------------|--------------|------------|-------|---------------------|
| WS-C1 | Verify agent registration schema | None | S | `app/schemas/agent.py`, `app/api/v1/endpoints/agents.py` (verify/modify) | POST `/api/v1/agents/` accepts `agent_id`, `name`, `public_key` |
| WS-C2 | Update delegation response format | None | S | `app/api/v1/endpoints/delegation.py` (modify) | Response includes `delegation_token` and `permissions` fields |
| WS-C3 | Wire new routes to API router | WS-A3, WS-B3 | S | `app/api/v1/api.py` (modify) | All new endpoints accessible via router |

### Workstream D: E2E Test Validation

**Status:** BLOCKED BY A, B, C (MP1)  
**Service:** Cross-service (tests at root)

| Task ID | Description | Dependencies | Complexity | Files | Acceptance Criteria |
|---------|-------------|--------------|------------|-------|---------------------|
| WS-D1 | Update E2E test endpoint paths | WS-C3 | S | `demos/demo_sarah_journey_e2e.py` (modify) | Tests use correct endpoint paths |
| WS-D2 | Run and validate E2E demo | WS-D1 | M | `demos/demo_sarah_journey_e2e.py` | All 10 steps pass with live services |

---

## Phase 1: Real Backend Integration

### Workstream E: Vault & Credential Storage (Control Plane)

**Status:** STARTS after MP1 (P0 complete)  
**Service:** `deeptrail-control`

| Task ID | Description | Dependencies | Complexity | Files | Acceptance Criteria |
|---------|-------------|--------------|------------|-------|---------------------|
| WS-E1 | Enhance vault client for token storage | MP1 | M | `app/services/vault_client.py` (modify) | Encrypted token storage, retrieval by credential_ref |
| WS-E2 | Create vault token retrieval endpoint | WS-E1 | M | `app/api/v1/endpoints/vault.py` (modify) | GET `/api/v1/vault/tokens/{credential_ref}` returns token data |
| WS-E3 | Create vault token refresh endpoint | WS-E1 | M | `app/api/v1/endpoints/vault.py` (modify) | POST `/api/v1/vault/tokens/{credential_ref}/refresh` refreshes token |

### Workstream F: OAuth Flows (Control Plane)

**Status:** PARALLEL with E  
**Service:** `deeptrail-control`

| Task ID | Description | Dependencies | Complexity | Files | Acceptance Criteria |
|---------|-------------|--------------|------------|-------|---------------------|
| WS-F1 | Create OAuth service | MP1 | L | `app/services/oauth_service.py` (create) | Generate auth URLs, handle callbacks, refresh tokens for Notion/Slack/HubSpot |
| WS-F2 | Create OAuth configuration | WS-F1 | M | `app/core/oauth_config.py` (create) | Per-service OAuth credentials, scopes, redirect URIs |
| WS-F3 | Create OAuth endpoints | WS-F1 | M | `app/api/v1/endpoints/oauth.py` (create) | `/authorize`, `/callback`, `/refresh` for each service |

### Workstream G: Real Backend Clients (Gateway)

**Status:** BLOCKED BY E2 (needs vault API)  
**Service:** `deeptrail-gateway`

| Task ID | Description | Dependencies | Complexity | Files | Acceptance Criteria |
|---------|-------------|--------------|------------|-------|---------------------|
| WS-G1 | Add backend configuration | MP1 | S | `app/core/config.py` (create/modify) | Backend API URLs, version headers configurable |
| WS-G2 | Implement Notion REST API calls | WS-G1 | L | `app/backends/notion_client.py` (modify) | `search_pages`, `read_page`, `create_page` call real Notion API |
| WS-G3 | Implement Slack REST API calls | WS-G1 | L | `app/backends/slack_client.py` (modify) | `search_messages`, `post_message`, `list_channels` call real Slack API |
| WS-G4 | Implement HubSpot REST API calls | WS-G1 | L | `app/backends/hubspot_client.py` (modify) | `get_contact`, `create_contact`, `list_deals` call real HubSpot API |

### Workstream H: Credential Injection (Gateway)

**Status:** BLOCKED BY E2 (needs vault API)  
**Service:** `deeptrail-gateway`

| Task ID | Description | Dependencies | Complexity | Files | Acceptance Criteria |
|---------|-------------|--------------|------------|-------|---------------------|
| WS-H1 | Connect CredentialInjector to vault API | WS-E2 | M | `app/middleware/credential_injection.py` (modify) | `_fetch_from_vault()` calls Control Plane vault API |
| WS-H2 | Implement token refresh in injector | WS-E3 | M | `app/middleware/credential_injection.py` (modify) | `_refresh_token()` calls Control Plane refresh endpoint |

---

## Phase 2: Production Hardening

### Workstream I: Enterprise IdP (Control Plane)

**Status:** STARTS after MP3 (P1 complete)  
**Service:** `deeptrail-control`

| Task ID | Description | Dependencies | Complexity | Files | Acceptance Criteria |
|---------|-------------|--------------|------------|-------|---------------------|
| WS-I1 | Create IdP service | MP3 | L | `app/services/idp_service.py` (create) | OIDC client for Okta/Entra ID, user provisioning |
| WS-I2 | Create SSO endpoints | WS-I1 | M | `app/api/v1/endpoints/sso.py` (create) | `/sso/{idp}/authorize`, `/callback`, `/logout` |

### Workstream J: Security Hardening (Gateway)

**Status:** PARALLEL with I  
**Service:** `deeptrail-gateway`

| Task ID | Description | Dependencies | Complexity | Files | Acceptance Criteria |
|---------|-------------|--------------|------------|-------|---------------------|
| WS-J1 | Implement result filtering | MP3 | M | `app/middleware/result_filter.py` (create) | PII masking (emails, phones, SSNs), configurable per-backend |
| WS-J2 | Implement prompt injection detection | MP3 | M | `app/security/prompt_injection.py` (create) | Pattern validation, malicious payload blocking |
| WS-J3 | Implement Keycloak token exchange | MP3 | L | `app/security/token_exchange.py` (create) | RFC 8693 token exchange for backend OAuth tokens |

### Workstream K: Task Token System (Control Plane)

**Status:** PARALLEL with I, J  
**Service:** `deeptrail-control`

| Task ID | Description | Dependencies | Complexity | Files | Acceptance Criteria |
|---------|-------------|--------------|------------|-------|---------------------|
| WS-K1 | Create TaskToken model | MP3 | M | `app/models/task_token.py` (create) | Per-task scoped permissions, auto-revocation |
| WS-K2 | Create TaskService | WS-K1 | M | `app/services/task_service.py` (create) | Create, validate, complete, revoke tasks |
| WS-K3 | Create task endpoints | WS-K2 | M | `app/api/v1/endpoints/tasks.py` (create) | POST `/tasks`, GET `/tasks/{id}`, POST `/tasks/{id}/complete` |

---

## Batch Execution Model

### Phase 0 Batches

| Batch | Tasks (Parallel) | Depends On | Blocking For | Est. Time |
|-------|------------------|------------|--------------|-----------|
| P0-B1 | A1, B1, C1, C2 | None | P0-B2 | 1-2 hours |
| P0-B2 | A2, B2 | P0-B1 | P0-B3 | 2-3 hours |
| P0-B3 | A3, B3, C3 | P0-B2 | P0-B4 | 2-3 hours |
| P0-B4 | D1, D2 | P0-B3 | MP1 | 1-2 hours |

### Phase 1 Batches

| Batch | Tasks (Parallel) | Depends On | Blocking For | Est. Time |
|-------|------------------|------------|--------------|-----------|
| P1-B1 | E1, F1, G1 | MP1 | P1-B2 | 3-4 hours |
| P1-B2 | E2, E3, F2, F3, G2, G3, G4 | P1-B1 | P1-B3 | 4-6 hours |
| P1-B3 | H1, H2 | P1-B2 | MP3 | 2-3 hours |

### Phase 2 Batches

| Batch | Tasks (Parallel) | Depends On | Blocking For | Est. Time |
|-------|------------------|------------|--------------|-----------|
| P2-B1 | I1, J1, J2, K1 | MP3 | P2-B2 | 4-6 hours |
| P2-B2 | I2, J3, K2, K3 | P2-B1 | Done | 4-6 hours |

---

## Merge Points

| Point | Converging Tasks | Enables | Git Action |
|-------|------------------|---------|------------|
| **MP1** | D2 (P0 complete) | P1 workstreams E, F, G | Merge P0 to dev, create P1 branches |
| **MP2** | E2, E3 (Vault ready) | G*, H* (backend/injection) | Gateway can start consuming vault API |
| **MP3** | H2 (P1 complete) | P2 workstreams I, J, K | Merge P1 to dev, create P2 branches |

---

## Critical Path Analysis

```
PHASE 0 (Sequential - Control Plane only):
A1 → A2 → A3 → C3 → D1 → D2 [MP1]
     ↗               ↗
B1 → B2 → B3 ────────┘

PHASE 1 (Parallel after MP1):
Control:  E1 → E2 → [MP2]
              ↘ E3 → [MP2]
          F1 → F2 → F3

Gateway:  G1 → G2, G3, G4 (parallel per backend)
          [MP2] → H1 → H2 → [MP3]

PHASE 2 (Parallel after MP3):
Control:  I1 → I2
          K1 → K2 → K3

Gateway:  J1, J2, J3 (parallel)
```

**Critical Path (Total):** 
- P0: ~6-10 hours
- P1: ~9-13 hours  
- P2: ~8-12 hours
- **Total: ~23-35 hours**

---

## Acceptance Mapping

### Demo/Milestone Matrix

| Demo | Description | Validating Tasks |
|------|-------------|------------------|
| E2E Step 2 | Sarah Authenticates | A1, A2, A3 |
| E2E Step 3 | Sarah Connects Services | B1, B2, B3 |
| E2E Step 4 | Sarah Delegates to Agent | C1, C2 |
| E2E All 10 Steps | Complete Sarah's Journey | D1, D2 |
| Real Notion API | Search actual Notion pages | E2, G2, H1 |
| Real Slack API | Search actual Slack messages | E2, G3, H1 |
| Real HubSpot API | Query actual HubSpot contacts | E2, G4, H1 |
| Enterprise SSO | Login via Okta/Entra | I1, I2 |
| PII Masking | Sensitive data filtered | J1 |

### Sarah's Journey Step Matrix

| Step | Action | Implementing Tasks |
|------|--------|-------------------|
| 1 | Enterprise Registration | Pre-seeded (existing) |
| 2 | Sarah Authenticates | A1, A2, A3 |
| 3 | Sarah Connects Services | B1, B2, B3 |
| 4 | Sarah Registers Agent | C1 |
| 5 | Sarah Creates Delegation | C2 |
| 6 | Agent Requests Challenge | Existing (agent_auth.py) |
| 7 | Agent Authenticates | Existing (agent_auth.py) |
| 8 | Agent Connects to Gateway | Existing (gateway MCP) |
| 9 | Agent Executes Tools | G2, G3, G4 (real APIs) |
| 10 | Sarah Reviews Audit | Existing (audit.py) |

---

## API Contract Summary

> **CRITICAL**: These endpoints must match E2E test expectations exactly.

### Phase 0 Endpoints (Control Plane)

| Service | Method | Endpoint | Implementing Task | Status |
|---------|--------|----------|-------------------|--------|
| Control | POST | `/api/v1/auth/login` | A3 | **NEW** |
| Control | POST | `/api/v1/users/me/services/connect` | B3 | **NEW** |
| Control | POST | `/api/v1/agents/` | C1 | Verify |
| Control | POST | `/api/v1/auth/delegate` | C2 | Modify response |

### Phase 1 Endpoints (Control Plane)

| Service | Method | Endpoint | Implementing Task | Status |
|---------|--------|----------|-------------------|--------|
| Control | GET | `/api/v1/vault/tokens/{credential_ref}` | E2 | **NEW** |
| Control | POST | `/api/v1/vault/tokens/{credential_ref}/refresh` | E3 | **NEW** |
| Control | GET | `/api/v1/oauth/{service_id}/authorize` | F3 | **NEW** |
| Control | GET | `/api/v1/oauth/{service_id}/callback` | F3 | **NEW** |
| Control | POST | `/api/v1/oauth/{service_id}/refresh` | F3 | **NEW** |

### Phase 2 Endpoints (Control Plane)

| Service | Method | Endpoint | Implementing Task | Status |
|---------|--------|----------|-------------------|--------|
| Control | GET | `/api/v1/auth/sso/{idp}/authorize` | I2 | **NEW** |
| Control | GET | `/api/v1/auth/sso/{idp}/callback` | I2 | **NEW** |
| Control | POST | `/api/v1/auth/sso/logout` | I2 | **NEW** |
| Control | POST | `/api/v1/tasks` | K3 | **NEW** |
| Control | GET | `/api/v1/tasks/{task_id}` | K3 | **NEW** |
| Control | POST | `/api/v1/tasks/{task_id}/complete` | K3 | **NEW** |

---

## File Organization Plan

| Type | Location | Files | Notes |
|------|----------|-------|-------|
| **P0 Schemas** | `deeptrail-control/app/schemas/` | `user_auth.py`, `user_services.py` | Pydantic models |
| **P0 Services** | `deeptrail-control/app/services/` | `user_auth_service.py` | Business logic |
| **P0 Endpoints** | `deeptrail-control/app/api/v1/endpoints/` | `user_auth.py`, `user_services.py` | FastAPI routes |
| **P1 Control Services** | `deeptrail-control/app/services/` | `oauth_service.py` | OAuth handling |
| **P1 Control Config** | `deeptrail-control/app/core/` | `oauth_config.py` | OAuth credentials |
| **P1 Gateway Config** | `deeptrail-gateway/app/core/` | `config.py` | Backend API URLs |
| **P1 Gateway Middleware** | `deeptrail-gateway/app/middleware/` | `credential_injection.py` (modify) | Vault integration |
| **P2 Control Services** | `deeptrail-control/app/services/` | `idp_service.py`, `task_service.py` | Enterprise features |
| **P2 Control Models** | `deeptrail-control/app/models/` | `task_token.py` | Task token model |
| **P2 Gateway Security** | `deeptrail-gateway/app/security/` | `prompt_injection.py`, `token_exchange.py` | Security hardening |
| **P2 Gateway Middleware** | `deeptrail-gateway/app/middleware/` | `result_filter.py` | PII masking |
| **E2E Tests** | `tests/e2e/` (ROOT) | Update existing | Cross-service |
| **Demos** | `demos/` (ROOT) | Update existing | Cross-service |

---

## File Naming Conventions

| Pattern | Convention | Example |
|---------|------------|---------|
| Services | `*_service.py` suffix | `user_auth_service.py` |
| Schemas | Domain name | `user_auth.py`, `user_services.py` |
| Endpoints | Domain name | `user_auth.py`, `oauth.py` |
| Middleware | Descriptive action | `credential_injection.py` |
| Security | Descriptive action | `prompt_injection.py`, `token_exchange.py` |
| Config | `*_config.py` or `config.py` | `oauth_config.py` |

---

## Dependency Graph

```
                              ┌─────────────────────────────────────────────────────────────┐
                              │                         PHASE 0                              │
                              │                    (Control Plane Only)                      │
                              └─────────────────────────────────────────────────────────────┘
                                                         │
    ┌────────────────────────────────────────────────────┼────────────────────────────────────┐
    │                                                    │                                    │
    ▼                                                    ▼                                    ▼
┌───────┐                                          ┌───────┐                            ┌───────┐
│  A1   │ User Auth Schemas                        │  B1   │ Service Schemas            │ C1,C2 │
└───┬───┘                                          └───┬───┘                            └───┬───┘
    │                                                  │                                    │
    ▼                                                  ▼                                    │
┌───────┐                                          ┌───────┐                                │
│  A2   │ UserAuthService                          │  B2   │ ConnectedServiceService        │
└───┬───┘                                          └───┬───┘                                │
    │                                                  │                                    │
    ▼                                                  ▼                                    │
┌───────┐                                          ┌───────┐                                │
│  A3   │ Login Endpoint                           │  B3   │ Connect Endpoint               │
└───┬───┘                                          └───┬───┘                                │
    │                                                  │                                    │
    └──────────────────────────┬───────────────────────┴────────────────────────────────────┘
                               │
                               ▼
                          ┌───────┐
                          │  C3   │ Wire Routes (api.py)
                          └───┬───┘
                               │
                               ▼
                          ┌───────┐
                          │  D1   │ Update E2E Tests
                          └───┬───┘
                               │
                               ▼
                          ┌───────┐
                          │  D2   │ Validate E2E Demo
                          └───┬───┘
                               │
                               ▼
                          ┌──────────────────────────────────────────────────────────────────┐
                          │                            [MP1]                                  │
                          │                     P0 COMPLETE - MERGE                          │
                          └──────────────────────────────────────────────────────────────────┘
                                                         │
         ┌───────────────────────────────────────────────┼───────────────────────────────────┐
         │                                               │                                   │
         ▼                                               ▼                                   ▼
    ┌─────────┐                                    ┌─────────┐                         ┌─────────┐
    │   E1    │ Vault Client                       │   F1    │ OAuth Service           │   G1    │
    └────┬────┘                                    └────┬────┘                         └────┬────┘
         │                                              │                                   │
    ┌────┴────┐                                    ┌────┴────┐                         ┌────┴────────────┐
    │         │                                    │         │                         │         │       │
    ▼         ▼                                    ▼         ▼                         ▼         ▼       ▼
┌──────┐  ┌──────┐                            ┌──────┐  ┌──────┐                  ┌──────┐  ┌──────┐  ┌──────┐
│  E2  │  │  E3  │                            │  F2  │  │  F3  │                  │  G2  │  │  G3  │  │  G4  │
└──┬───┘  └──┬───┘                            └──────┘  └──────┘                  └──────┘  └──────┘  └──────┘
   │         │                                                                     Notion   Slack    HubSpot
   └────┬────┘
        │
        ▼
   ┌──────────────────────────────────────────────────────────────────────────────────────────┐
   │                                          [MP2]                                            │
   │                                   VAULT API READY                                         │
   └──────────────────────────────────────────────────────────────────────────────────────────┘
        │
        ▼
   ┌─────────┐
   │   H1    │ CredentialInjector → Vault API
   └────┬────┘
        │
        ▼
   ┌─────────┐
   │   H2    │ Token Refresh
   └────┬────┘
        │
        ▼
   ┌──────────────────────────────────────────────────────────────────────────────────────────┐
   │                                          [MP3]                                            │
   │                                   P1 COMPLETE - MERGE                                     │
   └──────────────────────────────────────────────────────────────────────────────────────────┘
        │
        ├─────────────────────────────────────┬────────────────────────────────┐
        │                                     │                                │
        ▼                                     ▼                                ▼
   ┌─────────┐                          ┌───────────────────┐            ┌─────────┐
   │   I1    │ IdP Service              │  J1, J2, J3       │            │   K1    │ TaskToken Model
   └────┬────┘                          │  (parallel)       │            └────┬────┘
        │                               │  Result Filter,   │                 │
        ▼                               │  Prompt Injection,│                 ▼
   ┌─────────┐                          │  Token Exchange   │            ┌─────────┐
   │   I2    │ SSO Endpoints            └───────────────────┘            │   K2    │ TaskService
   └─────────┘                                                           └────┬────┘
                                                                              │
                                                                              ▼
                                                                         ┌─────────┐
                                                                         │   K3    │ Task Endpoints
                                                                         └─────────┘
```

---

## Next Steps

After saving this breakdown, the following commands are available:

1. **Create workstream structure:**
   ```
   /create-workstream mvp-production-readiness
   ```

2. **Create batch execution plan:**
   ```
   /create-batch-execution-plan mvp-production-readiness
   ```

3. **Create task specifications (for P0):**
   ```
   /plan
   /create-task-spec P0-B1 mvp-production-readiness
   ```

4. **Generate individual task tickets:**
   ```
   /create-task-ticket WS-A1 mvp-production-readiness
   ```

5. **Start execution:**
   ```
   /execute-task WS-A1
   ```

---

## Technical Requirements Checklist

| Requirement | Pattern | Applies To |
|-------------|---------|------------|
| Async fixtures | `@pytest_asyncio.fixture` | All E2E tests |
| HTTP client | `httpx.AsyncClient` | All async tests |
| JWT generation | Use existing `app/core/security.py` | A2, I1 |
| Token encryption | Use Fernet or similar | E1 |
| OAuth 2.0 PKCE | Required for Notion | F1 |
| Rate limiting | Respect backend limits | G2, G3, G4 |

---

*Document generated: February 2026*  
*Based on: plans/mvp_production_readiness.plan.md*
