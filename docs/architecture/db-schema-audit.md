# Database Schema Audit: Tables vs. UI Requirements

> **Created:** May 7, 2026  
> **Source:** Analysis performed during [frontend integration debugging session](../../plans/integration_verification_pipeline.plan.md)  
> **Purpose:** Document the gap between SQLAlchemy models defined in code, Alembic migrations that exist, and what the UI actually needs to function end-to-end.

---

## Summary

The control plane defines **16 SQLAlchemy models** (tables). Of these, **4 have no Alembic migration** — they exist in code but not in the database. Three of those 4 missing tables directly break UI pages at runtime. All three use in-memory Python dicts or lists as workarounds, meaning their data is lost every time the container restarts.

---

## All 16 SQLAlchemy Models

| # | Table Name | Model File | Migration Exists? | Exists in DB? |
|---|-----------|-----------|-------------------|---------------|
| 1 | `agents` | `app/models/agent.py` | ✅ Yes | ✅ Yes |
| 2 | `credentials` | `app/models/credential.py` | ✅ Yes | ✅ Yes |
| 3 | `secrets` | `app/models/credential.py` | ✅ Yes | ✅ Yes |
| 4 | `nonces` | `app/models/nonce.py` | ✅ Yes | ✅ Yes |
| 5 | `policies` | `app/models/policy.py` | ✅ Yes | ✅ Yes |
| 6 | `attestation_policies` | `app/models/attestation_policy.py` | ✅ Yes | ✅ Yes |
| 7 | `connected_services` | `app/models/connected_service.py` | ✅ Yes | ✅ Yes |
| 8 | `vault_tokens` | `app/models/vault_token.py` | ✅ Yes | ✅ Yes |
| 9 | `idp_sessions` | `app/models/idp_session.py` | ✅ Yes | ✅ Yes |
| 10 | `users` | `app/models/user.py` | ✅ Yes | ✅ Yes |
| 11 | `tasks` | `app/models/task_token.py` | ✅ Yes | ✅ Yes |
| 12 | `scoped_permissions` | `app/models/task_token.py` | ✅ Yes | ✅ Yes |
| 13 | `user_sessions` | `app/models/user_session.py` | ❌ No | ❌ No |
| 14 | `delegation_tokens` | `app/models/delegation.py` | ❌ No | ❌ No |
| 15 | `agent_sessions` | `app/models/agent_session.py` | ❌ No | ❌ No |
| 16 | `audit_events` | `app/models/audit_event.py` | ❌ No | ❌ No |

---

## 4 Missing Tables and Their UI Impact

### 1. `delegation_tokens` — CRITICAL

**Used by:** Delegation page, Agent Activity page (tools endpoint queries this table)  
**Frontend calls:** `agents/{id}/tools` queries `DelegationToken`; `auth/delegate` (POST) should write to it  
**Current workaround:** `get_agent_tools` has a `try/except` catching `UndefinedTable`, returning "Not in delegation" for all tools. The `POST /auth/delegate` endpoint uses an in-memory `_delegations` dict.  
**Runtime impact:**
- Delegation creation works but data is **lost on container restart** — all user delegations wiped
- Agent tools page always shows "Not in delegation" regardless of what was delegated
- No persistent delegation history

---

### 2. `agent_sessions` — HIGH

**Used by:** Agent Activity page (SSE events reference session data), agent authentication flow  
**Frontend calls:** `agents/{id}/activity` needs session data  
**Current workaround:** Challenge-response auth flow uses the `nonces` table for the nonce. Agent JWTs are issued but not tracked in any session table.  
**Runtime impact:**
- No persistent agent session tracking
- Cannot show real session history on the activity page
- Agent activity page works only for in-memory SSE events

---

### 3. `audit_events` — HIGH

**Used by:** Dashboard overview (recent activity), Audit page, Agent Activity page  
**Frontend calls:** `audit/events`, `audit/events?agent_id=X&limit=20`, `audit/events?limit=10`  
**Current workaround:** `audit.py` uses `_mvp_audit_events` (a module-level Python list). Events are appended in-process.  
**Runtime impact:**
- Audit trail is **ephemeral** — lost on every container restart
- Dashboard shows empty event list after restart
- Agent activity page shows no history after restart
- No queryable audit history

