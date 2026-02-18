# Task Specification: WS-F3 OAuth Endpoints

> **IMMUTABLE AFTER DESIGN APPROVAL**
>
> This specification defines what implementation MUST match exactly.
> Do not modify without updating the design doc first.
>
> **Source:** BATCH_EXECUTION_PLAN.md - P1-B2

---

## Overview

| Field | Value |
|-------|-------|
| **Task ID** | WS-F3 |
| **Task Name** | Create OAuth Endpoints |
| **Type** | API Endpoints |
| **Service** | deeptrail-control |
| **Dependencies** | WS-F1 (OAuthService), WS-F2 (OAuth Config) |

---

## API Contracts

### Endpoint 1: Authorize

| Field | Value |
|-------|-------|
| **Method** | `GET` |
| **Path** | `/api/v1/oauth/{service_id}/authorize` |
| **Auth** | User session token |
| **Purpose** | Initiate OAuth flow, return authorization URL |

#### Path Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `service_id` | `str` | Yes | Provider identifier (notion, slack, hubspot) |

#### Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `scopes` | `str` | No | Comma-separated scopes to request |
| `redirect` | `bool` | No | If true, 302 redirect; if false, return JSON (default: false) |

#### Response Schema (Success - 200, JSON mode)

```json
{
  "authorization_url": "string - full URL with state/PKCE parameters",
  "state": "string - state token (for client-side verification)"
}
```

#### Response (302, redirect mode)

Redirects to provider's authorization URL with state/PKCE parameters.

#### Error Responses

| Status | Condition | Response Body |
|--------|-----------|---------------|
| 401 | Invalid/missing session | `{"error": "unauthorized"}` |
| 400 | Unknown service_id | `{"error": "invalid_service", "message": "Unknown service: x"}` |

---

### Endpoint 2: Callback

| Field | Value |
|-------|-------|
| **Method** | `GET` |
| **Path** | `/api/v1/oauth/{service_id}/callback` |
| **Auth** | None (state token validates) |
| **Purpose** | Handle OAuth callback, exchange code for tokens |

#### Path Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `service_id` | `str` | Yes | Provider identifier |

#### Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `code` | `str` | Yes | Authorization code from provider |
| `state` | `str` | Yes | State token for validation |
| `error` | `str` | No | Error code if authorization failed |
| `error_description` | `str` | No | Error description |

#### Response Schema (Success - 200)

```json
{
  "success": true,
  "service_id": "string - e.g., 'notion'",
  "connected": true,
  "scopes_granted": ["string - list of granted scopes"]
}
```

#### Error Responses

| Status | Condition | Response Body |
|--------|-----------|---------------|
| 400 | Invalid/expired state | `{"error": "invalid_state", "message": "State token invalid or expired"}` |
| 400 | OAuth error from provider | `{"error": "oauth_error", "message": "[error_description]"}` |
| 502 | Token exchange failed | `{"error": "token_exchange_failed", "message": "..."}` |

---

### Endpoint 3: Refresh

| Field | Value |
|-------|-------|
| **Method** | `POST` |
| **Path** | `/api/v1/oauth/{service_id}/refresh` |
| **Auth** | User session token |
| **Purpose** | Manually refresh OAuth token |

#### Path Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `service_id` | `str` | Yes | Provider identifier |

#### Response Schema (Success - 200)

```json
{
  "refreshed": true,
  "expires_in": "int | null - seconds until new expiration"
}
```

#### Error Responses

| Status | Condition | Response Body |
|--------|-----------|---------------|
| 401 | Invalid session | `{"error": "unauthorized"}` |
| 404 | Service not connected | `{"error": "not_found", "message": "Service not connected"}` |
| 400 | No refresh token | `{"error": "no_refresh_token", "message": "Service does not support refresh"}` |
| 502 | Refresh failed | `{"error": "refresh_failed", "message": "..."}` |

---

## Implementation Notes

### Authorize Flow

```python
@router.get("/oauth/{service_id}/authorize")
async def oauth_authorize(
    service_id: str,
    scopes: str | None = None,
    redirect: bool = False,
    current_user: User = Depends(get_current_user),
    oauth_service: OAuthService = Depends(get_oauth_service),
):
    scope_list = scopes.split(",") if scopes else None

    auth_url, state = await oauth_service.start_authorization(
        service_id=service_id,
        user_id=str(current_user.id),
        scopes=scope_list
    )

    if redirect:
        return RedirectResponse(url=auth_url, status_code=302)

    return {"authorization_url": auth_url, "state": state}
```

