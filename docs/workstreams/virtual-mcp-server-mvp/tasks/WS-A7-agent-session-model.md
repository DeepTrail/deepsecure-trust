# Task: WS-A7 Define Agent Session Data Model

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
| **Estimated Complexity** | `S` (< 2 hours) |
| **Batch** | 4 |

---

## Validation Mapping

| Mapping | Value |
|---------|-------|
| **Validates Demo** | Demo 3: Delegation Execution, Demo 4: Permission Enforcement |
| **Validates User Journey Step** | Step 5: Agent Authenticates |

---

## Pre-Conditions

Before starting this task, ensure:

- [x] A5 (Delegation Token model) is complete
- [x] A6 (DelegationService) is complete  
- [ ] `deeptrail-control/` service structure exists
- [ ] Database/ORM setup is available (SQLAlchemy)
- [ ] DelegationToken model can be imported from `deeptrail-control.models`
- [ ] UserSession model can be imported from `deeptrail-control.models`

---

## Task Description

Define the Agent Session data model that represents an authenticated agent's active session. This is **Layer 3** of the three-layer token architecture and captures the agent's runtime context including its scoped permissions, parent user session, and MCP session state.

### Context

From the MVP design (Section 2.6 - Step 5: Agent Authenticates):

**Agent Session JWT (Layer 3):**
```json
{
  "sub": "agent-sdr-001",
  "owner": "sarah@acme.com",
  "idp_issuer": "https://acme.okta.com",
  "party_type": "first_party",
  "delegated_permissions": [
    "notion:pages:search",
    "notion:pages:read",
    "slack:messages:search",
    "slack:channels:list"
  ],
  "delegation_id": "del-sarah-sdr-001",
  "groups": ["sales"],
  "session_id": "asess-sdr-001-ghi789",
  "exp": 1737936000
}
```

**Agent Session State:**
```json
{
  "agent_session_id": "asess-sdr-001-ghi789",
  "parent_user_session_id": "usess-sarah-abc123",
  "agent_id": "agent-sdr-001",
  "party_type": "first_party",
  "scoped_permissions": ["notion:pages:search", "notion:pages:read", ...],
  "mcp_sessions": {}
}
```

This enables:
- **Agent Authentication**: Challenge-response Ed25519 verification
- **Permission Scoping**: Agent only has permissions from delegation
- **Session Linking**: Agent session → User session → Organization
- **MCP Session Tracking**: Track which backends the agent has connected to

### Technical Notes

- Use SQLAlchemy ORM for database model
- Store permissions as JSON array (use JSON column type)
- Store `mcp_sessions` as JSON object for flexible backend tracking
- Link to DelegationToken (many-to-one: multiple sessions per delegation)
- Link to UserSession through DelegationToken (indirect relationship)
- Include `challenge_nonce` for authentication flow (used once, then cleared)
- Session lifetime is shorter than delegation lifetime (8 hours vs 7 days)

---

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `deeptrail-control/models/agent_session.py` | **CREATE** | AgentSession SQLAlchemy model |
| `deeptrail-control/models/__init__.py` | **MODIFY** | Export AgentSession |
| `deeptrail-control/tests/models/test_agent_session.py` | **CREATE** | Unit tests for model |

---

## Implementation Details

### 1. AgentSession Model (`deeptrail-control/models/agent_session.py`)

