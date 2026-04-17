# Task: WS-L2 Create SSO Endpoints

## Metadata

| Field | Value |
|-------|-------|
| **Task ID** | WS-L2 |
| **Task Name** | Create SSO Endpoints |
| **Workstream** | mvp-production-readiness |
| **Phase** | P2 (Production Hardening) |
| **Batch** | P2-B2 |
| **Status** | `ready` |
| **Dependencies** | WS-L1 (IdP Service — ✅ Complete) |
| **Complexity** | M (1-3 hours) |
| **Service** | deeptrail-control |
| **Validates** | Enterprise SSO login via Keycloak; OIDC authorization code flow |

---

## Specification

| Field | Value |
|-------|-------|
| **Spec File** | [WS-L2-spec.md](../specs/WS-L2-spec.md) |
| **Source** | `deepsecure-comprehensive-architecture-consolidated.md` (Layer 0 User ID-Token, User Sessions) |
| **L1 Dependency** | [WS-L1-spec.md](../specs/WS-L1-spec.md) — OIDCProvider protocol, KeycloakProvider, IdPConfig |

### Key Contracts

| Component | Contract |
|-----------|----------|
| **GET `/{idp}/authorize`** | Returns `SSOAuthorizeResponse` with `authorization_url`, `state`, `expires_in` — or 302 redirect |
| **GET `/{idp}/callback`** | Exchanges code via `OIDCProvider`, validates ID token, provisions user, issues DeepSecure JWT → `SSOCallbackResponse` |
| **POST `/logout`** | Invalidates session, returns IdP `logout_url` → `SSOLogoutResponse` |
| **State management** | `PendingSSO` dataclass: `state`, `idp`, `redirect_uri`, `code_verifier`, `created_at`, `expires_in` (5 min) |
| **User provisioning** | `provision_user_from_claims(claims, db)` — JIT user creation/matching from OIDC claims |
| **JWT format** | Same as existing `POST /login` response: `token` field, `sub`, `session_id`, `organization_id`, `exp`, `iat` |
| **Router prefix** | `/auth/sso` in `api.py` → paths become `/api/v1/auth/sso/{idp}/...` |

---

## API Contracts

### Endpoint: SSO Authorize

| Field | Value |
|-------|-------|
| **Method** | `GET` |
| **Path** | `/api/v1/auth/sso/{idp}/authorize` |
| **Auth** | None (public — initiates login) |
| **Purpose** | Generate IdP authorization URL and redirect or return it |

**Path Parameters:** `idp` (string) — IdP identifier (e.g., `keycloak`, `okta`, `entra`)

**Query Parameters:** `redirect_uri` (optional), `response_mode` (optional, default `json`)

**Response (200 — JSON mode):**

```json
{
  "authorization_url": "https://keycloak:8080/realms/deepsecure/protocol/openid-connect/auth?...",
  "state": "random-opaque-state-string",
  "expires_in": 300
}
```

**Response (302 — redirect mode):** Redirects to IdP with `state` and `redirect_uri`.

**Errors:** 400 (unknown IdP), 503 (IdP unavailable)

---

### Endpoint: SSO Callback

| Field | Value |
|-------|-------|
| **Method** | `GET` |
| **Path** | `/api/v1/auth/sso/{idp}/callback` |
| **Auth** | None (public — IdP redirects here) |
| **Purpose** | Exchange authorization code for tokens, provision user, issue DeepSecure JWT |

**Query Parameters (from IdP):** `code`, `state`, `error` (optional), `error_description` (optional)

**Response (200):**

```json
{
  "token": "eyJhbGciOiJIUzI1NiJ9...",
  "user": {
    "user_id": "user-uuid",
    "email": "sarah@acme.com",
    "name": "Sarah Chen",
    "organization_id": "org-acme",
    "is_new_user": false
  },
  "expires_in": 86400,
  "idp": "keycloak"
}
```

**Errors:** 400 (missing code, invalid/expired state, IdP error), 401 (token validation failed), 500 (code exchange failed)

---

### Endpoint: SSO Logout

| Field | Value |
|-------|-------|
| **Method** | `POST` |
| **Path** | `/api/v1/auth/sso/logout` |
| **Auth** | Bearer token (DeepSecure JWT) |
| **Purpose** | Invalidate session and return IdP logout URL |