---

### 4. `user_sessions` — LOW (deferred)

**Used by:** Referenced architecturally; not directly used by current frontend  
**Frontend calls:** None directly — SSO sessions handled via JWT cookies + `idp_sessions` table  
**Current workaround:** The existing `idp_sessions` table and JWT cookies handle the SSO session flow adequately  
**Runtime impact:** Low — SSO flow works. This table is planned for future use but not blocking any current page.

---

## UI Page → API → Database Mapping

| Page | API Calls Made | Backend Tables | Status |
|------|---------------|----------------|--------|
| `/dashboard` | `agents/`, `policies/`, `audit/events?limit=10`, `users/me` | `agents` ✅, `policies` ✅, **audit: in-memory** ⚠️, `users` ✅ | Partial — audit events empty after restart |
| `/dashboard/agents` | `agents/` (GET, DELETE) | `agents` ✅ | ✅ Works |
| `/dashboard/agents/create` | `agents/` (POST) | `agents` ✅ | ✅ Works |
| `/dashboard/agents/[id]/activity` | `agents/{id}/tools`, `audit/events?agent_id=X`, SSE stream | `agents` ✅, **delegation_tokens** ❌ (graceful fallback), **audit: in-memory** ⚠️, **SSE: 404** ❌ | Partial — tools show "not in delegation", audit ephemeral, SSE broken |
| `/dashboard/policies` | `policies/` (GET, POST, PUT, DELETE) | `agents` ✅, `policies` ✅ | ⚠️ Schema mismatch on create/update (see below) |
| `/dashboard/services` | `users/me/available-permissions`, `oauth/{id}/authorize`, `users/me/services/{id}` (DELETE) | `connected_services` ✅ | ✅ Works (OAuth flow implemented) |
| `/dashboard/audit` | `audit/events?<filters>` | **audit: in-memory** ⚠️ | Works but ephemeral; filter params partially ignored |
| `/dashboard/vault` | `vault/secrets`, `vault/store`, `vault/secrets/{name}` | `secrets` ✅ | ❌ 401 — vault uses API key auth, dashboard sends JWT |
| `/dashboard/delegation` | `auth/delegations` (GET) | **delegation_tokens: in-memory** ⚠️ | Works but data lost on restart |
| `/dashboard/delegation/create` | `agents/`, `users/me/available-permissions`, `auth/delegate` (POST) | `agents` ✅, `connected_services` ✅, **delegation_tokens: in-memory** ⚠️ | Works but delegation lost on restart |
| `/dashboard/tasks` | `tasks/` (GET, POST) | `tasks` ✅, `scoped_permissions` ✅ | ⚠️ Schema mismatch on create (see below) |
| `/dashboard/tasks/[id]` | `tasks/{id}` (GET, POST actions) | `tasks` ✅ | ✅ Works |
| `/onboarding` | `users/me` (GET, PATCH) | `users` ✅ | ✅ Works |

---

## Additional Schema Issues (Beyond Missing Tables)

### Request/Response Mismatches

These are cases where the frontend sends a JSON body that does not match the backend Pydantic model. They result in silent 422 validation errors or ignored fields.

| Page | Frontend Sends | Backend Expects | Effect |
|------|---------------|-----------------|--------|
| Vault (all endpoints) | User JWT via proxy | `APIKeyDep` (static `BACKEND_API_TOKEN`) | **401 on every vault operation** |
| Services Connect | `{ service_id }` | `ConnectServiceRequest` with `oauth_token` (full token object) | 422 validation error (now bypassed by OAuth redirect flow) |
| Policy Create | `{ permissions, agent_ids }` | `PolicyCreate` with `name, actions, resources, agent_id` | **422 — permissions/agent_ids unknown fields** |
| Task Create | `{ name, description, agent_id }` | `TaskCreate` with `requested_permissions` (min 1), agent from token | **422 — missing required field** |
| Audit Filters | `from_date, to_date, token_layer` | `start_time, end_time` (no `token_layer`) | Filters silently ignored |

### Missing Backend Route

| Frontend Call | Expected Route | Actual State | Effect |
|--------------|---------------|-------------|--------|
| SSE: `/api/events/stream` | `GET /api/v1/audit/events/stream` | **Route does not exist** in `audit.py` | Agent activity live feed always 404s |

