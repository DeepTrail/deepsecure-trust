"""Secure OAuth token vault storage.

This module provides encrypted storage for OAuth tokens. For MVP, tokens are
stored in-memory with encryption. In production, this would integrate with
HashiCorp Vault, AWS Secrets Manager, or similar.

Security properties:
- Tokens are encrypted at rest using Fernet (AES-128-CBC + HMAC)
- Encryption key is loaded from environment (never hardcoded)
- Token references are opaque (no token data in reference string)
- No token data appears in logs

Token lifecycle features:
- Expiration tracking (expires_at timestamp)
- Usage tracking (last_used_at timestamp)
- Refresh support (refresh_token, refresh_count)
- Expiring token identification (get_expiring_tokens)
"""

import json
import logging
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from cryptography.fernet import Fernet, InvalidToken

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
    """Secure storage for OAuth tokens.

    MVP Implementation: In-memory encrypted storage (singleton pattern).
    Production: Integrate with HashiCorp Vault or AWS Secrets Manager.

    Example:
        vault = VaultClient()
        ref = vault.store_token("sarah@acme.com", "notion", {
            "access_token": "abc123",
            "refresh_token": "xyz789",
            "expires_in": 3600
        })
        # ref = "vault://sarah-notion-a1b2c3d4"

        # Later, retrieve the token
        token = vault.retrieve_token(ref)
        # token = {"access_token": "abc123", ...}
    """

    # Environment variable name for encryption key
    ENV_KEY_NAME = "VAULT_ENCRYPTION_KEY"

    # Singleton instance
    _instance: Optional["VaultClient"] = None
    _initialized: bool = False

    def __new__(cls, encryption_key: Optional[str] = None) -> "VaultClient":
        """Ensure only one instance exists (singleton pattern)."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, encryption_key: Optional[str] = None):
        """Initialize vault with encryption key.

        Args:
            encryption_key: Fernet-compatible base64 key. If None, loads from
                           VAULT_ENCRYPTION_KEY environment variable. If env
                           var not set, generates ephemeral key (dev only).

        Note:
            In production, always provide encryption_key or set the environment
            variable. Ephemeral keys will cause token loss on restart.
        """
        # Prevent re-initialization (singleton pattern)
        if self._initialized:
            return
        self.__class__._initialized = True

        key = encryption_key or os.environ.get(self.ENV_KEY_NAME)

        if not key:
            # Development only - generate ephemeral key
            # Log warning to make it obvious this is not production-ready
            logger.warning(
                "No encryption key provided. Generating ephemeral key. "
                "Set %s environment variable for production.",
                self.ENV_KEY_NAME,
            )
            key = Fernet.generate_key().decode()

        # Handle string vs bytes key
        key_bytes = key.encode() if isinstance(key, str) else key
        self._fernet = Fernet(key_bytes)

        # In-memory storage: token_ref -> encrypted_data
        # In production, this would be replaced with vault API calls
        self._storage: Dict[str, bytes] = {}

    @staticmethod
    def generate_encryption_key() -> str:
        """Generate a new Fernet encryption key.

        Returns:
            Base64-encoded Fernet key suitable for VAULT_ENCRYPTION_KEY env var.

        Example:
            key = VaultClient.generate_encryption_key()
            # Set as environment variable:
            # export VAULT_ENCRYPTION_KEY="<key>"
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
        # Sanitize user_id: take part before @ if email, otherwise use as-is
        user_part = user_id.split("@")[0] if "@" in user_id else user_id
        # Use 8 chars of UUID for uniqueness
        suffix = uuid.uuid4().hex[:8]
        return f"vault://{user_part}-{service_id}-{suffix}"

    def store_token(
        self,
        user_id: str,
        service_id: str,
        token_data: Dict[str, Any],
        expires_in: Optional[int] = None,
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

        Returns:
            Opaque token reference (e.g., "vault://sarah-notion-a1b2c3d4")

        Note:
            The token_data is serialized to JSON and encrypted before storage.
            The reference contains no sensitive data.
        """
        token_ref = self._generate_ref(user_id, service_id)

        # Calculate timestamps
        now = datetime.now(timezone.utc)
        expires_at = None
        if expires_in is not None:
            from datetime import timedelta

            expires_at = now + timedelta(seconds=expires_in)

        # Create metadata
        metadata = TokenMetadata(
            created_at=now,
            expires_at=expires_at,
            last_used_at=None,
            refresh_count=0,
        )

        # Wrap token with metadata
        stored = StoredTokenData(token_data=token_data, metadata=metadata)

        # Serialize and encrypt token data
        plaintext = json.dumps(stored.to_dict()).encode("utf-8")
        encrypted = self._fernet.encrypt(plaintext)

        # Store encrypted data
        self._storage[token_ref] = encrypted

        # Log without exposing token data
        logger.debug(
            "Stored token for user=%s service=%s ref=%s expires_at=%s",
            user_id,
            service_id,
            token_ref,
            expires_at.isoformat() if expires_at else "never",
        )

        return token_ref

    def retrieve_token(
        self, token_ref: str, update_usage: bool = True
    ) -> Optional[Dict[str, Any]]:
        """Retrieve decrypted OAuth token.

        Args:
            token_ref: Token reference from store_token()
            update_usage: If True, updates last_used_at timestamp.
                         Set to False for read-only access (e.g., checking expiration).

        Returns:
            Decrypted token data dictionary with metadata, or None if not found.
            Structure: {
                "access_token": "...",
                "refresh_token": "...",
                ...original token fields...,
                "metadata": {
                    "created_at": "2026-02-16T12:00:00+00:00",
                    "expires_at": "2026-02-16T13:00:00+00:00" or None,
                    "last_used_at": "2026-02-16T12:30:00+00:00" or None,
                    "refresh_count": 0
                }
            }

        Raises:
            DecryptionError: If the token exists but cannot be decrypted
                            (e.g., key mismatch, data corruption).
        """
        encrypted = self._storage.get(token_ref)
        if not encrypted:
            logger.debug("Token not found: ref=%s", token_ref)
            return None

        try:
            # Decrypt token data
            plaintext = self._fernet.decrypt(encrypted)
            raw_data = json.loads(plaintext.decode("utf-8"))

            # Parse stored data (handles legacy format)
            stored = StoredTokenData.from_dict(raw_data)

            # Optionally update usage timestamp
            if update_usage:
                stored.metadata.last_used_at = datetime.now(timezone.utc)
                # Re-encrypt and store updated data
                updated_plaintext = json.dumps(stored.to_dict()).encode("utf-8")
                self._storage[token_ref] = self._fernet.encrypt(updated_plaintext)

            # Return token data with metadata included
            result = dict(stored.token_data)
            result["metadata"] = stored.metadata.to_dict()

            logger.debug("Retrieved token: ref=%s", token_ref)
            return result
        except InvalidToken as e:
            logger.error("Failed to decrypt token: ref=%s error=%s", token_ref, e)
            raise DecryptionError(f"Failed to decrypt token: {token_ref}") from e

    def delete_token(self, token_ref: str) -> bool:
        """Delete token from storage.

        Args:
            token_ref: Token reference to delete.

        Returns:
            True if token was deleted, False if not found.
        """
        if token_ref in self._storage:
            del self._storage[token_ref]
            logger.debug("Deleted token: ref=%s", token_ref)
            return True

        logger.debug("Token not found for deletion: ref=%s", token_ref)
        return False

    def token_exists(self, token_ref: str) -> bool:
        """Check if token exists in storage.

        Args:
            token_ref: Token reference to check.

        Returns:
            True if token exists, False otherwise.
        """
        return token_ref in self._storage

    def update_token(
        self,
        token_ref: str,
        token_data: Dict[str, Any],
    ) -> bool:
        """Update an existing token in storage.

        Useful for token refresh operations where the reference stays
        the same but the token data changes. Preserves existing metadata.

        Args:
            token_ref: Existing token reference.
            token_data: New token data to store.

        Returns:
            True if token was updated, False if not found.
        """
        if token_ref not in self._storage:
            logger.debug("Token not found for update: ref=%s", token_ref)
            return False

        try:
            # Get existing data to preserve metadata
            encrypted = self._storage[token_ref]
            plaintext = self._fernet.decrypt(encrypted)
            raw_data = json.loads(plaintext.decode("utf-8"))
            stored = StoredTokenData.from_dict(raw_data)

            # Update token data, preserve metadata
            stored.token_data = token_data

            # Serialize and encrypt new token data
            new_plaintext = json.dumps(stored.to_dict()).encode("utf-8")
            self._storage[token_ref] = self._fernet.encrypt(new_plaintext)

            logger.debug("Updated token: ref=%s", token_ref)
            return True
        except InvalidToken as e:
            logger.error("Failed to decrypt token for update: ref=%s error=%s", token_ref, e)
            return False

    def refresh_token(
        self,
        token_ref: str,
        new_access_token: str,
        new_expires_in: Optional[int] = None,
        new_refresh_token: Optional[str] = None,
    ) -> bool:
        """Update token after OAuth refresh flow.

        Updates the access_token (and optionally refresh_token) while preserving
        other token data and metadata. Recalculates expires_at if new_expires_in
        is provided. Increments refresh_count.

        Args:
            token_ref: Existing token reference.
            new_access_token: The new access token from refresh flow.
            new_expires_in: Seconds until new token expires. If None, keeps
                           existing expires_at.
            new_refresh_token: New refresh token, if rotated. If None, keeps
                              existing refresh_token.

        Returns:
            True if token was refreshed, False if not found.
        """
        if token_ref not in self._storage:
            logger.debug("Token not found for refresh: ref=%s", token_ref)
            return False

        try:
            # Get existing data
            encrypted = self._storage[token_ref]
            plaintext = self._fernet.decrypt(encrypted)
            raw_data = json.loads(plaintext.decode("utf-8"))
            stored = StoredTokenData.from_dict(raw_data)

            # Update access_token
            stored.token_data["access_token"] = new_access_token

            # Update refresh_token if provided
            if new_refresh_token is not None:
                stored.token_data["refresh_token"] = new_refresh_token

            # Update expires_at if new_expires_in provided
            if new_expires_in is not None:
                from datetime import timedelta

                stored.metadata.expires_at = datetime.now(timezone.utc) + timedelta(
                    seconds=new_expires_in
                )

            # Increment refresh count
            stored.metadata.refresh_count += 1

            # Serialize and encrypt updated data
            new_plaintext = json.dumps(stored.to_dict()).encode("utf-8")
            self._storage[token_ref] = self._fernet.encrypt(new_plaintext)

            logger.debug(
                "Refreshed token: ref=%s refresh_count=%d",
                token_ref,
                stored.metadata.refresh_count,
            )
            return True
        except InvalidToken as e:
            logger.error("Failed to decrypt token for refresh: ref=%s error=%s", token_ref, e)
            return False

    def get_expiring_tokens(self, threshold_minutes: int = 15) -> list[str]:
        """Find tokens that are expiring within the threshold.

        Useful for proactive token refresh before API calls fail.

        Args:
            threshold_minutes: Minutes until expiration to consider "expiring".
                              Default is 15 minutes.

        Returns:
            List of token references that will expire within threshold_minutes.
            Tokens with expires_at=None (no expiration) are NOT included.
        """
        from datetime import timedelta

        expiring = []
        threshold = datetime.now(timezone.utc) + timedelta(minutes=threshold_minutes)

        for token_ref, encrypted in self._storage.items():
            try:
                plaintext = self._fernet.decrypt(encrypted)
                raw_data = json.loads(plaintext.decode("utf-8"))
                stored = StoredTokenData.from_dict(raw_data)

                # Only consider tokens with expiration set
                if stored.metadata.expires_at is not None:
                    if stored.metadata.expires_at <= threshold:
                        expiring.append(token_ref)
            except (InvalidToken, json.JSONDecodeError, KeyError) as e:
                logger.warning("Failed to check expiration for ref=%s: %s", token_ref, e)
                continue

        logger.debug(
            "Found %d tokens expiring within %d minutes",
            len(expiring),
            threshold_minutes,
        )
        return expiring

    def is_token_expired(self, token_ref: str) -> bool:
        """Check if a token has expired.

        Args:
            token_ref: Token reference to check.

        Returns:
            True if the token has passed its expires_at time.
            False if the token is still valid, has no expiration (expires_at=None),
            or if the token is not found.

        Note:
            Returns False for non-existent tokens. Use token_exists() to
            distinguish between "not expired" and "not found".
        """
        if token_ref not in self._storage:
            logger.debug("Token not found for expiration check: ref=%s", token_ref)
            return False

        try:
            encrypted = self._storage[token_ref]
            plaintext = self._fernet.decrypt(encrypted)
            raw_data = json.loads(plaintext.decode("utf-8"))
            stored = StoredTokenData.from_dict(raw_data)

            # No expiration = never expired
            if stored.metadata.expires_at is None:
                return False

            # Check if past expiration
            is_expired = stored.metadata.expires_at <= datetime.now(timezone.utc)
            if is_expired:
                logger.debug(
                    "Token expired: ref=%s expires_at=%s",
                    token_ref,
                    stored.metadata.expires_at.isoformat(),
                )
            return is_expired
        except InvalidToken as e:
            logger.error("Failed to decrypt token for expiration check: ref=%s error=%s", token_ref, e)
            return False

    def list_tokens_for_user(self, user_id: str) -> list[str]:
        """List all token references for a user.

        Args:
            user_id: User identifier.

        Returns:
            List of token references belonging to the user.
        """
        # Extract user part for matching
        user_part = user_id.split("@")[0] if "@" in user_id else user_id
        prefix = f"vault://{user_part}-"

        return [ref for ref in self._storage.keys() if ref.startswith(prefix)]

    def clear_all(self) -> int:
        """Clear all tokens from storage.

        Returns:
            Number of tokens deleted.

        Warning:
            This is primarily for testing. Use with extreme caution in production.
        """
        count = len(self._storage)
        self._storage.clear()
        logger.warning("Cleared all tokens from vault: count=%d", count)
        return count
