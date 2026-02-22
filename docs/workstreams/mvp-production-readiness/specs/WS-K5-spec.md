# Task Specification: WS-K5 Available Permissions Endpoint

> **IMMUTABLE AFTER DESIGN APPROVAL**
>
> This specification defines what implementation MUST match exactly.
> Do not modify without updating the design doc first.
>
> **Source:** PERMISSION_FLOW_ARCHITECTURE.md, Gap #3 (No Scope Discovery UI)

---

## Overview

| Field | Value |
|-------|-------|
| **Task ID** | WS-K5 |
| **Task Name** | Available Permissions Endpoint |
| **Type** | API Endpoint |
| **Service** | deeptrail-control |
| **Complexity** | S (< 1 hr) |
| **Dependencies** | WS-K3 (ScopeMapper) |
| **Validates** | User permission discovery |

---

## Problem Statement

### Current State

Users must manually know what permission strings to delegate. There's no endpoint to discover:
1. What services they have connected
2. What scopes each service has
3. What permissions those scopes allow

```
Current: User manually types permissions

Step 9: Create Delegation
POST /api/v1/auth/delegate
{
  "agent_id": "sdr-assistant-001",
  "permissions": [
    "notion:pages:search",   ← User must know this format!
    "notion:pages:read",     ← User must know what's allowed!
    "notion:pages:create"    ← Might not be allowed by scopes!
  ]
}
```

### Target State

New endpoint returns available permissions based on connected services:

```
Step 8.5: Discover Available Permissions (NEW)

GET /api/v1/users/me/available-permissions
Response:
{
  "services": {
    "notion": {
      "connected": true,
      "scopes_granted": ["read_pages", "search_content"],
      "available_permissions": [
        "notion:pages:read",
        "notion:pages:search"
      ]
    },
    "slack": {
      "connected": true,
      "scopes_granted": ["channels:read"],
      "available_permissions": [
        "slack:channels:list"
      ]
    }
  },
  "all_permissions": [
    "notion:pages:read",
    "notion:pages:search",
    "slack:channels:list"
  ]
}
```

---

## API Contract

### Endpoint Definition

| Field | Value |
|-------|-------|
| **Method** | `GET` |
| **Path** | `/api/v1/users/me/available-permissions` |
| **Auth** | Bearer token (User JWT) |
| **Content-Type** | `application/json` |

### Request

No request body. User identified from Bearer token.

### Response Schema (Success - 200)

```json
{
  "services": {
    "<service_id>": {
      "connected": true,
      "service_name": "string",
      "scopes_granted": ["string"],
      "available_permissions": ["string"],
      "connected_at": "ISO datetime"
    }
  },
  "all_permissions": ["string"],
  "total_services": 2,
  "total_permissions": 5
}
```

### Response Schema (Pydantic)

```python
from pydantic import BaseModel, Field
from typing import Dict, List, Optional


class ServicePermissions(BaseModel):
    """Permissions available for a single connected service."""
    
    connected: bool = True
    service_name: Optional[str] = None
    scopes_granted: List[str] = Field(default_factory=list)
    available_permissions: List[str] = Field(default_factory=list)
    connected_at: Optional[str] = None


class AvailablePermissionsResponse(BaseModel):
    """Response for available permissions endpoint."""
    
    services: Dict[str, ServicePermissions] = Field(
        default_factory=dict,
        description="Map of service_id to permissions info",
    )
    all_permissions: List[str] = Field(
        default_factory=list,
        description="Flat list of all available permissions",
    )
    total_services: int = Field(
        default=0,
        description="Number of connected services",
    )
    total_permissions: int = Field(
        default=0,
        description="Total unique permissions available",
    )
```

### Error Responses

| Status | Condition | Response Body |
|--------|-----------|---------------|
| 401 | Missing/invalid token | `{"detail": "Not authenticated"}` |
| 401 | Expired token | `{"detail": "Token expired"}` |

---

## Implementation Specification

### File: `deeptrail-control/app/api/v1/endpoints/users.py`

#### Add Response Models

```python
from pydantic import BaseModel, Field
from typing import Dict, List, Optional


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

#### Add Endpoint

```python
from app.services.scope_mapper import ScopeMapper


