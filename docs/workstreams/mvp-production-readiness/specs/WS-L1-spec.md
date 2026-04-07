# Task Specification: WS-L1 Create IdP Service (OIDC Abstraction + Keycloak)

> **IMMUTABLE AFTER DESIGN APPROVAL**
>
> This specification defines what implementation MUST match exactly.
> Do not modify without updating the design doc first.
>
> **Source:** `plans/mvp_production_readiness.plan.md` P2-1, `deepsecure-comprehensive-architecture-consolidated.md` Section 6
>
> **Design Decision:** Option C — Keycloak as dev-time IdP, generic OIDC abstraction for production swappability.

---

## Overview

| Field | Value |
|-------|-------|
| **Task ID** | WS-L1 |
| **Task Name** | Create IdP Service (OIDC Abstraction + Keycloak) |
| **Type** | Service + Infrastructure |
| **Service** | deeptrail-control + docker-compose |
| **Complexity** | L (3+ hours) |
| **Dependencies** | MP3.5 (P1.5 complete) |
| **Validates** | Token Layers 0-1 (User ID-Token, Agent-ID Token), Enterprise SSO foundation |
| **Unblocks** | WS-L2 (SSO endpoints), WS-J6 (Keycloak token exchange reuses same instance) |

---

## Problem Statement

### Current State (MVP)

```
User login → POST /api/v1/auth/login → UserAuthService
                                        ↓
                                  Hardcoded password check
                                        ↓
                                  JWT issued by Control Plane
                                  (no external IdP)
```

**Root Cause:** No integration with any external identity provider. User identity is simulated with hardcoded config. Token Layers 0 (User ID-Token) and 1 (Agent-ID Token) are not implemented.

### Desired State

```
User login → GET /api/v1/auth/sso/{idp}/authorize → IdPService
                                                      ↓
                                                OIDCProvider.get_authorization_url()
                                                      ↓
                                                Redirect to Keycloak (dev) / Okta (prod)
                                                      ↓
                                                User authenticates at IdP
                                                      ↓
                                                OIDC callback with auth code
                                                      ↓
                                                OIDCProvider.exchange_code()
                                                      ↓
                                                Validate ID token, provision user
                                                      ↓
                                                Issue DeepSecure session JWT
```

---

## API Contracts

> **Note:** This task implements an internal service module (`idp_service.py`) and infrastructure (Keycloak docker-compose), not API endpoints directly.
> See **WS-L2** for the SSO API endpoints (`/sso/{idp}/authorize`, `/callback`, `/logout`) that consume this service.

---

## Component Specification

### 1. OIDCProvider Protocol

| Field | Value |
|-------|-------|
| **Module** | `deeptrail-control/app/services/idp_service.py` |
| **Type** | Protocol (typing.Protocol) |
| **Purpose** | Abstract interface for OIDC identity providers |

