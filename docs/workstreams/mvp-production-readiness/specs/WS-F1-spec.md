# Task Specification: WS-F1 Create OAuth Service

> **IMMUTABLE AFTER DESIGN APPROVAL**
>
> This specification defines what implementation MUST match exactly.
> Do not modify without updating the design doc first.
>
> **Source:** plans/mvp_production_readiness.plan.md - P1-2: Real OAuth Flow for Service Connection

---

## Overview

| Field | Value |
|-------|-------|
| **Task ID** | WS-F1 |
| **Task Name** | Create OAuth service |
| **Type** | Service Creation |
| **Service** | deeptrail-control |
| **Complexity** | L (3+ hours) |
| **Validates** | Real OAuth flows for Notion, Slack, HubSpot |

---

## Current State Analysis

**Existing Implementation:**
- `app/api/v1/endpoints/users.py` - Has `POST /api/v1/users/me/services/connect` endpoint
- `app/services/connected_service_service.py` - Stores tokens after OAuth complete
- `app/services/vault_client.py` - Encrypted token storage

**What's Missing:**
- OAuth authorization URL generation
- OAuth callback handler (authorization_code → tokens)
- OAuth state/PKCE security
- Provider configuration management
- Token exchange logic

---

## Component Specification

### Class: `OAuthService`

| Field | Value |
|-------|-------|
| **Module** | `deeptrail-control/app/services/oauth_service.py` |
| **Type** | Class (create new) |
| **Purpose** | Handle OAuth 2.0 flows for service connections |

### Interface Contract

```python
from dataclasses import dataclass
from enum import Enum

class OAuthProvider(str, Enum):
    """Supported OAuth providers."""
    NOTION = "notion"
    SLACK = "slack"
    HUBSPOT = "hubspot"

@dataclass
class OAuthConfig:
    """Provider-specific OAuth configuration."""
    provider: OAuthProvider
    client_id: str
    client_secret: str
    authorization_url: str
    token_url: str
    scopes: list[str]
    redirect_uri: str
    uses_pkce: bool = False  # Notion requires PKCE

@dataclass
class AuthorizationRequest:
    """OAuth authorization URL request."""
    provider: OAuthProvider
    user_id: str
    requested_scopes: list[str] | None = None
    state: str | None = None  # Generated if not provided

@dataclass
class AuthorizationResponse:
    """OAuth authorization URL response."""
    authorization_url: str
    state: str
    code_verifier: str | None = None  # For PKCE flows

@dataclass
class TokenExchangeRequest:
    """OAuth callback token exchange request."""
    provider: OAuthProvider
    authorization_code: str
    state: str
    code_verifier: str | None = None  # For PKCE flows

@dataclass
class OAuthTokenResponse:
    """Standardized OAuth token response."""
    access_token: str
    token_type: str
    expires_in: int | None
    refresh_token: str | None
    scope: str | None

@dataclass
class TokenRefreshRequest:
    """OAuth token refresh request."""
    provider: OAuthProvider
    refresh_token: str

class OAuthService:
    """
    Handles OAuth 2.0 authorization flows for external services.

    Supports:
    - Authorization URL generation with state/PKCE
    - Authorization code exchange for tokens
    - Token refresh
    - Provider configuration management
    """

    def __init__(
        self,
        vault_client: VaultClient,
        connected_service_service: ConnectedServiceService
    ):
        """Initialize with dependencies."""
        ...

    async def get_authorization_url(
        self,
        request: AuthorizationRequest
    ) -> AuthorizationResponse:
        """
        Generate OAuth authorization URL.

        Args:
            request: Authorization request with provider and user

        Returns:
            AuthorizationResponse with URL, state, and optional code_verifier

        Raises:
            OAuthConfigError: Provider not configured
            OAuthError: URL generation failed
        """
        ...

    async def exchange_code_for_tokens(
        self,
        request: TokenExchangeRequest
    ) -> OAuthTokenResponse:
        """
        Exchange authorization code for tokens.

        Args:
            request: Token exchange request with code and state

        Returns:
            OAuthTokenResponse with tokens

        Raises:
            OAuthStateError: Invalid or expired state
            OAuthExchangeError: Token exchange failed
        """
        ...

    async def refresh_tokens(
        self,
        request: TokenRefreshRequest
    ) -> OAuthTokenResponse:
        """
        Refresh expired OAuth tokens.

        Args:
            request: Refresh request with provider and refresh_token

        Returns:
            OAuthTokenResponse with new tokens

        Raises:
            OAuthRefreshError: Refresh failed (token revoked, etc.)
        """
        ...

    def get_provider_config(
        self,
        provider: OAuthProvider
    ) -> OAuthConfig:
        """
        Get OAuth configuration for provider.

        Args:
            provider: OAuth provider enum

        Returns:
            OAuthConfig for the provider

        Raises:
            OAuthConfigError: Provider not configured
        """
        ...
```

