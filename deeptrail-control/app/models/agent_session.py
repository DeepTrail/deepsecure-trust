"""SQLAlchemy model for Agent Session entities.

Agent sessions represent Layer 3 of the three-layer token architecture:
- Layer 1: User Session (human identity)
- Layer 2: Delegation Token (permission grant to agent)
- Layer 3: Agent Session (ephemeral agent context) <- THIS

An AgentSession is created when an agent authenticates via challenge-response
and receives a JWT for accessing the Virtual MCP Server.

Key characteristics:
- Short-lived (8 hours) compared to delegations (7 days)
- Scoped permissions (subset of delegation permissions)
- Tracks MCP backend connections
- Supports challenge-response authentication flow
"""

import enum
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy import JSON
from sqlalchemy import Enum as SQLAlchemyEnum
from sqlalchemy.orm import relationship

from app.db.base import Base


# Default session duration (8 hours as per design doc)
DEFAULT_SESSION_DURATION_HOURS = 8

# Challenge TTL (5 minutes for authentication flow)
CHALLENGE_TTL_SECONDS = 300


def generate_session_id() -> str:
    """Generate a unique agent session ID."""
    return f"asess-{uuid.uuid4().hex[:16]}"


def get_default_expiry() -> datetime:
    """Calculate default session expiry (8 hours from now)."""
    return datetime.now(timezone.utc) + timedelta(hours=DEFAULT_SESSION_DURATION_HOURS)


class PartyType(enum.Enum):
    """Agent party type relative to organization.

    Determines trust level and policy application:
    - FIRST_PARTY: Owned by same organization, highest trust
    - THIRD_PARTY: External agent, more restricted
    - FEDERATED: Cross-org federated, specific federation policies apply
    """

    FIRST_PARTY = "first_party"
    THIRD_PARTY = "third_party"
    FEDERATED = "federated"