```python
from typing import Protocol, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class OIDCTokens:
    """Token set returned by OIDC code exchange."""
    id_token: str
    access_token: str
    refresh_token: Optional[str] = None
    expires_at: Optional[datetime] = None
    token_type: str = "Bearer"


@dataclass
class OIDCClaims:
    """Validated claims from an OIDC ID token."""
    sub: str
    email: str
    email_verified: bool = False
    name: Optional[str] = None
    given_name: Optional[str] = None
    family_name: Optional[str] = None
    groups: list[str] | None = None
    roles: list[str] | None = None
    issuer: Optional[str] = None
    audience: Optional[str] = None
    issued_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    raw_claims: dict | None = None


@dataclass
class UserInfo:
    """User profile information from the IdP userinfo endpoint."""
    sub: str
    email: str
    name: Optional[str] = None
    groups: list[str] | None = None
    roles: list[str] | None = None
    organization_id: Optional[str] = None


class OIDCProvider(Protocol):
    """Protocol defining the contract for OIDC identity providers.

    Implementations must support the Authorization Code flow with PKCE.
    Dev: KeycloakProvider (local docker container)
    Prod: OktaProvider, EntraIDProvider (SaaS)
    """

    async def get_authorization_url(
        self,
        state: str,
        redirect_uri: str,
        scopes: list[str] | None = None,
    ) -> str:
        """Generate the IdP authorization URL for the OIDC Authorization Code flow.

        Args:
            state: CSRF protection state parameter (opaque, caller-generated).
            redirect_uri: Where the IdP should redirect after authentication.
            scopes: OIDC scopes to request. Defaults to ["openid", "profile", "email"].

        Returns:
            Full authorization URL to redirect the user to.
        """
        ...

    async def exchange_code(
        self,
        code: str,
        redirect_uri: str,
    ) -> OIDCTokens:
        """Exchange an authorization code for tokens.

        Args:
            code: The authorization code from the IdP callback.
            redirect_uri: Must match the redirect_uri used in get_authorization_url.

        Returns:
            OIDCTokens with id_token, access_token, and optional refresh_token.

        Raises:
            OIDCError: If code exchange fails (expired, invalid, etc.).
        """
        ...

    async def validate_token(self, id_token: str) -> OIDCClaims:
        """Validate an OIDC ID token and extract claims.

        Validates:
        - Signature (using IdP's JWKS endpoint)
        - Issuer (matches configured issuer)
        - Audience (matches configured client_id)
        - Expiration (not expired)
        - Nonce (if provided)

        Args:
            id_token: The raw JWT ID token string.

        Returns:
            OIDCClaims with validated, extracted claims.

        Raises:
            OIDCError: If token validation fails for any reason.
        """
        ...

    async def get_user_info(self, access_token: str) -> UserInfo:
        """Fetch user profile from the IdP's userinfo endpoint.

        Args:
            access_token: A valid OIDC access token.

        Returns:
            UserInfo with user profile data.

        Raises:
            OIDCError: If the userinfo request fails.
        """
        ...

    async def refresh_token(self, refresh_token: str) -> OIDCTokens:
        """Refresh an expired access token using a refresh token.

        Args:
            refresh_token: A valid OIDC refresh token.

        Returns:
            New OIDCTokens with fresh access_token (and possibly new refresh_token).

        Raises:
            OIDCError: If refresh fails (token revoked, expired, etc.).
        """
        ...

    async def logout_url(
        self,
        id_token_hint: Optional[str] = None,
        post_logout_redirect_uri: Optional[str] = None,
    ) -> str:
        """Generate the IdP logout URL.

        Args:
            id_token_hint: The ID token to hint which session to end.
            post_logout_redirect_uri: Where to redirect after logout.

        Returns:
            Logout URL to redirect the user to.
        """
        ...
```

### 2. OIDCError Exception

```python
class OIDCError(Exception):
    """Base exception for OIDC operations."""

    def __init__(self, message: str, error_code: str | None = None, details: dict | None = None):
        super().__init__(message)
        self.error_code = error_code
        self.details = details or {}


class OIDCTokenExpiredError(OIDCError):
    """Token has expired."""
    pass


class OIDCTokenInvalidError(OIDCError):
    """Token signature or claims validation failed."""
    pass


class OIDCProviderUnavailableError(OIDCError):
    """IdP is unreachable or returned an error."""
    pass
```

### 3. KeycloakProvider Implementation

| Field | Value |
|-------|-------|
| **Module** | `deeptrail-control/app/services/providers/keycloak.py` |
| **Type** | Class implementing OIDCProvider |
| **Purpose** | OIDC client for Keycloak (dev-time and default IdP) |

