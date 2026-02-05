# Task: WS-A5 Define Delegation Token Model

---

## Metadata

| Field | Value |
|-------|-------|
| **Status** | `ready` |
| **Design Doc** | [deepsecure-virtual-mcp-server-mvp.md](../../../design/internal/markdowns/deepsecure-virtual-mcp-server-mvp.md) |
| **Workstream** | WS-A: Control Plane Foundation |
| **Dependencies** | A1 (User Session data model) |
| **Blocked By** | None (A1 is complete ✅) |
| **Assigned** | - |
| **Created** | January 30, 2026 |
| **Estimated Complexity** | `S` (< 2 hours) |
| **Batch** | 2 |

---

## Validation Mapping

| Mapping | Value |
|---------|-------|
| **Validates Demo** | Demo 3: Permission Enforcement (foundation) |
| **Validates User Journey Step** | Step 4: Sarah Delegates to Agent |

---

## Pre-Conditions

Before starting this task, ensure:

- [x] A1 (User Session data model) is complete
- [ ] `deeptrail-control/` service structure exists
- [ ] Database/ORM setup is available (SQLAlchemy)
- [ ] UserSession model can be imported from `deeptrail-control.models`

---

## Task Description

Define the Delegation Token data model that represents a user's delegation of permissions to an agent. This is **Layer 2** of the three-layer token architecture and captures what permissions a user grants to a specific agent, along with constraints and binding information.

### Context

From the MVP design (Section 2.5 - Step 4):

```json
LAYER 2: DELEGATION TOKEN
{
  "sub": "agent-sdr-001",
  "delegator": "sarah@acme.com",
  "delegator_idp": "https://acme.okta.com",
  "user_token_hash": "sha256:abc...",     // Binds to Sarah's identity
  "agent_token_hash": "sha256:def...",    // Binds to agent's identity
  "delegated_permissions": [
    "notion:pages:search",
    "notion:pages:read",
    "slack:messages:search",
    "slack:channels:list"
  ],
  "constraints": {
    "max_actions_per_day": 100
  },
  "exp": 1738512000,  // 7 days
  "logging_uri": "https://audit.deeptrail.io/log",
  "revocation_uri": "https://deeptrail.io/revoke/del-sarah-sdr-001"
}
```

This enables:
- **Monotonic Attenuation**: Agent permissions ⊂ Sarah's permissions
- **Bounded Delegation**: Time-limited with explicit expiration
- **Constraint Enforcement**: Rate limits, action caps
- **Revocability**: Sarah can revoke at any time via revocation_uri

### Technical Notes

- Use SQLAlchemy ORM for database model
- Delegation Token is stored in DB; can be serialized to JWT for transmission
- `delegated_permissions` stored as JSON array
- `constraints` stored as JSON object for flexibility
- Consider separate `DelegationConstraint` model if constraints become complex
- Foreign key relationships to User (delegator) and Agent (sub)

---

## Acceptance Criteria

### Protocol
- [ ] N/A (data model only)

### Security
- [ ] Token binding fields (user_token_hash, agent_token_hash) are present
- [ ] Revocation support via revoked_at timestamp and revocation_uri
- [ ] Expiration is mandatory (no indefinite delegations)

### Integration
- [ ] Model can be imported from `deeptrail-control.models`
- [ ] Model follows existing ORM patterns in the codebase
- [ ] Serialization to JWT-compatible dict is available

### Functional
- [ ] All fields from Step 4 are present:
  - sub (agent_id)
  - delegator (user_id)
  - delegator_idp
  - user_token_hash
  - agent_token_hash
  - delegated_permissions (JSON array)
  - constraints (JSON object)
  - exp (expires_at)
  - logging_uri
  - revocation_uri
- [ ] `is_valid` property checks expiration and revocation
- [ ] `has_permission(permission: str)` method for checking grants
- [ ] Unique constraint on (delegator, agent_id) or allow multiple delegations?

### General
- [ ] Unit tests for model instantiation, validation, and permission checks
- [ ] No new linting errors introduced

---

## Files to Create

| File | Purpose |
|------|---------|
| `deeptrail-control/models/delegation.py` | Delegation Token SQLAlchemy model |
| `deeptrail-control/tests/models/test_delegation.py` | Unit tests for the model |

---

## Files to Modify

