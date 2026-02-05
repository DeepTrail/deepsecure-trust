# Task: WS-A6 Implement DelegationService

---

## Metadata

| Field | Value |
|-------|-------|
| **Status** | `ready` |
| **Design Doc** | [deepsecure-virtual-mcp-server-mvp.md](../../../design/internal/markdowns/deepsecure-virtual-mcp-server-mvp.md) |
| **Workstream** | WS-A: Control Plane Foundation |
| **Dependencies** | A5 (Delegation Token model) |
| **Blocked By** | None (A5 is complete ✅) |
| **Assigned** | - |
| **Created** | January 30, 2026 |
| **Estimated Complexity** | `M` (2-4 hours) |
| **Batch** | 3 |

---

## Validation Mapping

| Mapping | Value |
|---------|-------|
| **Validates Demo** | Demo 3: Permission Enforcement, Demo 4: Delegation Execution |
| **Validates User Journey Step** | Step 4: Sarah Delegates to Agent |

---

## Pre-Conditions

Before starting this task, ensure:

- [x] A5 (Delegation Token model) is complete
- [ ] `deeptrail-control/` service structure exists
- [ ] DelegationToken model can be imported from `deeptrail-control.models`
- [ ] ConnectedService model available for permission validation (A3)

---

## Task Description

Implement the DelegationService that manages the lifecycle of delegation tokens - the mechanism by which users grant specific permissions to agents. This service enables Step 4 of Sarah's journey where she delegates limited access to her connected services to an agent.

### Context

From the MVP design (Section 2.5 - Step 4):

```
Sarah in Console → "My Agents" → "SDR-Assistant" → "Permissions"

DELEGATE PERMISSIONS TO SDR-ASSISTANT:
  NOTION PERMISSIONS:
  ☑ Search pages (notion:pages:search)
  ☑ Read pages (notion:pages:read)
  ☐ Create pages (notion:pages:create)  ← Sarah doesn't grant this

  CONSTRAINTS:
  • Delegation expires: 7 days
  • Max actions per day: 100

  [Save Delegation]
```

The service must enforce **Monotonic Attenuation**:
- Sarah has: `notion:*`, `slack:*` (from her OAuth consent)
- Agent gets: subset of Sarah's permissions
- Agent permissions ⊂ Sarah's permissions ✓

### Technical Notes

- **Create**: Generate delegation with permissions subset of user's connected service scopes
- **Validate**: Check expiry, revocation, and permission membership
- **Revoke**: Mark delegation as revoked (soft delete)
- **Query**: Find delegations by user (delegator) or agent (sub)
- **Constraints**: Store and retrieve constraint metadata (max_actions_per_day, etc.)

---

## Acceptance Criteria

### Protocol
- [ ] N/A (internal service)

### Security
- [ ] Validates requested permissions are subset of user's connected service scopes (monotonic attenuation)
- [ ] Delegation cannot be created for expired or revoked user session
- [ ] Revocation is immediate and permanent (no unrevoke)
- [ ] Token binding hashes are generated securely (SHA-256)

### Integration
- [ ] DelegationService can be imported from `deeptrail-control.services`
- [ ] Works with DelegationToken model from A5
- [ ] Can query ConnectedService to validate permission scope
- [ ] Gateway can call to validate agent permissions (for C6)

### Functional
- [ ] `create_delegation(delegator, agent_id, permissions, constraints, expires_in)` → DelegationToken
- [ ] `validate_delegation(delegation_id)` → ValidationResult with is_valid, reason
- [ ] `revoke_delegation(delegation_id)` → bool
- [ ] `get_delegation(delegation_id)` → DelegationToken or None
- [ ] `get_delegations_for_user(user_id)` → List[DelegationToken]
- [ ] `get_delegations_for_agent(agent_id)` → List[DelegationToken]
- [ ] `has_permission(delegation_id, permission)` → bool
- [ ] `get_active_delegation(delegator, agent_id)` → DelegationToken or None

### General
- [ ] Unit tests for all service methods
- [ ] Tests for permission validation (monotonic attenuation)
- [ ] Tests for expiry and revocation handling
- [ ] No new linting errors introduced

---

## Files to Create

| File | Purpose |
|------|---------|
| `deeptrail-control/services/delegation_service.py` | Delegation lifecycle management |
| `deeptrail-control/tests/services/test_delegation_service.py` | Unit tests |

---

## Files to Modify

| File | Changes |
|------|---------|
| `deeptrail-control/services/__init__.py` | Export DelegationService |

---

## Implementation Hints

