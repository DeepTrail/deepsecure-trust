# Task: WS-E3 Vault Token Refresh Endpoint

> **Status:** `completed`
> **Batch:** P1-B2
> **Worktree:** mvp-prod-control
> **Completed:** 2026-02-17

---

## Metadata

| Field | Value |
|-------|-------|
| **Task ID** | WS-E3 |
| **Workstream** | E (Vault & Credential Storage) |
| **Phase** | P1 (Real Backend Integration) |
| **Dependencies** | WS-E1 ✅, WS-E2, WS-F1 ✅ |
| **Complexity** | M (1-3 hours) |
| **Service** | deeptrail-control |
| **Validates** | Gateway token refresh, P1-B3 (H2) |

---

## Specification

> See full specification: [../specs/WS-E3-spec.md](../specs/WS-E3-spec.md)

### Key Contracts

**Endpoint:**
| Field | Value |
|-------|-------|
| **Method** | `POST` |
| **Path** | `/api/v1/vault/tokens/{service_id}/refresh` |
| **Auth** | Internal API token (gateway-to-control) |

**Request Headers:**
| Header | Required | Description |
|--------|----------|-------------|
| `Authorization` | Yes | `Bearer <internal_api_token>` |
| `X-User-ID` | Yes | User UUID whose token to refresh |

**Request Body:**
```json
{
  "force": false
}
```

**Response (200):**
```json
{
  "access_token": "new_token",
  "token_type": "bearer",
  "expires_in": 3600,
  "refreshed": true,
  "message": "Token refreshed"
}
```

**Error Responses:**
| Status | Condition |
|--------|-----------|
| 401 | Invalid internal token |
| 404 | Service not connected |
| 400 | No refresh token available |
| 502 | OAuth provider error |

---

## Pre-Conditions

- [x] WS-E1 complete (VaultClient with token storage)
- [x] WS-F1 complete (OAuthService with refresh_tokens method)
- [ ] WS-E2 complete (Token retrieval endpoint - can run in parallel)
- [x] ConnectedServiceService exists
- [x] Internal API token authentication exists

---

## Task Description

### Objective

Create an API endpoint that allows the Gateway to refresh OAuth tokens when they expire or are about to expire. This is an internal endpoint (gateway-to-control) that does not use agent JWT authentication.

### Background

When the Gateway detects an expired or expiring token during credential injection, it needs to refresh the token via the Control Plane. This endpoint:
1. Validates the internal API token (not agent JWT)
2. Gets the user's refresh_token from the vault
3. Calls the OAuth provider to refresh
4. Updates the vault with new tokens
5. Returns the new access token

### What to Implement

1. **Add refresh schemas to `app/schemas/vault.py`**:
   ```python
   class TokenRefreshRequest(BaseModel):
       """Request schema for token refresh."""
       force: bool = False

   class TokenRefreshResponse(BaseModel):
       """Response schema for token refresh."""
       access_token: str
       token_type: str = "bearer"
       expires_in: int | None = None
       refreshed: bool
       message: str
   ```

2. **Add refresh endpoint to `app/api/v1/endpoints/vault.py`**:
   ```python
   @router.post("/tokens/{service_id}/refresh", response_model=TokenRefreshResponse)
   async def refresh_token(
       service_id: str,
       request: TokenRefreshRequest,
       x_user_id: str = Header(..., alias="X-User-ID"),
       internal_token: str = Depends(verify_internal_token),
       connected_service: ConnectedServiceService = Depends(),
       oauth_service: OAuthService = Depends(),
   ):
       # 1. Get current connection
       connection = await connected_service.get_connection(x_user_id, service_id)
       if not connection:
           raise HTTPException(404, detail={"error": "not_found", "message": "Service not connected"})

       # 2. Check if refresh_token exists
       if not connection.refresh_token:
           raise HTTPException(400, detail={"error": "no_refresh_token", "message": "Service does not support refresh"})

       # 3. Check if refresh needed (unless force=True)
       if not request.force and not connection.is_expired():
           return TokenRefreshResponse(
               access_token=connection.access_token,
               token_type="bearer",
               expires_in=connection.time_until_expiry(),
               refreshed=False,
               message="Token still valid"
           )

       # 4. Call OAuth provider to refresh
       try:
           new_tokens = await oauth_service.refresh_tokens(
               service_id=service_id,
               refresh_token=connection.refresh_token
           )
       except Exception as e:
           raise HTTPException(502, detail={"error": "provider_error", "message": f"Failed to refresh: {str(e)}"})

       # 5. Update vault
       await connected_service.refresh_token(
           user_id=x_user_id,
           service_id=service_id,
           new_access_token=new_tokens.access_token,
           new_refresh_token=new_tokens.refresh_token,
           expires_in=new_tokens.expires_in
       )

       return TokenRefreshResponse(
           access_token=new_tokens.access_token,
           token_type="bearer",
           expires_in=new_tokens.expires_in,
           refreshed=True,
           message="Token refreshed"
       )
   ```

