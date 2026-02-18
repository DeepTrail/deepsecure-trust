# Task Specification: WS-E2 Vault Token Retrieval Endpoint

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
| **Task ID** | WS-E2 |
| **Task Name** | Create Vault Token Retrieval Endpoint |
| **Type** | API Endpoint |
| **Service** | deeptrail-control |
| **Dependencies** | WS-E1 (VaultClient enhancement) ✅ Complete |

---

## API Contract

### Endpoint Definition

| Field | Value |
|-------|-------|
| **Method** | `GET` |
| **Path** | `/api/v1/vault/tokens/{service_id}` |
| **Auth** | Agent JWT (Bearer token with `delegated_permissions`) |
| **Content-Type** | `application/json` |

### Path Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `service_id` | `str` | Yes | Service identifier (e.g., "notion", "slack", "hubspot") |

### Request Headers

| Header | Required | Description |
|--------|----------|-------------|
| `Authorization` | Yes | `Bearer <agent_jwt>` - JWT containing `user_id` from delegation |

### Response Schema (Success - 200)

```json
{
  "access_token": "string - OAuth access token",
  "token_type": "string - e.g., 'bearer'",
  "expires_in": "int | null - seconds until expiration",
  "scope": "string | null - granted scopes"
}
```

**Security Note:** `refresh_token` is NOT returned to agents.

### Error Responses

| Status | Condition | Response Body |
|--------|-----------|---------------|
| 401 | Invalid/missing JWT | `{"error": "unauthorized", "message": "Invalid token"}` |
| 403 | Service not in delegated_permissions | `{"error": "forbidden", "message": "Service not delegated"}` |
| 404 | Service not connected | `{"error": "not_found", "message": "Service not connected"}` |

---

## Implementation Notes

### Service Integration

```python
# Uses existing ConnectedServiceService
from app.services.connected_service_service import ConnectedServiceService

token_data = await connected_service_service.get_token_for_service(
    user_id=jwt_claims["user_id"],  # From delegation
    service_id=service_id
)
```

### Permission Validation

The endpoint MUST validate that `service_id` is in the agent JWT's `delegated_permissions` array before returning tokens.

```python
# Example JWT claims structure
{
    "sub": "agent_id",
    "user_id": "user_uuid",
    "delegated_permissions": ["notion:read", "notion:write", "slack:read"]
}
```

---

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `deeptrail-control/app/api/v1/endpoints/vault.py` | Create | Vault endpoints |
| `deeptrail-control/app/schemas/vault.py` | Create | Request/response schemas |
| `deeptrail-control/tests/api/test_vault.py` | Create | Endpoint tests |

---

## Test Endpoint Mapping

| Test Case | Method | Endpoint | Expected Status | Notes |
|-----------|--------|----------|-----------------|-------|
| Happy path | GET | `/api/v1/vault/tokens/notion` | 200 | Valid JWT, connected service |
| Unauthorized | GET | `/api/v1/vault/tokens/notion` | 401 | Missing/invalid JWT |
| Forbidden | GET | `/api/v1/vault/tokens/notion` | 403 | Service not in permissions |
| Not found | GET | `/api/v1/vault/tokens/notion` | 404 | Service not connected |

---

## Contract Verification Checklist

- [ ] Endpoint path matches spec exactly: `/api/v1/vault/tokens/{service_id}`
- [ ] Agent JWT validated before token retrieval
- [ ] Permission check against `delegated_permissions`
- [ ] Response excludes `refresh_token` (security)
- [ ] Error responses match spec format
- [ ] Tests cover all 4 cases (200, 401, 403, 404)

---

## References

- **Design Doc:** `plans/mvp_production_readiness.plan.md`
- **Upstream:** WS-E1 (VaultClient) ✅ Complete
- **Downstream:** WS-H1, WS-H2 (Gateway credential injection)
