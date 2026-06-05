"""Credential encryption client with GCP KMS and Fernet fallback.

Production: Uses GCP KMS envelope encryption (KMS wraps a DEK,
the DEK encrypts the plaintext value).

Local development: Falls back to Fernet symmetric encryption using
the FERNET_KEY environment variable when GCP KMS is unavailable.
"""

import base64
import logging
import os
import struct
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

logger = logging.getLogger(__name__)

_GCP_KMS_AVAILABLE = False
try:
    from google.cloud import kms  # type: ignore[import-untyped]

    _GCP_KMS_AVAILABLE = True
except ImportError:
    pass

# Envelope encryption wire format version
_ENVELOPE_VERSION = 1


class KMSClient:
    """Encrypt/decrypt credentials for service registry secrets.

    Automatically selects the backend:
      - GCP KMS when GOOGLE_CLOUD_PROJECT and KMS_KEY_NAME are set
      - Fernet when FERNET_KEY is set (local dev)
      - Raises RuntimeError if neither is configured

    Supports two modes:
      - String encrypt/decrypt (existing) for ServiceOAuthConfig
      - Bytes encrypt_bytes/decrypt_bytes (envelope encryption) for VaultClient
    """

    def __init__(
        self,
        *,
        gcp_project: Optional[str] = None,
        gcp_location: Optional[str] = None,
        gcp_keyring: Optional[str] = None,
        gcp_key: Optional[str] = None,
        fernet_key: Optional[str] = None,
    ):
        self._gcp_project = gcp_project or os.getenv("GOOGLE_CLOUD_PROJECT")
        self._gcp_location = gcp_location or os.getenv("KMS_LOCATION", "us-central1")
        self._gcp_keyring = gcp_keyring or os.getenv("KMS_KEYRING", "deepsecure")
        self._gcp_key = gcp_key or os.getenv("KMS_KEY_NAME", "service-credentials")
        self._gcp_vault_key = os.getenv("KMS_VAULT_KEY_NAME", "vault-tokens")
        self._fernet_key = fernet_key or os.getenv("FERNET_KEY")
        self._backend: str = "none"
        self._fernet: Optional[Fernet] = None
        self._kms_client = None
        self._key_name: Optional[str] = None
        self._vault_key_name: Optional[str] = None

        if _GCP_KMS_AVAILABLE and self._gcp_project:
            self._backend = "gcp-kms"
            self._kms_client = kms.KeyManagementServiceClient()
            self._key_name = self._kms_client.crypto_key_path(
                self._gcp_project,
                self._gcp_location,
                self._gcp_keyring,
                self._gcp_key,
            )
            self._vault_key_name = self._kms_client.crypto_key_path(
                self._gcp_project,
                self._gcp_location,
                self._gcp_keyring,
                self._gcp_vault_key,
            )
            logger.info("KMS backend: GCP KMS (project=%s)", self._gcp_project)
        elif self._fernet_key:
            self._backend = "fernet"
            self._fernet = Fernet(self._fernet_key.encode())
            logger.info("KMS backend: Fernet (local dev)")
        else:
            logger.warning(
                "No encryption backend configured. "
                "Set GOOGLE_CLOUD_PROJECT for KMS or FERNET_KEY for local dev."
            )

    @property
    def backend(self) -> str:
        return self._backend

    # ─── String encrypt/decrypt (service credentials) ─────────────────────

    def encrypt(self, plaintext: str) -> str:
        """Encrypt a plaintext string. Returns base64-encoded ciphertext."""
        if self._backend == "gcp-kms":
            return self._encrypt_kms(plaintext)
        elif self._backend == "fernet":
            return self._encrypt_fernet(plaintext)
        raise RuntimeError(
            "No encryption backend configured. "
            "Set GOOGLE_CLOUD_PROJECT or FERNET_KEY."
        )

    def decrypt(self, ciphertext: str) -> str:
        """Decrypt a ciphertext string back to plaintext."""
        if self._backend == "gcp-kms":
            return self._decrypt_kms(ciphertext)
        elif self._backend == "fernet":
            return self._decrypt_fernet(ciphertext)
        raise RuntimeError(
            "No encryption backend configured. "
            "Set GOOGLE_CLOUD_PROJECT or FERNET_KEY."
        )

    # ─── Bytes encrypt/decrypt (envelope encryption for vault tokens) ─────

    def encrypt_bytes(self, plaintext: bytes) -> bytes:
        """Envelope-encrypt arbitrary bytes.

        KMS path: generates a random AES-256 DEK, encrypts plaintext with
        AES-GCM, wraps DEK with KMS, returns a versioned binary blob:
            [1B version][2B wrapped_dek_len][wrapped_dek][12B nonce][ciphertext+tag]

        Fernet path: delegates to Fernet.encrypt (returns Fernet token bytes).
        """
        if self._backend == "gcp-kms":
            return self._envelope_encrypt_kms(plaintext)
        elif self._backend == "fernet":
            assert self._fernet is not None
            return self._fernet.encrypt(plaintext)
        raise RuntimeError(
            "No encryption backend configured. "
            "Set GOOGLE_CLOUD_PROJECT or FERNET_KEY."
        )

    def decrypt_bytes(self, ciphertext: bytes) -> bytes:
        """Decrypt bytes produced by encrypt_bytes.

        Auto-detects format: if the first byte is the envelope version marker
        it uses KMS envelope decryption, otherwise falls back to Fernet.
        """
        if len(ciphertext) > 0 and ciphertext[0] == _ENVELOPE_VERSION:
            return self._envelope_decrypt_kms(ciphertext)
        if self._backend == "fernet" or self._fernet is not None:
            if self._fernet is None:
                raise RuntimeError("Fernet key not configured")
            try:
                return self._fernet.decrypt(ciphertext)
            except InvalidToken as exc:
                raise ValueError("Failed to decrypt: invalid token or wrong key") from exc
        raise RuntimeError(
            "No decryption backend available for this ciphertext format."
        )

    # ─── GCP KMS (string) ────────────────────────────────────────────────

    def _encrypt_kms(self, plaintext: str) -> str:
        response = self._kms_client.encrypt(
            request={
                "name": self._key_name,
                "plaintext": plaintext.encode("utf-8"),
            }
        )
        return base64.b64encode(response.ciphertext).decode("ascii")

    def _decrypt_kms(self, ciphertext: str) -> str:
        response = self._kms_client.decrypt(
            request={
                "name": self._key_name,
                "ciphertext": base64.b64decode(ciphertext),
            }
        )
        return response.plaintext.decode("utf-8")

    # ─── GCP KMS envelope encryption (bytes) ─────────────────────────────

    def _envelope_encrypt_kms(self, plaintext: bytes) -> bytes:
        dek = os.urandom(32)  # AES-256
        nonce = os.urandom(12)
        aesgcm = AESGCM(dek)
        ciphertext = aesgcm.encrypt(nonce, plaintext, None)

        kms_key = self._vault_key_name or self._key_name
        response = self._kms_client.encrypt(
            request={"name": kms_key, "plaintext": dek}
        )
        wrapped_dek = response.ciphertext

        # Wire format: [version:1B][wrapped_dek_len:2B][wrapped_dek][nonce:12B][ciphertext+tag]
        return (
            struct.pack("!BH", _ENVELOPE_VERSION, len(wrapped_dek))
            + wrapped_dek
            + nonce
            + ciphertext
        )

    def _envelope_decrypt_kms(self, blob: bytes) -> bytes:
        offset = 0
        version, wrapped_dek_len = struct.unpack_from("!BH", blob, offset)
        if version != _ENVELOPE_VERSION:
            raise ValueError(f"Unknown envelope version: {version}")
        offset += 3

        wrapped_dek = blob[offset : offset + wrapped_dek_len]
        offset += wrapped_dek_len

        nonce = blob[offset : offset + 12]
        offset += 12

        ciphertext = blob[offset:]

        kms_key = self._vault_key_name or self._key_name
        response = self._kms_client.decrypt(
            request={"name": kms_key, "ciphertext": wrapped_dek}
        )
        dek = response.plaintext

        aesgcm = AESGCM(dek)
        return aesgcm.decrypt(nonce, ciphertext, None)

    # ─── Fernet (local dev fallback) ─────────────────────────────────────

    def _encrypt_fernet(self, plaintext: str) -> str:
        assert self._fernet is not None
        return self._fernet.encrypt(plaintext.encode("utf-8")).decode("ascii")

    def _decrypt_fernet(self, ciphertext: str) -> str:
        assert self._fernet is not None
        try:
            return self._fernet.decrypt(ciphertext.encode("ascii")).decode("utf-8")
        except InvalidToken as exc:
            raise ValueError("Failed to decrypt: invalid token or wrong key") from exc


# Singleton — initialized once at startup
_kms_instance: Optional[KMSClient] = None


def get_kms_client() -> KMSClient:
    """Return the module-level KMS client singleton.

    Creates the instance on first call (lazy init).
    """
    global _kms_instance
    if _kms_instance is None:
        _kms_instance = KMSClient()
    return _kms_instance


def get_vault_kms_client() -> KMSClient:
    """Return a KMS client configured for vault token encryption.

    Uses the same singleton as get_kms_client() since the KMSClient
    internally routes to the vault-tokens key via _vault_key_name.
    """
    return get_kms_client()


def reset_kms_client() -> None:
    """Reset the singleton (for testing)."""
    global _kms_instance
    _kms_instance = None