3. **Create/update internal token validation** (if not exists):
   ```python
   # In app/api/deps.py or similar
   async def verify_internal_token(authorization: str = Header(...)):
       """Verify internal API token for gateway-to-control calls."""
       if not authorization.startswith("Bearer "):
           raise HTTPException(401, detail={"error": "unauthorized", "message": "Invalid internal token"})
       token = authorization[7:]
       # Validate against configured internal token
       if token != settings.internal_api_token:
           raise HTTPException(401, detail={"error": "unauthorized", "message": "Invalid internal token"})
       return token
   ```

4. **Add tests in `tests/api/test_vault.py`**

---

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `deeptrail-control/app/schemas/vault.py` | Modify | Add refresh schemas |
| `deeptrail-control/app/api/v1/endpoints/vault.py` | Modify | Add refresh endpoint |
| `deeptrail-control/app/api/deps.py` | Modify | Add internal token validation |
| `deeptrail-control/tests/api/test_vault.py` | Modify | Add refresh tests |

---

## Acceptance Criteria

### Functional Criteria

- [ ] `POST /api/v1/vault/tokens/{service_id}/refresh` endpoint created
- [ ] Returns `TokenRefreshResponse` with refreshed flag
- [ ] Supports `force` parameter to force refresh even if not expired
- [ ] Returns existing token if not expired and `force=false`

### Security Criteria

- [ ] Uses internal API token authentication (NOT agent JWT)
- [ ] Validates `X-User-ID` header is present
- [ ] Returns 401 for invalid internal token
- [ ] Does not expose refresh_token in response

### Integration Criteria

- [ ] Uses `OAuthService.refresh_tokens()` from WS-F1
- [ ] Uses `ConnectedServiceService.refresh_token()` from WS-E1
- [ ] Handles OAuth provider errors gracefully (502)

### Contract Verification (from spec)

- [ ] Endpoint path matches: `/api/v1/vault/tokens/{service_id}/refresh`
- [ ] Internal token auth (not agent JWT)
- [ ] `X-User-ID` header required
- [ ] `refreshed` boolean in response
- [ ] Tests cover all 7 cases

---

## Test Cases

| Test Case | Method | Endpoint | Expected Status | Notes |
|-----------|--------|----------|-----------------|-------|
| Happy path (expired) | POST | `/api/v1/vault/tokens/notion/refresh` | 200 | `refreshed: true` |
| Token still valid | POST | `/api/v1/vault/tokens/notion/refresh` | 200 | `refreshed: false` |
| Force refresh | POST | `/api/v1/vault/tokens/notion/refresh` | 200 | `force: true`, `refreshed: true` |
| Missing X-User-ID | POST | `/api/v1/vault/tokens/notion/refresh` | 422 | Missing header |
| Invalid internal token | POST | `/api/v1/vault/tokens/notion/refresh` | 401 | Wrong token |
| Service not connected | POST | `/api/v1/vault/tokens/notion/refresh` | 404 | No connection |
| No refresh token | POST | `/api/v1/vault/tokens/slack/refresh` | 400 | refresh_token is null |
| Provider error | POST | `/api/v1/vault/tokens/notion/refresh` | 502 | OAuth call fails |

---

## Post-Conditions

After this task is complete:
- [ ] Gateway can refresh expired tokens via Control Plane
- [ ] Token refresh is automatic (when force=false, only refresh if expired)
- [ ] WS-H2 (Gateway token refresh integration) unblocked
- [ ] MP2 (Vault API ready) closer to completion

---

## Validation

### Unit Tests
```bash
cd deeptrail-control
pytest tests/api/test_vault.py::test_refresh -v
```

### Manual Verification
```bash
# 1. Store a token first (via connect endpoint)
# 2. Call the refresh endpoint
curl -X POST http://localhost:8000/api/v1/vault/tokens/notion/refresh \
  -H "Authorization: Bearer <internal_token>" \
  -H "X-User-ID: <user_uuid>" \
  -H "Content-Type: application/json" \
  -d '{"force": true}'

# Expected: {"access_token": "...", "refreshed": true, "message": "Token refreshed"}
```

---

## References

- **Specification:** [../specs/WS-E3-spec.md](../specs/WS-E3-spec.md)
- **Design Doc:** `plans/mvp_production_readiness.plan.md`
- **Upstream:** WS-E1 (VaultClient), WS-E2 (Token retrieval), WS-F1 (OAuthService)
- **Downstream:** WS-H2 (Gateway token refresh integration)
- **Related Code:**
  - `deeptrail-control/app/services/oauth_service.py` (refresh_tokens)
  - `deeptrail-control/app/services/connected_service_service.py`

---

## Execution

```bash
# Run in mvp-prod-control worktree:
cd /Users/imaxxs/repositories/mvp-prod-control
/execute-task WS-E3 mvp-production-readiness
```

---

## Progress Updates

| Date | Update |
|------|--------|
| 2026-02-17 | Started task implementation |
| 2026-02-17 | Added TokenRefreshRequest and TokenRefreshResponse schemas to vault_token.py |
| 2026-02-17 | Added verify_internal_token dependency to deps.py |
| 2026-02-17 | Added POST /tokens/{service_id}/refresh endpoint to vault.py |
| 2026-02-17 | Added 10 tests covering all acceptance criteria |
| 2026-02-17 | All 26 vault token tests pass (16 existing + 10 new) |
| 2026-02-17 | Ready for completion |
