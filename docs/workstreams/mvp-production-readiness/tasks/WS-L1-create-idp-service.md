# Task: WS-L1 Create IdP Service (OIDC Abstraction + Keycloak)

## Metadata

| Field | Value |
|-------|-------|
| **Task ID** | WS-L1 |
| **Task Name** | Create IdP Service (OIDC Abstraction + Keycloak) |
| **Workstream** | mvp-production-readiness |
| **Phase** | P2 (Production Hardening) |
| **Batch** | P2-B1 |
| **Status** | `completed` ✅ |
| **Dependencies** | MP3.5 (P1.5 complete — ✅ reached Feb 23, 2026) |
| **Complexity** | L (3+ hours) |
| **Service** | deeptrail-control + docker-compose |
| **Validates** | Token Layers 0-1 (User ID-Token, Agent-ID Token), Enterprise SSO foundation |

---

## Specification

| Field | Value |
|-------|-------|
| **Spec File** | [WS-L1-spec.md](../specs/WS-L1-spec.md) |
| **Source** | `plans/mvp_production_readiness.plan.md` P2-1, `deepsecure-comprehensive-architecture-consolidated.md` Section 6 |
| **Design Decision** | Option C — Keycloak as dev-time IdP, generic OIDC abstraction for production swappability |

### Key Contracts

| Component | Contract |
|-----------|----------|
| **OIDCProvider** | `typing.Protocol` with 6 methods: `get_authorization_url()`, `exchange_code()`, `validate_token()`, `get_user_info()`, `refresh_token()`, `logout_url()` |
| **OIDCTokens** | Dataclass: `id_token`, `access_token`, `refresh_token`, `expires_at`, `token_type` |
| **OIDCClaims** | Dataclass: `sub`, `email`, `email_verified`, `name`, `groups`, `roles`, `issuer`, `audience`, `raw_claims` |
| **UserInfo** | Dataclass: `sub`, `email`, `name`, `groups`, `roles`, `organization_id` |
| **OIDCError** | Exception hierarchy: `OIDCError` → `OIDCTokenExpiredError`, `OIDCTokenInvalidError`, `OIDCProviderUnavailableError` |
| **KeycloakProvider** | Implements `OIDCProvider` using httpx + python-jose for RS256/JWKS token validation |
| **IdPConfig** | Pydantic settings: `IDP_PROVIDER`, `IDP_ISSUER_URL`, `IDP_CLIENT_ID`, `IDP_CLIENT_SECRET`, `IDP_REALM`, `IDP_REDIRECT_URI` |
| **create_oidc_provider()** | Factory function: config → `OIDCProvider` (returns `KeycloakProvider`; Okta/Entra raise `NotImplementedError`) |
| **Keycloak Docker** | `quay.io/keycloak/keycloak:24.0` with realm import, health check, port 8080 |
| **Realm Config** | `deepsecure` realm: clients (`deepsecure-control`, `gateway`), users (`sarah@acme.com`, `admin@acme.com`), groups (`acme-org`), roles (`user`, `admin`) |

---

## API Contracts

> **Note:** This task implements an internal service module (`idp_service.py`) and infrastructure (Keycloak docker-compose), not API endpoints directly.
> See **WS-L2** for the SSO API endpoints (`/sso/{idp}/authorize`, `/callback`, `/logout`) that consume this service.

### Internal Service Interface

| Method | Signature | Returns | Purpose |
|--------|-----------|---------|---------|
| `get_authorization_url()` | `(state: str, redirect_uri: str, scopes: list[str] \| None) → str` | Full IdP authorization URL | Start OIDC Authorization Code flow |
| `exchange_code()` | `(code: str, redirect_uri: str) → OIDCTokens` | Token set (ID, access, refresh) | Exchange auth code for tokens |
| `validate_token()` | `(id_token: str) → OIDCClaims` | Validated claims | Verify ID token signature, issuer, audience, expiry |
| `get_user_info()` | `(access_token: str) → UserInfo` | User profile | Fetch profile from IdP userinfo endpoint |
| `refresh_token()` | `(refresh_token: str) → OIDCTokens` | New token set | Refresh expired access token |
| `logout_url()` | `(id_token_hint: str \| None, post_logout_redirect_uri: str \| None) → str` | Logout URL | Generate IdP logout URL |
| `create_oidc_provider()` | `(config: IdPConfig \| None) → OIDCProvider` | Provider instance | Factory for configured provider |
| `provision_user_from_claims()` | `(claims: OIDCClaims) → dict` | User record dict | Create/update user from OIDC claims |

