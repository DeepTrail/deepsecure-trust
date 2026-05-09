# Spec: DeepSecure MVP Foundation — DB Persistence, Schema Fixes & Integration Verification

---

## Priority & Roadmap Mapping

> **Why this section exists:** The `plans/PRIORITY_MASTER.md` and `plans/PRODUCT_ROADMAP.md` define the sequence all workstreams must follow. This mapping shows exactly where this spec sits in that sequence, which priorities it covers, and what it unblocks.

### Priority Master Mapping ([`plans/PRIORITY_MASTER.md`](../../plans/PRIORITY_MASTER.md))

This spec consolidates **Priority 1A**, **Priority 1B**, and **Tooling** from the Priority Master — the three groups that must land before any Q3 work begins.

| Priority Group | Coverage | Items in This Spec |
|---------------|----------|--------------------|
| **Priority 1A — Foundation** *(Sequential: must run C1 → C2)* | ✅ Full | C1: Alembic migrations (`delegation_tokens`, `agent_sessions`, `audit_events`) → C2: Replace `_delegations` dict, `_mvp_audit_events` list, `try/except` hack with DB persistence |
| **Priority 1B — Schema Fixes** *(Parallel with 1A)* | ✅ Full | Vault flexible auth, policy aliases, task optional fields, audit filter aliases, ScopeMapper Level 1 DB column, cross-mapper consistency test, E3 `db=db` one-line fix |
| **Tooling — Cross-Cutting** *(Any time, independent)* | ✅ Full | `scripts/verify_integration.py` (5 checks), `run-batch` Step 6.5, Steps 6g/6h/6i |
| **Priority 2 — Core Experience** *(After 1A)* | ⚠️ Partial | C3b: WelcomeWizard real OAuth buttons; C5: `GET /audit/events/stream` SSE endpoint — pulled forward because they share files already being modified in Track B |
| **Priority 2 — Agent Lifecycle** *(After 1A)* | ❌ Not in scope | Lifecycle state API, session tracking, lifecycle badges UI, agent detail redesign — deferred to next workstream |
| **Priority 2B — Claude Code** *(After 1A)* | ❌ Not in scope | MCP proxy, plugin scaffold, hooks, skills — deferred to next workstream |
| **Priority 3 — Token Refresh Worker** *(Independent)* | ❌ Not in scope | Full `TokenRefreshWorker` asyncio loop — deferred; only the E3 one-line fix (B1) is in scope |
| **Priority 4 — AgentCore** *(Future)* | ❌ Not in scope | Design doc only, no plan file yet |

### Product Roadmap Mapping ([`plans/PRODUCT_ROADMAP.md`](../../plans/PRODUCT_ROADMAP.md))

This spec delivers the entirety of **Phase 1: Now — Q2 2026 (Foundation)** plus two items pulled forward from Phase 2.

| Roadmap Phase | Coverage | What This Spec Delivers |
|--------------|----------|------------------------|
| **Phase 1: Now — Q2 2026 (Foundation)** | ✅ Complete | All Priority 1A items, all Priority 1B items, all Tooling items — listed explicitly in the Phase 1 roadmap tables |
| **Phase 2: Q3 2026 (Core Experience)** | ⚠️ Partial (2 of 7 items) | C3b: Onboarding OAuth buttons; C5: SSE audit stream route — both pulled forward because they touch files already modified in Track B and have no DB dependency |
| **Phase 3: Q4 2026 (Enterprise + Identity)** | ❌ Not in scope | AgentCore, Admin governance, Security capabilities |
| **Phase 4: Future / Backlog** | ❌ Not in scope | Emergency controls, SIEM, framework integrations |

### Persona Capability Unlocked by This Spec

Taken directly from the roadmap's **"Persona Capability Timeline"**:

| Persona | Capability Unlocked ("Now" column after 1A + 1B) |
|---------|--------------------------------------------------|
| **Employee (Sarah)** | Delegations persist across restarts; correct permission list (no phantom HubSpot); vault accessible; OAuth service connection end-to-end |
| **IT Admin (Alex)** | Audit trail persists; vault page accessible; policy creation works; audit date filters work |
| **Security Team** | Audit trail persists; `from_date`/`to_date`/`token_layer` filters work; policy creation works |
| **Engineer / Developer** | `verify_integration.py` catches cross-service regressions in CI; mapper consistency test; run-batch Step 6.5; clean error paths in agents endpoint |