---

## Existing Alembic Migration Files

Located in `deeptrail-control/alembic/versions/`:

| File | What It Creates/Modifies |
|------|--------------------------|
| `8a916b49e686_initial_database_schema_for_agents_and_.py` | `agents`, `credentials`, `policies` |
| `288224a3929d_add_credential_table_and_update_agent.py` | Updates `credentials` |
| `203db040fcb3_add_secrets_table.py` | `secrets` |
| `e91bddf1b5b4_create_nonces_table_for_challenge_.py` | `nonces` |
| `5906eb3332a8_add_policy_table.py` | `policies` (update) |
| `ad30f11f4f01_add_attestation_policies_table_and_.py` | `attestation_policies` |
| `a9f7c2d4e1b3_add_vault_tokens_table.py` | `vault_tokens` |
| `b7d3f8a1c2e5_create_task_tables.py` | `tasks`, `scoped_permissions` |
| `add_connected_services_table.py` | `connected_services` |
| `c3a8f5d7e9b1_create_idp_sessions.py` | `idp_sessions` |
| `d4e5f6a7b8c9_add_users_table_with_onboarding.py` | `users` (untracked, not applied) |
| `62d521598579_merge_idp_sessions_and_users_table.py` | Merge head (untracked, not applied) |
| `e65664cca5ae_add_full_fields_to_agents_table.py` | Adds fields to `agents` |
| `3695f3bddaa9_rename_current_public_key_to_public_key.py` | Renames column in `agents` |
| `a24369bdaffd_add_status_to_credentials_table.py` | Adds `status` to `credentials` |
| `13bdfc2959b8_make_credentials_signature_nullable.py` | Makes `signature` nullable |
| `556ee3ed451b_modify_secrets_table_for_split_key_.py` | Split-key fields in `secrets` |
| `85a042468f08_add_metadata_column_to_secrets_table.py` | `metadata` column in `secrets` |
| `fad6afa30f7f_test_valid_template_empty_metadata.py` | Test/empty migration |

**Not yet applied (untracked):** `d4e5f6a7b8c9`, `62d521598579` — verify these before creating the new missing-tables migration.

---

## How the API Proxy Routes Work

`apiClient("some/path")` in the frontend hits `/api/proxy/some/path` (defined in `frontend/src/lib/api/client.ts`), which proxies to `{DEEPTRAIL_CONTROL_INTERNAL_URL}/api/v1/some/path` unless the first path segment is `gateway` (handled by `frontend/src/app/api/proxy/[...path]/route.ts`).

So `apiClient("agents/")` → `GET http://localhost:8000/api/v1/agents/`.

The proxy forwards the user's session JWT as `Authorization: Bearer <jwt>`. Backend endpoints that use `APIKeyDep` instead of JWT auth will reject these requests with 401.

---

## Priority Order for Fixes

| Priority | Fix | Unlocks |
|----------|-----|---------|
| **P1** | Create Alembic migration for `delegation_tokens`, `agent_sessions`, `audit_events` | Everything below |
| **P1** | Update `delegation.py`: persist `DelegationToken` to DB | Persistent delegations, agent tools |
| **P1** | Update `audit.py`: persist `AuditEvent` to DB | Persistent audit trail |
| **P2** | Update `agents.py`: remove `try/except UndefinedTable` hack | Clean agent tools response |
| **P2** | Update `vault.py`: flexible auth (JWT or API key) | Vault page works for dashboard users |
| **P2** | Update `policies.py`: field aliases | Policy create/update from dashboard |
| **P2** | Update `tasks.py`: optional `requested_permissions`, accept `agent_id` | Task create from dashboard |
| **P2** | Add `GET /audit/events/stream` SSE endpoint | Agent activity live feed |
| **P3** | Update `audit.py`: `from_date`/`to_date` aliases, `token_layer` filter | Audit page filtering |
| **P3** | Update `WelcomeWizard.tsx`: real OAuth connect buttons | Onboarding service connect step |
| **P3** | Create `user_sessions` migration | Architectural completeness (no current UI need) |

See [`plans/integration_verification_pipeline.plan.md`](../../plans/integration_verification_pipeline.plan.md) for full implementation details on each fix.
