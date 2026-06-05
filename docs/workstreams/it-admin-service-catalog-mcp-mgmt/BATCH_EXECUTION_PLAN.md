# Batch Execution Plan: P5.2 IT Admin Service Catalog + MCP Server Management

> **Feature:** `it-admin-service-catalog-mcp-mgmt`
> **Created:** May 29, 2026
> **Batches:** 4 | **Tasks:** 35 | **Merge Points:** 3

---

## Quick Reference

| Batch | Tag | Tasks | Merge Point |
|-------|-----|-------|-------------|
| P0-B1 | `mp1-foundation-complete` | WS-A1, A2, A3, A4, A5 | MP1 |
| P0-B2 | `mp2-backend-apis-complete` | WS-B1-B6, D1-D5, C5-C8 | MP2 |
| P0-B3 | `mp3-full-feature-functional` | WS-C1-C4, E1-E7 | MP3 |
| P0-B4 | — (final) | WS-F1-F4 | — |

---

## Batch P0-B1: Foundation — Admin Role + DB Schema + KMS

### Wave Analysis

**Wave 1 (parallel):** WS-A1 (Migration) + WS-A3 (KMS Client)
- No dependencies between them. A1 creates tables; A3 creates encryption utility.

**Wave 2 (sequential after Wave 1):** WS-A2 (Models) → depends on A1
- Models reference tables created by migration.

**Wave 3 (sequential after Wave 1):** WS-A4 (Admin Middleware) → depends on A1
- Middleware checks `user_sessions.role` column created by A1.

**Wave 4 (sequential after Wave 3):** WS-A5 (Seed Script + Role API) → depends on A1, A4
- Seed script updates `role` column; role API uses admin middleware.

### Visual Dependency Graph

```
Wave 1:  [WS-A1: Migration] ──────────────────┐
         [WS-A3: KMS Client] (parallel)        │
                                                │
Wave 2:  [WS-A2: Models] ◄────────────────────┘
                                                │
Wave 3:  [WS-A4: Admin Middleware] ◄───────────┘
                                                │
Wave 4:  [WS-A5: Seed + Role API] ◄───────────┘
```

### Execution Strategy

1. Start WS-A1 (migration) and WS-A3 (KMS) in parallel
2. After A1 completes: WS-A2 (models)
3. After A1 completes: WS-A4 (middleware) — parallel with A2
4. After A4 completes: WS-A5 (seed + role API)

### Commands

```bash
/execute-task WS-A1 it-admin-service-catalog-mcp-mgmt
/execute-task WS-A3 it-admin-service-catalog-mcp-mgmt  # parallel with A1
/execute-task WS-A2 it-admin-service-catalog-mcp-mgmt
/execute-task WS-A4 it-admin-service-catalog-mcp-mgmt
/execute-task WS-A5 it-admin-service-catalog-mcp-mgmt
```

### Validation

```bash
# Verify migration
cd deeptrail-control && alembic upgrade head

# Verify models import
python -c "from app.models.service_registry import ServiceRegistry, ServiceOAuthConfig; print('✅ Models OK')"
python -c "from app.models.delegation_template import DelegationTemplate; print('✅ Template OK')"

# Verify KMS
pytest tests/core/test_kms.py -v

# Verify admin middleware
pytest tests/middleware/test_admin_auth.py -v
```

### Summary

| Task | Description | Complexity | Dependencies | Status |
|------|-------------|------------|--------------|--------|
| WS-A1 | Alembic migration: 3 tables + 2 column mods | M | None | 🔲 |
| WS-A2 | SQLAlchemy models | S | A1 | 🔲 |
| WS-A3 | KMS client wrapper (Fernet fallback) | M | None | 🔲 |
| WS-A4 | Admin middleware (require_admin) | S | A1 | 🔲 |
| WS-A5 | Seed script + role assignment endpoint | S | A1, A4 | 🔲 |

---

## ── MERGE POINT 1: Foundation Complete ──

**Trigger:** All 5 tasks above pass validation
**Action:** Commit, push, tag `mp1-foundation-complete-$(git branch --show-current)`
**Verify:** `scripts/execute_merge_point.sh scripts/mp_configs/it-admin-service-catalog-mcp-mgmt-mp1.conf`