```python
import httpx
import logging
from jose import jwt, JWTError

logger = logging.getLogger(__name__)


class KeycloakProvider:
    """OIDC provider implementation for Keycloak.

    Used as the dev-time IdP and as the default provider.
    In production, Keycloak can also serve as an SSO broker,
    federating to upstream IdPs (Okta, Entra ID) via identity brokering.
    """

    def __init__(
        self,
        issuer_url: str,
        client_id: str,
        client_secret: str | None = None,
        realm: str = "deepsecure",
    ):
        self._issuer_url = issuer_url.rstrip("/")
        self._client_id = client_id
        self._client_secret = client_secret
        self._realm = realm

        # Standard OIDC endpoints derived from issuer
        self._auth_endpoint = f"{self._issuer_url}/protocol/openid-connect/auth"
        self._token_endpoint = f"{self._issuer_url}/protocol/openid-connect/token"
        self._userinfo_endpoint = f"{self._issuer_url}/protocol/openid-connect/userinfo"
        self._jwks_uri = f"{self._issuer_url}/protocol/openid-connect/certs"
        self._logout_endpoint = f"{self._issuer_url}/protocol/openid-connect/logout"

        self._jwks_cache: dict | None = None

    async def get_authorization_url(
        self,
        state: str,
        redirect_uri: str,
        scopes: list[str] | None = None,
    ) -> str:
        scopes = scopes or ["openid", "profile", "email"]
        params = {
            "response_type": "code",
            "client_id": self._client_id,
            "redirect_uri": redirect_uri,
            "scope": " ".join(scopes),
            "state": state,
        }
        query = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{self._auth_endpoint}?{query}"

    async def exchange_code(self, code: str, redirect_uri: str) -> OIDCTokens:
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": self._client_id,
        }
        if self._client_secret:
            data["client_secret"] = self._client_secret

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self._token_endpoint,
                data=data,
                timeout=10.0,
            )
            if response.status_code != 200:
                raise OIDCError(
                    f"Token exchange failed: {response.status_code}",
                    error_code="token_exchange_failed",
                    details=response.json() if response.headers.get("content-type", "").startswith("application/json") else {},
                )
            token_data = response.json()

        return OIDCTokens(
            id_token=token_data["id_token"],
            access_token=token_data["access_token"],
            refresh_token=token_data.get("refresh_token"),
            token_type=token_data.get("token_type", "Bearer"),
        )

    async def validate_token(self, id_token: str) -> OIDCClaims:
        jwks = await self._get_jwks()

        try:
            claims = jwt.decode(
                id_token,
                jwks,
                algorithms=["RS256"],
                audience=self._client_id,
                issuer=self._issuer_url,
            )
        except JWTError as e:
            raise OIDCTokenInvalidError(
                f"ID token validation failed: {e}",
                error_code="token_invalid",
            )

        return OIDCClaims(
            sub=claims["sub"],
            email=claims.get("email", ""),
            email_verified=claims.get("email_verified", False),
            name=claims.get("name"),
            given_name=claims.get("given_name"),
            family_name=claims.get("family_name"),
            groups=claims.get("groups"),
            roles=claims.get("realm_access", {}).get("roles"),
            issuer=claims.get("iss"),
            audience=claims.get("aud"),
            raw_claims=claims,
        )

    async def get_user_info(self, access_token: str) -> UserInfo:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                self._userinfo_endpoint,
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=10.0,
            )
            if response.status_code != 200:
                raise OIDCError(
                    f"Userinfo request failed: {response.status_code}",
                    error_code="userinfo_failed",
                )
            data = response.json()

        return UserInfo(
            sub=data["sub"],
            email=data.get("email", ""),
            name=data.get("name"),
            groups=data.get("groups"),
            roles=data.get("realm_access", {}).get("roles"),
        )

    async def refresh_token(self, refresh_token: str) -> OIDCTokens:
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": self._client_id,
        }
        if self._client_secret:
            data["client_secret"] = self._client_secret

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self._token_endpoint,
                data=data,
                timeout=10.0,
            )
            if response.status_code != 200:
                raise OIDCError(
                    f"Token refresh failed: {response.status_code}",
                    error_code="refresh_failed",
                )
            token_data = response.json()

        return OIDCTokens(
            id_token=token_data.get("id_token", ""),
            access_token=token_data["access_token"],
            refresh_token=token_data.get("refresh_token", refresh_token),
            token_type=token_data.get("token_type", "Bearer"),
        )

    async def logout_url(
        self,
        id_token_hint: str | None = None,
        post_logout_redirect_uri: str | None = None,
    ) -> str:
        params = {}
        if id_token_hint:
            params["id_token_hint"] = id_token_hint
        if post_logout_redirect_uri:
            params["post_logout_redirect_uri"] = post_logout_redirect_uri
        query = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{self._logout_endpoint}?{query}" if query else self._logout_endpoint

    async def _get_jwks(self) -> dict:
        if self._jwks_cache:
            return self._jwks_cache
        async with httpx.AsyncClient() as client:
            response = await client.get(self._jwks_uri, timeout=10.0)
            if response.status_code != 200:
                raise OIDCProviderUnavailableError(
                    f"JWKS fetch failed: {response.status_code}",
                    error_code="jwks_unavailable",
                )
            self._jwks_cache = response.json()
        return self._jwks_cache
```