**Request Body (optional):** `{ "post_logout_redirect_uri": "https://..." }`

**Response (200):**

```json
{
  "logout_url": "https://keycloak:8080/realms/deepsecure/protocol/openid-connect/logout?...",
  "message": "Session invalidated. Redirect to logout_url to complete IdP logout."
}
```

**Errors:** 401 (not authenticated)

---

## Pre-Conditions

- [x] WS-L1 complete (IdP Service — OIDCProvider + KeycloakProvider + IdPConfig)
- [ ] `deeptrail-control` service compiles and starts
- [ ] `create_oidc_provider()` factory function available from L1
- [ ] `app/api/v1/api.py` router wiring exists (for adding `/auth/sso` prefix)
- [ ] Existing `auth.py` JWT issuance pattern available as reference

---

## Task Description

### Objective

Create three SSO endpoints (`authorize`, `callback`, `logout`) that integrate with the WS-L1 OIDCProvider to enable enterprise SSO login via Keycloak (dev) or Okta/Entra (production). After successful OIDC authentication, the control plane issues its own session JWT in the same format as the existing `/login` endpoint.

### Background

User authentication currently relies on a mock login endpoint (`POST /api/v1/auth/login`) that accepts any email/password. The L1 task created the OIDC abstraction layer (OIDCProvider protocol + KeycloakProvider); this task exposes it via HTTP endpoints.

The SSO flow follows the standard OIDC Authorization Code flow:

1. Client calls `/authorize` → gets IdP login URL with opaque `state`
2. User authenticates at IdP → IdP redirects to `/callback` with `code` + `state`
3. Callback exchanges code for tokens, validates ID token, provisions user, issues DeepSecure JWT
4. Client receives JWT in same format as existing login

The P2 validation criteria include testing SSO login via Keycloak, so these endpoints are required for the production readiness milestone.

### What to Implement

#### 1. Pydantic Schemas (`app/schemas/sso.py`)

- `SSOAuthorizeResponse`: `authorization_url`, `state`, `expires_in`
- `SSOUserInfo`: `user_id`, `email`, `name`, `organization_id`, `is_new_user`
- `SSOCallbackResponse`: `token`, `user` (SSOUserInfo), `expires_in`, `idp`
- `SSOLogoutRequest`: optional `post_logout_redirect_uri`
- `SSOLogoutResponse`: `logout_url`, `message`

#### 2. SSO State Management

- `PendingSSO` dataclass: `state`, `idp`, `redirect_uri`, `code_verifier` (PKCE), `created_at`, `expires_in` (default 300s)
- In-memory dict `_pending_sso: Dict[str, PendingSSO]` for MVP
- State is generated, stored, validated, consumed (one-time use), and expired

#### 3. SSO Router (`app/api/v1/endpoints/sso.py`)

**`GET /{idp}/authorize`:**
- Resolve OIDCProvider via `create_oidc_provider()` for the given `idp`
- Generate random `state`, store as `PendingSSO`
- Call `provider.get_authorization_url(state, redirect_uri, scopes)`
- Return `SSOAuthorizeResponse` (JSON) or `RedirectResponse` (302)

**`GET /{idp}/callback`:**
- Validate `state` against `_pending_sso` (exists, not expired, not consumed)
- Handle IdP error parameters (`error`, `error_description`)
- Call `provider.exchange_code(code, redirect_uri)` → `OIDCTokens`
- Call `provider.validate_token(id_token)` → `OIDCClaims`
- Optionally call `provider.get_user_info(access_token)` → `UserInfo`
- Call `provision_user_from_claims(claims, db)` → find/create user
- Issue DeepSecure JWT (same pattern as `auth.py` login: `sub`, `session_id`, `organization_id`, `exp`, `iat`)
- Return `SSOCallbackResponse`

**`POST /logout`:**
- Validate Bearer token
- Invalidate server-side session (if applicable)
- Call `provider.logout_url(id_token_hint, post_logout_redirect_uri)`
- Return `SSOLogoutResponse`

#### 4. User Provisioning

- `provision_user_from_claims(claims: OIDCClaims, db: Session) -> dict`
- Find existing user by email
- Create new user if not found (JIT provisioning)
- Return `user_id`, `email`, `name`, `organization_id`, `is_new_user`

