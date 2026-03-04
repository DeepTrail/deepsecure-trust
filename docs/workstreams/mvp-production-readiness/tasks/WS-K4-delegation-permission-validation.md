# Task: WS-K4 Delegation Permission Validation

## Metadata

| Field | Value |
|-------|-------|
| **Task ID** | WS-K4 |
| **Task Name** | Delegation Permission Validation |
| **Workstream** | mvp-production-readiness |
| **Phase** | P1.5 (Integration Bug Fixes) |
| **Batch** | P1.5-B1 |
| **Status** | `pending` |
| **Dependencies** | WS-K3 (ScopeMapper) |
| **Complexity** | M (1-3 hrs) |
| **Service** | deeptrail-control |
| **Validates** | Monotonic attenuation principle |

---

## Specification

| Field | Value |
|-------|-------|
| **Spec File** | [WS-K4-spec.md](../specs/WS-K4-spec.md) |
| **Source** | PERMISSION_FLOW_ARCHITECTURE.md, Gap #2 (No Delegation Validation) |

### Key Contracts

| Component | Contract |
|-----------|----------|
| **Endpoint** | `POST /api/v1/auth/delegate` (enhancement) |
| **Validation** | Use `ScopeMapper.validate_permissions()` |
| **Error Response** | 400 Bad Request with `invalid_permissions` and `allowed_permissions` |
| **Exception** | `PermissionValidationError` class |

---

## API Contracts

### Endpoint: Create Delegation (Enhanced)

| Field | Value |
|-------|-------|
| **Method** | `POST` |
| **Path** | `/api/v1/auth/delegate` |
| **Status** | Existing (enhancement) |

### Current Behavior

| Validation | Current | After |
|------------|---------|-------|
| Connected service | Service-level check | Permission-level check |
| Error message | `"User not connected to service: {service}"` | Detailed with allowed/invalid |

### New Error Response (400 Bad Request)

```json
{
  "detail": {
    "error": "permission_validation_failed",
    "message": "Requested permissions not allowed by connected scopes",
    "invalid_permissions": [
      "notion:pages:create",
      "notion:pages:update"
    ],
    "allowed_permissions": [
      "notion:pages:read",
      "notion:pages:search"
    ],
    "hint": "Connect service with additional scopes or remove invalid permissions"
  }
}
```

---

## Pre-Conditions

- [ ] WS-K3 (ScopeMapper) is complete
- [ ] `ScopeMapper` class is importable from `app.services.scope_mapper`
- [ ] `ConnectedService` model exists with `scopes_granted` field
- [ ] Delegation endpoint exists at `/api/v1/auth/delegate`

---

## Task Description

### Objective

Enhance the delegation endpoint to validate that requested permissions are allowed by the user's connected service scopes, enforcing the monotonic attenuation principle.

### Background

During Integration Validation Guide testing (Step 9), a gap was identified:

1. User connects Notion with scopes `"read_pages search_content"`
2. User tries to delegate `["notion:pages:search", "notion:pages:create"]`
3. **Current:** Delegation succeeds (only checks if Notion is connected)
4. **Problem:** Agent gets `notion:pages:create` permission but will fail when calling Notion API

The proper behavior is to reject the delegation at creation time with a clear error message explaining what permissions are allowed.

### What to Implement

1. **Enhance `_validate_permissions_subset` in DelegationService**
   - Import and use `ScopeMapper.validate_permissions()`
   - Return invalid permissions and allowed permissions in response
   - Log validation failures with details

2. **Create `PermissionValidationError` exception**
   - Include `invalid_permissions` and `allowed_permissions` fields
   - Raise from `create_delegation()` when validation fails

3. **Update delegation endpoint error handling**
   - Catch `PermissionValidationError`
   - Return 400 status with detailed error response
   - Include hint for user action

4. **Maintain backward compatibility**
   - Existing valid delegations should continue to work
   - In-memory storage pattern unchanged

---

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `deeptrail-control/app/services/delegation_service.py` | Modify | Add `ScopeMapper` validation, `PermissionValidationError` |
| `deeptrail-control/app/api/v1/endpoints/delegation.py` | Modify | Enhanced error handling for validation failures |
| `deeptrail-control/tests/api/test_delegation_validation.py` | Create | Unit tests for permission validation |

---

## Acceptance Criteria

### Functional

