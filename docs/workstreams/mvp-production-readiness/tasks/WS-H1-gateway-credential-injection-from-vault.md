# Task: WS-H1 Gateway Credential Injection from Vault

> **Status:** `completed`
> **Completion Date:** February 18, 2026
> **Batch:** P1-B3
> **Worktree:** mvp-prod-gateway

---

## Metadata

| Field | Value |
|-------|-------|
| **Task ID** | WS-H1 |
| **Workstream** | H (Credential Injection) |
| **Phase** | P1 (Real Backend Integration) |
| **Dependencies** | MP2 (E2, E3 endpoints) ✅ Complete |
| **Complexity** | M (1-3 hrs) |
| **Service** | deeptrail-gateway |
| **Validates** | E2E Step 8 (Execute Tool) with real token, MP3 criteria |

---

## Specification

> See full specification: [../specs/WS-H1-spec.md](../specs/WS-H1-spec.md)

### Key Contracts

**E2 Endpoint Called by This Middleware:**

| Field | Value |
|-------|-------|
| **Method** | `GET` |
| **Path** | `/api/v1/vault/tokens/{service_id}` |
| **Auth** | Agent Session JWT via `Authorization: Bearer` |

**Response (Success 200):**
```json
{
  "access_token": "string",
  "token_type": "bearer",
  "expires_in": 3600,
  "scope": "read_pages write_pages"
}
```

**Error Responses:**

| Status | Condition |
|--------|-----------|
| 401 | Invalid/missing Agent JWT |
| 403 | Service not in delegated_permissions |
| 404 | Service not connected for user |

---

## API Contracts

> **Note:** This task implements an internal middleware module, not API endpoints.
> The CredentialInjector calls the Control Plane vault API but does not expose any Gateway API endpoints.
> See WS-E2 for the vault token retrieval endpoint it calls.

---

## Pre-Conditions

- [x] MP2 reached (E2, E3 endpoints working)
- [x] `CredentialInjector` class exists with mock implementation
- [x] `AgentContext` dataclass available with `owner` field
- [x] Gateway `proxy_config` has `internal_api_token` field
- [x] `httpx` library available

---

## Task Description

### Objective

Replace the mock token in `_fetch_from_vault()` with a real HTTP call to the Control Plane E2 endpoint, and thread the Agent JWT through the call chain.

### Background

Currently, the Gateway's `CredentialInjector` returns a hardcoded mock token (`"mock_access_token_never_exposed_to_agent"`) at line 298. Additionally, the existing "production" code path (lines 303-327) has bugs: it uses `credential_ref` in the URL instead of `service_id`, and sends no auth headers. This task fixes both issues and wires up the real token flow.

### What to Implement

1. **Store raw JWT in request state** (`jwt_validation.py`):
   - Add `request.state.agent_jwt_token = token` after line 276

2. **Thread JWT through MCP context** (`main.py`):
   - Add `"agent_jwt_token"` to the `_context` dict passed to handlers

3. **Extract and pass JWT in handler** (`tools_call.py`):
   - Extract `agent_jwt_token` from `_context`
   - Add `agent_jwt_token` parameter to `_forward_to_backend()`
   - Pass to `inject_credentials()`

4. **Update CredentialInjector signatures** (`credential_injection.py`):
   - Constructor: add `internal_api_token` parameter (for H2)
   - `inject_credentials()`: add `agent_jwt_token` and `user_id` parameters
   - `_get_token()`: add `backend_id` and `agent_jwt_token` parameters
   - `_fetch_from_vault()`: add `backend_id` and `agent_jwt_token` parameters
   - `_refresh_token()`: add `backend_id` and `user_id` parameters (for H2)

5. **Fix `_fetch_from_vault` production path** (`credential_injection.py`):
   - URL: `{control_plane_url}/api/v1/vault/tokens/{backend_id}` (NOT `{credential_ref}`)
   - Header: `Authorization: Bearer {agent_jwt_token}`
   - Handle 200, 403, 404, 5xx, timeout

6. **Update module-level functions** (`credential_injection.py`):
   - `configure_credential_injector()`: add `internal_api_token` param
   - Module-level `inject_credentials()`: add new params

7. **Wire up injector at startup** (`main.py`):
   - Call `configure_credential_injector(control_plane_url=..., internal_api_token=...)`

8. **Add tests** (`test_credential_injection.py`):
   - New `TestRealVaultFetch` class with 7+ test cases

---

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `deeptrail-gateway/app/middleware/credential_injection.py` | Modify | Fix `_fetch_from_vault`, update all signatures, add `internal_api_token` to constructor |
| `deeptrail-gateway/app/middleware/jwt_validation.py` | Modify | Add 1 line: `request.state.agent_jwt_token = token` |
| `deeptrail-gateway/app/mcp/handlers/tools_call.py` | Modify | Thread `agent_jwt_token` through `_forward_to_backend` to `inject_credentials` |
| `deeptrail-gateway/app/main.py` | Modify | Add `agent_jwt_token` to context dict; configure injector at startup |
| `deeptrail-gateway/tests/middleware/test_credential_injection.py` | Modify | Add `TestRealVaultFetch` test class |