```python
# deeptrail-control/services/delegation_service.py

from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
import hashlib
import uuid

from ..models.delegation import DelegationToken
from ..models.connected_service import ConnectedService

@dataclass
class ValidationResult:
    """Result of delegation validation."""
    is_valid: bool
    reason: Optional[str] = None
    delegation: Optional[DelegationToken] = None


class DelegationService:
    """
    Service for managing delegation tokens.
    
    Handles the lifecycle of user → agent permission delegations.
    """
    
    DEFAULT_EXPIRY_DAYS = 7
    
    def __init__(self, db_session):
        self._db = db_session
    
    def _generate_token_hash(self, token_data: str) -> str:
        """Generate SHA-256 hash for token binding."""
        return f"sha256:{hashlib.sha256(token_data.encode()).hexdigest()[:16]}"
    
    def _generate_revocation_uri(self, delegation_id: str) -> str:
        """Generate revocation URI for delegation."""
        return f"https://deeptrail.io/revoke/{delegation_id}"
    
    def _validate_permissions_subset(
        self,
        delegator: str,
        requested_permissions: List[str]
    ) -> tuple[bool, Optional[str]]:
        """
        Validate that requested permissions are subset of user's scopes.
        
        Enforces monotonic attenuation principle.
        """
        # Get all user's connected services
        connections = self._db.query(ConnectedService).filter(
            ConnectedService.user_id == delegator,
            ConnectedService.disconnected_at.is_(None)
        ).all()
        
        # Build set of all user's available permissions
        user_permissions = set()
        for conn in connections:
            service_id = conn.service_id
            for scope in (conn.scopes_granted or []):
                # Convert scope to permission format
                # e.g., "read_content" on "notion" → "notion:content:read"
                # For MVP, assume scopes are already in permission format
                user_permissions.add(f"{service_id}:{scope}")
        
        # Check each requested permission
        for perm in requested_permissions:
            # Extract service from permission (e.g., "notion:pages:search" → "notion")
            service = perm.split(":")[0]
            
            # Check if user has this service connected
            service_connected = any(c.service_id == service for c in connections)
            if not service_connected:
                return False, f"User not connected to service: {service}"
            
            # For MVP, allow any permission if service is connected
            # Production would check against specific scopes
        
        return True, None
    
    def create_delegation(
        self,
        delegator: str,
        agent_id: str,
        permissions: List[str],
        constraints: Optional[Dict[str, Any]] = None,
        expires_in_days: int = DEFAULT_EXPIRY_DAYS,
        delegator_idp: Optional[str] = None
    ) -> DelegationToken:
        """
        Create a new delegation from user to agent.
        
        Args:
            delegator: User ID granting delegation (e.g., "sarah@acme.com")
            agent_id: Agent ID receiving delegation (e.g., "agent-sdr-001")
            permissions: List of permissions to delegate
            constraints: Optional constraints (e.g., {"max_actions_per_day": 100})
            expires_in_days: Delegation validity period
            delegator_idp: Optional IdP issuer for delegator
        
        Returns:
            Created DelegationToken
        
        Raises:
            ValueError: If permissions validation fails
        """
        # Validate permissions are subset of user's scopes
        is_valid, reason = self._validate_permissions_subset(delegator, permissions)
        if not is_valid:
            raise ValueError(f"Permission validation failed: {reason}")
        
        # Check for existing active delegation
        existing = self.get_active_delegation(delegator, agent_id)
        if existing:
            # Revoke existing before creating new
            self.revoke_delegation(str(existing.id))
        
        # Generate token bindings
        user_token_hash = self._generate_token_hash(f"{delegator}-{uuid.uuid4()}")
        agent_token_hash = self._generate_token_hash(f"{agent_id}-{uuid.uuid4()}")
        
        # Calculate expiration
        expires_at = datetime.now(timezone.utc) + timedelta(days=expires_in_days)
        
        # Create delegation
        delegation = DelegationToken(
            agent_id=agent_id,
            delegator=delegator,
            delegator_idp=delegator_idp,
            user_token_hash=user_token_hash,
            agent_token_hash=agent_token_hash,
            delegated_permissions=permissions,
            constraints=constraints or {},
            expires_at=expires_at,
            revocation_uri=self._generate_revocation_uri(str(uuid.uuid4())[:8])
        )
        
        self._db.add(delegation)
        return delegation
    
    def validate_delegation(self, delegation_id: str) -> ValidationResult:
        """
        Validate a delegation token.
        
        Checks:
        - Delegation exists
        - Not expired
        - Not revoked
        
        Returns:
            ValidationResult with is_valid flag and reason if invalid
        """
        delegation = self.get_delegation(delegation_id)
        
        if not delegation:
            return ValidationResult(is_valid=False, reason="Delegation not found")
        
        if delegation.is_expired:
            return ValidationResult(
                is_valid=False, 
                reason="Delegation expired",
                delegation=delegation
            )
        
        if delegation.is_revoked:
            return ValidationResult(
                is_valid=False,
                reason="Delegation revoked",
                delegation=delegation
            )
        
        return ValidationResult(is_valid=True, delegation=delegation)
    
    def revoke_delegation(self, delegation_id: str) -> bool:
        """
        Revoke a delegation.
        
        Args:
            delegation_id: Delegation UUID
        
        Returns:
            True if revoked, False if not found
        """
        delegation = self.get_delegation(delegation_id)
        if not delegation:
            return False
        
        delegation.revoke()
        return True
    
    def get_delegation(self, delegation_id: str) -> Optional[DelegationToken]:
        """Get delegation by ID."""
        return self._db.query(DelegationToken).filter(
            DelegationToken.id == delegation_id
        ).first()
    
    def get_delegations_for_user(self, user_id: str) -> List[DelegationToken]:
        """Get all delegations created by a user."""
        return self._db.query(DelegationToken).filter(
            DelegationToken.delegator == user_id
        ).all()
    
    def get_delegations_for_agent(self, agent_id: str) -> List[DelegationToken]:
        """Get all delegations granted to an agent."""
        return self._db.query(DelegationToken).filter(
            DelegationToken.agent_id == agent_id
        ).all()
    
    def get_active_delegation(
        self, 
        delegator: str, 
        agent_id: str
    ) -> Optional[DelegationToken]:
        """
        Get active (not expired, not revoked) delegation between user and agent.
        """
        now = datetime.now(timezone.utc)
        return self._db.query(DelegationToken).filter(
            DelegationToken.delegator == delegator,
            DelegationToken.agent_id == agent_id,
            DelegationToken.expires_at > now,
            DelegationToken.revoked_at.is_(None)
        ).first()
    
    def has_permission(self, delegation_id: str, permission: str) -> bool:
        """
        Check if delegation grants a specific permission.
        
        Args:
            delegation_id: Delegation UUID
            permission: Permission string (e.g., "notion:pages:search")
        
        Returns:
            True if permission is delegated and delegation is valid
        """
        result = self.validate_delegation(delegation_id)
        if not result.is_valid:
            return False
        
        return result.delegation.has_permission(permission)
```