### Callback Flow

```python
@router.get("/oauth/{service_id}/callback")
async def oauth_callback(
    service_id: str,
    code: str,
    state: str,
    error: str | None = None,
    error_description: str | None = None,
    oauth_service: OAuthService = Depends(get_oauth_service),
    connected_service: ConnectedServiceService = Depends(get_connected_service),
):
    if error:
        raise HTTPException(400, detail={"error": "oauth_error", "message": error_description or error})

    # Validate state and get user_id
    user_id = await oauth_service.validate_state(state)

    # Exchange code for tokens
    tokens = await oauth_service.exchange_code(service_id, code)

    # Store tokens via ConnectedServiceService
    await connected_service.connect_service(
        user_id=user_id,
        service_id=service_id,
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        expires_in=tokens.expires_in,
        scopes=tokens.scope
    )

    return {
        "success": True,
        "service_id": service_id,
        "connected": True,
        "scopes_granted": tokens.scope.split() if tokens.scope else []
    }
```

---

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `deeptrail-control/app/api/v1/endpoints/oauth.py` | Create | OAuth endpoints |
| `deeptrail-control/app/schemas/oauth.py` | Create | Pydantic models |
| `deeptrail-control/tests/api/test_oauth.py` | Create | Endpoint tests |

---

## Test Endpoint Mapping

### Authorize Endpoint

| Test Case | Method | Endpoint | Expected Status | Notes |
|-----------|--------|----------|-----------------|-------|
| Happy path (JSON) | GET | `/api/v1/oauth/notion/authorize` | 200 | Returns auth_url |
| Happy path (redirect) | GET | `/api/v1/oauth/notion/authorize?redirect=true` | 302 | Redirects |
| With scopes | GET | `/api/v1/oauth/slack/authorize?scopes=chat:write` | 200 | Custom scopes |
| Unauthorized | GET | `/api/v1/oauth/notion/authorize` | 401 | No session |
| Invalid service | GET | `/api/v1/oauth/invalid/authorize` | 400 | Unknown service |

### Callback Endpoint

| Test Case | Method | Endpoint | Expected Status | Notes |
|-----------|--------|----------|-----------------|-------|
| Happy path | GET | `/api/v1/oauth/notion/callback?code=x&state=y` | 200 | Tokens stored |
| Invalid state | GET | `/api/v1/oauth/notion/callback?code=x&state=bad` | 400 | State validation fails |
| OAuth error | GET | `/api/v1/oauth/notion/callback?error=access_denied` | 400 | Provider error |
| Token exchange fail | GET | `/api/v1/oauth/notion/callback?code=bad&state=y` | 502 | Provider rejects code |

### Refresh Endpoint

| Test Case | Method | Endpoint | Expected Status | Notes |
|-----------|--------|----------|-----------------|-------|
| Happy path | POST | `/api/v1/oauth/notion/refresh` | 200 | Token refreshed |
| Not connected | POST | `/api/v1/oauth/notion/refresh` | 404 | No connection |
| No refresh token | POST | `/api/v1/oauth/slack/refresh` | 400 | No refresh_token stored |
| Unauthorized | POST | `/api/v1/oauth/notion/refresh` | 401 | No session |

---

## Contract Verification Checklist

- [ ] Authorize endpoint returns `authorization_url` and `state`
- [ ] Authorize supports both JSON (default) and redirect modes
- [ ] Callback validates state token
- [ ] Callback handles OAuth error responses from providers
- [ ] Callback stores tokens via ConnectedServiceService
- [ ] Refresh endpoint requires user session
- [ ] All error responses match spec format
- [ ] Tests cover all cases for all 3 endpoints

---

## References

- **Design Doc:** `plans/mvp_production_readiness.plan.md`
- **Upstream:** WS-F1 (OAuthService), WS-F2 (OAuth Config)
- **Downstream:** WS-G2, WS-G3, WS-G4 (Backend integrations)
