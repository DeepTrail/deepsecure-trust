# Task Specification: WS-J6 Implement Keycloak Token Exchange

> **IMMUTABLE AFTER DESIGN APPROVAL**
>
> This specification defines what implementation MUST match exactly.
> Do not modify without updating the design doc first.
>
> **Source:** `deepsecure-comprehensive-architecture-consolidated.md` (OAuth Authorization Layer, Token Exchange Client),
> RFC 8693 (OAuth 2.0 Token Exchange)
>
> **Breakdown:** `mvp-production-readiness-breakdown.md` — WS-J3: RFC 8693 token exchange for backend OAuth tokens

---

## Overview

| Field | Value |
|-------|-------|
| **Task ID** | WS-J6 |
| **Task Name** | Implement Keycloak Token Exchange |
| **Type** | Security Module |
| **Service** | deeptrail-gateway |
| **Complexity** | L (3+ hours) |
| **Dependencies** | WS-J4, WS-J5 (governance layer), WS-L1 (Keycloak infrastructure) |
| **Validates** | RFC 8693 token exchange, backend OAuth token acquisition |
| **Unblocks** | Production-grade backend authentication (replaces vault-sourced static tokens) |

---

## Problem Statement

### Current State

The gateway's `CredentialInjector` retrieves backend OAuth tokens from the Control Plane's vault (`vault://` credential references). These are static tokens stored during service connection — they expire, require manual refresh, and don't support per-request audience/scope narrowing.

```
Agent JWT ──► Gateway ──► CredentialInjector ──► Vault (static token) ──► Backend API
                                                       │
                                            Token may be expired
                                            No per-request scoping
```

### Target State

The gateway exchanges the agent's DeepSecure JWT (or Task Token) for a backend-specific OAuth access token via Keycloak's token exchange endpoint. This provides fresh, audience-scoped tokens for each backend call.

```
Agent JWT ──► Gateway ──► TokenExchangeClient ──► Keycloak ──► Backend OAuth Token ──► Backend API
                                │                     │
                         subject_token=JWT       RFC 8693 exchange
                         audience=backend        Fresh, scoped token
```

---

## Component Specification

### Module: `TokenExchangeClient`

| Field | Value |
|-------|-------|
| **Module** | `deeptrail_gateway.app.security.token_exchange` |
| **File** | `deeptrail-gateway/app/security/token_exchange.py` |
| **Type** | Class |
| **Pattern** | Configurable client with caching and module accessor |

### Core Data Models

```python
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


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


@dataclass
class TokenExchangeConfig:
    """Configuration for the token exchange client."""
    enabled: bool = True
    keycloak_url: str = "http://localhost:8080"
    realm: str = "deepsecure"
    client_id: str = "gateway"
    client_secret: str = "gateway-secret"
    cache_ttl_buffer_seconds: int = 60  # Cache tokens until (expires_in - buffer)
    request_timeout_seconds: int = 10
    # Backend audience mapping: backend_id → Keycloak audience/resource
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
        from datetime import timedelta
        if self.expires_in <= 0:
            return True
        return datetime.now(timezone.utc) > self.issued_at + timedelta(seconds=self.expires_in)


class TokenExchangeError(Exception):
    """Base error for token exchange operations."""
    def __init__(self, message: str, error_code: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.error_code = error_code
        self.details = details or {}


class TokenExchangeUnavailableError(TokenExchangeError):
    """Keycloak is unreachable."""
    pass


class TokenExchangeDeniedError(TokenExchangeError):
    """Exchange was denied (invalid subject, insufficient scope, etc.)."""
    pass
```

### Interface Contract

