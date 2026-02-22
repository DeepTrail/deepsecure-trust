# Task Specification: WS-I3 Convert expires_in to expires_at in Vault Token Response

> **IMMUTABLE AFTER DESIGN APPROVAL**
>
> This specification defines what implementation MUST match exactly.
> Do not modify without updating the design doc first.
>
> **Source:** User feedback on Test Scenario 9 (Vault Token Retrieval)

---

## Overview

| Field | Value |
|-------|-------|
| **Task ID** | WS-I3 |
| **Task Name** | Convert expires_in to expires_at in Vault Token Response |
| **Type** | Schema Change / API Response Update |
| **Service** | deeptrail-control |
| **Complexity** | S (< 1 hour) |
| **Dependencies** | WS-E2 (Vault Token Retrieval) ✅ Complete |
| **Validates** | Test Scenario 9 response format, E2E token handling |

---

## Problem Statement

### Current State

```
POST /api/v1/users/me/services/connect
  Input: { "oauth_token": { "expires_in": 31536000, ... } }
  ↓
VaultClient.store_token()
  Internal: converts expires_in → expires_at (datetime)
  ↓
GET /api/v1/vault/tokens/{service_id}
  Output: { "expires_in": 31536000, ... }  ← INCONSISTENT
```

**Issue:** The response returns `expires_in` (seconds), but:
1. This value is recalculated from the stored `expires_at` timestamp
2. Absolute timestamps (`expires_at`) are more useful for scheduling/comparison
3. The current `expires_in` may drift from what was originally provided

### Desired State

```
POST /api/v1/users/me/services/connect
  Input: { "oauth_token": { "expires_in": 31536000, ... } }
  ↓
VaultClient.store_token()
  Internal: converts expires_in → expires_at (datetime)
  ↓
GET /api/v1/vault/tokens/{service_id}
  Output: { "expires_at": "2027-02-22T03:58:23.418842+00:00", ... }  ← ABSOLUTE TIMESTAMP
```

---

## API Contract

### Endpoint Definition

| Field | Value |
|-------|-------|
| **Method** | `GET` |
| **Path** | `/api/v1/vault/tokens/{service_id}` |
| **Auth** | Agent JWT (Bearer token with `owner` claim) |
| **Content-Type** | `application/json` |

### Response Schema (Success - 200) - UPDATED

```json
{
  "service_id": "string - service identifier (e.g., 'notion')",
  "access_token": "string - OAuth access token",
  "token_type": "string - e.g., 'bearer'",
  "expires_at": "string | null - ISO 8601 datetime when token expires",
  "scope": "string | null - space-separated granted scopes"
}
```

**Changes from current:**
| Field | Before | After |
|-------|--------|-------|
| `expires_in` | `int \| null` (seconds) | REMOVED |
| `expires_at` | N/A | `string \| null` (ISO 8601 datetime) |
| `service_id` | N/A | `string` (ADDED for clarity) |

### Example Response

**Before (Current):**
```json
{
  "access_token": "secret_xxx",
  "token_type": "bearer",
  "expires_in": 3600,
  "scope": "read_pages search_content"
}
```

**After (WS-I3):**
```json
{
  "service_id": "notion",
  "access_token": "secret_xxx",
  "token_type": "bearer",
  "expires_at": "2026-02-22T04:58:23.418842+00:00",
  "scope": "read_pages search_content"
}
```

---

## Component Specification

### Schema: `TokenResponse` (Updated)

| Field | Value |
|-------|-------|
| **Module** | `deeptrail-control/app/schemas/vault_token.py` |
| **Type** | Pydantic Model |
| **Purpose** | Response schema for vault token retrieval |

### Schema Definition

```python
from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional


class TokenResponse(BaseModel):
    """Response schema for token retrieval.

    Returns the OAuth access token and metadata for a connected service.

    Attributes:
        service_id: Service identifier (e.g., "notion").
        access_token: The OAuth access token for API calls.
        token_type: Token type, typically "bearer".
        expires_at: ISO 8601 datetime when token expires (optional).
        scope: Space-separated list of granted scopes (optional).

    Security:
        - Does NOT include refresh_token (security requirement)
        - Agents should never see refresh tokens
    """

    service_id: str = Field(..., description="Service identifier")
    access_token: str = Field(..., description="OAuth access token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_at: Optional[datetime] = Field(
        default=None,
        description="ISO 8601 datetime when token expires"
    )
    scope: Optional[str] = Field(
        default=None,
        description="Space-separated list of granted scopes"
    )
```

---

## Implementation Details

### Endpoint Change: `GET /api/v1/vault/tokens/{service_id}`

**File:** `deeptrail-control/app/api/v1/endpoints/vault.py`

**Current Code (lines 182-201):**
```python
# 5. Build response (never include refresh_token)
expires_in = token_data.get("expires_in")
scope = token_data.get("scope")

# Convert scope list to space-separated string if needed
if isinstance(scope, list):
    scope = " ".join(scope)

return TokenResponse(
    access_token=access_token,
    token_type=token_data.get("token_type", "bearer"),
    expires_in=expires_in,
    scope=scope,
)
```