#### 5. Router Wiring

- Add `include_router(sso.router, prefix="/auth/sso", tags=["sso"])` in `api.py`

---

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `deeptrail-control/app/schemas/sso.py` | Create | Pydantic schemas: SSOAuthorizeResponse, SSOCallbackResponse, SSOLogoutRequest/Response, SSOUserInfo |
| `deeptrail-control/app/api/v1/endpoints/sso.py` | Create | SSO router: authorize, callback, logout endpoints + state management + user provisioning |
| `deeptrail-control/app/api/v1/api.py` | Modify | Add `include_router(sso.router, prefix="/auth/sso", tags=["sso"])` |
| `deeptrail-control/tests/api/test_sso.py` | Create | Unit tests for all SSO endpoints |

---

## Acceptance Criteria

### Functional

- [ ] `GET /api/v1/auth/sso/{idp}/authorize` returns `SSOAuthorizeResponse` with valid Keycloak URL
- [ ] `GET /api/v1/auth/sso/{idp}/authorize?response_mode=redirect` returns 302 redirect
- [ ] Unknown `idp` returns 400 with descriptive error
- [ ] `GET /api/v1/auth/sso/{idp}/callback` exchanges code, validates token, provisions user, issues JWT
- [ ] Callback JWT format matches existing login: `token` field, `sub`, `session_id`, `organization_id`, `exp`, `iat`
- [ ] New users are created via JIT provisioning (`is_new_user: true`)
- [ ] Existing users are matched by email (`is_new_user: false`)
- [ ] `POST /api/v1/auth/sso/logout` returns IdP logout URL
- [ ] State is opaque, one-time use, expires after 5 minutes
- [ ] Expired/invalid/consumed state returns 400
- [ ] IdP errors forwarded: `error` + `error_description` → 400

### Security

- [ ] State provides CSRF protection (random, opaque, one-time)
- [ ] State consumed on use (replay returns 400)
- [ ] ID token validated via OIDCProvider (signature, expiry, audience, issuer)
- [ ] No secrets in error responses or logs
- [ ] Logout invalidates server-side session

### Integration

- [ ] SSO router mounted at `/auth/sso` prefix in `api.py`
- [ ] Delegates to L1 OIDCProvider (authorize, exchange_code, validate_token, get_user_info, logout_url)
- [ ] OIDCProvider errors mapped to appropriate HTTP status codes
- [ ] Existing login endpoint still works (no regression)

---

## Test Cases

| Test Case | Method | Endpoint | Expected Status | Notes |
|-----------|--------|----------|-----------------|-------|
| Authorize returns URL | GET | `/api/v1/auth/sso/keycloak/authorize` | 200 | JSON with `authorization_url`, `state` |
| Authorize redirect mode | GET | `/api/v1/auth/sso/keycloak/authorize?response_mode=redirect` | 302 | Redirect to Keycloak |
| Authorize unknown IdP | GET | `/api/v1/auth/sso/invalid/authorize` | 400 | Unknown IdP error |
| Callback success | GET | `/api/v1/auth/sso/keycloak/callback?code=X&state=Y` | 200 | Returns `token`, `user` |
| Callback missing code | GET | `/api/v1/auth/sso/keycloak/callback?state=Y` | 400 | Missing code error |
| Callback invalid state | GET | `/api/v1/auth/sso/keycloak/callback?code=X&state=bad` | 400 | Invalid state error |
| Callback expired state | GET | `/api/v1/auth/sso/keycloak/callback?code=X&state=expired` | 400 | Expired state error |
| Callback state replay | GET | `/api/v1/auth/sso/keycloak/callback?code=X&state=used` | 400 | Consumed state |
| Callback IdP error | GET | `/api/v1/auth/sso/keycloak/callback?error=access_denied` | 400 | IdP error forwarded |
| Callback new user | GET | `/api/v1/auth/sso/keycloak/callback?code=X&state=Y` | 200 | `is_new_user: true` |
| Callback existing user | GET | `/api/v1/auth/sso/keycloak/callback?code=X&state=Y` | 200 | `is_new_user: false` |
| Logout with token | POST | `/api/v1/auth/sso/logout` | 200 | Returns `logout_url` |
| Logout no auth | POST | `/api/v1/auth/sso/logout` | 401 | Not authenticated |