```python
import httpx
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class TokenExchangeClient:
    """Exchanges DeepSecure JWTs for backend-specific OAuth tokens via Keycloak.

    Implements RFC 8693 (OAuth 2.0 Token Exchange) using Keycloak's
    token exchange endpoint. Caches exchanged tokens to minimize
    round-trips to Keycloak.
    """

    def __init__(self, config: Optional[TokenExchangeConfig] = None):
        self._config = config or TokenExchangeConfig()
        self._cache: Dict[str, ExchangedToken] = {}  # cache_key → ExchangedToken
        self._http_client: Optional[httpx.AsyncClient] = None

    @property
    def token_endpoint(self) -> str:
        """Keycloak OIDC token endpoint URL."""
        return (
            f"{self._config.keycloak_url}/realms/{self._config.realm}"
            f"/protocol/openid-connect/token"
        )

    async def exchange_token(
        self,
        subject_token: str,
        backend_id: str,
        scopes: Optional[List[str]] = None,
    ) -> ExchangedToken:
        """Exchange a DeepSecure JWT for a backend-specific OAuth token.

        Args:
            subject_token: The agent JWT or task token to exchange.
            backend_id: Backend service identifier (e.g., "hubspot", "notion").
            scopes: Optional specific scopes to request.

        Returns:
            ExchangedToken with the backend access token.

        Raises:
            TokenExchangeUnavailableError: Keycloak is unreachable.
            TokenExchangeDeniedError: Exchange denied by Keycloak.
            TokenExchangeError: Other exchange failures.
        """
        ...

    async def get_backend_token(
        self,
        subject_token: str,
        backend_id: str,
        scopes: Optional[List[str]] = None,
        force_refresh: bool = False,
    ) -> ExchangedToken:
        """Get a backend token, using cache when available.

        This is the primary method called by the credential injection pipeline.
        Checks cache first, then performs exchange if needed.

        Args:
            subject_token: The agent JWT or task token.
            backend_id: Backend service identifier.
            scopes: Optional specific scopes.
            force_refresh: Bypass cache and force a new exchange.

        Returns:
            ExchangedToken (from cache or fresh exchange).
        """
        ...

    def _build_exchange_params(
        self,
        subject_token: str,
        backend_id: str,
        scopes: Optional[List[str]] = None,
    ) -> Dict[str, str]:
        """Build RFC 8693 token exchange form parameters."""
        audience = self._config.audience_map.get(backend_id, backend_id)
        params = {
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
        import hashlib
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
        # Reduce effective TTL by buffer to avoid using nearly-expired tokens
        token.expires_in = max(0, token.expires_in - self._config.cache_ttl_buffer_seconds)
        self._cache[cache_key] = token

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
```

### Module-Level Accessor Pattern

```python
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
    return _exchange_client


def reset_token_exchange_client() -> None:
    """Reset exchange client (for testing)."""
    global _exchange_client
    _exchange_client = None
```

### Integration: Credential Injection Enhancement

The `CredentialInjector` gains a new path: when token exchange is configured, it can obtain fresh backend tokens via Keycloak instead of (or as fallback to) vault-sourced tokens.

```python
# In deeptrail-gateway/app/middleware/credential_injection.py
# Add to inject_credentials():

exchange_client = get_token_exchange_client()
if exchange_client and exchange_client._config.enabled:
    try:
        exchanged = await exchange_client.get_backend_token(
            subject_token=agent_jwt_token,
            backend_id=backend_id,
        )
        return InjectionResult(
            headers={"Authorization": f"Bearer {exchanged.access_token}"},
            credential_source="token_exchange",
        )
    except TokenExchangeError:
        logger.warning("Token exchange failed, falling back to vault")
        # Fall through to existing vault path
```

### Startup Configuration

```python
# In deeptrail-gateway/app/main.py
from app.security.token_exchange import configure_token_exchange_client, TokenExchangeConfig

# During app startup:
configure_token_exchange_client(
    TokenExchangeConfig(
        keycloak_url=settings.KEYCLOAK_URL,
        realm=settings.KEYCLOAK_REALM,
        client_id=settings.KEYCLOAK_GATEWAY_CLIENT_ID,
        client_secret=settings.KEYCLOAK_GATEWAY_CLIENT_SECRET,
    )
)
```

---

## API Contracts

> **Note:** This task implements an internal security module, not API endpoints.
> The token exchange client operates within the credential injection pipeline.
> No new HTTP endpoints are created on the gateway.
>
> The gateway calls Keycloak's token endpoint:
> `POST {keycloak_url}/realms/{realm}/protocol/openid-connect/token`

### Keycloak Token Exchange Request (RFC 8693)

```
POST /realms/deepsecure/protocol/openid-connect/token HTTP/1.1
Host: localhost:8080
Content-Type: application/x-www-form-urlencoded

grant_type=urn:ietf:params:oauth:grant-type:token-exchange
&client_id=gateway
&client_secret=gateway-secret
&subject_token=eyJhbGciOiJIUzI1NiJ9...
&subject_token_type=urn:ietf:params:oauth:token-type:access_token
&requested_token_type=urn:ietf:params:oauth:token-type:access_token
&audience=hubspot
```

### Keycloak Token Exchange Response (Success)

```json
{
  "access_token": "eyJhbGciOiJSUzI1NiJ9...",
  "token_type": "Bearer",
  "expires_in": 300,
  "scope": "contacts:read"
}
```

### Keycloak Token Exchange Response (Error)

```json
{
  "error": "invalid_grant",
  "error_description": "token is not active"
}
```

---

## File Location Rules

