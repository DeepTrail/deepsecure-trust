"""
RFC 8693 Token Exchange Client for Keycloak.

Exchanges DeepSecure Agent JWTs for backend-specific OAuth access tokens
via Keycloak's token exchange endpoint. Provides fresh, audience-scoped
tokens per backend, eliminating static token expiration issues.

Flow:
    Agent JWT → Gateway → TokenExchangeClient → Keycloak → Backend OAuth Token
                               ↓                    ↓
                        Cache-first lookup      RFC 8693 exchange
                        TTL-buffered             Audience-scoped

Integrates into credential_injection.py as the primary token source,
with vault as fallback for graceful degradation.

Usage:
    from app.security.token_exchange import (
        configure_token_exchange_client, get_token_exchange_client,
    )

    configure_token_exchange_client(TokenExchangeConfig(
        keycloak_url="http://keycloak:8080",
        realm="deepsecure",
        client_id="gateway",
        client_secret="...",
    ))

    client = get_token_exchange_client()
    token = await client.get_backend_token(
        subject_token=agent_jwt,
        backend_id="hubspot",
    )
"""

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


# =============================================================================
# RFC 8693 Enums
# =============================================================================


class TokenExchangeGrantType(str, Enum):
    """RFC 8693 grant types."""
    TOKEN_EXCHANGE = "urn:ietf:params:oauth:grant-type:token-exchange"


class SubjectTokenType(str, Enum):
    """RFC 8693 token type identifiers."""
    ACCESS_TOKEN = "urn:ietf:params:oauth:token-type:access_token"
    JWT = "urn:ietf:params:oauth:token-type:jwt"


class RequestedTokenType(str, Enum):
    """Requested token type for the exchange."""
    ACCESS_TOKEN = "urn:ietf:params:oauth:token-type:access_token"


# =============================================================================
# Data Models
# =============================================================================


@dataclass
class TokenExchangeConfig:
    """Configuration for the token exchange client."""
    enabled: bool = True
    keycloak_url: str = "http://localhost:8080"
    realm: str = "deepsecure"
    client_id: str = "gateway"
    client_secret: str = "gateway-secret"
    cache_ttl_buffer_seconds: int = 60
    request_timeout_seconds: int = 10
    audience_map: Dict[str, str] = field(default_factory=dict)


@dataclass
class ExchangedToken:
    """Result of a successful token exchange."""
    access_token: str
    token_type: str = "Bearer"
    expires_in: int = 0
    scope: Optional[str] = None
    issued_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_expired(self) -> bool:
        if self.expires_in <= 0:
            return True
        return datetime.now(timezone.utc) > self.issued_at + timedelta(seconds=self.expires_in)


# =============================================================================
# Error Hierarchy
# =============================================================================


class TokenExchangeError(Exception):
    """Base error for token exchange operations."""
    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.error_code = error_code
        self.details = details or {}


class TokenExchangeUnavailableError(TokenExchangeError):
    """Keycloak is unreachable."""
    pass


class TokenExchangeDeniedError(TokenExchangeError):
    """Exchange was denied (invalid subject, insufficient scope, etc.)."""
    pass


# =============================================================================
# TokenExchangeClient
# =============================================================================


