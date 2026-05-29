# Task Breakdown: P5.2 IT Admin Service Catalog + MCP Server Management

> **Generated:** May 29, 2026 by `/run-plan --auto-heal --skip-checkpoint`
> **Design Doc:** `docs/design/p5.2-it-admin-service-catalog.md`
> **Spec:** `docs/spec/p5.2-it-admin-service-catalog-spec.md`
> **Feature:** `it-admin-service-catalog-mcp-mgmt`
> **Codebase Analysis:** `CODEBASE_ANALYSIS.md` (all 35 tasks verified against codebase)

## Scope

35 tasks across 6 workstreams, touching 3 services:
- **deeptrail-control** (Control Plane): ~15 new/modified files, 3 new DB tables, 24 admin endpoints
- **deeptrail-gateway** (Gateway): ~8 new/modified files, dynamic backend loading, multi-user runtime
- **frontend**: ~10 new files, 4 admin pages, role-based navigation

## Workstream Summary

| Workstream | Tasks | Focus | Service | Dependencies |
|------------|-------|-------|---------|--------------|
| **WS-A: Foundation** | 5 | Admin role, DB schema, KMS | Control Plane | None (root) |
| **WS-B: Service Catalog Backend** | 6 | Service CRUD, registry API | Control Plane | WS-A |
| **WS-C: Gateway Dynamic + Multi-User** | 8 | Dynamic loading, multi-user tools/call | Gateway | WS-B (partial) |
| **WS-D: Fleet + Delegation Backend** | 5 | Fleet API, templates, emergency | Control Plane | WS-A |
| **WS-E: Admin Frontend** | 7 | 4 admin pages, role hook, sidebar | Frontend | WS-B, WS-D |
| **WS-F: Integration + Demo** | 4 | E2E, employee updates, demo | Cross-service | WS-C, WS-D, WS-E |

## Parallelization Decision

**Recommended: Single-branch execution**

Rationale:
- WS-A is a hard prerequisite for all other workstreams (migration + models)
- WS-B and WS-D can be parallelized (different endpoint files) but share the same DB models from WS-A
- WS-C depends on WS-B4 (internal registry API) for the dynamic loader
- WS-E depends on backends being available for API calls
- With single-branch, we avoid merge conflicts on shared files (`main.py`, `api.py`, `delegation.py`)
- Fewer than 6 tasks per batch — overhead of worktrees exceeds benefit

**Execution order:**
```
Batch 1: WS-A (Foundation) — all 5 tasks sequential
   ──── MERGE POINT 1: Schema + middleware ready ────
Batch 2: WS-B + WS-D + WS-C5-C8 (Backend tracks in parallel)
   - WS-B1-B6 (Service catalog backend)
   - WS-D1-D5 (Fleet + delegation backend) — parallel with WS-B
   - WS-C5-C8 (Multi-user runtime) — parallel, no dependency on WS-B
   ──── MERGE POINT 2: All backend APIs ready ────
Batch 3: WS-C1-C4 + WS-E (Gateway dynamic + Frontend)
   - WS-C1-C4 (Dynamic loader, health reporter) — depends on WS-B4
   - WS-E1-E7 (Frontend admin pages) — depends on WS-B + WS-D APIs
   ──── MERGE POINT 3: Full feature functional ────
Batch 4: WS-F (Integration + Demo + E2E)
   - WS-F1-F4 (Employee updates, template enforcement, E2E, demo)
```

## All Tasks

