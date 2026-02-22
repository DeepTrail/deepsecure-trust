# Task Specification: WS-K3 Scope-to-Permission Mapper

> **IMMUTABLE AFTER DESIGN APPROVAL**
>
> This specification defines what implementation MUST match exactly.
> Do not modify without updating the design doc first.
>
> **Source:** PERMISSION_FLOW_ARCHITECTURE.md, Gap #1 (No Scope→Permission Mapping)

---

## Overview

| Field | Value |
|-------|-------|
| **Task ID** | WS-K3 |
| **Task Name** | Scope-to-Permission Mapper |
| **Type** | Service Module |
| **Service** | deeptrail-control |
| **Complexity** | M (1-3 hrs) |
| **Dependencies** | None (standalone) |
| **Validates** | Permission flow integrity |

---

## Problem Statement

### Current Architecture

```
Step 6: Connect Service              Step 9: Delegation              Gateway
┌──────────────────────────┐        ┌──────────────────────────┐    ┌──────────────────────┐
│ scope: "read_pages"      │        │ permissions: [           │    │ Tool → Permission    │
│        "search_content"  │   ❓   │   "notion:pages:search", │    │ notion.search_pages  │
│        "write_pages"     │   ──►  │   "notion:pages:create"  │    │   → notion:pages:search│
└──────────────────────────┘        │ ]                        │    └──────────────────────┘
     No mapping!                    └──────────────────────────┘
```

**Issues:**
1. User-declared scopes (e.g., `"read_pages"`) don't map to permission strings (e.g., `"notion:pages:read"`)
2. Delegation validation can't check if requested permissions are allowed by connected scopes
3. User must manually know what permissions to delegate

### Target Architecture

```
Step 6: Connect Service              ScopeMapper (NEW)            Step 9: Delegation
┌──────────────────────────┐        ┌──────────────────────────┐  ┌──────────────────────────┐
│ scope: "read_pages"      │        │ "read_pages" → [         │  │ Validate:                │
│        "search_content"  │   ──►  │   "notion:pages:read",   │  │ notion:pages:search ∈    │
│                          │        │   "notion:pages:search"  │  │   allowed? ✓             │
└──────────────────────────┘        │ ]                        │  └──────────────────────────┘
                                    └──────────────────────────┘
```

---

## Data Model Specification

### Service Module: `ScopeMapper`

| Field | Value |
|-------|-------|
| **Module** | `deeptrail-control/app/services/scope_mapper.py` |
| **Type** | Class with static mappings |
| **Purpose** | Map OAuth scopes to DeepSecure permission strings |

### Scope Mapping Tables

#### Notion Scopes

| Scope String | Permission Strings | Notes |
|--------------|-------------------|-------|
| `read_content` | `notion:pages:read`, `notion:pages:search`, `notion:databases:list`, `notion:databases:query` | Notion API "Read content" capability |
| `update_content` | `notion:pages:update` | Notion API "Update content" capability |
| `insert_content` | `notion:pages:create` | Notion API "Insert content" capability |
| `read_pages` | `notion:pages:read`, `notion:pages:search` | User-friendly alias |
| `search_content` | `notion:pages:search` | User-friendly alias |
| `write_pages` | `notion:pages:create`, `notion:pages:update` | User-friendly alias |
| `read_databases` | `notion:databases:list`, `notion:databases:query` | User-friendly alias |

#### Slack Scopes

| Scope String | Permission Strings | Notes |
|--------------|-------------------|-------|
| `channels:read` | `slack:channels:list` | List channels |
| `channels:history` | `slack:messages:search` | Read channel messages |
| `chat:write` | `slack:messages:send` | Send messages |
| `users:read` | `slack:users:list` | List users |
| `reactions:write` | `slack:reactions:write` | Add reactions |
| `search:read` | `slack:messages:search` | Search messages |

#### HubSpot Scopes

| Scope String | Permission Strings | Notes |
|--------------|-------------------|-------|
| `crm.objects.contacts.read` | `hubspot:contacts:read`, `hubspot:contacts:list` | Read contacts |
| `crm.objects.contacts.write` | `hubspot:contacts:create`, `hubspot:contacts:update` | Write contacts |
| `crm.objects.deals.read` | `hubspot:deals:list` | Read deals |
| `crm.objects.deals.write` | `hubspot:deals:create`, `hubspot:deals:update` | Write deals |

---

## Interface Contract

### Class: `ScopeMapper`

