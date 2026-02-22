# MVP Production Readiness: Batch Execution Plan

> **Generated from:** [mvp-production-readiness-breakdown.md](../../mvp-production-readiness-breakdown.md)
>
> **Source Plan:** [mvp_production_readiness.plan.md](../../../.cursor/plans/mvp_production_readiness.plan.md)
>
> **Last Updated:** February 22, 2026
>
> **Latest Change:** Added Phase 1.5 (Integration Bug Fixes) - 6 tasks to fix issues found during Integration Validation Guide testing

---

## Quick Reference

| Batch | Total Tasks | Complete | Waves | Status | Worktrees |
|-------|-------------|----------|-------|--------|-----------|
| P0-B1 | 4 | 4 ✅ | 1 | ✅ Complete | main (control only) |
| P0-B2 | 2 | 2 ✅ | 1 | ✅ Complete | main (control only) |
| P0-B3 | 3 | 3 ✅ | 2 | ✅ Complete | main (control only) |
| P0-B4 | 2 | 2 ✅ | 1 | ✅ Complete (MP1!) | main |
| P1-B1 | 3 | 3 ✅ | 1 | ✅ Complete | mvp-prod-control, mvp-prod-gateway |
| P1-B2 | 7 | 7 ✅ | 1 | ✅ Complete (MP2!) | mvp-prod-control, mvp-prod-gateway |
| P1-B3 | 2 | 2 ✅ | 2 | ✅ Complete (MP3!) | mvp-prod-gateway |
| **P1.5-B1** | 6 | 0 | 2 | ⏳ **NEW** Bug Fixes | mvp-prod-control, mvp-prod-gateway |
| P2-B1 | 4 | 0 | 1 | ⏳ Pending | mvp-prod-control, mvp-prod-gateway |
| P2-B2 | 4 | 0 | 2 | ⏳ Pending | mvp-prod-control, mvp-prod-gateway |

**Total Tasks:** 37 | **Completed:** 23 (P0 + P1) | **Remaining:** 14 (P1.5 + P2)

---

## Worktree Reference

| Worktree | Path | Branch | Workstreams | Phase |
|----------|------|--------|-------------|-------|
| **main** | `/Users/imaxxs/repositories/deepsecure-mvp` | `dev` | A, B, C, D | P0 |
| **mvp-prod-control** | `../mvp-prod-control` | `feature/mvp-prod-control` | E, F, I, K (K1-K5) | P1, P1.5, P2 |
| **mvp-prod-gateway** | `../mvp-prod-gateway` | `feature/mvp-prod-gateway` | G, H, J (J2) | P1, P1.5, P2 |

**Worktree Setup (run before P1):**

```bash
# From main repo
cd /Users/imaxxs/repositories/deepsecure-mvp
git worktree add ../mvp-prod-control -b feature/mvp-prod-control dev
git worktree add ../mvp-prod-gateway -b feature/mvp-prod-gateway dev

# Copy .cursor commands to each worktree
cp -r .cursor ../mvp-prod-control/
cp -r .cursor ../mvp-prod-gateway/
```

---

## Phase Distribution

```
┌───────────────────────────────────────────────────────────────────────────────────────────────┐
│                                      TIMELINE OVERVIEW                                         │
├───────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                               │
│  PHASE 0 (E2E)      PHASE 1 (Integration)     P1.5 (Bug Fixes)    PHASE 2 (Harden)           │
│  ──────────────     ─────────────────────     ────────────────    ────────────────           │
│  P0-B1 │...│ P0-B4 │ P1-B1 │ P1-B2 │ P1-B3 │    P1.5-B1       │ P2-B1 │ P2-B2 │            │
│   ✅   │ ✅ │  ✅   │  ✅   │  ✅   │  ✅   │      ⏳          │  ⏳   │  ⏳   │            │
│                    [MP1]         [MP2]  [MP3]                 [MP3.5]                        │
│                                                                                               │
│  Phase 1.5 addresses bugs found during Integration Validation Guide testing (Steps 1-18)     │
│                                                                                               │
│  Total: ~27-40 hours estimated                                                                │
└───────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Phase 0: Enable E2E Tests

> **Status:** ✅ **COMPLETE** (E2E demo passed)
> **Worktree:** main repo only (no worktrees needed)
> **Important:** P0 verified E2E flow works. Unit tests may still have pre-existing failures.

### Batch P0-B1: Foundation Schemas & Fixes (4 tasks) ✅

### Dependencies

| Task | Description | Dependencies | Worktree | Status |
|------|-------------|--------------|----------|--------|
| A1 | Create user auth schemas | None | main | ✅ |
| B1 | Create service connection schemas | None | main | ✅ |
| C1 | Verify agent registration schema | None | main | ✅ |
| C2 | Update delegation response format | None | main | ✅ |

### Wave Analysis

| Wave | Control Plane | Gateway |
|------|---------------|---------|
| **1** | A1, B1, C1, C2 | (none) |

### Visual Dependency Graph

```
CONTROL (main repo)                    GATEWAY
───────────────────                    ───────
    A1   B1   C1   C2                  (none - P0 is control only)
    │    │    │    │
    └────┴────┴────┘
            │
     [Batch P0-B1 Complete]
            │
            ▼
        Batch P0-B2
```

### Execution Strategy

All 4 tasks run in parallel in the main repo. No worktrees needed for P0.

### Commands

```bash
# ═══════════════════════════════════════════════════════════════
# BATCH P0-B1 - WAVE 1 (All Parallel) ✅ COMPLETE
# ═══════════════════════════════════════════════════════════════

# --- Create Task Specs (from main repo, in Plan mode) ---
cd /Users/imaxxs/repositories/deepsecure-mvp
/create-task-spec P0-B1 mvp-production-readiness

# --- Create Task Tickets (from main repo) ---
/create-task-ticket WS-A1 mvp-production-readiness
/create-task-ticket WS-B1 mvp-production-readiness
/create-task-ticket WS-C1 mvp-production-readiness
/create-task-ticket WS-C2 mvp-production-readiness

# --- Execute Tasks (parallel in separate terminals) ---

# Terminal 1:
cd /Users/imaxxs/repositories/deepsecure-mvp/deeptrail-control
/execute-task WS-A1 mvp-production-readiness
/complete-task WS-A1 mvp-production-readiness

# Terminal 2:
cd /Users/imaxxs/repositories/deepsecure-mvp/deeptrail-control
/execute-task WS-B1 mvp-production-readiness
/complete-task WS-B1 mvp-production-readiness

# Terminal 3:
cd /Users/imaxxs/repositories/deepsecure-mvp/deeptrail-control
/execute-task WS-C1 mvp-production-readiness
/complete-task WS-C1 mvp-production-readiness

# Terminal 4:
cd /Users/imaxxs/repositories/deepsecure-mvp/deeptrail-control
/execute-task WS-C2 mvp-production-readiness
/complete-task WS-C2 mvp-production-readiness
```

### Validation

```bash
# Run schema tests (Note: pre-existing failures may exist)
cd /Users/imaxxs/repositories/deepsecure-mvp/deeptrail-control
pytest tests/schemas/ -v

# Check delegation endpoint response
grep -r "delegation_token" app/api/v1/endpoints/delegation.py
```

### Summary

| Metric | Value |
|--------|-------|
| **Parallelism** | 100% (all 4 tasks parallel) |
| **Waves** | 1 |
| **Bottleneck** | None |
| **Merge Point** | None |
| **Unblocks** | Batch P0-B2 (A2, B2) |

---

### Batch P0-B2: Core Services (2 tasks) ✅

### Dependencies

| Task | Description | Dependencies | Worktree | Status |
|------|-------------|--------------|----------|--------|
| A2 | Create UserAuthService | A1 ✅ | main | ✅ |
| B2 | Extend ConnectedServiceService | B1 ✅ | main | ✅ |

### Wave Analysis

| Wave | Control Plane | Gateway |
|------|---------------|---------|
| **1** | A2, B2 | (none) |

### Visual Dependency Graph

```
CONTROL (main repo)                    GATEWAY
───────────────────                    ───────
    A1 ✅    B1 ✅                      (none)
    │         │
    ▼         ▼
   A2 ✅     B2 ✅
    │         │
    └────┬────┘
         │
  [Batch P0-B2 Complete]
         │
         ▼
     Batch P0-B3
```

### Execution Strategy

Both tasks run in parallel after P0-B1 completes.

### Commands

```bash
# ═══════════════════════════════════════════════════════════════
# BATCH P0-B2 - WAVE 1 (All Parallel) ✅ COMPLETE
# ═══════════════════════════════════════════════════════════════

# --- Create Task Specs (from main repo, in Plan mode) ---
cd /Users/imaxxs/repositories/deepsecure-mvp
/create-task-spec P0-B2 mvp-production-readiness

# --- Create Task Tickets ---
/create-task-ticket WS-A2 mvp-production-readiness
/create-task-ticket WS-B2 mvp-production-readiness

# --- Execute Tasks (parallel in separate terminals) ---

# Terminal 1:
cd /Users/imaxxs/repositories/deepsecure-mvp/deeptrail-control
/execute-task WS-A2 mvp-production-readiness
/complete-task WS-A2 mvp-production-readiness

# Terminal 2:
cd /Users/imaxxs/repositories/deepsecure-mvp/deeptrail-control
/execute-task WS-B2 mvp-production-readiness
/complete-task WS-B2 mvp-production-readiness
```

### Validation

```bash
# Run service tests
cd /Users/imaxxs/repositories/deepsecure-mvp/deeptrail-control
pytest tests/services/test_user_auth_service.py -v
pytest tests/services/test_connected_service_service.py -v
```

### Summary

| Metric | Value |
|--------|-------|
| **Parallelism** | 100% (both tasks parallel) |
| **Waves** | 1 |
| **Bottleneck** | None |
| **Merge Point** | None |
| **Unblocks** | Batch P0-B3 (A3, B3, C3) |

---

### Batch P0-B3: API Endpoints (3 tasks) ✅

### Dependencies

| Task | Description | Dependencies | Worktree | Status |
|------|-------------|--------------|----------|--------|
| A3 | Create login endpoint | A2 ✅ | main | ✅ |
| B3 | Create service connection endpoint | B2 ✅ | main | ✅ |
| C3 | Wire routes to API router | A3, B3 | main | ✅ |

### Wave Analysis

| Wave | Control Plane | Gateway |
|------|---------------|---------|
| **1** | A3, B3 | (none) |
| **2** | C3 | (none) |

### Visual Dependency Graph

```
CONTROL (main repo)                    GATEWAY
───────────────────                    ───────
    A2 ✅    B2 ✅                      (none)
    │         │
    ▼         ▼
   A3 ✅     B3 ✅   ← Wave 1 (parallel)
    │         │
    └────┬────┘
         │
         ▼
       C3 ✅         ← Wave 2 (wires A3 + B3)
         │
  [Batch P0-B3 Complete]
         │
         ▼
     Batch P0-B4
```

### Execution Strategy

Wave 1: A3 and B3 run in parallel.
Wave 2: C3 runs after both A3 and B3 complete (wires them to router).

### Commands

```bash
# ═══════════════════════════════════════════════════════════════
# BATCH P0-B3 - WAVE 1 (A3, B3 Parallel) ✅ COMPLETE
# ═══════════════════════════════════════════════════════════════

# --- Create Task Specs ---
cd /Users/imaxxs/repositories/deepsecure-mvp
/create-task-spec P0-B3 mvp-production-readiness