---

## Batch P0-B2: Backend APIs — Service Catalog + Fleet + Multi-User Runtime

### Wave Analysis

**Wave 1 (parallel — 3 tracks):**

Track A (Service Catalog):
- WS-B1 (Registry Service) → depends on A2, A3
- WS-B2 (CRUD Endpoints) → depends on B1, A4
- WS-B3 (OAuth Endpoints) → depends on B1
- WS-B4 (Internal Registry) → depends on B1
- WS-B5 (Health Reporting) → depends on A2
- WS-B6 (Register Routers) → depends on B2

Track B (Fleet + Delegation):
- WS-D1 (Fleet API) → depends on A4
- WS-D2 (Agent Suspend) → depends on D1
- WS-D3 (Template CRUD) → depends on A2, A4
- WS-D4 (Delegation Mgmt) → depends on D3
- WS-D5 (Emergency) → depends on A4

Track C (Multi-User Runtime):
- WS-C5 (Extract user_id) → no deps
- WS-C6 (Per-User Delegation) → depends on C5
- WS-C7 (Credential Injection) → depends on C6
- WS-C8 (Backward Compat) → depends on C5

### Visual Dependency Graph

```
Track A (Control Plane - Service Catalog):
  WS-B1 → WS-B2 → WS-B6
       └→ WS-B3
       └→ WS-B4
  WS-B5 (parallel)

Track B (Control Plane - Fleet):
  WS-D1 → WS-D2
  WS-D3 → WS-D4
  WS-D5 (parallel with D1-D4)

Track C (Gateway - Multi-User):
  WS-C5 → WS-C6 → WS-C7
       └→ WS-C8
```

### Execution Strategy

Run 3 tracks in sequence (single-branch), but within each track follow the dependency chain:

1. **Track A:** B1 → B2 → B3 → B4 → B5 → B6
2. **Track B:** D1 → D2 → D3 → D4 → D5
3. **Track C:** C5 → C6 → C7 → C8

Alternative (faster): Interleave tracks — B1, D1, C5, B2, D2, C6, B3, D3, C7, B4, D4, C8, B5, D5, B6.

### Commands

```bash
# Track A: Service Catalog Backend
/execute-task WS-B1 it-admin-service-catalog-mcp-mgmt
/execute-task WS-B2 it-admin-service-catalog-mcp-mgmt
/execute-task WS-B3 it-admin-service-catalog-mcp-mgmt
/execute-task WS-B4 it-admin-service-catalog-mcp-mgmt
/execute-task WS-B5 it-admin-service-catalog-mcp-mgmt
/execute-task WS-B6 it-admin-service-catalog-mcp-mgmt

# Track B: Fleet + Delegation Backend
/execute-task WS-D1 it-admin-service-catalog-mcp-mgmt
/execute-task WS-D2 it-admin-service-catalog-mcp-mgmt
/execute-task WS-D3 it-admin-service-catalog-mcp-mgmt
/execute-task WS-D4 it-admin-service-catalog-mcp-mgmt
/execute-task WS-D5 it-admin-service-catalog-mcp-mgmt

# Track C: Multi-User Runtime
/execute-task WS-C5 it-admin-service-catalog-mcp-mgmt
/execute-task WS-C6 it-admin-service-catalog-mcp-mgmt
/execute-task WS-C7 it-admin-service-catalog-mcp-mgmt
/execute-task WS-C8 it-admin-service-catalog-mcp-mgmt
```

### Validation

```bash
# Service catalog endpoints
cd deeptrail-control && pytest tests/services/test_service_registry_service.py -v
cd deeptrail-control && pytest tests/api/test_admin_services.py -v

# Fleet + delegation endpoints
cd deeptrail-control && pytest tests/api/test_admin_fleet.py -v
cd deeptrail-control && pytest tests/api/test_admin_emergency.py -v
cd deeptrail-control && pytest tests/services/test_delegation_template_service.py -v

# Multi-user runtime
cd deeptrail-gateway && pytest tests/handlers/test_tools_call_multiuser.py -v
```

### Summary

