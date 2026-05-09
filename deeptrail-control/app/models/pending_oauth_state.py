"""SQLAlchemy model for transient OAuth PKCE state.

Stores the in-flight state for the Authorization Code + PKCE flow between
the /authorize redirect and the /callback. Replaces the in-memory
_pending_sso dict, ensuring OAuth flows survive pod restarts.

Each row expires after 5 minutes and is consumed (deleted) on callback.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import Column, DateTime, String, Text, func

from app.db.base import Base

DEFAULT_TTL_SECONDS = 300  # 5 minutes — matches PendingSSO.expires_in


def _default_expires_at() -> datetime:
    return datetime.now(timezone.utc) + timedelta(seconds=DEFAULT_TTL_SECONDS)


class PendingOAuthState(Base):
    """One row per in-flight OAuth Authorization Code flow.

    Created in /authorize, consumed (deleted) in /callback.
    Rows that are never consumed expire and can be purged lazily.
    """

    __tablename__ = "pending_oauth_states"

    state = Column(
        String(128),
        primary_key=True,
        comment="OAuth state parameter (random, URL-safe)",
    )
    idp = Column(
        String(32),
        nullable=False,
        comment="Identity provider: google | keycloak | etc.",
    )
    redirect_uri = Column(
        Text,
        nullable=False,
        comment="Callback URI passed to the IdP",
    )
    code_verifier = Column(
        Text,
        nullable=True,
        comment="PKCE code_verifier (S256); NULL if PKCE not used",
    )
    post_login_redirect = Column(
        Text,
        nullable=True,
        comment="Frontend URL to redirect to after successful login",
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        comment="When this pending state was created",
    )
    expires_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=_default_expires_at,
        comment="When this state expires (5 minutes after creation)",
    )

    def _ensure_tz(self, dt: datetime) -> datetime:
        if dt is None:
            return None
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

    @property
    def is_expired(self) -> bool:
        expires = self._ensure_tz(self.expires_at)
        return datetime.now(timezone.utc) > expires

    def __repr__(self) -> str:
        return (
            f"<PendingOAuthState(state='{self.state[:8]}...', "
            f"idp='{self.idp}', expired={self.is_expired})>"
        )