---

## Pre-Conditions

- [x] MP3.5 reached (P1.5 integration bugs fixed — Feb 23, 2026)
- [ ] PostgreSQL database running (for user provisioning)
- [ ] `deeptrail-control` service compiles and starts
- [ ] Port 8080 available for Keycloak (verify no conflict with existing services)
- [ ] `docker-compose.yml` accessible for modification

---

## Task Description

### Objective

Create a generic OIDC identity provider abstraction with a Keycloak implementation for dev-time use, plus the Keycloak Docker infrastructure. This replaces the hardcoded password login with a standards-compliant OIDC authentication pathway while keeping the OIDC provider swappable (Keycloak dev → Okta/Entra prod).

### Background

The current MVP authenticates users with a hardcoded password check in `UserAuthService`. Token Layers 0 (User ID-Token from Enterprise IdP) and 1 (Agent-ID Token from Enterprise IdP) are not implemented. The architecture specifies a 6-layer token hierarchy where the first two layers come from an external IdP.

**Design Decision (Option C):**
- `idp_service.py` defines a generic `OIDCProvider` protocol
- `KeycloakProvider` is the dev-time implementation (runs in docker-compose)
- Production swaps to `OktaProvider` or `EntraIDProvider` via config (`IDP_PROVIDER=okta`)
- Keycloak is also reused by WS-J6 as the Authorization Server for RFC 8693 token exchange

**Why Keycloak for dev:**
- Fully local (no external IdP tenant needed for `docker compose up`)
- Supports SSO brokering (can federate to upstream Okta/Entra in staging)
- Reused by WS-J6 for token exchange (same instance)
- OIDC-compliant (validates the abstraction works with a real provider)

### What to Implement

#### 1. OIDC Provider Protocol and Data Models (`idp_service.py`)

- Define `OIDCTokens`, `OIDCClaims`, `UserInfo` dataclasses
- Define `OIDCError` exception hierarchy (base + 3 subclasses)
- Define `OIDCProvider` protocol with 6 async methods
- Implement `create_oidc_provider()` factory function
- Implement `provision_user_from_claims()` for user auto-provisioning

#### 2. KeycloakProvider Implementation (`providers/keycloak.py`)

- Implement all 6 `OIDCProvider` methods using `httpx`
- Use `python-jose` with RS256/JWKS for token validation (NOT shared secrets)
- Implement JWKS caching (avoid repeated network calls)
- Derive standard OIDC endpoints from issuer URL:
  - Auth: `{issuer}/protocol/openid-connect/auth`
  - Token: `{issuer}/protocol/openid-connect/token`
  - UserInfo: `{issuer}/protocol/openid-connect/userinfo`
  - JWKS: `{issuer}/protocol/openid-connect/certs`
  - Logout: `{issuer}/protocol/openid-connect/logout`

#### 3. IdP Configuration (`idp_config.py`)

- Create `IdPProviderType` enum: `keycloak`, `okta`, `entra`
- Create `IdPConfig` Pydantic settings model with env var mapping
- Default to Keycloak at `http://localhost:8080/realms/deepsecure`

#### 4. Provider Stubs (`providers/okta.py`, `providers/entra.py`)

- Create placeholder files that raise `NotImplementedError`
- Include docstrings explaining they're for future enterprise use

#### 5. Keycloak Docker Service (`docker-compose.yml`)

- Add `keycloak` service using `quay.io/keycloak/keycloak:24.0`
- Configure `start-dev --import-realm` command
- Map port 8080, add health check, depend on `db`
- Mount `config/keycloak/` for realm import