### What This Spec Unblocks

| Blocked Item | Needs | Covered By |
|--------------|-------|-----------|
| Priority 2: `lifecycle_state` API | 1A `agent_sessions` + `delegation_tokens` tables | Track A (this spec) |
| Priority 2: SSE real-time activity feed | 1A `audit_events` table | Track A (this spec) |
| Priority 2B: Claude Code plugin demo | 1A delegations survive restart | Track A (this spec) |
| Priority 3: `TokenRefreshWorker` reliable | 1B E3 `db=db` fix | Track B B1 (this spec) |
| `frontend-architecture` Batch 7 (E8 onboarding E2E, F5 audit analytics) | Both 1A + 1B working | Both tracks (this spec) |

---

## 1. Objective

After completing Batches 1–6 of the `frontend-architecture` workstream, a manual cross-service review discovered four categories of systemic issues that make every stateful page in the dashboard broken in production. This spec consolidates the fixes into a single workstream that must land before any Q3 features (agent lifecycle UI, SSE live feeds, onboarding OAuth, Claude Code plugin) are built on top of it.

**Without this workstream:** Priority 2 and Priority 2B features would be built on in-memory state that vanishes on every container restart, repeating the same mistake as the current code.

### Problem Categories

| # | Category | Symptoms | Root Cause |
|---|----------|----------|------------|
| 1 | **Missing DB migrations** | Delegations reset on restart; audit trail empties on restart; agent tools list always fails | 3 SQLAlchemy models exist (`DelegationToken`, `AgentSession`, `AuditEvent`) but no Alembic migration was ever created for them |
| 2 | **In-memory storage** | All delegation data lost on container restart; audit events accumulate only until restart | `_delegations: dict = {}` and `_mvp_audit_events: list = []` module-level variables in endpoint files |
| 3 | **Schema mismatches** | Vault page returns 401; policy create returns 422; task create returns 422; audit filters silently ignored | Frontend sends field names or auth headers not matching what backend Pydantic models expect |
| 4 | **Missing backend route** | Agent activity feed always 404s | `frontend/src/app/api/events/stream/route.ts` proxies to `/api/v1/audit/events/stream` which does not exist in `audit.py` |
| 5 | **No cross-service verification** | Issues 1–4 were not caught by run-batch Step 6 audit | Step 6 is a per-task, single-service static checker; cannot see cross-service contracts, runtime behavior, or implicit dependencies |

### Success Criteria

- [ ] `delegation_tokens`, `agent_sessions`, `audit_events` tables exist in PostgreSQL after `alembic upgrade head`
- [ ] Delegations created via the dashboard survive a `docker compose restart deeptrail-control`
- [ ] Audit events persist across restarts and appear in the dashboard audit trail
- [ ] Vault page renders with real secret data (no 401) for authenticated dashboard users
- [ ] Policy create succeeds via the dashboard UI (no 422)
- [ ] Task create succeeds via the dashboard UI (no 422)
- [ ] Audit filters (`from_date`, `to_date`, `token_layer`) correctly filter results
- [ ] Agent activity SSE feed connects (no 404)
- [ ] `scripts/verify_integration.py` exits 0 with 0 CRITICAL findings after all fixes land
- [ ] `WelcomeWizard.tsx` shows real OAuth connect buttons (not static text) for onboarding step

---

## 2. Technical Design

### Services Affected

| Service | Impact | Changes |
|---------|--------|---------|
| `deeptrail-control` (DB) | **High** (Track A) | New Alembic migration; `delegation.py`, `audit.py`, `agents.py` endpoints use DB instead of memory |
| `deeptrail-control` (Schema) | **Medium** (Track B) | `vault.py`, `policies.py`, `tasks.py`, `audit.py`, `users.py` endpoint schema fixes |
| `deeptrail-control` (New route) | **Low** (Track B) | Add `GET /api/v1/audit/events/stream` SSE endpoint |
| `frontend/` | **Low** (Track B) | `WelcomeWizard.tsx` real OAuth connect buttons |
| `scripts/` | **Low** (Tooling) | New `verify_integration.py` cross-service static checker |
| `.cursor/commands/run-batch.md` | **Low** (Tooling) | Add Step 6.5 integration verification + Steps 6g/6h/6i |
| `.claude/commands/run-batch.md` | **Low** (Tooling) | Same as above, kept in sync |

