# Codebase Analysis: P5.2 IT Admin Service Catalog + MCP Server Management

> **Generated:** May 29, 2026 by `/run-plan --auto-heal --skip-checkpoint`
> **Design Doc:** `docs/design/p5.2-it-admin-service-catalog.md`
> **Feature:** `it-admin-service-catalog-mcp-mgmt`

## Summary

| Category | Count |
|----------|-------|
| Tasks in design | 35 |
| Classified as Create | 25 |
| Classified as Modify | 10 |
| Classified as Verify | 0 |
| Classified as Skip | 0 |

All 35 tasks require implementation work. No existing implementations match the design — this is a greenfield feature with modifications to existing files.

---

## Control Plane (`deeptrail-control/`)

### Models (`app/models/`)

| Component | Status | Evidence |
|-----------|--------|----------|
| `service_registry.py` | **MISSING** | No file exists. 15 models present, none for service registry |
| `delegation_template.py` | **MISSING** | No file exists |
| `user_session.py` → `role` column | **MISSING** | File exists (UserSession model) but no `role` column |
| `delegation.py` → `template_id`, `source` | **MISSING** | File exists (DelegationToken model) but no `template_id` or `source` columns |

### Middleware (`app/middleware/`)

| Component | Status | Evidence |
|-----------|--------|----------|
| `middleware/` directory | **MISSING** | Directory does not exist. No admin auth middleware anywhere |
| `admin_auth.py` | **MISSING** | — |
| Role checking in `api/deps.py` | **MISSING** | deps.py has placeholder comment: "# You can add more dependencies here later, e.g., for role checks" |

### Services (`app/services/`)

| Component | Status | Evidence |
|-----------|--------|----------|
| `service_registry_service.py` | **MISSING** | 18 service files exist, none for service registry |
| `delegation_template_service.py` | **MISSING** | `delegation_service.py` exists but handles existing delegation CRUD only |

### Core (`app/core/`)

| Component | Status | Evidence |
|-----------|--------|----------|
| `kms.py` | **MISSING** | 8 core files exist, no KMS/encryption wrapper |
| `config.py` | EXISTS | May need `ADMIN_EMAILS` and `FERNET_KEY` config additions |

### API Endpoints (`app/api/v1/endpoints/`)

| Component | Status | Evidence |
|-----------|--------|----------|
| `admin_services.py` | **MISSING** | 13 endpoint files exist, none with "admin" prefix |
| `admin_fleet.py` | **MISSING** | — |
| `admin_emergency.py` | **MISSING** | — |
| `internal.py` | EXISTS | Has existing internal endpoints. Needs registry + health endpoints added |
| `delegation.py` | EXISTS | Needs template enforcement integration |
| Router registration (`api.py`, `main.py`) | EXISTS | Need admin routers added |

### Scripts

| Component | Status | Evidence |
|-----------|--------|----------|
| `seed_admin.py` | **MISSING** | No admin seed script |

### Migrations (`alembic/versions/`)

| Component | Status | Evidence |
|-----------|--------|----------|
| `service_registry` migration | **MISSING** | No migration for service_registry, service_oauth_configs, or delegation_templates |

### Tests

Existing test files: `tests/` directory with standard pytest structure. No admin-related tests exist.

---

## Gateway (`deeptrail-gateway/`)

### Backends (`app/backends/`)

| Component | Status | Evidence |
|-----------|--------|----------|
| `adapter.py` (BackendClientAdapter) | EXISTS | Has `register_client()`. Needs `unregister_client()` for dynamic lifecycle |
| `connection_manager.py` (BackendConnectionManager) | EXISTS | Has `register_backend()`. Supports dynamic addition already |
| `base_mcp_client.py` (GenericMCPClient) | EXISTS | Full MCP protocol client with `initialize()`, `list_tools()`, `call_tool()`. **Not wired into production** |
| `dynamic_registry.py` | **MISSING** | No dynamic registry loader |
| DirectClients (6) | EXISTS | notion, slack, hubspot, gdrive, gcalendar, gmail — all functional |

### MCP Handlers (`app/mcp/`)

| Component | Status | Evidence |
|-----------|--------|----------|
| `tool_cache.py` (ToolCache) | EXISTS | TTL-based cache with `set_tools()`, `get_tools()`. Ready for dynamic population |
| `tool_definitions.py` | EXISTS | Hardcoded NOTION_TOOLS, SLACK_TOOLS, etc. Needs to work alongside dynamic tools |
| `handlers/tools_call.py` | EXISTS | Uses `_resolve_owner()` from JWT. No `_meta.user_id` handling |
| `permission_mapper.py` | EXISTS | Static permission mapping. Needs dynamic extension for MCP tools |

### Middleware (`app/middleware/`)

| Component | Status | Evidence |
|-----------|--------|----------|
| `credential_injection.py` | EXISTS | `inject_credentials()` accepts `user_id` for refresh but NOT for credential selection |
| `delegation_validator.py` | EXISTS | Validates delegation permissions. Needs per-user delegation support |

### Core (`app/core/`)

| Component | Status | Evidence |
|-----------|--------|----------|
| `config.py` | EXISTS | Has `control_plane_url`, `gateway_internal_api_token`. Needs `registry_refresh_interval` |

### Main (`app/main.py`)

| Component | Status | Evidence |
|-----------|--------|----------|
| Backend initialization | EXISTS | Uses `create_backend_adapter()` factory — hardcoded. Needs dynamic loader integration |
| Lifespan | EXISTS | Needs dynamic loader startup + periodic refresh task |

