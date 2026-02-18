# Bug Fix: E2/E3 Vault Token Retrieval Uses Wrong Reference Generation

## Context

**Problem:** The vault token endpoints (E2 retrieval, E3 refresh) cannot retrieve tokens because they regenerate token references instead of looking up stored references.

**Root Cause:** In `deeptrail-control/app/api/v1/endpoints/vault.py`:
```python
# Line 134-135 (E2) and Line 271 (E3)
token_ref = vault_client._generate_ref(user_id, service_id)  # BUG!
token_data = vault_client.retrieve_token(token_ref)
```

The `_generate_ref()` function uses `uuid.uuid4().hex[:8]` which creates a **unique reference each call**:
- Storage creates: `vault://sarah-notion-a1b2c3d4`
- Retrieval generates: `vault://sarah-notion-x9y8z7w6` (different!)
- Result: 404 "Service not connected" every time

**Impact:** E2 and E3 endpoints always return 404, even when services are connected.

**Correct Behavior:** Query the `ConnectedService` database to get the stored `oauth_token_ref`.

---

## Task Specification: WS-E2E3-BUGFIX

### Metadata

| Field | Value |
|-------|-------|
| **Task ID** | WS-E2E3-BUGFIX |
| **Type** | Bug Fix |
| **Severity** | High (blocks E2/E3 functionality) |
| **Phase** | P1 (Real Backend Integration) |
| **Service** | deeptrail-control |
| **Complexity** | S (< 1hr) |

### Bug Description

**Symptom:** `GET /api/v1/vault/tokens/{service_id}` and `POST /api/v1/vault/tokens/{service_id}/refresh` always return 404 "Service not connected" even when the service IS connected.

**Root Cause:** Both endpoints call `vault_client._generate_ref(user_id, service_id)` to create a token reference, but `_generate_ref()` uses `uuid.uuid4()` which generates a **different reference each call**.

```python
# vault_client.py line 206 - creates UNIQUE ref each time
def _generate_ref(self, user_id: str, service_id: str) -> str:
    suffix = uuid.uuid4().hex[:8]  # Different every call!
    return f"vault://{user_part}-{service_id}-{suffix}"
```

**Correct Pattern:** The `ConnectedServiceService.get_token_for_service()` method (line 240-270) does this correctly - it queries the database for the stored `oauth_token_ref`:

```python
connection = self._db.query(ConnectedService).filter(
    ConnectedService.user_id == user_id,
    ConnectedService.service_id == service_id,
).first()
return self._vault.retrieve_token(connection.oauth_token_ref)  # Uses STORED ref
```

---

## Files to Modify

### Primary File: `deeptrail-control/app/api/v1/endpoints/vault.py`

**Change 1: Fix E2 - `get_token_for_service()` (lines 80-180)**

```python
# BEFORE (line 134-135):
token_ref = vault_client._generate_ref(user_id, service_id)
token_data = vault_client.retrieve_token(token_ref)

# AFTER:
# Query database for stored token reference
connection = db.query(ConnectedService).filter(
    ConnectedService.user_id == user_id,
    ConnectedService.service_id == service_id,
    ConnectedService.disconnected_at.is_(None),
).first()

if not connection or not connection.oauth_token_ref:
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"error": "not_found", "message": "Service not connected"},
    )

token_data = vault_client.retrieve_token(connection.oauth_token_ref)
```

**Change 2: Fix E3 - `refresh_token()` (line ~271)**

```python
# BEFORE (line 271):
token_ref = vault_client._generate_ref(x_user_id, service_id)

# AFTER:
connection = db.query(ConnectedService).filter(
    ConnectedService.user_id == x_user_id,
    ConnectedService.service_id == service_id,
    ConnectedService.disconnected_at.is_(None),
).first()

if not connection or not connection.oauth_token_ref:
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"error": "not_found", "message": "Service not connected"},
    )

token_ref = connection.oauth_token_ref
```

**Change 3: Add imports and dependencies**

```python
# Add import at top:
from app.models.connected_service import ConnectedService

# Add db dependency to function signatures:
async def get_token_for_service(
    service_id: str,
    agent_claims: deps.AgentClaimsDep,
    db: deps.DbDep,  # ADD THIS
    vault_client: VaultClient = Depends(get_vault_client),
) -> TokenResponse:

async def refresh_token(
    service_id: str,
    request: TokenRefreshRequest,
    x_user_id: str = Header(..., alias="X-User-ID"),
    internal_token: str = Depends(deps.verify_internal_token),
    db: deps.DbDep,  # ADD THIS
    vault_client: VaultClient = Depends(get_vault_client),
    oauth_service: OAuthService = Depends(get_oauth_service_dep),
) -> TokenRefreshResponse:
```