```python
# deeptrail-control/app/services/scope_mapper.py

from typing import Dict, List, Set

class ScopeMapper:
    """Maps OAuth scopes to DeepSecure permission strings.
    
    Used by:
    - DelegationService: Validate delegated permissions against connected scopes
    - Available Permissions endpoint: Show what user can delegate
    
    Design Principle:
    - Scopes are what the user grants during OAuth/service connection
    - Permissions are fine-grained actions on resources
    - Multiple scopes can grant the same permission
    - One scope can grant multiple permissions
    """
    
    # Static mapping: service_id → {scope → [permissions]}
    SCOPE_TO_PERMISSIONS: Dict[str, Dict[str, List[str]]] = {
        "notion": {
            # Notion API capabilities (from integration settings)
            "read_content": [
                "notion:pages:read",
                "notion:pages:search",
                "notion:databases:list",
                "notion:databases:query",
            ],
            "update_content": ["notion:pages:update"],
            "insert_content": ["notion:pages:create"],
            # User-friendly aliases
            "read_pages": ["notion:pages:read", "notion:pages:search"],
            "search_content": ["notion:pages:search"],
            "write_pages": ["notion:pages:create", "notion:pages:update"],
            "read_databases": ["notion:databases:list", "notion:databases:query"],
        },
        "slack": {
            "channels:read": ["slack:channels:list"],
            "channels:history": ["slack:messages:search"],
            "chat:write": ["slack:messages:send"],
            "users:read": ["slack:users:list"],
            "reactions:write": ["slack:reactions:write"],
            "search:read": ["slack:messages:search"],
            # User-friendly aliases
            "read_messages": ["slack:messages:search"],
            "send_messages": ["slack:messages:send"],
            "list_channels": ["slack:channels:list"],
        },
        "hubspot": {
            "crm.objects.contacts.read": ["hubspot:contacts:read", "hubspot:contacts:list"],
            "crm.objects.contacts.write": ["hubspot:contacts:create", "hubspot:contacts:update"],
            "crm.objects.deals.read": ["hubspot:deals:list"],
            "crm.objects.deals.write": ["hubspot:deals:create", "hubspot:deals:update"],
            # User-friendly aliases
            "read_contacts": ["hubspot:contacts:read", "hubspot:contacts:list"],
            "write_contacts": ["hubspot:contacts:create", "hubspot:contacts:update"],
            "read_deals": ["hubspot:deals:list"],
            "write_deals": ["hubspot:deals:create", "hubspot:deals:update"],
        },
    }
    
    @classmethod
    def get_permissions_for_scope(
        cls,
        service_id: str,
        scope: str,
    ) -> List[str]:
        """Get permissions granted by a single scope.
        
        Args:
            service_id: Service identifier (e.g., "notion")
            scope: Scope string (e.g., "read_pages")
            
        Returns:
            List of permission strings, empty if scope unknown
        """
        ...
    
    @classmethod
    def get_permissions_for_scopes(
        cls,
        service_id: str,
        scopes: List[str],
    ) -> Set[str]:
        """Get all permissions granted by multiple scopes.
        
        Args:
            service_id: Service identifier
            scopes: List of scope strings
            
        Returns:
            Set of unique permission strings
        """
        ...
    
    @classmethod
    def get_all_allowed_permissions(
        cls,
        connected_services: List[tuple[str, List[str]]],
    ) -> Set[str]:
        """Get all permissions allowed across multiple connected services.
        
        Args:
            connected_services: List of (service_id, scopes) tuples
            
        Returns:
            Set of all allowed permission strings
            
        Example:
            >>> connected = [
            ...     ("notion", ["read_pages", "search_content"]),
            ...     ("slack", ["channels:read"]),
            ... ]
            >>> ScopeMapper.get_all_allowed_permissions(connected)
            {"notion:pages:read", "notion:pages:search", "slack:channels:list"}
        """
        ...
    
    @classmethod
    def validate_permissions(
        cls,
        requested_permissions: List[str],
        connected_services: List[tuple[str, List[str]]],
    ) -> tuple[bool, List[str]]:
        """Validate that requested permissions are allowed by connected scopes.
        
        Args:
            requested_permissions: List of permissions to validate
            connected_services: List of (service_id, scopes) tuples
            
        Returns:
            Tuple of (is_valid, list of invalid permissions)
            
        Example:
            >>> perms = ["notion:pages:search", "notion:pages:create"]
            >>> connected = [("notion", ["read_pages"])]  # No write!
            >>> ScopeMapper.validate_permissions(perms, connected)
            (False, ["notion:pages:create"])
        """
        ...
    
    @classmethod
    def get_available_permissions_by_service(
        cls,
        connected_services: List[tuple[str, List[str]]],
    ) -> Dict[str, List[str]]:
        """Get available permissions grouped by service.
        
        Useful for UI display.
        
        Args:
            connected_services: List of (service_id, scopes) tuples
            
        Returns:
            Dict mapping service_id to list of available permissions
            
        Example:
            >>> connected = [("notion", ["read_pages"])]
            >>> ScopeMapper.get_available_permissions_by_service(connected)
            {"notion": ["notion:pages:read", "notion:pages:search"]}
        """
        ...
    
    @classmethod
    def get_supported_services(cls) -> List[str]:
        """Get list of services with scope mappings."""
        return list(cls.SCOPE_TO_PERMISSIONS.keys())
    
    @classmethod
    def get_supported_scopes(cls, service_id: str) -> List[str]:
        """Get list of known scopes for a service."""
        return list(cls.SCOPE_TO_PERMISSIONS.get(service_id, {}).keys())
```