### Tracks and Dependencies

```
Track T (Tooling)   ─────────────────────────────────────────────────────────→ merge (any time)
Track B (1B Schema) ──── B1 ── B2 ── B3 ── B4 ── B5 ──── B6* ── B7 ─────────→ merge (any time, B6 after A1 if ScopeMapper adds column)
Track A (1A DB)     ──── A1 → A2 → A3 → A4 ────────────────────────────────→ merge (before B6 ScopeMapper if that adds a column)

After all land:
feature/frontend-architecture → Batch 7 resumes (E8 onboarding E2E, F5 audit analytics)
```

`*` B6 (ScopeMapper Level 1) adds an `available_permissions JSONB` column to `connected_services`. If it requires a migration, A1 must land first. If it only updates the endpoint logic reading an existing column, it can run independently.

### Architecture: Why In-Memory State Was a Problem

The per-task, per-batch audit in `run-batch` Step 6 cannot detect cross-service issues because it asks "does this task's implementation match this task's spec?" — never "does the whole system work end-to-end?" Four structural blind spots:

```
What Step 6 Checks                  What It Cannot See
─────────────────────────────       ──────────────────────────────────────────
Read spec for WS-E3                 Cross-service contracts
Check files exist                     (frontend body shape vs backend schema)
Check acceptance criteria text      Cross-artifact dependencies
Check test files exist                (SQLAlchemy model exists, no migration)
Report: ✅ All files present        Runtime behavior
                                      (endpoint uses in-memory list vs DB)
                                    Implicit dependencies
                                      (frontend URL points to nonexistent route)
```

The fix: `scripts/verify_integration.py` — five deterministic, stdlib-only, no-running-services-required checks that catch all four categories. Runs in under 10 seconds.

### API Contracts

#### Track A — New/Modified Control Plane Endpoints

**Delegation endpoints** — behavior change, not contract change. `POST /api/v1/auth/delegate` and `GET /api/v1/auth/delegations` currently read/write `_delegations: dict`. After A2, they read/write `DelegationToken` rows in PostgreSQL. The API surface (paths, request bodies, response shapes) does not change.

**Agents endpoint** — `GET /api/v1/agents/{id}/tools` currently wraps logic in `try/except UndefinedTable`. After A4, the `try/except` is removed. The API surface does not change.

**Audit endpoints** — behavior change only. `GET /api/v1/audit/events` and `POST /api/v1/auth/agent/verify` currently read/write `_mvp_audit_events: list`. After A3, they use `AuditEvent` rows in PostgreSQL.

#### Track B — Schema Fix Endpoints

**Vault flexible auth** — endpoints currently accept only `APIKeyDep` (static `BACKEND_API_TOKEN`). After B2, they accept either the user's JWT Bearer token OR API key. No contract change — the frontend proxy already sends Bearer tokens.

**Policy aliases** — `PolicyCreate` / `PolicyUpdate` currently require `{ actions, resources, agent_id }`. After B3, field aliases allow the frontend to send `{ permissions, agent_ids }`. Both forms accepted.

| Method | Endpoint | Change |
|--------|----------|--------|
| POST | `/api/v1/policies/` | Accept `permissions` → `actions`, `agent_ids` → `agent_id` aliases |
| PUT | `/api/v1/policies/{id}` | Same aliases |

**Task schema** — `TaskCreate` currently requires `requested_permissions` (min 1 item) and ignores `agent_id` in body. After B4:

| Field | Before | After |
|-------|--------|-------|
| `requested_permissions` | Required, min 1 | Optional, defaults to `[]` |
| `agent_id` | Derived from JWT only | Accept from body as override |

**Audit filter aliases** — `GET /api/v1/audit/events` currently ignores unknown query params.