---

## Acceptance Criteria

### Functional Criteria

- [ ] E2: `GET /api/v1/vault/tokens/{service_id}` returns 200 with token data when service is connected
- [ ] E2: Returns 404 only when service is genuinely not connected
- [ ] E3: `POST /api/v1/vault/tokens/{service_id}/refresh` returns 200 when refreshing connected service
- [ ] E3: Returns 404 only when service is genuinely not connected
- [ ] Both endpoints query `ConnectedService` table for stored `oauth_token_ref`
- [ ] No calls to `vault_client._generate_ref()` in retrieval paths

### Test Criteria

- [ ] Existing unit tests in `tests/api/test_vault_tokens.py` still pass
- [ ] Integration test with live services returns 200 (not 404)

---

## Verification

### Unit Tests

```bash
cd /Users/imaxxs/repositories/deepsecure-mvp/deeptrail-control
pytest tests/api/test_vault_tokens.py -v
```

### Integration Test (After Fix)

```bash
# 1. Start services
docker compose up -d

# 2. Login and connect service
USER_TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"sarah@acme.com","password":"test_password"}' | jq -r '.token')

curl -s -X POST http://localhost:8000/api/v1/users/me/services/connect \
  -H "Authorization: Bearer $USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "service_id": "notion",
    "oauth_token": {"access_token": "test_token", "token_type": "bearer"}
  }'

# 3. Generate Agent JWT (using docker's SECRET_KEY)
AGENT_JWT=$(python3 -c "
import jwt
from datetime import datetime, timezone, timedelta
payload = {
    'iss': 'deeptrail-control', 'aud': 'deeptrail-gateway', 'sub': 'agent-test-001',
    'iat': int(datetime.now(timezone.utc).timestamp()),
    'exp': int((datetime.now(timezone.utc) + timedelta(hours=8)).timestamp()),
    'session_id': 'test-session-123', 'owner': 'sarah@acme.com',
    'delegated_permissions': ['notion', 'slack', 'hubspot'], 'delegation_id': 'test-delegation-001',
}
print(jwt.encode(payload, 'your-secret-key-for-jwt', algorithm='HS256'))
")

# 4. Test E2 - Should return 200 with token (not 404)
curl -s -w "\nHTTP Status: %{http_code}\n" \
  -X GET "http://localhost:8000/api/v1/vault/tokens/notion" \
  -H "Authorization: Bearer $AGENT_JWT"
# Expected: {"service_id": "notion", "access_token": "test_token", ...}

# 5. Test E3 - Should return 200 (not 404)
curl -s -w "\nHTTP Status: %{http_code}\n" \
  -X POST "http://localhost:8000/api/v1/vault/tokens/notion/refresh" \
  -H "Authorization: Bearer gateway-internal-secret-token" \
  -H "X-User-ID: sarah@acme.com" \
  -H "Content-Type: application/json" \
  -d '{"force": false}'
# Expected: 200 with refresh result (or 400 if no refresh_token - but NOT 404)
```

---

## Related Files

| File | Purpose |
|------|---------|
| `deeptrail-control/app/api/v1/endpoints/vault.py` | **Primary file to fix** |
| `deeptrail-control/app/models/connected_service.py` | ConnectedService model |
| `deeptrail-control/app/services/vault_client.py` | Token storage (reference) |
| `deeptrail-control/app/services/connected_service_service.py` | Correct pattern (line 240-270) |
| `deeptrail-control/tests/api/test_vault_tokens.py` | Unit tests (update if needed) |

---

## Summary

| Bug Location | Line | Current Code | Fixed Code |
|--------------|------|--------------|------------|
| `vault.py` E2 | 134-135 | `vault_client._generate_ref(...)` | Query `ConnectedService` for `oauth_token_ref` |
| `vault.py` E3 | ~271 | `vault_client._generate_ref(...)` | Query `ConnectedService` for `oauth_token_ref` |

**Root Cause:** `_generate_ref()` uses `uuid.uuid4()` which creates unique refs each time.

**Fix:** Query the database to get the stored reference instead of regenerating it.
