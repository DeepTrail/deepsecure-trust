# MVP Production Readiness: Batch Execution Plan

> **Workstream:** MVP Production Readiness  
> **Created:** February 2026  
> **Total Batches:** 7 (P0: 4, P1: 3, P2: 2)

---

## Overview

This document provides a wave-by-wave execution plan with copy-paste ready commands and parallelism calculations.

### Phase Distribution

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            TIMELINE OVERVIEW                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  PHASE 0 (E2E Tests)          PHASE 1 (Integration)      PHASE 2 (Harden)  │
│  ──────────────────────       ─────────────────────      ─────────────────  │
│  P0-B1 │ P0-B2 │ P0-B3 │ P0-B4 │ P1-B1 │ P1-B2 │ P1-B3 │ P2-B1 │ P2-B2 │  │
│   1-2h │  2-3h │  2-3h │  1-2h │  3-4h │  4-6h │  2-3h │  4-6h │  4-6h │  │
│        ↑       ↑       ↑      [MP1]   ↑      [MP2]   [MP3]    ↑            │
│                                                                             │
│  Total: ~23-35 hours estimated                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Phase 0: Enable E2E Tests

### Batch P0-B1: Foundation Schemas & Fixes

**Wave Analysis:**
- **Parallel Tasks:** 4 (A1, B1, C1, C2)
- **Sequential Dependencies:** None
- **Estimated Duration:** 1-2 hours
- **Service:** `deeptrail-control` only

**Dependency Graph:**

```
┌───────────────────────────────────────────────────────────┐
│                        P0-B1                              │
├───────────────────────────────────────────────────────────┤
│                                                           │
│  ┌─────┐   ┌─────┐   ┌─────┐   ┌─────┐                   │
│  │ A1  │   │ B1  │   │ C1  │   │ C2  │   ← All parallel  │
│  └─────┘   └─────┘   └─────┘   └─────┘                   │
│                                                           │
└───────────────────────────────────────────────────────────┘
```

**Tasks:**

| Task | Description | Complexity | Files |
|------|-------------|------------|-------|
| A1 | Create user auth schemas | S | `app/schemas/user_auth.py` |
| B1 | Create service connection schemas | S | `app/schemas/user_services.py` |
| C1 | Verify agent registration schema | S | `app/schemas/agent.py` |
| C2 | Update delegation response format | S | `app/api/v1/endpoints/delegation.py` |

**Execute Commands:**

```bash
# Start 4 parallel Claude instances (or 4 terminal sessions)
# Each works on one task

# Instance 1: WS-A1
cd deeptrail-control
# Create app/schemas/user_auth.py with LoginRequest, LoginResponse, UserInfo

# Instance 2: WS-B1
cd deeptrail-control
# Create app/schemas/user_services.py with ConnectServiceRequest, ConnectServiceResponse

# Instance 3: WS-C1
cd deeptrail-control
# Verify app/schemas/agent.py has agent_id, name, public_key fields

# Instance 4: WS-C2
cd deeptrail-control
# Modify app/api/v1/endpoints/delegation.py response format
```

**Validation:**

```bash
# Run schema tests
cd deeptrail-control
pytest tests/unit/schemas/ -v

# Check delegation endpoint response
grep -r "delegation_token" app/api/v1/endpoints/delegation.py
```

---

### Batch P0-B2: Core Services

**Wave Analysis:**
- **Parallel Tasks:** 2 (A2, B2)
- **Sequential Dependencies:** A1, B1
- **Estimated Duration:** 2-3 hours
- **Service:** `deeptrail-control` only

**Dependency Graph:**

```
┌───────────────────────────────────────────────────────────┐
│                        P0-B2                              │
├───────────────────────────────────────────────────────────┤
│                                                           │
│  A1 ──▶ ┌─────┐         B1 ──▶ ┌─────┐                   │
│         │ A2  │                 │ B2  │   ← Parallel      │
│         └─────┘                 └─────┘                   │
│                                                           │
└───────────────────────────────────────────────────────────┘
```

**Tasks:**

