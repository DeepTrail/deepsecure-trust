# Task Ticket: WS-F3 Create OAuth Endpoints

> **Status:** ✅ Complete
>
> **Created:** February 17, 2026
> **Assigned Worktree:** mvp-prod-control

---

## Task Overview

| Field | Value |
|-------|-------|
| **Task ID** | WS-F3 |
| **Task Name** | Create OAuth Endpoints |
| **Batch** | P1-B2 |
| **Type** | API Endpoints |
| **Service** | deeptrail-control |
| **Complexity** | M (Medium - 2-4 hours) |
| **Dependencies** | WS-F1 ✅ Complete, WS-F2 (OAuth Config) |
| **Blocks** | WS-G2, WS-G3, WS-G4 (Backend integrations) |

---

## Objective

Create three OAuth API endpoints to enable real OAuth flows for service connections:
1. **Authorize** - Initiate OAuth flow, return/redirect to provider's auth URL
2. **Callback** - Handle OAuth callback, exchange code for tokens
3. **Refresh** - Manually refresh OAuth tokens

---

## Specification Reference

> **Spec:** [WS-F3-spec.md](../specs/WS-F3-spec.md)
>
> All implementation MUST match the specification exactly.

---

## API Contracts

### Endpoint 1: Authorize

| Field | Value |
|-------|-------|
| **Method** | `GET` |
| **Path** | `/api/v1/oauth/{service_id}/authorize` |
| **Auth** | User session token |

**Response (200, JSON mode):**
```json
{
  "authorization_url": "https://api.notion.com/v1/oauth/authorize?...",
  "state": "abc123..."
}
```

### Endpoint 2: Callback

| Field | Value |
|-------|-------|
| **Method** | `GET` |
| **Path** | `/api/v1/oauth/{service_id}/callback` |
| **Auth** | None (state token validates) |

**Response (200):**
```json
{
  "success": true,
  "service_id": "notion",
  "connected": true,
  "scopes_granted": ["read_content", "search"]
}
```

### Endpoint 3: Refresh

| Field | Value |
|-------|-------|
| **Method** | `POST` |
| **Path** | `/api/v1/oauth/{service_id}/refresh` |
| **Auth** | User session token |

**Response (200):**
```json
{
  "refreshed": true,
  "expires_in": 3600
}
```

---

## Implementation Steps

### Step 1: Create OAuth Schemas

**File:** `deeptrail-control/app/schemas/oauth.py`

```python
"""OAuth Pydantic schemas for API request/response."""

from pydantic import BaseModel


class AuthorizeResponse(BaseModel):
    """Response for /oauth/{service_id}/authorize."""
    authorization_url: str
    state: str


class CallbackResponse(BaseModel):
    """Response for /oauth/{service_id}/callback."""
    success: bool
    service_id: str
    connected: bool
    scopes_granted: list[str]


class RefreshResponse(BaseModel):
    """Response for /oauth/{service_id}/refresh."""
    refreshed: bool
    expires_in: int | None


class OAuthError(BaseModel):
    """Standard OAuth error response."""
    error: str
    message: str | None = None
```

### Step 2: Create OAuth Endpoints

**File:** `deeptrail-control/app/api/v1/endpoints/oauth.py`

