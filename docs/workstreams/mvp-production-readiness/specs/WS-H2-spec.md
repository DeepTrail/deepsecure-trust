# Task Specification: WS-H2 Implement Token Refresh in Injector

> **IMMUTABLE AFTER DESIGN APPROVAL**
>
> This specification defines what implementation MUST match exactly.
> Do not modify without updating the design doc first.
>
> **Source:** BATCH_EXECUTION_PLAN.md P1-B3, MERGE_POINTS.md MP3

---

## Overview

| Field | Value |
|-------|-------|
| **Task ID** | WS-H2 |
| **Task Name** | Implement Token Refresh in Injector |
| **Type** | Middleware (Service/Handler) |
| **Service** | deeptrail-gateway |
| **Complexity** | M (1-3 hrs) |
| **Dependencies** | WS-H1 (constructor changes, parameter threading) |
| **Validates** | Token refresh during credential injection, MP3 criteria |

---

## Component Specification

### Method: `_refresh_token`

| Field | Value |
|-------|-------|
| **Module** | `deeptrail-gateway/app/middleware/credential_injection.py` |
| **Class** | `CredentialInjector` |
| **Purpose** | Refresh expired OAuth tokens by calling Control Plane E3 endpoint |

### Method Signature

```python
async def _refresh_token(
    self,
    credential_ref: str,
    token_data: dict[str, Any],
    backend_id: str,              # NEW — service_id for E3 URL
    user_id: str | None = None,   # NEW — for X-User-ID header
) -> dict[str, Any] | None:
```

---

## API Contract: E3 Vault Token Refresh (called by this middleware)

### Endpoint Definition

| Field | Value |
|-------|-------|
| **Method** | `POST` |
| **Path** | `/api/v1/vault/tokens/{service_id}/refresh` |
| **Auth** | Internal API Token via `Authorization: Bearer <gateway-internal-token>` |
| **Headers** | `X-User-ID: <user-email>` (required) |
| **Content-Type** | `application/json` |

### Request

- **Path Parameter:** `service_id` (string) — e.g., `"notion"`, `"slack"`, `"hubspot"`
- **Headers:**
  - `Authorization: Bearer <gateway-internal-secret-token>`
  - `X-User-ID: sarah@acme.com`
  - `Content-Type: application/json`
- **Body:** `{"force": false}`

### Response Schema (Success - 200)

```json
{
  "access_token": "string — new OAuth access token",
  "token_type": "string — default: bearer",
  "expires_in": "int | null — seconds until expiration",
  "refreshed": "bool — true if token was actually refreshed",
  "message": "string — status message"
}
```

### Error Responses

| Status | Condition | Response Body |
|--------|-----------|---------------|
| 400 | No refresh token available | `{"detail": {"error": "no_refresh_token", "message": "..."}}` |
| 401 | Invalid internal token | `{"detail": {"error": "unauthorized", "message": "..."}}` |
| 404 | Service not connected | `{"detail": {"error": "not_found", "message": "Service not connected"}}` |
| 502 | OAuth provider error | `{"detail": {"error": "provider_error", "message": "..."}}` |

---

## Implementation: Fixed `_refresh_token`

### Key Fixes from Buggy Existing Code

1. URL uses `backend_id` (service_id), NOT `credential_ref`
2. Sends `Authorization: Bearer <internal_api_token>` header
3. Sends `X-User-ID: <user_id>` header
4. Sends JSON body `{"force": false}`

```python
async def _refresh_token(
    self,
    credential_ref: str,
    token_data: dict[str, Any],
    backend_id: str,
    user_id: str | None = None,
) -> dict[str, Any] | None:
    refresh_token = token_data.get("refresh_token")
    if not refresh_token:
        logger.warning("No refresh_token available for token refresh")
        return None

    if not self.control_plane_url:
        # MVP mode: unchanged
        logger.info("MVP mode: token refresh not implemented")
        return None

    # Production: Call Control Plane E3 endpoint
    if not self.internal_api_token:
        logger.error("No internal API token configured for token refresh")
        return None

    if not user_id:
        logger.error("No user_id available for token refresh")
        return None

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.control_plane_url}/api/v1/vault/tokens/{backend_id}/refresh",
                headers={
                    "Authorization": f"Bearer {self.internal_api_token}",
                    "X-User-ID": user_id,
                },
                json={"force": False},
                timeout=10.0,
            )

            if response.status_code == 200:
                new_token = response.json()
                self._token_cache.pop(credential_ref, None)  # Invalidate cache
                logger.info("Token refresh successful for service %s", backend_id)
                return new_token
            elif response.status_code == 400:
                logger.warning("Token refresh 400: no refresh token for %s", backend_id)
                return None
            elif response.status_code == 404:
                logger.warning("Token refresh 404: service %s not connected", backend_id)
                return None
            elif response.status_code == 502:
                logger.error("Token refresh 502: provider error for %s", backend_id)
                return None
            else:
                logger.error("Token refresh status %d for %s", response.status_code, backend_id)
                return None

    except httpx.TimeoutException:
        logger.error("Token refresh timeout for service %s", backend_id)
        return None
    except Exception as e:
        logger.error("Token refresh error: %s", type(e).__name__)
        return None
```

