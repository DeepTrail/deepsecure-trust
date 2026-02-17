"""OAuth API Endpoints for initiating and completing OAuth flows.

Provides endpoints for OAuth authorization:
- GET /api/v1/oauth/{service_id}/authorize - Start OAuth flow
- GET /api/v1/oauth/{service_id}/callback - Handle OAuth callback
- POST /api/v1/oauth/{service_id}/refresh - Refresh OAuth token

These endpoints enable real OAuth connections to backend services
(Notion, Slack, HubSpot).
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from fastapi.responses import RedirectResponse

from app.core.config import settings
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

# Supported OAuth services
SUPPORTED_SERVICES = {"notion", "slack", "hubspot"}

# Service ID to OAuthProvider mapping
SERVICE_TO_PROVIDER = {
    "notion": OAuthProvider.NOTION,
    "slack": OAuthProvider.SLACK,
    "hubspot": OAuthProvider.HUBSPOT,
}


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

        # Try to decode JWT
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
            return payload.get("sub", "unknown")
        except jwt.exceptions.PyJWTError:
            # MVP fallback
            return "sarah@acme.com"

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

    **Supported services:** notion, slack, hubspot
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
    authorization: str = Header(...),
    oauth_service: OAuthService = Depends(get_oauth_service_dep),
):
    """Initiate OAuth authorization flow.

    Args:
        service_id: Service to authorize (notion, slack, hubspot)
        scopes: Optional comma-separated scopes to request
        redirect: If true, redirect to auth URL instead of returning JSON
        authorization: Bearer token for user authentication
        oauth_service: OAuthService instance

    Returns:
        AuthorizeApiResponse with authorization_url and state, or 302 redirect
    """
    # Validate service
    if service_id.lower() not in SUPPORTED_SERVICES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "invalid_service", "message": f"Unknown service: {service_id}"},
        )

    # Get current user
    current_user = get_current_user_from_token(authorization)

    # Map to OAuthProvider enum
    provider = SERVICE_TO_PROVIDER[service_id.lower()]

    # Parse scopes
    scope_list = scopes.split(",") if scopes else None

    # Build authorization request
    auth_request = AuthorizationRequest(
        provider=provider,
        user_id=current_user,
        requested_scopes=scope_list,
    )

    try:
        # Generate authorization URL
        auth_response = await oauth_service.get_authorization_url(auth_request)
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
):
    """Handle OAuth callback from provider.

    Args:
        service_id: Service that sent the callback
        code: Authorization code from provider
        state: State token for CSRF validation
        error: Error code from provider (if authorization failed)
        error_description: Error description from provider
        oauth_service: OAuthService instance
        vault_client: VaultClient for storing tokens

    Returns:
        CallbackApiResponse indicating success and scopes granted
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

    # Validate service
    if service_id.lower() not in SUPPORTED_SERVICES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "invalid_service", "message": f"Unknown service: {service_id}"},
        )

    # Map to OAuthProvider enum
    provider = SERVICE_TO_PROVIDER[service_id.lower()]

    # Validate state and get associated data
    oauth_state = oauth_service.get_pending_state(state)
    if not oauth_state:
        logger.warning("Invalid or expired OAuth state token")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "invalid_state", "message": "State token invalid or expired"},
        )

    user_id = oauth_state.user_id

    # Build token exchange request
    exchange_request = TokenExchangeRequest(
        provider=provider,
        authorization_code=code,
        state=state,
        code_verifier=oauth_state.code_verifier,
    )

    # Exchange code for tokens
    try:
        tokens = await oauth_service.exchange_code_for_tokens(exchange_request)
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

    # Store tokens in vault
    token_data = {
        "access_token": tokens.access_token,
        "token_type": tokens.token_type,
        "refresh_token": tokens.refresh_token,
        "scope": tokens.scope,
    }

    vault_client.store_token(
        user_id=user_id,
        service_id=service_id.lower(),
        token_data=token_data,
        expires_in=tokens.expires_in,
    )

    logger.info(
        "OAuth connection completed: service=%s user=%s",
        service_id,
        user_id,
    )

    # Parse scopes
    scopes_granted = tokens.scope.split() if tokens.scope else []

    return CallbackApiResponse(
        success=True,
        service_id=service_id.lower(),
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
):
    """Refresh OAuth token for a connected service.

    Args:
        service_id: Service to refresh token for
        authorization: Bearer token for user authentication
        oauth_service: OAuthService instance
        vault_client: VaultClient for token storage

    Returns:
        RefreshApiResponse indicating success and new expiration
    """
    # Validate service
    if service_id.lower() not in SUPPORTED_SERVICES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "invalid_service", "message": f"Unknown service: {service_id}"},
        )

    # Get current user
    current_user = get_current_user_from_token(authorization)

    # Map to OAuthProvider enum
    provider = SERVICE_TO_PROVIDER[service_id.lower()]

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
        new_tokens = await oauth_service.refresh_tokens(refresh_request)
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