| Task | Description | Complexity | Files |
|------|-------------|------------|-------|
| A2 | Create UserAuthService | M | `app/services/user_auth_service.py` |
| B2 | Extend ConnectedServiceService | S | `app/services/connected_service_service.py` |

**Execute Commands:**

```bash
# Instance 1: WS-A2
cd deeptrail-control
# Create app/services/user_auth_service.py
# - authenticate(email, password) -> UserSession
# - create_session_token(user) -> JWT
# - validate_credentials() MVP: config-based

# Instance 2: WS-B2
cd deeptrail-control
# Modify app/services/connected_service_service.py
# - Add connect_service(user_id, service_id, oauth_token) method
# - Store OAuth tokens in database
```

**Validation:**

```bash
# Run service tests
cd deeptrail-control
pytest tests/unit/services/test_user_auth_service.py -v
pytest tests/unit/services/test_connected_service_service.py -v
```

---

### Batch P0-B3: API Endpoints

**Wave Analysis:**
- **Parallel Tasks:** 3 (A3, B3, C3)
- **Sequential Dependencies:** A2, B2
- **Estimated Duration:** 2-3 hours
- **Service:** `deeptrail-control` only

**Dependency Graph:**

```
┌───────────────────────────────────────────────────────────┐
│                        P0-B3                              │
├───────────────────────────────────────────────────────────┤
│                                                           │
│  A2 ──▶ ┌─────┐   B2 ──▶ ┌─────┐         ┌─────┐         │
│         │ A3  │          │ B3  │ ──┬──▶  │ C3  │         │
│         └──┬──┘          └──┬──┘   │     └─────┘         │
│            └────────────────┴──────┘                      │
│                                                           │
└───────────────────────────────────────────────────────────┘
```

**Tasks:**

| Task | Description | Complexity | Files |
|------|-------------|------------|-------|
| A3 | Create login endpoint | S | `app/api/v1/endpoints/user_auth.py` |
| B3 | Create service connection endpoint | M | `app/api/v1/endpoints/user_services.py` |
| C3 | Wire routes to API router | S | `app/api/v1/api.py` |

**Execute Commands:**

```bash
# Instance 1: WS-A3
cd deeptrail-control
# Create app/api/v1/endpoints/user_auth.py
# POST /api/v1/auth/login -> {token, user}

# Instance 2: WS-B3
cd deeptrail-control
# Create app/api/v1/endpoints/user_services.py
# POST /api/v1/users/me/services/connect -> {connected, service_id}

# Instance 3: WS-C3 (after A3, B3 complete)
cd deeptrail-control
# Modify app/api/v1/api.py to include new routers
```

**Validation:**

```bash
# Start services
docker compose up deeptrail-control -d

# Test login endpoint
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"sarah@acme.com","password":"test123"}'

# Test service connection endpoint
curl -X POST http://localhost:8000/api/v1/users/me/services/connect \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"service_id":"notion","oauth_token":{"access_token":"test"}}'
```

---

### Batch P0-B4: E2E Validation

**Wave Analysis:**
- **Parallel Tasks:** 1 (D1), then D2
- **Sequential Dependencies:** C3 (all P0 endpoints ready)
- **Estimated Duration:** 1-2 hours
- **Service:** Cross-service (tests at root)

**Dependency Graph:**

```
┌───────────────────────────────────────────────────────────┐
│                        P0-B4                              │
├───────────────────────────────────────────────────────────┤
│                                                           │
│  C3 ──▶ ┌─────┐ ──▶ ┌─────┐ ──▶ [MP1]                    │
│         │ D1  │     │ D2  │                               │
│         └─────┘     └─────┘                               │
│                                                           │
└───────────────────────────────────────────────────────────┘
```

**Tasks:**

| Task | Description | Complexity | Files |
|------|-------------|------------|-------|
| D1 | Update E2E test endpoint paths | S | `demos/demo_sarah_journey_e2e.py` |
| D2 | Run and validate E2E demo | M | `demos/demo_sarah_journey_e2e.py` |