- [ ] `_validate_permissions_subset` uses `ScopeMapper.validate_permissions()`
- [ ] Valid permissions create delegation successfully (200 OK)
- [ ] Invalid permissions rejected with 400 Bad Request
- [ ] Error response includes `invalid_permissions` array
- [ ] Error response includes `allowed_permissions` array
- [ ] Error response includes actionable `hint`
- [ ] Mixed valid/invalid only shows invalid in error

### Security

- [ ] Monotonic attenuation enforced (agent can't get more than user)
- [ ] No sensitive data in error responses
- [ ] Validation failures logged with details

### Integration

- [ ] Backward compatible with existing delegations
- [ ] Works with in-memory storage pattern
- [ ] Integration Validation Guide Step 9 properly rejects over-permissioned delegations

---

## Test Cases

| Test Case | Method | Endpoint | Expected Status | Notes |
|-----------|--------|----------|-----------------|-------|
| Valid permissions | `test_valid_permissions_succeed` | `POST /api/v1/auth/delegate` | 200 | Permissions match scopes |
| Invalid permissions | `test_invalid_permissions_rejected` | `POST /api/v1/auth/delegate` | 400 | Requires write, only read connected |
| Mixed valid/invalid | `test_mixed_permissions_shows_invalid_only` | `POST /api/v1/auth/delegate` | 400 | Error lists only invalid |
| No connected services | `test_no_connected_services_error` | `POST /api/v1/auth/delegate` | 400 | User has no connections |
| Unknown service permission | `test_unknown_service_rejected` | `POST /api/v1/auth/delegate` | 400 | Permission for unconnected service |

---

## Post-Conditions

After this task is complete:

- [ ] Integration Validation Guide Step 9 properly validates delegations
- [ ] Users receive clear feedback on invalid permission requests
- [ ] Agents cannot receive permissions beyond user's connected scopes
- [ ] WS-K5 (Available Permissions) can help users know what to delegate

---

## Validation

### Unit Tests

```bash
cd /Users/imaxxs/repositories/deepsecure-mvp/deeptrail-control

# Run delegation validation tests
pytest tests/api/test_delegation_validation.py -v

# Run with coverage
pytest tests/api/test_delegation_validation.py -v --cov=app.api.v1.endpoints.delegation
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

# 3. Connect Notion with read-only scopes
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
# Expected: success

# 4. Register agent
curl -s -X POST http://localhost:8000/api/v1/agents/register \
  -H "Authorization: Bearer $USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"agent_id": "test-agent", "description": "Test"}' | jq .

# 5. Try to delegate VALID permissions (should succeed)
curl -s -X POST http://localhost:8000/api/v1/auth/delegate \
  -H "Authorization: Bearer $USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "test-agent",
    "permissions": ["notion:pages:search", "notion:pages:read"]
  }' | jq .
# Expected: 200 OK with delegation_token

# 6. Try to delegate INVALID permissions (should fail)
curl -s -X POST http://localhost:8000/api/v1/auth/delegate \
  -H "Authorization: Bearer $USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "test-agent",
    "permissions": ["notion:pages:search", "notion:pages:create"]
  }' | jq .
# Expected: 400 Bad Request with:
# {
#   "detail": {
#     "error": "permission_validation_failed",
#     "invalid_permissions": ["notion:pages:create"],
#     "allowed_permissions": ["notion:pages:read", "notion:pages:search"],
#     "hint": "Connect service with additional scopes..."
#   }
# }

# 7. Clean up
docker compose down
```

---

## References

- **Spec:** [WS-K4-spec.md](../specs/WS-K4-spec.md)
- **Architecture:** [PERMISSION_FLOW_ARCHITECTURE.md](../../architecture/PERMISSION_FLOW_ARCHITECTURE.md)
- **Upstream Dependencies:** WS-K3 (ScopeMapper)
- **Downstream Dependents:** None (end of validation chain)
- **Existing Service:** `deeptrail-control/app/services/delegation_service.py`
- **Existing Endpoint:** `deeptrail-control/app/api/v1/endpoints/delegation.py`

---

## Execution

```bash
# Run in mvp-prod-control worktree:
cd /Users/imaxxs/repositories/mvp-prod-control

# Execute the task (after WS-K3 is complete)
/execute-task WS-K4 mvp-production-readiness

# After completion
/complete-task WS-K4 mvp-production-readiness
```
