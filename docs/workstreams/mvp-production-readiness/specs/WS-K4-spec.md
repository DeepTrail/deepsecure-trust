# Task Specification: WS-K4 Delegation Permission Validation

> **IMMUTABLE AFTER DESIGN APPROVAL**
>
> This specification defines what implementation MUST match exactly.
> Do not modify without updating the design doc first.
>
> **Source:** PERMISSION_FLOW_ARCHITECTURE.md, Gap #2 (No Delegation Validation)

---

## Overview

| Field | Value |
|-------|-------|
| **Task ID** | WS-K4 |
| **Task Name** | Delegation Permission Validation |
| **Type** | Service Enhancement |
| **Service** | deeptrail-control |
| **Complexity** | M (1-3 hrs) |
| **Dependencies** | WS-K3 (ScopeMapper) |
| **Validates** | Monotonic attenuation principle |

---

## Problem Statement

### Current Architecture

```python
# deeptrail-control/app/services/delegation_service.py (lines 133-184)

def _validate_permissions_subset(
    self,
    delegator: str,
    requested_permissions: List[str],
) -> tuple[bool, Optional[str]]:
    # Get all user's active connected services
    connections = self._db.query(ConnectedService).filter(...)
    
    # Build map of connected services and their scopes
    connected_services = {}
    for conn in connections:
        connected_services[conn.service_id] = set(conn.scopes_granted or [])
    
    # Validate each requested permission
    for perm in requested_permissions:
        parts = perm.split(":")
        service = parts[0]
        
        # ⚠️ CURRENT: Only checks if SERVICE is connected!
        if service not in connected_services:
            return False, f"User not connected to service: {service}"
        
        # ⚠️ MISSING: Should check if specific permission is allowed by scopes!
        # e.g., "notion:pages:create" requires "write_pages" scope
```

**Issue:** User can delegate `notion:pages:create` even if they only connected with `read_pages` scope. The agent would only fail when Notion API rejects the call.

### Target Architecture

```python
def _validate_permissions_subset(
    self,
    delegator: str,
    requested_permissions: List[str],
) -> tuple[bool, Optional[str], List[str]]:
    # Get connected services with scopes
    connections = self._db.query(ConnectedService).filter(...)
    
    connected_services = [
        (conn.service_id, conn.scopes_granted or [])
        for conn in connections
    ]
    
    # ✅ NEW: Use ScopeMapper to validate permissions
    is_valid, invalid_perms = ScopeMapper.validate_permissions(
        requested_permissions,
        connected_services,
    )
    
    if not is_valid:
        return False, f"Permissions not allowed by connected scopes: {invalid_perms}", invalid_perms
    
    return True, None, []
```

---

## API Contract Changes

### Delegation Endpoint Enhancement

| Field | Current | New |
|-------|---------|-----|
| **Endpoint** | `POST /api/v1/auth/delegate` | Same |
| **Validation** | Service-level only | Permission-level |
| **Error Response** | `"User not connected to service: {service}"` | Detailed with allowed/invalid |

### New Error Response Schema

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

### HTTP Status: 400 Bad Request

The delegation endpoint should return 400 (not 403) for invalid permissions because:
- 403 means "you're not authorized to do this"
- 400 means "your request is invalid" (which is more accurate - the user CAN delegate, but they requested invalid permissions)

---

## Implementation Specification

### File: `deeptrail-control/app/services/delegation_service.py`

#### Changes to `_validate_permissions_subset`

```python
from app.services.scope_mapper import ScopeMapper

def _validate_permissions_subset(
    self,
    delegator: str,
    requested_permissions: List[str],
) -> tuple[bool, Optional[str], List[str], List[str]]:
    """Validate that requested permissions are subset of user's connected scopes.

    Enforces the Monotonic Attenuation principle: agent permissions must
    be a subset of the delegator's connected service scopes.

    Args:
        delegator: User ID (e.g., "sarah@acme.com")
        requested_permissions: List of permissions to delegate

    Returns:
        Tuple of (is_valid, reason_if_invalid, invalid_permissions, allowed_permissions)
    """
    # Get all user's active connected services
    connections = (
        self._db.query(ConnectedService)
        .filter(
            ConnectedService.user_id == delegator,
            ConnectedService.disconnected_at.is_(None),
        )
        .all()
    )

    if not connections:
        return False, "User has no connected services", [], []

    # Build list of (service_id, scopes) for ScopeMapper
    connected_services = [
        (conn.service_id, conn.scopes_granted or [])
        for conn in connections
    ]

    # Validate each requested permission using ScopeMapper
    is_valid, invalid_perms = ScopeMapper.validate_permissions(
        requested_permissions,
        connected_services,
    )

    if not is_valid:
        # Get allowed permissions for error message
        allowed = ScopeMapper.get_all_allowed_permissions(connected_services)
        return (
            False,
            f"Permissions not allowed by connected scopes: {invalid_perms}",
            invalid_perms,
            list(allowed),
        )

    return True, None, [], []
```

