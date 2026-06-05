"""
OAuth 2.1 token validation via Keycloak JWKS.

Validates Bearer tokens issued by Keycloak's MCP realm using the
JSON Web Key Set (JWKS) endpoint.  Tokens are validated for:
  - Signature (RS256 via JWKS)
  - Expiration
  - Audience (must include "mcp-gateway")
  - Issuer (must match Keycloak realm URL)

The JWKS is cached with a configurable TTL to avoid hitting Keycloak
on every request.

References:
    RFC 7517 - JSON Web Key
    RFC 8414 - Authorization Server Metadata
"""

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any

import httpx
from jose import jwt as jose_jwt, JWTError, jwk

logger = logging.getLogger(__name__)

KEYCLOAK_URL = os.environ.get("KEYCLOAK_URL", "http://localhost:8080")
# Public issuer URL in tokens/PRM (e.g. localhost). JWKS fetched via KEYCLOAK_URL (e.g. keycloak:8080).
KEYCLOAK_ISSUER_URL = os.environ.get("KEYCLOAK_ISSUER_URL", KEYCLOAK_URL)
KEYCLOAK_MCP_REALM = os.environ.get("KEYCLOAK_MCP_REALM", "mcp")
OAUTH_AUDIENCE = os.environ.get("OAUTH_AUDIENCE", "mcp-gateway")

JWKS_CACHE_TTL_SECONDS = int(os.environ.get("JWKS_CACHE_TTL_SECONDS", "300"))


@dataclass
class OAuthTokenClaims:
    """Parsed and validated claims from an OAuth Bearer token."""
    sub: str
    iss: str
    aud: str | list[str]
    scope: str = ""
    preferred_username: str = ""
    email: str = ""
    realm_access: dict[str, Any] = field(default_factory=dict)
    resource_access: dict[str, Any] = field(default_factory=dict)
    exp: int = 0
    iat: int = 0
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def scopes(self) -> list[str]:
        return self.scope.split() if self.scope else []


class JWKSCache:
    """In-memory JWKS cache with TTL."""

    def __init__(self, ttl_seconds: int = JWKS_CACHE_TTL_SECONDS):
        self._keys: dict[str, Any] | None = None
        self._fetched_at: float = 0
        self._ttl = ttl_seconds

    def is_stale(self) -> bool:
        return self._keys is None or (time.time() - self._fetched_at) > self._ttl

    def set(self, keys: dict[str, Any]) -> None:
        self._keys = keys
        self._fetched_at = time.time()

    def get(self) -> dict[str, Any] | None:
        if self.is_stale():
            return None
        return self._keys


class OAuthTokenValidator:
    """Validates OAuth 2.1 tokens from Keycloak using JWKS."""

    def __init__(
        self,
        keycloak_url: str = KEYCLOAK_URL,
        realm: str = KEYCLOAK_MCP_REALM,
        audience: str = OAUTH_AUDIENCE,
        issuer_url: str = KEYCLOAK_ISSUER_URL,
    ):
        self._issuer = f"{issuer_url}/realms/{realm}"
        self._jwks_url = f"{keycloak_url}/realms/{realm}/protocol/openid-connect/certs"
        self._audience = audience
        self._cache = JWKSCache()
        self._enabled = True
        logger.info(
            "OAuthTokenValidator configured: issuer=%s audience=%s",
            self._issuer,
            self._audience,
        )

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def issuer(self) -> str:
        return self._issuer

    async def fetch_jwks(self) -> dict[str, Any]:
        """Fetch JWKS from Keycloak, using cache when possible."""
        cached = self._cache.get()
        if cached is not None:
            return cached

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(self._jwks_url)
                response.raise_for_status()
                keys = response.json()
                self._cache.set(keys)
                logger.debug("JWKS fetched from %s (%d keys)", self._jwks_url, len(keys.get("keys", [])))
                return keys
        except Exception as e:
            logger.error("Failed to fetch JWKS from %s: %s", self._jwks_url, e)
            raise OAuthValidationError(f"Cannot fetch JWKS: {e}") from e

    async def validate_token(self, token: str) -> OAuthTokenClaims:
        """Validate an OAuth Bearer token and return parsed claims.

        Raises OAuthValidationError on any validation failure.
        """
        jwks = await self.fetch_jwks()

        try:
            payload = jose_jwt.decode(
                token,
                jwks,
                algorithms=["RS256", "RS384", "RS512"],
                audience=self._audience,
                issuer=self._issuer,
            )
        except JWTError as e:
            raise OAuthValidationError(f"Token validation failed: {e}") from e

        return OAuthTokenClaims(
            sub=payload.get("sub", ""),
            iss=payload.get("iss", ""),
            aud=payload.get("aud", ""),
            scope=payload.get("scope", ""),
            preferred_username=payload.get("preferred_username", ""),
            email=payload.get("email", ""),
            realm_access=payload.get("realm_access", {}),
            resource_access=payload.get("resource_access", {}),
            exp=payload.get("exp", 0),
            iat=payload.get("iat", 0),
            raw=payload,
        )

    def is_oauth_token(self, token: str) -> bool:
        """Heuristic: check if a Bearer token looks like a Keycloak JWT.

        Keycloak RS256 tokens have a header with ``"alg": "RS256"`` and
        ``"typ": "JWT"``.  DeepSecure proprietary JWTs use HS256.
        """
        try:
            header = jose_jwt.get_unverified_header(token)
            return header.get("alg", "").startswith("RS")
        except Exception:
            return False


class OAuthValidationError(Exception):
    """Raised when OAuth token validation fails."""
    pass


# Module-level singleton
_validator: OAuthTokenValidator | None = None


def configure_oauth_validator(
    keycloak_url: str = KEYCLOAK_URL,
    realm: str = KEYCLOAK_MCP_REALM,
    audience: str = OAUTH_AUDIENCE,
    issuer_url: str = KEYCLOAK_ISSUER_URL,
) -> None:
    global _validator
    _validator = OAuthTokenValidator(keycloak_url, realm, audience, issuer_url)


def get_oauth_validator() -> OAuthTokenValidator | None:
    return _validator