---

## Implementation Details

### File: `deeptrail-control/app/services/scope_mapper.py`

```python
"""Scope to Permission Mapper for DeepSecure.

Maps OAuth scopes (what user grants during service connection) to
DeepSecure permission strings (what gets delegated to agents).

This enables:
1. Validation that delegated permissions are subset of connected scopes
2. UI display of what permissions user can delegate
3. Automatic permission suggestions based on connected services

Usage:
    from app.services.scope_mapper import ScopeMapper
    
    # Get permissions for a scope
    perms = ScopeMapper.get_permissions_for_scope("notion", "read_pages")
    # Returns: ["notion:pages:read", "notion:pages:search"]
    
    # Validate permissions
    is_valid, invalid = ScopeMapper.validate_permissions(
        ["notion:pages:search", "notion:pages:create"],
        [("notion", ["read_pages"])],
    )
    # Returns: (False, ["notion:pages:create"])
"""

import logging
from typing import Dict, List, Set, Tuple

logger = logging.getLogger(__name__)


class ScopeMapper:
    """Maps OAuth scopes to DeepSecure permission strings."""
    
    SCOPE_TO_PERMISSIONS: Dict[str, Dict[str, List[str]]] = {
        "notion": {
            "read_content": [
                "notion:pages:read",
                "notion:pages:search",
                "notion:databases:list",
                "notion:databases:query",
            ],
            "update_content": ["notion:pages:update"],
            "insert_content": ["notion:pages:create"],
            "read_pages": ["notion:pages:read", "notion:pages:search"],
            "search_content": ["notion:pages:search"],
            "write_pages": ["notion:pages:create", "notion:pages:update"],
            "read_databases": ["notion:databases:list", "notion:databases:query"],
        },
        "slack": {
            "channels:read": ["slack:channels:list"],
            "channels:history": ["slack:messages:search"],
            "chat:write": ["slack:messages:send"],
            "users:read": ["slack:users:list"],
            "reactions:write": ["slack:reactions:write"],
            "search:read": ["slack:messages:search"],
            "read_messages": ["slack:messages:search"],
            "send_messages": ["slack:messages:send"],
            "list_channels": ["slack:channels:list"],
        },
        "hubspot": {
            "crm.objects.contacts.read": ["hubspot:contacts:read", "hubspot:contacts:list"],
            "crm.objects.contacts.write": ["hubspot:contacts:create", "hubspot:contacts:update"],
            "crm.objects.deals.read": ["hubspot:deals:list"],
            "crm.objects.deals.write": ["hubspot:deals:create", "hubspot:deals:update"],
            "read_contacts": ["hubspot:contacts:read", "hubspot:contacts:list"],
            "write_contacts": ["hubspot:contacts:create", "hubspot:contacts:update"],
            "read_deals": ["hubspot:deals:list"],
            "write_deals": ["hubspot:deals:create", "hubspot:deals:update"],
        },
    }
    
    @classmethod
    def get_permissions_for_scope(
        cls,
        service_id: str,
        scope: str,
    ) -> List[str]:
        service_map = cls.SCOPE_TO_PERMISSIONS.get(service_id.lower(), {})
        return service_map.get(scope, [])
    
    @classmethod
    def get_permissions_for_scopes(
        cls,
        service_id: str,
        scopes: List[str],
    ) -> Set[str]:
        permissions: Set[str] = set()
        for scope in scopes:
            permissions.update(cls.get_permissions_for_scope(service_id, scope))
        return permissions
    
    @classmethod
    def get_all_allowed_permissions(
        cls,
        connected_services: List[Tuple[str, List[str]]],
    ) -> Set[str]:
        allowed: Set[str] = set()
        for service_id, scopes in connected_services:
            allowed.update(cls.get_permissions_for_scopes(service_id, scopes))
        return allowed
    
    @classmethod
    def validate_permissions(
        cls,
        requested_permissions: List[str],
        connected_services: List[Tuple[str, List[str]]],
    ) -> Tuple[bool, List[str]]:
        allowed = cls.get_all_allowed_permissions(connected_services)
        invalid = [p for p in requested_permissions if p not in allowed]
        return (len(invalid) == 0, invalid)
    
    @classmethod
    def get_available_permissions_by_service(
        cls,
        connected_services: List[Tuple[str, List[str]]],
    ) -> Dict[str, List[str]]:
        result: Dict[str, List[str]] = {}
        for service_id, scopes in connected_services:
            perms = cls.get_permissions_for_scopes(service_id, scopes)
            if perms:
                result[service_id] = sorted(list(perms))
        return result
    
    @classmethod
    def get_supported_services(cls) -> List[str]:
        return list(cls.SCOPE_TO_PERMISSIONS.keys())
    
    @classmethod
    def get_supported_scopes(cls, service_id: str) -> List[str]:
        return list(cls.SCOPE_TO_PERMISSIONS.get(service_id.lower(), {}).keys())
```