# --- Create Task Tickets ---
/create-task-ticket WS-A3 mvp-production-readiness
/create-task-ticket WS-B3 mvp-production-readiness
/create-task-ticket WS-C3 mvp-production-readiness

# ───────────────────────────────────────────────────────────────
# WAVE 1: A3, B3
# ───────────────────────────────────────────────────────────────

# Terminal 1:
cd /Users/imaxxs/repositories/deepsecure-mvp/deeptrail-control
/execute-task WS-A3 mvp-production-readiness
/complete-task WS-A3 mvp-production-readiness

# Terminal 2:
cd /Users/imaxxs/repositories/deepsecure-mvp/deeptrail-control
/execute-task WS-B3 mvp-production-readiness
/complete-task WS-B3 mvp-production-readiness

# ⏸️ WAIT: A3 and B3 must complete before C3

# ───────────────────────────────────────────────────────────────
# WAVE 2: C3
# ───────────────────────────────────────────────────────────────

cd /Users/imaxxs/repositories/deepsecure-mvp/deeptrail-control
/execute-task WS-C3 mvp-production-readiness
/complete-task WS-C3 mvp-production-readiness
```

### Validation

```bash
# Start services
cd /Users/imaxxs/repositories/deepsecure-mvp
docker compose up -d db redis deeptrail-control
sleep 15

# Verify Control Plane is healthy
curl -sf http://localhost:8000/health && echo "✅ Control Plane healthy"

# Test login endpoint and capture token
# Note: Login returns "token" field, not "access_token"
USER_TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"sarah@acme.com","password":"test123"}' | jq -r '.token')
echo "User token: ${USER_TOKEN:0:20}..."

# Test service connection endpoint
curl -s -X POST http://localhost:8000/api/v1/users/me/services/connect \
  -H "Authorization: Bearer $USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"service_id":"notion","oauth_token":{"access_token":"test"}}' | jq .

# Cleanup
docker compose down
```

### Summary

| Metric | Value |
|--------|-------|
| **Parallelism** | 67% (2 parallel in Wave 1, 1 in Wave 2) |
| **Waves** | 2 |
| **Bottleneck** | C3 (must wait for A3 + B3) |
| **Merge Point** | None |
| **Unblocks** | Batch P0-B4 (D1, D2) |

---

### Batch P0-B4: E2E Validation (2 tasks) ✅ MP1

### Dependencies

| Task | Description | Dependencies | Worktree | Status |
|------|-------------|--------------|----------|--------|
| D1 | Update E2E test endpoint paths | C3 ✅ | main | ✅ |
| D2 | Run and validate E2E demo | D1 | main | ✅ |

### Wave Analysis

| Wave | Control Plane | Gateway | Root (tests) |
|------|---------------|---------|--------------|
| **1** | (none) | (none) | D1, D2 |

### Visual Dependency Graph

```
CONTROL (main repo)                    ROOT (demos/)
───────────────────                    ─────────────
       C3 ✅                               │
         │                                 │
         └─────────────────────────▶ D1 ✅
                                        │
                                        ▼
                                     D2 ✅
                                        │
                                 [MP1: E2E Flow Verified]
                                        │
                                        ▼
                                 Phase 1 Unlocked
```

### Execution Strategy

Sequential: D1 then D2. Both run from main repo root.

### Commands

```bash
# ═══════════════════════════════════════════════════════════════
# BATCH P0-B4 - E2E Validation ✅ COMPLETE (MP1 REACHED!)
# ═══════════════════════════════════════════════════════════════

# --- Create Task Tickets ---
cd /Users/imaxxs/repositories/deepsecure-mvp
/create-task-ticket WS-D1 mvp-production-readiness
/create-task-ticket WS-D2 mvp-production-readiness

# --- Execute Tasks (sequential) ---
/execute-task WS-D1 mvp-production-readiness
/complete-task WS-D1 mvp-production-readiness

/execute-task WS-D2 mvp-production-readiness
/complete-task WS-D2 mvp-production-readiness

# --- Sync Status ---
/sync-worktree-status mvp-production-readiness
```

### Validation (MP1 Criteria) ✅ PASSED

```bash
# ALL steps should pass
python demos/demo_sarah_journey_e2e.py

# Expected output (VERIFIED Feb 15, 2026):
# ✅ Step 1: Enterprise Registration
# ✅ Step 2: Sarah Authenticates
# ✅ Step 3: Sarah Connects Services
# ✅ Step 4: Sarah Registers Agent
# ✅ Step 5: Sarah Creates Delegation
# ✅ Step 6: Agent Requests Challenge
# ✅ Step 7: Agent Authenticates
# ✅ Step 8: Agent Connects to Gateway
# ✅ Step 9: Agent Executes Tools
# ✅ Step 10: Sarah Reviews Audit

# Interactive mode
python demos/demo_sarah_journey_interactive.py --auto
```

### Summary

| Metric | Value |
|--------|-------|
| **Parallelism** | 0% (sequential D1 → D2) |
| **Waves** | 1 (but sequential within) |
| **Bottleneck** | D1 (E2E path updates) |
| **Merge Point** | **MP1: E2E Flow Verified** ✅ |
| **Unblocks** | Phase 1 (P1-B1: E1, F1, G1) |

---

## Phase 1: Real Backend Integration

> **Prerequisite:** MP1 (P0 complete) ✅
> **Status:** 🔄 IN PROGRESS (P1-B1 ✅, P1-B2 ✅, P1-B3 ⏳)
> **Worktrees:** mvp-prod-control, mvp-prod-gateway

### Worktree Setup (Required for P1)

```bash
# From main repo - run ONCE before starting P1
cd /Users/imaxxs/repositories/deepsecure-mvp
git worktree add ../mvp-prod-control -b feature/mvp-prod-control dev
git worktree add ../mvp-prod-gateway -b feature/mvp-prod-gateway dev

# Copy .cursor commands to each worktree
cp -r .cursor ../mvp-prod-control/
cp -r .cursor ../mvp-prod-gateway/
```

---

### Batch P1-B1: Foundation Services (3 tasks) ✅ COMPLETE

### Dependencies

| Task | Description | Dependencies | Worktree | Status |
|------|-------------|--------------|----------|--------|
| E1 | Enhance vault client for token storage | MP1 ✅ | mvp-prod-control | ✅ |
| F1 | Create OAuth service | MP1 ✅ | mvp-prod-control | ✅ |
| G1 | Add backend configuration | MP1 ✅ | mvp-prod-gateway | ✅ |

### Wave Analysis

| Wave | Control Plane (mvp-prod-control) | Gateway (mvp-prod-gateway) |
|------|----------------------------------|----------------------------|
| **1** | E1, F1 | G1 |

### Visual Dependency Graph

```
CONTROL (mvp-prod-control)             GATEWAY (mvp-prod-gateway)
──────────────────────────             ─────────────────────────

[MP1] ─────┬───────────────────────────┬────────────────────────
           │                           │
           ▼                           ▼
    E1          F1                    G1
    │           │                      │
    └─────┬─────┘                      │
          │                            │
          └──────────┬─────────────────┘
                     │
              [Batch P1-B1 Complete]
                     │
                     ▼
                 Batch P1-B2
```

### Execution Strategy

All 3 tasks run in parallel across 2 worktrees. Control handles E1 + F1, Gateway handles G1.

### Commands

```bash
# ═══════════════════════════════════════════════════════════════
# BATCH P1-B1 - WAVE 1 (All Parallel)
# ═══════════════════════════════════════════════════════════════

# --- Create Task Specs (from main repo, in Plan mode) ---
cd /Users/imaxxs/repositories/deepsecure-mvp
/plan
/create-task-spec P1-B1 mvp-production-readiness

# --- Create Task Tickets (from main repo) ---
/create-task-ticket WS-E1 mvp-production-readiness
/create-task-ticket WS-F1 mvp-production-readiness
/create-task-ticket WS-G1 mvp-production-readiness

# ───────────────────────────────────────────────────────────────
# WAVE 1: E1, F1 (Control) + G1 (Gateway)
# ───────────────────────────────────────────────────────────────

# Terminal 1: mvp-prod-control
cd /Users/imaxxs/repositories/mvp-prod-control
/execute-task WS-E1 mvp-production-readiness
/complete-task WS-E1 mvp-production-readiness
/execute-task WS-F1 mvp-production-readiness
/complete-task WS-F1 mvp-production-readiness

# Terminal 2: mvp-prod-gateway
cd /Users/imaxxs/repositories/mvp-prod-gateway
/execute-task WS-G1 mvp-production-readiness
/complete-task WS-G1 mvp-production-readiness

# --- Sync Status (from main repo) ---
cd /Users/imaxxs/repositories/deepsecure-mvp
/sync-worktree-status mvp-production-readiness
```

### Validation

```bash
# Control: Test vault client
cd /Users/imaxxs/repositories/mvp-prod-control/deeptrail-control
pytest tests/services/test_vault_client.py -v

# Control: Test OAuth service
pytest tests/services/test_oauth_service.py -v

# Gateway: Verify config (check backend API URLs are configured)
cd /Users/imaxxs/repositories/mvp-prod-gateway/deeptrail-gateway
grep -r "NOTION_BASE_URL\|SLACK_BASE_URL" app/core/config.py
```

### Summary

| Metric | Value |
|--------|-------|
| **Parallelism** | 100% (all 3 tasks parallel) |
| **Waves** | 1 |
| **Bottleneck** | None |
| **Merge Point** | None |
| **Unblocks** | Batch P1-B2 (E2, E3, F2, F3, G2, G3, G4) |

---

### Batch P1-B2: Integration Components (7 tasks) ✅ COMPLETE

### Dependencies

| Task | Description | Dependencies | Worktree | Status |
|------|-------------|--------------|----------|--------|
| E2 | Create vault token retrieval endpoint | E1 ✅ | mvp-prod-control | ✅ |
| E3 | Create vault token refresh endpoint | E1 ✅ | mvp-prod-control | ✅ |
| F2 | Create OAuth configuration | F1 ✅ | mvp-prod-control | ✅ |
| F3 | Create OAuth endpoints | F1 ✅ | mvp-prod-control | ✅ |
| G2 | Implement Notion REST API calls | G1 ✅ | mvp-prod-gateway | ✅ |
| G3 | Implement Slack REST API calls | G1 ✅ | mvp-prod-gateway | ✅ |
| G4 | Implement HubSpot REST API calls | G1 ✅ | mvp-prod-gateway | ✅ |

### Wave Analysis

| Wave | Control Plane (mvp-prod-control) | Gateway (mvp-prod-gateway) |
|------|----------------------------------|----------------------------|
| **1** | E2, E3, F2, F3 | G2, G3, G4 |

### Visual Dependency Graph

```
CONTROL (mvp-prod-control)             GATEWAY (mvp-prod-gateway)
──────────────────────────             ─────────────────────────

E1 ──┬──▶ E2 ──┐                       G1 ──┬──▶ G2 (Notion)
     │         │                            │
     └──▶ E3 ──┼──▶ [MP2]                   ├──▶ G3 (Slack)
               │                            │
F1 ──┬──▶ F2   │                            └──▶ G4 (HubSpot)
     │         │                                  │
     └──▶ F3 ──┘                                  │
               │                                  │
               └──────────────┬───────────────────┘
                              │
                       [Batch P1-B2 Complete]
                              │
                              ▼
                       [MP2: Vault API Ready]
                              │
                              ▼
                          Batch P1-B3
