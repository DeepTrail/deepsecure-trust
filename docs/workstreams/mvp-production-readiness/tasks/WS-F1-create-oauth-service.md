# Task: WS-F1 Create OAuth Service

> **Status:** `ready`
> **Batch:** P1-B1
> **Worktree:** mvp-prod-control

---

## Metadata

| Field | Value |
|-------|-------|
| **Task ID** | WS-F1 |
| **Workstream** | F (OAuth Flows) |
| **Phase** | P1 (Real Backend Integration) |
| **Dependencies** | MP1 (P0 complete) ✅ |
| **Complexity** | L (3+ hours) |
| **Service** | deeptrail-control |
| **Validates** | Real OAuth flows for Notion, Slack, HubSpot |

---

## Specification

> See full specification: [../specs/WS-F1-spec.md](../specs/WS-F1-spec.md)

### Key Contracts

**Public Methods:**

| Method | Arguments | Returns | Description |
|--------|-----------|---------|-------------|
| `get_authorization_url` | `AuthorizationRequest` | `AuthorizationResponse` | Generate OAuth URL with state/PKCE |
| `exchange_code_for_tokens` | `TokenExchangeRequest` | `OAuthTokenResponse` | Exchange code for tokens |
| `refresh_tokens` | `TokenRefreshRequest` | `OAuthTokenResponse` | Refresh expired tokens |
| `get_provider_config` | `OAuthProvider` | `OAuthConfig` | Get provider configuration |

**Data Classes to Create:**
- `OAuthProvider` (enum) - NOTION, SLACK, HUBSPOT
- `OAuthConfig` - Provider-specific configuration
- `AuthorizationRequest` / `AuthorizationResponse`
- `TokenExchangeRequest` / `OAuthTokenResponse`
- `TokenRefreshRequest`
- `OAuthState` - State token payload

**Provider Configuration:**

| Provider | Auth URL | Token URL | PKCE |
|----------|----------|-----------|------|
| Notion | `api.notion.com/v1/oauth/authorize` | `api.notion.com/v1/oauth/token` | Required |
| Slack | `slack.com/oauth/v2/authorize` | `slack.com/api/oauth.v2.access` | No |
| HubSpot | `app.hubspot.com/oauth/authorize` | `api.hubapi.com/oauth/v1/token` | No |

---

## Pre-Conditions

- [x] MP1 reached (P0 complete, E2E demo verified)
- [x] `deeptrail-control/app/api/v1/endpoints/users.py` has connect endpoint
- [x] `deeptrail-control/app/services/connected_service_service.py` exists
- [x] `deeptrail-control/app/services/vault_client.py` exists

---

## Task Description

### Objective

Create an OAuthService that handles the complete OAuth 2.0 authorization flow for external services (Notion, Slack, HubSpot).

### Background

The current implementation stores OAuth tokens via the connect endpoint, but:
- Users must manually obtain tokens elsewhere
- No authorization URL generation
- No callback handling
- No PKCE support (required by Notion)
- No state validation (CSRF protection)

This service enables:
- Redirect-based OAuth flow (standard web OAuth)
- Secure state tokens to prevent CSRF
- PKCE for Notion's enhanced security
- Token refresh for long-running integrations

### What to Implement

1. **Create data classes** (`app/schemas/oauth.py`):
   ```python
   class OAuthProvider(str, Enum):
       NOTION = "notion"
       SLACK = "slack"
       HUBSPOT = "hubspot"

   @dataclass
   class OAuthConfig:
       provider: OAuthProvider
       client_id: str
       client_secret: str
       authorization_url: str
       token_url: str
       scopes: list[str]
       redirect_uri: str
       uses_pkce: bool = False

   @dataclass
   class AuthorizationRequest:
       provider: OAuthProvider
       user_id: str
       requested_scopes: list[str] | None = None

   @dataclass
   class AuthorizationResponse:
       authorization_url: str
       state: str
       code_verifier: str | None = None

   @dataclass
   class TokenExchangeRequest:
       provider: OAuthProvider
       authorization_code: str
       state: str
       code_verifier: str | None = None

   @dataclass
   class OAuthTokenResponse:
       access_token: str
       token_type: str
       expires_in: int | None
       refresh_token: str | None
       scope: str | None
   ```

2. **Create OAuthService** (`app/services/oauth_service.py`):
   ```python
   class OAuthService:
       def __init__(self, vault_client, connected_service_service):
           self._vault = vault_client
           self._service = connected_service_service
           self._pending_states: dict[str, OAuthState] = {}

       async def get_authorization_url(self, request: AuthorizationRequest) -> AuthorizationResponse:
           # Generate state, PKCE if needed, build URL
           ...

       async def exchange_code_for_tokens(self, request: TokenExchangeRequest) -> OAuthTokenResponse:
           # Validate state, exchange code, return tokens
           ...

       async def refresh_tokens(self, request: TokenRefreshRequest) -> OAuthTokenResponse:
           # Call provider's refresh endpoint
           ...
   ```

3. **Implement PKCE** (for Notion):
   ```python
   def _generate_pkce_pair(self) -> tuple[str, str]:
       code_verifier = secrets.token_urlsafe(32)
       challenge_bytes = hashlib.sha256(code_verifier.encode()).digest()
       code_challenge = base64.urlsafe_b64encode(challenge_bytes).rstrip(b'=').decode()
       return code_verifier, code_challenge
   ```

