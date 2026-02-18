# Task Specification: WS-E3 Vault Token Refresh Endpoint

> **IMMUTABLE AFTER DESIGN APPROVAL**
>
> This specification defines what implementation MUST match exactly.
> Do not modify without updating the design doc first.
>
> **Source:** BATCH_EXECUTION_PLAN.md - P1-B2

---

## Overview

| Field | Value |
|-------|-------|
| **Task ID** | WS-E3 |
| **Task Name** | Create Vault Token Refresh Endpoint |
| **Type** | API Endpoint |
| **Service** | deeptrail-control |
| **Dependencies** | WS-E1, WS-E2, WS-F1 |

---

## API Contract

### Endpoint Definition

| Field | Value |
|-------|-------|
| **Method** | `POST` |
| **Path** | `/api/v1/vault/tokens/{service_id}/refresh` |
| **Auth** | Internal API token (gateway-to-control) |
| **Content-Type** | `application/json` |

### Path Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `service_id` | `str` | Yes | Service identifier (e.g., "notion", "slack", "hubspot") |

### Request Headers

| Header | Required | Description |
|--------|----------|-------------|
| `Authorization` | Yes | `Bearer <internal_api_token>` - Gateway internal token |
| `X-User-ID` | Yes | User UUID whose token to refresh |

### Request Body

```json
{
  "force": "bool - force refresh even if not expired (optional, default: false)"
}
```

### Response Schema (Success - 200)

```json
{
  "access_token": "string - new OAuth access token",
  "token_type": "string - e.g., 'bearer'",
  "expires_in": "int | null - seconds until expiration",
  "refreshed": "bool - true if actually refreshed",
  "message": "string - e.g., 'Token refreshed' or 'Token still valid'"
}
```

### Error Responses

| Status | Condition | Response Body |
|--------|-----------|---------------|
| 401 | Invalid internal token | `{"error": "unauthorized", "message": "Invalid internal token"}` |
| 404 | Service not connected | `{"error": "not_found", "message": "Service not connected"}` |
| 400 | No refresh token available | `{"error": "no_refresh_token", "message": "Service does not support refresh"}` |
| 502 | OAuth provider error | `{"error": "provider_error", "message": "Failed to refresh: [details]"}` |

---

## Implementation Notes

### Service Flow

```python
# Implementation flow:
# 1. Get current connection and refresh_token from vault
connection = await connected_service_service.get_connection(user_id, service_id)
if not connection.refresh_token:
    raise HTTPException(400, "no_refresh_token")

# 2. Call OAuthService to refresh tokens
new_tokens = await oauth_service.refresh_tokens(
    service_id=service_id,
    refresh_token=connection.refresh_token
)

# 3. Update vault via ConnectedServiceService
await connected_service_service.refresh_token(
    user_id=user_id,
    service_id=service_id,
    new_access_token=new_tokens.access_token,
    new_refresh_token=new_tokens.refresh_token,
    expires_in=new_tokens.expires_in
)
```

### Internal Authentication

This endpoint is for gateway-to-control communication only. Use internal API token validation (not agent JWT).

---

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `deeptrail-control/app/api/v1/endpoints/vault.py` | Modify | Add refresh endpoint |
| `deeptrail-control/app/schemas/vault.py` | Modify | Add refresh schemas |
| `deeptrail-control/tests/api/test_vault.py` | Modify | Add refresh tests |

---

## Test Endpoint Mapping

| Test Case | Method | Endpoint | Expected Status | Notes |
|-----------|--------|----------|-----------------|-------|
| Happy path | POST | `/api/v1/vault/tokens/notion/refresh` | 200 | Valid token, refreshed |
| Token still valid | POST | `/api/v1/vault/tokens/notion/refresh` | 200 | `refreshed: false` |
| Force refresh | POST | `/api/v1/vault/tokens/notion/refresh` | 200 | `force: true` |
| Unauthorized | POST | `/api/v1/vault/tokens/notion/refresh` | 401 | Invalid internal token |
| Not found | POST | `/api/v1/vault/tokens/notion/refresh` | 404 | Service not connected |
| No refresh token | POST | `/api/v1/vault/tokens/notion/refresh` | 400 | Service has no refresh_token |
| Provider error | POST | `/api/v1/vault/tokens/notion/refresh` | 502 | OAuth provider fails |

---

## Contract Verification Checklist

- [ ] Endpoint path matches spec: `/api/v1/vault/tokens/{service_id}/refresh`
- [ ] Internal token authentication (not agent JWT)
- [ ] `X-User-ID` header required and validated
- [ ] `force` parameter supported
- [ ] `refreshed` boolean in response indicates actual refresh
- [ ] Handles missing refresh_token (400)
- [ ] Handles provider errors (502)

---

## References

- **Design Doc:** `plans/mvp_production_readiness.plan.md`
- **Upstream:** WS-E1 (VaultClient), WS-E2 (Token retrieval), WS-F1 (OAuthService)
- **Downstream:** WS-H2 (Gateway token refresh integration)