```

### Execution Strategy

All 7 tasks run in parallel across 2 worktrees:
- Control: E2, E3, F2, F3 (4 tasks, can be 2-4 parallel Claude instances)
- Gateway: G2, G3, G4 (3 tasks, can be 3 parallel Claude instances)

### Commands

```bash
# ═══════════════════════════════════════════════════════════════
# BATCH P1-B2 - WAVE 1 (All 7 Parallel)
# ═══════════════════════════════════════════════════════════════

# --- Create Task Specs (from main repo, in Plan mode) ---
cd /Users/imaxxs/repositories/deepsecure-mvp
/plan
/create-task-spec P1-B2 mvp-production-readiness

# --- Create Task Tickets (from main repo) ---
/create-task-ticket WS-E2 mvp-production-readiness
/create-task-ticket WS-E3 mvp-production-readiness
/create-task-ticket WS-F2 mvp-production-readiness
/create-task-ticket WS-F3 mvp-production-readiness
/create-task-ticket WS-G2 mvp-production-readiness
/create-task-ticket WS-G3 mvp-production-readiness
/create-task-ticket WS-G4 mvp-production-readiness

# ───────────────────────────────────────────────────────────────
# WAVE 1: Control (E2, E3, F2, F3) + Gateway (G2, G3, G4)
# ───────────────────────────────────────────────────────────────

# Terminal 1: mvp-prod-control (E*)
cd /Users/imaxxs/repositories/mvp-prod-control
/execute-task WS-E2 mvp-production-readiness
/complete-task WS-E2 mvp-production-readiness
/execute-task WS-E3 mvp-production-readiness
/complete-task WS-E3 mvp-production-readiness

# Terminal 2: mvp-prod-control (F*)
cd /Users/imaxxs/repositories/mvp-prod-control
/execute-task WS-F2 mvp-production-readiness
/complete-task WS-F2 mvp-production-readiness
/execute-task WS-F3 mvp-production-readiness
/complete-task WS-F3 mvp-production-readiness

# Terminal 3: mvp-prod-gateway (G2 - Notion)
cd /Users/imaxxs/repositories/mvp-prod-gateway
/execute-task WS-G2 mvp-production-readiness
/complete-task WS-G2 mvp-production-readiness

# Terminal 4: mvp-prod-gateway (G3 - Slack)
cd /Users/imaxxs/repositories/mvp-prod-gateway
/execute-task WS-G3 mvp-production-readiness
/complete-task WS-G3 mvp-production-readiness

# Terminal 5: mvp-prod-gateway (G4 - HubSpot)
cd /Users/imaxxs/repositories/mvp-prod-gateway
/execute-task WS-G4 mvp-production-readiness
/complete-task WS-G4 mvp-production-readiness

# --- Sync Status (from main repo) ---
cd /Users/imaxxs/repositories/deepsecure-mvp
/sync-worktree-status mvp-production-readiness
```

### Validation

**⚠️ IMPORTANT:** These validation commands test endpoints created by P1-B2 tasks. 
They only work AFTER:
1. All P1-B2 tasks are implemented in worktrees
2. Code is merged to main branch  
3. Docker containers are rebuilt: `docker compose build deeptrail-control`

#### Pre-Merge Validation (Unit Tests Only)

Run these in worktrees before merging:

```bash
# Control worktree: Test vault client and OAuth modules
cd /Users/imaxxs/repositories/mvp-prod-control/deeptrail-control
pytest tests/services/test_vault_client.py -v      # Vault client tests
pytest tests/services/test_oauth_service.py -v     # OAuth service tests
pytest tests/core/test_oauth_config.py -v          # OAuth config tests
pytest tests/api/test_vault_tokens.py -v           # Vault token endpoints
pytest tests/api/test_oauth.py -v                  # OAuth endpoints

# Gateway worktree: Test backend API clients
cd /Users/imaxxs/repositories/mvp-prod-gateway/deeptrail-gateway
pytest tests/backends/ -v                          # All backend client tests
```

#### Post-Merge Validation (Integration Tests)

Run these AFTER merging and rebuilding containers:

```bash
# ═══════════════════════════════════════════════════════════════
# P1-B2 VALIDATION - Vault API + Backend Clients (POST-MERGE)
# ═══════════════════════════════════════════════════════════════
# All commands should return 200 (or 404 if no data stored yet)
# ═══════════════════════════════════════════════════════════════

# 0. Rebuild containers with new code (includes OAuth env vars)
cd /Users/imaxxs/repositories/deepsecure-mvp
docker compose build deeptrail-control
docker compose up -d db redis deeptrail-control
sleep 15

# 1. Verify Control Plane is healthy
curl -sf http://localhost:8000/health && echo "✅ Control Plane healthy"

# 2. Verify new endpoints exist
curl -s http://localhost:8000/openapi.json | jq '.paths | keys | map(select(contains("vault/tokens") or contains("oauth")))' 
# Expected: ["/api/v1/oauth/{service_id}/authorize", "/api/v1/vault/tokens/{service_id}", ...]

# ─────────────────────────────────────────────────────────────────
# SETUP: Login and connect a service
# ─────────────────────────────────────────────────────────────────

# 3. Get user token via login
USER_TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"sarah@acme.com","password":"test_password"}' | jq -r '.token')
echo "User token: ${USER_TOKEN:0:20}..."

# 4. Connect a service (creates the token reference in database)
curl -s -X POST http://localhost:8000/api/v1/users/me/services/connect \
  -H "Authorization: Bearer $USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "service_id": "notion",
    "oauth_token": {
      "access_token": "test_notion_token_123",
      "token_type": "bearer",
      "scope": "read_pages",
      "refresh_token": "test_refresh_token_456",
      "expires_at": "2026-02-19T22:06:59.361415+00:00"
    }
  }' | jq .
# Expected: 200 {"success": true, "connection": {...}}

# ─────────────────────────────────────────────────────────────────
# TEST E2: Vault Token Retrieval (requires Agent JWT)
# ─────────────────────────────────────────────────────────────────

# 5a. Generate Ed25519 keypair for agent
python3 -c "
from nacl.signing import SigningKey
import base64
private_key = SigningKey.generate()
public_key = private_key.verify_key
print(f'PRIVATE_KEY_HEX={private_key.encode().hex()}')
print(f'PUBLIC_KEY_B64={base64.b64encode(public_key.encode()).decode()}')
" > /tmp/agent_keys.env
source /tmp/agent_keys.env

# 5b. Register agent with public key
curl -s -X POST http://localhost:8000/api/v1/agents/ \
  -H "Authorization: Bearer $USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"agent_id\": \"test-agent-001\",
    \"name\": \"Test Agent\",
    \"public_key\": \"$PUBLIC_KEY_B64\"
  }" | jq .

# 5c. Create delegation (grant permissions to agent)
curl -s -X POST http://localhost:8000/api/v1/auth/delegate \
  -H "Authorization: Bearer $USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "test-agent-001",
    "permissions": ["notion:pages:search", "notion:pages:read"]
  }' | jq .

# 5d. Request challenge
CHALLENGE=$(curl -s -X POST http://localhost:8000/api/v1/auth/agent/challenge \
  -H "Content-Type: application/json" \
  -d '{"agent_id": "test-agent-001"}' | jq -r '.challenge')
echo "Challenge: $CHALLENGE"

# 5e. Sign challenge with Ed25519 private key
SIGNATURE=$(python3 -c "
from nacl.signing import SigningKey
import base64
private_key = SigningKey(bytes.fromhex('$PRIVATE_KEY_HEX'))
signed = private_key.sign('$CHALLENGE'.encode())
print(base64.urlsafe_b64encode(signed.signature).decode())
")

# 5f. Verify and get Agent JWT
AGENT_JWT=$(curl -s -X POST http://localhost:8000/api/v1/auth/agent/verify \
  -H "Content-Type: application/json" \
  -d "{
    \"agent_id\": \"test-agent-001\",
    \"challenge\": \"$CHALLENGE\",
    \"signature\": \"$SIGNATURE\"
  }" | jq -r '.access_token')
echo "Agent JWT: ${AGENT_JWT:0:30}..."

# 5g. TEST E2: Vault token retrieval with Agent JWT
curl -s -w "\nHTTP Status: %{http_code}\n" \
  -X GET "http://localhost:8000/api/v1/vault/tokens/notion" \
  -H "Authorization: Bearer $AGENT_JWT"
# Expected: 200 {"service_id": "notion", "access_token": "test_notion_token_123", ...}

# ─────────────────────────────────────────────────────────────────
# TEST E3: Vault Token Refresh (requires Internal API Token)
# ─────────────────────────────────────────────────────────────────

# 6. Test refresh with internal token (Gateway→Control communication)
# Internal token value from docker-compose.yml: gateway-internal-secret-token
curl -s -w "\nHTTP Status: %{http_code}\n" \
  -X POST "http://localhost:8000/api/v1/vault/tokens/notion/refresh" \
  -H "Authorization: Bearer gateway-internal-secret-token" \
  -H "X-User-ID: sarah@acme.com" \
  -H "Content-Type: application/json" \
  -d '{"force": false}'
# Expected: 200 {"refreshed": true/false, ...} or 400 if no refresh_token stored

# ─────────────────────────────────────────────────────────────────
# TEST F3: OAuth Authorize (requires OAuth env vars - already configured)
# ─────────────────────────────────────────────────────────────────

# 7. Test OAuth authorize URL generation
curl -s -w "\nHTTP Status: %{http_code}\n" \
  -X GET "http://localhost:8000/api/v1/oauth/notion/authorize" \
  -H "Authorization: Bearer $USER_TOKEN"
# Expected: 200 {"authorization_url": "https://api.notion.com/v1/oauth/authorize?...", "state": "..."}

# ─────────────────────────────────────────────────────────────────
# CLEANUP
# ─────────────────────────────────────────────────────────────────

# 8. Cleanup
rm -f /tmp/agent_keys.env
docker compose down

echo "✅ P1-B2 Post-Merge Validation Complete - All endpoints return 200"
```

### Summary

| Metric | Value |
|--------|-------|
| **Parallelism** | 100% (all 7 tasks parallel) |
| **Waves** | 1 |
| **Bottleneck** | None |
| **Merge Point** | **MP2: Vault API Ready** (E2 + E3 complete) |
| **Unblocks** | Batch P1-B3 (H1, H2) |

---

### ⚠️ Post-Batch P1-B2 Verification (MANDATORY)

**Before proceeding to P1-B3, you MUST verify status consistency.**

```bash
# Run from main repo
cd /Users/imaxxs/repositories/deepsecure-mvp

# Verify batch completion
/verify-batch-completion P1-B2 mvp-production-readiness
```

**Verification Checklist:**
- [ ] All 7 P1-B2 tasks have completion reports in `reports/`
- [ ] STATUS.md shows all tasks as "✅ Complete"
- [ ] WORKSTREAM.md shows all tasks with correct status and report links
- [ ] BATCH_EXECUTION_PLAN.md Quick Reference shows P1-B2 as "✅ Complete"
- [ ] MERGE_POINTS.md shows MP2 as "✅ Reached"

**DO NOT proceed to P1-B3 until verification passes.**

If verification fails, run:
```bash
/sync-worktree-status mvp-production-readiness
```

---

### Batch P1-B3: Credential Injection (2 tasks) - MP2, MP3 ✅

### Dependencies

| Task | Description | Dependencies | Worktree | Status |
|------|-------------|--------------|----------|--------|
| H1 | Connect CredentialInjector to vault API | MP2 (E2, E3) | mvp-prod-gateway | ✅ |
| H2 | Implement token refresh in injector | H1 | mvp-prod-gateway | ✅ |

### Wave Analysis

| Wave | Control Plane | Gateway (mvp-prod-gateway) |
|------|---------------|----------------------------|
| **1** | (none) | H1 |
| **2** | (none) | H2 |

### Visual Dependency Graph

```
CONTROL (mvp-prod-control)             GATEWAY (mvp-prod-gateway)
──────────────────────────             ─────────────────────────

[MP2: Vault API Ready] ────────────────▶ H1 ✅
                                          │
                                          ▼
                                         H2 ✅
                                          │
                                   [MP3: P1 Complete] ✅
                                          │
                                          ▼
                                    Phase 1.5 Unlocked
                                   (Integration Bug Fixes)
```

### Execution Strategy

Sequential within Gateway worktree: H1 → H2.
H1 must complete before H2 can start.

### Commands

```bash
# ═══════════════════════════════════════════════════════════════
# BATCH P1-B3 - Credential Injection
# ═══════════════════════════════════════════════════════════════

# --- Create Task Specs (from main repo, in Plan mode) ---
cd /Users/imaxxs/repositories/deepsecure-mvp
/plan
/create-task-spec P1-B3 mvp-production-readiness

# --- Create Task Tickets (from main repo) ---
/create-task-ticket WS-H1 mvp-production-readiness
/create-task-ticket WS-H2 mvp-production-readiness

# ───────────────────────────────────────────────────────────────
# WAVE 1: H1
# ───────────────────────────────────────────────────────────────

# Terminal 1: mvp-prod-gateway
cd /Users/imaxxs/repositories/mvp-prod-gateway
/execute-task WS-H1 mvp-production-readiness
/complete-task WS-H1 mvp-production-readiness

# ⏸️ WAIT: H1 must complete before H2

# ───────────────────────────────────────────────────────────────
# WAVE 2: H2
# ───────────────────────────────────────────────────────────────

/execute-task WS-H2 mvp-production-readiness
/complete-task WS-H2 mvp-production-readiness

# --- Sync Status (from main repo) ---
cd /Users/imaxxs/repositories/deepsecure-mvp
/sync-worktree-status mvp-production-readiness
```

### Validation (MP3 Criteria)

```bash
# ═══════════════════════════════════════════════════════════════
# P1-B3 VALIDATION - Credential Injection (MP3 Criteria)
# ═══════════════════════════════════════════════════════════════

# 1. Start full stack
cd /Users/imaxxs/repositories/deepsecure-mvp
docker compose up -d
sleep 20

# 2. Verify services are healthy
curl -sf http://localhost:8000/health && echo "✅ Control Plane healthy"
curl -sf http://localhost:8002/health && echo "✅ Gateway healthy"

# 3. Get user token via login
# Note: Login returns "token" field, not "access_token"
USER_TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"sarah@acme.com","password":"test_password"}' | jq -r '.token')
echo "User token: ${USER_TOKEN:0:20}..."