4. **Implement state management**:
   ```python
   @dataclass
   class OAuthState:
       user_id: str
       provider: str
       nonce: str
       created_at: datetime
       expires_at: datetime
       code_verifier: str | None = None

   async def _store_state(self, state: OAuthState) -> str:
       state_token = secrets.token_urlsafe(32)
       self._pending_states[state_token] = state
       return state_token

   async def _validate_and_consume_state(self, state_token: str) -> OAuthState:
       if state_token not in self._pending_states:
           raise OAuthStateError("Invalid or expired state")
       state = self._pending_states.pop(state_token)
       if datetime.utcnow() > state.expires_at:
           raise OAuthStateError("State token expired")
       return state
   ```

5. **Create error types** (`app/services/oauth_service.py`):
   ```python
   class OAuthError(Exception): pass
   class OAuthConfigError(OAuthError): pass
   class OAuthStateError(OAuthError): pass
   class OAuthExchangeError(OAuthError): pass
   class OAuthRefreshError(OAuthError): pass
   ```

---

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `deeptrail-control/app/schemas/oauth.py` | Create | Data classes for OAuth |
| `deeptrail-control/app/services/oauth_service.py` | Create | OAuth service implementation |
| `deeptrail-control/tests/services/test_oauth_service.py` | Create | Unit tests |

---

## Acceptance Criteria

### Functional Criteria

- [ ] `OAuthService` class created with all public methods
- [ ] `get_authorization_url()` returns valid OAuth URL with state parameter
- [ ] `get_authorization_url()` generates PKCE for Notion
- [ ] `exchange_code_for_tokens()` validates state before exchange
- [ ] `exchange_code_for_tokens()` makes correct HTTP POST to token URL
- [ ] `exchange_code_for_tokens()` includes code_verifier for PKCE flows
- [ ] `refresh_tokens()` makes correct HTTP POST to refresh endpoint
- [ ] All three providers configured (Notion, Slack, HubSpot)
- [ ] State tokens expire after TTL (default 10 minutes)
- [ ] `get_provider_config()` raises `OAuthConfigError` if env vars missing

### Security Criteria

- [ ] State tokens are cryptographically random (32+ bytes)
- [ ] State tokens are single-use (consumed on validation)
- [ ] PKCE code_verifier is 43-128 characters (RFC 7636)
- [ ] Client secrets read from environment variables
- [ ] No secrets in logs or error messages

### Integration Criteria

- [ ] Works with existing `ConnectedServiceService`
- [ ] Works with existing `VaultClient`
- [ ] Httpx used for async HTTP requests
- [ ] Environment variables follow existing patterns

---

## Test Cases

| Test Case | Method | Input | Expected Output |
|-----------|--------|-------|-----------------|
| Generate Notion auth URL | `get_authorization_url()` | `provider=NOTION` | URL with code_challenge |
| Generate Slack auth URL | `get_authorization_url()` | `provider=SLACK` | URL without code_challenge |
| Exchange valid code | `exchange_code_for_tokens()` | Valid state + code | `OAuthTokenResponse` |
| Exchange invalid state | `exchange_code_for_tokens()` | Invalid state | `OAuthStateError` |
| Exchange expired state | `exchange_code_for_tokens()` | Expired state | `OAuthStateError` |
| Refresh valid token | `refresh_tokens()` | Valid refresh_token | New `OAuthTokenResponse` |
| Refresh revoked token | `refresh_tokens()` | Revoked token | `OAuthRefreshError` |
| Get unconfigured provider | `get_provider_config()` | Missing env vars | `OAuthConfigError` |
| PKCE generation | `_generate_pkce_pair()` | N/A | Valid verifier/challenge |
| State generation | `_generate_state()` | User/provider | Secure state token |

---

## Environment Variables

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

## Post-Conditions

After this task is complete:
- [ ] `OAuthService` can generate authorization URLs for all providers
- [ ] `OAuthService` can exchange authorization codes for tokens
- [ ] `OAuthService` can refresh expired tokens
- [ ] PKCE implemented for Notion
- [ ] State management prevents CSRF attacks
- [ ] All unit tests pass

---

## Validation

### Unit Tests
```bash
cd deeptrail-control
pytest tests/services/test_oauth_service.py -v
```

### Manual Verification
```python
# In Python REPL or test
from app.services.oauth_service import OAuthService, get_oauth_service
from app.schemas.oauth import OAuthProvider, AuthorizationRequest

oauth = get_oauth_service()

# Test auth URL generation
request = AuthorizationRequest(
    provider=OAuthProvider.NOTION,
    user_id="user-123"
)
response = await oauth.get_authorization_url(request)
print(f"Auth URL: {response.authorization_url}")
print(f"State: {response.state}")
print(f"Code verifier: {response.code_verifier}")  # Should be set for Notion
assert "code_challenge" in response.authorization_url  # PKCE
assert "state=" in response.authorization_url

# Verify state stored
assert response.state in oauth._pending_states
```

---

## References

- **Specification:** [../specs/WS-F1-spec.md](../specs/WS-F1-spec.md)
- **Design Doc:** `plans/mvp_production_readiness.plan.md` - P1-2
- **OAuth 2.0 PKCE:** [RFC 7636](https://tools.ietf.org/html/rfc7636)
- **Related Files:**
  - `deeptrail-control/app/services/vault_client.py` (token storage)
  - `deeptrail-control/app/services/connected_service_service.py` (connection storage)
  - `deeptrail-control/app/api/v1/endpoints/users.py` (connect endpoint)
- **Downstream Tasks:** WS-F2 (config), WS-F3 (endpoints)

---

## Execution

```bash
# Run in mvp-prod-control worktree:
cd /Users/imaxxs/repositories/mvp-prod-control
/execute-task WS-F1 mvp-production-readiness
```