@router.get(
    "/me/available-permissions",
    response_model=AvailablePermissionsResponse,
    summary="Get available permissions for delegation",
    description="""
    Returns all permissions the user can delegate based on their connected services.
    
    This helps users discover what permissions they can grant to agents without
    having to know the permission string format.
    
    **Use case:** Before creating a delegation, UI can show a picker of available
    permissions instead of requiring manual input.
    """,
)
def get_available_permissions(
    current_user: CurrentUserDep,
    db: Session = Depends(deps.get_db),
) -> AvailablePermissionsResponse:
    """Get all permissions available for delegation based on connected services.
    
    Returns:
        AvailablePermissionsResponse with services map and flat permission list
    """
    # Get all active connected services for user
    connections = (
        db.query(ConnectedService)
        .filter(
            ConnectedService.user_id == current_user,
            ConnectedService.disconnected_at.is_(None),
        )
        .all()
    )
    
    services: Dict[str, ServicePermissions] = {}
    all_permissions: set = set()
    
    for conn in connections:
        # Get permissions for this service's scopes
        scopes = conn.scopes_granted or []
        perms = ScopeMapper.get_permissions_for_scopes(conn.service_id, scopes)
        
        services[conn.service_id] = ServicePermissions(
            connected=True,
            service_name=conn.service_name,
            scopes_granted=scopes,
            available_permissions=sorted(list(perms)),
            connected_at=conn.connected_at.isoformat() if conn.connected_at else None,
        )
        
        all_permissions.update(perms)
    
    return AvailablePermissionsResponse(
        services=services,
        all_permissions=sorted(list(all_permissions)),
        total_services=len(services),
        total_permissions=len(all_permissions),
    )
```

---

## Example Responses

### User with Notion and Slack Connected

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
      "scopes_granted": ["channels:read", "chat:write"],
      "available_permissions": [
        "slack:channels:list",
        "slack:messages:send"
      ],
      "connected_at": "2026-02-22T05:00:00.000000+00:00"
    }
  },
  "all_permissions": [
    "notion:pages:read",
    "notion:pages:search",
    "slack:channels:list",
    "slack:messages:send"
  ],
  "total_services": 2,
  "total_permissions": 4
}
```

### User with No Connected Services

```json
{
  "services": {},
  "all_permissions": [],
  "total_services": 0,
  "total_permissions": 0
}
```

### User with Full Notion Access

```json
{
  "services": {
    "notion": {
      "connected": true,
      "service_name": "Notion",
      "scopes_granted": ["read_content", "update_content", "insert_content"],
      "available_permissions": [
        "notion:databases:list",
        "notion:databases:query",
        "notion:pages:create",
        "notion:pages:read",
        "notion:pages:search",
        "notion:pages:update"
      ],
      "connected_at": "2026-02-22T04:42:38.796552+00:00"
    }
  },
  "all_permissions": [
    "notion:databases:list",
    "notion:databases:query",
    "notion:pages:create",
    "notion:pages:read",
    "notion:pages:search",
    "notion:pages:update"
  ],
  "total_services": 1,
  "total_permissions": 6
}
```

---

## Integration with INTEGRATION_VALIDATION_GUIDE.md

### New Test Scenario (Insert After Step 8)

```markdown
## 8.5 Test Scenario: Available Permissions Discovery (NEW)

### Purpose

User discovers what permissions they can delegate before creating delegation.

### API Reference

| Field | Value |
|-------|-------|
| **Endpoint** | `GET /api/v1/users/me/available-permissions` |
| **URL** | `http://localhost:8000/api/v1/users/me/available-permissions` |
| **Auth** | `Bearer $USER_TOKEN` |

### Command

```bash
echo "=== Discover Available Permissions ==="
curl -s -X GET http://localhost:8000/api/v1/users/me/available-permissions \
  -H "Authorization: Bearer $USER_TOKEN" | jq .
```

### Expected Response

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
    }
  },
  "all_permissions": [
    "notion:pages:read",
    "notion:pages:search"
  ],
  "total_services": 1,
  "total_permissions": 2
}
```

### Verification

```bash
# Count available permissions
PERM_COUNT=$(curl -s -X GET http://localhost:8000/api/v1/users/me/available-permissions \
  -H "Authorization: Bearer $USER_TOKEN" | jq '.total_permissions')
echo "✅ User has $PERM_COUNT permissions available for delegation"
```

### Notes

- Permissions shown are based on connected service scopes
- Use these permissions in the delegation request (Step 9)
- Attempting to delegate permissions NOT in this list will fail
```

---

## Test Specification

### Test File: `deeptrail-control/tests/api/test_available_permissions.py`