```python
"""
OAuth API Endpoints

Provides endpoints for OAuth authorization flow:
- GET /api/v1/oauth/{service_id}/authorize - Start OAuth flow
- GET /api/v1/oauth/{service_id}/callback - Handle OAuth callback
- POST /api/v1/oauth/{service_id}/refresh - Refresh OAuth token
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse

from app.api.deps import get_current_user
from app.models.user import User
from app.services.oauth_service import OAuthService, get_oauth_service
from app.services.connected_service_service import ConnectedServiceService, get_connected_service
from app.schemas.oauth import AuthorizeResponse, CallbackResponse, RefreshResponse

router = APIRouter(prefix="/oauth", tags=["oauth"])

SUPPORTED_SERVICES = {"notion", "slack", "hubspot"}


@router.get("/{service_id}/authorize", response_model=AuthorizeResponse)
async def oauth_authorize(
    service_id: str,
    scopes: str | None = Query(None, description="Comma-separated scopes"),
    redirect: bool = Query(False, description="If true, redirect to auth URL"),
    current_user: User = Depends(get_current_user),
    oauth_service: OAuthService = Depends(get_oauth_service),
):
    """
    Initiate OAuth authorization flow.
    
    Returns authorization URL for the specified service.
    If redirect=true, performs 302 redirect instead of returning JSON.
    """
    if service_id not in SUPPORTED_SERVICES:
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_service", "message": f"Unknown service: {service_id}"}
        )
    
    scope_list = scopes.split(",") if scopes else None
    
    auth_url, state = await oauth_service.start_authorization(
        service_id=service_id,
        user_id=str(current_user.id),
        scopes=scope_list
    )
    
    if redirect:
        return RedirectResponse(url=auth_url, status_code=302)
    
    return AuthorizeResponse(authorization_url=auth_url, state=state)


@router.get("/{service_id}/callback", response_model=CallbackResponse)
async def oauth_callback(
    service_id: str,
    code: str = Query(..., description="Authorization code from provider"),
    state: str = Query(..., description="State token for validation"),
    error: str | None = Query(None, description="Error code from provider"),
    error_description: str | None = Query(None, description="Error description"),
    oauth_service: OAuthService = Depends(get_oauth_service),
    connected_service: ConnectedServiceService = Depends(get_connected_service),
):
    """
    Handle OAuth callback from provider.
    
    Validates state, exchanges code for tokens, and stores the connection.
    """
    # Handle OAuth error from provider
    if error:
        raise HTTPException(
            status_code=400,
            detail={"error": "oauth_error", "message": error_description or error}
        )
    
    # Validate state and get user_id
    try:
        user_id = await oauth_service.validate_state(state)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_state", "message": "State token invalid or expired"}
        )
    
    # Exchange code for tokens
    try:
        tokens = await oauth_service.exchange_code(service_id, code)
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail={"error": "token_exchange_failed", "message": str(e)}
        )
    
    # Store tokens via ConnectedServiceService
    await connected_service.connect_service(
        user_id=user_id,
        service_id=service_id,
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        expires_in=tokens.expires_in,
        scopes=tokens.scope
    )
    
    return CallbackResponse(
        success=True,
        service_id=service_id,
        connected=True,
        scopes_granted=tokens.scope.split() if tokens.scope else []
    )


@router.post("/{service_id}/refresh", response_model=RefreshResponse)
async def oauth_refresh(
    service_id: str,
    current_user: User = Depends(get_current_user),
    oauth_service: OAuthService = Depends(get_oauth_service),
    connected_service: ConnectedServiceService = Depends(get_connected_service),
):
    """
    Manually refresh OAuth token for a connected service.
    """
    # Check if service is connected
    connection = await connected_service.get_connection(
        user_id=str(current_user.id),
        service_id=service_id
    )
    
    if not connection:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "message": "Service not connected"}
        )
    
    if not connection.refresh_token:
        raise HTTPException(
            status_code=400,
            detail={"error": "no_refresh_token", "message": "Service does not support refresh"}
        )
    
    # Refresh the token
    try:
        new_tokens = await oauth_service.refresh_token(service_id, connection.refresh_token)
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail={"error": "refresh_failed", "message": str(e)}
        )
    
    # Update stored tokens
    await connected_service.update_tokens(
        user_id=str(current_user.id),
        service_id=service_id,
        access_token=new_tokens.access_token,
        refresh_token=new_tokens.refresh_token or connection.refresh_token,
        expires_in=new_tokens.expires_in
    )
    
    return RefreshResponse(refreshed=True, expires_in=new_tokens.expires_in)
```

### Step 3: Register Router

**File:** `deeptrail-control/app/api/v1/api.py` (modify)

