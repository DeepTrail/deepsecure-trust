# WS-K3 Completion Report: Scope-to-Permission Mapper

## Summary

| Field | Value |
|-------|-------|
| **Task ID** | WS-K3 |
| **Task Name** | Scope-to-Permission Mapper |
| **Status** | ✅ Complete |
| **Completed** | February 22, 2026 |
| **Phase** | P1.5 (Integration Bug Fixes) |
| **Service** | deeptrail-control |

---

## Implementation Details

### Files Created

| File | Description |
|------|-------------|
| `deeptrail-control/app/services/scope_mapper.py` | ScopeMapper class with static OAuth scope → permission mappings |
| `deeptrail-control/tests/services/test_scope_mapper.py` | Comprehensive unit tests (43 tests) |

### Files Modified

| File | Change |
|------|--------|
| `deeptrail-control/app/services/__init__.py` | Export `ScopeMapper` class |

---

## What Was Implemented

### 1. ScopeMapper Class

A static mapper that converts OAuth scopes to DeepSecure permission strings:

```python
from app.services.scope_mapper import ScopeMapper

# Single scope lookup
perms = ScopeMapper.get_permissions_for_scope("notion", "read_pages")
# Returns: ["notion:pages:read", "notion:pages:search"]

# Multiple scopes
perms = ScopeMapper.get_permissions_for_scopes("notion", ["read_pages", "write_pages"])
# Returns: {"notion:pages:read", "notion:pages:search", "notion:pages:create", "notion:pages:update"}

# Validate delegation permissions
is_valid, invalid = ScopeMapper.validate_permissions(
    ["notion:pages:search", "notion:pages:create"],
    [("notion", ["read_pages"])],  # No write scope!
)
# Returns: (False, ["notion:pages:create"])

# Group by service for UI
result = ScopeMapper.get_available_permissions_by_service([
    ("notion", ["read_pages"]),
    ("slack", ["channels:read"]),
])
# Returns: {"notion": [...], "slack": [...]}
```

### 2. Scope Mappings

**Notion (8 scopes):**
| Scope | Permissions |
|-------|-------------|
| `read_content` | `notion:pages:read`, `notion:pages:search`, `notion:databases:list`, `notion:databases:query` |
| `update_content` | `notion:pages:update` |
| `insert_content` | `notion:pages:create` |
| `read_pages` | `notion:pages:read`, `notion:pages:search` |
| `search_content` | `notion:pages:search` |
| `write_pages` | `notion:pages:create`, `notion:pages:update` |
| `read_databases` | `notion:databases:list`, `notion:databases:query` |
| `full_access` | All 7 Notion permissions |

**Slack (9 scopes):**
| Scope | Permissions |
|-------|-------------|
| `channels:read` | `slack:channels:list` |
| `channels:history` | `slack:messages:search` |
| `chat:write` | `slack:messages:send` |
| `users:read` | `slack:users:list` |
| `reactions:write` | `slack:reactions:write` |
| `search:read` | `slack:messages:search` |
| `read_messages` | `slack:messages:search` |
| `send_messages` | `slack:messages:send` |
| `list_channels` | `slack:channels:list` |

**HubSpot (8 scopes):**
| Scope | Permissions |
|-------|-------------|
| `crm.objects.contacts.read` | `hubspot:contacts:read`, `hubspot:contacts:list` |
| `crm.objects.contacts.write` | `hubspot:contacts:create`, `hubspot:contacts:update` |
| `crm.objects.deals.read` | `hubspot:deals:list` |
| `crm.objects.deals.write` | `hubspot:deals:create`, `hubspot:deals:update` |
| `read_contacts` | `hubspot:contacts:read`, `hubspot:contacts:list` |
| `write_contacts` | `hubspot:contacts:create`, `hubspot:contacts:update` |
| `read_deals` | `hubspot:deals:list` |
| `write_deals` | `hubspot:deals:create`, `hubspot:deals:update` |

### 3. Methods Implemented

| Method | Purpose |
|--------|---------|
| `get_permissions_for_scope(service_id, scope)` | Single scope → permissions |
| `get_permissions_for_scopes(service_id, scopes)` | Multiple scopes → set of permissions |
| `get_all_allowed_permissions(connected_services)` | All permissions across services |
| `validate_permissions(requested, connected)` | Check if delegation is valid |
| `get_available_permissions_by_service(connected)` | Group permissions for UI |
| `get_supported_services()` | List known services |
| `get_supported_scopes(service_id)` | List known scopes for service |
| `get_all_permissions_for_service(service_id)` | All permissions for a service |

