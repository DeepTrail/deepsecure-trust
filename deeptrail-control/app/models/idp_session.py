"""SQLAlchemy model for server-side IdP session storage.

Stores encrypted IdP refresh and access tokens so that DeepTrail can silently
renew user sessions without re-authenticating through the IdP.

Security properties:
- Refresh and access tokens stored with Fernet encryption (AES-128-CBC + HMAC).
- Encryption / decryption is NOT performed in this model — that responsibility
  belongs to ``IdPSessionService`` (WS-B2) which holds the encryption key.
- The ``encrypted_*`` columns store Fernet ciphertext as UTF-8 text (base64).
- ``id_token_claims`` stores non-sensitive, already-public claims extracted
  from the ID token (sub, email, groups, etc.).
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import JSON, Boolean, Column, DateTime, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB

from app.db.base import Base


class IdPSession(Base):
    """Encrypted IdP session for offline access / silent refresh.

    One row per DeepTrail login session.  Linked to the DeepTrail JWT via
    ``session_id`` (the ``session_id`` claim inside the JWT).

    Example::

        session = IdPSession(
            id=uuid4().hex,
            session_id="jwt-session-abc123",
            user_id="sarah@acme.com",
            idp="google",
            encrypted_refresh_token=fernet.encrypt(refresh_token.encode()).decode(),
            encrypted_access_token=fernet.encrypt(access_token.encode()).decode(),
            id_token_claims={"sub": "1234", "email": "sarah@acme.com"},
        )
    """

    __tablename__ = "idp_sessions"

    id = Column(
        String(64),
        primary_key=True,
        comment="UUID generated in Python",
    )
    session_id = Column(
        String(128),
        nullable=False,
        unique=True,
        comment="Links to DeepTrail JWT session_id claim",
    )
    user_id = Column(
        String(255),
        nullable=False,
        comment="User email / identifier",
    )
    idp = Column(
        String(32),
        nullable=False,
        comment="Identity provider: keycloak | google",
    )

    encrypted_refresh_token = Column(
        Text,
        nullable=True,
        comment="Fernet-encrypted IdP refresh token",
    )
    encrypted_access_token = Column(
        Text,
        nullable=True,
        comment="Fernet-encrypted IdP access token",
    )
    id_token_claims = Column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=True,
        comment="Cached claims dict from the ID token",
    )

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        comment="Row creation timestamp",
    )
    refreshed_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last successful token refresh timestamp",
    )
    expires_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Refresh token expiry (NULL = unknown / no expiry)",
    )
    revoked = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        comment="Set to true on logout to prevent further refreshes",
    )

    __table_args__ = (
        Index("ix_idp_session_session_id", "session_id", unique=True),
        Index("ix_idp_session_user_id", "user_id"),
        Index("ix_idp_session_idp", "idp"),
    )

    # ------------------------------------------------------------------
    # Helper properties
    # ------------------------------------------------------------------

    @property
    def is_revoked(self) -> bool:
        """Whether this session has been explicitly revoked (e.g. on logout)."""
        return self.revoked

    def _ensure_timezone_aware(self, dt: Optional[datetime]) -> Optional[datetime]:
        """Ensure a datetime is timezone-aware (handles SQLite returning naive datetimes)."""
        if dt is None:
            return None
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt

    @property
    def is_expired(self) -> bool:
        """Whether the refresh token has expired.

        Returns ``False`` if ``expires_at`` is ``None`` (unknown expiry).
        """
        if self.expires_at is None:
            return False
        expires_at = self._ensure_timezone_aware(self.expires_at)
        return expires_at <= datetime.now(timezone.utc)

    def __repr__(self) -> str:
        status = "revoked" if self.is_revoked else ("expired" if self.is_expired else "active")
        return (
            f"<IdPSession(id='{self.id}', "
            f"session_id='{self.session_id}', "
            f"user_id='{self.user_id}', "
            f"idp='{self.idp}', "
            f"status='{status}')>"
        )