### 4. IdP Configuration Model

| Field | Value |
|-------|-------|
| **Module** | `deeptrail-control/app/core/idp_config.py` |
| **Type** | Pydantic Settings |
| **Purpose** | Configuration for IdP provider selection and connection |

```python
from pydantic_settings import BaseSettings
from pydantic import Field
from enum import Enum


class IdPProviderType(str, Enum):
    KEYCLOAK = "keycloak"
    OKTA = "okta"
    ENTRA = "entra"


class IdPConfig(BaseSettings):
    """IdP configuration loaded from environment variables.

    Environment variables:
        IDP_PROVIDER: Provider type (keycloak, okta, entra). Default: keycloak
        IDP_ISSUER_URL: OIDC issuer URL
        IDP_CLIENT_ID: OIDC client ID registered at the IdP
        IDP_CLIENT_SECRET: OIDC client secret (optional for public clients)
        IDP_REALM: Keycloak realm name (only for keycloak provider)
        IDP_REDIRECT_URI: Default redirect URI after authentication
    """

    provider: IdPProviderType = Field(
        default=IdPProviderType.KEYCLOAK,
        alias="IDP_PROVIDER",
    )
    issuer_url: str = Field(
        default="http://localhost:8080/realms/deepsecure",
        alias="IDP_ISSUER_URL",
    )
    client_id: str = Field(
        default="deepsecure-control",
        alias="IDP_CLIENT_ID",
    )
    client_secret: str | None = Field(
        default=None,
        alias="IDP_CLIENT_SECRET",
    )
    realm: str = Field(
        default="deepsecure",
        alias="IDP_REALM",
    )
    redirect_uri: str = Field(
        default="http://localhost:8000/api/v1/auth/sso/callback",
        alias="IDP_REDIRECT_URI",
    )

    class Config:
        env_prefix = ""
        case_sensitive = True
```

### 5. Provider Factory

```python
# In deeptrail-control/app/services/idp_service.py

from .providers.keycloak import KeycloakProvider
from ..core.idp_config import IdPConfig, IdPProviderType

import logging

logger = logging.getLogger(__name__)


def create_oidc_provider(config: IdPConfig | None = None) -> OIDCProvider:
    """Factory to create the configured OIDC provider.

    Args:
        config: IdP configuration. If None, loads from environment.

    Returns:
        An OIDCProvider implementation based on the configured provider type.

    Raises:
        ValueError: If the provider type is not supported.
    """
    if config is None:
        config = IdPConfig()

    if config.provider == IdPProviderType.KEYCLOAK:
        logger.info("Creating KeycloakProvider: issuer=%s, realm=%s", config.issuer_url, config.realm)
        return KeycloakProvider(
            issuer_url=config.issuer_url,
            client_id=config.client_id,
            client_secret=config.client_secret,
            realm=config.realm,
        )
    elif config.provider == IdPProviderType.OKTA:
        raise NotImplementedError("OktaProvider not yet implemented. Use KeycloakProvider with Okta identity brokering.")
    elif config.provider == IdPProviderType.ENTRA:
        raise NotImplementedError("EntraIDProvider not yet implemented. Use KeycloakProvider with Entra identity brokering.")
    else:
        raise ValueError(f"Unknown IdP provider: {config.provider}")
```

