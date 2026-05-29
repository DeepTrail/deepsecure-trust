# Workstream: P5.2 IT Admin Service Catalog + MCP Server Management

> **Feature:** `it-admin-service-catalog-mcp-mgmt`
> **Created:** May 29, 2026
> **Status:** Planning Complete → Ready for Execution
> **Design Doc:** `docs/design/p5.2-it-admin-service-catalog.md`
> **Spec:** `docs/spec/p5.2-it-admin-service-catalog-spec.md`
> **Plan File:** `plans/p5.2_it_admin_service_catalog_cd7a2c1d.plan.md`

---

## Executive Summary

Implement a complete IT Admin workflow for managing MCP backend services, agent fleets, and delegations across an organization. The core deliverables are:

1. **Dynamic Service Registry** — DB-driven service catalog replacing hardcoded backend config in frontend and gateway. Supports both REST+OAuth (existing DirectClients) and Remote MCP Servers (GenericMCPClient).
2. **Multi-User `tools/call`** — Agents specify `params._meta.user_id` per call; gateway resolves the correct user's delegation and OAuth tokens. Core customer requirement: 1 agent serving N users.
3. **Admin Role Model** — JWT `roles` claim + DB column, admin middleware, conditional UI navigation.
4. **Delegation Templates** — Per-permission ceilings with blocked permissions, rate limits, working hours. Frontend shows grayed-out blocked permissions with tooltips.
5. **Emergency Controls** — Suspend all agents, disable all delegations, full lockdown with audit trail.
6. **Admin UI** — 4 new pages: Service Catalog, Agent Fleet, Delegation Management, Gateway Health.

35 tasks, 6 workstreams, 4 batches, 3 merge points. Estimated ~70 hours of implementation.

---

## Scope

### In Scope
- Admin role model (JWT + DB, middleware, seed script)
- Service registry (3 new DB tables, CRUD API, encryption via GCP KMS)
- Dynamic gateway loading (registry API, periodic refresh, REST + MCP client instantiation)
- MCP tool auto-discovery (`tools/list` proxy)
- Multi-user `tools/call` (`_meta.user_id`, per-user delegation, per-user credentials)
- Admin fleet API (cross-user agent listing, suspend, delegation management)
- Delegation templates (per-permission ceilings, enforcement at delegation creation)
- Emergency controls (suspend-all, disable-delegations, lockdown)
- Admin frontend (4 pages, role hook, conditional sidebar)
- Employee services page migration (hardcoded → DB)

### Out of Scope (Non-Goals from Design Doc)
- IdP integration (Okta/Azure AD group sync) — manual role assignment for now
- MCP Authorization Spec Compliance — separate P5.3 workstream
- Vendor agent approval workflow — P6 (requires org model)
- Agent provisioning automation — future work

---

## Key Decisions

| Decision | Chosen | Rationale |
|----------|--------|-----------|
| Backend type discriminator | Single table with `backend_type` column | Both types share 80% of fields |
| Secret encryption | GCP KMS with Fernet fallback | GCP-native, Fernet for dev |
| Multi-user user_id location | `params._meta.user_id` | MCP convention for per-call metadata |
| Gateway registry refresh | Polling (60s) | Simplest, acceptable latency |
| Admin role source | JWT `roles` + DB `user_sessions.role` fallback | SSO covers JWT; DB covers non-SSO |
| Template enforcement | Full stack (frontend gray-out + backend validation) | Best UX + safety net |

---

## Batch Overview

| Batch | ID | Focus | Tasks | Merge Point |
|-------|-----|-------|-------|-------------|
| 1 | P0-B1 | Foundation: Admin Role + DB Schema + KMS | WS-A1, A2, A3, A4, A5 | MP1: Schema + middleware ready |
| 2 | P0-B2 | Backend APIs: Service Catalog + Fleet + Multi-User Runtime | WS-B1-B6, D1-D5, C5-C8 | MP2: All backend APIs ready |
| 3 | P0-B3 | Gateway Dynamic Loading + Admin Frontend | WS-C1-C4, E1-E7 | MP3: Full feature functional |
| 4 | P0-B4 | Integration: Employee Updates + E2E + Demo | WS-F1-F4 | — (final) |

---

## Critical Path

```
WS-A1 → WS-A2 → WS-B1 → WS-B4 → WS-C1 → WS-C2 → WS-F3
                ↘ WS-A4 → WS-D1 → WS-D5 → WS-E4
```

Longest chain: 7 tasks. Estimated duration: ~4-5 execution sessions.

---

## All Tasks

