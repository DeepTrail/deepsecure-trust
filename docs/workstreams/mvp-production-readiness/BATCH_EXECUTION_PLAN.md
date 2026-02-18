# MVP Production Readiness: Batch Execution Plan

> **Generated from:** [mvp-production-readiness-breakdown.md](../../mvp-production-readiness-breakdown.md)
>
> **Source Plan:** [mvp_production_readiness.plan.md](../../../.cursor/plans/mvp_production_readiness.plan.md)
>
> **Last Updated:** February 15, 2026

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
| P1-B3 | 2 | 0 | 2 | ⏳ Pending (MP3) | mvp-prod-gateway |
| P2-B1 | 4 | 0 | 1 | ⏳ Pending | mvp-prod-control, mvp-prod-gateway |
| P2-B2 | 4 | 0 | 2 | ⏳ Pending | mvp-prod-control, mvp-prod-gateway |

**Total Tasks:** 31 | **Completed:** 21 (P0 + P1-B1 + P1-B2) | **Remaining:** 10 (P1-B3 + P2)

---

## Worktree Reference

| Worktree | Path | Branch | Workstreams | Phase |
|----------|------|--------|-------------|-------|
| **main** | `/Users/imaxxs/repositories/deepsecure-mvp` | `dev` | A, B, C, D | P0 |
| **mvp-prod-control** | `../mvp-prod-control` | `feature/mvp-prod-control` | E, F, I, K | P1, P2 |
| **mvp-prod-gateway** | `../mvp-prod-gateway` | `feature/mvp-prod-gateway` | G, H, J | P1, P2 |

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
┌─────────────────────────────────────────────────────────────────────────────┐
│                            TIMELINE OVERVIEW                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  PHASE 0 (E2E Tests)          PHASE 1 (Integration)      PHASE 2 (Harden)  │
│  ──────────────────────       ─────────────────────      ─────────────────  │
│  P0-B1 │ P0-B2 │ P0-B3 │ P0-B4 │ P1-B1 │ P1-B2 │ P1-B3 │ P2-B1 │ P2-B2 │  │
│   1-2h │  2-3h │  2-3h │  1-2h │  3-4h │  4-6h │  2-3h │  4-6h │  4-6h │  │
│   ✅   │  ✅   │  ✅   │  ✅   │  ✅   │  ✅   │  ⏳   │  ⏳   │  ⏳   │  │
│                       [MP1]               [MP2]   [MP3]                     │
│                                                                             │
│  Total: ~23-35 hours estimated                                              │
└─────────────────────────────────────────────────────────────────────────────┘
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
      "expires_in": 3600
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

### Batch P1-B3: Credential Injection (2 tasks) - MP2, MP3

### Dependencies

| Task | Description | Dependencies | Worktree | Status |
|------|-------------|--------------|----------|--------|
| H1 | Connect CredentialInjector to vault API | MP2 (E2, E3) | mvp-prod-gateway | ⏳ |
| H2 | Implement token refresh in injector | H1 | mvp-prod-gateway | ⏳ |

### Wave Analysis

| Wave | Control Plane | Gateway (mvp-prod-gateway) |
|------|---------------|----------------------------|
| **1** | (none) | H1 |
| **2** | (none) | H2 |

### Visual Dependency Graph

