"""SQLAlchemy model for Delegation Token entities.

Delegation tokens represent Layer 2 of the three-layer token architecture.
They capture what permissions a user grants to a specific agent, along with
constraints and binding information.

Key principles:
- Monotonic Attenuation: Agent permissions ⊂ User's permissions
- Bounded Delegation: Time-limited with explicit expiration
- Constraint Enforcement: Rate limits, action caps
- Revocability: User can revoke at any time
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import Column, DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy import JSON
from sqlalchemy.orm import relationship

from app.db.base import Base

# Default delegation duration (7 days as per design doc)
DEFAULT_DELEGATION_DURATION_DAYS = 7


def generate_delegation_id() -> str:
    """Generate a unique delegation ID."""
    return f"del-{uuid.uuid4()}"


def get_default_expiry() -> datetime:
    """Calculate default delegation expiry (7 days from now)."""
    return datetime.now(timezone.utc) + timedelta(days=DEFAULT_DELEGATION_DURATION_DAYS)


class DelegationToken(Base):
    """Represents a user's delegation of permissions to an agent.

    This is Layer 2 of the three-layer token architecture:
    - Layer 1: User Session (human identity)
    - Layer 2: Delegation Token (permission grant to agent) <- THIS
    - Layer 3: Agent Session (ephemeral agent context)

    Example from design doc:
        Sarah delegates to SDR agent:
        - agent_id: "agent-sdr-001"
        - delegator: "sarah@acme.com"
        - delegated_permissions: ["notion:pages:search", "slack:messages:search"]
        - constraints: {"max_actions_per_day": 100}
        - expires: 7 days
    """

    __tablename__ = "delegation_tokens"

    # Primary key - unique delegation identifier
    id = Column(
        String(64),
        primary_key=True,
        default=generate_delegation_id,
        comment="Unique delegation identifier (e.g., del-<uuid>)",
    )

    # Agent receiving delegation (Layer 2 "sub" in JWT)
    agent_id = Column(
        String(64),
        nullable=False,
        index=True,
        comment="Agent identifier receiving the delegation (e.g., agent-sdr-001)",
    )

    # User granting delegation (Layer 2 "delegator" in JWT)
    delegator = Column(
        String(255),
        nullable=False,
        index=True,
        comment="User identifier granting delegation (e.g., sarah@acme.com)",
    )

    delegator_idp = Column(
        String(512),
        nullable=True,
        comment="Identity provider of the delegator (e.g., https://acme.okta.com)",
    )

    # Token binding - cryptographic link to user and agent identity
    user_token_hash = Column(
        String(128),
        nullable=True,
        comment="Hash binding to user's identity token (sha256:...)",
    )

    agent_token_hash = Column(
        String(128),
        nullable=True,
        comment="Hash binding to agent's identity token (sha256:...)",
    )

    # Delegated permissions (subset of user's permissions)
    # Format: {service}:{resource}:{action} (e.g., "notion:pages:search")
    delegated_permissions = Column(
        JSON().with_variant(postgresql.JSONB(), "postgresql"),
        nullable=False,
        default=list,
        comment='Delegated permissions (e.g., ["notion:pages:search", "slack:messages:search"])',
    )

    # Constraints on delegation
    constraints = Column(
        JSON().with_variant(postgresql.JSONB(), "postgresql"),
        nullable=False,
        default=dict,
        comment='Delegation constraints (e.g., {"max_actions_per_day": 100})',
    )

    # Organization context (optional, for multi-tenant)
    organization_id = Column(
        String(64),
        nullable=True,
        index=True,
        comment="Organization identifier for multi-tenant deployments",
    )

    template_id = Column(
        String(36),
        ForeignKey("delegation_templates.id", ondelete="SET NULL"),
        nullable=True,
        comment="Delegation template that constrained this delegation",
    )

    source = Column(
        String(20),
        nullable=False,
        server_default="manual",
        comment="How this delegation was created: 'manual', 'template', 'invite', 'admin'",
    )

    status = Column(
        String(20),
        nullable=False,
        server_default="active",
        comment="Lifecycle status: pending, active, revoked, expired",
    )

    # Lifecycle timestamps
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
        comment="Timestamp when the delegation was created",
    )

    expires_at = Column(
        DateTime(timezone=True),
        default=get_default_expiry,
        nullable=False,
        comment="Timestamp when the delegation expires (REQUIRED - no indefinite delegations)",
    )

    revoked_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when the delegation was revoked (NULL if active)",
    )

    # URIs for audit and revocation
    logging_uri = Column(
        String(512),
        nullable=True,
        comment="URI for audit logging (e.g., https://audit.deeptrail.io/log)",
    )

    revocation_uri = Column(
        String(512),
        nullable=True,
        comment="URI for revocation endpoint (e.g., https://deeptrail.io/revoke/...)",
    )

    # Indexes for efficient lookups
    __table_args__ = (
        Index("ix_delegation_agent_delegator", "agent_id", "delegator"),
        Index("ix_delegation_delegator_time", "delegator", "created_at"),
        Index("ix_delegation_org", "organization_id"),
    )

    # Relationship to AgentSession (one delegation can have many sessions)
    agent_sessions = relationship(
        "AgentSession",
        back_populates="delegation",
        cascade="all, delete-orphan",
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
        """Check if the delegation has expired."""
        expires_at = self._ensure_timezone_aware(self.expires_at)
        return datetime.now(timezone.utc) >= expires_at

    @hybrid_property
    def is_revoked(self) -> bool:
        """Check if the delegation has been revoked."""
        return self.revoked_at is not None

    @hybrid_property
    def is_valid(self) -> bool:
        """Check if the delegation is currently valid (not expired, not revoked)."""
        return not self.is_expired and not self.is_revoked

    def has_permission(self, permission: str) -> bool:
        """Check if a specific permission is delegated.

        Args:
            permission: Permission string (e.g., "notion:pages:search")

        Returns:
            True if the permission is delegated, False otherwise
        """
        return permission in (self.delegated_permissions or [])

    def has_all_permissions(self, permissions: List[str]) -> bool:
        """Check if all specified permissions are delegated.

        Args:
            permissions: List of permission strings

        Returns:
            True if all permissions are delegated, False otherwise
        """
        granted = set(self.delegated_permissions or [])
        return all(p in granted for p in permissions)

    def has_any_permission(self, permissions: List[str]) -> bool:
        """Check if any of the specified permissions are delegated.

        Args:
            permissions: List of permission strings

        Returns:
            True if at least one permission is delegated, False otherwise
        """
        granted = set(self.delegated_permissions or [])
        return any(p in granted for p in permissions)

    def get_permissions_for_service(self, service: str) -> List[str]:
        """Get all delegated permissions for a specific service.

        Args:
            service: Service identifier (e.g., "notion", "slack")

        Returns:
            List of permissions for that service
        """
        return [
            p for p in (self.delegated_permissions or [])
            if p.startswith(f"{service}:")
        ]

    def get_constraint(self, key: str, default: Any = None) -> Any:
        """Get a constraint value by key.

        Args:
            key: Constraint key (e.g., "max_actions_per_day")
            default: Default value if constraint not set

        Returns:
            Constraint value or default
        """
        return (self.constraints or {}).get(key, default)

    def revoke(self) -> None:
        """Revoke this delegation immediately."""
        self.revoked_at = datetime.now(timezone.utc)
        self.status = "revoked"

    def sync_status(self) -> None:
        """Keep persisted status aligned with revocation/expiry timestamps."""
        if self.revoked_at is not None:
            self.status = "revoked"
        elif self.is_expired:
            self.status = "expired"
        elif self.status not in ("pending", "active"):
            self.status = "active"

    def to_claims_dict(self) -> Dict[str, Any]:
        """Serialize to JWT-compatible claims dictionary.

        Returns:
            Dictionary suitable for JWT encoding (Layer 2 token format)
        """
        created_at = self._ensure_timezone_aware(self.created_at)
        expires_at = self._ensure_timezone_aware(self.expires_at)

        return {
            "jti": self.id,  # JWT ID
            "sub": self.agent_id,
            "delegator": self.delegator,
            "delegator_idp": self.delegator_idp,
            "user_token_hash": self.user_token_hash,
            "agent_token_hash": self.agent_token_hash,
            "delegated_permissions": self.delegated_permissions,
            "constraints": self.constraints,
            "iat": int(created_at.timestamp()) if created_at else None,
            "exp": int(expires_at.timestamp()) if expires_at else None,
            "logging_uri": self.logging_uri,
            "revocation_uri": self.revocation_uri,
        }

    @classmethod
    def from_claims_dict(cls, claims: Dict[str, Any]) -> "DelegationToken":
        """Create a DelegationToken from JWT claims dictionary.

        Args:
            claims: JWT claims dictionary

        Returns:
            DelegationToken instance
        """
        return cls(
            id=claims.get("jti") or generate_delegation_id(),
            agent_id=claims["sub"],
            delegator=claims["delegator"],
            delegator_idp=claims.get("delegator_idp"),
            user_token_hash=claims.get("user_token_hash"),
            agent_token_hash=claims.get("agent_token_hash"),
            delegated_permissions=claims.get("delegated_permissions", []),
            constraints=claims.get("constraints", {}),
            created_at=datetime.fromtimestamp(claims["iat"], tz=timezone.utc)
            if claims.get("iat") else datetime.now(timezone.utc),
            expires_at=datetime.fromtimestamp(claims["exp"], tz=timezone.utc)
            if claims.get("exp") else get_default_expiry(),
            logging_uri=claims.get("logging_uri"),
            revocation_uri=claims.get("revocation_uri"),
        )

    def generate_revocation_uri(self, base_url: str = "https://deeptrail.io") -> str:
        """Generate a revocation URI for this delegation.

        Args:
            base_url: Base URL for the revocation endpoint

        Returns:
            Revocation URI string
        """
        return f"{base_url}/revoke/{self.id}"

    def __repr__(self) -> str:
        """Return a string representation of the DelegationToken."""
        status = "valid" if self.is_valid else ("revoked" if self.is_revoked else "expired")
        return (
            f"<DelegationToken(id='{self.id}', "
            f"delegator='{self.delegator}', "
            f"agent_id='{self.agent_id}', "
            f"status='{status}')>"
        )