| Task | Description | Complexity | Track | Status |
|------|-------------|------------|-------|--------|
| WS-B1 | Service registry CRUD service | M | A | 🔲 |
| WS-B2 | Service CRUD endpoints (8) | M | A | 🔲 |
| WS-B3 | OAuth config endpoints | S | A | 🔲 |
| WS-B4 | Internal registry API | S | A | 🔲 |
| WS-B5 | Health reporting endpoint | S | A | 🔲 |
| WS-B6 | Register admin routers | S | A | 🔲 |
| WS-D1 | Admin fleet API | M | B | 🔲 |
| WS-D2 | Agent suspend | S | B | 🔲 |
| WS-D3 | Delegation template CRUD | M | B | 🔲 |
| WS-D4 | Admin delegation management | M | B | 🔲 |
| WS-D5 | Emergency endpoints | M | B | 🔲 |
| WS-C5 | Extract user_id from _meta | S | C | 🔲 |
| WS-C6 | Per-user delegation resolution | M | C | 🔲 |
| WS-C7 | User-scoped credential injection | M | C | 🔲 |
| WS-C8 | Backward compatibility | S | C | 🔲 |

---

## ── MERGE POINT 2: Backend APIs Complete ──

**Trigger:** All 15 tasks above pass validation
**Action:** Commit, push, tag `mp2-backend-apis-complete-$(git branch --show-current)`
**Verify:** `scripts/execute_merge_point.sh scripts/mp_configs/it-admin-service-catalog-mcp-mgmt-mp2.conf`

---

## Batch P0-B3: Gateway Dynamic Loading + Admin Frontend

### Wave Analysis

**Wave 1 (Gateway):**
- WS-C1 (Dynamic Loader) → depends on B4
- WS-C2 (Startup Integration) → depends on C1
- WS-C3 (ToolCache Population) → depends on C1
- WS-C4 (Health Reporter) → depends on C1, B5

**Wave 2 (Frontend — after gateway or parallel):**
- WS-E7 (Admin Types) → no deps
- WS-E1 (Role Hook + Sidebar) → depends on E7
- WS-E2 (Service Catalog Page) → depends on E1, B2
- WS-E3 (Add Service Modal) → depends on E2
- WS-E4 (Health Dashboard) → depends on E1, B5, D5
- WS-E5 (Agent Fleet View) → depends on E1, D1
- WS-E6 (Delegation Mgmt) → depends on E1, D3, D4

### Visual Dependency Graph

```
Gateway:
  WS-C1 → WS-C2
       └→ WS-C3
       └→ WS-C4

Frontend:
  WS-E7 → WS-E1 → WS-E2 → WS-E3
                 └→ WS-E4
                 └→ WS-E5
                 └→ WS-E6
```

### Execution Strategy

1. Gateway first: C1 → C2 → C3 → C4
2. Frontend: E7 → E1 → E2 → E3 → E4 → E5 → E6

### Commands

```bash
# Gateway Dynamic Loading
/execute-task WS-C1 it-admin-service-catalog-mcp-mgmt
/execute-task WS-C2 it-admin-service-catalog-mcp-mgmt
/execute-task WS-C3 it-admin-service-catalog-mcp-mgmt
/execute-task WS-C4 it-admin-service-catalog-mcp-mgmt

# Admin Frontend
/execute-task WS-E7 it-admin-service-catalog-mcp-mgmt
/execute-task WS-E1 it-admin-service-catalog-mcp-mgmt
/execute-task WS-E2 it-admin-service-catalog-mcp-mgmt
/execute-task WS-E3 it-admin-service-catalog-mcp-mgmt
/execute-task WS-E4 it-admin-service-catalog-mcp-mgmt
/execute-task WS-E5 it-admin-service-catalog-mcp-mgmt
/execute-task WS-E6 it-admin-service-catalog-mcp-mgmt
```

### Validation

```bash
# Gateway dynamic registry
cd deeptrail-gateway && pytest tests/backends/test_dynamic_registry.py -v

# Frontend build
cd frontend && npm run build
echo "Exit code: $?"

# Frontend type check
cd frontend && npx tsc --noEmit
```

### Summary