```
CONTROL (mvp-prod-control)             GATEWAY (mvp-prod-gateway)
──────────────────────────             ─────────────────────────

[MP2: Vault API Ready] ────────────────▶ H1
                                          │
                                          ▼
                                         H2
                                          │
                                   [MP3: P1 Complete]
                                          │
                                          ▼
                                    Phase 2 Unlocked
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
      "expires_in": 3600
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

### Summary

| Metric | Value |
|--------|-------|
| **Parallelism** | 0% (sequential H1 → H2) |
| **Waves** | 2 |
| **Bottleneck** | H1 (must complete first) |
| **Merge Point** | **MP3: P1 Complete** ✅ |
| **Unblocks** | Phase 2 (P2-B1: I1, J1, J2, K1) |

---

## Phase 2: Production Hardening

> **Prerequisite:** MP3 (P1 complete)
> **Status:** ⏳ PENDING
> **Worktrees:** mvp-prod-control, mvp-prod-gateway (continue from P1)

---

### Batch P2-B1: Core Security Features (4 tasks)

### Dependencies

| Task | Description | Dependencies | Worktree | Status |
|------|-------------|--------------|----------|--------|
| I1 | Create IdP service | MP3 | mvp-prod-control | ⏳ |
| J1 | Implement result filtering | MP3 | mvp-prod-gateway | ⏳ |
| J2 | Implement prompt injection detection | MP3 | mvp-prod-gateway | ⏳ |
| K1 | Create TaskToken model | MP3 | mvp-prod-control | ⏳ |

### Wave Analysis

| Wave | Control Plane (mvp-prod-control) | Gateway (mvp-prod-gateway) |
|------|----------------------------------|----------------------------|
| **1** | I1, K1 | J1, J2 |

### Visual Dependency Graph

```
CONTROL (mvp-prod-control)             GATEWAY (mvp-prod-gateway)
──────────────────────────             ─────────────────────────

[MP3] ─────┬───────────────────────────┬────────────────────────
           │                           │
           ▼                           ▼
    I1 (IdP)    K1 (TaskToken)        J1 (PII)    J2 (Prompt)
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
- Control: I1, K1 (2 tasks)
- Gateway: J1, J2 (2 tasks)

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
/create-task-ticket WS-J1 mvp-production-readiness
/create-task-ticket WS-J2 mvp-production-readiness
/create-task-ticket WS-K1 mvp-production-readiness

# ───────────────────────────────────────────────────────────────
# WAVE 1: Control (I1, K1) + Gateway (J1, J2)
# ───────────────────────────────────────────────────────────────

# Terminal 1: mvp-prod-control
cd /Users/imaxxs/repositories/mvp-prod-control
/execute-task WS-I1 mvp-production-readiness
/complete-task WS-I1 mvp-production-readiness
/execute-task WS-K1 mvp-production-readiness
/complete-task WS-K1 mvp-production-readiness

# Terminal 2: mvp-prod-gateway
cd /Users/imaxxs/repositories/mvp-prod-gateway
/execute-task WS-J1 mvp-production-readiness
/complete-task WS-J1 mvp-production-readiness
/execute-task WS-J2 mvp-production-readiness
/complete-task WS-J2 mvp-production-readiness

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
| **Unblocks** | Batch P2-B2 (I2, J3, K2, K3) |

---

### Batch P2-B2: Endpoints & Integration (4 tasks) - FINAL

### Dependencies

| Task | Description | Dependencies | Worktree | Status |
|------|-------------|--------------|----------|--------|
| I2 | Create SSO endpoints | I1 | mvp-prod-control | ⏳ |
| J3 | Implement Keycloak token exchange | J1, J2 | mvp-prod-gateway | ⏳ |
| K2 | Create TaskService | K1 | mvp-prod-control | ⏳ |
| K3 | Create task endpoints | K2 | mvp-prod-control | ⏳ |

### Wave Analysis

| Wave | Control Plane (mvp-prod-control) | Gateway (mvp-prod-gateway) |
|------|----------------------------------|----------------------------|
| **1** | I2, K2 | J3 |
| **2** | K3 | (none) |

### Visual Dependency Graph

```
CONTROL (mvp-prod-control)             GATEWAY (mvp-prod-gateway)
──────────────────────────             ─────────────────────────

I1 ──▶ I2 (SSO)                        J1, J2 ──▶ J3 (Keycloak)
           │                                       │
K1 ──▶ K2 (TaskSvc)                                │
           │                                       │
           ▼                                       │
       K3 (TaskAPI)                                │
           │                                       │
           └───────────────┬───────────────────────┘
                           │
                    [Batch P2-B2 Complete]
                           │
                           ▼
                  [MVP Production Ready!]
```