### 6. User Provisioning Service

```python
# In deeptrail-control/app/services/idp_service.py

async def provision_user_from_claims(claims: OIDCClaims) -> dict:
    """Create or update a user record from OIDC claims.

    Called after successful OIDC authentication. Maps IdP claims
    to DeepSecure's internal user model.

    Args:
        claims: Validated OIDC claims from the ID token.

    Returns:
        Dict with user_id, email, is_new_user, and mapped roles.
    """
    # Implementation should:
    # 1. Look up user by claims.sub (IdP subject identifier)
    # 2. If not found, create new user with email, name from claims
    # 3. If found, update last_login, sync groups/roles
    # 4. Map IdP groups to DeepSecure roles
    # 5. Return user dict with is_new_user flag
    ...
```

---

## Infrastructure Specification

### 7. Keycloak Docker Service

Add to `docker-compose.yml`:

```yaml
  keycloak:
    image: quay.io/keycloak/keycloak:24.0
    command: start-dev --import-realm
    environment:
      - KEYCLOAK_ADMIN=admin
      - KEYCLOAK_ADMIN_PASSWORD=admin
      - KC_HEALTH_ENABLED=true
    ports:
      - "8080:8080"
    volumes:
      - ./config/keycloak:/opt/keycloak/data/import
    healthcheck:
      test: ["CMD-SHELL", "exec 3<>/dev/tcp/localhost/8080 && echo -e 'GET /health/ready HTTP/1.1\\r\\nHost: localhost\\r\\n\\r\\n' >&3 && head -1 <&3 | grep -q '200'"]
      interval: 10s
      timeout: 5s
      retries: 15
      start_period: 30s
    depends_on:
      - db
```

### 8. Keycloak Realm Configuration

**File:** `config/keycloak/deepsecure-realm.json`

The realm export must include:

| Component | Value | Purpose |
|-----------|-------|---------|
| **Realm** | `deepsecure` | Namespace for all DeepSecure IdP config |
| **Client: deepsecure-control** | Confidential, Authorization Code + PKCE | Control Plane OIDC client |
| **Client: gateway** | Confidential, Client Credentials + Token Exchange | Gateway token exchange (for WS-J6) |
| **User: sarah@acme.com** | Password: `test_password`, Groups: `acme-org` | Test user matching E2E demo |
| **User: admin@acme.com** | Password: `admin_password`, Groups: `acme-org`, Roles: `admin` | Admin test user |
| **Group: acme-org** | Default group | Organization grouping |
| **Role: user** | Default realm role | Basic user access |
| **Role: admin** | Admin realm role | Administrative access |
| **Token settings** | Access token: 5 min, Refresh token: 30 min | Standard short-lived tokens |

**Valid redirect URIs for deepsecure-control client:**
- `http://localhost:8000/api/v1/auth/sso/*/callback`
- `http://localhost:8000/*` (dev only)

---

## Error Handling Matrix

| Scenario | Behavior | User Impact |
|----------|----------|-------------|
| Keycloak healthy | Normal OIDC flow | None |
| Keycloak unreachable | Raise `OIDCProviderUnavailableError` | SSO login unavailable, fallback to password login |
| Invalid ID token signature | Raise `OIDCTokenInvalidError` | Authentication rejected |
| Expired ID token | Raise `OIDCTokenExpiredError` | Re-authentication required |
| JWKS endpoint unavailable | Raise `OIDCProviderUnavailableError` | Cannot validate tokens |
| Unknown provider configured | Raise `ValueError` at startup | Application fails to start (fail-fast) |
| Code exchange fails (expired code) | Raise `OIDCError` | User must restart login flow |

**Key Principle:** Fail-closed for authentication. If the IdP is unavailable, SSO login is blocked. Password-based login (existing `/api/v1/auth/login`) remains available as fallback.