#### Changes to `create_delegation`

```python
def create_delegation(
    self,
    delegator: str,
    agent_id: str,
    permissions: List[str],
    constraints: Optional[Dict[str, Any]] = None,
    expires_in_days: int = DEFAULT_EXPIRY_DAYS,
    delegator_idp: Optional[str] = None,
    organization_id: Optional[str] = None,
) -> DelegationToken:
    """Create a new delegation from user to agent."""
    
    # Validate permissions are subset of user's connected scopes
    is_valid, reason, invalid_perms, allowed_perms = self._validate_permissions_subset(
        delegator, permissions
    )
    
    if not is_valid:
        logger.warning(
            "Permission validation failed: delegator=%s reason=%s invalid=%s",
            delegator,
            reason,
            invalid_perms,
        )
        raise PermissionValidationError(
            message=reason,
            invalid_permissions=invalid_perms,
            allowed_permissions=allowed_perms,
        )
    
    # ... rest of method unchanged
```

### File: `deeptrail-control/app/services/delegation_service.py`

#### Enhanced Exception Class

```python
class PermissionValidationError(DelegationError):
    """Raised when requested permissions fail validation."""
    
    def __init__(
        self,
        message: str,
        invalid_permissions: List[str] = None,
        allowed_permissions: List[str] = None,
    ):
        super().__init__(message)
        self.message = message
        self.invalid_permissions = invalid_permissions or []
        self.allowed_permissions = allowed_permissions or []
```

### File: `deeptrail-control/app/api/v1/endpoints/delegation.py`

#### Enhanced Error Handling

```python
from app.services.delegation_service import (
    DelegationService,
    PermissionValidationError,
)

@router.post("/delegate", response_model=UserDelegationResponse)
def create_user_delegation(
    request: UserDelegationRequest,
    authorization: str = Header(...),
    db: Session = Depends(deps.get_db),
):
    """Create a delegation from a user to an agent."""
    current_user = get_current_user_from_token(authorization)
    
    try:
        # Use DelegationService for proper validation
        service = DelegationService(db)
        
        ttl_hours = 8
        if request.constraints and "expires_in_hours" in request.constraints:
            ttl_hours = request.constraints["expires_in_hours"]
        
        delegation = service.create_delegation(
            delegator=current_user,
            agent_id=request.agent_id,
            permissions=request.permissions,
            constraints=request.constraints,
            expires_in_days=ttl_hours / 24,  # Convert hours to days
        )
        
        # Generate delegation token using macaroon service
        delegation_token = macaroon_service.mint_delegation_macaroon(
            target_agent_id=request.agent_id,
            resource="*",
            permissions=request.permissions,
            ttl_seconds=ttl_hours * 3600,
        )
        
        db.commit()
        
        return UserDelegationResponse(
            delegation_token=delegation_token,
            delegation_id=delegation.id,
            permissions=request.permissions,
            expires_in=ttl_hours * 3600,
        )
        
    except PermissionValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "permission_validation_failed",
                "message": e.message,
                "invalid_permissions": e.invalid_permissions,
                "allowed_permissions": e.allowed_permissions,
                "hint": "Connect service with additional scopes or remove invalid permissions",
            },
        )
```

---

## Backward Compatibility

### MVP Mode (In-Memory Storage)

The current endpoint uses in-memory storage (`_delegations` dict). To maintain backward compatibility during transition:

```python
@router.post("/delegate", response_model=UserDelegationResponse)
def create_user_delegation(
    request: UserDelegationRequest,
    authorization: str = Header(...),
    db: Session = Depends(deps.get_db),
):
    current_user = get_current_user_from_token(authorization)
    
    # Get connected services for validation
    connections = (
        db.query(ConnectedService)
        .filter(
            ConnectedService.user_id == current_user,
            ConnectedService.disconnected_at.is_(None),
        )
        .all()
    )
    
    if not connections:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "no_connected_services",
                "message": "User has no connected services",
            },
        )
    
    # Validate permissions using ScopeMapper
    connected_services = [
        (conn.service_id, conn.scopes_granted or [])
        for conn in connections
    ]
    
    is_valid, invalid_perms = ScopeMapper.validate_permissions(
        request.permissions,
        connected_services,
    )
    
    if not is_valid:
        allowed = ScopeMapper.get_all_allowed_permissions(connected_services)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "permission_validation_failed",
                "message": "Requested permissions not allowed by connected scopes",
                "invalid_permissions": invalid_perms,
                "allowed_permissions": list(allowed),
                "hint": "Connect service with additional scopes or remove invalid permissions",
            },
        )
    
    # Continue with existing in-memory storage...
    delegation_id = f"del-{uuid.uuid4()}"
    
    delegation_token = macaroon_service.mint_delegation_macaroon(
        target_agent_id=request.agent_id,
        resource="*",
        permissions=request.permissions,
        ttl_seconds=ttl_seconds,
    )
    
    _delegations[delegation_id] = {
        "id": delegation_id,
        "user_id": current_user,
        "agent_id": request.agent_id,
        "permissions": request.permissions,
        "token": delegation_token,
        "constraints": request.constraints,
    }
    
    return UserDelegationResponse(...)
```