---

## Integration Points

### Export from `__init__.py`

```python
# deeptrail-control/app/services/__init__.py

from .scope_mapper import ScopeMapper  # noqa
```

---

## Test Specification

### Test File: `deeptrail-control/tests/services/test_scope_mapper.py`

```python
import pytest
from app.services.scope_mapper import ScopeMapper


class TestGetPermissionsForScope:
    """Test single scope → permissions."""
    
    def test_notion_read_pages(self):
        perms = ScopeMapper.get_permissions_for_scope("notion", "read_pages")
        assert "notion:pages:read" in perms
        assert "notion:pages:search" in perms
    
    def test_unknown_scope_returns_empty(self):
        perms = ScopeMapper.get_permissions_for_scope("notion", "unknown_scope")
        assert perms == []
    
    def test_unknown_service_returns_empty(self):
        perms = ScopeMapper.get_permissions_for_scope("unknown", "read_pages")
        assert perms == []


class TestGetPermissionsForScopes:
    """Test multiple scopes → permissions."""
    
    def test_multiple_scopes_combined(self):
        perms = ScopeMapper.get_permissions_for_scopes(
            "notion", ["read_pages", "write_pages"]
        )
        assert "notion:pages:read" in perms
        assert "notion:pages:search" in perms
        assert "notion:pages:create" in perms
        assert "notion:pages:update" in perms


class TestValidatePermissions:
    """Test permission validation."""
    
    def test_valid_permissions(self):
        is_valid, invalid = ScopeMapper.validate_permissions(
            ["notion:pages:search"],
            [("notion", ["read_pages"])],
        )
        assert is_valid is True
        assert invalid == []
    
    def test_invalid_permission(self):
        is_valid, invalid = ScopeMapper.validate_permissions(
            ["notion:pages:create"],  # Requires write scope
            [("notion", ["read_pages"])],  # Only read scope
        )
        assert is_valid is False
        assert "notion:pages:create" in invalid
    
    def test_mixed_valid_invalid(self):
        is_valid, invalid = ScopeMapper.validate_permissions(
            ["notion:pages:search", "notion:pages:create"],
            [("notion", ["read_pages"])],
        )
        assert is_valid is False
        assert invalid == ["notion:pages:create"]


class TestGetAvailablePermissions:
    """Test available permissions helper."""
    
    def test_grouped_by_service(self):
        result = ScopeMapper.get_available_permissions_by_service([
            ("notion", ["read_pages"]),
            ("slack", ["channels:read"]),
        ])
        assert "notion" in result
        assert "slack" in result
        assert "notion:pages:read" in result["notion"]
        assert "slack:channels:list" in result["slack"]
```

---

## Acceptance Criteria

- [ ] `ScopeMapper` class created with static mappings
- [ ] All three services (Notion, Slack, HubSpot) have scope mappings
- [ ] `get_permissions_for_scope()` returns correct permissions
- [ ] `validate_permissions()` correctly identifies invalid permissions
- [ ] Unit tests pass
- [ ] Module exported from `__init__.py`

---

## File Locations

| Artifact | Path |
|----------|------|
| Implementation | `deeptrail-control/app/services/scope_mapper.py` |
| Tests | `deeptrail-control/tests/services/test_scope_mapper.py` |
| Export | `deeptrail-control/app/services/__init__.py` |

---

## References

- **Architecture Doc:** `docs/architecture/PERMISSION_FLOW_ARCHITECTURE.md`
- **Related Specs:** WS-K4 (uses this for validation), WS-K5 (uses this for endpoint)
- **Gateway Permission Mapper:** `deeptrail-gateway/app/mcp/permission_mapper.py` (uses same permission strings)