### Public Methods

| Method | Arguments | Returns | Description |
|--------|-----------|---------|-------------|
| `get_authorization_url` | `AuthorizationRequest` | `AuthorizationResponse` | Generate OAuth URL with state/PKCE |
| `exchange_code_for_tokens` | `TokenExchangeRequest` | `OAuthTokenResponse` | Exchange code for tokens |
| `refresh_tokens` | `TokenRefreshRequest` | `OAuthTokenResponse` | Refresh expired tokens |
| `get_provider_config` | `OAuthProvider` | `OAuthConfig` | Get provider configuration |
| `validate_state` | `state: str` | `dict` | Validate and decode state token |

### Private Methods

| Method | Purpose |
|--------|---------|
| `_generate_state` | Create cryptographic state token |
| `_generate_pkce_pair` | Create code_verifier and code_challenge |
| `_store_state` | Store state for validation (Redis/memory) |
| `_validate_and_consume_state` | Validate state token, mark as used |
| `_make_token_request` | HTTP POST to token endpoint |

---

## Provider Configuration

### Notion OAuth Config

| Field | Value |
|-------|-------|
| Authorization URL | `https://api.notion.com/v1/oauth/authorize` |
| Token URL | `https://api.notion.com/v1/oauth/token` |
| PKCE | Required (code_challenge_method: S256) |
| Scopes | Provider manages scopes via integration capabilities |

### Slack OAuth Config

| Field | Value |
|-------|-------|
| Authorization URL | `https://slack.com/oauth/v2/authorize` |
| Token URL | `https://slack.com/api/oauth.v2.access` |
| PKCE | Not required |
| Scopes | `channels:read`, `channels:history`, `chat:write`, `users:read` |

### HubSpot OAuth Config

| Field | Value |
|-------|-------|
| Authorization URL | `https://app.hubspot.com/oauth/authorize` |
| Token URL | `https://api.hubapi.com/oauth/v1/token` |
| PKCE | Not required |
| Scopes | `crm.objects.contacts.read`, `crm.objects.deals.read` |

---

## State Management

### State Token Format

```python
@dataclass
class OAuthState:
    """OAuth state token payload."""
    user_id: str
    provider: str
    nonce: str  # Random bytes for uniqueness
    created_at: datetime
    expires_at: datetime
    code_verifier: str | None = None  # For PKCE
```

### State Storage (MVP)

```python
# In-memory state storage (MVP)
# Production: Use Redis with TTL
_pending_states: dict[str, OAuthState] = {}

async def _store_state(self, state: OAuthState) -> str:
    """Store state and return encoded token."""
    state_token = self._encode_state(state)
    self._pending_states[state_token] = state
    return state_token

async def _validate_and_consume_state(self, state_token: str) -> OAuthState:
    """Validate state token and remove from storage."""
    if state_token not in self._pending_states:
        raise OAuthStateError("Invalid or expired state")

    state = self._pending_states.pop(state_token)

    if datetime.utcnow() > state.expires_at:
        raise OAuthStateError("State token expired")

    return state
```

---

## PKCE Implementation

For Notion (and other PKCE-required providers):

```python
import secrets
import hashlib
import base64

def _generate_pkce_pair(self) -> tuple[str, str]:
    """
    Generate PKCE code_verifier and code_challenge.

    Returns:
        Tuple of (code_verifier, code_challenge)
    """
    # code_verifier: 43-128 character random string
    code_verifier = secrets.token_urlsafe(32)

    # code_challenge: SHA256 hash of verifier, base64url encoded
    challenge_bytes = hashlib.sha256(code_verifier.encode()).digest()
    code_challenge = base64.urlsafe_b64encode(challenge_bytes).rstrip(b'=').decode()

    return code_verifier, code_challenge
```

---

## Error Types

```python
class OAuthError(Exception):
    """Base OAuth error."""
    pass

class OAuthConfigError(OAuthError):
    """Provider not configured or invalid configuration."""
    pass

class OAuthStateError(OAuthError):
    """Invalid, expired, or missing state token."""
    pass

class OAuthExchangeError(OAuthError):
    """Token exchange failed."""
    def __init__(self, message: str, provider_error: str | None = None):
        super().__init__(message)
        self.provider_error = provider_error

class OAuthRefreshError(OAuthError):
    """Token refresh failed."""
    pass
```

---

## Technical Requirements

### Framework-Specific

| Requirement | Pattern | Why |
|-------------|---------|-----|
| HTTP Client | `httpx.AsyncClient` | Project standard |
| State Storage | In-memory dict (MVP) | Production: Redis with TTL |
| PKCE | SHA256 + base64url | Notion requirement |
| State TTL | 10 minutes | Security best practice |