| Artifact | Correct Location |
|----------|------------------|
| Implementation | `deeptrail-gateway/app/security/token_exchange.py` |
| Unit tests | `deeptrail-gateway/tests/security/test_token_exchange.py` |
| Integration point | `deeptrail-gateway/app/middleware/credential_injection.py` (modify) |
| Configuration | `deeptrail-gateway/app/main.py` (add `configure_token_exchange_client()`) |
| Exports | `deeptrail-gateway/app/security/__init__.py` (update) |

---

## Technical Requirements

### Framework-Specific

| Requirement | Pattern | Why |
|-------------|---------|-----|
| Async HTTP client | `httpx.AsyncClient` | Token exchange is async I/O |
| Module accessor | `get_*`, `configure_*`, `reset_*` | Gateway security module pattern |
| Token caching | In-memory dict with TTL buffer | Avoid round-trip per tool call |
| Fallback | Token exchange → vault fallback | Graceful degradation |
| Form-encoded body | `application/x-www-form-urlencoded` | OAuth token endpoint standard |

### Dependencies

| Dependency | Version | Purpose |
|------------|---------|---------|
| `httpx` | existing | Async HTTP client for Keycloak calls |
| `hashlib` | stdlib | Cache key generation |
| `logging` | stdlib | Structured logging |
| `dataclasses` | stdlib | Configuration and result models |

### Existing Code Relationship

| Existing Module | Relationship | Notes |
|-----------------|-------------|-------|
| `credential_injection.py` | Integration point | Add token exchange as primary path, vault as fallback |
| `fail_closed.py` | Pattern reference | Module accessor pattern |
| `prompt_injection.py` (J5) | Sibling security module | Same module structure |
| `result_filter.py` (J4) | Sibling security module | Same module structure |

---

## Test Cases

### Unit Tests

| Test Case | Method | Expected | Notes |
|-----------|--------|----------|-------|
| Exchange token success | `exchange_token()` | `ExchangedToken` with access_token | Mock Keycloak response |
| Exchange token denied | `exchange_token()` | `TokenExchangeDeniedError` | Keycloak returns `invalid_grant` |
| Exchange Keycloak unavailable | `exchange_token()` | `TokenExchangeUnavailableError` | Connection error |
| Build exchange params | `_build_exchange_params()` | Correct RFC 8693 params | Form params verified |
| Audience mapping | `_build_exchange_params()` | Mapped audience used | `audience_map` config |
| Cache hit | `get_backend_token()` | Cached token returned | No HTTP call |
| Cache miss | `get_backend_token()` | Fresh exchange performed | HTTP call made |
| Cache expired | `get_backend_token()` | Fresh exchange | Expired entry evicted |
| Force refresh bypasses cache | `get_backend_token()` | Fresh exchange | `force_refresh=True` |
| Cache TTL buffer | `_put_cache()` | `expires_in` reduced by buffer | Avoids nearly-expired tokens |
| Token is_expired property | `ExchangedToken.is_expired` | True when past expiry | Datetime comparison |
| Disabled client passthrough | `get_backend_token()` | Not called | `enabled=False` |
| Module accessor lifecycle | `configure/get/reset` | Lifecycle works | Global state |
| Scopes included in request | `_build_exchange_params()` | `scope` param set | Space-separated |

### Integration Tests

| Test Case | Setup | Expected | Notes |
|-----------|-------|----------|-------|
| Exchange via live Keycloak | Keycloak running, gateway client configured | Valid backend token | E2E with Keycloak |
| Credential injection with exchange | Token exchange configured | Backend gets exchanged token | Full pipeline |
| Fallback to vault on exchange failure | Keycloak down, vault has token | Vault token used | Graceful degradation |

### Test Code Example

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta, timezone

from deeptrail_gateway.app.security.token_exchange import (
    TokenExchangeClient,
    TokenExchangeConfig,
    ExchangedToken,
    TokenExchangeDeniedError,
    TokenExchangeUnavailableError,
    configure_token_exchange_client,
    get_token_exchange_client,
    reset_token_exchange_client,
)