#### 6. Keycloak Realm Configuration (`config/keycloak/deepsecure-realm.json`)

- Create `deepsecure` realm
- Register `deepsecure-control` client (confidential, Authorization Code + PKCE)
- Register `gateway` client (confidential, Client Credentials + Token Exchange — for WS-J6)
- Create test users: `sarah@acme.com` (password: `test_password`), `admin@acme.com` (password: `admin_password`)
- Create group `acme-org` and roles `user`, `admin`
- Configure token lifetimes: access 5 min, refresh 30 min
- Set valid redirect URIs for dev

#### 7. Dependencies

- Add `python-jose[cryptography]>=3.3.0` to Control Plane requirements
- Add `pydantic-settings>=2.0.0` if not already present (verify first)

---

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `deeptrail-control/app/services/idp_service.py` | Create | `OIDCProvider` protocol, dataclasses, error hierarchy, factory, user provisioning |
| `deeptrail-control/app/services/providers/__init__.py` | Create | Provider package init |
| `deeptrail-control/app/services/providers/keycloak.py` | Create | `KeycloakProvider` implementing `OIDCProvider` |
| `deeptrail-control/app/services/providers/okta.py` | Create | Stub raising `NotImplementedError` |
| `deeptrail-control/app/services/providers/entra.py` | Create | Stub raising `NotImplementedError` |
| `deeptrail-control/app/core/idp_config.py` | Create | `IdPConfig` Pydantic settings, `IdPProviderType` enum |
| `config/keycloak/deepsecure-realm.json` | Create | Keycloak realm import (clients, users, groups, roles) |
| `docker-compose.yml` | Modify | Add `keycloak` service |
| `deeptrail-control/requirements.txt` (or `pyproject.toml`) | Modify | Add `python-jose[cryptography]`, `pydantic-settings` |
| `deeptrail-control/tests/services/test_idp_service.py` | Create | Unit tests for factory, config, provisioning |
| `deeptrail-control/tests/services/providers/__init__.py` | Create | Test package init |
| `deeptrail-control/tests/services/providers/test_keycloak.py` | Create | Unit tests for KeycloakProvider (mock httpx) |

---

## Acceptance Criteria

### Functional

- [ ] `OIDCProvider` protocol defined with all 6 methods in `idp_service.py`
- [ ] `OIDCTokens`, `OIDCClaims`, `UserInfo` dataclasses defined and usable
- [ ] `OIDCError` hierarchy defined: base + `TokenExpired`, `TokenInvalid`, `ProviderUnavailable`
- [ ] `KeycloakProvider` implements all 6 `OIDCProvider` methods
- [ ] `KeycloakProvider.validate_token()` uses JWKS (RS256), not shared secret
- [ ] JWKS caching implemented (only one HTTP fetch per token validation session)
- [ ] `IdPConfig` loads from environment variables with sensible defaults
- [ ] `create_oidc_provider()` factory returns `KeycloakProvider` for `keycloak` config
- [ ] `create_oidc_provider()` raises `NotImplementedError` for `okta` and `entra`
- [ ] `create_oidc_provider()` raises `ValueError` for unknown provider
- [ ] `provision_user_from_claims()` creates/updates user from OIDC claims
- [ ] Keycloak service starts via `docker compose up`
- [ ] Keycloak health check passes at `/health/ready`
- [ ] OIDC discovery endpoint accessible at `/.well-known/openid-configuration`
- [ ] Test user `sarah@acme.com` can authenticate against Keycloak
- [ ] Realm config includes both `deepsecure-control` and `gateway` clients
- [ ] `python-jose[cryptography]` added to dependencies

### Security

- [ ] Token validation checks signature, issuer, audience, and expiration
- [ ] Client secret not logged in plaintext
- [ ] JWKS fetched over HTTPS in production (HTTP allowed for localhost only)
- [ ] Fail-closed: if IdP unavailable, SSO login is blocked (password login remains)
- [ ] No tokens or secrets in error messages returned to client

### Integration