# 4. Connect service with real OAuth token (stores in vault + connected_services DB)
curl -s -X POST http://localhost:8000/api/v1/users/me/services/connect \
  -H "Authorization: Bearer $USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "service_id": "notion",
    "oauth_token": {
      "access_token": "'"${NOTION_API_KEY:-test_notion_token}"'",
      "token_type": "bearer",
      "scope": "read_pages search_content",
      "expires_at": "2027-02-22T00:00:00.000000+00:00"
    }
  }' | jq .

# 5. Complete agent auth flow to get Agent JWT
# Generate Ed25519 keypair
python3 -c "
from nacl.signing import SigningKey
import base64
private_key = SigningKey.generate()
public_key = private_key.verify_key
print(f'PRIVATE_KEY_HEX={private_key.encode().hex()}')
print(f'PUBLIC_KEY_B64={base64.b64encode(public_key.encode()).decode()}')
" > /tmp/agent_keys.env
source /tmp/agent_keys.env

# Register agent
curl -s -X POST http://localhost:8000/api/v1/agents/ \
  -H "Authorization: Bearer $USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"agent_id\": \"p1b3-test-agent\",
    \"name\": \"P1-B3 Test Agent\",
    \"public_key\": \"$PUBLIC_KEY_B64\"
  }" | jq .

# Create delegation
curl -s -X POST http://localhost:8000/api/v1/auth/delegate \
  -H "Authorization: Bearer $USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "p1b3-test-agent",
    "permissions": ["notion:pages:search", "notion:pages:read"]
  }' | jq .

# Challenge-response
CHALLENGE=$(curl -s -X POST http://localhost:8000/api/v1/auth/agent/challenge \
  -H "Content-Type: application/json" \
  -d '{"agent_id": "p1b3-test-agent"}' | jq -r '.challenge')

SIGNATURE=$(python3 -c "
from nacl.signing import SigningKey
import base64
private_key = SigningKey(bytes.fromhex('$PRIVATE_KEY_HEX'))
signed = private_key.sign('$CHALLENGE'.encode())
print(base64.urlsafe_b64encode(signed.signature).decode())
")

AGENT_JWT=$(curl -s -X POST http://localhost:8000/api/v1/auth/agent/verify \
  -H "Content-Type: application/json" \
  -d "{
    \"agent_id\": \"p1b3-test-agent\",
    \"challenge\": \"$CHALLENGE\",
    \"signature\": \"$SIGNATURE\"
  }" | jq -r '.access_token')
echo "Agent JWT: ${AGENT_JWT:0:30}..."

# ─────────────────────────────────────────────────────────────────
# 6. Initialize MCP Session (REQUIRED before tools/call)
# ─────────────────────────────────────────────────────────────────
echo "Initializing MCP session..."
INIT_RESULT=$(curl -s -X POST http://localhost:8002/mcp \
  -H "Authorization: Bearer $AGENT_JWT" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "initialize",
    "id": 1,
    "params": {
      "protocolVersion": "2024-11-05",
      "capabilities": {},
      "clientInfo": {"name": "p1b3-test-agent", "version": "1.0.0"}
    }
  }')
echo "Initialize result: $INIT_RESULT"
# Expected: {"jsonrpc":"2.0","id":1,"result":{"protocolVersion":"2024-11-05","serverInfo":{...}}}

# 7. List available tools (optional but verifies session)
echo "Listing tools..."
TOOLS_RESULT=$(curl -s -X POST http://localhost:8002/mcp \
  -H "Authorization: Bearer $AGENT_JWT" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/list",
    "id": 2,
    "params": {}
  }')
echo "Tools available: $(echo $TOOLS_RESULT | jq -r '.result.tools | length') tools"

# 8. Make tool call through Gateway (should inject real token)
TOOL_RESULT=$(curl -s -X POST http://localhost:8002/mcp \
  -H "Authorization: Bearer $AGENT_JWT" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "id": 3,
    "params": {"name": "notion.search_pages", "arguments": {"query": "test"}}
  }')
echo "Tool result: $TOOL_RESULT"

# 9. Verify NOT a mock response
if [[ "$TOOL_RESULT" != *"MVP Mock"* ]] && [[ "$TOOL_RESULT" != *"error"* ]]; then
  echo "✅ Real API response (credential injection working)"
else
  echo "❌ Still returning mock response or error"
  echo "$TOOL_RESULT" | jq .
fi

# 10. Run E2E demo
python demos/demo_sarah_journey_e2e.py --verbose

# 11. Run credential injection tests
cd /Users/imaxxs/repositories/mvp-prod-gateway/deeptrail-gateway
pytest tests/middleware/test_credential_injection.py -v

# 12. Cleanup
rm -f /tmp/agent_keys.env
cd /Users/imaxxs/repositories/deepsecure-mvp
docker compose down

echo "✅ P1-B3 Validation Complete"
```

---

### Real API Integration Testing

With P1-B3 (WS-H1, WS-H2) complete, you can now test with **real Notion/Slack API keys** instead of mock tokens. This section explains how to set up and validate real API integration.

#### Prerequisites

| Service | What You Need | How to Get It |
|---------|---------------|---------------|
| **Notion** | Internal Integration API Key | [notion.so/my-integrations](https://www.notion.so/my-integrations) |
| **Slack** | Bot User OAuth Token | [api.slack.com/apps](https://api.slack.com/apps) → OAuth & Permissions |
| **HubSpot** | Private App Access Token | [developers.hubspot.com](https://developers.hubspot.com) → Private Apps |

---

#### Option A: Notion API Integration Testing

##### Step 1: Create Notion Internal Integration

1. Go to [https://www.notion.so/my-integrations](https://www.notion.so/my-integrations)
2. Click **"+ New integration"**
3. Fill in:
   - **Name**: `DeepSecure Test Integration`
   - **Associated workspace**: Select your workspace
   - **Capabilities**: Check "Read content", "Update content", "Insert content"
4. Click **"Submit"** → Copy the **Internal Integration Token** (starts with `secret_`)

##### Step 2: Share a Page with the Integration

1. Open any Notion page you want to access
2. Click **"Share"** (top right)
3. Click **"Invite"** → Search for `DeepSecure Test Integration`
4. Click **"Invite"**

> **Note:** The integration can ONLY access pages explicitly shared with it.

##### Step 3: Set Environment Variable and Test

```bash
# ═══════════════════════════════════════════════════════════════
# REAL NOTION API TESTING
# ═══════════════════════════════════════════════════════════════

# Set your REAL Notion API key
export NOTION_API_KEY="secret_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

# Verify the key format
if [[ "$NOTION_API_KEY" != secret_* ]]; then
  echo "❌ Invalid Notion API key format (should start with 'secret_')"
  exit 1
fi
echo "✅ Notion API key set: ${NOTION_API_KEY:0:12}..."

# Start services
cd /Users/imaxxs/repositories/deepsecure-mvp
docker compose up -d
sleep 20

# Verify services
curl -sf http://localhost:8000/health && echo "✅ Control Plane healthy"
curl -sf http://localhost:8002/health && echo "✅ Gateway healthy"

# Login
USER_TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"sarah@acme.com","password":"test_password"}' | jq -r '.token')
echo "User token: ${USER_TOKEN:0:20}..."

# Connect Notion with REAL API key (stored encrypted in vault)
CONNECT_RESULT=$(curl -s -X POST http://localhost:8000/api/v1/users/me/services/connect \
  -H "Authorization: Bearer $USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"service_id\": \"notion\",
    \"oauth_token\": {
      \"access_token\": \"$NOTION_API_KEY\",
      \"token_type\": \"bearer\",
      \"scope\": \"read_pages search_content\",
      \"expires_at\": \"2027-02-22T00:00:00.000000+00:00\"
    }
  }")
echo "Connection result: $CONNECT_RESULT" | jq .

# Generate agent keys
python3 -c "
from nacl.signing import SigningKey
import base64
private_key = SigningKey.generate()
public_key = private_key.verify_key
print(f'PRIVATE_KEY_HEX={private_key.encode().hex()}')
print(f'PUBLIC_KEY_B64={base64.b64encode(public_key.encode()).decode()}')
" > /tmp/agent_keys.env
source /tmp/agent_keys.env