```python
"""Agent Session data model for Virtual MCP Server MVP.

Represents Layer 3 of the three-layer token architecture:
- Layer 0: User ID-Token (from IdP)
- Layer 1: User Session (from UserSession model)
- Layer 2: Delegation Token (from DelegationToken model)
- Layer 3: Agent Session (THIS MODEL)

An AgentSession is created when an agent authenticates via challenge-response
and receives a JWT for accessing the Virtual MCP Server.
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy import Column, String, DateTime, ForeignKey, JSON, Boolean, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid
import enum

from .base import Base


class PartyType(enum.Enum):
    """Agent party type relative to organization."""
    FIRST_PARTY = "first_party"      # Owned by same org
    THIRD_PARTY = "third_party"      # External agent
    FEDERATED = "federated"          # Cross-org federated


class AgentSession(Base):
    """
    Agent Session model representing an authenticated agent's active session.
    
    This is Layer 3 of the token architecture, created after an agent
    successfully completes challenge-response authentication.
    
    Relationships:
    - ManyToOne: DelegationToken (agent can have multiple sessions per delegation)
    - OneToMany: MCP Sessions tracked via JSON (gateway backends)
    
    Lifecycle:
    1. Agent requests challenge (nonce stored)
    2. Agent signs challenge with Ed25519 key
    3. Control plane verifies signature
    4. AgentSession created with JWT issued
    5. Session expires after TTL (8 hours default)
    """
    
    __tablename__ = "agent_sessions"
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Session identifier (used in JWT sub claim)
    session_id = Column(String(64), unique=True, nullable=False, index=True)
    
    # Agent identification
    agent_id = Column(String(128), nullable=False, index=True)
    
    # Foreign key to delegation (provides user context and permissions)
    delegation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("delegation_tokens.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Party type for policy decisions
    party_type = Column(
        Enum(PartyType),
        nullable=False,
        default=PartyType.FIRST_PARTY
    )
    
    # Scoped permissions (subset of delegation permissions)
    # Stored as JSON array for flexibility
    scoped_permissions = Column(JSON, nullable=False, default=list)
    
    # MCP sessions - tracks backend connections
    # Format: {"notion": {"session_id": "...", "connected_at": "..."}, ...}
    mcp_sessions = Column(JSON, nullable=False, default=dict)
    
    # Authentication challenge (used during auth flow)
    # Cleared after successful verification
    challenge_nonce = Column(String(128), nullable=True)
    challenge_expires_at = Column(DateTime, nullable=True)
    
    # Session state
    is_active = Column(Boolean, nullable=False, default=True)
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    last_activity_at = Column(DateTime, nullable=True)
    revoked_at = Column(DateTime, nullable=True)
    
    # Revocation info
    revoked_by = Column(String(128), nullable=True)  # Who revoked (user, admin, system)
    revoke_reason = Column(String(256), nullable=True)
    
    # Metadata for JWT claims
    # Copied from delegation for fast access (denormalized)
    owner_email = Column(String(256), nullable=False)  # sarah@acme.com
    idp_issuer = Column(String(512), nullable=True)    # https://acme.okta.com
    groups = Column(JSON, nullable=False, default=list)  # ["sales"]
    
    # Relationship to DelegationToken
    delegation = relationship("DelegationToken", back_populates="agent_sessions")
    
    # --- Constants ---
    DEFAULT_TTL_HOURS = 8
    CHALLENGE_TTL_SECONDS = 300  # 5 minutes
    
    def __init__(self, **kwargs):
        """Initialize AgentSession with defaults."""
        if "session_id" not in kwargs:
            kwargs["session_id"] = f"asess-{uuid.uuid4().hex[:16]}"
        if "expires_at" not in kwargs:
            kwargs["expires_at"] = datetime.utcnow() + timedelta(hours=self.DEFAULT_TTL_HOURS)
        super().__init__(**kwargs)
    
    @property
    def is_expired(self) -> bool:
        """Check if session has expired."""
        return datetime.utcnow() > self.expires_at
    
    @property
    def is_valid(self) -> bool:
        """Check if session is valid (active and not expired)."""
        return self.is_active and not self.is_expired and self.revoked_at is None
    
    @property
    def challenge_is_valid(self) -> bool:
        """Check if there's a valid pending challenge."""
        if not self.challenge_nonce or not self.challenge_expires_at:
            return False
        return datetime.utcnow() < self.challenge_expires_at
    
    def set_challenge(self, nonce: str) -> None:
        """Set a new authentication challenge."""
        self.challenge_nonce = nonce
        self.challenge_expires_at = datetime.utcnow() + timedelta(
            seconds=self.CHALLENGE_TTL_SECONDS
        )
    
    def clear_challenge(self) -> None:
        """Clear the authentication challenge after use."""
        self.challenge_nonce = None
        self.challenge_expires_at = None
    
    def revoke(self, revoked_by: str = "system", reason: str = None) -> None:
        """Revoke the agent session."""
        self.is_active = False
        self.revoked_at = datetime.utcnow()
        self.revoked_by = revoked_by
        self.revoke_reason = reason
    
    def add_mcp_session(self, backend: str, session_data: Dict[str, Any]) -> None:
        """Track a new MCP backend session."""
        if self.mcp_sessions is None:
            self.mcp_sessions = {}
        self.mcp_sessions[backend] = {
            **session_data,
            "connected_at": datetime.utcnow().isoformat()
        }
    
    def remove_mcp_session(self, backend: str) -> None:
        """Remove an MCP backend session."""
        if self.mcp_sessions and backend in self.mcp_sessions:
            del self.mcp_sessions[backend]
    
    def has_permission(self, permission: str) -> bool:
        """Check if session has a specific permission."""
        return permission in (self.scoped_permissions or [])
    
    def touch(self) -> None:
        """Update last activity timestamp."""
        self.last_activity_at = datetime.utcnow()
    
    def to_jwt_claims(self) -> Dict[str, Any]:
        """Generate claims for Agent Session JWT (Layer 3)."""
        return {
            "sub": self.agent_id,
            "session_id": self.session_id,
            "owner": self.owner_email,
            "idp_issuer": self.idp_issuer,
            "party_type": self.party_type.value,
            "delegated_permissions": self.scoped_permissions,
            "delegation_id": str(self.delegation_id),
            "groups": self.groups,
            "exp": int(self.expires_at.timestamp()),
            "iat": int(self.created_at.timestamp())
        }
    
    def __repr__(self) -> str:
        return (
            f"<AgentSession(session_id='{self.session_id}', "
            f"agent_id='{self.agent_id}', "
            f"owner='{self.owner_email}', "
            f"is_valid={self.is_valid})>"
        )
```