---

## Post-Conditions

After this task is complete:

- [ ] Users can authenticate via Keycloak SSO in development
- [ ] P2 validation criteria #3 (SSO login test) can be executed
- [ ] Enterprise IdP demo (Keycloak broker → Okta/Entra) is enabled
- [ ] Existing login endpoint continues to work (dual auth paths)
- [ ] Production SSO via Okta/Entra achievable by swapping IdP config (no code changes)

---

## Validation

### Unit Tests

```bash
cd /Users/imaxxs/repositories/mvp-prod-control/deeptrail-control

# Run SSO endpoint tests
pytest tests/api/test_sso.py -v

# Run all auth-related tests to check no regression
pytest tests/api/test_auth*.py tests/api/test_sso.py -v
```

### Manual Verification

```bash
# 1. Start services (with Keycloak from L1)
cd /Users/imaxxs/repositories/deepsecure-mvp
docker compose up -d
sleep 20

# 2. Verify Keycloak is healthy
curl -sf http://localhost:8080/health/ready && echo "Keycloak healthy"

# 3. Test SSO authorize (JSON mode)
AUTH_RESP=$(curl -s http://localhost:8000/api/v1/auth/sso/keycloak/authorize)
echo "$AUTH_RESP" | jq '.authorization_url'
# Expected: Keycloak URL with client_id, state, redirect_uri
STATE=$(echo "$AUTH_RESP" | jq -r '.state')
echo "State: $STATE"

# 4. Test SSO authorize (redirect mode)
curl -s -o /dev/null -w "%{http_code}" "http://localhost:8000/api/v1/auth/sso/keycloak/authorize?response_mode=redirect"
# Expected: 302

# 5. Test unknown IdP
curl -s http://localhost:8000/api/v1/auth/sso/invalid/authorize | jq '.detail'
# Expected: "Unknown IdP: invalid..."

# 6. Test callback with invalid state
curl -s "http://localhost:8000/api/v1/auth/sso/keycloak/callback?code=test&state=invalid" | jq '.detail'
# Expected: "Invalid or expired state parameter"

# 7. Manual SSO flow (browser):
#    a. Open authorization_url from step 3 in browser
#    b. Login with Keycloak test user
#    c. Observe redirect to callback with code + state
#    d. Verify JWT is returned

# 8. Verify existing login still works
curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"sarah@acme.com","password":"test_password"}' | jq '.token'
# Expected: Valid JWT (no regression)

# 9. Test logout (with valid token)
USER_TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"sarah@acme.com","password":"test_password"}' | jq -r '.token')

curl -s -X POST http://localhost:8000/api/v1/auth/sso/logout \
  -H "Authorization: Bearer $USER_TOKEN" | jq '.'
# Expected: { "logout_url": "https://...", "message": "..." }
```

---

## References

- **Spec:** [WS-L2-spec.md](../specs/WS-L2-spec.md) — full endpoint contracts, schemas, state management, user provisioning
- **L1 Spec:** [WS-L1-spec.md](../specs/WS-L1-spec.md) — OIDCProvider protocol, KeycloakProvider, `create_oidc_provider()`, `IdPConfig`
- **Architecture:** `deepsecure-comprehensive-architecture-consolidated.md` — Layer 0 User ID-Token, User Sessions
- **Existing Auth Pattern:** `deeptrail-control/app/api/v1/endpoints/auth.py` — JWT issuance, `UserLoginResponse`
- **Existing OAuth Pattern:** `deeptrail-control/app/api/v1/endpoints/oauth.py` — authorize/callback flow, state management
- **Router Wiring:** `deeptrail-control/app/api/v1/api.py` — `include_router` pattern
- **Upstream Dependencies:** WS-L1 (✅ Complete)
- **Downstream Dependents:** P2 validation criteria #3 (SSO login test), enterprise IdP demo

---

## Execution

```bash
# Run in mvp-prod-control worktree:
cd /Users/imaxxs/repositories/mvp-prod-control

# Execute the task
/execute-task WS-L2 mvp-production-readiness

# After completion
/complete-task WS-L2 mvp-production-readiness
```