# Register agent with unique ID
AGENT_ID="notion-real-api-test-$(date +%s)"
curl -s -X POST http://localhost:8000/api/v1/agents/ \
  -H "Authorization: Bearer $USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"agent_id\": \"$AGENT_ID\",
    \"name\": \"Notion Real API Test Agent\",
    \"public_key\": \"$PUBLIC_KEY_B64\"
  }" | jq .

# Create delegation for Notion tools
curl -s -X POST http://localhost:8000/api/v1/auth/delegate \
  -H "Authorization: Bearer $USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"agent_id\": \"$AGENT_ID\",
    \"permissions\": [\"notion:pages:search\", \"notion:pages:read\", \"notion:databases:query\"]
  }" | jq .

# Challenge-response authentication
CHALLENGE=$(curl -s -X POST http://localhost:8000/api/v1/auth/agent/challenge \
  -H "Content-Type: application/json" \
  -d "{\"agent_id\": \"$AGENT_ID\"}" | jq -r '.challenge')

SIGNATURE=$(python3 -c "
from nacl.signing import SigningKey
import base64
private_key = SigningKey(bytes.fromhex('$PRIVATE_KEY_HEX'))
signed = private_key.sign('$CHALLENGE'.encode())
print(base64.urlsafe_b64encode(signed.signature).decode())
")

AGENT_JWT=$(curl -s -X POST http://localhost:8000/api/v1/auth/agent/verify \
  -H "Content-Type: application/json" \
  -d "{
    \"agent_id\": \"$AGENT_ID\",
    \"challenge\": \"$CHALLENGE\",
    \"signature\": \"$SIGNATURE\"
  }" | jq -r '.access_token')
echo "Agent JWT: ${AGENT_JWT:0:30}..."

# Initialize MCP session
curl -s -X POST http://localhost:8002/mcp \
  -H "Authorization: Bearer $AGENT_JWT" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "initialize",
    "id": 1,
    "params": {
      "protocolVersion": "2024-11-05",
      "capabilities": {},
      "clientInfo": {"name": "notion-test", "version": "1.0.0"}
    }
  }' | jq .

# ─────────────────────────────────────────────────────────────────
# REAL API CALL: Search Notion Pages
# ─────────────────────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "Making REAL Notion API call through Gateway..."
echo "═══════════════════════════════════════════════════════════════"

NOTION_RESULT=$(curl -s -X POST http://localhost:8002/mcp \
  -H "Authorization: Bearer $AGENT_JWT" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "id": 2,
    "params": {
      "name": "notion.search_pages",
      "arguments": {"query": ""}
    }
  }')

echo "Notion API Response:"
echo "$NOTION_RESULT" | jq .

# Verify it's a REAL response (not mock)
if echo "$NOTION_RESULT" | grep -q '"object":"list"'; then
  echo ""
  echo "✅ SUCCESS: Real Notion API response received!"
  echo "   - Contains Notion 'object' field"
  echo "   - Results from your actual workspace"
elif echo "$NOTION_RESULT" | grep -q 'MVP Mock'; then
  echo ""
  echo "❌ FAILED: Still returning mock response"
  echo "   Check WS-H1 implementation (credential injection)"
elif echo "$NOTION_RESULT" | grep -q 'unauthorized'; then
  echo ""
  echo "❌ FAILED: Notion API returned unauthorized"
  echo "   - Verify your NOTION_API_KEY is valid"
  echo "   - Ensure you've shared pages with the integration"
else
  echo ""
  echo "⚠️  UNKNOWN: Unexpected response format"
  echo "   Review the response above"
fi

# Cleanup
rm -f /tmp/agent_keys.env
echo ""
echo "✅ Real Notion API test complete"
```

##### Expected Real API Response

When connected with a **real Notion API key**, you should see actual workspace data:

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "{\"object\":\"list\",\"results\":[{\"object\":\"page\",\"id\":\"abc123...\",\"created_time\":\"2025-01-15T10:00:00.000Z\",\"last_edited_time\":\"2026-02-10T14:30:00.000Z\",\"properties\":{...}}],\"next_cursor\":null,\"has_more\":false}"
      }
    ],
    "isError": false
  }
}
```

---

#### Option B: Slack API Integration Testing

##### Step 1: Create Slack App

