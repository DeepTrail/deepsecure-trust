"""Service for managing encrypted IdP session token storage.

Provides CRUD operations over IdP sessions with Fernet-encrypted
refresh and access tokens. All encryption/decryption happens in
this service layer, not in the model.

Security properties:
- Tokens encrypted at rest using Fernet (AES-128-CBC + HMAC)
- Encryption key loaded from VAULT_ENCRYPTION_KEY env var
- No plaintext tokens in logs
- Revoked/expired sessions filtered from queries
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.idp_session import IdPSession
from app.services.idp_service import OIDCTokens

logger = logging.getLogger(__name__)

ENV_KEY_NAME = "VAULT_ENCRYPTION_KEY"


class IdPSessionService:
    """CRUD service for IdP sessions with Fernet-encrypted token storage."""

    def __init__(self, db: Session, encryption_key: str | None = None):
        self.db = db
        key = encryption_key or os.environ.get(ENV_KEY_NAME)
        if not key:
            logger.warning(
                "No encryption key provided. Generating ephemeral key. "
                "Set %s environment variable for production.",
                ENV_KEY_NAME,
            )
            key = Fernet.generate_key().decode()
        key_bytes = key.encode() if isinstance(key, str) else key
        self._fernet = Fernet(key_bytes)

    # ------------------------------------------------------------------
    # Store
    # ------------------------------------------------------------------

    def store(
        self,
        session_id: str,
        user_id: str,
        idp: str,
        tokens: OIDCTokens,
        id_token_claims: dict | None = None,
    ) -> IdPSession:
        """Create new IdP session with encrypted tokens.

        Args:
            session_id: DeepTrail JWT session_id claim.
            user_id: User identifier (email).
            idp: Provider name ("google" or "keycloak").
            tokens: OIDCTokens from authentication.
            id_token_claims: Optional cached ID token claims dict.

        Returns:
            Created IdPSession instance.

        Raises:
            SQLAlchemyError: If database operation fails.
        """
        try:
            encrypted_refresh = None
            if tokens.refresh_token:
                encrypted_refresh = self._fernet.encrypt(
                    tokens.refresh_token.encode()
                ).decode()

            encrypted_access = self._fernet.encrypt(
                tokens.access_token.encode()
            ).decode()

            idp_session = IdPSession(
                id=str(uuid.uuid4()),
                session_id=session_id,
                user_id=user_id,
                idp=idp,
                encrypted_refresh_token=encrypted_refresh,
                encrypted_access_token=encrypted_access,
                id_token_claims=id_token_claims,
            )

            self.db.add(idp_session)
            self.db.commit()
            self.db.refresh(idp_session)

            logger.info(
                "Stored IdP session: session_id=%s, user_id=%s, idp=%s",
                session_id,
                user_id,
                idp,
            )
            return idp_session

        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error("Failed to store IdP session for %s: %s", user_id, e)
            raise

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_by_session(self, session_id: str) -> IdPSession | None:
        """Lookup by DeepTrail session_id. Returns None if revoked or not found."""
        try:
            result = self.db.execute(
                select(IdPSession).where(
                    IdPSession.session_id == session_id,
                    IdPSession.revoked == False,  # noqa: E712
                )
            )
            return result.scalar_one_or_none()
        except SQLAlchemyError as e:
            logger.error("Error retrieving IdP session %s: %s", session_id, e)
            raise

    def get_decrypted_tokens(self, session_id: str) -> dict | None:
        """Decrypt and return tokens for a session.

        Returns:
            ``{"refresh_token": str | None, "access_token": str}``
            or ``None`` if session not found or decryption fails.
        """
        idp_session = self.get_by_session(session_id)
        if idp_session is None:
            return None

        try:
            access_token = self._fernet.decrypt(
                idp_session.encrypted_access_token.encode()
            ).decode()

            refresh_token = None
            if idp_session.encrypted_refresh_token:
                refresh_token = self._fernet.decrypt(
                    idp_session.encrypted_refresh_token.encode()
                ).decode()

            return {
                "refresh_token": refresh_token,
                "access_token": access_token,
            }
        except InvalidToken as e:
            logger.error(
                "Failed to decrypt tokens for session %s: %s", session_id, e
            )
            return None

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    def refresh(self, session_id: str, new_tokens: OIDCTokens) -> IdPSession:
        """Update encrypted tokens and refreshed_at timestamp.

        Raises:
            ValueError: If session not found or revoked.
            SQLAlchemyError: If database operation fails.
        """
        idp_session = self.get_by_session(session_id)
        if idp_session is None:
            raise ValueError(f"IdP session not found or revoked: {session_id}")

        try:
            idp_session.encrypted_access_token = self._fernet.encrypt(
                new_tokens.access_token.encode()
            ).decode()

            if new_tokens.refresh_token:
                idp_session.encrypted_refresh_token = self._fernet.encrypt(
                    new_tokens.refresh_token.encode()
                ).decode()

            idp_session.refreshed_at = datetime.now(timezone.utc)
            self.db.commit()
            self.db.refresh(idp_session)

            logger.info("Refreshed IdP session: session_id=%s", session_id)
            return idp_session

        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error("Failed to refresh IdP session %s: %s", session_id, e)
            raise

    # ------------------------------------------------------------------
    # Revoke
    # ------------------------------------------------------------------

    def revoke(self, session_id: str) -> bool:
        """Set revoked=True for a session. Returns True on success, False if not found."""
        try:
            result = self.db.execute(
                select(IdPSession).where(IdPSession.session_id == session_id)
            )
            idp_session = result.scalar_one_or_none()
            if idp_session is None:
                logger.warning("Cannot revoke non-existent IdP session: %s", session_id)
                return False

            if idp_session.revoked:
                return True

            idp_session.revoked = True
            self.db.commit()
            logger.info("Revoked IdP session: session_id=%s", session_id)
            return True

        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error("Failed to revoke IdP session %s: %s", session_id, e)
            raise

    def revoke_all_for_user(self, user_id: str) -> int:
        """Revoke all active sessions for a user. Returns count revoked."""
        try:
            result = self.db.execute(
                select(IdPSession).where(
                    IdPSession.user_id == user_id,
                    IdPSession.revoked == False,  # noqa: E712
                )
            )
            sessions = list(result.scalars().all())
            count = 0
            for session in sessions:
                session.revoked = True
                count += 1

            self.db.commit()
            logger.info("Revoked %d IdP sessions for user %s", count, user_id)
            return count

        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error("Failed to revoke sessions for user %s: %s", user_id, e)
            raise

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def cleanup_expired(self) -> int:
        """Delete expired and revoked sessions. Returns count deleted."""
        try:
            now = datetime.now(timezone.utc)
            result = self.db.execute(
                select(IdPSession).where(
                    (IdPSession.revoked == True)  # noqa: E712
                    | (
                        (IdPSession.expires_at != None)  # noqa: E711
                        & (IdPSession.expires_at < now)
                    )
                )
            )
            sessions = list(result.scalars().all())
            count = len(sessions)
            for session in sessions:
                self.db.delete(session)

            self.db.commit()
            logger.info("Cleaned up %d expired/revoked IdP sessions", count)
            return count

        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error("Failed to cleanup expired IdP sessions: %s", e)
            raise
