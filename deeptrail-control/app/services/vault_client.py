"""Secure OAuth token vault storage with PostgreSQL persistence.

This module provides encrypted storage for OAuth tokens using PostgreSQL
for persistence. Tokens survive container restarts.

Security properties:
- Tokens are encrypted at rest using Fernet (AES-128-CBC + HMAC)
- Encryption key is loaded from environment (never hardcoded)
- Token references are opaque (no token data in reference string)
- No token data appears in logs
- SQL injection prevented via SQLAlchemy ORM

Token lifecycle features:
- Expiration tracking (expires_at timestamp)
- Usage tracking (last_used_at timestamp)
- Refresh support (refresh_token, refresh_count)
- Expiring token identification (get_expiring_tokens)
- User token cleanup (delete_user_tokens)
"""

import json
import logging
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.orm import Session

from app.services.cache_events import (
    publish_token_stored,
    publish_token_updated,
    publish_token_deleted,
)

logger = logging.getLogger(__name__)


@dataclass
class TokenMetadata:
    """Metadata for tracking token lifecycle.

    Attributes:
        created_at: When the token was stored (UTC).
        expires_at: When the token expires (UTC), or None if no expiration.
        last_used_at: When the token was last retrieved (UTC), or None if never used.
        refresh_count: Number of times the token has been refreshed.
    """

    created_at: datetime
    expires_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None
    refresh_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict with ISO format timestamps."""
        return {
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
            "refresh_count": self.refresh_count,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TokenMetadata":
        """Create from dict with ISO format timestamps."""
        return cls(
            created_at=datetime.fromisoformat(data["created_at"]),
            expires_at=datetime.fromisoformat(data["expires_at"]) if data.get("expires_at") else None,
            last_used_at=datetime.fromisoformat(data["last_used_at"]) if data.get("last_used_at") else None,
            refresh_count=data.get("refresh_count", 0),
        )


@dataclass
class StoredTokenData:
    """Complete token with metadata.

    Attributes:
        token_data: The actual OAuth token data (access_token, refresh_token, etc).
        metadata: Token lifecycle metadata.
    """

    token_data: Dict[str, Any]
    metadata: TokenMetadata

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for storage."""
        return {
            "token_data": self.token_data,
            "metadata": self.metadata.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StoredTokenData":
        """Create from storage dict."""
        # Handle legacy format (no metadata wrapper)
        if "token_data" not in data:
            # Legacy: data IS the token_data, create default metadata
            return cls(
                token_data=data,
                metadata=TokenMetadata(created_at=datetime.now(timezone.utc)),
            )
        return cls(
            token_data=data["token_data"],
            metadata=TokenMetadata.from_dict(data["metadata"]),
        )


class VaultError(Exception):
    """Base exception for vault operations."""

    pass


class TokenNotFoundError(VaultError):
    """Raised when a token reference is not found in the vault."""

    pass


class DecryptionError(VaultError):
    """Raised when token decryption fails."""

    pass


class VaultClient:
    """Secure storage for OAuth tokens using PostgreSQL.

    Stores encrypted OAuth tokens in PostgreSQL for persistence across
    container restarts. Uses Fernet encryption for token data.

    Example:
        vault = VaultClient()
        ref = vault.store_token("sarah@acme.com", "notion", {
            "access_token": "abc123",
            "refresh_token": "xyz789",
            "expires_in": 3600
        }, db=db_session)
        # ref = "vault://sarah-notion-a1b2c3d4"

        # Later, retrieve the token
        token = vault.retrieve_token(ref, db=db_session)
        # token = {"access_token": "abc123", ...}
    """

    # Environment variable name for encryption key
    ENV_KEY_NAME = "VAULT_ENCRYPTION_KEY"

    # Singleton instance
    _instance: Optional["VaultClient"] = None
    _initialized: bool = False

    def __new__(cls, encryption_key: Optional[str] = None, db_session_factory: Optional[Callable[[], Session]] = None) -> "VaultClient":
        """Ensure only one instance exists (singleton pattern)."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        encryption_key: Optional[str] = None,
        db_session_factory: Optional[Callable[[], Session]] = None,
    ):
        """Initialize vault with encryption key and optional database session factory.

        Args:
            encryption_key: Fernet-compatible base64 key. If None, loads from
                           VAULT_ENCRYPTION_KEY environment variable. If env
                           var not set, generates ephemeral key (dev only).
            db_session_factory: Callable that returns a database session.
                               If None, operations require explicit db parameter.

        Note:
            In production, always provide encryption_key or set the environment
            variable. Ephemeral keys will cause token loss on key change.
        """
        # Prevent re-initialization (singleton pattern)
        if self._initialized:
            return
        self.__class__._initialized = True

        self._kms_client = None
        self._encryption_backend = "fernet"

        # Try KMS first (production)
        gcp_project = os.environ.get("GOOGLE_CLOUD_PROJECT")
        if gcp_project:
            try:
                from app.core.kms import get_vault_kms_client
                kms = get_vault_kms_client()
                if kms.backend == "gcp-kms":
                    self._kms_client = kms
                    self._encryption_backend = "kms"
                    logger.info("VaultClient using KMS envelope encryption")
            except Exception as e:
                logger.warning("KMS init failed, falling back to Fernet: %s", e)

        key = encryption_key or os.environ.get(self.ENV_KEY_NAME)

        if not key:
            logger.warning(
                "No encryption key provided. Generating ephemeral key. "
                "Set %s environment variable for production.",
                self.ENV_KEY_NAME,
            )
            key = Fernet.generate_key().decode()

        key_bytes = key.encode() if isinstance(key, str) else key
        self._fernet = Fernet(key_bytes)

        # Database session factory for obtaining sessions
        self._db_session_factory = db_session_factory

        # In-memory fallback for testing (when no db provided)
        self._storage: Dict[str, bytes] = {}

    @property
    def encryption_backend(self) -> str:
        """Return the active encryption backend name ('fernet' or 'kms')."""
        return self._encryption_backend

    def _encrypt(self, plaintext: bytes) -> bytes:
        """Encrypt bytes using the active backend (KMS or Fernet)."""
        if self._kms_client is not None:
            return self._kms_client.encrypt_bytes(plaintext)
        return self._fernet.encrypt(plaintext)

    def _decrypt(self, ciphertext: bytes) -> bytes:
        """Decrypt bytes using the active backend (KMS or Fernet).

        Supports mixed-format reads: KMS-encrypted blobs are auto-detected
        by their version prefix, so tokens encrypted with Fernet before
        migration still decrypt correctly.
        """
        if self._kms_client is not None:
            return self._kms_client.decrypt_bytes(ciphertext)
        return self._fernet.decrypt(ciphertext)

    @staticmethod
    def generate_encryption_key() -> str:
        """Generate a new Fernet encryption key.

        Returns:
            Base64-encoded Fernet key suitable for VAULT_ENCRYPTION_KEY env var.
        """
        return Fernet.generate_key().decode()

    def _generate_ref(self, user_id: str, service_id: str) -> str:
        """Generate opaque token reference.

        The reference format is: vault://{user}-{service}-{unique_suffix}

        Args:
            user_id: User identifier (e.g., "sarah@acme.com")
            service_id: Service identifier (e.g., "notion")

        Returns:
            Opaque reference string (e.g., "vault://sarah-notion-a1b2c3d4")
        """
        user_part = user_id.split("@")[0] if "@" in user_id else user_id
        suffix = uuid.uuid4().hex[:8]
        return f"vault://{user_part}-{service_id}-{suffix}"

    def _use_database(self, db: Optional[Session]) -> bool:
        """Check if we should use database storage."""
        return db is not None

    def store_token(
        self,
        user_id: str,
        service_id: str,
        token_data: Dict[str, Any],
        expires_in: Optional[int] = None,
        db: Optional[Session] = None,
    ) -> str:
        """Store OAuth token securely.

        Args:
            user_id: User identifier (e.g., "sarah@acme.com")
            service_id: Service identifier (e.g., "notion")
            token_data: OAuth token response containing access_token,
                       refresh_token, expires_in, etc.
            expires_in: Seconds until token expires. If None, token has no
                       expiration. If provided, expires_at is calculated as
                       current time + expires_in.
            db: Database session. If provided, stores in PostgreSQL.
                If None, falls back to in-memory storage (testing only).

        Returns:
            Opaque token reference (e.g., "vault://sarah-notion-a1b2c3d4")
        """
        token_ref = self._generate_ref(user_id, service_id)

        now = datetime.now(timezone.utc)
        expires_at = None
        if expires_in is not None:
            expires_at = now + timedelta(seconds=expires_in)

        metadata = TokenMetadata(
            created_at=now,
            expires_at=expires_at,
            last_used_at=None,
            refresh_count=0,
        )

        stored = StoredTokenData(token_data=token_data, metadata=metadata)
        plaintext = json.dumps(stored.to_dict()).encode("utf-8")
        encrypted = self._encrypt(plaintext)

        if self._use_database(db):
            from app.models.vault_token import VaultToken

            vault_token = VaultToken(
                token_ref=token_ref,
                user_id=user_id,
                service_id=service_id,
                encrypted_data=encrypted,
                expires_at=expires_at,
                refresh_count=0,
            )
            db.add(vault_token)
            db.commit()
        else:
            self._storage[token_ref] = encrypted

        logger.debug(
            "Stored token for user=%s service=%s ref=%s expires_at=%s",
            user_id,
            service_id,
            token_ref,
            expires_at.isoformat() if expires_at else "never",
        )

        # Publish cache invalidation event
        publish_token_stored(user_id, service_id, token_ref)

        # Schedule proactive refresh if token expires and has a refresh_token
        if expires_in and token_data.get("refresh_token"):
            try:
                from app.services.token_refresh_scheduler import (
                    get_scheduler,
                    compute_refresh_at,
                )

                refresh_at = compute_refresh_at(expires_in)
                get_scheduler().schedule_refresh(
                    token_ref, service_id, user_id, refresh_at
                )
            except Exception as e:
                logger.debug("Could not schedule refresh: %s", e)

        return token_ref

    def retrieve_token(
        self,
        token_ref: str,
        update_usage: bool = True,
        db: Optional[Session] = None,
    ) -> Optional[Dict[str, Any]]:
        """Retrieve decrypted OAuth token.

        Args:
            token_ref: Token reference from store_token()
            update_usage: If True, updates last_used_at timestamp.
            db: Database session. If provided, retrieves from PostgreSQL.

        Returns:
            Decrypted token data dictionary with metadata, or None if not found.

        Raises:
            DecryptionError: If the token exists but cannot be decrypted.
        """
        encrypted: Optional[bytes] = None

        if self._use_database(db):
            from app.models.vault_token import VaultToken

            vault_token = db.query(VaultToken).filter(
                VaultToken.token_ref == token_ref
            ).first()

            if not vault_token:
                logger.debug("Token not found in database: ref=%s", token_ref)
                return None

            encrypted = vault_token.encrypted_data

            if update_usage:
                vault_token.last_used_at = datetime.now(timezone.utc)
                db.commit()
        else:
            encrypted = self._storage.get(token_ref)
            if not encrypted:
                logger.debug("Token not found: ref=%s", token_ref)
                return None

        try:
            plaintext = self._decrypt(encrypted)
            raw_data = json.loads(plaintext.decode("utf-8"))
            stored = StoredTokenData.from_dict(raw_data)

            # For in-memory storage, update usage in memory
            if not self._use_database(db) and update_usage:
                stored.metadata.last_used_at = datetime.now(timezone.utc)
                updated_plaintext = json.dumps(stored.to_dict()).encode("utf-8")
                self._storage[token_ref] = self._encrypt(updated_plaintext)

            result = dict(stored.token_data)
            result["metadata"] = stored.metadata.to_dict()

            logger.debug("Retrieved token: ref=%s", token_ref)
            return result
        except (InvalidToken, ValueError) as e:
            logger.error("Failed to decrypt token: ref=%s error=%s", token_ref, e)
            raise DecryptionError(f"Failed to decrypt token: {token_ref}") from e

    def delete_token(
        self,
        token_ref: str,
        db: Optional[Session] = None,
    ) -> bool:
        """Delete token from storage.

        Args:
            token_ref: Token reference to delete.
            db: Database session.

        Returns:
            True if token was deleted, False if not found.
        """
        if self._use_database(db):
            from app.models.vault_token import VaultToken

            result = db.query(VaultToken).filter(
                VaultToken.token_ref == token_ref
            ).delete()
            db.commit()

            if result > 0:
                logger.debug("Deleted token from database: ref=%s", token_ref)
                publish_token_deleted(token_ref)
                try:
                    from app.services.token_refresh_scheduler import get_scheduler
                    get_scheduler().cancel_refresh(token_ref)
                except Exception:
                    pass
                return True
            logger.debug("Token not found for deletion in database: ref=%s", token_ref)
            return False

        if token_ref in self._storage:
            del self._storage[token_ref]
            logger.debug("Deleted token: ref=%s", token_ref)
            publish_token_deleted(token_ref)
            try:
                from app.services.token_refresh_scheduler import get_scheduler
                get_scheduler().cancel_refresh(token_ref)
            except Exception:
                pass
            return True

        logger.debug("Token not found for deletion: ref=%s", token_ref)
        return False

    def token_exists(
        self,
        token_ref: str,
        db: Optional[Session] = None,
    ) -> bool:
        """Check if token exists in storage.

        Args:
            token_ref: Token reference to check.
            db: Database session.

        Returns:
            True if token exists, False otherwise.
        """
        if self._use_database(db):
            from app.models.vault_token import VaultToken

            count = db.query(VaultToken).filter(
                VaultToken.token_ref == token_ref
            ).count()
            return count > 0

        return token_ref in self._storage

    def update_token(
        self,
        token_ref: str,
        token_data: Dict[str, Any],
        db: Optional[Session] = None,
    ) -> bool:
        """Update an existing token in storage.

        Preserves existing metadata while replacing token data.

        Args:
            token_ref: Existing token reference.
            token_data: New token data to store.
            db: Database session.

        Returns:
            True if token was updated, False if not found.
        """
        if self._use_database(db):
            from app.models.vault_token import VaultToken

            vault_token = db.query(VaultToken).filter(
                VaultToken.token_ref == token_ref
            ).first()

            if not vault_token:
                logger.debug("Token not found for update in database: ref=%s", token_ref)
                return False

            try:
                plaintext = self._decrypt(vault_token.encrypted_data)
                raw_data = json.loads(plaintext.decode("utf-8"))
                stored = StoredTokenData.from_dict(raw_data)
                stored.token_data = token_data

                new_plaintext = json.dumps(stored.to_dict()).encode("utf-8")
                vault_token.encrypted_data = self._encrypt(new_plaintext)
                db.commit()

                logger.debug("Updated token in database: ref=%s", token_ref)
                publish_token_updated(token_ref)
                return True
            except (InvalidToken, ValueError) as e:
                logger.error("Failed to decrypt token for update: ref=%s error=%s", token_ref, e)
                return False

        # In-memory fallback
        if token_ref not in self._storage:
            logger.debug("Token not found for update: ref=%s", token_ref)
            return False

        try:
            encrypted = self._storage[token_ref]
            plaintext = self._decrypt(encrypted)
            raw_data = json.loads(plaintext.decode("utf-8"))
            stored = StoredTokenData.from_dict(raw_data)
            stored.token_data = token_data

            new_plaintext = json.dumps(stored.to_dict()).encode("utf-8")
            self._storage[token_ref] = self._encrypt(new_plaintext)

            logger.debug("Updated token: ref=%s", token_ref)
            publish_token_updated(token_ref)
            return True
        except (InvalidToken, ValueError) as e:
            logger.error("Failed to decrypt token for update: ref=%s error=%s", token_ref, e)
            return False

    def refresh_token(
        self,
        token_ref: str,
        new_access_token: str,
        new_expires_in: Optional[int] = None,
        new_refresh_token: Optional[str] = None,
        db: Optional[Session] = None,
        latency_ms: Optional[float] = None,
    ) -> bool:
        """Update token after OAuth refresh flow.

        Updates the access_token (and optionally refresh_token) while preserving
        other token data and metadata. Increments refresh_count.

        Args:
            token_ref: Existing token reference.
            new_access_token: The new access token from refresh flow.
            new_expires_in: Seconds until new token expires.
            new_refresh_token: New refresh token, if rotated.
            db: Database session.
            latency_ms: Time taken for the OAuth provider call (for refresh_log).

        Returns:
            True if token was refreshed, False if not found.
        """
        if self._use_database(db):
            from app.models.vault_token import VaultToken

            vault_token = db.query(VaultToken).filter(
                VaultToken.token_ref == token_ref
            ).first()

            if not vault_token:
                logger.debug("Token not found for refresh in database: ref=%s", token_ref)
                return False

            try:
                plaintext = self._decrypt(vault_token.encrypted_data)
                raw_data = json.loads(plaintext.decode("utf-8"))
                stored = StoredTokenData.from_dict(raw_data)

                stored.token_data["access_token"] = new_access_token
                if new_refresh_token is not None:
                    stored.token_data["refresh_token"] = new_refresh_token

                now = datetime.now(timezone.utc)
                if new_expires_in is not None:
                    stored.metadata.expires_at = now + timedelta(seconds=new_expires_in)
                    vault_token.expires_at = stored.metadata.expires_at

                stored.metadata.refresh_count += 1
                vault_token.refresh_count = stored.metadata.refresh_count
                vault_token.last_refreshed_at = now

                # Append to refresh_log (keep last 20 entries)
                log_entry: Dict[str, Any] = {
                    "timestamp": now.isoformat(),
                    "status": "success",
                    "latency_ms": round(latency_ms, 1) if latency_ms is not None else None,
                    "new_expires_in": new_expires_in,
                }
                log = list(vault_token.refresh_log or [])
                log.append(log_entry)
                vault_token.refresh_log = log[-20:]

                new_plaintext = json.dumps(stored.to_dict()).encode("utf-8")
                vault_token.encrypted_data = self._encrypt(new_plaintext)
                db.commit()

                logger.debug(
                    "Refreshed token in database: ref=%s refresh_count=%d",
                    token_ref,
                    stored.metadata.refresh_count,
                )

                # Re-schedule next proactive refresh (self-chaining)
                if new_expires_in and stored.token_data.get("refresh_token"):
                    try:
                        from app.services.token_refresh_scheduler import (
                            get_scheduler,
                            compute_refresh_at,
                        )

                        refresh_at = compute_refresh_at(new_expires_in)
                        get_scheduler().schedule_refresh(
                            token_ref,
                            vault_token.service_id,
                            vault_token.user_id,
                            refresh_at,
                        )
                    except Exception as e:
                        logger.debug("Could not re-schedule refresh: %s", e)

                return True
            except (InvalidToken, ValueError) as e:
                logger.error("Failed to decrypt token for refresh: ref=%s error=%s", token_ref, e)
                return False

        # In-memory fallback
        if token_ref not in self._storage:
            logger.debug("Token not found for refresh: ref=%s", token_ref)
            return False

        try:
            encrypted = self._storage[token_ref]
            plaintext = self._decrypt(encrypted)
            raw_data = json.loads(plaintext.decode("utf-8"))
            stored = StoredTokenData.from_dict(raw_data)

            stored.token_data["access_token"] = new_access_token
            if new_refresh_token is not None:
                stored.token_data["refresh_token"] = new_refresh_token

            if new_expires_in is not None:
                stored.metadata.expires_at = datetime.now(timezone.utc) + timedelta(
                    seconds=new_expires_in
                )

            stored.metadata.refresh_count += 1

            new_plaintext = json.dumps(stored.to_dict()).encode("utf-8")
            self._storage[token_ref] = self._encrypt(new_plaintext)

            logger.debug(
                "Refreshed token: ref=%s refresh_count=%d",
                token_ref,
                stored.metadata.refresh_count,
            )
            return True
        except (InvalidToken, ValueError) as e:
            logger.error("Failed to decrypt token for refresh: ref=%s error=%s", token_ref, e)
            return False

    def get_expiring_tokens(
        self,
        threshold_minutes: int = 15,
        db: Optional[Session] = None,
    ) -> List[str]:
        """Find tokens that are expiring within the threshold.

        Useful for proactive token refresh before API calls fail.

        Args:
            threshold_minutes: Minutes until expiration to consider "expiring".
            db: Database session.

        Returns:
            List of token references that will expire within threshold_minutes.
        """
        threshold = datetime.now(timezone.utc) + timedelta(minutes=threshold_minutes)

        if self._use_database(db):
            from app.models.vault_token import VaultToken

            results = db.query(VaultToken.token_ref).filter(
                VaultToken.expires_at.isnot(None),
                VaultToken.expires_at <= threshold,
            ).all()

            expiring = [r[0] for r in results]
            logger.debug(
                "Found %d tokens expiring within %d minutes (database)",
                len(expiring),
                threshold_minutes,
            )
            return expiring

        # In-memory fallback
        expiring = []
        for token_ref, encrypted in self._storage.items():
            try:
                plaintext = self._decrypt(encrypted)
                raw_data = json.loads(plaintext.decode("utf-8"))
                stored = StoredTokenData.from_dict(raw_data)

                if stored.metadata.expires_at is not None:
                    if stored.metadata.expires_at <= threshold:
                        expiring.append(token_ref)
            except (InvalidToken, ValueError, json.JSONDecodeError, KeyError) as e:
                logger.warning("Failed to check expiration for ref=%s: %s", token_ref, e)
                continue

        logger.debug(
            "Found %d tokens expiring within %d minutes",
            len(expiring),
            threshold_minutes,
        )
        return expiring

    def get_tokens_needing_refresh(
        self,
        threshold_minutes: int = 120,
        db: Optional[Session] = None,
    ) -> List[Tuple[str, str, str, datetime]]:
        """Find tokens expiring within threshold that have a refresh_token.

        Returns tuples of (token_ref, service_id, user_id, expires_at)
        for tokens that can and should be proactively refreshed.
        """
        threshold = datetime.now(timezone.utc) + timedelta(minutes=threshold_minutes)

        if self._use_database(db):
            from app.models.vault_token import VaultToken

            rows = db.query(
                VaultToken.token_ref,
                VaultToken.service_id,
                VaultToken.user_id,
                VaultToken.expires_at,
            ).filter(
                VaultToken.expires_at.isnot(None),
                VaultToken.expires_at <= threshold,
                VaultToken.expires_at > datetime.now(timezone.utc),
            ).all()

            results = []
            for token_ref, service_id, user_id, expires_at in rows:
                try:
                    plaintext = self._decrypt(
                        db.query(VaultToken.encrypted_data)
                        .filter(VaultToken.token_ref == token_ref)
                        .scalar()
                    )
                    raw = json.loads(plaintext.decode("utf-8"))
                    if raw.get("token_data", {}).get("refresh_token"):
                        results.append((token_ref, service_id, user_id, expires_at))
                except Exception:
                    continue

            logger.debug(
                "Found %d tokens needing refresh within %d minutes",
                len(results),
                threshold_minutes,
            )
            return results

        return []

    def is_token_expired(
        self,
        token_ref: str,
        db: Optional[Session] = None,
    ) -> bool:
        """Check if a token has expired.

        Args:
            token_ref: Token reference to check.
            db: Database session.

        Returns:
            True if the token has passed its expires_at time.
            False if still valid, has no expiration, or not found.
        """
        if self._use_database(db):
            from app.models.vault_token import VaultToken

            vault_token = db.query(VaultToken).filter(
                VaultToken.token_ref == token_ref
            ).first()

            if not vault_token:
                logger.debug("Token not found for expiration check in database: ref=%s", token_ref)
                return False

            if vault_token.expires_at is None:
                return False

            expires_at = vault_token.expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)

            is_expired = expires_at <= datetime.now(timezone.utc)
            if is_expired:
                logger.debug(
                    "Token expired: ref=%s expires_at=%s",
                    token_ref,
                    expires_at.isoformat(),
                )
            return is_expired

        # In-memory fallback
        if token_ref not in self._storage:
            logger.debug("Token not found for expiration check: ref=%s", token_ref)
            return False

        try:
            encrypted = self._storage[token_ref]
            plaintext = self._decrypt(encrypted)
            raw_data = json.loads(plaintext.decode("utf-8"))
            stored = StoredTokenData.from_dict(raw_data)

            if stored.metadata.expires_at is None:
                return False

            is_expired = stored.metadata.expires_at <= datetime.now(timezone.utc)
            if is_expired:
                logger.debug(
                    "Token expired: ref=%s expires_at=%s",
                    token_ref,
                    stored.metadata.expires_at.isoformat(),
                )
            return is_expired
        except (InvalidToken, ValueError) as e:
            logger.error("Failed to decrypt token for expiration check: ref=%s error=%s", token_ref, e)
            return False

    def list_tokens_for_user(
        self,
        user_id: str,
        db: Optional[Session] = None,
    ) -> List[str]:
        """List all token references for a user.

        Args:
            user_id: User identifier.
            db: Database session.

        Returns:
            List of token references belonging to the user.
        """
        if self._use_database(db):
            from app.models.vault_token import VaultToken

            results = db.query(VaultToken.token_ref).filter(
                VaultToken.user_id == user_id
            ).all()
            return [r[0] for r in results]

        # In-memory fallback
        user_part = user_id.split("@")[0] if "@" in user_id else user_id
        prefix = f"vault://{user_part}-"
        return [ref for ref in self._storage.keys() if ref.startswith(prefix)]

    def delete_user_tokens(
        self,
        user_id: str,
        service_id: Optional[str] = None,
        db: Optional[Session] = None,
    ) -> int:
        """Delete all tokens for a user (or user+service).

        Args:
            user_id: User identifier.
            service_id: Optional service to filter by.
            db: Database session.

        Returns:
            Number of tokens deleted.
        """
        if self._use_database(db):
            from app.models.vault_token import VaultToken

            query = db.query(VaultToken).filter(VaultToken.user_id == user_id)
            if service_id:
                query = query.filter(VaultToken.service_id == service_id)

            count = query.delete()
            db.commit()
            logger.debug(
                "Deleted %d tokens for user=%s service=%s",
                count,
                user_id,
                service_id or "all",
            )
            return count

        # In-memory fallback
        refs_to_delete = self.list_tokens_for_user(user_id)
        if service_id:
            refs_to_delete = [r for r in refs_to_delete if f"-{service_id}-" in r]

        for ref in refs_to_delete:
            del self._storage[ref]

        logger.debug(
            "Deleted %d tokens for user=%s service=%s",
            len(refs_to_delete),
            user_id,
            service_id or "all",
        )
        return len(refs_to_delete)

    def clear_all(self, db: Optional[Session] = None) -> int:
        """Clear all tokens from storage.

        Args:
            db: Database session.

        Returns:
            Number of tokens deleted.

        Warning:
            This is primarily for testing. Use with extreme caution in production.
        """
        if self._use_database(db):
            from app.models.vault_token import VaultToken

            count = db.query(VaultToken).delete()
            db.commit()
            logger.warning("Cleared all tokens from vault (database): count=%d", count)
            return count

        count = len(self._storage)
        self._storage.clear()
        logger.warning("Cleared all tokens from vault: count=%d", count)
        return count
