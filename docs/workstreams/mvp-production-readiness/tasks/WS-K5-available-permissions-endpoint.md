# Task: WS-K5 Available Permissions Endpoint

## Metadata

| Field | Value |
|-------|-------|
| **Task ID** | WS-K5 |
| **Task Name** | Available Permissions Endpoint |
| **Workstream** | mvp-production-readiness |
| **Phase** | P1.5 (Integration Bug Fixes) |
| **Batch** | P1.5-B1 |
| **Status** | `pending` |
| **Dependencies** | WS-K3 (ScopeMapper) |
| **Complexity** | S (< 1 hr) |
| **Service** | deeptrail-control |
| **Validates** | User permission discovery |

---

## Specification

| Field | Value |
|-------|-------|
| **Spec File** | [WS-K5-spec.md](../specs/WS-K5-spec.md) |
| **Source** | PERMISSION_FLOW_ARCHITECTURE.md, Gap #3 (No Scope Discovery UI) |

### Key Contracts

| Component | Contract |
|-----------|----------|
| **Endpoint** | `GET /api/v1/users/me/available-permissions` |
| **Auth** | Bearer token (User JWT) |
| **Uses** | `ScopeMapper.get_permissions_for_scopes()` |
| **Response** | Services map + flat permission list |

---

## API Contracts

### Endpoint: Available Permissions

| Field | Value |
|-------|-------|
| **Method** | `GET` |
| **Path** | `/api/v1/users/me/available-permissions` |
| **Auth** | Bearer token (User JWT) |
| **Content-Type** | `application/json` |

### Response Schema (200 OK)

```json
{
  "services": {
    "notion": {
      "connected": true,
      "service_name": "Notion",
      "scopes_granted": ["read_pages", "search_content"],
      "available_permissions": [
        "notion:pages:read",
        "notion:pages:search"
      ],
      "connected_at": "2026-02-22T04:42:38.796552+00:00"
    },
    "slack": {
      "connected": true,
      "service_name": "Slack",
      "scopes_granted": ["channels:read"],
      "available_permissions": [
        "slack:channels:list"
      ],
      "connected_at": "2026-02-22T05:00:00.000000+00:00"
    }
  },
  "all_permissions": [
    "notion:pages:read",
    "notion:pages:search",
    "slack:channels:list"
  ],
  "total_services": 2,
  "total_permissions": 3
}
```

### Error Responses

| Status | Condition | Response |
|--------|-----------|----------|
| 401 | Missing/invalid token | `{"detail": "Not authenticated"}` |
| 401 | Expired token | `{"detail": "Token expired"}` |

---

## Pre-Conditions

- [ ] WS-K3 (ScopeMapper) is complete
- [ ] `ScopeMapper` class is importable from `app.services.scope_mapper`
- [ ] `ConnectedService` model exists with `scopes_granted` field
- [ ] User authentication via Bearer token works

---

## Task Description

### Objective

Create an endpoint that returns all permissions a user can delegate based on their connected service scopes.

### Background

During Integration Validation Guide testing (Step 9), users must manually know permission strings to delegate. There's no way to discover:
1. What services they have connected
2. What scopes each service has
3. What permissions those scopes allow

This endpoint enables:
- UI permission pickers
- CLI permission suggestions
- Self-service delegation without documentation lookup

### What to Implement

1. **Create Pydantic Response Models**
   - `ServicePermissions` - Per-service permissions info
   - `AvailablePermissionsResponse` - Full response

2. **Add GET endpoint**
   - Path: `/api/v1/users/me/available-permissions`
   - Query connected services for current user
   - Use `ScopeMapper.get_permissions_for_scopes()` to derive permissions
   - Return both per-service and flat permission lists

3. **Write unit tests**
   - Test with connected services
   - Test with multiple services
   - Test with no connected services
   - Test excludes disconnected services
   - Test unauthorized access

---

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `deeptrail-control/app/api/v1/endpoints/users.py` | Modify | Add endpoint and response models |
| `deeptrail-control/tests/api/test_available_permissions.py` | Create | Unit tests for endpoint |

---

## Acceptance Criteria

### Functional

- [ ] Endpoint `GET /api/v1/users/me/available-permissions` exists
- [ ] Returns permissions based on connected service scopes
- [ ] Uses `ScopeMapper` to derive permissions from scopes
- [ ] Response includes `services` map with per-service details
- [ ] Response includes `all_permissions` flat list
- [ ] Includes `total_services` and `total_permissions` counts
- [ ] Excludes disconnected services (where `disconnected_at` is set)
- [ ] Permissions are sorted alphabetically
- [ ] Returns empty response (not error) for users with no connections