| File | Changes |
|------|---------|
| `deeptrail-control/models/__init__.py` | Export DelegationToken model |

---

## Implementation Hints

```python
# deeptrail-control/models/delegation.py

from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from sqlalchemy import Column, String, DateTime, JSON, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import UUID
import uuid

class DelegationToken(Base):
    __tablename__ = "delegation_tokens"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Agent receiving delegation (Layer 2 "sub")
    agent_id = Column(String, nullable=False, index=True)  # e.g., "agent-sdr-001"
    
    # User granting delegation (Layer 2 "delegator")
    delegator = Column(String, nullable=False, index=True)  # e.g., "sarah@acme.com"
    delegator_idp = Column(String, nullable=True)  # e.g., "https://acme.okta.com"
    
    # Token binding (cryptographic link to user and agent identity)
    user_token_hash = Column(String, nullable=True)   # sha256:abc...
    agent_token_hash = Column(String, nullable=True)  # sha256:def...
    
    # Delegated permissions (subset of user's permissions)
    delegated_permissions = Column(JSON, nullable=False, default=list)
    # e.g., ["notion:pages:search", "notion:pages:read", "slack:messages:search"]
    
    # Constraints on delegation
    constraints = Column(JSON, nullable=False, default=dict)
    # e.g., {"max_actions_per_day": 100}
    
    # Lifecycle
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    expires_at = Column(DateTime(timezone=True), nullable=False)  # Required!
    revoked_at = Column(DateTime(timezone=True), nullable=True)   # None = active
    
    # URIs for audit and revocation
    logging_uri = Column(String, nullable=True)
    revocation_uri = Column(String, nullable=True)
    
    @property
    def is_valid(self) -> bool:
        """Check if delegation is currently valid (not expired, not revoked)."""
        now = datetime.now(timezone.utc)
        if self.revoked_at is not None:
            return False
        if self.expires_at <= now:
            return False
        return True
    
    @property
    def is_expired(self) -> bool:
        """Check if delegation has expired."""
        return datetime.now(timezone.utc) >= self.expires_at
    
    @property
    def is_revoked(self) -> bool:
        """Check if delegation has been revoked."""
        return self.revoked_at is not None
    
    def has_permission(self, permission: str) -> bool:
        """Check if a specific permission is delegated."""
        return permission in (self.delegated_permissions or [])
    
    def get_constraint(self, key: str, default: Any = None) -> Any:
        """Get a constraint value by key."""
        return (self.constraints or {}).get(key, default)
    
    def to_claims_dict(self) -> Dict[str, Any]:
        """Serialize to JWT-compatible claims dictionary."""
        return {
            "sub": self.agent_id,
            "delegator": self.delegator,
            "delegator_idp": self.delegator_idp,
            "user_token_hash": self.user_token_hash,
            "agent_token_hash": self.agent_token_hash,
            "delegated_permissions": self.delegated_permissions,
            "constraints": self.constraints,
            "exp": int(self.expires_at.timestamp()),
            "iat": int(self.created_at.timestamp()),
            "logging_uri": self.logging_uri,
            "revocation_uri": self.revocation_uri,
        }
    
    def revoke(self) -> None:
        """Revoke this delegation."""
        self.revoked_at = datetime.now(timezone.utc)
```

---

## Post-Conditions

After completing this task:

- [ ] All acceptance criteria met
- [ ] Tests pass locally: `pytest deeptrail-control/tests/models/test_delegation.py`
- [ ] Linting passes: `ruff check deeptrail-control/models/`
- [ ] Type checking passes: `mypy deeptrail-control/models/`
- [ ] Task A6 can now start (DelegationService depends on A5)

---

## References

- Design Doc Section 2.5: Step 4 - Sarah Delegates to Agent
- Design Doc Section 3.2: Three-Layer Token Architecture (Layer 2)
- Design Doc Section 4.1: Monotonic Attenuation principle
- A1 Task: UserSession model for user_id pattern

---

## Notes

- This is a **critical security model** - Layer 2 of the token architecture
- Permissions format: `{service}:{resource}:{action}` (e.g., `notion:pages:search`)
- Consider indexing `agent_id` + `delegator` for fast lookups
- A6 (DelegationService) will implement create/validate/revoke logic
- The `to_claims_dict()` method enables JWT serialization for transmission

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
