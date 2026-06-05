"""
RS256 JWT signing for the Control Plane.

Generates RSA-2048 keypairs, caches them in memory, and provides a
``sign_jwt`` function that replaces direct ``jwt.encode`` calls.

Key Management:
  - On first use, generates an ephemeral RSA keypair (dev mode)
  - In production, reads PEM files from ``JWT_RS256_PRIVATE_KEY_PATH``
  - The public key is exposed via the JWKS endpoint (D2) and as a PEM
  - A ``kid`` (Key ID) is derived from the SHA-256 thumbprint of the
    public key per RFC 7638

Migration Strategy:
  - ``JWT_ALGORITHM`` env var controls the active algorithm
  - Default: ``RS256`` (new behavior)
  - Set ``JWT_ALGORITHM=HS256`` to revert to legacy behavior
  - Gateway must be updated (D3) to verify RS256 signatures before
    flipping the algorithm in production
"""

import base64
import hashlib
import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import jwt as pyjwt
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class JWTKeyPair:
    """Holds an RSA keypair plus its JWKS metadata."""

    kid: str
    private_key: rsa.RSAPrivateKey
    public_key: rsa.RSAPublicKey
    private_pem: bytes
    public_pem: bytes
    algorithm: str = "RS256"

    def jwk_dict(self) -> dict[str, str]:
        """Return the public key as a JWK dict (for JWKS endpoint)."""
        pub_numbers = self.public_key.public_numbers()
        return {
            "kty": "RSA",
            "use": "sig",
            "alg": self.algorithm,
            "kid": self.kid,
            "n": _int_to_base64url(pub_numbers.n),
            "e": _int_to_base64url(pub_numbers.e),
        }


class JWTSigningService:
    """Manages JWT signing keys and produces signed tokens.

    Supports both RS256 (asymmetric, recommended) and HS256 (symmetric,
    legacy) algorithms.  The active algorithm is determined by the
    ``JWT_ALGORITHM`` environment variable.
    """

    def __init__(self) -> None:
        self._algorithm = os.environ.get("JWT_ALGORITHM", "RS256")
        self._hs256_secret: str = os.environ.get(
            "SECRET_KEY",
            os.environ.get("JWT_SECRET", "a_very_insecure_default_secret_key_replace_me"),
        )
        self._keypair: JWTKeyPair | None = None

        if self._algorithm.startswith("RS"):
            self._keypair = self._load_or_generate_keypair()
            logger.info(
                "JWT signing initialized: algorithm=%s kid=%s",
                self._algorithm,
                self._keypair.kid,
            )
        else:
            logger.info("JWT signing initialized: algorithm=%s (symmetric)", self._algorithm)

    @property
    def algorithm(self) -> str:
        return self._algorithm

    @property
    def keypair(self) -> JWTKeyPair | None:
        return self._keypair

    def sign(self, payload: dict[str, Any]) -> str:
        """Sign a JWT payload with the configured algorithm."""
        if self._algorithm.startswith("RS") and self._keypair:
            return pyjwt.encode(
                payload,
                self._keypair.private_pem,
                algorithm=self._algorithm,
                headers={"kid": self._keypair.kid},
            )
        return pyjwt.encode(payload, self._hs256_secret, algorithm="HS256")

    def get_jwks(self) -> dict[str, list[dict[str, str]]]:
        """Return the JWKS document containing all public signing keys."""
        if self._keypair:
            return {"keys": [self._keypair.jwk_dict()]}
        return {"keys": []}

    def get_verification_key(self) -> bytes | str:
        """Return the key material needed to verify tokens.

        For RS256: returns the PEM-encoded public key bytes.
        For HS256: returns the shared secret string.
        """
        if self._keypair:
            return self._keypair.public_pem
        return self._hs256_secret

    def _load_or_generate_keypair(self) -> JWTKeyPair:
        """Load RSA key from PEM file or generate an ephemeral one."""
        private_key_path = os.environ.get("JWT_RS256_PRIVATE_KEY_PATH")

        if private_key_path and os.path.exists(private_key_path):
            logger.info("Loading RSA private key from %s", private_key_path)
            with open(private_key_path, "rb") as f:
                private_key = serialization.load_pem_private_key(
                    f.read(), password=None, backend=default_backend()
                )
        else:
            if private_key_path:
                logger.warning(
                    "JWT_RS256_PRIVATE_KEY_PATH=%s not found, generating ephemeral key",
                    private_key_path,
                )
            else:
                logger.info("Generating ephemeral RSA-2048 keypair for development")

            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048,
                backend=default_backend(),
            )

        public_key = private_key.public_key()

        private_pem = private_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
        public_pem = public_key.public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )

        kid = _compute_kid(public_key)

        return JWTKeyPair(
            kid=kid,
            private_key=private_key,
            public_key=public_key,
            private_pem=private_pem,
            public_pem=public_pem,
            algorithm=self._algorithm,
        )


# ─────────────────────────────────────────────────────────────────────
# Module-level singleton
# ─────────────────────────────────────────────────────────────────────

_service: JWTSigningService | None = None


def get_jwt_signing_service() -> JWTSigningService:
    """Return the module-level JWTSigningService, creating it on first call."""
    global _service
    if _service is None:
        _service = JWTSigningService()
    return _service


def reset_jwt_signing_service() -> None:
    """Reset the singleton (for testing)."""
    global _service
    _service = None


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────


def _int_to_base64url(n: int) -> str:
    data = n.to_bytes((n.bit_length() + 7) // 8, byteorder="big")
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _compute_kid(public_key: rsa.RSAPublicKey) -> str:
    """Compute a JWK Thumbprint (RFC 7638) as the key ID."""
    pub_numbers = public_key.public_numbers()
    jwk_obj = {
        "e": _int_to_base64url(pub_numbers.e),
        "kty": "RSA",
        "n": _int_to_base64url(pub_numbers.n),
    }
    canonical = json.dumps(jwk_obj, separators=(",", ":"), sort_keys=True)
    digest = hashlib.sha256(canonical.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