---

## Post-Conditions

After completing this task:

- [ ] All acceptance criteria met
- [ ] Tests pass locally: `pytest deeptrail-control/tests/services/test_delegation_service.py`
- [ ] Linting passes: `ruff check deeptrail-control/services/`
- [ ] Type checking passes: `mypy deeptrail-control/services/`
- [ ] Task A8 (AgentSessionService) can use delegations
- [ ] Task C6 (delegation validator) can use this service

---

## References

- Design Doc Section 2.5: Step 4 - Sarah Delegates to Agent
- Design Doc Section 4.1: Monotonic Attenuation principle
- A5 Task: DelegationToken model
- A3 Task: ConnectedService model (for permission validation)

---

## Notes

- **Monotonic Attenuation**: Critical security property - agent can never have more permissions than user
- **One active delegation per user-agent pair**: Simplifies lookup and revocation
- **Constraints**: Stored as JSON, enforced by E5 (constraint checker) in gateway
- **Revocation**: Immediate and permanent - consider adding revocation reason in production
- **Token binding**: user_token_hash and agent_token_hash bind delegation to specific identities

---

## Test Cases to Cover

```python
# test_delegation_service.py

def test_create_delegation_success():
    service = DelegationService(mock_db_with_connected_services)
    
    delegation = service.create_delegation(
        delegator="sarah@acme.com",
        agent_id="agent-sdr-001",
        permissions=["notion:pages:search", "notion:pages:read"],
        constraints={"max_actions_per_day": 100}
    )
    
    assert delegation.delegator == "sarah@acme.com"
    assert delegation.agent_id == "agent-sdr-001"
    assert len(delegation.delegated_permissions) == 2
    assert delegation.is_valid

def test_create_delegation_rejects_unconnected_service():
    service = DelegationService(mock_db_no_hubspot)
    
    with pytest.raises(ValueError, match="not connected"):
        service.create_delegation(
            delegator="sarah@acme.com",
            agent_id="agent-001",
            permissions=["hubspot:contacts:read"]  # Not connected
        )

def test_validate_expired_delegation():
    service = DelegationService(mock_db_with_expired_delegation)
    
    result = service.validate_delegation("expired-delegation-id")
    
    assert result.is_valid is False
    assert "expired" in result.reason.lower()

def test_validate_revoked_delegation():
    service = DelegationService(mock_db)
    delegation = create_test_delegation()
    
    service.revoke_delegation(str(delegation.id))
    result = service.validate_delegation(str(delegation.id))
    
    assert result.is_valid is False
    assert "revoked" in result.reason.lower()

def test_has_permission_returns_true_for_delegated():
    service = DelegationService(mock_db)
    delegation = service.create_delegation(
        delegator="user",
        agent_id="agent",
        permissions=["notion:pages:search"]
    )
    
    assert service.has_permission(str(delegation.id), "notion:pages:search") is True
    assert service.has_permission(str(delegation.id), "notion:pages:create") is False

def test_get_active_delegation():
    service = DelegationService(mock_db)
    service.create_delegation("sarah", "agent-1", ["perm:1"])
    
    active = service.get_active_delegation("sarah", "agent-1")
    assert active is not None
    
    none = service.get_active_delegation("sarah", "agent-2")
    assert none is None
```

---

## Execution Log

### Progress Updates

| Date | Update |
|------|--------|
| - | Task created, ready to start |

### Blockers Encountered

| Date | Blocker | Resolution |
|------|---------|------------|
| - | - | - |