class TestTokenExchangeClient:
    def setup_method(self):
        self.config = TokenExchangeConfig(
            keycloak_url="http://keycloak:8080",
            realm="deepsecure",
            client_id="gateway",
            client_secret="secret",
            audience_map={"hubspot": "hubspot-api", "notion": "notion-api"},
        )
        self.client = TokenExchangeClient(config=self.config)

    def test_token_endpoint_url(self):
        assert self.client.token_endpoint == (
            "http://keycloak:8080/realms/deepsecure/protocol/openid-connect/token"
        )

    def test_build_exchange_params(self):
        params = self.client._build_exchange_params(
            subject_token="jwt-token",
            backend_id="hubspot",
            scopes=["contacts:read"],
        )
        assert params["grant_type"] == "urn:ietf:params:oauth:grant-type:token-exchange"
        assert params["subject_token"] == "jwt-token"
        assert params["audience"] == "hubspot-api"
        assert params["scope"] == "contacts:read"

    def test_audience_map_fallback(self):
        params = self.client._build_exchange_params(
            subject_token="jwt-token",
            backend_id="unknown-backend",
        )
        assert params["audience"] == "unknown-backend"

    def test_cache_key_deterministic(self):
        key1 = self.client._cache_key("token-a", "hubspot")
        key2 = self.client._cache_key("token-a", "hubspot")
        assert key1 == key2

    def test_cache_key_varies_by_backend(self):
        key1 = self.client._cache_key("token-a", "hubspot")
        key2 = self.client._cache_key("token-a", "notion")
        assert key1 != key2

    def test_exchanged_token_not_expired(self):
        token = ExchangedToken(
            access_token="x",
            expires_in=300,
            issued_at=datetime.now(timezone.utc),
        )
        assert not token.is_expired

    def test_exchanged_token_expired(self):
        token = ExchangedToken(
            access_token="x",
            expires_in=1,
            issued_at=datetime.now(timezone.utc) - timedelta(seconds=10),
        )
        assert token.is_expired

    def test_module_accessor_lifecycle(self):
        reset_token_exchange_client()
        assert get_token_exchange_client() is None

        client = configure_token_exchange_client(self.config)
        assert get_token_exchange_client() is client

        reset_token_exchange_client()
        assert get_token_exchange_client() is None
```

---

## Contract Verification Checklist

- [ ] `TokenExchangeClient` class in `deeptrail-gateway/app/security/token_exchange.py`
- [ ] `exchange_token()` sends RFC 8693 form POST to Keycloak token endpoint
- [ ] `get_backend_token()` checks cache before exchange
- [ ] Token caching with TTL buffer (expires_in - buffer_seconds)
- [ ] `_build_exchange_params()` produces correct RFC 8693 parameters
- [ ] Audience mapping via `audience_map` config with fallback to `backend_id`
- [ ] Error hierarchy: `TokenExchangeError`, `TokenExchangeUnavailableError`, `TokenExchangeDeniedError`
- [ ] Module accessor pattern: `get_*`, `configure_*`, `reset_*`
- [ ] `credential_injection.py` enhanced: exchange → vault fallback
- [ ] `main.py` calls `configure_token_exchange_client()` on startup
- [ ] Exports added to `app/security/__init__.py`
- [ ] Async HTTP client (`httpx.AsyncClient`) used for Keycloak calls
- [ ] No secrets logged (token values never in log output)
- [ ] All unit tests pass

---

## Security Considerations

| Aspect | Status | Notes |
|--------|--------|-------|
| Token confidentiality | Protected | `client_secret` never logged; exchanged tokens cached in-memory only |
| Token scoping | Enforced | `audience` parameter limits backend access |
| Token lifetime | Bounded | Cached with TTL buffer; never used past expiry |
| Fallback security | Safe | Vault fallback uses existing credential path |
| TLS | Required (prod) | Keycloak URL should use HTTPS in production |
| Client authentication | Confidential client | `client_id` + `client_secret` in form body |

---

## Keycloak Configuration Prerequisites

The following must be configured in Keycloak (done in WS-L1 realm setup):

1. **Client: `gateway`** — confidential client with token exchange enabled
2. **Token Exchange permission** — `gateway` client allowed to exchange tokens
3. **Audience mappers** — map backend audiences to Keycloak clients/resources
4. **Scope definitions** — backend-specific scopes registered

---

## References

- **RFC 8693:** OAuth 2.0 Token Exchange — https://datatracker.ietf.org/doc/html/rfc8693
- **Architecture:** `deepsecure-comprehensive-architecture-consolidated.md` — OAuth Authorization Layer, Token Exchange Client
- **Breakdown:** `mvp-production-readiness-breakdown.md` — WS-J3: RFC 8693 token exchange
- **L1 Spec:** [WS-L1-spec.md](./WS-L1-spec.md) — Keycloak realm config, gateway client
- **Existing Pattern:** `deeptrail-gateway/app/middleware/credential_injection.py` — current credential path
- **Module Pattern:** `deeptrail-gateway/app/security/fail_closed.py` — module accessor
- **Upstream Dependencies:** WS-J4 (PII masking), WS-J5 (prompt injection), WS-L1 (Keycloak infrastructure)
- **Downstream Dependents:** Production deployment, P2 validation (Keycloak token exchange test)