**Execute Commands:**

```bash
# WS-D1: Update E2E test paths
# Review demos/demo_sarah_journey_e2e.py
# Ensure endpoint paths match actual implementation

# WS-D2: Run E2E validation
docker compose up -d  # All services
python demos/demo_sarah_journey_e2e.py
```

**Validation (MP1 Criteria):**

```bash
# ALL steps should pass
python demos/demo_sarah_journey_e2e.py

# Expected output:
# ✓ Step 1: Enterprise Registration
# ✓ Step 2: Sarah Authenticates
# ✓ Step 3: Sarah Connects Services
# ✓ Step 4: Sarah Registers Agent
# ✓ Step 5: Sarah Creates Delegation
# ✓ Step 6: Agent Requests Challenge
# ✓ Step 7: Agent Authenticates
# ✓ Step 8: Agent Connects to Gateway
# ✓ Step 9: Agent Executes Tools
# ✓ Step 10: Sarah Reviews Audit

# Interactive mode
python demos/demo_sarah_journey_interactive.py --auto
```

---

## Phase 1: Real Backend Integration

> **Prerequisite:** MP1 (P0 complete)

### Batch P1-B1: Foundation Services

**Wave Analysis:**
- **Parallel Tasks:** 3 (E1, F1, G1)
- **Sequential Dependencies:** MP1
- **Estimated Duration:** 3-4 hours
- **Services:** `deeptrail-control` (E1, F1), `deeptrail-gateway` (G1)

**Recommended:** Use 2 worktrees

```bash
# Setup worktrees
git worktree add ../mvp-prod-control -b feature/mvp-prod-control dev
git worktree add ../mvp-prod-gateway -b feature/mvp-prod-gateway dev
```

**Dependency Graph:**

```
┌───────────────────────────────────────────────────────────┐
│                        P1-B1                              │
├───────────────────────────────────────────────────────────┤
│                                                           │
│  [MP1] ──▶ ┌─────┐   ┌─────┐   ┌─────┐                   │
│            │ E1  │   │ F1  │   │ G1  │   ← All parallel  │
│            └─────┘   └─────┘   └─────┘                   │
│            Control   Control   Gateway                    │
│                                                           │
└───────────────────────────────────────────────────────────┘
```

**Tasks:**

| Task | Description | Complexity | Files | Service |
|------|-------------|------------|-------|---------|
| E1 | Enhance vault client for token storage | M | `app/services/vault_client.py` | Control |
| F1 | Create OAuth service | L | `app/services/oauth_service.py` | Control |
| G1 | Add backend configuration | S | `app/core/config.py` | Gateway |

**Execute Commands:**

```bash
# Worktree 1 (Control): E1 + F1
cd ../mvp-prod-control/deeptrail-control
# E1: Enhance app/services/vault_client.py
# F1: Create app/services/oauth_service.py

# Worktree 2 (Gateway): G1
cd ../mvp-prod-gateway/deeptrail-gateway
# G1: Add backend URLs to app/core/config.py
```

---

### Batch P1-B2: Integration Components

**Wave Analysis:**
- **Parallel Tasks:** 7 (E2, E3, F2, F3, G2, G3, G4)
- **Sequential Dependencies:** E1, F1, G1
- **Estimated Duration:** 4-6 hours
- **Services:** Both

**Dependency Graph:**

```
┌───────────────────────────────────────────────────────────────────────────┐
│                                  P1-B2                                     │
├───────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  E1 ──┬──▶ ┌─────┐                                                        │
│       │    │ E2  │ ──┐                                                    │
│       │    └─────┘   │                                                    │
│       │              ├──▶ [MP2]                                           │
│       └──▶ ┌─────┐   │                                                    │
│            │ E3  │ ──┘                                                    │
│            └─────┘                                                        │
│                                                                           │
│  F1 ──┬──▶ ┌─────┐                                                        │
│       │    │ F2  │                                                        │
│       │    └─────┘                                                        │
│       │                                                                   │
│       └──▶ ┌─────┐                                                        │
│            │ F3  │                                                        │
│            └─────┘                                                        │
│                                                                           │
│  G1 ──┬──▶ ┌─────┐   ┌─────┐   ┌─────┐                                   │
│       │    │ G2  │   │ G3  │   │ G4  │   ← Parallel backends              │
│       │    └─────┘   └─────┘   └─────┘                                   │
│       │    Notion    Slack     HubSpot                                    │
│                                                                           │
└───────────────────────────────────────────────────────────────────────────┘
```