```python
import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timezone

from app.main import app
from app.models.connected_service import ConnectedService

client = TestClient(app)


class TestAvailablePermissionsEndpoint:
    """Test GET /api/v1/users/me/available-permissions."""
    
    @pytest.fixture
    def connected_notion(self, db_session):
        """Notion connected with read scopes."""
        conn = ConnectedService(
            user_id="sarah@acme.com",
            service_id="notion",
            service_name="Notion",
            scopes_granted=["read_pages", "search_content"],
            oauth_token_ref="vault://test-notion",
            connected_at=datetime.now(timezone.utc),
        )
        db_session.add(conn)
        db_session.commit()
        return conn
    
    @pytest.fixture
    def connected_slack(self, db_session):
        """Slack connected with channel scopes."""
        conn = ConnectedService(
            user_id="sarah@acme.com",
            service_id="slack",
            service_name="Slack",
            scopes_granted=["channels:read"],
            oauth_token_ref="vault://test-slack",
            connected_at=datetime.now(timezone.utc),
        )
        db_session.add(conn)
        db_session.commit()
        return conn
    
    def test_returns_permissions_for_connected_service(
        self, connected_notion, user_token
    ):
        """Should return permissions based on connected scopes."""
        response = client.get(
            "/api/v1/users/me/available-permissions",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "notion" in data["services"]
        assert data["services"]["notion"]["connected"] is True
        assert "notion:pages:read" in data["services"]["notion"]["available_permissions"]
        assert "notion:pages:search" in data["services"]["notion"]["available_permissions"]
    
    def test_returns_multiple_services(
        self, connected_notion, connected_slack, user_token
    ):
        """Should return permissions for all connected services."""
        response = client.get(
            "/api/v1/users/me/available-permissions",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["total_services"] == 2
        assert "notion" in data["services"]
        assert "slack" in data["services"]
    
    def test_all_permissions_is_flat_list(
        self, connected_notion, connected_slack, user_token
    ):
        """Should return flat list of all permissions."""
        response = client.get(
            "/api/v1/users/me/available-permissions",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        
        data = response.json()
        
        assert "notion:pages:read" in data["all_permissions"]
        assert "slack:channels:list" in data["all_permissions"]
        assert data["total_permissions"] == len(data["all_permissions"])
    
    def test_empty_when_no_services(self, user_token):
        """Should return empty when no services connected."""
        response = client.get(
            "/api/v1/users/me/available-permissions",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["services"] == {}
        assert data["all_permissions"] == []
        assert data["total_services"] == 0
    
    def test_excludes_disconnected_services(self, db_session, user_token):
        """Should not include disconnected services."""
        # Create and disconnect a service
        conn = ConnectedService(
            user_id="sarah@acme.com",
            service_id="hubspot",
            scopes_granted=["read_contacts"],
            oauth_token_ref="vault://test",
            disconnected_at=datetime.now(timezone.utc),
        )
        db_session.add(conn)
        db_session.commit()
        
        response = client.get(
            "/api/v1/users/me/available-permissions",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        
        data = response.json()
        assert "hubspot" not in data["services"]
    
    def test_unauthorized_without_token(self):
        """Should return 401 without token."""
        response = client.get("/api/v1/users/me/available-permissions")
        assert response.status_code in [401, 422]  # 422 if header required
    
    def test_permissions_are_sorted(self, connected_notion, user_token):
        """Should return sorted permission lists."""
        response = client.get(
            "/api/v1/users/me/available-permissions",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        
        data = response.json()
        perms = data["all_permissions"]
        
        assert perms == sorted(perms)
```

---

## Acceptance Criteria

- [ ] Endpoint `GET /api/v1/users/me/available-permissions` exists
- [ ] Returns permissions based on connected service scopes
- [ ] Uses `ScopeMapper` to derive permissions from scopes
- [ ] Response includes per-service breakdown and flat list
- [ ] Excludes disconnected services
- [ ] Permissions are sorted alphabetically
- [ ] Returns empty response for users with no connections (not error)
- [ ] Unit tests pass

---

## File Locations

| Artifact | Path |
|----------|------|
| Endpoint | `deeptrail-control/app/api/v1/endpoints/users.py` |
| Tests | `deeptrail-control/tests/api/test_available_permissions.py` |

---

## Test Endpoint Mapping

| Test Case | Method | Endpoint | Expected Status |
|-----------|--------|----------|-----------------|
| With connected services | GET | `/api/v1/users/me/available-permissions` | 200 |
| No connected services | GET | `/api/v1/users/me/available-permissions` | 200 (empty) |
| No auth token | GET | `/api/v1/users/me/available-permissions` | 401 |

---

## References

- **Architecture Doc:** `docs/architecture/PERMISSION_FLOW_ARCHITECTURE.md`
- **Upstream Dependencies:** WS-K3 (ScopeMapper)
- **Related Specs:** WS-K4 (Delegation Validation uses same data)
- **Existing File:** `deeptrail-control/app/api/v1/endpoints/users.py`