### Security

- [ ] Requires valid Bearer token
- [ ] Returns 401 for missing/invalid/expired token
- [ ] Only returns permissions for authenticated user

### Integration

- [ ] Can be used in Integration Validation Guide Step 8.5
- [ ] Permissions match what WS-K4 accepts for delegation
- [ ] Compatible with existing connected services data

---

## Test Cases

| Test Case | Method | Endpoint | Expected Status | Notes |
|-----------|--------|----------|-----------------|-------|
| Connected services | `test_returns_permissions_for_connected_service` | `GET /api/v1/users/me/available-permissions` | 200 | Returns Notion permissions |
| Multiple services | `test_returns_multiple_services` | `GET /api/v1/users/me/available-permissions` | 200 | Returns Notion + Slack |
| Flat list | `test_all_permissions_is_flat_list` | `GET /api/v1/users/me/available-permissions` | 200 | Combined from all services |
| No services | `test_empty_when_no_services` | `GET /api/v1/users/me/available-permissions` | 200 | Empty response |
| Excludes disconnected | `test_excludes_disconnected_services` | `GET /api/v1/users/me/available-permissions` | 200 | Disconnected not shown |
| No token | `test_unauthorized_without_token` | `GET /api/v1/users/me/available-permissions` | 401 | Auth required |
| Sorted | `test_permissions_are_sorted` | `GET /api/v1/users/me/available-permissions` | 200 | Alphabetical order |

---

## Post-Conditions

After this task is complete:

- [ ] Users can discover available permissions before creating delegations
- [ ] Integration Validation Guide can include Step 8.5
- [ ] UI/CLI can build permission pickers
- [ ] No more guessing permission string formats

---

## Validation

### Unit Tests

```bash
cd /Users/imaxxs/repositories/deepsecure-mvp/deeptrail-control

# Run available permissions tests
pytest tests/api/test_available_permissions.py -v

# Run with coverage
pytest tests/api/test_available_permissions.py -v --cov=app.api.v1.endpoints.users
```

### Manual Verification

```bash
# 1. Start services
cd /Users/imaxxs/repositories/deepsecure-mvp
docker compose up -d

# 2. Login
USER_TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"sarah@acme.com","password":"test_password"}' | jq -r '.token')

# 3. Connect Notion with read scopes
curl -s -X POST http://localhost:8000/api/v1/users/me/services/connect \
  -H "Authorization: Bearer $USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "service_id": "notion",
    "oauth_token": {
      "access_token": "test_token",
      "token_type": "Bearer",
      "scope": "read_pages search_content",
      "expires_at": "2027-02-22T00:00:00+00:00"
    }
  }' | jq .

# 4. Get available permissions
echo "=== Available Permissions ==="
curl -s -X GET http://localhost:8000/api/v1/users/me/available-permissions \
  -H "Authorization: Bearer $USER_TOKEN" | jq .
# Expected:
# {
#   "services": {
#     "notion": {
#       "connected": true,
#       "service_name": "Notion",
#       "scopes_granted": ["read_pages", "search_content"],
#       "available_permissions": ["notion:pages:read", "notion:pages:search"],
#       "connected_at": "..."
#     }
#   },
#   "all_permissions": ["notion:pages:read", "notion:pages:search"],
#   "total_services": 1,
#   "total_permissions": 2
# }

# 5. Verify count
PERM_COUNT=$(curl -s -X GET http://localhost:8000/api/v1/users/me/available-permissions \
  -H "Authorization: Bearer $USER_TOKEN" | jq '.total_permissions')
echo "✅ User has $PERM_COUNT permissions available for delegation"

# 6. Test with no token (should fail)
curl -s -X GET http://localhost:8000/api/v1/users/me/available-permissions | jq .
# Expected: 401 Unauthorized

# 7. Clean up
docker compose down
```

---

## References

- **Spec:** [WS-K5-spec.md](../specs/WS-K5-spec.md)
- **Architecture:** [PERMISSION_FLOW_ARCHITECTURE.md](../../architecture/PERMISSION_FLOW_ARCHITECTURE.md)
- **Upstream Dependencies:** WS-K3 (ScopeMapper)
- **Related:** WS-K4 (Delegation Validation uses same permission data)
- **Existing File:** `deeptrail-control/app/api/v1/endpoints/users.py`

---

## Execution

```bash
# Run in mvp-prod-control worktree (after WS-K3 is complete):
cd /Users/imaxxs/repositories/mvp-prod-control

# Execute the task
/execute-task WS-K5 mvp-production-readiness

# After completion
/complete-task WS-K5 mvp-production-readiness
```