**Tasks:**

| Task | Description | Complexity | Files | Service |
|------|-------------|------------|-------|---------|
| E2 | Create vault token retrieval endpoint | M | `app/api/v1/endpoints/vault.py` | Control |
| E3 | Create vault token refresh endpoint | M | `app/api/v1/endpoints/vault.py` | Control |
| F2 | Create OAuth configuration | M | `app/core/oauth_config.py` | Control |
| F3 | Create OAuth endpoints | M | `app/api/v1/endpoints/oauth.py` | Control |
| G2 | Implement Notion REST API calls | L | `app/backends/notion_client.py` | Gateway |
| G3 | Implement Slack REST API calls | L | `app/backends/slack_client.py` | Gateway |
| G4 | Implement HubSpot REST API calls | L | `app/backends/hubspot_client.py` | Gateway |

**Execute Commands:**

```bash
# Worktree 1 (Control): E2, E3, F2, F3
cd ../mvp-prod-control/deeptrail-control
# Work on vault and OAuth endpoints

# Worktree 2 (Gateway): G2, G3, G4 (can be further parallelized)
cd ../mvp-prod-gateway/deeptrail-gateway
# Work on backend clients
```

---

### Batch P1-B3: Credential Injection

**Wave Analysis:**
- **Parallel Tasks:** 2 (H1, H2)
- **Sequential Dependencies:** E2, E3 (vault API ready = MP2)
- **Estimated Duration:** 2-3 hours
- **Service:** `deeptrail-gateway`

**Dependency Graph:**

```
┌───────────────────────────────────────────────────────────┐
│                        P1-B3                              │
├───────────────────────────────────────────────────────────┤
│                                                           │
│  [MP2] ──▶ ┌─────┐ ──▶ ┌─────┐ ──▶ [MP3]                 │
│            │ H1  │     │ H2  │                            │
│            └─────┘     └─────┘                            │
│                                                           │
└───────────────────────────────────────────────────────────┘
```

**Tasks:**

| Task | Description | Complexity | Files |
|------|-------------|------------|-------|
| H1 | Connect CredentialInjector to vault API | M | `app/middleware/credential_injection.py` |
| H2 | Implement token refresh in injector | M | `app/middleware/credential_injection.py` |

**Execute Commands:**

```bash
cd deeptrail-gateway
# Modify app/middleware/credential_injection.py
# - _fetch_from_vault() calls Control Plane API
# - _refresh_token() calls Control Plane refresh endpoint
```

**Validation (MP3 Criteria):**

```bash
# Test with real OAuth tokens
# 1. Connect a service with real OAuth
# 2. Run agent tool call
# 3. Verify real API response

# Integration test
pytest tests/integration/test_credential_injection.py -v
```

---

## Phase 2: Production Hardening

> **Prerequisite:** MP3 (P1 complete)

### Batch P2-B1: Core Security Features

**Wave Analysis:**
- **Parallel Tasks:** 4 (I1, J1, J2, K1)
- **Sequential Dependencies:** MP3
- **Estimated Duration:** 4-6 hours
- **Services:** Both

**Dependency Graph:**

```
┌───────────────────────────────────────────────────────────┐
│                        P2-B1                              │
├───────────────────────────────────────────────────────────┤
│                                                           │
│  [MP3] ──▶ ┌─────┐   ┌─────┐   ┌─────┐   ┌─────┐         │
│            │ I1  │   │ J1  │   │ J2  │   │ K1  │         │
│            └─────┘   └─────┘   └─────┘   └─────┘         │
│            Control   Gateway   Gateway   Control          │
│            IdP       PII       Prompt    TaskToken        │
│                                                           │
└───────────────────────────────────────────────────────────┘
```

