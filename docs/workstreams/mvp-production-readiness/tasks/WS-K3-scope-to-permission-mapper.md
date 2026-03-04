# Task: WS-K3 Scope-to-Permission Mapper

## Metadata

| Field | Value |
|-------|-------|
| **Task ID** | WS-K3 |
| **Task Name** | Scope-to-Permission Mapper |
| **Workstream** | mvp-production-readiness |
| **Phase** | P1.5 (Integration Bug Fixes) |
| **Batch** | P1.5-B1 |
| **Status** | `ready` |
| **Dependencies** | None (standalone) |
| **Complexity** | M (1-3 hrs) |
| **Service** | deeptrail-control |
| **Validates** | Permission flow integrity, delegation validation |

---

## Specification

| Field | Value |
|-------|-------|
| **Spec File** | [WS-K3-spec.md](../specs/WS-K3-spec.md) |
| **Source** | PERMISSION_FLOW_ARCHITECTURE.md, Gap #1 (No Scope→Permission Mapping) |

### Key Contracts

| Component | Contract |
|-----------|----------|
| **Class** | `ScopeMapper` with static mappings |
| **Purpose** | Map OAuth scopes to DeepSecure permission strings |
| **Services** | Notion, Slack, HubSpot scope mappings |
| **Key Methods** | `get_permissions_for_scope()`, `validate_permissions()`, `get_available_permissions_by_service()` |

---

## API Contracts

> **Note:** This task implements an internal service module, not API endpoints.
> The `ScopeMapper` class is used by:
> - WS-K4 (Delegation validation)
> - WS-K5 (Available permissions endpoint)
> See [WS-K5](./WS-K5-available-permissions-endpoint.md) for the API endpoint that exposes this functionality.

### Internal Interface

```python
class ScopeMapper:
    @classmethod
    def get_permissions_for_scope(cls, service_id: str, scope: str) -> List[str]: ...
    
    @classmethod
    def get_permissions_for_scopes(cls, service_id: str, scopes: List[str]) -> Set[str]: ...
    
    @classmethod
    def validate_permissions(
        cls,
        requested_permissions: List[str],
        connected_services: List[Tuple[str, List[str]]],
    ) -> Tuple[bool, List[str]]: ...
    
    @classmethod
    def get_available_permissions_by_service(
        cls,
        connected_services: List[Tuple[str, List[str]]],
    ) -> Dict[str, List[str]]: ...
```

---

## Pre-Conditions

- [ ] deeptrail-control service exists
- [ ] `app/services/` directory exists
- [ ] No existing `scope_mapper.py` (new file)

---

## Task Description

### Objective

Create a `ScopeMapper` class that maps OAuth scopes (what users grant during service connection) to DeepSecure permission strings (what gets delegated to agents).

### Background

During Integration Validation Guide testing, a gap was identified:

1. **Step 6:** User connects Notion with scopes `"read_pages search_content"`
2. **Step 9:** User tries to delegate permissions `["notion:pages:search", "notion:pages:create"]`
3. **Problem:** No way to validate that `notion:pages:create` is NOT allowed by the connected scopes

The `ScopeMapper` fills this gap by providing a mapping between OAuth scopes and fine-grained DeepSecure permissions.

### What to Implement

1. **Create `ScopeMapper` class**
   - Static mapping dictionary: `SCOPE_TO_PERMISSIONS`
   - Support for Notion, Slack, HubSpot services
   - Both official OAuth scopes and user-friendly aliases

2. **Implement core methods**
   - `get_permissions_for_scope(service_id, scope)` - Single scope lookup
   - `get_permissions_for_scopes(service_id, scopes)` - Multiple scopes combined
   - `get_all_allowed_permissions(connected_services)` - All permissions across services
   - `validate_permissions(requested, connected)` - Validate delegation requests
   - `get_available_permissions_by_service(connected)` - Group by service for UI

3. **Add helper methods**
   - `get_supported_services()` - List known services
   - `get_supported_scopes(service_id)` - List known scopes for service

4. **Write comprehensive tests**

---

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `deeptrail-control/app/services/scope_mapper.py` | Create | ScopeMapper class with static mappings |
| `deeptrail-control/app/services/__init__.py` | Modify | Export ScopeMapper |
| `deeptrail-control/tests/services/test_scope_mapper.py` | Create | Unit tests for all methods |

---

## Scope Mapping Tables

### Notion Scopes

| Scope | Permissions |
|-------|-------------|
| `read_content` | `notion:pages:read`, `notion:pages:search`, `notion:databases:list`, `notion:databases:query` |
| `update_content` | `notion:pages:update` |
| `insert_content` | `notion:pages:create` |
| `read_pages` | `notion:pages:read`, `notion:pages:search` |
| `search_content` | `notion:pages:search` |
| `write_pages` | `notion:pages:create`, `notion:pages:update` |
| `read_databases` | `notion:databases:list`, `notion:databases:query` |

### Slack Scopes

| Scope | Permissions |
|-------|-------------|
| `channels:read` | `slack:channels:list` |
| `channels:history` | `slack:messages:search` |
| `chat:write` | `slack:messages:send` |
| `search:read` | `slack:messages:search` |
| `read_messages` | `slack:messages:search` |
| `list_channels` | `slack:channels:list` |

### HubSpot Scopes

| Scope | Permissions |
|-------|-------------|
| `crm.objects.contacts.read` | `hubspot:contacts:read`, `hubspot:contacts:list` |
| `crm.objects.contacts.write` | `hubspot:contacts:create`, `hubspot:contacts:update` |
| `crm.objects.deals.read` | `hubspot:deals:list` |
| `read_contacts` | `hubspot:contacts:read`, `hubspot:contacts:list` |