class TokenExchangeClient:
    """Exchanges DeepSecure JWTs for backend-specific OAuth tokens via Keycloak.

    Implements RFC 8693 (OAuth 2.0 Token Exchange) using Keycloak's
    token exchange endpoint. Caches exchanged tokens to minimize
    round-trips to Keycloak.
    """

    def __init__(self, config: Optional[TokenExchangeConfig] = None):
        self._config = config or TokenExchangeConfig()
        self._cache: Dict[str, ExchangedToken] = {}
        self._http_client: Optional[httpx.AsyncClient] = None

        if (
            self._config.enabled
            and self._config.keycloak_url.startswith("http://")
            and "localhost" not in self._config.keycloak_url
        ):
            logger.warning(
                "Token exchange configured with non-TLS URL — use HTTPS in production"
            )

    @property
    def config(self) -> TokenExchangeConfig:
        return self._config

    @property
    def token_endpoint(self) -> str:
        """Keycloak OIDC token endpoint URL."""
        return (
            f"{self._config.keycloak_url}/realms/{self._config.realm}"
            f"/protocol/openid-connect/token"
        )

    # -----------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------

    async def exchange_token(
        self,
        subject_token: str,
        backend_id: str,
        scopes: Optional[List[str]] = None,
    ) -> ExchangedToken:
        """Exchange a DeepSecure JWT for a backend-specific OAuth token.

        Raises:
            TokenExchangeUnavailableError: Keycloak is unreachable.
            TokenExchangeDeniedError: Exchange denied by Keycloak.
            TokenExchangeError: Other exchange failures.
        """
        params = self._build_exchange_params(subject_token, backend_id, scopes)

        try:
            client = self._get_http_client()
            response = await client.post(
                self.token_endpoint,
                data=params,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

            if response.status_code == 200:
                data = response.json()
                token = ExchangedToken(
                    access_token=data["access_token"],
                    token_type=data.get("token_type", "Bearer"),
                    expires_in=data.get("expires_in", 0),
                    scope=data.get("scope"),
                )
                logger.debug(
                    "Token exchange successful: backend=%s, expires_in=%d",
                    backend_id,
                    token.expires_in,
                )
                return token

            body = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
            error_code = body.get("error", "unknown_error")
            error_desc = body.get("error_description", "")

            if error_code in ("invalid_grant", "unauthorized_client"):
                raise TokenExchangeDeniedError(
                    f"Token exchange denied: {error_code}",
                    error_code=error_code,
                    details={"backend_id": backend_id, "description": error_desc},
                )

            raise TokenExchangeError(
                f"Token exchange failed: HTTP {response.status_code}",
                error_code=error_code,
                details={
                    "backend_id": backend_id,
                    "status_code": response.status_code,
                    "description": error_desc,
                },
            )

        except TokenExchangeError:
            raise
        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.TimeoutException) as exc:
            raise TokenExchangeUnavailableError(
                f"Keycloak unreachable: {type(exc).__name__}",
                error_code="connection_error",
                details={"backend_id": backend_id, "endpoint": self.token_endpoint},
            ) from exc
        except Exception as exc:
            raise TokenExchangeError(
                f"Token exchange error: {type(exc).__name__}",
                error_code="internal_error",
                details={"backend_id": backend_id},
            ) from exc

    async def get_backend_token(
        self,
        subject_token: str,
        backend_id: str,
        scopes: Optional[List[str]] = None,
        force_refresh: bool = False,
    ) -> ExchangedToken:
        """Get a backend token, using cache when available.

        This is the primary method called by the credential injection pipeline.
        """
        if not self._config.enabled:
            raise TokenExchangeError(
                "Token exchange is disabled",
                error_code="disabled",
            )

        cache_key = self._cache_key(subject_token, backend_id)

        if not force_refresh:
            cached = self._get_cached(cache_key)
            if cached is not None:
                logger.debug("Token exchange cache hit: backend=%s", backend_id)
                return cached

        token = await self.exchange_token(subject_token, backend_id, scopes)
        self._put_cache(cache_key, token)
        return token

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None

    # -----------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------

    def _get_http_client(self) -> httpx.AsyncClient:
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(
                timeout=self._config.request_timeout_seconds,
            )
        return self._http_client

    def _build_exchange_params(
        self,
        subject_token: str,
        backend_id: str,
        scopes: Optional[List[str]] = None,
    ) -> Dict[str, str]:
        """Build RFC 8693 token exchange form parameters."""
        audience = self._config.audience_map.get(backend_id, backend_id)
        params: Dict[str, str] = {
            "grant_type": TokenExchangeGrantType.TOKEN_EXCHANGE.value,
            "client_id": self._config.client_id,
            "client_secret": self._config.client_secret,
            "subject_token": subject_token,
            "subject_token_type": SubjectTokenType.ACCESS_TOKEN.value,
            "requested_token_type": RequestedTokenType.ACCESS_TOKEN.value,
            "audience": audience,
        }
        if scopes:
            params["scope"] = " ".join(scopes)
        return params

    def _cache_key(self, subject_token: str, backend_id: str) -> str:
        """Generate cache key from subject token hash and backend."""
        token_hash = hashlib.sha256(subject_token.encode()).hexdigest()[:16]
        return f"{token_hash}:{backend_id}"

    def _get_cached(self, cache_key: str) -> Optional[ExchangedToken]:
        """Get a non-expired cached token."""
        token = self._cache.get(cache_key)
        if token is None:
            return None
        if token.is_expired:
            del self._cache[cache_key]
            return None
        return token

    def _put_cache(self, cache_key: str, token: ExchangedToken) -> None:
        """Cache an exchanged token with TTL buffer."""
        token.expires_in = max(0, token.expires_in - self._config.cache_ttl_buffer_seconds)
        self._cache[cache_key] = token


# =============================================================================
# Module-Level Accessor Pattern
# =============================================================================


_exchange_client: Optional[TokenExchangeClient] = None


def get_token_exchange_client() -> Optional[TokenExchangeClient]:
    """Get the configured TokenExchangeClient instance."""
    return _exchange_client


def configure_token_exchange_client(
    config: Optional[TokenExchangeConfig] = None,
) -> TokenExchangeClient:
    """Configure and store the global TokenExchangeClient."""
    global _exchange_client
    _exchange_client = TokenExchangeClient(config=config)
    logger.info(
        "Token exchange client configured: enabled=%s, endpoint=%s",
        _exchange_client.config.enabled,
        _exchange_client.token_endpoint,
    )
    return _exchange_client


def reset_token_exchange_client() -> None:
    """Reset exchange client (for testing)."""
    global _exchange_client
    _exchange_client = None
