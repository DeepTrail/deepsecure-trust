"""Secure OAuth token vault storage.

This module provides encrypted storage for OAuth tokens. For MVP, tokens are
stored in-memory with encryption. In production, this would integrate with
HashiCorp Vault, AWS Secrets Manager, or similar.

Security properties:
- Tokens are encrypted at rest using Fernet (AES-128-CBC + HMAC)
- Encryption key is loaded from environment (never hardcoded)
- Token references are opaque (no token data in reference string)
- No token data appears in logs
"""

import json
import logging
import os
import uuid
from typing import Any, Dict, Optional

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)


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

    MVP Implementation: In-memory encrypted storage.
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
    ) -> str:
        """Store OAuth token securely.

        Args:
            user_id: User identifier (e.g., "sarah@acme.com")
            service_id: Service identifier (e.g., "notion")
            token_data: OAuth token response containing access_token,
                       refresh_token, expires_in, etc.

        Returns:
            Opaque token reference (e.g., "vault://sarah-notion-a1b2c3d4")

        Note:
            The token_data is serialized to JSON and encrypted before storage.
            The reference contains no sensitive data.
        """
        token_ref = self._generate_ref(user_id, service_id)

        # Serialize and encrypt token data
        plaintext = json.dumps(token_data).encode("utf-8")
        encrypted = self._fernet.encrypt(plaintext)

        # Store encrypted data
        self._storage[token_ref] = encrypted

        # Log without exposing token data
        logger.debug(
            "Stored token for user=%s service=%s ref=%s",
            user_id,
            service_id,
            token_ref,
        )

        return token_ref

    def retrieve_token(self, token_ref: str) -> Optional[Dict[str, Any]]:
        """Retrieve decrypted OAuth token.

        Args:
            token_ref: Token reference from store_token()

        Returns:
            Decrypted token data dictionary, or None if not found.

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
            token_data = json.loads(plaintext.decode("utf-8"))
            logger.debug("Retrieved token: ref=%s", token_ref)
            return token_data
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
        the same but the token data changes.

        Args:
            token_ref: Existing token reference.
            token_data: New token data to store.

        Returns:
            True if token was updated, False if not found.
        """
        if token_ref not in self._storage:
            logger.debug("Token not found for update: ref=%s", token_ref)
            return False

        # Serialize and encrypt new token data
        plaintext = json.dumps(token_data).encode("utf-8")
        encrypted = self._fernet.encrypt(plaintext)
        self._storage[token_ref] = encrypted

        logger.debug("Updated token: ref=%s", token_ref)
        return True

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