---

## Test Specification

### Test File: `deeptrail-control/tests/api/test_delegation_validation.py`

```python
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.models.connected_service import ConnectedService

client = TestClient(app)


class TestDelegationPermissionValidation:
    """Test permission validation in delegation endpoint."""
    
    @pytest.fixture
    def connected_notion_read_only(self, db_session):
        """User with read-only Notion connection."""
        conn = ConnectedService(
            user_id="sarah@acme.com",
            service_id="notion",
            scopes_granted=["read_pages", "search_content"],
            oauth_token_ref="vault://test",
        )
        db_session.add(conn)
        db_session.commit()
        return conn
    
    def test_valid_permissions_succeed(self, connected_notion_read_only, user_token):
        """Should succeed when permissions match scopes."""
        response = client.post(
            "/api/v1/auth/delegate",
            headers={"Authorization": f"Bearer {user_token}"},
            json={
                "agent_id": "test-agent",
                "permissions": ["notion:pages:search", "notion:pages:read"],
            },
        )
        assert response.status_code == 200
    
    def test_invalid_permissions_rejected(self, connected_notion_read_only, user_token):
        """Should reject permissions not in connected scopes."""
        response = client.post(
            "/api/v1/auth/delegate",
            headers={"Authorization": f"Bearer {user_token}"},
            json={
                "agent_id": "test-agent",
                "permissions": ["notion:pages:create"],  # Requires write scope!
            },
        )
        assert response.status_code == 400
        data = response.json()
        assert data["detail"]["error"] == "permission_validation_failed"
        assert "notion:pages:create" in data["detail"]["invalid_permissions"]
        assert "notion:pages:read" in data["detail"]["allowed_permissions"]
    
    def test_mixed_permissions_shows_invalid_only(self, connected_notion_read_only, user_token):
        """Should list only invalid permissions in error."""
        response = client.post(
            "/api/v1/auth/delegate",
            headers={"Authorization": f"Bearer {user_token}"},
            json={
                "agent_id": "test-agent",
                "permissions": [
                    "notion:pages:search",  # Valid
                    "notion:pages:create",  # Invalid
                    "notion:pages:update",  # Invalid
                ],
            },
        )
        assert response.status_code == 400
        data = response.json()
        invalid = data["detail"]["invalid_permissions"]
        assert "notion:pages:search" not in invalid
        assert "notion:pages:create" in invalid
        assert "notion:pages:update" in invalid
    
    def test_no_connected_services_error(self, user_token):
        """Should error if user has no connected services."""
        response = client.post(
            "/api/v1/auth/delegate",
            headers={"Authorization": f"Bearer {user_token}"},
            json={
                "agent_id": "test-agent",
                "permissions": ["notion:pages:search"],
            },
        )
        assert response.status_code == 400
        assert "no_connected_services" in response.json()["detail"]["error"]
```

---

## Acceptance Criteria

- [ ] `_validate_permissions_subset` uses `ScopeMapper.validate_permissions()`
- [ ] Delegation endpoint returns 400 for invalid permissions
- [ ] Error response includes `invalid_permissions` and `allowed_permissions`
- [ ] Valid permissions still create delegation successfully
- [ ] Backward compatible with existing delegations
- [ ] Unit tests pass
- [ ] Integration tests pass

---

## File Locations

| Artifact | Path |
|----------|------|
| Service changes | `deeptrail-control/app/services/delegation_service.py` |
| Endpoint changes | `deeptrail-control/app/api/v1/endpoints/delegation.py` |
| Tests | `deeptrail-control/tests/api/test_delegation_validation.py` |

---

## Test Endpoint Mapping

| Test Case | Method | Endpoint | Expected Status |
|-----------|--------|----------|-----------------|
| Valid permissions | POST | `/api/v1/auth/delegate` | 200 |
| Invalid permissions | POST | `/api/v1/auth/delegate` | 400 |
| No connected services | POST | `/api/v1/auth/delegate` | 400 |
| Mixed valid/invalid | POST | `/api/v1/auth/delegate` | 400 |

---

## References

- **Architecture Doc:** `docs/architecture/PERMISSION_FLOW_ARCHITECTURE.md`
- **Upstream Dependencies:** WS-K3 (ScopeMapper)
- **Related Specs:** WS-K5 (Available Permissions Endpoint)
- **Existing Service:** `deeptrail-control/app/services/delegation_service.py`