---

## Acceptance Criteria

### Functional

- [ ] `ScopeMapper` class created with static `SCOPE_TO_PERMISSIONS` dict
- [ ] Notion scope mappings implemented (7+ scopes)
- [ ] Slack scope mappings implemented (6+ scopes)
- [ ] HubSpot scope mappings implemented (6+ scopes)
- [ ] `get_permissions_for_scope()` returns correct permissions for known scopes
- [ ] `get_permissions_for_scope()` returns empty list for unknown scopes
- [ ] `get_permissions_for_scopes()` combines multiple scopes correctly
- [ ] `validate_permissions()` returns `(True, [])` for valid permissions
- [ ] `validate_permissions()` returns `(False, [invalid...])` for invalid permissions
- [ ] `get_available_permissions_by_service()` groups correctly

### Security

- [ ] No sensitive data in mappings
- [ ] Case-insensitive service_id handling
- [ ] No logging of permission details at DEBUG level

### Integration

- [ ] Module exported from `__init__.py`
- [ ] Permission strings match Gateway's `PermissionMapper` strings
- [ ] Ready for use by WS-K4 (DelegationService)
- [ ] Ready for use by WS-K5 (Available permissions endpoint)

---

## Test Cases

| Test Case | Method | Module | Expected | Notes |
|-----------|--------|--------|----------|-------|
| Single scope lookup | `test_notion_read_pages` | `test_scope_mapper.py` | Returns `["notion:pages:read", "notion:pages:search"]` | |
| Unknown scope | `test_unknown_scope_returns_empty` | `test_scope_mapper.py` | Returns `[]` | |
| Unknown service | `test_unknown_service_returns_empty` | `test_scope_mapper.py` | Returns `[]` | |
| Multiple scopes | `test_multiple_scopes_combined` | `test_scope_mapper.py` | Union of all permissions | |
| Valid permissions | `test_valid_permissions` | `test_scope_mapper.py` | `(True, [])` | |
| Invalid permission | `test_invalid_permission` | `test_scope_mapper.py` | `(False, ["notion:pages:create"])` | |
| Mixed valid/invalid | `test_mixed_valid_invalid` | `test_scope_mapper.py` | Returns only invalid ones | |
| Group by service | `test_grouped_by_service` | `test_scope_mapper.py` | Dict with service keys | |
| Supported services | `test_get_supported_services` | `test_scope_mapper.py` | `["notion", "slack", "hubspot"]` | |
| Supported scopes | `test_get_supported_scopes` | `test_scope_mapper.py` | List of known scopes | |

---

## Post-Conditions

After this task is complete:

- [ ] WS-K4 (Delegation Validation) can use `ScopeMapper.validate_permissions()`
- [ ] WS-K5 (Available Permissions Endpoint) can use `ScopeMapper.get_available_permissions_by_service()`
- [ ] Integration Validation Guide Step 9 can properly validate delegations

---

## Validation

### Unit Tests

```bash
cd /Users/imaxxs/repositories/deepsecure-mvp/deeptrail-control

# Run ScopeMapper tests
pytest tests/services/test_scope_mapper.py -v

# Run with coverage
pytest tests/services/test_scope_mapper.py -v --cov=app.services.scope_mapper
```

### Manual Verification

```python
# In Python REPL or test script
from app.services.scope_mapper import ScopeMapper

# 1. Test single scope lookup
perms = ScopeMapper.get_permissions_for_scope("notion", "read_pages")
print(f"read_pages → {perms}")
# Expected: ["notion:pages:read", "notion:pages:search"]

# 2. Test multiple scopes
perms = ScopeMapper.get_permissions_for_scopes("notion", ["read_pages", "write_pages"])
print(f"Combined → {perms}")
# Expected: {"notion:pages:read", "notion:pages:search", "notion:pages:create", "notion:pages:update"}

# 3. Test validation
is_valid, invalid = ScopeMapper.validate_permissions(
    ["notion:pages:search", "notion:pages:create"],
    [("notion", ["read_pages"])]
)
print(f"Valid: {is_valid}, Invalid: {invalid}")
# Expected: Valid: False, Invalid: ["notion:pages:create"]

# 4. Test permissions by service
result = ScopeMapper.get_available_permissions_by_service([
    ("notion", ["read_pages"]),
    ("slack", ["channels:read"])
])
print(f"By service: {result}")
# Expected: {"notion": [...], "slack": [...]}
```

### Verify Permission String Consistency

```bash
# Ensure ScopeMapper permission strings match Gateway's PermissionMapper
cd /Users/imaxxs/repositories/deepsecure-mvp

# Extract permission strings from Gateway
grep -oE '"[a-z]+:[a-z]+:[a-z]+"' deeptrail-gateway/app/mcp/permission_mapper.py | sort -u

# These should match the permissions in ScopeMapper
```

---

## References

- **Spec:** [WS-K3-spec.md](../specs/WS-K3-spec.md)
- **Architecture:** [PERMISSION_FLOW_ARCHITECTURE.md](../../architecture/PERMISSION_FLOW_ARCHITECTURE.md)
- **Gateway PermissionMapper:** `deeptrail-gateway/app/mcp/permission_mapper.py` (must use same permission strings)
- **Upstream Dependencies:** None
- **Downstream Dependents:** WS-K4 (Delegation Validation), WS-K5 (Available Permissions Endpoint)

---

## Execution

```bash
# Run in mvp-prod-control worktree:
cd /Users/imaxxs/repositories/mvp-prod-control

# Execute the task
/execute-task WS-K3 mvp-production-readiness

# After completion
/complete-task WS-K3 mvp-production-readiness
```