**Tasks:**

| Task | Description | Complexity | Files | Service |
|------|-------------|------------|-------|---------|
| I1 | Create IdP service | L | `app/services/idp_service.py` | Control |
| J1 | Implement result filtering | M | `app/middleware/result_filter.py` | Gateway |
| J2 | Implement prompt injection detection | M | `app/security/prompt_injection.py` | Gateway |
| K1 | Create TaskToken model | M | `app/models/task_token.py` | Control |

---

### Batch P2-B2: Endpoints & Integration

**Wave Analysis:**
- **Parallel Tasks:** 4 (I2, J3, K2, K3)
- **Sequential Dependencies:** I1, J1, J2, K1
- **Estimated Duration:** 4-6 hours
- **Services:** Both

**Dependency Graph:**

```
┌───────────────────────────────────────────────────────────┐
│                        P2-B2                              │
├───────────────────────────────────────────────────────────┤
│                                                           │
│  I1 ──▶ ┌─────┐         K1 ──▶ ┌─────┐ ──▶ ┌─────┐       │
│         │ I2  │                │ K2  │     │ K3  │       │
│         └─────┘                └─────┘     └─────┘       │
│         SSO                    TaskSvc     TaskAPI        │
│                                                           │
│         ┌─────┐                                           │
│         │ J3  │   Keycloak Token Exchange                 │
│         └─────┘                                           │
│                                                           │
└───────────────────────────────────────────────────────────┘
```

**Tasks:**

| Task | Description | Complexity | Files | Service |
|------|-------------|------------|-------|---------|
| I2 | Create SSO endpoints | M | `app/api/v1/endpoints/sso.py` | Control |
| J3 | Implement Keycloak token exchange | L | `app/security/token_exchange.py` | Gateway |
| K2 | Create TaskService | M | `app/services/task_service.py` | Control |
| K3 | Create task endpoints | M | `app/api/v1/endpoints/tasks.py` | Control |

---

## Parallelism Summary

| Phase | Max Parallel Instances | Worktrees Needed |
|-------|------------------------|------------------|
| P0 | 4 | 1 (Control only) |
| P1 | 2-7 | 2 (Control + Gateway) |
| P2 | 4 | 2 (Control + Gateway) |

### Optimal Execution Strategy

**P0:** Single developer, 4 parallel tasks max
- Batches are short, stay in main worktree

**P1:** Two developers (or two Claude instances)
- Developer 1: Control Plane (E*, F*)
- Developer 2: Gateway (G*, H*)
- Merge at MP2 and MP3

**P2:** Two developers (or two Claude instances)
- Developer 1: Control Plane (I*, K*)
- Developer 2: Gateway (J*)

---

## Quick Start Commands

### Start P0

```bash
# Ensure services are up
docker compose up -d

# Start Batch P0-B1 (4 parallel tasks)
# Task A1:
/execute-task WS-A1

# Task B1:
/execute-task WS-B1

# Task C1:
/execute-task WS-C1

# Task C2:
/execute-task WS-C2
```

### Start P1 (after MP1)

```bash
# Setup worktrees
git worktree add ../mvp-prod-control -b feature/mvp-prod-control dev
git worktree add ../mvp-prod-gateway -b feature/mvp-prod-gateway dev

# Control Plane instance
cd ../mvp-prod-control
/execute-task WS-E1
/execute-task WS-F1

# Gateway instance
cd ../mvp-prod-gateway
/execute-task WS-G1
```

### Start P2 (after MP3)

```bash
# Merge P1 branches
git checkout dev
git merge feature/mvp-prod-control feature/mvp-prod-gateway

# Create P2 branches
git checkout -b feature/mvp-prod-p2-control
git checkout -b feature/mvp-prod-p2-gateway

# Execute P2 batches
/execute-task WS-I1
/execute-task WS-J1
# ...
```

---

*Document generated: February 2026*