---

## Acceptance Criteria Verification

| Criterion | Status | Evidence |
|-----------|--------|----------|
| ScopeMapper class created with static mappings | ✅ | `scope_mapper.py` with `SCOPE_TO_PERMISSIONS` dict |
| Notion scope mappings (7+ scopes) | ✅ | 8 scopes including full_access |
| Slack scope mappings (6+ scopes) | ✅ | 9 scopes including aliases |
| HubSpot scope mappings (6+ scopes) | ✅ | 8 scopes including aliases |
| `get_permissions_for_scope()` returns correct permissions | ✅ | 9 tests pass |
| `get_permissions_for_scope()` returns empty for unknown | ✅ | Tests for unknown scope/service |
| `get_permissions_for_scopes()` combines correctly | ✅ | 5 tests pass |
| `validate_permissions()` returns `(True, [])` for valid | ✅ | 7 validation tests pass |
| `validate_permissions()` returns `(False, [invalid])` for invalid | ✅ | Tests include mixed valid/invalid |
| `get_available_permissions_by_service()` groups correctly | ✅ | 5 tests pass |
| Case-insensitive service_id handling | ✅ | Explicit test for case insensitivity |
| Module exported from `__init__.py` | ✅ | Added to imports and `__all__` |
| Permission strings match Gateway's PermissionMapper | ✅ | 3 consistency tests validate all permissions |

---

## Test Results

```
============================= test session starts ==============================
platform darwin -- Python 3.12.2
collected 43 items

tests/services/test_scope_mapper.py::TestGetPermissionsForScope (9 tests)     PASSED
tests/services/test_scope_mapper.py::TestGetPermissionsForScopes (5 tests)    PASSED
tests/services/test_scope_mapper.py::TestGetAllAllowedPermissions (3 tests)   PASSED
tests/services/test_scope_mapper.py::TestValidatePermissions (7 tests)        PASSED
tests/services/test_scope_mapper.py::TestGetAvailablePermissionsByService (5 tests) PASSED
tests/services/test_scope_mapper.py::TestGetSupportedServices (2 tests)       PASSED
tests/services/test_scope_mapper.py::TestGetSupportedScopes (5 tests)         PASSED
tests/services/test_scope_mapper.py::TestGetAllPermissionsForService (4 tests) PASSED
tests/services/test_scope_mapper.py::TestPermissionConsistency (3 tests)      PASSED

======================== 43 passed in 0.08s ====================================
```

### Lint Status

```
ruff check app/services/scope_mapper.py tests/services/test_scope_mapper.py
All checks passed!
```

---

## Post-Conditions Enabled

| Task | How This Enables It |
|------|---------------------|
| **WS-K4** (Delegation Permission Validation) | Can use `ScopeMapper.validate_permissions()` to verify delegated permissions match connected scopes |
| **WS-K5** (Available Permissions Endpoint) | Can use `ScopeMapper.get_available_permissions_by_service()` to show users what they can delegate |
| **Integration Validation Guide Step 9** | Delegation requests can now be properly validated against connected services |

---

## Technical Notes

### Permission String Consistency

The `ScopeMapper` permission strings are verified to match the Gateway's `PermissionMapper` exactly. This is critical because:

1. **Control Plane** uses `ScopeMapper` to validate what permissions can be delegated
2. **Gateway** uses `PermissionMapper` to check if a tool call is authorized

If these permission strings diverge, agents could be delegated permissions that don't work, or be blocked from tools they should have access to.

The `TestPermissionConsistency` test class verifies all permissions match:
- Notion: 7 permissions
- Slack: 6 permissions  
- HubSpot: 7 permissions

### User-Friendly Scope Aliases

In addition to official OAuth scopes (like `channels:read`, `crm.objects.contacts.read`), user-friendly aliases are supported:

- `read_pages` instead of `read_content` (Notion)
- `list_channels` instead of `channels:read` (Slack)
- `read_contacts` instead of `crm.objects.contacts.read` (HubSpot)

This allows demos and tests to use simpler scope names while production can use official OAuth scopes.

---

## References

- **Implementation**: `deeptrail-control/app/services/scope_mapper.py`
- **Tests**: `deeptrail-control/tests/services/test_scope_mapper.py`
- **Spec**: `docs/workstreams/mvp-production-readiness/specs/WS-K3-spec.md`
- **Gateway PermissionMapper**: `deeptrail-gateway/app/mcp/permission_mapper.py`
- **Architecture**: `docs/architecture/PERMISSION_FLOW_ARCHITECTURE.md`
