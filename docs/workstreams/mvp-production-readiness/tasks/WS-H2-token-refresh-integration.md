# Task: WS-H2 Token Refresh Integration

> **Status:** `completed`
> **Completion Date:** February 18, 2026
> **Batch:** P1-B3
> **Worktree:** mvp-prod-gateway

---

## Metadata

| Field | Value |
|-------|-------|
| **Task ID** | WS-H2 |
| **Workstream** | H (Credential Injection) |
| **Phase** | P1 (Real Backend Integration) |
| **Dependencies** | WS-H1 (constructor changes, parameter threading) |
| **Complexity** | M (1-3 hrs) |
| **Service** | deeptrail-gateway |
| **Validates** | Token refresh during credential injection, MP3 criteria |

---

## Specification

> See full specification: [../specs/WS-H2-spec.md](../specs/WS-H2-spec.md)

### Key Contracts

**E3 Endpoint Called by This Middleware:**

| Field | Value |
|-------|-------|
| **Method** | `POST` |
| **Path** | `/api/v1/vault/tokens/{service_id}/refresh` |
| **Auth** | Internal API Token via `Authorization: Bearer` + `X-User-ID` header |

**Request Body:**
```json
{"force": false}
```

**Response (Success 200):**
```json
{
  "access_token": "string",
  "token_type": "bearer",
  "expires_in": 3600,
  "refreshed": true,
  "message": "Token refreshed"
}
```

**Error Responses:**

| Status | Condition |
|--------|-----------|
| 400 | No refresh token available |
| 401 | Invalid internal token |
| 404 | Service not connected |
| 502 | OAuth provider error |

---

## API Contracts

> **Note:** This task implements an internal middleware module, not API endpoints.
> The CredentialInjector calls the Control Plane refresh API but does not expose any Gateway API endpoints.
> See WS-E3 for the vault token refresh endpoint it calls.

---

## Pre-Conditions

- [x] WS-H1 complete (constructor changes, parameter threading, `internal_api_token` in constructor)
- [x] E3 endpoint working (`POST /api/v1/vault/tokens/{service_id}/refresh`)
- [x] `CredentialInjector` has `internal_api_token` field (added in H1)
- [x] `_refresh_token()` signature updated with `backend_id` and `user_id` params (added in H1)
- [x] `user_id` available via `agent_context.owner`

---

## Task Description

### Objective

Replace the mock return in `_refresh_token()` with a real HTTP call to the Control Plane E3 endpoint, using the internal API token and X-User-ID header for authentication.

### Background

Currently, the Gateway's `_refresh_token()` method returns `None` at line 374 when `control_plane_url` is not set (MVP mode). The existing "production" code path (lines 378-403) has bugs: it uses `credential_ref` in the URL instead of `service_id`, sends no auth headers, no X-User-ID header, and no JSON request body. This task fixes these bugs and wires up the real token refresh flow.

### What to Implement

1. **Fix `_refresh_token` production path** (`credential_injection.py`):
   - URL: `{control_plane_url}/api/v1/vault/tokens/{backend_id}/refresh` (NOT `{credential_ref}/refresh`)
   - Header: `Authorization: Bearer {self.internal_api_token}`
   - Header: `X-User-ID: {user_id}`
   - Body: `{"force": false}`
   - Handle 200 (refreshed=true/false), 400, 404, 502, timeout
   - Invalidate `_token_cache` on successful refresh

2. **Add pre-flight validation**:
   - Return None if `self.internal_api_token` is None
   - Return None if `user_id` is None

3. **Pass `user_id` from caller** (`tools_call.py`):
   - Add `user_id=agent_context.owner if agent_context else None` to `inject_credentials()` call

4. **Add tests** (`test_credential_injection.py`):
   - New `TestRealTokenRefresh` class with 10+ test cases

---

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `deeptrail-gateway/app/middleware/credential_injection.py` | Modify | Fix `_refresh_token()` implementation (lines 349-403) |
| `deeptrail-gateway/app/mcp/handlers/tools_call.py` | Modify | Pass `user_id=agent_context.owner` to `inject_credentials()` |
| `deeptrail-gateway/tests/middleware/test_credential_injection.py` | Modify | Add `TestRealTokenRefresh` test class |

---

## Acceptance Criteria

### Functional Criteria