class AgentSession(Base):
    """Agent Session model representing an authenticated agent's active session.

    This is Layer 3 of the token architecture, created after an agent
    successfully completes challenge-response authentication.

    Example from design doc:
        Agent SDR-Assistant authenticates:
        - session_id: "asess-abc123def456"
        - agent_id: "agent-sdr-001"
        - owner_email: "sarah@acme.com"
        - scoped_permissions: ["notion:pages:search", "slack:messages:search"]
        - party_type: "first_party"
        - groups: ["sales"]
        - expires_at: 8 hours from now

    Lifecycle:
        1. Agent requests challenge (nonce stored)
        2. Agent signs challenge with Ed25519 key
        3. Control plane verifies signature
        4. AgentSession created with JWT issued
        5. Session expires after TTL (8 hours default)
    """

    __tablename__ = "agent_sessions"

    # Primary key - unique session identifier
    id = Column(
        String(64),
        primary_key=True,
        default=generate_session_id,
        comment="Unique session identifier (e.g., asess-<uuid>)",
    )

    # Agent identification
    agent_id = Column(
        String(128),
        nullable=False,
        index=True,
        comment="Agent identifier (e.g., agent-sdr-001)",
    )

    # Foreign key to delegation (provides user context and permissions)
    delegation_id = Column(
        String(64),
        ForeignKey("delegation_tokens.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Reference to parent delegation token",
    )

    # Party type for policy decisions
    party_type = Column(
        SQLAlchemyEnum(PartyType, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=PartyType.FIRST_PARTY,
        comment="Agent party type (first_party, third_party, federated)",
    )

    # Scoped permissions (subset of delegation permissions)
    # Stored as JSON array for flexibility
    scoped_permissions = Column(
        JSON().with_variant(postgresql.JSONB(), "postgresql"),
        nullable=False,
        default=list,
        comment='Scoped permissions (e.g., ["notion:pages:search"])',
    )

    # MCP sessions - tracks backend connections
    # Format: {"notion": {"session_id": "...", "connected_at": "..."}, ...}
    mcp_sessions = Column(
        JSON().with_variant(postgresql.JSONB(), "postgresql"),
        nullable=False,
        default=dict,
        comment='MCP backend sessions (e.g., {"notion": {"session_id": "..."}})',
    )

    # Authentication challenge (used during auth flow)
    # Cleared after successful verification
    challenge_nonce = Column(
        String(128),
        nullable=True,
        comment="Challenge nonce for authentication (cleared after use)",
    )

    challenge_expires_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Challenge expiration timestamp",
    )

    # Session state
    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether the session is active",
    )

    # Timestamps
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
        comment="Timestamp when the session was created",
    )

    expires_at = Column(
        DateTime(timezone=True),
        default=get_default_expiry,
        nullable=False,
        comment="Timestamp when the session expires (8 hours default)",
    )

    last_activity_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp of last activity",
    )

    revoked_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when the session was revoked",
    )

    # Revocation info
    revoked_by = Column(
        String(128),
        nullable=True,
        comment="Who revoked the session (user, admin, system)",
    )

    revoke_reason = Column(
        String(256),
        nullable=True,
        comment="Reason for revocation",
    )

    # Metadata for JWT claims (denormalized from delegation for performance)
    owner_email = Column(
        String(256),
        nullable=False,
        comment="Owner email (e.g., sarah@acme.com)",
    )

    idp_issuer = Column(
        String(512),
        nullable=True,
        comment="Identity provider issuer (e.g., https://acme.okta.com)",
    )

    groups = Column(
        JSON().with_variant(postgresql.JSONB(), "postgresql"),
        nullable=False,
        default=list,
        comment='User groups (e.g., ["sales"])',
    )

    # Organization context (optional, for multi-tenant)
    organization_id = Column(
        String(64),
        nullable=True,
        index=True,
        comment="Organization identifier for multi-tenant deployments",
    )

    # Network context
    source_ip = Column(
        String(45),
        nullable=True,
        comment="IP address of the authenticating agent (IPv4 or IPv6)",
    )

    # Session provenance
    created_via = Column(
        String(64),
        nullable=True,
        comment="How this session was created (bootstrap_gcp, bootstrap_local, challenge_response)",
    )

    llm_provider = Column(
        String(32),
        nullable=True,
        comment="LLM provider used in this session (gemini, claude, codex) -- updated post-creation",
    )

    # Indexes for efficient lookups
    __table_args__ = (
        Index("ix_agent_session_agent_owner", "agent_id", "owner_email"),
        Index("ix_agent_session_delegation", "delegation_id"),
        Index("ix_agent_session_org", "organization_id"),
    )

    # Relationship to DelegationToken
    delegation = relationship(
        "DelegationToken",
        back_populates="agent_sessions",
        foreign_keys=[delegation_id],
    )

    def _ensure_timezone_aware(self, dt: Optional[datetime]) -> Optional[datetime]:
        """Ensure a datetime is timezone-aware (handles SQLite returning naive datetimes)."""
        if dt is None:
            return None
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt

    @hybrid_property
    def is_expired(self) -> bool:
        """Check if the session has expired."""
        expires_at = self._ensure_timezone_aware(self.expires_at)
        return datetime.now(timezone.utc) >= expires_at

    @hybrid_property
    def is_revoked(self) -> bool:
        """Check if the session has been revoked."""
        return self.revoked_at is not None

    @hybrid_property
    def is_valid(self) -> bool:
        """Check if session is valid (active, not expired, not revoked)."""
        # Handle case where is_active is None (not yet persisted to DB)
        # SQLAlchemy defaults are only applied on insert, not in-memory
        is_active = self.is_active if self.is_active is not None else True
        return is_active and not self.is_expired and not self.is_revoked

    @property
    def challenge_is_valid(self) -> bool:
        """Check if there's a valid pending challenge."""
        if not self.challenge_nonce or not self.challenge_expires_at:
            return False
        challenge_expires = self._ensure_timezone_aware(self.challenge_expires_at)
        return datetime.now(timezone.utc) < challenge_expires

    def set_challenge(self, nonce: str) -> None:
        """Set a new authentication challenge.

        Args:
            nonce: Random nonce for the challenge
        """
        self.challenge_nonce = nonce
        self.challenge_expires_at = datetime.now(timezone.utc) + timedelta(
            seconds=CHALLENGE_TTL_SECONDS
        )

    def clear_challenge(self) -> None:
        """Clear the authentication challenge after use."""
        self.challenge_nonce = None
        self.challenge_expires_at = None

    def revoke(
        self,
        revoked_by: str = "system",
        reason: Optional[str] = None,
    ) -> None:
        """Revoke the agent session.

        Args:
            revoked_by: Who revoked the session
            reason: Optional reason for revocation
        """
        self.is_active = False
        self.revoked_at = datetime.now(timezone.utc)
        self.revoked_by = revoked_by
        self.revoke_reason = reason

    def add_mcp_session(self, backend: str, session_data: Dict[str, Any]) -> None:
        """Track a new MCP backend session.

        Args:
            backend: Backend service identifier (e.g., "notion")
            session_data: Session data to store
        """
        if self.mcp_sessions is None:
            self.mcp_sessions = {}

        # Create a copy to trigger SQLAlchemy change detection
        updated_sessions = dict(self.mcp_sessions)
        updated_sessions[backend] = {
            **session_data,
            "connected_at": datetime.now(timezone.utc).isoformat(),
        }
        self.mcp_sessions = updated_sessions

    def remove_mcp_session(self, backend: str) -> bool:
        """Remove an MCP backend session.

        Args:
            backend: Backend service identifier

        Returns:
            True if removed, False if not found
        """
        if not self.mcp_sessions or backend not in self.mcp_sessions:
            return False

        # Create a copy to trigger SQLAlchemy change detection
        updated_sessions = dict(self.mcp_sessions)
        del updated_sessions[backend]
        self.mcp_sessions = updated_sessions
        return True

    def get_mcp_session(self, backend: str) -> Optional[Dict[str, Any]]:
        """Get MCP session data for a backend.

        Args:
            backend: Backend service identifier

        Returns:
            Session data or None if not found
        """
        if not self.mcp_sessions:
            return None
        return self.mcp_sessions.get(backend)

    def has_permission(self, permission: str) -> bool:
        """Check if session has a specific permission.

        Args:
            permission: Permission string (e.g., "notion:pages:search")

        Returns:
            True if permission is granted
        """
        return permission in (self.scoped_permissions or [])

    def has_all_permissions(self, permissions: List[str]) -> bool:
        """Check if session has all specified permissions.

        Args:
            permissions: List of permission strings

        Returns:
            True if all permissions are granted
        """
        granted = set(self.scoped_permissions or [])
        return all(p in granted for p in permissions)

    def has_any_permission(self, permissions: List[str]) -> bool:
        """Check if session has any of the specified permissions.

        Args:
            permissions: List of permission strings

        Returns:
            True if at least one permission is granted
        """
        granted = set(self.scoped_permissions or [])
        return any(p in granted for p in permissions)

    def touch(self) -> None:
        """Update last activity timestamp."""
        self.last_activity_at = datetime.now(timezone.utc)

    def to_jwt_claims(self) -> Dict[str, Any]:
        """Generate claims for Agent Session JWT (Layer 3).

        Returns:
            Dictionary suitable for JWT encoding
        """
        created_at = self._ensure_timezone_aware(self.created_at)
        expires_at = self._ensure_timezone_aware(self.expires_at)

        return {
            "sub": self.agent_id,
            "session_id": self.id,
            "owner": self.owner_email,
            "idp_issuer": self.idp_issuer,
            "party_type": self.party_type.value if self.party_type else None,
            "delegated_permissions": self.scoped_permissions or [],
            "delegation_id": self.delegation_id,
            "organization_id": self.organization_id,
            "groups": self.groups or [],
            "exp": int(expires_at.timestamp()) if expires_at else None,
            "iat": int(created_at.timestamp()) if created_at else None,
        }

    @classmethod
    def from_delegation(
        cls,
        delegation: "DelegationToken",  # noqa: F821
        agent_id: str,
        party_type: PartyType = PartyType.FIRST_PARTY,
        scoped_permissions: Optional[List[str]] = None,
        groups: Optional[List[str]] = None,
        created_via: Optional[str] = None,
    ) -> "AgentSession":
        """Create an AgentSession from a DelegationToken.

        Convenience method for creating sessions from delegations.

        Args:
            delegation: Parent delegation token
            agent_id: Agent identifier
            party_type: Agent party type
            scoped_permissions: Permissions to grant (defaults to delegation permissions)
            groups: User groups
            created_via: How this session was created (bootstrap_gcp, challenge_response, etc.)

        Returns:
            New AgentSession instance
        """
        return cls(
            agent_id=agent_id,
            delegation_id=delegation.id,
            party_type=party_type,
            scoped_permissions=scoped_permissions or delegation.delegated_permissions,
            owner_email=delegation.delegator,
            idp_issuer=delegation.delegator_idp,
            groups=groups or [],
            organization_id=delegation.organization_id,
            created_via=created_via,
        )

    def __repr__(self) -> str:
        """Return a string representation of the AgentSession."""
        status = "valid" if self.is_valid else (
            "revoked" if self.is_revoked else (
                "expired" if self.is_expired else "inactive"
            )
        )
        return (
            f"<AgentSession(id='{self.id}', "
            f"agent_id='{self.agent_id}', "
            f"owner='{self.owner_email}', "
            f"status='{status}')>"
        )