| Param | Before | After |
|-------|--------|-------|
| `from_date` | Silently ignored | Alias for `start_time` |
| `to_date` | Silently ignored | Alias for `end_time` |
| `token_layer` | Does not exist | New filter: `L2`/`L3`/`L4` |

**ScopeMapper Level 1** — `GET /api/v1/users/me/available-permissions` currently recomputes available permissions on every call from OAuth scopes stored at connect time. After B6:
- Add `available_permissions JSONB` column to `connected_services` table
- Populate it at OAuth callback time via `ScopeMapper`
- Endpoint reads from the DB column instead of recomputing

**SSE stream route** — new endpoint:

| Method | Endpoint | Auth | Purpose |
|--------|----------|------|---------|
| GET | `/api/v1/audit/events/stream` | JWT Bearer | Server-Sent Events stream of audit events. Optional query params: `agent_id`. Polls `audit_events` table every 2s, yields new events in SSE format. |

#### Tooling — No API Changes

`scripts/verify_integration.py` is a CLI script, not a server. `run-batch.md` changes add a new step 6.5 to the orchestration workflow.

### Data Models

#### New Alembic Migration (Track A, Task A1)

Three tables that have SQLAlchemy models but no corresponding migration:

**`delegation_tokens`** — stores delegation grants

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID | PK |
| `user_id` | UUID | FK → users |
| `agent_id` | VARCHAR | FK → agents |
| `permissions` | JSONB | List of permission strings |
| `expires_at` | TIMESTAMP | Delegation TTL |
| `created_at` | TIMESTAMP | |
| `is_active` | BOOLEAN | Default true |

**`agent_sessions`** — tracks agent authentication sessions

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID | PK |
| `agent_id` | VARCHAR | FK → agents |
| `user_id` | UUID | FK → users |
| `created_at` | TIMESTAMP | |
| `expires_at` | TIMESTAMP | |
| `source_ip` | VARCHAR | Optional |
| `last_used_at` | TIMESTAMP | Updated on tool calls |

**`audit_events`** — persists all platform events

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID | PK |
| `user_id` | UUID | on_behalf_of |
| `agent_id` | VARCHAR | acting agent |
| `delegation_id` | UUID | FK → delegation_tokens |
| `agent_session_id` | UUID | FK → agent_sessions |
| `mcp_session_id` | VARCHAR | Gateway session |
| `event_type` | VARCHAR | `mcp_tool_call`, `permission_denied`, `delegation_created`, etc. |
| `tool` | VARCHAR | nullable |
| `success` | BOOLEAN | |
| `duration_ms` | INTEGER | nullable |
| `extra_data` | JSONB | arguments, result_summary, reason, etc. |
| `created_at` | TIMESTAMP | indexed |

### Architecture Decisions

| Decision | Options Considered | Chosen | Rationale |
|----------|--------------------|--------|-----------|
| Migration scope | One migration per table vs single migration | Single migration for all 3 tables | Atomic — either all 3 exist or none; simpler rollback |
| In-memory replacement strategy | Drop-in DB replacement vs refactor | Drop-in replacement | Keep the endpoint interface identical; change only the storage layer |
| Vault auth approach | Require JWT everywhere vs API key everywhere vs flexible | Flexible auth (JWT first, fallback to API key) | BFF proxy sends JWT; gateway internal calls send API key; both must work |
| ScopeMapper persistence | Compute at call time vs cache in DB | DB column on `connected_services` | Eliminates repeated computation; enables consistent permissions across sessions |
| SSE implementation | WebSocket vs SSE vs polling | SSE via polling loop | Matches existing gateway pattern; works with HTTP/1.1 and BFF cookie auth; unidirectional is sufficient |
| verify_integration.py scope | Full E2E tests vs static checks | Static checks only | No running containers needed; fast (< 10s); catches all four issue categories statically |

---

## 3. Project Structure

### Files to Create

| File | Purpose | Track |
|------|---------|-------|
| `scripts/verify_integration.py` | 5 cross-service static checks (model-migration parity, route existence, auth compat, body shape, in-memory detection) | T |
| `deeptrail-control/alembic/versions/XXXX_add_delegation_agent_session_audit_tables.py` | Alembic migration for 3 missing tables | A |