| Task | Description | Complexity | Service | Status |
|------|-------------|------------|---------|--------|
| WS-C1 | Dynamic backend loader | L | Gateway | 🔲 |
| WS-C2 | Gateway startup integration | M | Gateway | 🔲 |
| WS-C3 | ToolCache dynamic population | S | Gateway | 🔲 |
| WS-C4 | Health reporter | M | Gateway | 🔲 |
| WS-E7 | Admin TypeScript types | S | Frontend | 🔲 |
| WS-E1 | Admin role hook + sidebar | M | Frontend | 🔲 |
| WS-E2 | Service Catalog page | L | Frontend | 🔲 |
| WS-E3 | Add Service modal | M | Frontend | 🔲 |
| WS-E4 | Health dashboard + emergency | L | Frontend | 🔲 |
| WS-E5 | Agent Fleet view | L | Frontend | 🔲 |
| WS-E6 | Delegation Management | L | Frontend | 🔲 |

---

## ── MERGE POINT 3: Full Feature Functional ──

**Trigger:** All 11 tasks above pass validation
**Action:** Commit, push, tag `mp3-full-feature-functional-$(git branch --show-current)`
**Verify:** `scripts/execute_merge_point.sh scripts/mp_configs/it-admin-service-catalog-mcp-mgmt-mp3.conf`

---

## Batch P0-B4: Integration — Employee Updates + E2E + Demo

### Wave Analysis

**Wave 1 (parallel):** WS-F1 (Employee Services) + WS-F2 (Template Enforcement)
**Wave 2 (after Wave 1):** WS-F3 (E2E Tests) + WS-F4 (Demo Script)

### Visual Dependency Graph

```
Wave 1: [WS-F1: Employee Services] (parallel)
        [WS-F2: Template Enforcement]

Wave 2: [WS-F3: E2E Tests] ◄── depends on all prior
        [WS-F4: Multi-User Demo] ◄── depends on all prior
```

### Commands

```bash
/execute-task WS-F1 it-admin-service-catalog-mcp-mgmt
/execute-task WS-F2 it-admin-service-catalog-mcp-mgmt
/execute-task WS-F3 it-admin-service-catalog-mcp-mgmt
/execute-task WS-F4 it-admin-service-catalog-mcp-mgmt
```

### Validation

```bash
# Employee services page
cd frontend && npm run build

# Template enforcement
cd deeptrail-control && pytest tests/api/test_delegation_template_enforcement.py -v

# E2E tests
cd /Users/imaxxs/repositories/deepsecure-mvp
pytest tests/e2e/test_admin_service_catalog_e2e.py -v

# Demo
python demos/demo_admin_multi_user.py --auto --skip-api
echo "Exit code: $?"
```

### Summary

| Task | Description | Complexity | Service | Status |
|------|-------------|------------|---------|--------|
| WS-F1 | Employee services from DB | M | Frontend | 🔲 |
| WS-F2 | Template enforcement at delegation creation | M | Control | 🔲 |
| WS-F3 | Full-flow E2E tests | L | Cross | 🔲 |
| WS-F4 | Multi-user demo script | M | Cross | 🔲 |

---

## Overall Execution Summary

| Batch | Tasks | Complexity | Estimated Sessions |
|-------|-------|------------|-------------------|
| P0-B1 | 5 | 2M + 3S | 1-2 |
| P0-B2 | 15 | 7M + 4S + 0L (+ 4M from Track C) | 3-4 |
| P0-B3 | 11 | 4L + 3M + 2S + 2S | 3-4 |
| P0-B4 | 4 | 1L + 3M | 1-2 |
| **Total** | **35** | | **8-12 sessions** |

## Optimal Execution Strategy

**Single-branch sequential** — execute B1 → B2 → B3 → B4 in order.

Rationale:
- WS-A (foundation) blocks everything else
- Shared files (`main.py`, `api.py`, `delegation.py`) would cause merge conflicts with worktrees
- Fewer than 6 tasks per parallel track — worktree overhead not justified
- Within each batch, tracks can be interleaved for variety

## Quick Start Commands

```bash
# Start first batch
/run-batch P0-B1 it-admin-service-catalog-mcp-mgmt

# With auto-continuation through all batches
/run-batch P0-B1 it-admin-service-catalog-mcp-mgmt --continue --auto-heal

# Individual task execution
/execute-task WS-A1 it-admin-service-catalog-mcp-mgmt
```