- [ ] Existing `POST /api/v1/auth/login` password flow continues to work (non-breaking)
- [ ] Keycloak doesn't conflict with existing services (port 8080 free)
- [ ] `docker compose up` still starts all services cleanly (including Keycloak)
- [ ] Keycloak `gateway` client prepared for WS-J6 token exchange reuse

---

## Test Cases

| Test Case | Method | Module | Expected | Notes |
|-----------|--------|--------|----------|-------|
| Factory creates KeycloakProvider | `create_oidc_provider(keycloak_config)` | `test_idp_service.py` | Returns `KeycloakProvider` | Default config |
| Factory raises NotImplementedError for Okta | `create_oidc_provider(okta_config)` | `test_idp_service.py` | `NotImplementedError` | Future provider |
| Factory raises ValueError for unknown | `create_oidc_provider(bad_config)` | `test_idp_service.py` | `ValueError` | Invalid provider |
| IdPConfig loads defaults | `IdPConfig()` | `test_idp_service.py` | `provider=keycloak`, correct issuer URL | Env defaults |
| IdPConfig loads from env | `IdPConfig()` with env set | `test_idp_service.py` | Values from env vars | Override |
| OIDCClaims maps fields | `OIDCClaims(sub=..., email=...)` | `test_idp_service.py` | All fields populated | Dataclass |
| Provision new user | `provision_user_from_claims(claims)` | `test_idp_service.py` | `is_new_user=True` | First login |
| Provision existing user | `provision_user_from_claims(existing)` | `test_idp_service.py` | `is_new_user=False` | Return visit |
| Auth URL includes params | `get_authorization_url(state, uri)` | `test_keycloak.py` | URL with `response_type=code`, `client_id`, `state`, `scope` | URL construction |
| Code exchange returns tokens | `exchange_code(code, uri)` | `test_keycloak.py` | `OIDCTokens` with `id_token`, `access_token` | Mock httpx 200 |
| Code exchange handles 400 | `exchange_code(bad_code, uri)` | `test_keycloak.py` | `OIDCError` raised | Mock httpx 400 |
| Token validation extracts claims | `validate_token(valid_jwt)` | `test_keycloak.py` | `OIDCClaims` with `sub`, `email` | Mock JWKS |
| Token validation rejects expired | `validate_token(expired_jwt)` | `test_keycloak.py` | `OIDCTokenInvalidError` | Expired token |
| Token validation rejects bad sig | `validate_token(tampered_jwt)` | `test_keycloak.py` | `OIDCTokenInvalidError` | Bad signature |
| Refresh returns new tokens | `refresh_token(valid_refresh)` | `test_keycloak.py` | New `OIDCTokens` | Mock httpx 200 |
| JWKS cache avoids repeat fetch | Two `validate_token()` calls | `test_keycloak.py` | Only one JWKS HTTP request | Caching |
| Logout URL includes hint | `logout_url(id_token_hint=...)` | `test_keycloak.py` | URL with `id_token_hint` param | URL construction |
| Userinfo returns profile | `get_user_info(access_token)` | `test_keycloak.py` | `UserInfo` with email | Mock httpx 200 |
| JWKS unavailable raises error | `validate_token()` with JWKS down | `test_keycloak.py` | `OIDCProviderUnavailableError` | Network error |

---

## Post-Conditions

After this task is complete:

- [ ] WS-L2 (SSO Endpoints) can be implemented — consumes `OIDCProvider` for `/sso/{idp}/authorize`, `/callback`, `/logout`
- [ ] WS-J6 (Keycloak Token Exchange) can reuse the same Keycloak instance — `gateway` client already registered
- [ ] `docker compose up` starts Keycloak alongside existing services
- [ ] Enterprise SSO pathway is available (Keycloak dev, swappable to Okta/Entra prod)
- [ ] Existing password login (`POST /api/v1/auth/login`) continues working as fallback

---

## Validation

### Unit Tests