Add import and include:
```python
from app.api.v1.endpoints import oauth

api_router.include_router(oauth.router)
```

### Step 4: Create Tests

**File:** `deeptrail-control/tests/api/test_oauth.py`

```python
"""Tests for OAuth endpoints."""

import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient


class TestOAuthAuthorize:
    """Tests for GET /api/v1/oauth/{service_id}/authorize."""

    @pytest.mark.asyncio
    async def test_authorize_returns_auth_url(self, client: AsyncClient, auth_headers):
        """Test successful authorization URL generation."""
        with patch("app.services.oauth_service.OAuthService.start_authorization") as mock:
            mock.return_value = ("https://notion.com/oauth?...", "state123")
            
            response = await client.get(
                "/api/v1/oauth/notion/authorize",
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "authorization_url" in data
            assert "state" in data

    @pytest.mark.asyncio
    async def test_authorize_redirect_mode(self, client: AsyncClient, auth_headers):
        """Test redirect mode returns 302."""
        with patch("app.services.oauth_service.OAuthService.start_authorization") as mock:
            mock.return_value = ("https://notion.com/oauth?...", "state123")
            
            response = await client.get(
                "/api/v1/oauth/notion/authorize?redirect=true",
                headers=auth_headers,
                follow_redirects=False
            )
            
            assert response.status_code == 302

    @pytest.mark.asyncio
    async def test_authorize_invalid_service(self, client: AsyncClient, auth_headers):
        """Test invalid service returns 400."""
        response = await client.get(
            "/api/v1/oauth/invalid_service/authorize",
            headers=auth_headers
        )
        
        assert response.status_code == 400
        assert response.json()["detail"]["error"] == "invalid_service"

    @pytest.mark.asyncio
    async def test_authorize_unauthorized(self, client: AsyncClient):
        """Test missing auth returns 401."""
        response = await client.get("/api/v1/oauth/notion/authorize")
        assert response.status_code == 401


class TestOAuthCallback:
    """Tests for GET /api/v1/oauth/{service_id}/callback."""

    @pytest.mark.asyncio
    async def test_callback_success(self, client: AsyncClient):
        """Test successful OAuth callback."""
        with patch("app.services.oauth_service.OAuthService.validate_state") as mock_state, \
             patch("app.services.oauth_service.OAuthService.exchange_code") as mock_exchange, \
             patch("app.services.connected_service_service.ConnectedServiceService.connect_service") as mock_connect:
            
            mock_state.return_value = "user-123"
            mock_exchange.return_value = AsyncMock(
                access_token="token",
                refresh_token="refresh",
                expires_in=3600,
                scope="read write"
            )
            
            response = await client.get(
                "/api/v1/oauth/notion/callback?code=abc&state=xyz"
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["connected"] is True

    @pytest.mark.asyncio
    async def test_callback_invalid_state(self, client: AsyncClient):
        """Test invalid state returns 400."""
        with patch("app.services.oauth_service.OAuthService.validate_state") as mock:
            mock.side_effect = ValueError("Invalid state")
            
            response = await client.get(
                "/api/v1/oauth/notion/callback?code=abc&state=bad"
            )
            
            assert response.status_code == 400
            assert response.json()["detail"]["error"] == "invalid_state"

    @pytest.mark.asyncio
    async def test_callback_oauth_error(self, client: AsyncClient):
        """Test OAuth error from provider."""
        response = await client.get(
            "/api/v1/oauth/notion/callback?error=access_denied&error_description=User%20denied"
        )
        
        assert response.status_code == 400
        assert response.json()["detail"]["error"] == "oauth_error"


class TestOAuthRefresh:
    """Tests for POST /api/v1/oauth/{service_id}/refresh."""

    @pytest.mark.asyncio
    async def test_refresh_success(self, client: AsyncClient, auth_headers):
        """Test successful token refresh."""
        with patch("app.services.connected_service_service.ConnectedServiceService.get_connection") as mock_conn, \
             patch("app.services.oauth_service.OAuthService.refresh_token") as mock_refresh, \
             patch("app.services.connected_service_service.ConnectedServiceService.update_tokens"):
            
            mock_conn.return_value = AsyncMock(refresh_token="refresh123")
            mock_refresh.return_value = AsyncMock(
                access_token="new_token",
                refresh_token="new_refresh",
                expires_in=3600
            )
            
            response = await client.post(
                "/api/v1/oauth/notion/refresh",
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["refreshed"] is True

    @pytest.mark.asyncio
    async def test_refresh_not_connected(self, client: AsyncClient, auth_headers):
        """Test refresh when service not connected."""
        with patch("app.services.connected_service_service.ConnectedServiceService.get_connection") as mock:
            mock.return_value = None
            
            response = await client.post(
                "/api/v1/oauth/notion/refresh",
                headers=auth_headers
            )
            
            assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_refresh_unauthorized(self, client: AsyncClient):
        """Test refresh without auth."""
        response = await client.post("/api/v1/oauth/notion/refresh")
        assert response.status_code == 401
```