---

## File Location Rules

| Artifact | Correct Location | Notes |
|----------|------------------|-------|
| OIDCProvider protocol + factory | `deeptrail-control/app/services/idp_service.py` | Core abstraction |
| Provider implementations | `deeptrail-control/app/services/providers/` | One file per provider |
| KeycloakProvider | `deeptrail-control/app/services/providers/keycloak.py` | Dev + default |
| OktaProvider stub | `deeptrail-control/app/services/providers/okta.py` | Future (raises NotImplementedError) |
| EntraIDProvider stub | `deeptrail-control/app/services/providers/entra.py` | Future (raises NotImplementedError) |
| IdP configuration | `deeptrail-control/app/core/idp_config.py` | Pydantic settings |
| Keycloak realm config | `config/keycloak/deepsecure-realm.json` | Imported on container start |
| Docker service | `docker-compose.yml` | Keycloak service definition |
| Unit tests | `deeptrail-control/tests/services/test_idp_service.py` | Mock OIDCProvider |
| Provider tests | `deeptrail-control/tests/services/providers/test_keycloak.py` | Integration with Keycloak |

---

## Dependencies

### Python Packages (add to requirements.txt / pyproject.toml)

| Package | Version | Purpose |
|---------|---------|---------|
| `python-jose[cryptography]` | >=3.3.0 | JWT validation (RS256, JWKS) |
| `httpx` | >=0.24.0 | Async HTTP client (already in project) |
| `pydantic-settings` | >=2.0.0 | Environment-based configuration |

### Service Dependencies

| Service | Health Check | Required For |
|---------|--------------|--------------|
| Keycloak | `curl http://localhost:8080/health/ready` | OIDC authentication |
| Control Plane | `curl http://localhost:8000/health` | User provisioning |
| PostgreSQL | `pg_isready` | User storage |

---

## Test Cases

### Unit Tests (Mock OIDCProvider)

| Test Case | Method | Expected |
|-----------|--------|----------|
| Factory creates KeycloakProvider for `keycloak` config | `create_oidc_provider(config)` | Returns `KeycloakProvider` instance |
| Factory raises NotImplementedError for `okta` | `create_oidc_provider(okta_config)` | `NotImplementedError` |
| Factory raises ValueError for unknown provider | `create_oidc_provider(bad_config)` | `ValueError` |
| IdPConfig loads defaults from env | `IdPConfig()` | `provider=keycloak`, `issuer_url=http://localhost:8080/realms/deepsecure` |
| OIDCClaims maps standard claims | `OIDCClaims(sub=..., email=...)` | All fields populated |
| Provision user creates new user | `provision_user_from_claims(claims)` | `is_new_user=True` |
| Provision user updates existing user | `provision_user_from_claims(existing_claims)` | `is_new_user=False` |

### KeycloakProvider Unit Tests (Mock httpx)

| Test Case | Method | Expected |
|-----------|--------|----------|
| Authorization URL includes required params | `get_authorization_url(state, redirect_uri)` | URL with `response_type=code`, `client_id`, `state`, `scope` |
| Code exchange returns OIDCTokens | `exchange_code(code, redirect_uri)` | `OIDCTokens` with `id_token`, `access_token` |
| Code exchange handles 400 error | `exchange_code(bad_code, redirect_uri)` | `OIDCError` raised |
| Token validation extracts claims | `validate_token(valid_jwt)` | `OIDCClaims` with `sub`, `email` |
| Token validation rejects expired token | `validate_token(expired_jwt)` | `OIDCTokenInvalidError` |
| Token validation rejects bad signature | `validate_token(tampered_jwt)` | `OIDCTokenInvalidError` |
| Refresh token returns new tokens | `refresh_token(valid_refresh)` | New `OIDCTokens` |
| JWKS cache avoids repeated fetches | Two `validate_token` calls | Only one JWKS HTTP request |
| Logout URL includes id_token_hint | `logout_url(id_token_hint=...)` | URL with `id_token_hint` param |