### Files to Modify

| File | Change | Track |
|------|--------|-------|
| `.cursor/commands/run-batch.md` | Add Step 6.5 integration verification between Step 6 (spec audit) and Step 7 (batch verify); add Steps 6g/6h/6i | T |
| `.claude/commands/run-batch.md` | Same as above, kept in sync | T |
| `deeptrail-control/app/api/v1/endpoints/delegation.py` | Replace `_delegations` dict with `DelegationToken` DB reads/writes | A |
| `deeptrail-control/app/api/v1/endpoints/audit.py` | Replace `_mvp_audit_events` list with `AuditEvent` DB; add filter aliases; add SSE stream endpoint | A + B |
| `deeptrail-control/app/api/v1/endpoints/agents.py` | Remove `try/except UndefinedTable` hack in `get_agent_tools` | A |
| `deeptrail-control/app/api/v1/endpoints/vault.py` | Flexible auth (JWT or API key); fix `db=db` bug in E3 refresh | B |
| `deeptrail-control/app/api/v1/endpoints/policies.py` | Field aliases in `PolicyCreate`/`PolicyUpdate` | B |
| `deeptrail-control/app/api/v1/endpoints/tasks.py` | Make `requested_permissions` optional; accept `agent_id` in body | B |
| `deeptrail-control/app/api/v1/endpoints/users.py` | `available-permissions` reads from `connected_services.available_permissions` JSONB column; OAuth callback populates column | B |
| `frontend/src/components/onboarding/WelcomeWizard.tsx` | Real OAuth connect buttons per service (notion, slack, gdrive, gmail, gcalendar); same flow as services/page.tsx | B |

---

## 4. Testing Strategy

### Test Levels

| Level | What | Location | Framework |
|-------|------|----------|-----------|
| Unit | `verify_integration.py` checks against fixture files | `tests/` | pytest |
| Unit | Vault flexible auth dependency | `deeptrail-control/tests/api/v1/` | pytest |
| Unit | `TokenRefreshWorker` mock tests | `deeptrail-control/tests/services/` | pytest |
| Integration | Delegation persistence across restart | `deeptrail-control/tests/api/v1/test_delegation.py` | pytest |
| Integration | Audit event persistence | `deeptrail-control/tests/api/v1/test_audit.py` | pytest |
| Integration | Policy create 201 (not 422) | `deeptrail-control/tests/api/v1/test_policies.py` | pytest |
| Integration | Task create 201 (not 422) | `deeptrail-control/tests/api/v1/test_tasks.py` | pytest |
| Integration | Vault read 200 (not 401) with JWT auth | `deeptrail-control/tests/api/v1/test_vault.py` | pytest |
| Integration | SSE stream 200 + event stream header | `deeptrail-control/tests/api/v1/test_audit.py` | pytest |
| E2E | Dashboard pages after restart | `tests/e2e/` | Playwright |

### Coverage Requirements

- `scripts/verify_integration.py`: 100% of the 5 check functions
- Delegation endpoint: test create, list, and persistence across DB session boundary
- Audit endpoint: test persist and retrieve; test filter aliases; test SSE headers
- Vault endpoint: test JWT auth path; test API key auth path; test flexible auth logic
- Cross-mapper consistency test: assert every `ScopeMapper.SCOPE_TO_PERMISSIONS` entry exists in `PermissionMapper.TOOL_TO_PERMISSION`

### Validation Script

After all fixes land, run:

```bash
# 1. Apply migrations
cd deeptrail-control
alembic upgrade head

# 2. Start services
cd ..
docker compose up deeptrail-control deeptrail-gateway db redis -d

# 3. Run cross-service verification
python scripts/verify_integration.py
# Expected: 0 CRITICAL findings, exit code 0

# 4. Run backend tests
cd deeptrail-control
pytest tests/ -v
# Expected: all pass

# 5. Restart control plane — delegations must survive
docker compose restart deeptrail-control
USER_TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"password"}' | jq -r '.token')
curl -s http://localhost:8000/api/v1/auth/delegations \
  -H "Authorization: Bearer $USER_TOKEN" | jq '.total'
# Expected: same count as before restart
```

---