### Execution Strategy

Wave 1: I2, K2, J3 run in parallel.
Wave 2: K3 runs after K2 completes.

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
/create-task-ticket WS-J3 mvp-production-readiness
/create-task-ticket WS-K2 mvp-production-readiness
/create-task-ticket WS-K3 mvp-production-readiness

# ───────────────────────────────────────────────────────────────
# WAVE 1: I2, K2 (Control) + J3 (Gateway)
# ───────────────────────────────────────────────────────────────

# Terminal 1: mvp-prod-control
cd /Users/imaxxs/repositories/mvp-prod-control
/execute-task WS-I2 mvp-production-readiness
/complete-task WS-I2 mvp-production-readiness
/execute-task WS-K2 mvp-production-readiness
/complete-task WS-K2 mvp-production-readiness

# Terminal 2: mvp-prod-gateway
cd /Users/imaxxs/repositories/mvp-prod-gateway
/execute-task WS-J3 mvp-production-readiness
/complete-task WS-J3 mvp-production-readiness

# ⏸️ WAIT: K2 must complete before K3

# ───────────────────────────────────────────────────────────────
# WAVE 2: K3
# ───────────────────────────────────────────────────────────────

# Terminal 1: mvp-prod-control (continue)
cd /Users/imaxxs/repositories/mvp-prod-control
/execute-task WS-K3 mvp-production-readiness
/complete-task WS-K3 mvp-production-readiness

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
| **Bottleneck** | K2 → K3 dependency |
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
| P1-B3 | 2 | 2 | 0% | No (gateway only) | ⏳ Pending (MP3) |
| P2-B1 | 4 | 1 | 100% | ✅ Yes | ⏳ Pending |
| P2-B2 | 4 | 2 | 75% | ✅ Yes | ⏳ Pending |

### Merge Points Summary

| Point | After Batch | Converging | Actions Required | Status |
|-------|-------------|------------|------------------|--------|
| MP1 | P0-B4 | D1 + D2 | Verify E2E demo passes | ✅ Reached |
| MP2 | P1-B2 | E2 + E3 | Vault API ready | ✅ Reached |
| MP3 | P1-B3 | H1 + H2 | Merge worktrees, verify credential injection | ⏳ Pending |
| MP4 | P2-B2 | All P2 | Final merge to dev, production deployment | ⏳ Pending |

### Total Commands Needed

| Command Type | Count | Notes |
|--------------|-------|-------|
| `/create-task-spec` | 9 | One per batch |
| `/create-task-ticket` | 31 | One per task |
| `/execute-task` | 31 | One per task |
| `/complete-task` | 31 | Auto after execute |
| `/sync-worktree-status` | 9 | One per batch |
| Merge actions | 4 | At each merge point |
| **Total** | ~115 | |

### Critical Path

```
P0: A1 → A2 → A3 → C3 → D1 → D2 → [MP1] ✅
P1: E1 → E2 → H1 → H2 → [MP3]
P2: K1 → K2 → K3 → [Production Ready]
```

### Worktree Distribution

| Worktree | Tasks | Phase |
|----------|-------|-------|
| **main** | A1-A3, B1-B3, C1-C3, D1-D2 (11 tasks) | P0 ✅ |
| **mvp-prod-control** | E1-E3, F1-F3, I1-I2, K1-K3 (11 tasks) | P1, P2 |
| **mvp-prod-gateway** | G1-G4, H1-H2, J1-J3 (9 tasks) | P1, P2 |

### Parallelism Summary

| Phase | Max Parallel Instances | Worktrees Needed |
|-------|------------------------|------------------|
| P0 | 4 | 1 (main only) |
| P1 | 7 | 2 (Control + Gateway) |
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

**P2:** Two developers (or two Claude instances)
- Developer 1: Control Plane (I*, K*)
- Developer 2: Gateway (J*)
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

### Start P2 (after MP3)

```bash
# 1. Verify MP3 criteria met
python demos/demo_sarah_journey_e2e.py --real-oauth

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