| ID | Description | Batch | Service | Complexity | Status |
|----|-------------|-------|---------|------------|--------|
| WS-A1 | Alembic migration (3 tables + 2 column mods) | B1 | Control | M | 🔲 |
| WS-A2 | SQLAlchemy models (ServiceRegistry, ServiceOAuthConfig, DelegationTemplate) | B1 | Control | S | 🔲 |
| WS-A3 | KMS client wrapper with Fernet fallback | B1 | Control | M | 🔲 |
| WS-A4 | Admin middleware (require_admin) + claims update | B1 | Control | S | 🔲 |
| WS-A5 | Seed script + role assignment endpoint | B1 | Control | S | 🔲 |
| WS-B1 | Service registry CRUD service | B2 | Control | M | 🔲 |
| WS-B2 | Service CRUD endpoints (8 endpoints) | B2 | Control | M | 🔲 |
| WS-B3 | OAuth config endpoints (GET/PUT) | B2 | Control | S | 🔲 |
| WS-B4 | Internal registry API | B2 | Control | S | 🔲 |
| WS-B5 | Health reporting endpoint | B2 | Control | S | 🔲 |
| WS-B6 | Register admin routers in main.py | B2 | Control | S | 🔲 |
| WS-C1 | Dynamic backend loader | B3 | Gateway | L | 🔲 |
| WS-C2 | Gateway startup integration | B3 | Gateway | M | 🔲 |
| WS-C3 | ToolCache dynamic population | B3 | Gateway | S | 🔲 |
| WS-C4 | Health reporter | B3 | Gateway | M | 🔲 |
| WS-C5 | Extract user_id from _meta | B2 | Gateway | S | 🔲 |
| WS-C6 | Per-user delegation resolution | B2 | Gateway | M | 🔲 |
| WS-C7 | User-scoped credential injection | B2 | Gateway | M | 🔲 |
| WS-C8 | Backward compatibility | B2 | Gateway | S | 🔲 |
| WS-D1 | Admin fleet API | B2 | Control | M | 🔲 |
| WS-D2 | Agent suspend | B2 | Control | S | 🔲 |
| WS-D3 | Delegation template CRUD | B2 | Control | M | 🔲 |
| WS-D4 | Admin delegation management | B2 | Control | M | 🔲 |
| WS-D5 | Emergency endpoints | B2 | Control | M | 🔲 |
| WS-E1 | Admin role hook + sidebar | B3 | Frontend | M | 🔲 |
| WS-E2 | Service Catalog page | B3 | Frontend | L | 🔲 |
| WS-E3 | Add Service modal | B3 | Frontend | M | 🔲 |
| WS-E4 | Health dashboard + emergency | B3 | Frontend | L | 🔲 |
| WS-E5 | Agent Fleet view | B3 | Frontend | L | 🔲 |
| WS-E6 | Delegation Management | B3 | Frontend | L | 🔲 |
| WS-E7 | Admin TypeScript types | B3 | Frontend | S | 🔲 |
| WS-F1 | Employee services from DB | B4 | Frontend | M | 🔲 |
| WS-F2 | Template enforcement | B4 | Control | M | 🔲 |
| WS-F3 | E2E tests | B4 | Cross | L | 🔲 |
| WS-F4 | Multi-user demo | B4 | Cross | M | 🔲 |

---

## Validation Criteria

### Per-Batch Acceptance

**Batch 1 (Foundation):**
- [ ] Migration runs clean: 3 tables created, 2 columns added
- [ ] Admin JWT returns 200; employee JWT returns 403 on admin endpoints
- [ ] KMS encrypt/decrypt works (mock KMS in test, Fernet in dev)
- [ ] Seed script sets admin role for specified emails

**Batch 2 (Backend APIs):**
- [ ] All 24 admin endpoints return correct responses per spec
- [ ] `tools/call` with `_meta.user_id` resolves correct user's delegation
- [ ] `tools/call` without `_meta.user_id` falls back to JWT owner (backward compat)
- [ ] Emergency suspend-all revokes all sessions + delegations with audit trail

**Batch 3 (Gateway + Frontend):**
- [ ] Gateway loads backends from registry on startup
- [ ] Gateway picks up new service within 60s after admin adds it
- [ ] Admin sees 4 admin nav items; employee does not
- [ ] Service Catalog page shows both REST and MCP services
- [ ] Agent Fleet shows per-user delegation details

**Batch 4 (Integration):**
- [ ] Employee services page loads from DB instead of hardcoded array
- [ ] Delegation creation blocked when exceeding template ceiling
- [ ] E2E test passes: admin adds MCP → gateway picks up → agent calls tool → audit logged
- [ ] Multi-user demo: 2+ users, different permissions, correct token selection

---

## History

| Date | Event |
|------|-------|
| May 28, 2026 | Design doc created (`docs/design/p5.2-it-admin-service-catalog.md`) |
| May 28, 2026 | Spec created (`docs/spec/p5.2-it-admin-service-catalog-spec.md`) |
| May 28, 2026 | Plan file created (`plans/p5.2_it_admin_service_catalog_cd7a2c1d.plan.md`) |
| May 29, 2026 | Codebase analysis completed — all 35 tasks confirmed as Create/Modify |
| May 29, 2026 | BREAKDOWN.md created — 35 tasks, 6 workstreams, 4 batches |
| May 29, 2026 | Workstream scaffolding created via `/run-plan --auto-heal --skip-checkpoint` |