- [ ] `_refresh_token` calls `POST /api/v1/vault/tokens/{backend_id}/refresh` (service_id in URL, not credential_ref)
- [ ] Internal API token sent via `Authorization: Bearer` header
- [ ] `X-User-ID` header sent with user email (from `agent_context.owner`)
- [ ] Request body is `{"force": false}`
- [ ] Returns new token data on 200 response
- [ ] Returns None on 400/404/502/timeout (graceful failure)
- [ ] Returns None if no `internal_api_token` configured
- [ ] Returns None if no `user_id` provided

### Security Criteria

- [ ] MVP mock path preserved when `control_plane_url` is None
- [ ] Internal API token loaded from env var, never logged
- [ ] No token values appear in log messages

### Integration Criteria

- [ ] Cache invalidated (`_token_cache.pop`) after successful refresh
- [ ] `user_id` threaded from `agent_context.owner` through `inject_credentials`
- [ ] Handles E3 `refreshed=false` response (token still valid, return it)
- [ ] All existing tests pass unchanged
- [ ] New `TestRealTokenRefresh` tests pass (10+ test cases)

---

## Test Cases

| Test Case | Module | Expected Result | Notes |
|-----------|--------|-----------------|-------|
| Refresh calls correct URL | `_refresh_token` | URL contains `/vault/tokens/notion/refresh` | Not `vault://...` |
| Sends internal token | `_refresh_token` | `Authorization: Bearer <internal-token>` | From constructor |
| Sends X-User-ID | `_refresh_token` | `X-User-ID: sarah@acme.com` header | From `agent_context.owner` |
| Sends force=false body | `_refresh_token` | JSON body `{"force": false}` | POST body |
| Returns None without internal token | `_refresh_token` | None | Error logged |
| Returns None without user_id | `_refresh_token` | None | Error logged |
| Handles 400 no refresh token | `_refresh_token` | None | Warning logged |
| Handles 404 not connected | `_refresh_token` | None | Warning logged |
| Handles 502 provider error | `_refresh_token` | None | Error logged |
| Handles timeout | `_refresh_token` | None | Error logged |
| Invalidates cache on success | `_refresh_token` | `_token_cache.pop` called | Cache cleared |
| Returns token when refreshed=false | `_refresh_token` | Valid token_data | E3 says still valid |
| MVP mode unchanged | `_refresh_token` | None | `control_plane_url=None` |

---

## Post-Conditions

After this task is complete:
- [ ] MP3 criteria met (credential injection from vault working end-to-end)
- [ ] Expired tokens refreshed automatically during credential injection
- [ ] Full E2E flow works with real tokens: login → connect → delegate → tool call → real API
- [ ] Phase 1 complete (all mocks replaced in credential injection path)

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

# 2. Login, connect service with short-lived token, get Agent JWT
# (See BATCH_EXECUTION_PLAN.md P1-B2 Post-Merge Validation for full flow)

# 3. Wait for token to expire (or use force refresh)

# 4. Make MCP tool call through Gateway (should trigger refresh)
curl -s -X POST http://localhost:8002/mcp \
  -H "Authorization: Bearer $AGENT_JWT" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "id": 1,
    "params": {"name": "notion.search_pages", "arguments": {"query": "test"}}
  }'

# 5. Check Gateway logs for refresh
docker compose logs deeptrail-gateway --tail=20 | grep -E "refresh|expired"
# Expected: "Token expired, attempting refresh" then "Token refresh successful"

# 6. Check Control Plane logs for E3 call
docker compose logs deeptrail-control --tail=20 | grep -E "refresh"
# Expected: "Token refresh request" with service and user info
```

---

## References

- **Specification:** [../specs/WS-H2-spec.md](../specs/WS-H2-spec.md)
- **Design Doc:** `plans/mvp_production_readiness.plan.md`
- **Upstream:** WS-H1 (Credential injection from vault) ⏳, WS-E3 (Token refresh endpoint) ✅ Complete
- **Downstream:** None (MP3 gate — completes Phase 1)
- **Related Code:**
  - `deeptrail-gateway/app/middleware/credential_injection.py` (primary file — `_refresh_token` method)
  - `deeptrail-gateway/app/mcp/handlers/tools_call.py` (caller — passes `user_id`)
  - `deeptrail-gateway/app/core/proxy_config.py` (`internal_api_token` config at line 385)
  - `deeptrail-control/app/api/v1/endpoints/vault.py` (E3 endpoint being called)

---

## Execution

```bash
# Run in mvp-prod-gateway worktree:
cd /Users/imaxxs/repositories/mvp-prod-gateway
/execute-task WS-H2 mvp-production-readiness

# Complete this task:
/complete-task WS-H2 mvp-production-readiness
```
