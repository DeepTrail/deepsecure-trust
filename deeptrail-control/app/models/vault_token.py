"""SQLAlchemy model for encrypted OAuth token storage.

This model provides persistent storage for OAuth tokens with Fernet encryption.
The actual token data (access_token, refresh_token, etc.) is encrypted; only
metadata is stored in plaintext for queries.

Security properties:
- Token data encrypted using VAULT_ENCRYPTION_KEY (Fernet/AES-128-CBC + HMAC)
- Encryption key never stored in database
- Token ref is opaque (no sensitive data in ref string)
- SQL injection prevented (using ORM)
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Column, DateTime, Index, Integer, LargeBinary, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON

from app.db.base import Base


class VaultToken(Base):
    """Encrypted OAuth token storage.

    Stores OAuth tokens with Fernet encryption. The actual token data
    (access_token, refresh_token, etc.) is encrypted; only metadata
    is stored in plaintext for queries.

    Example:
        vault_token = VaultToken(
            token_ref="vault://sarah-notion-abc123",
            user_id="sarah@acme.com",
            service_id="notion",
            encrypted_data=fernet.encrypt(json.dumps(token_data).encode()),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )

    The token_ref is used by ConnectedService.oauth_token_ref to reference
    this token without foreign key constraint (implicit relationship).
    """

    __tablename__ = "vault_tokens"

    # Primary key - the vault reference (e.g., vault://sarah-notion-abc123)
    token_ref = Column(
        String(512),
        primary_key=True,
        comment="Vault reference (e.g., vault://sarah-notion-abc123)",
    )

    # Ownership - who owns this token
    user_id = Column(
        String(255),
        nullable=False,
        index=True,
        comment="User identifier (e.g., sarah@acme.com)",
    )

    # Service identification
    service_id = Column(
        String(64),
        nullable=False,
        index=True,
        comment="Service identifier (e.g., notion, slack, hubspot)",
    )

    # Encrypted token data (Fernet-encrypted JSON)
    encrypted_data = Column(
        LargeBinary,
        nullable=False,
        comment="Fernet-encrypted OAuth token JSON",
    )

    # Timestamps and metadata (plaintext for queries)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
        comment="When token was stored",
    )

    expires_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Token expiration (NULL = no expiry)",
    )

    last_used_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last retrieval timestamp",
    )

    refresh_count = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of times token was refreshed",
    )

    last_refreshed_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp of last successful proactive refresh",
    )

    refresh_log = Column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=True,
        default=list,
        comment="Last N refresh events [{timestamp, status, latency_ms, error}]",
    )

    # Indexes for common queries
    __table_args__ = (
        Index("ix_vault_token_user_service", "user_id", "service_id"),
        Index("ix_vault_token_expires", "expires_at"),
    )

    def _ensure_timezone_aware(self, dt: Optional[datetime]) -> Optional[datetime]:
        """Ensure a datetime is timezone-aware (handles SQLite returning naive datetimes)."""
        if dt is None:
            return None
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt

    @property
    def is_expired(self) -> bool:
        """Check if the token has expired.

        Returns:
            True if expires_at is set and is in the past, False otherwise.
        """
        if self.expires_at is None:
            return False
        expires_at = self._ensure_timezone_aware(self.expires_at)
        return expires_at <= datetime.now(timezone.utc)

    def record_usage(self) -> None:
        """Update the last_used_at timestamp."""
        self.last_used_at = datetime.now(timezone.utc)

    def increment_refresh_count(self) -> None:
        """Increment the refresh count."""
        self.refresh_count = (self.refresh_count or 0) + 1

    def __repr__(self) -> str:
        """Return a string representation of the VaultToken."""
        status = "expired" if self.is_expired else "active"
        return (
            f"<VaultToken(token_ref='{self.token_ref[:30]}...', "
            f"user_id='{self.user_id}', "
            f"service_id='{self.service_id}', "
            f"status='{status}')>"
        )