---

## Validation Commands

```bash
# Navigate to worktree
cd /Users/imaxxs/repositories/mvp-prod-control/deeptrail-control

# Run OAuth endpoint tests
pytest tests/api/test_oauth.py -v

# Verify router registration
grep -r "oauth" app/api/v1/api.py

# Verify endpoints are accessible (requires running server)
# curl http://localhost:8000/api/v1/oauth/notion/authorize -H "Authorization: Bearer $TOKEN"
```

---

## Acceptance Criteria

### Protocol
- [ ] Authorize endpoint returns `authorization_url` and `state`
- [ ] Authorize supports both JSON (default) and redirect modes
- [ ] Callback validates state token before processing
- [ ] Callback handles OAuth error responses from providers
- [ ] Refresh endpoint requires user session

### Security
- [ ] Callback validates state token to prevent CSRF
- [ ] Tokens are stored securely via ConnectedServiceService
- [ ] No tokens exposed in response bodies

### Integration
- [ ] Callback stores tokens via ConnectedServiceService
- [ ] Router registered in api.py
- [ ] All error responses match spec format
- [ ] Tests cover all 3 endpoints × all cases

---

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `deeptrail-control/app/schemas/oauth.py` | Create | Pydantic schemas |
| `deeptrail-control/app/api/v1/endpoints/oauth.py` | Create | OAuth endpoints |
| `deeptrail-control/app/api/v1/api.py` | Modify | Register router |
| `deeptrail-control/tests/api/test_oauth.py` | Create | Endpoint tests |

---

## References

- **Spec:** [WS-F3-spec.md](../specs/WS-F3-spec.md)
- **Upstream:** 
  - WS-F1 (OAuthService) ✅ Complete - [Completion Report](../reports/WS-F1-completion.md)
  - WS-F2 (OAuth Config)
- **Downstream:** WS-G2, WS-G3, WS-G4 (Backend integrations)
- **Provider Docs:**
  - Notion: https://developers.notion.com/docs/authorization
  - Slack: https://api.slack.com/authentication/oauth-v2
  - HubSpot: https://developers.hubspot.com/docs/api/oauth-quickstart-guide

---

## Execution

```bash
# Execute this task
cd /Users/imaxxs/repositories/mvp-prod-control
/execute-task WS-F3 mvp-production-readiness

# Complete this task
/complete-task WS-F3 mvp-production-readiness
```

---

## Progress Updates

| Date | Update |
|------|--------|
| 2026-02-17 | Started task implementation |
| 2026-02-17 | Added Pydantic API response schemas to oauth.py |
| 2026-02-17 | Created oauth.py endpoints with all 3 endpoints |
| 2026-02-17 | Registered router in api.py |
| 2026-02-17 | Created 20 tests covering all acceptance criteria |
| 2026-02-17 | All 20 tests pass, lint passes |
| 2026-02-17 | Ready for completion |
