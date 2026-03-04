# WS-K5 Completion Report: Available Permissions Endpoint

## Summary

| Field | Value |
|-------|-------|
| **Task ID** | WS-K5 |
| **Task Name** | Available Permissions Endpoint |
| **Status** | ✅ Complete |
| **Completion Date** | February 22, 2026 |
| **Duration** | ~20 minutes |
| **Dependencies** | WS-K3 (ScopeMapper) ✅ |

---

## What Was Implemented

### 1. New Pydantic Response Models

Added to `users.py`:

```python
class ServicePermissions(BaseModel):
    """Permissions available for a single connected service."""
    connected: bool = True
    service_name: Optional[str] = None
    scopes_granted: List[str] = Field(default_factory=list)
    available_permissions: List[str] = Field(default_factory=list)
    connected_at: Optional[str] = None


class AvailablePermissionsResponse(BaseModel):
    """Response for available permissions endpoint."""
    services: Dict[str, ServicePermissions] = Field(default_factory=dict)
    all_permissions: List[str] = Field(default_factory=list)
    total_services: int = 0
    total_permissions: int = 0
```

### 2. New GET Endpoint

```python
@router.get(
    "/me/available-permissions",
    response_model=AvailablePermissionsResponse,
)
def get_available_permissions(
    current_user: CurrentUserDep,
    db: deps.DbDep,
) -> AvailablePermissionsResponse:
    # Query connected services
    # Use ScopeMapper.get_permissions_for_scopes() for each service
    # Return combined response with per-service and flat list
```

---

## Files Modified/Created

| File | Action | Description |
|------|--------|-------------|
| `deeptrail-control/app/api/v1/endpoints/users.py` | Modified | Added `ScopeMapper` import, response models, and endpoint |
| `deeptrail-control/tests/api/test_available_permissions.py` | Created | 9 unit tests |

---

## Acceptance Criteria Verification

### Functional

| Criterion | Status | Evidence |
|-----------|--------|----------|
| Endpoint `GET /api/v1/users/me/available-permissions` exists | ✅ | Router added |
| Returns permissions based on connected service scopes | ✅ | Uses ScopeMapper |
| Uses `ScopeMapper` to derive permissions from scopes | ✅ | Line 300 in users.py |
| Response includes `services` map with per-service details | ✅ | `test_returns_permissions_for_connected_service` |
| Response includes `all_permissions` flat list | ✅ | `test_all_permissions_is_flat_list` |
| Includes `total_services` and `total_permissions` counts | ✅ | In response model |
| Excludes disconnected services | ✅ | `test_excludes_disconnected_services` |
| Permissions are sorted alphabetically | ✅ | `test_permissions_are_sorted` |
| Returns empty response for users with no connections | ✅ | `test_empty_when_no_services` |

### Security

| Criterion | Status | Evidence |
|-----------|--------|----------|
| Requires valid Bearer token | ✅ | Uses `CurrentUserDep` |
| Returns 401/422 for missing token | ✅ | `test_unauthorized_without_token` |
| Only returns permissions for authenticated user | ✅ | Filters by `current_user` |

### Integration

| Criterion | Status | Evidence |
|-----------|--------|----------|
| Can be used in Integration Validation Guide Step 8.5 | ✅ | Endpoint operational |
| Permissions match what WS-K4 accepts for delegation | ✅ | Uses same ScopeMapper |
| Compatible with existing connected services data | ✅ | Queries ConnectedService model |

---

## Test Results

```
tests/api/test_available_permissions.py::TestAvailablePermissionsEndpoint::test_returns_permissions_for_connected_service PASSED
tests/api/test_available_permissions.py::TestAvailablePermissionsEndpoint::test_returns_multiple_services PASSED
tests/api/test_available_permissions.py::TestAvailablePermissionsEndpoint::test_all_permissions_is_flat_list PASSED
tests/api/test_available_permissions.py::TestAvailablePermissionsEndpoint::test_empty_when_no_services PASSED
tests/api/test_available_permissions.py::TestAvailablePermissionsEndpoint::test_excludes_disconnected_services PASSED
tests/api/test_available_permissions.py::TestAvailablePermissionsEndpoint::test_unauthorized_without_token PASSED
tests/api/test_available_permissions.py::TestAvailablePermissionsEndpoint::test_permissions_are_sorted PASSED
tests/api/test_available_permissions.py::TestAvailablePermissionsEndpoint::test_includes_service_metadata PASSED
tests/api/test_available_permissions.py::TestAvailablePermissionsEndpoint::test_full_access_scopes PASSED

======================== 9 passed ========================
```

---

## Quality Checks

| Check | Status |
|-------|--------|
| Ruff lint | ✅ All checks passed |
| Test coverage | ✅ 9 tests |
| No regressions | ✅ Existing users.py tests unaffected |

---

## Example Response

When a user has Notion and Slack connected:

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
      "connected_at": "2026-02-22T10:00:00+00:00"
    },
    "slack": {
      "connected": true,
      "service_name": "Slack",
      "scopes_granted": ["channels:read"],
      "available_permissions": [
        "slack:channels:list"
      ],
      "connected_at": "2026-02-22T10:05:00+00:00"
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

---

## Integration with Workflow

This endpoint enables:

1. **UI Permission Pickers** - Show users a list of permissions to select
2. **CLI Suggestions** - `deepsecure delegate --show-available`
3. **Self-service Delegation** - No need to lookup permission format
4. **Pre-validation** - User knows what will work before trying

### Integration Validation Guide Enhancement

New Step 8.5 can be added:

```bash
# Discover available permissions BEFORE creating delegation
curl -X GET http://localhost:8000/api/v1/users/me/available-permissions \
  -H "Authorization: Bearer $USER_TOKEN" | jq .

# Now user knows exactly what permissions they can delegate
```

---

## Post-Conditions Met

- [x] Users can discover available permissions before creating delegations
- [x] Integration Validation Guide can include Step 8.5
- [x] UI/CLI can build permission pickers
- [x] No more guessing permission string formats

---

## P1.5 Phase Progress

| Task | Status |
|------|--------|
| WS-J2 | ⏳ Pending |
| WS-K1 | ✅ Complete |
| WS-K2 | ⏳ Pending |
| WS-K3 | ✅ Complete |
| WS-K4 | ✅ Complete |
| **WS-K5** | ✅ **Complete** |

**Progress:** 4/6 tasks complete (67%)

**Remaining:** WS-J2 (Tool name derivation), WS-K2 (Cache invalidation)

---

## Next Steps

| Task | Description | Status |
|------|-------------|--------|
| **WS-K2** | Cache Invalidation via Redis Pub/Sub | ⏳ Pending |
| **WS-J2** | Fix tool name derivation and cache alignment | ⏳ Pending |

**Recommended next task:** WS-K2 or WS-J2 (either can proceed independently)