---

## Frontend (`frontend/`)

### Pages

| Component | Status | Evidence |
|-----------|--------|----------|
| `/dashboard/admin/services/page.tsx` | **MISSING** | No admin directory exists |
| `/dashboard/admin/agents/page.tsx` | **MISSING** | — |
| `/dashboard/admin/delegations/page.tsx` | **MISSING** | — |
| `/dashboard/admin/health/page.tsx` | **MISSING** | — |
| `/dashboard/services/page.tsx` | EXISTS | Hardcoded `SERVICE_CATALOG` array. Needs DB-driven loading |
| `/dashboard/delegation/` | EXISTS | Delegation pages exist. Need template enforcement UI |

### Components

| Component | Status | Evidence |
|-----------|--------|----------|
| `components/admin/` directory | **MISSING** | No admin components directory |
| `AddServiceModal.tsx` | **MISSING** | — |
| `DelegationTemplateEditor.tsx` | **MISSING** | — |
| `components/layout/sidebar.tsx` | EXISTS | 9 nav items, no role-based rendering, no "admin" references |

### Hooks & Types

| Component | Status | Evidence |
|-----------|--------|----------|
| `hooks/useAdminRole.ts` | **MISSING** | Only `useAgentNames.ts` and `useSSE.ts` exist |
| `lib/types/admin.ts` | **MISSING** | Types directory exists but no admin types |

---

## Task Classification Summary

| Task ID | Description | Classification | Rationale |
|---------|-------------|----------------|-----------|
| WS-A1 | Alembic migration (3 tables + 2 column mods) | Create | No existing migration |
| WS-A2 | SQLAlchemy models (3 new) | Create | No existing models |
| WS-A3 | KMS client wrapper | Create | No KMS utility exists |
| WS-A4 | Admin middleware | Create | No middleware dir exists |
| WS-A5 | Seed script + role API | Create | No seed script |
| WS-B1 | Service registry service | Create | No service file |
| WS-B2 | Service CRUD endpoints | Create | No admin endpoints |
| WS-B3 | OAuth config endpoints | Create | — |
| WS-B4 | Internal registry API | Modify | `internal.py` exists, needs new endpoints |
| WS-B5 | Health reporting endpoint | Modify | `internal.py` exists, needs new endpoint |
| WS-B6 | Register admin routers | Modify | `main.py` and `api.py` exist, need router additions |
| WS-C1 | Dynamic backend loader | Create | No `dynamic_registry.py` |
| WS-C2 | Gateway startup integration | Modify | `main.py` exists, needs loader init |
| WS-C3 | ToolCache dynamic population | Modify | `tool_cache.py` exists, works already |
| WS-C4 | Health reporter | Create | New functionality in dynamic_registry |
| WS-C5 | Extract user_id from _meta | Modify | `tools_call.py` exists, needs `_meta` handling |
| WS-C6 | Per-user delegation resolution | Create | New function in tools_call.py |
| WS-C7 | User-scoped credential injection | Modify | `credential_injection.py` exists, needs user_id selection |
| WS-C8 | Backward compatibility | Modify | Existing flow needs preservation |
| WS-D1 | Admin fleet API | Create | No admin endpoints |
| WS-D2 | Agent suspend | Create | — |
| WS-D3 | Delegation template CRUD | Create | No template service/endpoints |
| WS-D4 | Admin delegation management | Create | — |
| WS-D5 | Emergency endpoints | Create | — |
| WS-E1 | Role hook + sidebar | Create + Modify | No hook; sidebar needs modification |
| WS-E2 | Service Catalog page | Create | No admin pages |
| WS-E3 | Add Service modal | Create | — |
| WS-E4 | Health dashboard | Create | — |
| WS-E5 | Agent Fleet view | Create | — |
| WS-E6 | Delegation Management | Create | — |
| WS-E7 | Admin TypeScript types | Create | No admin types file |
| WS-F1 | Employee services from DB | Modify | Services page exists, needs DB source |
| WS-F2 | Template enforcement | Modify | Delegation endpoint exists, needs template check |
| WS-F3 | E2E tests | Create | No admin E2E tests |
| WS-F4 | Multi-user demo | Create | No demo script |

---

## Key Existing Infrastructure to Leverage

1. **GenericMCPClient** (`deeptrail-gateway/app/backends/base_mcp_client.py`): Full MCP protocol implementation. Ready to connect to remote MCP servers.
2. **BackendConnectionManager** (`deeptrail-gateway/app/backends/connection_manager.py`): Dynamic backend registration. `register_backend(BackendConfig)` already works.
3. **ToolCache** (`deeptrail-gateway/app/mcp/tool_cache.py`): TTL-based tool schema cache. `set_tools()` and `get_tools()` ready for dynamic population.
4. **BackendClientAdapter** (`deeptrail-gateway/app/backends/adapter.py`): Client routing. Has `register_client()`, needs `unregister_client()`.
5. **Internal API** (`deeptrail-control/app/api/v1/endpoints/internal.py`): Existing internal endpoint file. Ready for registry + health endpoints.
6. **Delegation service** (`deeptrail-control/app/services/delegation_service.py`): Existing delegation CRUD. Template enforcement hooks in here.
7. **OAuth service** (`deeptrail-control/app/services/oauth_service.py`): Existing OAuth flow. Currently reads from env vars — needs DB source option.
