"""SQLAlchemy model for Connected Service entities.

Connected services represent OAuth connections between a user and backend services
(Notion, Slack, etc.). The actual OAuth tokens are stored in vault;
this model only stores references to those tokens.
"""

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import Column, DateTime, Index, String, UniqueConstraint, func
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy import JSON

from app.db.base import Base


def generate_connection_id() -> str:
    """Generate a unique connection ID."""
    return f"conn-{uuid.uuid4()}"


class ConnectedService(Base):
    """Represents a user's OAuth connection to a backend service.

    This model tracks which services a user has connected via OAuth,
    the scopes they granted, and references to their OAuth tokens
    (stored securely in vault, not in this table).

    Example:
        Sarah connects Notion → DeepTrail stores:
        - service_id: "notion"
        - scopes_granted: ["read_content", "search", "create_pages"]
        - oauth_token_ref: "vault://sarah-notion-oauth-xyz"

    The agent can later use Sarah's credentials (via delegation) to access
    Notion on her behalf.
    """

    __tablename__ = "connected_services"

    # Primary key - unique connection identifier
    id = Column(
        String(64),
        primary_key=True,
        default=generate_connection_id,
        comment="Unique connection identifier (e.g., conn-<uuid>)",
    )

    # User association - matches user_id from UserSession
    user_id = Column(
        String(255),
        nullable=False,
        index=True,
        comment="User identifier, typically email (e.g., sarah@acme.com)",
    )

    # Service identification
    service_id = Column(
        String(64),
        nullable=False,
        index=True,
        comment="Backend service identifier (e.g., notion, slack)",
    )

    service_name = Column(
        String(128),
        nullable=True,
        comment="Human-readable service name (e.g., Notion, Slack)",
    )

    # OAuth token reference - stored in vault, NOT here
    # Format: vault://{user}-{service}-{unique-id}
    oauth_token_ref = Column(
        String(512),
        nullable=False,
        comment="Reference to OAuth token in vault (e.g., vault://sarah-notion-oauth-xyz)",
    )

    # Scopes granted by user during OAuth consent
    # Stored as JSON array for flexibility
    scopes_granted = Column(
        JSON().with_variant(postgresql.JSONB(), "postgresql"),
        nullable=False,
        default=list,
        comment='Scopes granted during OAuth consent (e.g., ["read_content", "search"])',
    )

    # Organization context (optional, for multi-tenant)
    organization_id = Column(
        String(64),
        nullable=True,
        index=True,
        comment="Organization identifier for multi-tenant deployments",
    )

    # Timestamps
    connected_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
        comment="Timestamp when the service was connected",
    )

    disconnected_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when the service was disconnected (NULL if still connected)",
    )

    # Last used timestamp (for audit and cleanup)
    last_used_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when this connection was last used",
    )

    # Unique constraint: one active connection per service per user
    __table_args__ = (
        UniqueConstraint("user_id", "service_id", name="uq_user_service"),
        Index("ix_connected_service_user_service", "user_id", "service_id"),
        Index("ix_connected_service_org", "organization_id"),
    )

    def _ensure_timezone_aware(self, dt: Optional[datetime]) -> Optional[datetime]:
        """Ensure a datetime is timezone-aware (handles SQLite returning naive datetimes)."""
        if dt is None:
            return None
        if dt.tzinfo is None:
            # Assume UTC for naive datetimes from database
            return dt.replace(tzinfo=timezone.utc)
        return dt

    @hybrid_property
    def is_active(self) -> bool:
        """Check if the connection is still active (not disconnected)."""
        return self.disconnected_at is None

    def has_scope(self, scope: str) -> bool:
        """Check if a specific scope was granted.

        Args:
            scope: The scope to check for (e.g., "read_content")

        Returns:
            True if the scope was granted, False otherwise
        """
        return scope in (self.scopes_granted or [])

    def has_all_scopes(self, scopes: List[str]) -> bool:
        """Check if all specified scopes were granted.

        Args:
            scopes: List of scopes to check for

        Returns:
            True if all scopes were granted, False otherwise
        """
        granted = set(self.scopes_granted or [])
        return all(s in granted for s in scopes)

    def has_any_scope(self, scopes: List[str]) -> bool:
        """Check if any of the specified scopes were granted.

        Args:
            scopes: List of scopes to check for

        Returns:
            True if at least one scope was granted, False otherwise
        """
        granted = set(self.scopes_granted or [])
        return any(s in granted for s in scopes)

    def disconnect(self) -> None:
        """Mark the connection as disconnected."""
        self.disconnected_at = datetime.now(timezone.utc)

    def record_usage(self) -> None:
        """Update the last_used_at timestamp."""
        self.last_used_at = datetime.now(timezone.utc)

    @classmethod
    def create_token_ref(cls, user_id: str, service_id: str) -> str:
        """Generate a vault token reference for a new connection.

        Args:
            user_id: The user identifier
            service_id: The service identifier

        Returns:
            A vault reference string (e.g., "vault://sarah-notion-oauth-abc123")
        """
        # Sanitize user_id for use in reference (take part before @)
        user_part = user_id.split("@")[0] if "@" in user_id else user_id
        unique_id = str(uuid.uuid4())[:8]
        return f"vault://{user_part}-{service_id}-oauth-{unique_id}"

    def __repr__(self) -> str:
        """Return a string representation of the ConnectedService."""
        status = "active" if self.is_active else "disconnected"
        return (
            f"<ConnectedService(id='{self.id}', "
            f"user_id='{self.user_id}', "
            f"service_id='{self.service_id}', "
            f"status='{status}')>"
        )
