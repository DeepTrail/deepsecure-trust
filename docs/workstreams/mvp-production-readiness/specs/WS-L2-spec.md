# Task Specification: WS-L2 Create SSO Endpoints

> **IMMUTABLE AFTER DESIGN APPROVAL**
>
> This specification defines what implementation MUST match exactly.
> Do not modify without updating the design doc first.
>
> **Source:** `deepsecure-comprehensive-architecture-consolidated.md` (Layer 0 User ID-Token, User Sessions),
> `WS-L1-spec.md` (OIDCProvider protocol, KeycloakProvider)
>
> **Breakdown:** `mvp-production-readiness-breakdown.md` — WS-L2: `/sso/{idp}/authorize`, `/callback`, `/logout` via Keycloak SSO broker

---

## Overview

| Field | Value |
|-------|-------|
| **Task ID** | WS-L2 |
| **Task Name** | Create SSO Endpoints |
| **Type** | API Endpoints |
| **Service** | deeptrail-control |
| **Complexity** | M (1-3 hours) |
| **Dependencies** | WS-L1 (IdP Service — OIDCProvider + KeycloakProvider) |
| **Validates** | Enterprise SSO login via Keycloak; OIDC authorization code flow |
| **Unblocks** | End-to-end SSO demo; P2 validation criteria (SSO login test) |

---

## Problem Statement

### Current State

User authentication is handled by a mock login endpoint (`POST /api/v1/auth/login`) that accepts any email/password combination and issues a DeepSecure JWT. There is no SSO/OIDC integration — users cannot authenticate through an enterprise IdP.

### Target State

Users authenticate via SSO through Keycloak (dev) or Okta/Entra (production). The control plane issues its own session JWT after OIDC validation, maintaining the existing token format.

```
Browser ──► /sso/{idp}/authorize ──► Keycloak login page
                                         │
Keycloak ──► /sso/{idp}/callback?code=X ──► Control Plane
                                              │
                                         exchange_code()
                                         validate_token()
                                         provision_user()
                                              │
                                         ◄── DeepSecure JWT
```

---

## API Contracts

### Endpoint: SSO Authorize

| Field | Value |
|-------|-------|
| **Method** | `GET` |
| **Path** | `/api/v1/auth/sso/{idp}/authorize` |
| **Auth** | None (public — initiates login) |
| **Purpose** | Generate IdP authorization URL and redirect or return it |

**Path Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `idp` | `str` | Yes | IdP identifier (e.g., `keycloak`, `okta`, `entra`) |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `redirect_uri` | `str` | No | Config default | Post-login redirect URI |
| `response_mode` | `str` | No | `json` | `json` returns URL in body; `redirect` returns 302 |

**Response (200 — JSON mode):**

```json
{
  "authorization_url": "https://keycloak:8080/realms/deepsecure/protocol/openid-connect/auth?client_id=...",
  "state": "random-opaque-state-string",
  "expires_in": 300
}
```

**Response (302 — Redirect mode):**

Redirects to IdP authorization URL with `state` and `redirect_uri` embedded.

**Error Responses:**

| Status | Condition | Response |
|--------|-----------|----------|
| 400 | Unknown `idp` identifier | `{"detail": "Unknown IdP: {idp}. Supported: keycloak, okta, entra"}` |
| 503 | IdP unavailable | `{"detail": "IdP service unavailable"}` |

---

### Endpoint: SSO Callback

| Field | Value |
|-------|-------|
| **Method** | `GET` |
| **Path** | `/api/v1/auth/sso/{idp}/callback` |
| **Auth** | None (public — IdP redirects here) |
| **Purpose** | Exchange authorization code for tokens, provision user, issue DeepSecure JWT |

**Path Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `idp` | `str` | Yes | IdP identifier (must match authorize request) |

**Query Parameters (set by IdP):**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `code` | `str` | Yes* | Authorization code from IdP |
| `state` | `str` | Yes | Opaque state for CSRF protection |
| `error` | `str` | No | OAuth error code (if login failed) |
| `error_description` | `str` | No | Human-readable error description |

**Response (200 — Success):**

