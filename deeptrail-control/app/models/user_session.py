"""SQLAlchemy model for User Session entities.

User sessions represent authenticated human users in the DeepTrail Control Plane.
They are the foundation for connected services, delegations, and agent sessions.
"""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import Column, DateTime, String, Text, func
from sqlalchemy.ext.hybrid import hybrid_property

from app.db.base import Base

# Default session duration (8 hours work day)
DEFAULT_SESSION_DURATION_HOURS = 8


def generate_session_id() -> str:
    """Generate a unique, URL-safe session ID."""
    return f"usess-{uuid.uuid4()}"


def get_default_expiry() -> datetime:
    """Calculate default session expiry (8 hours from now)."""
    return datetime.now(timezone.utc) + timedelta(hours=DEFAULT_SESSION_DURATION_HOURS)


class UserSession(Base):
    """Represents an authenticated user session in the database.

    User sessions are created when a human user authenticates via their
    identity provider (IdP). The session tracks:
    - User identity (email, IdP issuer)
    - Organization context (for multi-tenant support)
    - Session lifecycle (creation, expiry)

    Connected services and delegations are linked via relationships
    (to be implemented in subsequent tasks A3, A5).
    """

    __tablename__ = "user_sessions"

    # Primary key - cryptographically random, URL-safe identifier
    session_id = Column(
        String(64),
        primary_key=True,
        default=generate_session_id,
        index=True,
        comment="Unique session identifier (e.g., usess-<uuid>)",
    )

    # User identity
    user_id = Column(
        String(255),
        nullable=False,
        index=True,
        comment="User identifier, typically email (e.g., sarah@acme.com)",
    )

    idp_issuer = Column(
        String(512),
        nullable=False,
        comment="Identity provider issuer URL (e.g., https://acme.okta.com)",
    )

    # Multi-tenant support
    organization_id = Column(
        String(64),
        nullable=True,
        index=True,
        comment="Organization identifier for multi-tenant deployments",
    )

    # Session lifecycle
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
        comment="Timestamp when the session expires (default: 8 hours after creation)",
    )

    revoked_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when the session was explicitly revoked (NULL if active)",
    )

    # Optional metadata for extensibility
    idp_metadata = Column(
        Text,
        nullable=True,
        comment="Optional JSON metadata from the IdP (claims, groups, etc.)",
    )

    # Relationships (to be populated by later tasks - A3, A5)
    # connected_services = relationship("ConnectedService", back_populates="user_session")
    # delegations = relationship("Delegation", back_populates="user_session")

    def _ensure_timezone_aware(self, dt: datetime) -> datetime:
        """Ensure a datetime is timezone-aware (handles SQLite returning naive datetimes)."""
        if dt is None:
            return None
        if dt.tzinfo is None:
            # Assume UTC for naive datetimes from database
            return dt.replace(tzinfo=timezone.utc)
        return dt

    @hybrid_property
    def is_expired(self) -> bool:
        """Check if the session has expired based on expires_at timestamp."""
        expires_at = self._ensure_timezone_aware(self.expires_at)
        return datetime.now(timezone.utc) > expires_at

    @hybrid_property
    def is_revoked(self) -> bool:
        """Check if the session has been explicitly revoked."""
        return self.revoked_at is not None

    @hybrid_property
    def is_active(self) -> bool:
        """Check if the session is still active (not expired and not revoked)."""
        return not self.is_expired and not self.is_revoked

    def __repr__(self) -> str:
        """Return a string representation of the UserSession."""
        return (
            f"<UserSession(session_id='{self.session_id}', "
            f"user_id='{self.user_id}', "
            f"expires_at='{self.expires_at}')>"
        )