```bash
cd /Users/imaxxs/repositories/mvp-prod-control/deeptrail-control

# Run IdP service tests (factory, config, provisioning)
pytest tests/services/test_idp_service.py -v

# Run KeycloakProvider tests (mock httpx)
pytest tests/services/providers/test_keycloak.py -v

# Run all related tests
pytest tests/services/test_idp_service.py tests/services/providers/test_keycloak.py -v
```

### Manual Verification

```bash
# 1. Start full stack with Keycloak
cd /Users/imaxxs/repositories/deepsecure-mvp
docker compose up -d
sleep 30

# 2. Verify Keycloak is healthy
curl -sf http://localhost:8080/health/ready && echo "✅ Keycloak healthy"
# Expected: "✅ Keycloak healthy"

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
# Expected: Token string (not "null")

# 5. Verify userinfo endpoint
curl -s http://localhost:8080/realms/deepsecure/protocol/openid-connect/userinfo \
  -H "Authorization: Bearer $KC_TOKEN" | jq .
# Expected: {"sub": "...", "email": "sarah@acme.com", ...}

# 6. Verify factory creates provider
cd /Users/imaxxs/repositories/mvp-prod-control/deeptrail-control
python -c "
from app.services.idp_service import create_oidc_provider
from app.core.idp_config import IdPConfig

config = IdPConfig()
provider = create_oidc_provider(config)
print(f'Provider: {type(provider).__name__}')
print(f'Issuer: {provider._issuer_url}')
"
# Expected:
# Provider: KeycloakProvider
# Issuer: http://localhost:8080/realms/deepsecure

# 7. Verify existing login still works (non-breaking)
USER_TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"sarah@acme.com","password":"test_password"}' | jq -r '.token')
echo "Login token: ${USER_TOKEN:0:20}..."
# Expected: Token string (not "null") — existing flow unbroken

# 8. Clean up
docker compose down
```

### Infrastructure Verification

```bash
# Verify docker-compose includes Keycloak
cd /Users/imaxxs/repositories/deepsecure-mvp
docker compose config --services | grep keycloak
# Expected: "keycloak"

# Verify realm config file exists
ls config/keycloak/deepsecure-realm.json
# Expected: File exists

# Verify realm has correct clients
cat config/keycloak/deepsecure-realm.json | python -c "
import json, sys
realm = json.load(sys.stdin)
clients = [c['clientId'] for c in realm.get('clients', [])]
print(f'Clients: {clients}')
assert 'deepsecure-control' in clients, 'Missing deepsecure-control client'
assert 'gateway' in clients, 'Missing gateway client'
print('✅ Both clients present')
"
```

---

## References

- **Spec:** [WS-L1-spec.md](../specs/WS-L1-spec.md) — full protocol definitions, KeycloakProvider code, realm config
- **Architecture:** `docs/design/internal/markdowns/deepsecure-comprehensive-architecture-consolidated.md` Section 6 (Token Hierarchy, "WHO MANAGES WHAT")
- **Design Decision:** Option C — [conversation record](cf31f1ad-f36f-44e0-b61a-4aa9fbe7082e) — Keycloak dev-time IdP, OIDC abstraction
- **Plan:** `plans/mvp_production_readiness.plan.md` P2-1
- **Coverage Matrix:** `docs/workstreams/virtual-mcp-server-mvp/MVP_COVERAGE_MATRIX.md` (Token Layers 0-1: 0% → target ~70%)
- **Existing Service Patterns:** `deeptrail-control/app/services/oauth_service.py`, `deeptrail-control/app/services/delegation_service.py`
- **Existing Config Pattern:** `deeptrail-control/app/core/config.py`
- **Upstream Dependencies:** MP3.5 (✅ reached Feb 23, 2026)
- **Downstream Dependents:** WS-L2 (SSO endpoints), WS-J6 (Keycloak token exchange reuses infrastructure)

---

## Execution

```bash
# Run in mvp-prod-control worktree:
cd /Users/imaxxs/repositories/mvp-prod-control

# Execute the task
/execute-task WS-L1 mvp-production-readiness

# After completion
/complete-task WS-L1 mvp-production-readiness
```