```json
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
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

**Note:** The `token` field name matches the existing `POST /login` response (`UserLoginResponse.token`).

**Error Responses:**

| Status | Condition | Response |
|--------|-----------|----------|
| 400 | Missing `code` parameter | `{"detail": "Missing authorization code"}` |
| 400 | Invalid or expired `state` | `{"detail": "Invalid or expired state parameter"}` |
| 400 | IdP returned `error` | `{"detail": "IdP error: {error_description}"}` |
| 401 | Token validation failed | `{"detail": "ID token validation failed: {reason}"}` |
| 500 | Code exchange failed | `{"detail": "Failed to exchange authorization code"}` |

---

### Endpoint: SSO Logout

| Field | Value |
|-------|-------|
| **Method** | `POST` |
| **Path** | `/api/v1/auth/sso/logout` |
| **Auth** | Bearer token (DeepSecure JWT) |
| **Purpose** | Invalidate server-side session and return IdP logout URL |

**Request Body (optional):**

```json
{
  "post_logout_redirect_uri": "https://app.example.com/logged-out"
}
```

**Response (200):**

```json
{
  "logout_url": "https://keycloak:8080/realms/deepsecure/protocol/openid-connect/logout?id_token_hint=...",
  "message": "Session invalidated. Redirect to logout_url to complete IdP logout."
}
```

**Error Responses:**

| Status | Condition | Response |
|--------|-----------|----------|
| 401 | Missing or invalid Bearer token | `{"detail": "Not authenticated"}` |

---

## Component Specification

### Pydantic Schemas

```python
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class SSOAuthorizeResponse(BaseModel):
    """Response from SSO authorize endpoint."""
    authorization_url: str
    state: str
    expires_in: int = Field(default=300, description="State validity in seconds")


class SSOUserInfo(BaseModel):
    """User info returned after SSO login."""
    user_id: str
    email: str
    name: Optional[str] = None
    organization_id: Optional[str] = None
    is_new_user: bool = False


class SSOCallbackResponse(BaseModel):
    """Response from SSO callback (login success)."""
    token: str
    user: SSOUserInfo
    expires_in: int
    idp: str


class SSOLogoutRequest(BaseModel):
    """Optional request body for logout."""
    post_logout_redirect_uri: Optional[str] = None


class SSOLogoutResponse(BaseModel):
    """Response from SSO logout."""
    logout_url: Optional[str] = None
    message: str
```

### SSO State Management

```python
from dataclasses import dataclass, field
from datetime import datetime, timezone
import secrets


@dataclass
class PendingSSO:
    """Stored state for an in-flight SSO authorization."""
    state: str
    idp: str
    redirect_uri: str
    code_verifier: Optional[str] = None  # PKCE
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_in: int = 300  # 5 minutes

    @property
    def is_expired(self) -> bool:
        from datetime import timedelta
        return datetime.now(timezone.utc) > self.created_at + timedelta(seconds=self.expires_in)
```

**State storage:** In-memory dict for MVP (`_pending_sso: Dict[str, PendingSSO]`). For production, use Redis or DB-backed storage.

### Router Structure

```python
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse

router = APIRouter()

# Mounted at prefix="/auth/sso" in api.py → paths become /api/v1/auth/sso/...


@router.get("/{idp}/authorize", response_model=SSOAuthorizeResponse)
async def sso_authorize(
    idp: str,
    redirect_uri: Optional[str] = Query(None),
    response_mode: str = Query("json"),
):
    """Initiate SSO login via the specified IdP."""
    ...


@router.get("/{idp}/callback", response_model=SSOCallbackResponse)
async def sso_callback(
    idp: str,
    code: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
    error_description: Optional[str] = Query(None),
):
    """Handle IdP callback after user authentication."""
    ...


@router.post("/logout", response_model=SSOLogoutResponse)
async def sso_logout(
    body: Optional[SSOLogoutRequest] = None,
    # current_user dependency for auth
):
    """Logout: invalidate session and return IdP logout URL."""
    ...
```

### Integration with L1 OIDCProvider

The SSO endpoints delegate to the `OIDCProvider` interface from WS-L1:

| Endpoint | L1 Method Used |
|----------|----------------|
| `/authorize` | `provider.get_authorization_url(state, redirect_uri, scopes)` |
| `/callback` | `provider.exchange_code(code, redirect_uri)` → `provider.validate_token(id_token)` → `provider.get_user_info(access_token)` |
| `/logout` | `provider.logout_url(id_token_hint, post_logout_redirect_uri)` |

### User Provisioning

After successful callback:
1. `validate_token(id_token)` → `OIDCClaims` (sub, email, groups, roles)
2. `provision_user_from_claims(claims)` → find or create user in DB
3. Issue DeepSecure JWT (same format as existing `/login`): `sub`, `session_id`, `organization_id`, `exp`, `iat`

```python
def provision_user_from_claims(claims: OIDCClaims, db: Session) -> dict:
    """Map IdP claims to internal user. Create if new."""
    user = db.query(User).filter(User.email == claims.email).first()
    is_new = user is None
    if is_new:
        user = User(
            email=claims.email,
            name=claims.name or claims.email.split("@")[0],
            organization_id=_derive_org(claims),
            idp_subject=claims.sub,
        )
        db.add(user)
        db.commit()
    return {
        "user_id": str(user.id),
        "email": user.email,
        "name": user.name,
        "organization_id": user.organization_id,
        "is_new_user": is_new,
    }
