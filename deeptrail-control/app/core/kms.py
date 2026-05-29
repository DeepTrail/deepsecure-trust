"""Credential encryption client with GCP KMS and Fernet fallback.

Production: Uses GCP KMS envelope encryption (KMS wraps a DEK,
the DEK encrypts the plaintext value).

Local development: Falls back to Fernet symmetric encryption using
the FERNET_KEY environment variable when GCP KMS is unavailable.
"""

import base64
import logging
import os
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)

_GCP_KMS_AVAILABLE = False
try:
    from google.cloud import kms  # type: ignore[import-untyped]

    _GCP_KMS_AVAILABLE = True
except ImportError:
    pass


class KMSClient:
    """Encrypt/decrypt credentials for service registry secrets.

    Automatically selects the backend:
      - GCP KMS when GOOGLE_CLOUD_PROJECT and KMS_KEY_NAME are set
      - Fernet when FERNET_KEY is set (local dev)
      - Raises RuntimeError if neither is configured
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
        self._fernet_key = fernet_key or os.getenv("FERNET_KEY")
        self._backend: str = "none"
        self._fernet: Optional[Fernet] = None
        self._kms_client = None
        self._key_name: Optional[str] = None

        if _GCP_KMS_AVAILABLE and self._gcp_project:
            self._backend = "gcp-kms"
            self._kms_client = kms.KeyManagementServiceClient()
            self._key_name = self._kms_client.crypto_key_path(
                self._gcp_project,
                self._gcp_location,
                self._gcp_keyring,
                self._gcp_key,
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

    # --- GCP KMS ---

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

    # --- Fernet (local dev fallback) ---

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


def reset_kms_client() -> None:
    """Reset the singleton (for testing)."""
    global _kms_instance
    _kms_instance = None
