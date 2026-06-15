"""OAuth API Endpoints for initiating and completing OAuth flows.

Provides endpoints for OAuth authorization:
- GET /api/v1/oauth/{service_id}/authorize - Start OAuth flow
- GET /api/v1/oauth/{service_id}/callback - Handle OAuth callback
- POST /api/v1/oauth/{service_id}/refresh - Refresh OAuth token

These endpoints enable real OAuth connections to backend services
(Notion, Slack, Google, GitHub).
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import settings
from app.models.connected_service import ConnectedService
from app.schemas.oauth import (
    AuthorizationRequest,
    AuthorizeApiResponse,
    CallbackApiResponse,
    OAuthProvider,
    RefreshApiResponse,
    TokenExchangeRequest,
    TokenRefreshRequest,
)
from app.services.oauth_service import (
    OAuthExchangeError,
    OAuthRefreshError,
    OAuthService,
    OAuthStateError,
    get_oauth_service,
)
from app.services.vault_client import VaultClient

logger = logging.getLogger(__name__)

router = APIRouter()

# Service ID to OAuthProvider mapping for well-known providers
SERVICE_TO_PROVIDER = {
    "notion": OAuthProvider.NOTION,
    "slack": OAuthProvider.SLACK,
    "gdrive": OAuthProvider.GOOGLE,
    "gcalendar": OAuthProvider.GOOGLE,
    "gmail": OAuthProvider.GOOGLE,
    "github": OAuthProvider.GITHUB,
}


# =============================================================================
# Dynamic Provider Resolution
# =============================================================================


def resolve_provider(service_id: str, db: Session) -> OAuthProvider:
    """Resolve a service_id to an OAuthProvider.

    1. Check well-known SERVICE_TO_PROVIDER mapping
    2. Query service_registry + service_oauth_config for admin-added services
    3. Raise 400 if not found
    """
    sid = service_id.lower()
    if sid in SERVICE_TO_PROVIDER:
        return SERVICE_TO_PROVIDER[sid]

    from app.models.service_registry import ServiceOAuthConfig, ServiceRegistry

    svc = db.query(ServiceRegistry).filter(ServiceRegistry.service_id == sid).first()
    if svc and svc.backend_type == "rest":
        oauth_cfg = (
            db.query(ServiceOAuthConfig)
            .filter(ServiceOAuthConfig.service_id == sid)
            .first()
        )
        if oauth_cfg:
            return OAuthProvider.CUSTOM

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={"error": "invalid_service", "message": f"Unknown service: {service_id}"},
    )


# =============================================================================
# Dependencies
# =============================================================================


def get_current_user_from_token(
    authorization: str = Header(..., description="Bearer token"),
) -> str:
    """Extract user ID from authorization header.

    MVP: Accepts mock tokens and JWT tokens.
    Production: Should validate JWT properly.
    """
    import jwt

    try:
        token = authorization.replace("Bearer ", "")

        # MVP: Accept mock tokens for testing
        if token.startswith("mock_user_token_"):
            return token.replace("mock_user_token_", "")

        # Decode JWT — expired tokens must fail, not silently fallback
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        return payload.get("sub", "unknown")

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired. Please log in again.",
        )
    except jwt.exceptions.PyJWTError as e:
        logger.warning(f"JWT decode failed in OAuth: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"Failed to extract user from token: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "unauthorized", "message": "Invalid authorization header"},
        )


def get_oauth_service_dep() -> OAuthService:
    """Get OAuthService instance for dependency injection."""
    return get_oauth_service()


# Shared vault instance for MVP
_vault_client: Optional[VaultClient] = None


def get_vault_client() -> VaultClient:
    """Get singleton VaultClient instance."""
    global _vault_client
    if _vault_client is None:
        _vault_client = VaultClient()
    return _vault_client


# =============================================================================
# OAuth Authorize Endpoint
# =============================================================================


@router.get(
    "/{service_id}/authorize",
    response_model=AuthorizeApiResponse,
    summary="Start OAuth authorization flow",
    description="""
    Initiate OAuth authorization for a backend service.

    Returns the authorization URL to redirect the user to the OAuth provider.
    If redirect=true, performs a 302 redirect instead of returning JSON.

    **Supported services:** notion, slack, gdrive, gcalendar, gmail, github
    """,
    responses={
        400: {"description": "Invalid service or configuration error"},
        401: {"description": "Missing or invalid authorization"},
    },
)
async def oauth_authorize(
    service_id: str,
    scopes: Optional[str] = Query(None, description="Comma-separated scopes to request"),
    redirect: bool = Query(False, description="If true, redirect to auth URL"),
    post_connect_redirect: Optional[str] = Query(
        None, description="URL to redirect to after successful OAuth connection"
    ),
    authorization: str = Header(...),
    oauth_service: OAuthService = Depends(get_oauth_service_dep),
    db: Session = Depends(get_db),
):
    """Initiate OAuth authorization flow.

    Args:
        service_id: Service to authorize (notion, slack, gdrive, gcalendar, gmail, github)
        scopes: Optional comma-separated scopes to request
        redirect: If true, redirect to auth URL instead of returning JSON
        post_connect_redirect: URL to redirect to after successful connection
        authorization: Bearer token for user authentication
        oauth_service: OAuthService instance

    Returns:
        AuthorizeApiResponse with authorization_url and state, or 302 redirect
    """
    current_user = get_current_user_from_token(authorization)
    provider = resolve_provider(service_id, db)

    scope_list = scopes.split(",") if scopes else None

    auth_request = AuthorizationRequest(
        provider=provider,
        user_id=current_user,
        requested_scopes=scope_list,
        post_connect_redirect=post_connect_redirect,
    )

    try:
        auth_response = await oauth_service.get_authorization_url(
            auth_request, service_id=service_id.lower(), db=db
        )
    except Exception as e:
        logger.error(f"Failed to generate authorization URL: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "config_error", "message": str(e)},
        )

    logger.info(
        "Generated OAuth authorization URL: service=%s user=%s",
        service_id,
        current_user,
    )

    # Redirect mode
    if redirect:
        return RedirectResponse(url=auth_response.authorization_url, status_code=302)

    return AuthorizeApiResponse(
        authorization_url=auth_response.authorization_url,
        state=auth_response.state,
    )


# =============================================================================
# OAuth Callback Endpoint
# =============================================================================


@router.get(
    "/{service_id}/callback",
    response_model=CallbackApiResponse,
    summary="Handle OAuth callback from provider",
    description="""
    Handle the OAuth callback from the provider after user authorization.

    Validates the state token, exchanges the authorization code for tokens,
    and stores the connection in the vault.

    **Note:** This endpoint does not require user authentication as the
    state token validates the request.
    """,
    responses={
        400: {"description": "Invalid state, OAuth error, or exchange failed"},
        502: {"description": "Token exchange with provider failed"},
    },
)
async def oauth_callback(
    service_id: str,
    code: Optional[str] = Query(None, description="Authorization code from provider"),
    state: Optional[str] = Query(None, description="State token for validation"),
    error: Optional[str] = Query(None, description="Error code from provider"),
    error_description: Optional[str] = Query(None, description="Error description"),
    oauth_service: OAuthService = Depends(get_oauth_service_dep),
    vault_client: VaultClient = Depends(get_vault_client),
    db: Session = Depends(get_db),
):
    """Handle OAuth callback from provider.

    Exchanges the authorization code for tokens, persists them in the vault
    (DB-backed), and creates/updates a ConnectedService row so the gateway
    can retrieve the token via GET /vault/tokens/{service_id}.

    If post_connect_redirect was set during authorize, redirects there after
    storing the token (used by the demo script to detect completion).
    """
    # Handle OAuth error from provider
    if error:
        logger.warning(
            "OAuth error from provider: service=%s error=%s desc=%s",
            service_id,
            error,
            error_description,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "oauth_error", "message": error_description or error},
        )

    # Validate required params (only required when no error)
    if not code or not state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "missing_params", "message": "Missing code or state parameter"},
        )

    sid = service_id.lower()
    provider = resolve_provider(sid, db)

    # Validate state and get associated data
    oauth_state = oauth_service.get_pending_state(state)
    if not oauth_state:
        logger.warning("Invalid or expired OAuth state token")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "invalid_state", "message": "State token invalid or expired"},
        )

    user_id = oauth_state.user_id
    post_redirect = oauth_state.post_connect_redirect

    # Build token exchange request
    exchange_request = TokenExchangeRequest(
        provider=provider,
        authorization_code=code,
        state=state,
        code_verifier=oauth_state.code_verifier,
    )

    # Exchange code for tokens
    try:
        tokens = await oauth_service.exchange_code_for_tokens(
            exchange_request, service_id=sid, db=db
        )
    except OAuthStateError as e:
        logger.warning(f"OAuth state validation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "invalid_state", "message": str(e)},
        )
    except OAuthExchangeError as e:
        logger.error(f"OAuth token exchange failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"error": "token_exchange_failed", "message": str(e)},
        )

    # Clean up old token before storing new one (deduplication on reconnect)
    existing_conn = db.query(ConnectedService).filter(
        ConnectedService.user_id == user_id,
        ConnectedService.service_id == sid,
    ).first()

    if existing_conn and existing_conn.oauth_token_ref:
        old_ref = existing_conn.oauth_token_ref
        vault_client.delete_token(old_ref, db=db)
        try:
            from app.services.token_refresh_scheduler import get_scheduler
            get_scheduler().cancel_refresh(old_ref)
        except Exception:
            pass
        logger.debug("Cleaned up old token on reconnect: ref=%s", old_ref)

    # Store tokens in vault — with DB persistence
    token_data = {
        "access_token": tokens.access_token,
        "token_type": tokens.token_type or "bearer",
        "stored_at": datetime.now(timezone.utc).isoformat(),
    }
    if tokens.refresh_token:
        token_data["refresh_token"] = tokens.refresh_token
    if tokens.scope:
        token_data["scope"] = tokens.scope

    token_ref = vault_client.store_token(
        user_id=user_id,
        service_id=sid,
        token_data=token_data,
        expires_in=tokens.expires_in,
        db=db,
    )

    # Create or update ConnectedService row
    scopes_granted = tokens.scope.split() if tokens.scope else []
    connected_at = datetime.now(timezone.utc)

    if existing_conn:
        existing_conn.oauth_token_ref = token_ref
        existing_conn.scopes_granted = scopes_granted
        existing_conn.disconnected_at = None
        existing_conn.connected_at = connected_at
        db.commit()
        db.refresh(existing_conn)
        logger.info("OAuth reconnected: service=%s user=%s", sid, user_id)
    else:
        connection = ConnectedService(
            id=f"conn-{uuid.uuid4()}",
            user_id=user_id,
            service_id=sid,
            service_name=sid,
            oauth_token_ref=token_ref,
            scopes_granted=scopes_granted,
            connected_at=connected_at,
        )
        db.add(connection)
        db.commit()
        db.refresh(connection)
        logger.info("OAuth connected: service=%s user=%s", sid, user_id)

    # Redirect to post_connect_redirect if set (demo script pattern)
    if post_redirect:
        redirect_params = {
            "service_id": sid,
            "status": "connected",
            "scopes": ",".join(scopes_granted),
        }
        return RedirectResponse(
            url=f"{post_redirect}?{urlencode(redirect_params)}",
            status_code=302,
        )

    return CallbackApiResponse(
        success=True,
        service_id=sid,
        connected=True,
        scopes_granted=scopes_granted,
    )


# =============================================================================
# OAuth Refresh Endpoint
# =============================================================================


@router.post(
    "/{service_id}/refresh",
    response_model=RefreshApiResponse,
    summary="Refresh OAuth token for a connected service",
    description="""
    Manually refresh the OAuth token for a connected service.

    Requires the service to be connected and have a refresh token.
    The new tokens are stored in the vault, replacing the old ones.
    """,
    responses={
        400: {"description": "No refresh token available"},
        401: {"description": "Missing or invalid authorization"},
        404: {"description": "Service not connected"},
        502: {"description": "Token refresh failed"},
    },
)
async def oauth_refresh(
    service_id: str,
    authorization: str = Header(...),
    oauth_service: OAuthService = Depends(get_oauth_service_dep),
    vault_client: VaultClient = Depends(get_vault_client),
    db: Session = Depends(get_db),
):
    """Refresh OAuth token for a connected service."""
    current_user = get_current_user_from_token(authorization)
    provider = resolve_provider(service_id, db)

    # Get existing token from vault
    token_ref = vault_client._generate_ref(current_user, service_id.lower())
    token_data = vault_client.retrieve_token(token_ref, update_usage=False)

    if not token_data:
        logger.warning(
            "Service not connected for refresh: service=%s user=%s",
            service_id,
            current_user,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message": "Service not connected"},
        )

    # Check for refresh token
    refresh_token = token_data.get("refresh_token")
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "no_refresh_token", "message": "Service does not support refresh"},
        )

    # Build refresh request
    refresh_request = TokenRefreshRequest(
        provider=provider,
        refresh_token=refresh_token,
        user_id=current_user,
    )

    # Refresh the token
    try:
        new_tokens = await oauth_service.refresh_tokens(
            refresh_request, service_id=service_id.lower(), db=db
        )
    except OAuthRefreshError as e:
        logger.error(f"OAuth token refresh failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"error": "refresh_failed", "message": str(e)},
        )

    # Update tokens in vault
    vault_client.refresh_token(
        token_ref=token_ref,
        new_access_token=new_tokens.access_token,
        new_expires_in=new_tokens.expires_in,
        new_refresh_token=new_tokens.refresh_token,
    )

    logger.info(
        "OAuth token refreshed: service=%s user=%s",
        service_id,
        current_user,
    )

    return RefreshApiResponse(
        refreshed=True,
        expires_in=new_tokens.expires_in,
    )