```

---

## File Location Rules

| Artifact | Correct Location |
|----------|------------------|
| SSO endpoints | `deeptrail-control/app/api/v1/endpoints/sso.py` |
| SSO schemas | `deeptrail-control/app/schemas/sso.py` |
| Router wiring | `deeptrail-control/app/api/v1/api.py` (add `include_router(sso.router, prefix="/auth/sso")`) |
| Unit tests | `deeptrail-control/tests/api/test_sso.py` |

---

## Technical Requirements

### Framework-Specific

| Requirement | Pattern | Why |
|-------------|---------|-----|
| Async endpoints | `async def` | OIDCProvider methods are async |
| State management | In-memory dict (MVP) | Stateless SSO state for dev; Redis for prod |
| JWT issuance | Match existing `auth.py` pattern | `jwt.encode(claims, settings.SECRET_KEY, algorithm="HS256")` |
| Router prefix | `prefix="/auth/sso"` in `api.py` | Paths become `/api/v1/auth/sso/{idp}/...` |

### Dependencies

| Dependency | Version | Purpose |
|------------|---------|---------|
| `fastapi` | existing | API framework |
| `pyjwt` | existing | JWT issuance |
| L1 OIDCProvider | WS-L1 | `create_oidc_provider()`, `OIDCProvider` protocol |

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
| Callback IdP error | GET | `/api/v1/auth/sso/keycloak/callback?error=access_denied` | 400 | IdP error forwarded |
| Callback new user provisioned | GET | `/api/v1/auth/sso/keycloak/callback?code=X&state=Y` | 200 | `is_new_user: true` |
| Callback existing user matched | GET | `/api/v1/auth/sso/keycloak/callback?code=X&state=Y` | 200 | `is_new_user: false` |
| Logout with token | POST | `/api/v1/auth/sso/logout` | 200 | Returns `logout_url` |
| Logout without auth | POST | `/api/v1/auth/sso/logout` | 401 | Not authenticated |
| State consumed on use | GET | `/api/v1/auth/sso/keycloak/callback` (replay) | 400 | State already consumed |

---

## Contract Verification Checklist

- [ ] SSO router mounted at `/auth/sso` prefix in `api.py`
- [ ] `GET /{idp}/authorize` returns `SSOAuthorizeResponse` with valid URL
- [ ] `GET /{idp}/callback` exchanges code, validates token, provisions user, issues JWT
- [ ] `POST /logout` invalidates session and returns IdP logout URL
- [ ] State is generated, stored, validated, and consumed (one-time use)
- [ ] Expired state is rejected
- [ ] Unknown IdP returns 400
- [ ] Token format matches existing login JWT (sub, session_id, org, exp, iat)
- [ ] `provision_user_from_claims` creates new users or matches existing
- [ ] All OIDCProvider errors mapped to appropriate HTTP status codes
- [ ] All unit tests pass

---

## Security Considerations

| Aspect | Status | Notes |
|--------|--------|-------|
| CSRF protection | State parameter | Opaque random state, one-time use, 5-min expiry |
| PKCE | Optional (MVP) | Keycloak confidential client may not require PKCE; add `code_verifier` if configured |
| Token validation | Via OIDCProvider | L1 validates signature, expiry, audience, issuer |
| User provisioning | JIT | Create on first login; update on subsequent |
| State storage | In-memory (MVP) | Not persistent across restarts; use Redis for prod |

---

## References

- **L1 Spec:** [WS-L1-spec.md](./WS-L1-spec.md) — OIDCProvider interface, KeycloakProvider, IdPConfig
- **Architecture:** `deepsecure-comprehensive-architecture-consolidated.md` — Layer 0 User ID-Token, User Sessions
- **Breakdown:** `mvp-production-readiness-breakdown.md` — WS-L2: SSO endpoints
- **Existing Auth Pattern:** `deeptrail-control/app/api/v1/endpoints/auth.py` — JWT issuance, UserLoginResponse
- **Existing OAuth Pattern:** `deeptrail-control/app/api/v1/endpoints/oauth.py` — authorize/callback flow, state management
- **Upstream Dependencies:** WS-L1 (OIDCProvider + KeycloakProvider)
- **Downstream Dependents:** P2 validation (SSO login test), enterprise IdP demo