---

## Caller Change in tools_call.py

```python
# Pass user_id from agent_context.owner
injection_result = await injector.inject_credentials(
    credential_ref=cred_ref,
    backend_id=backend_id,
    agent_jwt_token=agent_jwt_token,
    user_id=agent_context.owner if agent_context else None,  # NEW for H2
)
```

---

## Error Handling Matrix

| E3 Response | Gateway Behavior | Result |
|-------------|------------------|--------|
| 200 (refreshed=true) | Return new token, invalidate cache | Success |
| 200 (refreshed=false) | Return existing token | Success |
| 400 | Log warning, return None | REFRESH_FAILED |
| 404 | Log warning, return None | REFRESH_FAILED |
| 502 | Log error, return None | REFRESH_FAILED |
| Timeout | Log error, return None | REFRESH_FAILED |
| No internal token | Log error, return None (before HTTP call) | REFRESH_FAILED |
| No user_id | Log error, return None (before HTTP call) | REFRESH_FAILED |

---

## Files to Modify

| File | Change | Lines |
|------|--------|-------|
| `deeptrail-gateway/app/middleware/credential_injection.py` | Fix `_refresh_token()` signature and implementation | 349-403 |
| `deeptrail-gateway/app/mcp/handlers/tools_call.py` | Pass `user_id=agent_context.owner` to `inject_credentials()` | ~618-621 |
| `deeptrail-gateway/tests/middleware/test_credential_injection.py` | Add `TestRealTokenRefresh` test class | new |

---

## Test Endpoint Mapping

> **CRITICAL**: Tests MUST mock these exact endpoints.

| Test Case | Method | Endpoint | Expected Status |
|-----------|--------|----------|-----------------|
| Happy path (refreshed) | POST | `/api/v1/vault/tokens/notion/refresh` | 200 |
| Token still valid | POST | `/api/v1/vault/tokens/notion/refresh` | 200 (refreshed=false) |
| No refresh token | POST | `/api/v1/vault/tokens/notion/refresh` | 400 |
| Service not connected | POST | `/api/v1/vault/tokens/notion/refresh` | 404 |
| Provider error | POST | `/api/v1/vault/tokens/notion/refresh` | 502 |
| Timeout | POST | `/api/v1/vault/tokens/notion/refresh` | (httpx.TimeoutException) |
| No internal token | N/A | N/A | Return None before HTTP call |
| No user_id | N/A | N/A | Return None before HTTP call |
| MVP mode | N/A | N/A | Return None (no control_plane_url) |

---

## Key Config Values

| Config | Source | Value (Docker) |
|--------|--------|---------------|
| `internal_api_token` | `GATEWAY_INTERNAL_API_TOKEN` env | `gateway-internal-secret-token` |
| `control_plane_url` | `CONTROL_PLANE_URL` env | `http://deeptrail-control:8001` |

---

## Contract Verification Checklist

Before marking implementation complete, verify:

- [ ] `_refresh_token` URL uses `backend_id` (service_id), not `credential_ref`
- [ ] `Authorization: Bearer <internal_api_token>` header sent to E3
- [ ] `X-User-ID` header sent with user email
- [ ] Request body is `{"force": false}`
- [ ] MVP mock path preserved when `control_plane_url` is None
- [ ] Cache invalidated after successful refresh (`_token_cache.pop`)
- [ ] `user_id` threaded from `agent_context.owner` through call chain
- [ ] Returns None gracefully when no `internal_api_token` or `user_id`
- [ ] All existing tests pass unchanged
- [ ] New `TestRealTokenRefresh` tests pass
- [ ] No token values appear in log messages

---

## References

- **Design Doc:** BATCH_EXECUTION_PLAN.md P1-B3
- **Related Specs:** [WS-E3-spec.md](./WS-E3-spec.md), [WS-H1-spec.md](./WS-H1-spec.md)
- **Upstream Dependencies:** WS-H1 (constructor and parameter threading), WS-E3 (refresh endpoint)
- **Downstream Dependents:** None (MP3 gate)