### 2. Update `__init__.py`

```python
# Add to deeptrail-control/models/__init__.py
from .agent_session import AgentSession, PartyType

__all__ = [
    # ... existing exports ...
    "AgentSession",
    "PartyType",
]
```

### 3. Update DelegationToken Model

Add back-reference in `delegation.py`:

```python
# Add relationship to DelegationToken model
agent_sessions = relationship(
    "AgentSession",
    back_populates="delegation",
    cascade="all, delete-orphan"
)
```

---

## Acceptance Criteria

### Data Model Criteria

- [ ] AgentSession model created with all required fields from design doc
- [ ] Session ID uses format `asess-{agent}-{random}` (e.g., `asess-sdr-001-ghi789`)
- [ ] Foreign key relationship to DelegationToken established
- [ ] Party type enum supports `first_party`, `third_party`, `federated`
- [ ] Scoped permissions stored as JSON array
- [ ] MCP sessions stored as JSON object

### Authentication Criteria

- [ ] Challenge nonce field for auth flow
- [ ] Challenge expiration (5 minute TTL)
- [ ] `set_challenge()` and `clear_challenge()` methods work correctly
- [ ] `challenge_is_valid` property correctly checks expiration

### Session Lifecycle Criteria

- [ ] Default TTL is 8 hours (shorter than delegation's 7 days)
- [ ] `is_expired` property works correctly
- [ ] `is_valid` checks active, not expired, and not revoked
- [ ] `revoke()` method sets all revocation fields
- [ ] `touch()` updates last activity timestamp

### JWT Generation Criteria

- [ ] `to_jwt_claims()` produces claims matching design doc format
- [ ] Claims include: sub, session_id, owner, idp_issuer, party_type
- [ ] Claims include: delegated_permissions, delegation_id, groups, exp, iat

### MCP Session Tracking Criteria

- [ ] `add_mcp_session()` stores backend session info
- [ ] `remove_mcp_session()` removes backend tracking
- [ ] MCP sessions include `connected_at` timestamp

### Permission Criteria

- [ ] `has_permission()` method correctly checks scoped_permissions
- [ ] Permissions are subset of delegation permissions (enforced at service layer)

### Integration Criteria

- [ ] Model exported from `models/__init__.py`
- [ ] Relationship from DelegationToken added (back_populates)
- [ ] All tests pass with `pytest tests/models/test_agent_session.py`
- [ ] Model can be used with SQLAlchemy session

---

## Test Cases

Create `deeptrail-control/tests/models/test_agent_session.py`:

```python
"""Tests for AgentSession model."""

import pytest
from datetime import datetime, timedelta
from models.agent_session import AgentSession, PartyType


class TestAgentSessionModel:
    """Test AgentSession model structure and validation."""
    
    def test_create_agent_session_minimal(self):
        """Test creating session with minimal fields."""
        session = AgentSession(
            agent_id="agent-sdr-001",
            delegation_id="...",  # Use actual UUID
            owner_email="sarah@acme.com",
            scoped_permissions=["notion:pages:search"]
        )
        assert session.session_id.startswith("asess-")
        assert session.agent_id == "agent-sdr-001"
        assert session.party_type == PartyType.FIRST_PARTY
    
    def test_session_id_auto_generated(self):
        """Test session_id is auto-generated if not provided."""
        session = AgentSession(
            agent_id="agent-001",
            delegation_id="...",
            owner_email="test@example.com"
        )
        assert session.session_id is not None
        assert session.session_id.startswith("asess-")
    
    def test_default_ttl(self):
        """Test default TTL is 8 hours."""
        session = AgentSession(
            agent_id="agent-001",
            delegation_id="...",
            owner_email="test@example.com"
        )
        expected_expiry = datetime.utcnow() + timedelta(hours=8)
        # Allow 1 minute tolerance
        assert abs((session.expires_at - expected_expiry).total_seconds()) < 60
    
    def test_is_expired(self):
        """Test is_expired property."""
        # Not expired
        session = AgentSession(
            agent_id="agent-001",
            delegation_id="...",
            owner_email="test@example.com",
            expires_at=datetime.utcnow() + timedelta(hours=1)
        )
        assert session.is_expired is False
        
        # Expired
        session.expires_at = datetime.utcnow() - timedelta(hours=1)
        assert session.is_expired is True
    
    def test_is_valid(self):
        """Test is_valid combines active, expired, and revoked checks."""
        session = AgentSession(
            agent_id="agent-001",
            delegation_id="...",
            owner_email="test@example.com",
            is_active=True,
            expires_at=datetime.utcnow() + timedelta(hours=1)
        )
        assert session.is_valid is True
        
        # Not active
        session.is_active = False
        assert session.is_valid is False
        
        # Revoked
        session.is_active = True
        session.revoked_at = datetime.utcnow()
        assert session.is_valid is False


class TestAgentSessionChallenge:
    """Test challenge-response authentication flow."""
    
    def test_set_challenge(self):
        """Test setting a challenge."""
        session = AgentSession(
            agent_id="agent-001",
            delegation_id="...",
            owner_email="test@example.com"
        )
        session.set_challenge("nonce-abc123")
        
        assert session.challenge_nonce == "nonce-abc123"
        assert session.challenge_expires_at is not None
        assert session.challenge_is_valid is True
    
    def test_clear_challenge(self):
        """Test clearing a challenge after use."""
        session = AgentSession(
            agent_id="agent-001",
            delegation_id="...",
            owner_email="test@example.com"
        )
        session.set_challenge("nonce-abc123")
        session.clear_challenge()
        
        assert session.challenge_nonce is None
        assert session.challenge_expires_at is None
        assert session.challenge_is_valid is False
    
    def test_challenge_expires(self):
        """Test challenge expiration (5 minutes)."""
        session = AgentSession(
            agent_id="agent-001",
            delegation_id="...",
            owner_email="test@example.com"
        )
        session.set_challenge("nonce-abc123")
        
        # Valid initially
        assert session.challenge_is_valid is True
        
        # Expired after 5 minutes
        session.challenge_expires_at = datetime.utcnow() - timedelta(minutes=1)
        assert session.challenge_is_valid is False


class TestAgentSessionJWT:
    """Test JWT claim generation."""
    
    def test_to_jwt_claims(self):
        """Test JWT claims match design doc format."""
        session = AgentSession(
            session_id="asess-sdr-001-ghi789",
            agent_id="agent-sdr-001",
            delegation_id="...",
            owner_email="sarah@acme.com",
            idp_issuer="https://acme.okta.com",
            party_type=PartyType.FIRST_PARTY,
            scoped_permissions=[
                "notion:pages:search",
                "notion:pages:read",
                "slack:messages:search"
            ],
            groups=["sales"]
        )
        
        claims = session.to_jwt_claims()
        
        assert claims["sub"] == "agent-sdr-001"
        assert claims["session_id"] == "asess-sdr-001-ghi789"
        assert claims["owner"] == "sarah@acme.com"
        assert claims["idp_issuer"] == "https://acme.okta.com"
        assert claims["party_type"] == "first_party"
        assert "notion:pages:search" in claims["delegated_permissions"]
        assert claims["groups"] == ["sales"]
        assert "exp" in claims
        assert "iat" in claims


class TestAgentSessionMCPTracking:
    """Test MCP session tracking."""
    
    def test_add_mcp_session(self):
        """Test adding an MCP backend session."""
        session = AgentSession(
            agent_id="agent-001",
            delegation_id="...",
            owner_email="test@example.com"
        )
        
        session.add_mcp_session("notion", {"session_id": "mcp-123"})
        
        assert "notion" in session.mcp_sessions
        assert session.mcp_sessions["notion"]["session_id"] == "mcp-123"
        assert "connected_at" in session.mcp_sessions["notion"]
    
    def test_remove_mcp_session(self):
        """Test removing an MCP backend session."""
        session = AgentSession(
            agent_id="agent-001",
            delegation_id="...",
            owner_email="test@example.com",
            mcp_sessions={"notion": {"session_id": "mcp-123"}}
        )
        
        session.remove_mcp_session("notion")
        
        assert "notion" not in session.mcp_sessions


class TestAgentSessionPermissions:
    """Test permission checking."""
    
    def test_has_permission(self):
        """Test permission check."""
        session = AgentSession(
            agent_id="agent-001",
            delegation_id="...",
            owner_email="test@example.com",
            scoped_permissions=["notion:pages:search", "slack:messages:read"]
        )
        
        assert session.has_permission("notion:pages:search") is True
        assert session.has_permission("notion:pages:delete") is False


class TestAgentSessionRevocation:
    """Test session revocation."""
    
    def test_revoke_session(self):
        """Test revoking a session."""
        session = AgentSession(
            agent_id="agent-001",
            delegation_id="...",
            owner_email="test@example.com"
        )
        
        session.revoke(revoked_by="sarah@acme.com", reason="User requested")
        
        assert session.is_active is False
        assert session.revoked_at is not None
        assert session.revoked_by == "sarah@acme.com"
        assert session.revoke_reason == "User requested"
        assert session.is_valid is False
```

---

## Post-Conditions

After completing this task:

- [ ] AgentSession model is available for import
- [ ] Database migration can be generated (if using Alembic)
- [ ] A8 (AgentSessionService) is unblocked
- [ ] C1, C2 (agent auth endpoints) have data model available
- [ ] All unit tests pass

---

## References

- **Design Doc Section**: 2.6 Step 5: Agent Authenticates
- **Token Architecture**: Section 4.1 (Three-Layer Token Model)
- **Related Models**: 
  - [WS-A1: UserSession](./WS-A1-user-session-model.md)
  - [WS-A5: DelegationToken](./WS-A5-delegation-token-model.md)
- **Downstream Tasks**:
  - [WS-A8: AgentSessionService](./WS-A8-agent-session-service.md)
  - [WS-C1: Agent Challenge Endpoint](./WS-C1-agent-challenge-endpoint.md)
  - [WS-C2: Agent Verify Endpoint](./WS-C2-agent-verify-endpoint.md)

---

## Notes

- This model stores denormalized data (owner_email, groups) from the delegation for performance
- The `mcp_sessions` JSON field allows flexible tracking without additional tables
- Challenge nonce is single-use: cleared after successful verification
- Session is shorter-lived (8 hours) than delegation (7 days) for security