**Updated Code:**
```python
# 5. Build response (never include refresh_token)
# Get expires_at from metadata (stored by VaultClient)
metadata = token_data.get("metadata", {})
expires_at_str = metadata.get("expires_at")
expires_at = None
if expires_at_str:
    from datetime import datetime
    expires_at = datetime.fromisoformat(expires_at_str)

scope = token_data.get("scope")

# Convert scope list to space-separated string if needed
if isinstance(scope, list):
    scope = " ".join(scope)

return TokenResponse(
    service_id=service_id,
    access_token=access_token,
    token_type=token_data.get("token_type", "bearer"),
    expires_at=expires_at,
    scope=scope,
)
```

### TokenRefreshResponse Also Needs Update

**File:** `deeptrail-control/app/schemas/vault_token.py`

```python
class TokenRefreshResponse(BaseModel):
    """Response schema for token refresh."""

    access_token: str = Field(..., description="OAuth access token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_at: Optional[datetime] = Field(  # Changed from expires_in
        default=None,
        description="ISO 8601 datetime when token expires"
    )
    refreshed: bool = Field(..., description="Whether token was actually refreshed")
    message: str = Field(..., description="Status message")
```

---

## VaultClient Metadata Structure

The VaultClient already stores `expires_at` in metadata:

```python
# From vault_client.py:store_token()
metadata = TokenMetadata(
    created_at=now,
    expires_at=expires_at,  # datetime object stored here
    last_used_at=None,
    refresh_count=0,
)
```

The token retrieval needs to read from `token_data["metadata"]["expires_at"]`.

---

## File Location Rules

| Artifact | Correct Location | Notes |
|----------|------------------|-------|
| Schema update | `deeptrail-control/app/schemas/vault_token.py` | Modify TokenResponse |
| Endpoint update | `deeptrail-control/app/api/v1/endpoints/vault.py` | Modify retrieval logic |
| Unit tests | `deeptrail-control/tests/api/test_vault_tokens.py` | Update expected responses |

---

## Test Cases

### Unit Tests (Update Required)

| Test Case | Method | Endpoint | Before | After |
|-----------|--------|----------|--------|-------|
| Token retrieval success | GET | `/api/v1/vault/tokens/notion` | `expires_in: 3600` | `expires_at: "2026-..."` |
| Token with no expiry | GET | `/api/v1/vault/tokens/notion` | `expires_in: null` | `expires_at: null` |
| Token refresh (valid) | POST | `/api/v1/vault/tokens/{id}/refresh` | `expires_in: 3600` | `expires_at: "2026-..."` |

### Manual Verification

```bash
# 1. Connect a service with expires_in
curl -s -X POST http://localhost:8000/api/v1/users/me/services/connect \
  -H "Authorization: Bearer $USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "service_id": "notion",
    "oauth_token": {
      "access_token": "secret_xxx",
      "token_type": "bearer",
      "scope": "read_pages search_content",
      "expires_in": 3600
    }
  }'

# 2. Retrieve token - should have expires_at
curl -s http://localhost:8000/api/v1/vault/tokens/notion \
  -H "Authorization: Bearer $AGENT_JWT" | jq .

# Expected output:
# {
#   "service_id": "notion",
#   "access_token": "secret_xxx",
#   "token_type": "bearer",
#   "expires_at": "2026-02-22T05:00:00.000000+00:00",
#   "scope": "read_pages search_content"
# }
```

---

## Contract Verification Checklist

Before marking implementation complete, verify:

- [ ] `TokenResponse` schema has `expires_at` (datetime) instead of `expires_in` (int)
- [ ] `TokenResponse` schema includes `service_id` field
- [ ] `TokenRefreshResponse` schema updated similarly
- [ ] Vault retrieval endpoint reads `expires_at` from metadata
- [ ] Response serializes `expires_at` as ISO 8601 string
- [ ] Tests updated to expect `expires_at` format
- [ ] Test Scenario 9 returns correct response format
- [ ] No `expires_in` field in any vault token response

---

## Backward Compatibility

**Breaking Change:** Yes, this changes the API response format.

**Impact:**
- Gateway credential injection (WS-H1) may need minor update to handle `expires_at`
- Any code expecting `expires_in` in response will break

**Mitigation:**
- Gateway can use `expires_at` for more accurate expiration checking
- This is within MVP scope, so breaking changes are acceptable

---

## Expected Output After Implementation

### Test Scenario 9 Response

**Before:**
```json
{
  "access_token": "test_notion_token_12345",
  "token_type": "bearer",
  "expires_in": 3600,
  "scope": "read_pages search_content"
}
```

**After:**
```json
{
  "service_id": "notion",
  "access_token": "test_notion_token_12345",
  "token_type": "bearer",
  "expires_at": "2026-02-22T05:00:00.000000+00:00",
  "scope": "read_pages search_content"
}
```

---

## References

- **Design Doc Section:** User feedback on vault token response format
- **Related Specs:** [WS-E2-spec.md](./WS-E2-spec.md) (original vault endpoint)
- **Upstream Dependencies:** WS-E2 ✅ Complete
- **Downstream Dependents:** WS-H1 (may need minor update for expires_at handling)
- **Test Scenario:** INTEGRATION_VALIDATION_GUIDE.md Section 12 (Test Scenario 9)