1. Go to [https://api.slack.com/apps](https://api.slack.com/apps)
2. Click **"Create New App"** → **"From scratch"**
3. Name: `DeepSecure Test Bot`, Workspace: Select yours
4. Click **"Create App"**

##### Step 2: Configure OAuth Scopes

1. Go to **"OAuth & Permissions"** in the left sidebar
2. Under **"Bot Token Scopes"**, add:
   - `channels:read` - List channels
   - `chat:write` - Send messages
   - `search:read` - Search messages
   - `users:read` - List users
3. Click **"Install to Workspace"** → **"Allow"**
4. Copy the **Bot User OAuth Token** (starts with `xoxb-`)

##### Step 3: Test with Real Slack API

```bash
# ═══════════════════════════════════════════════════════════════
# REAL SLACK API TESTING
# ═══════════════════════════════════════════════════════════════

# Set your REAL Slack Bot Token
export SLACK_BOT_TOKEN="xoxb-xxxxxxxxxxxx-xxxxxxxxxxxx-xxxxxxxxxxxxxxxxxxxxxxxx"

# Verify format
if [[ "$SLACK_BOT_TOKEN" != xoxb-* ]]; then
  echo "❌ Invalid Slack token format (should start with 'xoxb-')"
  exit 1
fi
echo "✅ Slack Bot Token set: ${SLACK_BOT_TOKEN:0:15}..."

# (Assume services already running from Notion test, or start them)

# Connect Slack with REAL token
curl -s -X POST http://localhost:8000/api/v1/users/me/services/connect \
  -H "Authorization: Bearer $USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"service_id\": \"slack\",
    \"oauth_token\": {
      \"access_token\": \"$SLACK_BOT_TOKEN\",
      \"token_type\": \"bearer\",
      \"scope\": \"channels:read chat:write search:read users:read\"
    }
  }" | jq .

# Create delegation for Slack tools
curl -s -X POST http://localhost:8000/api/v1/auth/delegate \
  -H "Authorization: Bearer $USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"agent_id\": \"$AGENT_ID\",
    \"permissions\": [\"slack:channels:list\", \"slack:messages:search\", \"slack:users:list\"]
  }" | jq .

# Re-authenticate agent to get updated permissions
CHALLENGE=$(curl -s -X POST http://localhost:8000/api/v1/auth/agent/challenge \
  -H "Content-Type: application/json" \
  -d "{\"agent_id\": \"$AGENT_ID\"}" | jq -r '.challenge')

SIGNATURE=$(python3 -c "
from nacl.signing import SigningKey
import base64
private_key = SigningKey(bytes.fromhex('$PRIVATE_KEY_HEX'))
signed = private_key.sign('$CHALLENGE'.encode())
print(base64.urlsafe_b64encode(signed.signature).decode())
")

AGENT_JWT=$(curl -s -X POST http://localhost:8000/api/v1/auth/agent/verify \
  -H "Content-Type: application/json" \
  -d "{
    \"agent_id\": \"$AGENT_ID\",
    \"challenge\": \"$CHALLENGE\",
    \"signature\": \"$SIGNATURE\"
  }" | jq -r '.access_token')

# Re-initialize MCP session with new JWT
curl -s -X POST http://localhost:8002/mcp \
  -H "Authorization: Bearer $AGENT_JWT" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "initialize",
    "id": 1,
    "params": {
      "protocolVersion": "2024-11-05",
      "capabilities": {},
      "clientInfo": {"name": "slack-test", "version": "1.0.0"}
    }
  }' | jq .

# ─────────────────────────────────────────────────────────────────
# REAL API CALL: List Slack Channels
# ─────────────────────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "Making REAL Slack API call through Gateway..."
echo "═══════════════════════════════════════════════════════════════"

SLACK_RESULT=$(curl -s -X POST http://localhost:8002/mcp \
  -H "Authorization: Bearer $AGENT_JWT" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "id": 3,
    "params": {
      "name": "slack.list_channels",
      "arguments": {"limit": 10}
    }
  }')

echo "Slack API Response:"
echo "$SLACK_RESULT" | jq .

# Verify real response
if echo "$SLACK_RESULT" | grep -q '"ok":true'; then
  echo ""
  echo "✅ SUCCESS: Real Slack API response received!"
elif echo "$SLACK_RESULT" | grep -q 'MVP Mock'; then
  echo ""
  echo "❌ FAILED: Still returning mock response"
else
  echo ""
  echo "⚠️  Check response format"
fi
```

---

#### Option C: HubSpot API Integration Testing

##### Step 1: Create HubSpot Private App

1. Go to [https://app.hubspot.com](https://app.hubspot.com)
2. Settings → Integrations → Private Apps
3. Click **"Create a private app"**
4. Name: `DeepSecure Test`
5. Under **Scopes**, enable:
   - `crm.objects.contacts.read`
   - `crm.objects.contacts.write`
   - `crm.objects.deals.read`
   - `crm.objects.deals.write`
6. Click **"Create app"** → Copy the **Access token**

##### Step 2: Test with Real HubSpot API

```bash
# ═══════════════════════════════════════════════════════════════
# REAL HUBSPOT API TESTING
# ═══════════════════════════════════════════════════════════════

export HUBSPOT_ACCESS_TOKEN="pat-na1-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"

# Connect HubSpot
curl -s -X POST http://localhost:8000/api/v1/users/me/services/connect \
  -H "Authorization: Bearer $USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"service_id\": \"hubspot\",
    \"oauth_token\": {
      \"access_token\": \"$HUBSPOT_ACCESS_TOKEN\",
      \"token_type\": \"bearer\",
      \"scope\": \"crm.objects.contacts.read crm.objects.deals.read\"
    }
  }" | jq .

# Create delegation for HubSpot
curl -s -X POST http://localhost:8000/api/v1/auth/delegate \
  -H "Authorization: Bearer $USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"agent_id\": \"$AGENT_ID\",
    \"permissions\": [\"hubspot:contacts:list\", \"hubspot:contacts:search\", \"hubspot:deals:list\"]
  }" | jq .

# (Re-authenticate agent, initialize MCP session as shown above)

# Make real HubSpot call
HUBSPOT_RESULT=$(curl -s -X POST http://localhost:8002/mcp \
  -H "Authorization: Bearer $AGENT_JWT" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "id": 4,
    "params": {
      "name": "hubspot.list_contacts",
      "arguments": {"limit": 10}
    }
  }')

echo "HubSpot API Response:"
echo "$HUBSPOT_RESULT" | jq .
```

---

#### Environment Variables Summary

For real API testing, set these environment variables before running validation:

```bash
# ═══════════════════════════════════════════════════════════════
# REAL API KEYS (for production validation)
# ═══════════════════════════════════════════════════════════════

# Notion Internal Integration Token
export NOTION_API_KEY="secret_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

# Slack Bot User OAuth Token  
export SLACK_BOT_TOKEN="xoxb-xxxxxxxxxxxx-xxxxxxxxxxxx-xxxxxxxxxxxxxxxxxxxxxxxx"

# HubSpot Private App Access Token
export HUBSPOT_ACCESS_TOKEN="pat-na1-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"

# Verify all are set
echo "Notion: ${NOTION_API_KEY:+✅ Set}${NOTION_API_KEY:-❌ Not set}"
echo "Slack:  ${SLACK_BOT_TOKEN:+✅ Set}${SLACK_BOT_TOKEN:-❌ Not set}"
echo "HubSpot: ${HUBSPOT_ACCESS_TOKEN:+✅ Set}${HUBSPOT_ACCESS_TOKEN:-❌ Not set}"
```

---

#### Mock vs Real Testing Matrix

| Test Mode | API Key | What Happens | Use Case |
|-----------|---------|--------------|----------|
| **Mock** | `test_notion_token` (default) | Returns simulated responses | CI/CD, unit tests |
| **Real** | `secret_xxx...` | Calls actual Notion API | Integration validation |

| Component | Mock Mode | Real Mode |
|-----------|-----------|-----------|
| Token storage | ✅ Encrypted in vault | ✅ Encrypted in vault |
| Credential injection | ✅ Token retrieved | ✅ Token retrieved |
| API call | ❌ Mock response | ✅ Real API call |
| Response | `"[Notion] Found 5 results..."` | `{"object":"list","results":[...]}` |

---

### Summary

| Metric | Value |
|--------|-------|
| **Status** | ✅ **COMPLETE** (Feb 18, 2026) |
| **Parallelism** | 0% (sequential H1 → H2) |
| **Waves** | 2 |
| **Bottleneck** | H1 (must complete first) |
| **Merge Point** | **MP3: P1 Complete** ✅ |
| **Unblocks** | **Phase 1.5** (P1.5-B1: WS-J2, WS-K1, WS-K2, WS-K3, WS-K4, WS-K5) |
| **Real API Testing** | ✅ Available (see "Real API Integration Testing" above) |

#### What P1-B3 Enables

| Capability | Before P1-B3 | After P1-B3 |
|------------|--------------|-------------|
| Credential Injection | Mock tokens | Real vault tokens |
| Token Refresh | Not implemented | Full refresh flow |
| Real API Calls | Not possible | ✅ Supported |
| E2E Testing | Mock responses only | Real API responses |

#### What Testing Revealed (P1.5)

After P1-B3, testing via [Integration Validation Guide](../../INTEGRATION_VALIDATION_GUIDE.md) revealed bugs requiring a new Phase 1.5 before Phase 2:

| Issue Found | Integration Guide Step | Fix |
|-------------|------------------------|-----|
| Tools filtered out / wrong names | Step 15-16 | WS-J2 |
| Tokens lost on restart | Step 17 | WS-K1 |
| Stale credentials | Step 17 | WS-K2 |
| No permission validation | Step 9 | WS-K3, WS-K4, WS-K5 |

---

## Phase 1.5: Integration Testing Bug Fixes

> **Prerequisite:** MP3 (P1 complete)
> **Status:** ⏳ PENDING
> **Worktrees:** mvp-prod-control, mvp-prod-gateway
> **Source:** Bugs discovered during [Integration Validation Guide](../../INTEGRATION_VALIDATION_GUIDE.md) testing (Steps 1-18)
> **Architecture Docs:** 
> - [PERMISSION_FLOW_ARCHITECTURE.md](../../architecture/PERMISSION_FLOW_ARCHITECTURE.md)
> - [MVP_ARCHITECTURE_DEEP_DIVE.md](../../architecture/MVP_ARCHITECTURE_DEEP_DIVE.md)

### Background

After completing Phase 1 (P1-B3), testing with the Integration Validation Guide revealed several issues:

| Issue | Discovered In | Impact |
|-------|---------------|--------|
| Tool name derivation mismatch | Step 16 (MCP List Tools) | Tools filtered out, minimal schemas |
| In-memory vault ephemeral | Container restart | Tokens lost, "Service not connected" errors |
| Stale credential cache | Token updates | 60s cache TTL causes stale tokens |
| No scope→permission mapping | Step 9 (Delegation) | Can't validate delegated permissions |
| No delegation validation | Step 9 (Delegation) | Invalid permissions accepted |
| No permission discovery | Step 9 (Delegation) | User must manually know permissions |

These issues must be fixed before Phase 2 (Production Hardening) can proceed.

---

### Batch P1.5-B1: Integration Bug Fixes (6 tasks) - MP3.5

### Dependencies

| Task | Description | Dependencies | Worktree | Status | Spec |
|------|-------------|--------------|----------|--------|------|
| WS-J2 | Fix tool name derivation and cache alignment | MP3 | mvp-prod-gateway | ⏳ | [WS-J2-spec.md](./specs/WS-J2-spec.md) |
| WS-K1 | Persistent Vault - Store OAuth tokens in PostgreSQL | MP3 | mvp-prod-control | ⏳ | [WS-K1-spec.md](./specs/WS-K1-spec.md) |
| WS-K2 | Cache Invalidation via Redis Pub/Sub | WS-K1 | mvp-prod-control, mvp-prod-gateway | ⏳ | [WS-K2-spec.md](./specs/WS-K2-spec.md) |
| WS-K3 | Scope-to-Permission Mapper | MP3 | mvp-prod-control | ⏳ | [WS-K3-spec.md](./specs/WS-K3-spec.md) |
| WS-K4 | Delegation Permission Validation | WS-K3 | mvp-prod-control | ⏳ | [WS-K4-spec.md](./specs/WS-K4-spec.md) |
| WS-K5 | Available Permissions Endpoint | WS-K3 | mvp-prod-control | ⏳ | [WS-K5-spec.md](./specs/WS-K5-spec.md) |

### Wave Analysis

| Wave | Control Plane (mvp-prod-control) | Gateway (mvp-prod-gateway) |
|------|----------------------------------|----------------------------|
| **1** | WS-K1, WS-K3 | WS-J2 |
| **2** | WS-K2 (Control publisher), WS-K4, WS-K5 | WS-K2 (Gateway subscriber) |

### Visual Dependency Graph

```
CONTROL (mvp-prod-control)                    GATEWAY (mvp-prod-gateway)
──────────────────────────                    ─────────────────────────

[MP3] ─────┬───────────────────────────────────┬───────────────────────
           │                                   │
           ▼                                   ▼
    WS-K1 (Vault)       WS-K3 (ScopeMapper)   WS-J2 (Tool Names)
           │                   │                      │
           │                   ├──────────────────────┘
           │                   │
           ▼                   ▼
    WS-K2 (Cache) ◄───────────┤
    (publisher)               │
           │                  ├───► WS-K4 (Delegation Validation)
           │                  │
           │                  └───► WS-K5 (Available Permissions)
           │
           └──────────────────────► WS-K2 (Cache)
                                   (subscriber)
                                        │
                                        ▼
                               [Batch P1.5-B1 Complete]
                                       [MP3.5]
                                        │
                                        ▼
                                   Phase 2 Unblocked
```

### Issue-to-Fix Mapping

| Integration Guide Step | Issue | Root Cause | Fix |
|------------------------|-------|------------|-----|
| Step 15-16 | Tools filtered out / minimal schemas | Tool names derived wrong in initialize.py | **WS-J2** |
| Step 17 | "Unauthorized: API token is invalid" after restart | In-memory vault lost tokens | **WS-K1** |
| Step 17 | Stale credentials after token update | 60s cache TTL in CredentialInjector | **WS-K2** |
| Step 9 | Can delegate any permission | No scope→permission mapping | **WS-K3** |
| Step 9 | Invalid permissions accepted | No validation in delegation endpoint | **WS-K4** |
| Step 9 | User must manually know permissions | No discovery endpoint | **WS-K5** |

### Execution Strategy

**Wave 1 (Parallel - 3 tasks):**
- Control: WS-K1 (Persistent Vault) + WS-K3 (ScopeMapper) 
- Gateway: WS-J2 (Tool Name Fix)

**Wave 2 (Parallel - 3 tasks, depends on Wave 1):**
- Control: WS-K2 (publisher), WS-K4, WS-K5
- Gateway: WS-K2 (subscriber)

### Commands

```bash
# ═══════════════════════════════════════════════════════════════
# BATCH P1.5-B1 - Integration Bug Fixes
# ═══════════════════════════════════════════════════════════════

# Specs already created in docs/workstreams/mvp-production-readiness/specs/
# Create task tickets if not yet done:

# --- Create Task Tickets (from main repo) ---
cd /Users/imaxxs/repositories/deepsecure-mvp
/create-task-ticket WS-J2 mvp-production-readiness
/create-task-ticket WS-K1 mvp-production-readiness
/create-task-ticket WS-K2 mvp-production-readiness
/create-task-ticket WS-K3 mvp-production-readiness
/create-task-ticket WS-K4 mvp-production-readiness
/create-task-ticket WS-K5 mvp-production-readiness

# ───────────────────────────────────────────────────────────────
# WAVE 1: Control (WS-K1, WS-K3) + Gateway (WS-J2)
# ───────────────────────────────────────────────────────────────

# Terminal 1: mvp-prod-control
cd /Users/imaxxs/repositories/mvp-prod-control
/execute-task WS-K1 mvp-production-readiness
# Then:
/execute-task WS-K3 mvp-production-readiness

# Terminal 2: mvp-prod-gateway
cd /Users/imaxxs/repositories/mvp-prod-gateway
/execute-task WS-J2 mvp-production-readiness

# ───────────────────────────────────────────────────────────────
# WAVE 2: Control (WS-K2 pub, WS-K4, WS-K5) + Gateway (WS-K2 sub)
# ───────────────────────────────────────────────────────────────

# Terminal 1: mvp-prod-control (after Wave 1)
/execute-task WS-K4 mvp-production-readiness
/execute-task WS-K5 mvp-production-readiness
/execute-task WS-K2 mvp-production-readiness  # Control Plane publisher

# Terminal 2: mvp-prod-gateway (after WS-J2)
/execute-task WS-K2 mvp-production-readiness  # Gateway subscriber
```

### Validation (MP3.5 Criteria)

After completing all 6 tasks, re-run Integration Validation Guide steps 1-18:

```bash
# Full validation
cd /Users/imaxxs/repositories/deepsecure-mvp

# Rebuild containers
docker compose build --no-cache deeptrail-control deeptrail-gateway
docker compose up -d

# Run integration steps
# Follow docs/INTEGRATION_VALIDATION_GUIDE.md Steps 1-18

# Expected results:
# - Step 16: All 5 tools with full inputSchema
# - Step 17: Real Notion API responses (not mock)
# - Container restart: Tokens persist
# - Step 9: Invalid permissions rejected with helpful error
```

### Summary

| Metric | Value |
|--------|-------|
| **Status** | ⏳ Pending |
| **Tasks** | 6 |
| **Waves** | 2 |
| **Parallelism** | 50% (3 tasks per wave) |
| **Merge Point** | **MP3.5: Integration Bugs Fixed** |
| **Unblocks** | Phase 2 (P2-B1) |

---

## Phase 2: Production Hardening

> **Prerequisite:** MP3.5 (P1.5 complete - Integration bugs fixed)
> **Status:** ⏳ PENDING
> **Worktrees:** mvp-prod-control, mvp-prod-gateway (continue from P1.5)

---

### Batch P2-B1: Core Security Features (4 tasks)

### Dependencies

| Task | Description | Dependencies | Worktree | Status |
|------|-------------|--------------|----------|--------|
| I1 | Create IdP service | MP3.5 | mvp-prod-control | ⏳ |
| J4 | Implement result filtering (PII) | MP3.5 | mvp-prod-gateway | ⏳ |
| J5 | Implement prompt injection detection | MP3.5 | mvp-prod-gateway | ⏳ |
| K6 | Create TaskToken model | MP3.5 | mvp-prod-control | ⏳ |

> **Note:** Task IDs J4, J5, K6 avoid conflict with P1.5 bug fix tasks (WS-J2, WS-K1-K5)

### Wave Analysis

| Wave | Control Plane (mvp-prod-control) | Gateway (mvp-prod-gateway) |
|------|----------------------------------|----------------------------|
| **1** | I1, K6 | J4, J5 |

### Visual Dependency Graph

```
CONTROL (mvp-prod-control)             GATEWAY (mvp-prod-gateway)
──────────────────────────             ─────────────────────────

[MP3.5] ───┬───────────────────────────┬────────────────────────
(P1.5 Done)│                           │
           ▼                           ▼
    I1 (IdP)    K6 (TaskToken)        J4 (PII)    J5 (Prompt)
    │           │                      │           │
    └─────┬─────┘                      └─────┬─────┘
          │                                  │
          └──────────────┬───────────────────┘
                         │
                  [Batch P2-B1 Complete]
                         │
                         ▼
                     Batch P2-B2
```

### Execution Strategy

All 4 tasks run in parallel across 2 worktrees:
- Control: I1, K6 (2 tasks)
- Gateway: J4, J5 (2 tasks)

### Commands

```bash
# ═══════════════════════════════════════════════════════════════
# BATCH P2-B1 - WAVE 1 (All 4 Parallel)
# ═══════════════════════════════════════════════════════════════

# --- Create Task Specs (from main repo, in Plan mode) ---
cd /Users/imaxxs/repositories/deepsecure-mvp
/plan
/create-task-spec P2-B1 mvp-production-readiness

# --- Create Task Tickets (from main repo) ---
/create-task-ticket WS-I1 mvp-production-readiness
/create-task-ticket WS-J4 mvp-production-readiness
/create-task-ticket WS-J5 mvp-production-readiness
/create-task-ticket WS-K6 mvp-production-readiness

# ───────────────────────────────────────────────────────────────
# WAVE 1: Control (I1, K6) + Gateway (J4, J5)
# ───────────────────────────────────────────────────────────────

# Terminal 1: mvp-prod-control
cd /Users/imaxxs/repositories/mvp-prod-control
/execute-task WS-I1 mvp-production-readiness
/complete-task WS-I1 mvp-production-readiness
/execute-task WS-K6 mvp-production-readiness
/complete-task WS-K6 mvp-production-readiness

# Terminal 2: mvp-prod-gateway
cd /Users/imaxxs/repositories/mvp-prod-gateway
/execute-task WS-J4 mvp-production-readiness
/complete-task WS-J4 mvp-production-readiness
/execute-task WS-J5 mvp-production-readiness
/complete-task WS-J5 mvp-production-readiness

# --- Sync Status (from main repo) ---
cd /Users/imaxxs/repositories/deepsecure-mvp
/sync-worktree-status mvp-production-readiness
```

### Validation

```bash
# Control: Test IdP service
cd /Users/imaxxs/repositories/mvp-prod-control/deeptrail-control
pytest tests/services/test_idp_service.py -v

# Control: Test TaskToken model
pytest tests/models/test_task_token.py -v

# Gateway: Test PII filtering
cd /Users/imaxxs/repositories/mvp-prod-gateway/deeptrail-gateway
pytest tests/middleware/test_result_filter.py -v

# Gateway: Test prompt injection
pytest tests/security/test_prompt_injection.py -v
```

### Summary

| Metric | Value |
|--------|-------|
| **Parallelism** | 100% (all 4 tasks parallel) |
| **Waves** | 1 |
| **Bottleneck** | None |
| **Merge Point** | None |
| **Unblocks** | Batch P2-B2 (I2, J6, K7, K8) |

---

### Batch P2-B2: Endpoints & Integration (4 tasks) - FINAL

### Dependencies

| Task | Description | Dependencies | Worktree | Status |
|------|-------------|--------------|----------|--------|
| I2 | Create SSO endpoints | I1 | mvp-prod-control | ⏳ |
| J6 | Implement Keycloak token exchange | J4, J5 | mvp-prod-gateway | ⏳ |
| K7 | Create TaskService | K6 | mvp-prod-control | ⏳ |
| K8 | Create task endpoints | K7 | mvp-prod-control | ⏳ |

> **Note:** Task IDs J6, K7, K8 avoid conflict with P1.5 bug fix tasks (WS-K1-K5)

### Wave Analysis

| Wave | Control Plane (mvp-prod-control) | Gateway (mvp-prod-gateway) |
|------|----------------------------------|----------------------------|
| **1** | I2, K7 | J6 |
| **2** | K8 | (none) |

### Visual Dependency Graph

```
CONTROL (mvp-prod-control)             GATEWAY (mvp-prod-gateway)
──────────────────────────             ─────────────────────────

I1 ──▶ I2 (SSO)                        J4, J5 ──▶ J6 (Keycloak)
           │                                       │
K6 ──▶ K7 (TaskSvc)                                │
           │                                       │
           ▼                                       │
       K8 (TaskAPI)                                │
           │                                       │
           └───────────────┬───────────────────────┘
                           │
                    [Batch P2-B2 Complete]
                           │
                           ▼
                  [MVP Production Ready!]
```

### Execution Strategy

Wave 1: I2, K7, J6 run in parallel.
Wave 2: K8 runs after K7 completes.

### Commands

```bash
# ═══════════════════════════════════════════════════════════════
# BATCH P2-B2 - Final Integration
# ═══════════════════════════════════════════════════════════════

# --- Create Task Specs (from main repo, in Plan mode) ---
cd /Users/imaxxs/repositories/deepsecure-mvp
/plan
/create-task-spec P2-B2 mvp-production-readiness

# --- Create Task Tickets (from main repo) ---
/create-task-ticket WS-I2 mvp-production-readiness
/create-task-ticket WS-J6 mvp-production-readiness
/create-task-ticket WS-K7 mvp-production-readiness
/create-task-ticket WS-K8 mvp-production-readiness

# ───────────────────────────────────────────────────────────────
# WAVE 1: I2, K7 (Control) + J6 (Gateway)
# ───────────────────────────────────────────────────────────────

# Terminal 1: mvp-prod-control
cd /Users/imaxxs/repositories/mvp-prod-control
/execute-task WS-I2 mvp-production-readiness
/complete-task WS-I2 mvp-production-readiness
/execute-task WS-K7 mvp-production-readiness
/complete-task WS-K7 mvp-production-readiness

# Terminal 2: mvp-prod-gateway
cd /Users/imaxxs/repositories/mvp-prod-gateway
/execute-task WS-J6 mvp-production-readiness
/complete-task WS-J6 mvp-production-readiness

# ⏸️ WAIT: K7 must complete before K8

# ───────────────────────────────────────────────────────────────
# WAVE 2: K8
# ───────────────────────────────────────────────────────────────

# Terminal 1: mvp-prod-control (continue)
cd /Users/imaxxs/repositories/mvp-prod-control
/execute-task WS-K8 mvp-production-readiness
/complete-task WS-K8 mvp-production-readiness

# --- Final Sync and Merge ---
cd /Users/imaxxs/repositories/deepsecure-mvp
/sync-worktree-status mvp-production-readiness

# Merge worktrees to dev
git checkout dev
git merge feature/mvp-prod-control --no-ff -m "Merge P2 control plane changes"
git merge feature/mvp-prod-gateway --no-ff -m "Merge P2 gateway changes"
```

### Validation (Production Ready Criteria)

```bash
# ═══════════════════════════════════════════════════════════════
# P2 VALIDATION - Production Ready Criteria
# ═══════════════════════════════════════════════════════════════

# 1. Start full stack with production config
cd /Users/imaxxs/repositories/deepsecure-mvp
export ENVIRONMENT=production
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
sleep 30

# 2. Verify all services healthy
curl -sf http://localhost:8000/health && echo "✅ Control Plane healthy"
curl -sf http://localhost:8002/health && echo "✅ Gateway healthy"
curl -sf http://localhost:8080/health/ready && echo "✅ Keycloak healthy"

# 3. Test SSO login (get redirect URL)
SSO_REDIRECT=$(curl -s -X GET "http://localhost:8000/api/v1/auth/sso/okta/authorize" | jq -r '.authorize_url')
echo "SSO URL: $SSO_REDIRECT"
# Manual: Complete SSO in browser, capture callback token

# 4. Get user token via standard login (fallback)
# Note: Login returns "token" field, not "access_token"
USER_TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"sarah@acme.com","password":"test_password"}' | jq -r '.token')
echo "User token: ${USER_TOKEN:0:20}..."

# 5. Test task token generation
TASK_TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/tasks/tokens \
  -H "Authorization: Bearer $USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"agent_id":"agent-123","permissions":["notion:read_pages"]}' | jq -r '.task_token')
echo "Task token: ${TASK_TOKEN:0:20}..."

# 6. Test task token scoped call (should succeed)
curl -s -X POST http://localhost:8002/mcp \
  -H "Authorization: Bearer $TASK_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "id": 1,
    "params": {"name": "notion.search_pages", "arguments": {"query": "test"}}
  }' | jq .

# 7. Test task token permission denial (should fail)
DENIED=$(curl -s -X POST http://localhost:8002/mcp \
  -H "Authorization: Bearer $TASK_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "id": 2,
    "params": {"name": "slack.send_message", "arguments": {"channel": "general"}}
  }')
echo "Permission denied response: $DENIED"

# 8. Test Keycloak token exchange
KEYCLOAK_TOKEN=$(curl -s -X POST http://localhost:8080/realms/deepsecure/protocol/openid-connect/token \
  -d "grant_type=urn:ietf:params:oauth:grant-type:token-exchange" \
  -d "client_id=gateway" \
  -d "client_secret=gateway-secret" \
  -d "subject_token=$USER_TOKEN" \
  -d "requested_token_type=urn:ietf:params:oauth:token-type:access_token" | jq -r '.access_token')
echo "Keycloak exchanged token: ${KEYCLOAK_TOKEN:0:20}..."

# 9. Run full E2E with production features
python demos/demo_sarah_journey_e2e.py --production

# 10. Run security test suite
pytest tests/security/ -v

# 11. Cleanup
docker compose -f docker-compose.yml -f docker-compose.prod.yml down

echo "✅ P2 Validation Complete - Production Ready"
```

### Summary

| Metric | Value |
|--------|-------|
| **Parallelism** | 75% (3 parallel in Wave 1, 1 in Wave 2) |
| **Waves** | 2 |
| **Bottleneck** | K7 → K8 dependency |
| **Merge Point** | **Production Ready** 🎉 |
| **Unblocks** | Production deployment |

---

## Overall Execution Summary

### Batch Parallelism Overview

| Batch | Tasks | Waves | Parallel % | Cross-Worktree? | Status |
|-------|-------|-------|------------|-----------------|--------|
| P0-B1 | 4 | 1 | 100% | No (control only) | ✅ Complete |
| P0-B2 | 2 | 1 | 100% | No (control only) | ✅ Complete |
| P0-B3 | 3 | 2 | 67% | No (control only) | ✅ Complete |
| P0-B4 | 2 | 1 | 0% | No (main) | ✅ Complete (MP1) |
| P1-B1 | 3 | 1 | 100% | ✅ Yes | ✅ Complete |
| P1-B2 | 7 | 1 | 100% | ✅ Yes | ✅ Complete (MP2) |
| P1-B3 | 2 | 2 | 0% | No (gateway only) | ✅ Complete (MP3) |
| **P1.5-B1** | 6 | 2 | 50% | ✅ Yes | ⏳ **NEW** (MP3.5) |
| P2-B1 | 4 | 1 | 100% | ✅ Yes | ⏳ Pending |
| P2-B2 | 4 | 2 | 75% | ✅ Yes | ⏳ Pending |

### Merge Points Summary

| Point | After Batch | Converging | Actions Required | Status |
|-------|-------------|------------|------------------|--------|
| MP1 | P0-B4 | D1 + D2 | Verify E2E demo passes | ✅ Reached |
| MP2 | P1-B2 | E2 + E3 | Vault API ready | ✅ Reached |
| MP3 | P1-B3 | H1 + H2 | Verify credential injection works | ✅ Reached |
| **MP3.5** | P1.5-B1 | WS-J2 + WS-K1-K5 | Integration bugs fixed, re-test Steps 1-18 | ⏳ **NEW** |
| MP4 | P2-B2 | All P2 | Final merge to dev, production deployment | ⏳ Pending |

### Total Commands Needed

| Command Type | Count | Notes |
|--------------|-------|-------|
| `/create-task-spec` | 10 | One per batch (includes P1.5-B1) |
| `/create-task-ticket` | 37 | One per task (31 original + 6 P1.5 bug fixes) |
| `/execute-task` | 37 | One per task |
| `/complete-task` | 37 | Auto after execute |
| `/sync-worktree-status` | 10 | One per batch |
| Merge actions | 5 | At each merge point (includes MP3.5) |
| **Total** | ~136 | |

### Critical Path

```
P0: A1 → A2 → A3 → C3 → D1 → D2 → [MP1] ✅
P1: E1 → E2 → H1 → H2 → [MP3] ✅
P1.5: WS-K1 → WS-K2 → [MP3.5]  ← Integration bug fixes
P2: I1 → I2 + K6 → K7 → K8 → [Production Ready]
```

### Worktree Distribution

| Worktree | Tasks | Phase |
|----------|-------|-------|
| **main** | A1-A3, B1-B3, C1-C3, D1-D2 (11 tasks) | P0 ✅ |
| **mvp-prod-control** | E1-E3, F1-F3, WS-K1-K5, I1-I2, K6-K8 (16 tasks) | P1, P1.5, P2 |
| **mvp-prod-gateway** | G1-G4, H1-H2, WS-J2, WS-K2 (sub), J4-J6 (10 tasks) | P1, P1.5, P2 |

### Parallelism Summary

| Phase | Max Parallel Instances | Worktrees Needed |
|-------|------------------------|------------------|
| P0 | 4 | 1 (main only) |
| P1 | 7 | 2 (Control + Gateway) |
| P1.5 | 3 | 2 (Control + Gateway) |
| P2 | 4 | 2 (Control + Gateway) |

### Optimal Execution Strategy

**P0:** ✅ COMPLETE
- Single developer, 4 parallel tasks max
- Stayed in main worktree
- E2E demo verified

**P1:** Two developers (or two Claude instances)
- Developer 1: Control Plane (E*, F*)
- Developer 2: Gateway (G*, H*)
- Merge at MP2 and MP3

**P1.5:** ⚠️ **NEW** Integration Bug Fixes
- Developer 1: Control Plane (WS-K1, WS-K2 pub, WS-K3, WS-K4, WS-K5)
- Developer 2: Gateway (WS-J2, WS-K2 sub)
- Re-test Integration Validation Guide Steps 1-18
- Complete MP3.5 before proceeding to P2

**P2:** Two developers (or two Claude instances)
- Developer 1: Control Plane (I1, I2, K6, K7, K8)
- Developer 2: Gateway (J4, J5, J6)
- Final merge to dev at completion

---

## Quick Start Commands

### P0 Complete ✅

P0 is already complete. E2E demo passes.

### Start P1 (after MP1) - NEXT

```bash
# 1. Setup worktrees (run once)
cd /Users/imaxxs/repositories/deepsecure-mvp
git worktree add ../mvp-prod-control -b feature/mvp-prod-control dev
git worktree add ../mvp-prod-gateway -b feature/mvp-prod-gateway dev
cp -r .cursor ../mvp-prod-control/
cp -r .cursor ../mvp-prod-gateway/

# 2. Create task specs for P1-B1
/plan
/create-task-spec P1-B1 mvp-production-readiness

# 3. Create task tickets
/create-task-ticket WS-E1 mvp-production-readiness
/create-task-ticket WS-F1 mvp-production-readiness
/create-task-ticket WS-G1 mvp-production-readiness

# 4. Execute in parallel
# Terminal 1 (Control):
cd ../mvp-prod-control
/execute-task WS-E1 mvp-production-readiness

# Terminal 2 (Gateway):
cd ../mvp-prod-gateway
/execute-task WS-G1 mvp-production-readiness
```

### Start P1.5 (after MP3) - ⚠️ **NEXT: Bug Fixes**

```bash
# 1. Verify MP3 criteria met
# All P1 batches complete, credential injection works

# 2. Specs already created - see docs/workstreams/mvp-production-readiness/specs/
# WS-J2-spec.md, WS-K1-spec.md, WS-K2-spec.md, WS-K3-spec.md, WS-K4-spec.md, WS-K5-spec.md

# 3. Create task tickets (from main repo)
cd /Users/imaxxs/repositories/deepsecure-mvp
/create-task-ticket WS-J2 mvp-production-readiness
/create-task-ticket WS-K1 mvp-production-readiness
/create-task-ticket WS-K2 mvp-production-readiness
/create-task-ticket WS-K3 mvp-production-readiness
/create-task-ticket WS-K4 mvp-production-readiness
/create-task-ticket WS-K5 mvp-production-readiness

# 4. Execute Wave 1 in parallel
# Terminal 1 (Control):
cd ../mvp-prod-control
/execute-task WS-K1 mvp-production-readiness
/execute-task WS-K3 mvp-production-readiness

# Terminal 2 (Gateway):
cd ../mvp-prod-gateway
/execute-task WS-J2 mvp-production-readiness

# 5. Execute Wave 2 after Wave 1 completes
# Terminal 1 (Control):
/execute-task WS-K2 mvp-production-readiness
/execute-task WS-K4 mvp-production-readiness
/execute-task WS-K5 mvp-production-readiness

# Terminal 2 (Gateway):
/execute-task WS-K2 mvp-production-readiness  # Gateway subscriber

# 6. Re-test Integration Validation Guide
cd /Users/imaxxs/repositories/deepsecure-mvp
docker compose build --no-cache deeptrail-control deeptrail-gateway
docker compose up -d
# Follow docs/INTEGRATION_VALIDATION_GUIDE.md Steps 1-18
```

### Start P2 (after MP3.5)

```bash
# 1. Verify MP3.5 criteria met
# Re-run Integration Validation Guide Steps 1-18
# All issues from P1.5 should be fixed

# 2. Continue in existing worktrees (no new setup needed)
cd ../mvp-prod-control
/execute-task WS-I1 mvp-production-readiness

cd ../mvp-prod-gateway
/execute-task WS-J1 mvp-production-readiness

# 3. After P2 complete, merge to dev
cd /Users/imaxxs/repositories/deepsecure-mvp
git checkout dev
git merge feature/mvp-prod-control --no-ff -m "Merge P1/P2 control plane"
git merge feature/mvp-prod-gateway --no-ff -m "Merge P1/P2 gateway"

# 4. Clean up worktrees (see detailed section below)
git worktree remove ../mvp-prod-control
git worktree remove ../mvp-prod-gateway
```

---

## Worktree Cleanup (End of Workstream)

> **When to run:** After ALL phases (P0, P1, P2) are complete and merged to `dev` branch.
> **Prerequisites:** All merge points (MP1-MP4) must be ✅ REACHED.

### Pre-Cleanup Verification

Before removing worktrees, verify all work is merged:

```bash
# 1. Navigate to main repo
cd /Users/imaxxs/repositories/deepsecure-mvp

# 2. Update dev branch
git checkout dev
git pull origin dev

# 3. Check if worktree branches are fully merged
git branch --merged dev | grep "mvp-prod"
# Expected output:
#   feature/mvp-prod-control
#   feature/mvp-prod-gateway

# 4. If branches NOT shown above, merge them first:
git merge feature/mvp-prod-control --no-ff -m "Merge MVP Production Readiness: Control Plane"
git merge feature/mvp-prod-gateway --no-ff -m "Merge MVP Production Readiness: Gateway"

# 5. Verify E2E demo passes on merged code
python demos/demo_sarah_journey_e2e.py
```

### Remove Worktrees

```bash
# Navigate to main repo
cd /Users/imaxxs/repositories/deepsecure-mvp

# List current worktrees
git worktree list
# Expected output:
# /Users/imaxxs/repositories/deepsecure-mvp          (dev)
# /Users/imaxxs/repositories/mvp-prod-control        (feature/mvp-prod-control)
# /Users/imaxxs/repositories/mvp-prod-gateway        (feature/mvp-prod-gateway)

# Remove worktrees (safe removal - fails if uncommitted changes)
git worktree remove ../mvp-prod-control
git worktree remove ../mvp-prod-gateway

# Verify removal
git worktree list
# Expected output:
# /Users/imaxxs/repositories/deepsecure-mvp          (dev)
```

### Delete Feature Branches (Optional)

After worktrees are removed, delete the feature branches if no longer needed:

```bash
# Delete local feature branches
git branch -d feature/mvp-prod-control
git branch -d feature/mvp-prod-gateway

# If branches were pushed to remote, delete them there too
git push origin --delete feature/mvp-prod-control
git push origin --delete feature/mvp-prod-gateway
```

### Force Removal (Use with Caution)

If worktree removal fails due to uncommitted changes:

```bash
# ⚠️ WARNING: This discards ALL uncommitted changes in the worktree!
# Only use if you're certain no work will be lost.

# Option 1: Stash changes, then remove
cd ../mvp-prod-control
git stash
cd /Users/imaxxs/repositories/deepsecure-mvp
git worktree remove ../mvp-prod-control

# Option 2: Force remove (destroys uncommitted work)
git worktree remove --force ../mvp-prod-control
git worktree remove --force ../mvp-prod-gateway
```

### Cleanup Summary Checklist

| Step | Command | Verified |
|------|---------|----------|
| 1. All phases complete | Check `STATUS.md` | ☐ |
| 2. All merge points reached | Check `MERGE_POINTS.md` | ☐ |
| 3. Branches merged to dev | `git branch --merged dev` | ☐ |
| 4. E2E demo passes | `python demos/demo_sarah_journey_e2e.py` | ☐ |
| 5. Worktrees removed | `git worktree remove ...` | ☐ |
| 6. Feature branches deleted | `git branch -d ...` | ☐ |
| 7. Worktree list clean | `git worktree list` | ☐ |

### Troubleshooting

| Issue | Solution |
|-------|----------|
| "worktree is dirty" | Commit or stash changes before removal |
| "branch still checked out" | Run from main repo, not from worktree |
| "worktree not found" | Already removed, or wrong path |
| "cannot delete branch" | Branch not fully merged; use `-D` to force (careful!) |
| Leftover `.cursor/` in worktree | Automatically removed with worktree |

---

*Last Updated: February 17, 2026*
*Generated by `/create-batch-execution-plan` command*