## 5. Boundaries

### Always Do

- Run `verify_integration.py` before marking any Track A or Track B task complete
- Apply the Alembic migration in a transaction — both apply cleanly or roll back entirely
- Keep `.cursor/commands/run-batch.md` and `.claude/commands/run-batch.md` in sync (same content)
- Test vault auth with both JWT Bearer AND API key paths — flexible auth must not break gateway internal calls

### Ask First

- Changes to Alembic migration rollback behavior (default is irreversible data removal)
- Changes to `ScopeMapper` or `PermissionMapper` beyond the Level 1 DB column addition
- New columns added to existing tables outside of the 3 missing tables (different migration scope)

### Never Do

- Remove the `_delegations` in-memory dict without first verifying the migration applied
- Add `verify_integration.py` as a blocking CI step before it has been run against the live codebase at least once
- Merge Track A into `feature/frontend-architecture` before the Alembic migration has been tested locally with `alembic upgrade head && alembic downgrade -1`

---

## 6. Validation Scenarios

### Scenario 1: Delegation Persistence

```
Step 1: Create delegation via dashboard → agent detail page
Step 2: Verify delegation appears in GET /api/v1/auth/delegations response
Step 3: docker compose restart deeptrail-control
Step 4: GET /api/v1/auth/delegations again
Step 5: Expected: same delegation still present (not 0)
```

### Scenario 2: Audit Trail Persistence

```
Step 1: Trigger some tool calls via MCP gateway
Step 2: Navigate to audit trail → verify events appear
Step 3: docker compose restart deeptrail-control
Step 4: Navigate to audit trail again
Step 5: Expected: same events still present
```

### Scenario 3: Vault Page No 401

```
Step 1: Login via SSO (JWT cookie set)
Step 2: Navigate to /vault
Step 3: Expected: vault secrets list renders (not 401 error card)
Step 4: Create a secret via the form
Step 5: Expected: 201 response, secret appears in list
```

### Scenario 4: Policy and Task Create

```
Step 1: Navigate to /policies → New Policy
Step 2: Fill form and submit
Step 3: Expected: 201 (not 422), policy appears in list

Step 4: Navigate to /tasks → New Task
Step 5: Fill form (no requested_permissions needed) and submit
Step 6: Expected: 201 (not 422), task appears in list
```

### Scenario 5: Integration Verification Script

```
$ python scripts/verify_integration.py

DeepSecure Integration Verification
====================================
Check 1: Model-Migration Parity          ✅ PASS (17/17 tables have migrations)
Check 2: Frontend-Backend Route Existence ✅ PASS (23/23 routes exist)
Check 3: Auth Mechanism Compatibility     ✅ PASS (no JWT/APIKey mismatches)
Check 4: Request Body Shape              ✅ PASS (no required field mismatches)
Check 5: In-Memory Storage Detection     ✅ PASS (no module-level mutable state)

Result: 0 CRITICAL  0 WARNING
Exit code: 0
```

### Scenario 6: SSE Agent Activity Feed

```
Step 1: Navigate to agent detail → Activity tab
Step 2: Trigger a tool call via MCP
Step 3: Expected: new event appears in activity feed without page refresh
Step 4: Inspect network tab → Expected: /api/events/stream is open with text/event-stream content-type
```

### Scenario 7: Onboarding OAuth Buttons

```
Step 1: Login as new user (onboarding_completed: false)
Step 2: Navigate to /onboarding → "Connect your first service" step
Step 3: Expected: real OAuth buttons for Notion, Slack, Google Drive, Gmail, Google Calendar
Step 4: Click "Connect Notion" → Expected: redirect to OAuth consent page
Step 5: Approve → redirect back to /onboarding with Notion shown as connected
```

---

## 7. Dependencies & Risks

### External Dependencies

| Dependency | Risk | Mitigation |
|------------|------|------------|
| Existing `users` and `agents` tables | `delegation_tokens` and `agent_sessions` FK reference them | Verify FK column names before writing migration; check `users.id` vs `agents.agent_id` |
| Alembic migration history | Two untracked migration stubs may conflict (`62d521598579`, `d4e5f6a7b8c9`) | Inspect existing migration chain head; use `alembic merge heads` if needed |
| OAuth callback flow | B6 ScopeMapper populates `available_permissions` at callback time | Existing OAuth callback in `users.py` must be modified atomically with DB column addition |

### Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Migration conflicts with existing untracked stubs | Medium | Medium | Inspect both stubs; merge or supersede before creating A1 migration |
| `get_agent_tools` hack removal breaks something unexpected | Low | Medium | Write test confirming tools endpoint works before and after removing `try/except` |
| Vault flexible auth breaks gateway internal API calls | Medium | High | Test API key path explicitly in integration tests; gateway calls use `BACKEND_API_TOKEN` |
| ScopeMapper Level 1 adds column that requires migration before B6 can land | Medium | Low | Coordinate B6 to run after A1; or make B6 additive-only (no migration needed) |
| `verify_integration.py` false positives block batch execution | Low | Low | Run manually first to baseline; add `--warn-only` flag for CI |
| SSE stream endpoint not closing cleanly on client disconnect | Medium | Low | Use `asyncio.CancelledError` handler in generator; standard pattern |

---

## 8. Open Questions

- [x] **Delegation token schema** → Use existing `DelegationToken` SQLAlchemy model from `app/models/delegation.py`
- [x] **Audit event fields** → Use existing `AuditEvent` SQLAlchemy model from `app/models/audit_event.py`
- [x] **Agent session fields** → Use existing `AgentSession` SQLAlchemy model (or `IDPSession` — verify)
- [x] **ScopeMapper Level 1 migration scope** → Add `available_permissions JSONB` column to `connected_services`; this is an additive migration that can be standalone if Track A is delayed
- [x] **run-batch sync strategy** → Both `.cursor/commands/run-batch.md` and `.claude/commands/run-batch.md` must be identical after each change; Tooling track includes explicit sync task T3
- [ ] **`verify_integration.py` in CI** → Should the script block CI on CRITICAL findings? Deferred until script has been validated against live codebase
- [ ] **Audit stream pagination** → Does `GET /audit/events/stream` need cursor-based pagination, or is a 2s poll sufficient for MVP? Propose: 2s poll is fine for MVP; stream all events for the given `agent_id` since last checkpoint

---

## 9. Implementation Tracks

### Track T — Tooling (independent, any time)

**Deliverables:**
- `scripts/verify_integration.py` with 5 static checks (exit 0 on pass, 1 on CRITICAL)
- `run-batch.md` Step 6.5 (invoke script between spec audit and batch verify)
- `run-batch.md` Steps 6g (build verify), 6h (container rebuild), 6i (browser smoke tests)
- Both `.cursor/` and `.claude/` run-batch files kept in sync

**Exit criteria:**
- `python scripts/verify_integration.py` runs without errors; correctly identifies the 4 known issue categories on the unpatched codebase
- After Track A and B land, script exits 0 with 0 CRITICAL

### Track A — Priority 1A: DB Persistence (sequential A1 → A2 → A3 → A4)

**Deliverables:**
- A1: Single Alembic migration covering `delegation_tokens`, `agent_sessions`, `audit_events`
- A2: `delegation.py` — replace `_delegations` dict with `DelegationToken` DB reads/writes
- A3: `audit.py` — replace `_mvp_audit_events` list with `AuditEvent` DB reads/writes
- A4: `agents.py` — remove `try/except UndefinedTable` hack from `get_agent_tools`

**Exit criteria:**
- `alembic upgrade head` applies cleanly
- `alembic downgrade -1` rolls back cleanly
- Delegations survive `docker compose restart deeptrail-control`
- Audit events survive `docker compose restart deeptrail-control`
- `verify_integration.py` Check 1 (model-migration parity) and Check 5 (in-memory storage) pass

### Track B — Priority 1B: Schema Fixes (all parallel, no DB dependency)