| ID | Description | Deps | Complexity | Files | Classification |
|----|-------------|------|------------|-------|----------------|
| **WS-A1** | Alembic migration: 3 tables + 2 column mods | None | M | `alembic/versions/xxx_add_service_registry.py` | Create |
| **WS-A2** | SQLAlchemy models: ServiceRegistry, ServiceOAuthConfig, DelegationTemplate | A1 | S | `models/service_registry.py`, `models/delegation_template.py` | Create |
| **WS-A3** | KMS client wrapper with Fernet fallback | None | M | `core/kms.py`, `tests/core/test_kms.py` | Create |
| **WS-A4** | Admin middleware (require_admin) + claims update | A1 | S | `middleware/admin_auth.py`, `tests/middleware/test_admin_auth.py` | Create |
| **WS-A5** | Seed script + role assignment endpoint | A1, A4 | S | `scripts/seed_admin.py`, endpoint in `admin_services.py` or `users.py` | Create |
| **WS-B1** | Service registry CRUD service | A2, A3 | M | `services/service_registry_service.py` | Create |
| **WS-B2** | Service registry CRUD endpoints (8 endpoints) | B1, A4 | M | `api/v1/endpoints/admin_services.py` | Create |
| **WS-B3** | OAuth config endpoints (GET/PUT) | B1 | S | Part of `admin_services.py` | Create |
| **WS-B4** | Internal registry API (GET /internal/services/registry) | B1 | S | Modify `api/v1/endpoints/internal.py` | Modify |
| **WS-B5** | Health reporting endpoint (POST /internal/services/{id}/health) | A2 | S | Modify `api/v1/endpoints/internal.py` | Modify |
| **WS-B6** | Register admin routers in main.py | B2 | S | Modify `main.py`, `api/v1/api.py` | Modify |
| **WS-C1** | Dynamic backend loader (DynamicBackendLoader) | B4 | L | `backends/dynamic_registry.py` | Create |
| **WS-C2** | Gateway startup integration | C1 | M | Modify `main.py` | Modify |
| **WS-C3** | ToolCache dynamic population from discovered_tools | C1 | S | Modify `tool_definitions.py` or `tool_cache.py` | Modify |
| **WS-C4** | Health reporter (probe + POST to Control Plane) | C1, B5 | M | Part of `dynamic_registry.py` | Create |
| **WS-C5** | Multi-user: extract user_id from _meta | None | S | Modify `handlers/tools_call.py` | Modify |
| **WS-C6** | Multi-user: per-user delegation resolution | C5 | M | Modify `handlers/tools_call.py` | Create |
| **WS-C7** | Multi-user: credential injection with user_id | C6 | M | Modify `middleware/credential_injection.py` | Modify |
| **WS-C8** | Backward compatibility: fallback to JWT owner | C5 | S | Part of C5/C6 changes | Modify |
| **WS-D1** | Admin fleet API (GET /admin/agents cross-user) | A4 | M | `api/v1/endpoints/admin_fleet.py` | Create |
| **WS-D2** | Agent suspend (POST /admin/agents/{id}/suspend) | D1 | S | Part of `admin_fleet.py` | Create |
| **WS-D3** | Delegation template CRUD service + endpoints | A2, A4 | M | `services/delegation_template_service.py`, `api/v1/endpoints/admin_fleet.py` | Create |
| **WS-D4** | Admin delegation management (cross-user, create on behalf, bulk revoke) | D3 | M | `api/v1/endpoints/admin_fleet.py` | Create |
| **WS-D5** | Emergency endpoints (suspend-all, disable-delegations, lockdown) | A4 | M | `api/v1/endpoints/admin_emergency.py` | Create |
| **WS-E1** | Admin role hook + conditional sidebar + route guard | A4 | M | `hooks/useAdminRole.ts`, modify `sidebar.tsx` | Create + Modify |
| **WS-E2** | Service Catalog page with type-aware rows | B2 | L | `admin/services/page.tsx` | Create |
| **WS-E3** | Add Service modal with type selector | B2 | M | `components/admin/AddServiceModal.tsx` | Create |
| **WS-E4** | Gateway Health dashboard + emergency controls | B5, D5 | L | `admin/health/page.tsx` | Create |
| **WS-E5** | Agent Fleet view with multi-user lifecycle | D1 | L | `admin/agents/page.tsx` | Create |
| **WS-E6** | Delegation Management with template editor | D3, D4 | L | `admin/delegations/page.tsx`, `DelegationTemplateEditor.tsx` | Create |
| **WS-E7** | Admin TypeScript types | None | S | `lib/types/admin.ts` | Create |
| **WS-F1** | Employee services page reads from DB | B4 | M | Modify `services/page.tsx` | Modify |
| **WS-F2** | Delegation creation enforces template ceilings | D3 | M | Modify `delegation.py` endpoint | Modify |
| **WS-F3** | Full-flow E2E tests | C7, D5, E6 | L | `tests/e2e/test_admin_service_catalog_e2e.py` | Create |
| **WS-F4** | Multi-user demo script | C7, E5 | M | `demos/demo_admin_multi_user.py` | Create |

## Critical Path

```
WS-A1 → WS-A2 → WS-B1 → WS-B4 → WS-C1 → WS-C2 → WS-F3
       ↘ WS-A4 → WS-D1 → WS-D5 → WS-E4
```

Longest path: 7 tasks (A1 → A2 → B1 → B4 → C1 → C2 → F3)

## Estimated Effort

| Size | Count | Approx Hours |
|------|-------|--------------|
| S (< 1hr) | 12 | ~10 |
| M (1-3hr) | 16 | ~32 |
| L (3+ hr) | 7 | ~28 |
| **Total** | **35** | **~70 hours** |

## Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|------------|
| GCP KMS not available in dev | Medium | Fernet fallback built into WS-A3 design |
| GenericMCPClient untested in production | Medium | WS-C1 needs extensive testing against real MCP servers |
| Multi-user credential isolation | High | WS-C7 must prevent cross-user token leakage — security-critical |
| Admin role bypass | High | WS-A4 must be fail-closed — block if role check fails |
| Migration on production DB | Medium | Test migration on staging first. Ensure nullable columns for backward compat |