### Dependencies

| Dependency | Version | Purpose |
|------------|---------|---------|
| `httpx` | existing | Async HTTP client |
| `pydantic` | existing | Data validation |
| `cryptography` | existing | State token signing |

### Environment Variables

| Variable | Purpose | Required |
|----------|---------|----------|
| `NOTION_CLIENT_ID` | Notion OAuth app ID | Yes (for Notion) |
| `NOTION_CLIENT_SECRET` | Notion OAuth app secret | Yes (for Notion) |
| `SLACK_CLIENT_ID` | Slack OAuth app ID | Yes (for Slack) |
| `SLACK_CLIENT_SECRET` | Slack OAuth app secret | Yes (for Slack) |
| `HUBSPOT_CLIENT_ID` | HubSpot OAuth app ID | Yes (for HubSpot) |
| `HUBSPOT_CLIENT_SECRET` | HubSpot OAuth app secret | Yes (for HubSpot) |
| `OAUTH_REDIRECT_BASE_URL` | Base URL for callbacks | Yes |
| `OAUTH_STATE_TTL_SECONDS` | State token TTL | No (default: 600) |

---

## File Location Rules

| Artifact | Correct Location | Notes |
|----------|------------------|-------|
| Implementation | `deeptrail-control/app/services/oauth_service.py` | Create new |
| Data classes | `deeptrail-control/app/schemas/oauth.py` | Create new |
| Unit tests | `deeptrail-control/tests/services/test_oauth_service.py` | Create new |
| Integration tests | `tests/e2e/` (ROOT) | Cross-service |

---

## Test Cases

| Test Case | Method | Expected | Notes |
|-----------|--------|----------|-------|
| Generate auth URL | `get_authorization_url()` | Valid URL with state | Check all query params |
| Generate auth URL with PKCE | `get_authorization_url()` | URL with code_challenge | Notion only |
| Exchange valid code | `exchange_code_for_tokens()` | Tokens returned | Mock provider response |
| Exchange with invalid state | `exchange_code_for_tokens()` | `OAuthStateError` | State validation |
| Exchange with expired state | `exchange_code_for_tokens()` | `OAuthStateError` | TTL enforcement |
| Refresh tokens | `refresh_tokens()` | New tokens returned | Mock provider response |
| Refresh with revoked token | `refresh_tokens()` | `OAuthRefreshError` | Handle provider error |
| Get unconfigured provider | `get_provider_config()` | `OAuthConfigError` | Missing env vars |
| PKCE pair generation | `_generate_pkce_pair()` | Valid verifier/challenge | RFC 7636 compliant |

---

## Contract Verification Checklist

Before marking implementation complete, verify:

- [ ] `OAuthService` class created with all methods
- [ ] All three providers configured (Notion, Slack, HubSpot)
- [ ] PKCE implemented for Notion
- [ ] State tokens generated and validated
- [ ] State tokens expire after TTL
- [ ] Token exchange makes correct HTTP request
- [ ] Token refresh makes correct HTTP request
- [ ] All error types defined and raised appropriately
- [ ] Environment variables documented and read
- [ ] Unit tests cover all methods
- [ ] Integration with VaultClient for token storage works

---

## Usage Example

```python
# In endpoint handler
oauth_service = get_oauth_service()

# Step 1: Generate authorization URL
auth_request = AuthorizationRequest(
    provider=OAuthProvider.NOTION,
    user_id="user-123",
    requested_scopes=None  # Notion manages scopes
)
auth_response = await oauth_service.get_authorization_url(auth_request)

# Return URL to frontend for redirect
return {"authorization_url": auth_response.authorization_url}

# Step 2: Handle callback (in callback endpoint)
exchange_request = TokenExchangeRequest(
    provider=OAuthProvider.NOTION,
    authorization_code=code,
    state=state,
    code_verifier=session.get("code_verifier")  # From session
)
tokens = await oauth_service.exchange_code_for_tokens(exchange_request)

# Step 3: Store tokens via ConnectedServiceService
await connected_service_service.connect_service(
    user_id=user_id,
    service_id="notion",
    oauth_response=tokens,
    scopes_granted=tokens.scope.split() if tokens.scope else []
)
```

---

## References

- **Design Doc Section:** P1-2: Real OAuth Flow for Service Connection
- **Related Specs:** WS-F2-spec.md (OAuth configuration), WS-F3-spec.md (OAuth endpoints)
- **Upstream Dependencies:** MP1 (P0 complete)
- **Downstream Dependents:** WS-F2, WS-F3, WS-G2/G3/G4 (real API calls)