---

## Acceptance Criteria

### Functional Criteria

- [ ] `_fetch_from_vault` calls `GET /api/v1/vault/tokens/{backend_id}` (service_id in URL, not credential_ref)
- [ ] Agent JWT forwarded via `Authorization: Bearer` header to E2
- [ ] Returns token data on 200 response
- [ ] Returns None on 403/404/5xx/timeout (fail-closed)
- [ ] Returns None if no agent JWT available (with error log)

### Security Criteria

- [ ] MVP mock path preserved when `control_plane_url` is None
- [ ] Raw JWT stored only in `request.state` (per-request, short-lived)
- [ ] No token values appear in log messages
- [ ] Token values never exposed to agent (existing security model preserved)

### Integration Criteria

- [ ] JWT threaded from `jwt_validation.py` → `request.state` → `_context` → `tools_call.py` → `inject_credentials` → `_fetch_from_vault`
- [ ] All existing tests pass unchanged (MVP mock path unaffected)
- [ ] New `TestRealVaultFetch` tests pass (7+ test cases)
- [ ] `configure_credential_injector()` called at startup with `control_plane_url` and `internal_api_token`

---

## Test Cases

| Test Case | Module | Expected Result | Notes |
|-----------|--------|-----------------|-------|
| Fetch calls correct URL | `_fetch_from_vault` | URL contains `/vault/tokens/notion` | Not `/vault/tokens/vault://...` |
| Fetch sends Agent JWT | `_fetch_from_vault` | `Authorization: Bearer <jwt>` header | Verified via mock |
| Fetch returns None without JWT | `_fetch_from_vault` | Returns None | Error logged |
| Fetch handles 403 | `_fetch_from_vault` | Returns None | Service not delegated |
| Fetch handles 404 | `_fetch_from_vault` | Returns None | Service not connected |
| Fetch handles timeout | `_fetch_from_vault` | Returns None | httpx.TimeoutException |
| MVP mode unchanged | `_fetch_from_vault` | Mock token returned | `control_plane_url=None` |
| inject_credentials threads JWT | `inject_credentials` | JWT reaches `_fetch_from_vault` | End-to-end parameter test |

---

## Post-Conditions

After this task is complete:
- [ ] WS-H2 unblocked (constructor changes and parameter threading in place)
- [ ] Gateway can fetch real OAuth tokens from Control Plane vault
- [ ] Backend API calls use real credentials (when `control_plane_url` configured)
- [ ] Mock path still works for development without Control Plane

---

## Validation

### Unit Tests
```bash
cd deeptrail-gateway
pytest tests/middleware/test_credential_injection.py -v
```

### Manual Verification
```bash
# 1. Start services
cd /Users/imaxxs/repositories/deepsecure-mvp
docker compose up -d

# 2. Login, connect service, get Agent JWT
# (See BATCH_EXECUTION_PLAN.md P1-B2 Post-Merge Validation for full flow)

# 3. Make MCP tool call through Gateway
curl -s -X POST http://localhost:8002/mcp \
  -H "Authorization: Bearer $AGENT_JWT" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "id": 1,
    "params": {"name": "notion.search_pages", "arguments": {"query": "test"}}
  }'
# Expected: Real token injected (check Gateway logs for "Token cache hit" or "Vault fetch")

# 4. Check Gateway logs for real vault fetch
docker compose logs deeptrail-gateway --tail=20 | grep -E "vault|token|credential"
# Expected: NOT "MVP mode: returning mock token"
```

---

## References

- **Specification:** [../specs/WS-H1-spec.md](../specs/WS-H1-spec.md)
- **Design Doc:** `plans/mvp_production_readiness.plan.md`
- **Upstream:** WS-E2 (Vault token retrieval) ✅ Complete, WS-E3 (Token refresh) ✅ Complete
- **Downstream:** WS-H2 (Token refresh integration)
- **Related Code:**
  - `deeptrail-gateway/app/middleware/credential_injection.py` (primary file)
  - `deeptrail-gateway/app/middleware/jwt_validation.py` (JWT storage)
  - `deeptrail-gateway/app/mcp/handlers/tools_call.py` (caller)
  - `deeptrail-gateway/app/main.py` (context wiring)
  - `deeptrail-gateway/app/core/proxy_config.py` (internal_api_token config)
  - `deeptrail-control/app/api/v1/endpoints/vault.py` (E2 endpoint being called)

---

## Execution

```bash
# Run in mvp-prod-gateway worktree:
cd /Users/imaxxs/repositories/mvp-prod-gateway
/execute-task WS-H1 mvp-production-readiness

# Complete this task:
/complete-task WS-H1 mvp-production-readiness
```