### Integration Tests (Keycloak Container)

| Test Case | Method | Expected |
|-----------|--------|----------|
| Keycloak health check passes | `GET /health/ready` | `200 OK` |
| Well-known config accessible | `GET /.well-known/openid-configuration` | JSON with endpoints |
| Token exchange with test user | Full auth code flow | Valid `OIDCTokens` returned |
| User info returns profile | `get_user_info(access_token)` | `UserInfo` with `sarah@acme.com` |

---

## Manual Verification

```bash
# 1. Start full stack with Keycloak
docker compose up -d
sleep 30

# 2. Verify Keycloak is healthy
curl -sf http://localhost:8080/health/ready && echo "✅ Keycloak healthy"

# 3. Verify OIDC discovery endpoint
curl -s http://localhost:8080/realms/deepsecure/.well-known/openid-configuration | jq '.issuer'
# Expected: "http://localhost:8080/realms/deepsecure"

# 4. Verify test user can authenticate (Resource Owner Password Grant - dev only)
KC_TOKEN=$(curl -s -X POST http://localhost:8080/realms/deepsecure/protocol/openid-connect/token \
  -d "grant_type=password" \
  -d "client_id=deepsecure-control" \
  -d "client_secret=control-secret" \
  -d "username=sarah@acme.com" \
  -d "password=test_password" | jq -r '.access_token')
echo "Keycloak token: ${KC_TOKEN:0:20}..."

# 5. Verify userinfo
curl -s http://localhost:8080/realms/deepsecure/protocol/openid-connect/userinfo \
  -H "Authorization: Bearer $KC_TOKEN" | jq .
# Expected: {"sub": "...", "email": "sarah@acme.com", ...}

# 6. Run unit tests
cd deeptrail-control
pytest tests/services/test_idp_service.py -v
pytest tests/services/providers/test_keycloak.py -v
```

---

## Contract Verification Checklist

Before marking implementation complete, verify:

- [ ] `OIDCProvider` protocol defined in `idp_service.py` with all 6 methods
- [ ] `OIDCTokens`, `OIDCClaims`, `UserInfo` dataclasses defined
- [ ] `OIDCError` exception hierarchy defined (base + 3 subclasses)
- [ ] `KeycloakProvider` implements all `OIDCProvider` methods
- [ ] `KeycloakProvider` uses JWKS for token validation (not shared secret)
- [ ] JWKS caching implemented (avoid repeated network calls)
- [ ] `IdPConfig` loads from environment variables
- [ ] `create_oidc_provider()` factory creates correct provider from config
- [ ] `providers/__init__.py` exists
- [ ] Keycloak service added to `docker-compose.yml`
- [ ] `config/keycloak/deepsecure-realm.json` created with realm, clients, test users
- [ ] Keycloak health check passes after `docker compose up`
- [ ] Test user `sarah@acme.com` can authenticate against Keycloak
- [ ] Unit tests pass with mocked HTTP client
- [ ] `python-jose[cryptography]` added to dependencies
- [ ] Existing tests not broken

---

## Backward Compatibility

**Non-breaking.** This task adds new modules without modifying existing endpoints. The existing `POST /api/v1/auth/login` password-based flow continues to work unchanged. SSO endpoints (WS-L2) will provide an additional authentication path.

---

## References

- **Architecture:** `docs/design/internal/markdowns/deepsecure-comprehensive-architecture-consolidated.md` Section 6 (Token Hierarchy, "WHO MANAGES WHAT")
- **Design Decision:** Option C from conversation analysis (Keycloak as dev-time IdP, OIDC abstraction)
- **Coverage Matrix:** `docs/workstreams/virtual-mcp-server-mvp/MVP_COVERAGE_MATRIX.md` (Token Layers 0-1: 0% → target ~70%)
- **Downstream:** WS-L2 (SSO endpoints consume this service), WS-J6 (Keycloak token exchange reuses infrastructure)
- **Batch:** P2-B1 (parallel with J4, J5, K6)