**Deliverables:**
- B1: `vault.py` — one-line fix: pass `db=db` to `vault_client.refresh_token()` (E3 bug)
- B2: `vault.py` — flexible auth dependency (JWT first, API key fallback)
- B3: `policies.py` — field aliases (`permissions→actions`, `agent_ids→agent_id`)
- B4: `tasks.py` — optional `requested_permissions`, accept `agent_id` in body
- B5: `audit.py` — `from_date`/`to_date` aliases, `token_layer` filter
- B6: `users.py` + OAuth callback — `available_permissions JSONB` column populated at OAuth time
- B7: `deeptrail-control/tests/` — cross-mapper consistency test
- C3b: `WelcomeWizard.tsx` — real OAuth buttons for onboarding connect step
- C5: `audit.py` — `GET /api/v1/audit/events/stream` SSE endpoint

**Exit criteria:**
- Vault page renders 200 for dashboard users authenticated via JWT
- Policy create returns 201 with `{ permissions: [...] }` body
- Task create returns 201 without `requested_permissions` in body
- Audit filters (`from_date`, `to_date`, `token_layer`) return filtered results
- `GET /api/v1/users/me/available-permissions` returns DB-backed results after OAuth connect
- Cross-mapper test passes: every `ScopeMapper` permission exists in `PermissionMapper`
- Onboarding wizard shows real OAuth connect buttons
- SSE endpoint returns 200 with `Content-Type: text/event-stream`
- `verify_integration.py` Check 3 (auth compat) and Check 4 (body shape) pass

---

## 10. References

### Source Plans (consolidated into this spec)

| Document | What It Covers |
|----------|----------------|
| [`plans/PRIORITY_MASTER.md`](../../plans/PRIORITY_MASTER.md) | Single source of truth mapping every priority item to its plan file |
| [`plans/integration_verification_pipeline.plan.md`](../../plans/integration_verification_pipeline.plan.md) | Root cause analysis, `verify_integration.py` design, all C1–C5 fix details |
| [`plans/agent_auth_flow_design_66bcb1ec.md`](../../plans/agent_auth_flow_design_66bcb1ec.md) | Four-state agent lifecycle (Priority 2, depends on Track A) |
| [`plans/proactive_token_refresh_e5fb79c0.plan.md`](../../plans/proactive_token_refresh_e5fb79c0.plan.md) | E3 `db=db` fix (B1) and Priority 3 token refresh worker |
| [`plans/post-batch-verification-steps.plan.md`](../../plans/post-batch-verification-steps.plan.md) | Steps 6g/6h/6i: build verification, container rebuild, browser smoke tests |

### Architecture & Context

| Document | What It Documents |
|----------|------------------|
| [`docs/architecture/db-schema-audit.md`](../architecture/db-schema-audit.md) | All 16 tables, 4 missing tables, page→API→DB map, schema mismatches — full gap analysis |
| [`docs/design/scope-permission-architecture.md`](../design/scope-permission-architecture.md) | ScopeMapper architecture, Level 0→3 evolution path |
| [`docs/architecture/PERMISSION_FLOW_ARCHITECTURE.md`](../architecture/PERMISSION_FLOW_ARCHITECTURE.md) | Four-layer permission flow, gap analysis, two-mapper design |
| [`docs/workstreams/mvp-foundation/WORKSTREAM.md`](../workstreams/mvp-foundation/WORKSTREAM.md) | Existing workstream tracking doc |

### Downstream Workstreams (unblocked by this spec)

| Workstream | Blocked On | Plan |
|------------|-----------|------|
| Agent lifecycle UI, SSE, onboarding OAuth (Priority 2) | Track A (delegation + audit DB) | `plans/agent_auth_flow_design_66bcb1ec.md` |
| Claude Code plugin demo (Priority 2B) | Track A (delegation persistence) | `plans/claude_code_integration.plan.md` |
| `frontend-architecture` Batch 7 | Both Track A + B | `docs/workstreams/frontend-architecture/STATUS.md` |

---

## Spec Complete

**Saved to:** `docs/spec/mvp-foundation-spec.md`
**Design Doc:** [`docs/design/mvp-foundation.md`](../design/mvp-foundation.md)

### Next Steps

1. `/run-plan mvp-foundation docs/spec/mvp-foundation-spec.md` — run the full PLAN phase
2. Review the generated `BREAKDOWN.md` and `BATCH_EXECUTION_PLAN.md`
3. Approve plan → `PIPELINE_STATE.md` written
4. `/run-batch 1 mvp-foundation` — begin execution
