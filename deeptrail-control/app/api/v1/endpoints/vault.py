"""API endpoints for Vault operations (credential issuance, revocation, verification, agent rotation).

Also includes token retrieval endpoints for OAuth tokens used in credential injection.
"""

import logging
import base64
from datetime import datetime, timezone, timedelta
from typing import Optional, Any

from fastapi import APIRouter, Depends, Header, HTTPException, status
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519 as ed25519_crypto
from cryptography.exceptions import InvalidSignature

from app import schemas, crud
from app.api import deps
from app.schemas.credential import SecretStoreRequest, SecretStoreResponse
from app.schemas.agent import AgentRotateRequest  # Import schema for rotation
from app.schemas.vault_token import (
    TokenResponse,
    TokenErrorResponse,
    TokenRefreshRequest,
    TokenRefreshResponse,
)
from app.services.vault_client import VaultClient
from app.services.oauth_service import OAuthService, get_oauth_service, OAuthRefreshError
from app.schemas.oauth import OAuthProvider, TokenRefreshRequest as OAuthTokenRefreshRequest
from app.models.connected_service import ConnectedService

logger = logging.getLogger(__name__)
router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────────
# Dependencies for Token Retrieval
# ─────────────────────────────────────────────────────────────────────────────


def get_vault_client() -> VaultClient:
    """Get singleton VaultClient instance.

    MVP: Uses the singleton VaultClient for in-memory token storage.
    Production: Would use a properly configured vault backend.
    """
    return VaultClient()


# ─────────────────────────────────────────────────────────────────────────────
# OAuth Token Retrieval Endpoint (WS-E2)
# ─────────────────────────────────────────────────────────────────────────────


@router.get(
    "/tokens/{service_id}",
    response_model=TokenResponse,
    responses={
        401: {"model": TokenErrorResponse, "description": "Invalid/missing JWT"},
        403: {"model": TokenErrorResponse, "description": "Service not delegated"},
        404: {"model": TokenErrorResponse, "description": "Service not connected"},
    },
    summary="Get OAuth token for a connected service",
    description="""
    Retrieve an OAuth access token for a user's connected service.

    This endpoint is called by the Gateway during credential injection
    to fetch tokens for backend API calls.

    **Security:**
    - Requires Agent Session JWT with delegated_permissions
    - Service must be in the agent's delegated_permissions array
    - Does NOT return refresh_token (security requirement)

    **Flow:**
    1. Validate agent JWT
    2. Check service_id is in delegated_permissions
    3. Retrieve token from vault
    4. Return access token (exclude refresh_token)
    """,
)
async def get_token_for_service(
    service_id: str,
    agent_claims: deps.AgentClaimsDep,
    db: deps.DbDep,
    vault_client: VaultClient = Depends(get_vault_client),
) -> TokenResponse:
    """Retrieve OAuth access token for a connected service.

    This endpoint enables credential injection by the Gateway.

    Args:
        service_id: Service identifier (e.g., "notion", "slack")
        agent_claims: Validated agent JWT claims from dependency
        vault_client: VaultClient instance for token storage

    Returns:
        TokenResponse with access_token (refresh_token excluded)

    Raises:
        HTTPException 403: If service not in delegated_permissions
        HTTPException 404: If service not connected for user
    """
    # 1. Extract user_id and permissions from agent claims
    user_id = agent_claims.get("user_id")
    delegated_permissions = agent_claims.get("delegated_permissions", [])

    logger.debug(
        "Token retrieval request: service=%s user=%s permissions=%s",
        service_id,
        user_id,
        delegated_permissions,
    )

    # 2. Check if service_id is in delegated_permissions
    # Permissions can be formatted as "service:action" or just "service"
    # e.g., ["notion:read", "notion:write", "slack:read"]
    service_delegated = any(
        perm == service_id or perm.startswith(f"{service_id}:")
        for perm in delegated_permissions
    )

    if not service_delegated:
        logger.warning(
            "Service not delegated: service=%s user=%s delegated=%s",
            service_id,
            user_id,
            delegated_permissions,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "forbidden", "message": "Service not delegated"},
        )

    # 3. Query database for stored token reference
    # BUG FIX: Previously used vault_client._generate_ref() which generates
    # a unique reference each call. Must query ConnectedService for stored ref.
    connection = db.query(ConnectedService).filter(
        ConnectedService.user_id == user_id,
        ConnectedService.service_id == service_id,
        ConnectedService.disconnected_at.is_(None),
    ).first()

    if not connection or not connection.oauth_token_ref:
        logger.warning(
            "Service not connected: service=%s user=%s",
            service_id,
            user_id,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message": "Service not connected"},
        )

    token_ref = connection.oauth_token_ref
    token_data = vault_client.retrieve_token(token_ref, db=db)

    if not token_data:
        logger.warning(
            "Token not found in vault: service=%s user=%s token_ref=%s",
            service_id,
            user_id,
            token_ref,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message": "Service not connected"},
        )

    # 4. Extract token fields (exclude refresh_token for security)
    access_token = token_data.get("access_token")
    if not access_token:
        logger.error(
            "Token data missing access_token: service=%s user=%s",
            service_id,
            user_id,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message": "Service not connected"},
        )

    # 5. Build response (never include refresh_token)
    scope = token_data.get("scope")

    # Convert scope to list for consistency with connect response
    scopes_granted = None
    if scope:
        if isinstance(scope, list):
            scopes_granted = scope
        elif isinstance(scope, str):
            scopes_granted = scope.split()

    # Calculate expires_at from expires_in if present
    expires_at = token_data.get("expires_at")
    if not expires_at and token_data.get("expires_in"):
        # Calculate from stored_at + expires_in, or use now + expires_in
        stored_at = token_data.get("stored_at")
        if stored_at:
            base_time = datetime.fromisoformat(stored_at.replace("Z", "+00:00"))
        else:
            base_time = datetime.now(timezone.utc)
        expires_at = (base_time + timedelta(seconds=token_data["expires_in"])).isoformat()

    logger.info(
        "Token retrieved successfully: service=%s user=%s",
        service_id,
        user_id,
    )

    return TokenResponse(
        service_id=service_id,
        access_token=access_token,
        token_type=token_data.get("token_type", "bearer"),
        scopes_granted=scopes_granted,
        expires_at=expires_at,
    )


# ─────────────────────────────────────────────────────────────────────────────
# OAuth Token Refresh Endpoint (WS-E3)
# ─────────────────────────────────────────────────────────────────────────────


# Map service_id to OAuth provider
SERVICE_TO_PROVIDER = {
    "notion": OAuthProvider.NOTION,
    "slack": OAuthProvider.SLACK,
    "gdrive": OAuthProvider.GOOGLE,
    "gcalendar": OAuthProvider.GOOGLE,
    "gmail": OAuthProvider.GOOGLE,
}


def get_oauth_service_dep() -> OAuthService:
    """Get OAuthService instance for dependency injection."""
    return get_oauth_service()


@router.post(
    "/tokens/{service_id}/refresh",
    response_model=TokenRefreshResponse,
    responses={
        401: {"model": TokenErrorResponse, "description": "Invalid internal token"},
        400: {"model": TokenErrorResponse, "description": "No refresh token available"},
        404: {"model": TokenErrorResponse, "description": "Service not connected"},
        502: {"model": TokenErrorResponse, "description": "OAuth provider error"},
    },
    summary="Refresh OAuth token for a connected service",
    description="""
    Refresh an OAuth access token for a user's connected service.

    This endpoint is called by the Gateway when it detects an expired or
    expiring token during credential injection.

    **Authentication:**
    - Uses internal API token (NOT agent JWT)
    - Requires X-User-ID header to identify the user

    **Behavior:**
    - If `force=false` and token is not expired, returns existing token
    - If `force=true`, always attempts to refresh
    - Calls OAuth provider to get new access token
    - Updates vault with new token data

    **Security:**
    - Does NOT return refresh_token (security requirement)
    - Internal endpoint (gateway-to-control only)
    """,
)
async def refresh_token(
    service_id: str,
    request: TokenRefreshRequest,
    db: deps.DbDep,
    x_user_id: str = Header(..., alias="X-User-ID"),
    internal_token: str = Depends(deps.verify_internal_token),
    vault_client: VaultClient = Depends(get_vault_client),
    oauth_service: OAuthService = Depends(get_oauth_service_dep),
) -> TokenRefreshResponse:
    """Refresh OAuth access token for a connected service.

    This endpoint enables the Gateway to refresh expired tokens without
    requiring agent re-authentication.

    Args:
        service_id: Service identifier (e.g., "notion", "slack")
        request: Refresh request with optional force flag
        x_user_id: User ID from X-User-ID header
        internal_token: Validated internal API token
        vault_client: VaultClient instance for token storage
        oauth_service: OAuthService instance for OAuth operations

    Returns:
        TokenRefreshResponse with access_token and refreshed flag

    Raises:
        HTTPException 401: If internal token is invalid
        HTTPException 400: If service has no refresh token
        HTTPException 404: If service not connected for user
        HTTPException 502: If OAuth provider refresh fails
    """
    logger.debug(
        "Token refresh request: service=%s user=%s force=%s",
        service_id,
        x_user_id,
        request.force,
    )

    # 1. Query database for stored token reference
    # BUG FIX: Previously used vault_client._generate_ref() which generates
    # a unique reference each call. Must query ConnectedService for stored ref.
    connection = db.query(ConnectedService).filter(
        ConnectedService.user_id == x_user_id,
        ConnectedService.service_id == service_id,
        ConnectedService.disconnected_at.is_(None),
    ).first()

    if not connection or not connection.oauth_token_ref:
        logger.warning(
            "Service not connected for refresh: service=%s user=%s",
            service_id,
            x_user_id,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message": "Service not connected"},
        )

    token_ref = connection.oauth_token_ref
    token_data = vault_client.retrieve_token(token_ref, update_usage=False, db=db)

    if not token_data:
        logger.warning(
            "Token not found in vault for refresh: service=%s user=%s token_ref=%s",
            service_id,
            x_user_id,
            token_ref,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message": "Service not connected"},
        )

    access_token = token_data.get("access_token")
    if not access_token:
        logger.error(
            "Token data missing access_token: service=%s user=%s",
            service_id,
            x_user_id,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message": "Service not connected"},
        )

    # 2. Check if refresh token exists
    refresh_token_value = token_data.get("refresh_token")
    if not refresh_token_value:
        logger.warning(
            "No refresh token for service: service=%s user=%s",
            service_id,
            x_user_id,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "no_refresh_token", "message": "Service does not support refresh"},
        )

    # 3. Check if refresh needed (unless force=True)
    if not request.force:
        is_expired = vault_client.is_token_expired(token_ref)
        if not is_expired:
            # Get remaining time from metadata
            metadata = token_data.get("metadata", {})
            expires_at_str = metadata.get("expires_at")
            expires_in = None
            if expires_at_str:
                from datetime import datetime, timezone
                expires_at = datetime.fromisoformat(expires_at_str)
                now = datetime.now(timezone.utc)
                expires_in = max(0, int((expires_at - now).total_seconds()))

            logger.info(
                "Token still valid, skipping refresh: service=%s user=%s",
                service_id,
                x_user_id,
            )
            return TokenRefreshResponse(
                access_token=access_token,
                token_type=token_data.get("token_type", "bearer"),
                expires_in=expires_in,
                refreshed=False,
                message="Token still valid",
            )

    # 4. Map service_id to OAuth provider
    provider = SERVICE_TO_PROVIDER.get(service_id.lower())
    if not provider:
        logger.warning(
            "Unknown service for refresh: service=%s user=%s",
            service_id,
            x_user_id,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "unsupported_service", "message": f"Service '{service_id}' not supported for OAuth refresh"},
        )

    # 5. Call OAuth provider to refresh
    import time as _time

    _refresh_start = _time.monotonic()
    try:
        oauth_request = OAuthTokenRefreshRequest(
            provider=provider,
            refresh_token=refresh_token_value,
            user_id=x_user_id,
        )
        new_tokens = await oauth_service.refresh_tokens(oauth_request)
    except OAuthRefreshError as e:
        _latency = (_time.monotonic() - _refresh_start) * 1000
        logger.error(
            "OAuth refresh failed: service=%s user=%s error=%s",
            service_id,
            x_user_id,
            str(e),
        )
        _append_refresh_log(db, token_ref, "failure", error=str(e), latency_ms=_latency)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"error": "provider_error", "message": f"Failed to refresh: {str(e)}"},
        )
    except Exception as e:
        _latency = (_time.monotonic() - _refresh_start) * 1000
        logger.error(
            "Unexpected error during OAuth refresh: service=%s user=%s error=%s",
            service_id,
            x_user_id,
            str(e),
            exc_info=True,
        )
        _append_refresh_log(db, token_ref, "failure", error=str(e), latency_ms=_latency)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"error": "provider_error", "message": f"Failed to refresh: {str(e)}"},
        )

    _refresh_latency_ms = (_time.monotonic() - _refresh_start) * 1000

    # 6. Update vault with new tokens
    success = vault_client.refresh_token(
        token_ref=token_ref,
        new_access_token=new_tokens.access_token,
        new_expires_in=new_tokens.expires_in,
        new_refresh_token=new_tokens.refresh_token,
        db=db,
        latency_ms=_refresh_latency_ms,
    )

    if not success:
        logger.error(
            "Failed to update vault with refreshed token: service=%s user=%s",
            service_id,
            x_user_id,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"error": "vault_error", "message": "Failed to store refreshed token"},
        )

    logger.info(
        "Token refreshed successfully: service=%s user=%s",
        service_id,
        x_user_id,
    )

    return TokenRefreshResponse(
        access_token=new_tokens.access_token,
        token_type=new_tokens.token_type or "bearer",
        expires_in=new_tokens.expires_in,
        refreshed=True,
        message="Token refreshed",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Internal Scheduled Refresh Endpoint (Cloud Tasks / EventBridge target)
# ─────────────────────────────────────────────────────────────────────────────


from pydantic import BaseModel


class ScheduledRefreshRequest(BaseModel):
    """Payload sent by Cloud Tasks / EventBridge when a scheduled refresh fires."""
    token_ref: str
    service_id: str
    user_id: str


class ScheduledRefreshResponse(BaseModel):
    refreshed: bool
    message: str


@router.post(
    "/internal/tokens/refresh-due",
    response_model=ScheduledRefreshResponse,
    responses={
        401: {"description": "Invalid internal token"},
    },
    summary="Trigger a scheduled token refresh (internal)",
    description="""
    Called by Cloud Tasks / EventBridge at the scheduled time to refresh
    an OAuth token proactively. Delegates to the existing refresh logic.
    
    Idempotent: if the token is not expired, returns refreshed=false.
    If the token was deleted, returns refreshed=false with a message.
    """,
)
async def scheduled_refresh(
    request: ScheduledRefreshRequest,
    db: deps.DbDep,
    internal_token: str = Depends(deps.verify_internal_token),
    vault_client: VaultClient = Depends(get_vault_client),
    oauth_service: OAuthService = Depends(get_oauth_service_dep),
) -> ScheduledRefreshResponse:
    """Handle a scheduled token refresh triggered by the scheduler backend."""
    logger.info(
        "Scheduled refresh triggered: service=%s user=%s token_ref=%s",
        request.service_id,
        request.user_id,
        request.token_ref[:30],
    )

    # Check if token still exists
    connection = db.query(ConnectedService).filter(
        ConnectedService.user_id == request.user_id,
        ConnectedService.service_id == request.service_id,
        ConnectedService.disconnected_at.is_(None),
    ).first()

    if not connection or not connection.oauth_token_ref:
        return ScheduledRefreshResponse(
            refreshed=False,
            message="Service not connected (may have been disconnected)",
        )

    if connection.oauth_token_ref != request.token_ref:
        return ScheduledRefreshResponse(
            refreshed=False,
            message="Token ref mismatch (token was replaced by reconnect)",
        )

    # Retrieve token data
    try:
        token_data = vault_client.retrieve_token(
            request.token_ref, update_usage=False, db=db
        )
    except Exception:
        return ScheduledRefreshResponse(
            refreshed=False, message="Token not found in vault"
        )

    if not token_data:
        return ScheduledRefreshResponse(
            refreshed=False, message="Token not found in vault"
        )

    refresh_token_value = token_data.get("refresh_token")
    if not refresh_token_value:
        return ScheduledRefreshResponse(
            refreshed=False, message="No refresh token available"
        )

    # Map service to OAuth provider
    provider = SERVICE_TO_PROVIDER.get(request.service_id.lower())
    if not provider:
        return ScheduledRefreshResponse(
            refreshed=False, message=f"Unsupported service: {request.service_id}"
        )

    # Perform the refresh
    import time as _time

    _sched_start = _time.monotonic()
    try:
        oauth_request = OAuthTokenRefreshRequest(
            provider=provider,
            refresh_token=refresh_token_value,
            user_id=request.user_id,
        )
        new_tokens = await oauth_service.refresh_tokens(oauth_request)
    except Exception as e:
        _latency = (_time.monotonic() - _sched_start) * 1000
        logger.error(
            "Scheduled refresh failed: service=%s user=%s error=%s",
            request.service_id,
            request.user_id,
            str(e),
        )
        _append_refresh_log(db, request.token_ref, "failure", error=str(e), latency_ms=_latency)
        return ScheduledRefreshResponse(
            refreshed=False, message=f"Provider refresh failed: {type(e).__name__}"
        )

    _sched_latency_ms = (_time.monotonic() - _sched_start) * 1000

    # Update vault (this also re-schedules the next refresh via hook)
    success = vault_client.refresh_token(
        token_ref=request.token_ref,
        new_access_token=new_tokens.access_token,
        new_expires_in=new_tokens.expires_in,
        new_refresh_token=new_tokens.refresh_token,
        db=db,
        latency_ms=_sched_latency_ms,
    )

    if not success:
        return ScheduledRefreshResponse(
            refreshed=False, message="Failed to update vault with refreshed token"
        )

    logger.info(
        "Scheduled refresh succeeded: service=%s user=%s",
        request.service_id,
        request.user_id,
    )
    return ScheduledRefreshResponse(refreshed=True, message="Token refreshed")


@router.get("/secrets", status_code=status.HTTP_200_OK)
def list_secrets(
    db: deps.DbDep,
    _: Any = deps.FlexibleAuthDep
):
    """
    Lists all secrets in the vault (metadata only, no values).
    Returns secret names, created timestamps, and metadata labels.
    Share values are never exposed.
    """
    logger.info("Listing all secrets in vault")
    try:
        secrets = crud.secret.list_secrets(db=db)
        return {
            "secrets": [
                {
                    "name": s.name,
                    "created_at": s.created_at.isoformat() if s.created_at else None,
                    "metadata": s.secret_metadata or {}
                }
                for s in secrets
            ],
            "count": len(secrets)
        }
    except Exception as e:
        logger.error(f"Failed to list secrets: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not list secrets")


@router.post("/store", response_model=SecretStoreResponse, status_code=status.HTTP_201_CREATED)
def store_secret(
    secret_in: SecretStoreRequest,
    db: deps.DbDep,
    _: Any = deps.FlexibleAuthDep
):
    """
    Store or update a secret in the vault.
    This is a simple key-value store for demonstration and testing.
    In a real-world scenario, this would involve encryption and more robust access control.
    """
    logger.info(f"Storing secret with name: {secret_in.name}")
    try:
        crud.secret.create_secret(db=db, obj_in=secret_in)
        return {"name": secret_in.name, "message": "Secret stored successfully"}
    except Exception as e:
        logger.error(f"Failed to store secret {secret_in.name}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not store secret")

@router.get("/secrets/{name}", status_code=status.HTTP_200_OK)
def get_secret_direct(
    name: str,
    db: deps.DbDep,
    _: Any = deps.FlexibleAuthDep
):
    """
    Retrieve a secret directly from the vault by name.
    This is for administrative/CLI use and bypasses the ephemeral credential system.
    For programmatic agent access, use the credential issuance flow instead.
    """
    logger.info(f"Retrieving secret with name: {name}")
    try:
        secret_obj = crud.secret.get_secret_by_name(db=db, name=name)
        if not secret_obj:
            logger.warning(f"Secret '{name}' not found")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Secret '{name}' not found")
        
        return {
            "name": secret_obj.name,
            "metadata": secret_obj.secret_metadata or {},
            "created_at": secret_obj.created_at.isoformat() if secret_obj.created_at else None
        }
    except HTTPException:
        raise  # Re-raise HTTP exceptions as-is
    except Exception as e:
        logger.error(f"Failed to retrieve secret {name}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not retrieve secret")


@router.get("/secrets/{name}/value", status_code=status.HTTP_200_OK)
def get_secret_with_value(
    name: str,
    db: deps.DbDep,
    _: Any = deps.FlexibleAuthDep
):
    """
    Retrieve a secret with its reassembled value.
    
    This endpoint fetches share_1 from the local database and share_2 from the gateway,
    then reassembles the original secret using Shamir's Secret Sharing algorithm.
    
    This is for administrative/CLI use and requires API key authentication.
    The reassembled secret only exists briefly in memory during this request.
    """
    import json
    import httpx
    from sslib import shamir
    from app.core.config import settings
    
    logger.info(f"Retrieving secret with value for: {name}")
    try:
        # 1. Get share_1 from the local database
        secret_obj = crud.secret.get_secret_by_name(db=db, name=name)
        if not secret_obj:
            logger.warning(f"Secret '{name}' not found")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Secret '{name}' not found")
        
        share_1_str = secret_obj.share_1
        
        # 2. Fetch share_2 from the gateway
        try:
            gateway_url = f"{settings.GATEWAY_URL}/internal/shares/{name}"
            headers = {"X-Internal-API-Token": settings.GATEWAY_INTERNAL_API_TOKEN}
            with httpx.Client() as client:
                response = client.get(gateway_url, headers=headers)
                if response.status_code == 404:
                    logger.warning(f"Share_2 for '{name}' not found in gateway (may have expired)")
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, 
                                      detail=f"Secret share not found in gateway (may have expired)")
                response.raise_for_status()
                gateway_data = response.json()
                # Gateway returns {"secret_name": ..., "share_2": {"share_value": [...], "prime_mod": ..., ...}}
                share_2_container = gateway_data.get("share_2", {})
                # Extract the actual share value from the container
                if isinstance(share_2_container, dict):
                    share_2_str = share_2_container.get("share_value")
                    gateway_prime_mod_hex = share_2_container.get("prime_mod")
                else:
                    share_2_str = share_2_container
                    gateway_prime_mod_hex = None
        except httpx.RequestError as e:
            logger.error(f"Could not connect to gateway for share_2: {e}")
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY,
                              detail="Could not retrieve secret share from gateway")
        
        # 3. Parse shares from JSON
        try:
            share_1 = json.loads(share_1_str) if isinstance(share_1_str, str) else share_1_str
            share_2 = json.loads(share_2_str) if isinstance(share_2_str, str) else share_2_str
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse shares: {e}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                              detail="Failed to parse secret shares")
        
        # 4. Reassemble the secret using Shamir's algorithm
        try:
            # Convert hex strings back to bytes
            share_1_bytes = (share_1[0], bytes.fromhex(share_1[1]))
            share_2_bytes = (share_2[0], bytes.fromhex(share_2[1]))
            
            # Get prime_mod from secret_metadata (stored during split) or gateway response
            prime_mod_hex = None
            if secret_obj.secret_metadata:
                prime_mod_hex = secret_obj.secret_metadata.get('_prime_mod')
            if not prime_mod_hex and gateway_prime_mod_hex:
                prime_mod_hex = gateway_prime_mod_hex
            
            if prime_mod_hex:
                prime_mod = bytes.fromhex(prime_mod_hex)
            else:
                # Fallback: estimate prime_mod based on share length (may not work)
                share_len = len(share_1_bytes[1])
                prime_mod = b'\x07' + b'\xff' * (share_len - 1)
                logger.warning(f"Using estimated prime_mod for secret '{name}' - consider re-storing")
            
            # Reconstruct the data structure expected by recover_secret
            recovery_data = {
                'required_shares': 2,
                'prime_mod': prime_mod,
                'shares': [share_1_bytes, share_2_bytes]
            }
            
            # Reassemble the secret
            recovered_secret = shamir.recover_secret(recovery_data)
            secret_value = recovered_secret.decode('utf-8')
            
            logger.info(f"Successfully reassembled secret '{name}'")
        except Exception as e:
            logger.error(f"Failed to reassemble secret '{name}': {e}", exc_info=True)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                              detail="Failed to reassemble secret")
        
        return {
            "name": secret_obj.name,
            "value": secret_value,
            "metadata": secret_obj.secret_metadata or {},
            "created_at": secret_obj.created_at.isoformat() if secret_obj.created_at else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve secret with value {name}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
                          detail="Could not retrieve secret")


@router.delete("/secrets/{name}", status_code=status.HTTP_200_OK)
def delete_secret(
    name: str,
    db: deps.DbDep,
    _: Any = deps.FlexibleAuthDep
):
    """
    Delete a secret from the vault by name.
    This also deletes the corresponding share from the gateway.
    """
    import httpx
    from app.core.config import settings
    
    logger.info(f"Deleting secret with name: {name}")
    try:
        # First, check if the secret exists
        secret_obj = crud.secret.get_secret_by_name(db=db, name=name)
        if not secret_obj:
            logger.warning(f"Secret '{name}' not found for deletion")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Secret '{name}' not found")
        
        # Delete share from gateway (best effort - gateway might already have expired it)
        try:
            gateway_url = f"{settings.GATEWAY_URL}/internal/shares/{name}"
            headers = {"X-Internal-API-Token": settings.GATEWAY_INTERNAL_API_TOKEN}
            with httpx.Client() as client:
                response = client.delete(gateway_url, headers=headers)
                if response.status_code == 404:
                    logger.info(f"Share for '{name}' not found in gateway (may have expired)")
                else:
                    response.raise_for_status()
                    logger.info(f"Successfully deleted share for '{name}' from gateway")
        except httpx.RequestError as e:
            logger.warning(f"Could not delete share from gateway for '{name}': {e}")
            # Continue with local deletion even if gateway fails
        
        # Delete from local database
        deleted = crud.secret.delete_secret(db=db, name=name)
        if deleted:
            logger.info(f"Successfully deleted secret '{name}' from control plane")
            return {"name": name, "message": "Secret deleted successfully"}
        else:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete secret")
            
    except HTTPException:
        raise  # Re-raise HTTP exceptions as-is
    except Exception as e:
        logger.error(f"Failed to delete secret {name}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not delete secret")

@router.post("/credentials", response_model=schemas.credential.CredentialIssueResponse, status_code=status.HTTP_201_CREATED)
def issue_credential(
    credential_in: schemas.credential.CredentialIssueRequest,
    db: deps.DbDep,
    _: Any = deps.FlexibleAuthDep
):
    # logger.info(f"[VAULT_EP_DEBUG] Received credential_in.origin_context: {credential_in.origin_context}")
    logger.info(f"Attempting to issue credential for agent: {credential_in.agent_id}, scope: {credential_in.scope}")

    # 1. Fetch the agent's long-term public key
    logger.info(f"Fetching agent record for agent_id: {credential_in.agent_id}")
    agent = crud.agent.get_by_agent_id(db=db, agent_id=credential_in.agent_id)
    if not agent:
        logger.warning(f"Agent not found during credential issuance: {credential_in.agent_id}. This agent MUST be registered first.")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Agent with ID '{credential_in.agent_id}' not found.")

    if not agent.public_key or not isinstance(agent.public_key, bytes):
        logger.error(f"Agent {credential_in.agent_id} has no valid public_key (must be bytes) in DB.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Agent public key not available or invalid in database.")

    # 2. Ephemeral public key and signature are already bytes from Pydantic model validation
    ephemeral_public_key_bytes = credential_in.ephemeral_public_key
    signature_bytes = credential_in.signature
    agent_public_key_bytes = agent.public_key

    # 3. Verify the signature - Mandatory
    logger.info(f"Attempting signature verification for agent {credential_in.agent_id}")
    # Optional: Detailed debug logging if needed, commented out by default
    # logger.debug(f"VERIFY_DEBUG: Agent's Stored PubKey (b64): {base64.b64encode(agent_public_key_bytes).decode('utf-8')}")
    # logger.debug(f"VERIFY_DEBUG: Ephemeral PubKey Received (bytes as hex): {ephemeral_public_key_bytes.hex()}")
    # logger.debug(f"VERIFY_DEBUG: Signature Received (bytes as hex): {signature_bytes.hex()}")
    try:
        public_key_obj = ed25519_crypto.Ed25519PublicKey.from_public_bytes(agent_public_key_bytes)
        public_key_obj.verify(signature_bytes, ephemeral_public_key_bytes) 
        logger.info(f"Signature verified successfully for agent {credential_in.agent_id}")
    except InvalidSignature:
        logger.warning(f"Invalid signature provided by agent {credential_in.agent_id}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid signature")
    except ValueError as ve: # Catch errors from from_public_bytes if key is malformed
        logger.error(f"Error loading agent's public key for signature verification (agent {credential_in.agent_id}): {ve}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid agent public key data: {ve}")
    except Exception as e:
        logger.error(f"Unexpected error during signature verification for agent {credential_in.agent_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Signature verification failed: {e}")

    # 4. Check if this is a secret access request and fetch the secret value
    secret_value = None
    if credential_in.scope and credential_in.scope.startswith("secret:"):
        secret_name = credential_in.scope[7:]  # Remove "secret:" prefix
        logger.info(f"Fetching secret '{secret_name}' for credential issuance")
        secret_obj = crud.secret.get_secret_by_name(db=db, name=secret_name)
        if not secret_obj:
            logger.warning(f"Secret '{secret_name}' not found for agent {credential_in.agent_id}")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Secret '{secret_name}' not found")
        secret_value = secret_obj.value
        logger.info(f"Successfully retrieved secret '{secret_name}' for credential issuance")

    # 5. Create the credential record in the database
    try:
        # crud.credential.create now expects obj_in where .ephemeral_public_key and .signature are bytes
        credential = crud.credential.create(db=db, obj_in=credential_in)
        logger.info(f"Successfully created credential {credential.credential_id} for agent {credential_in.agent_id}")
        # logger.info(f"[VAULT_EP_DEBUG] DB model credential.origin_context before return: {credential.origin_context}")
    except ValueError as ve: 
        logger.error(f"ValueError during credential creation in CRUD: {ve}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        logger.error(f"Failed to create credential record for agent {credential_in.agent_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not create credential")

    # 6. Add secret value to the response if this was a secret request
    if secret_value is not None:
        # We need to add the secret_value to the credential response
        # Since we're returning the credential object directly, we need to modify the response
        credential_dict = credential.__dict__.copy()
        credential_dict['secret_value'] = secret_value
        return credential_dict

    return credential # Pydantic will use schemas.credential.CredentialIssueResponse for serialization

@router.post("/credentials/{credential_id}/revoke", response_model=schemas.CredentialRevokeResponse)
def revoke_credential(
    credential_id: str,
    db: deps.DbDep,
    _: Any = deps.FlexibleAuthDep
):
    """Revoke an existing credential by setting its `revoked_at` timestamp.

    - Requires valid API Key authentication.
    - Idempotent: Returns success even if already revoked.

    Args:
        credential_id: The ID of the credential to revoke.
        db: Database session dependency.

    Raises:
        HTTPException 404: If the credential_id is not found.
        HTTPException 500: If a database error occurs during update.
    """
    logger.info(f"Attempting to revoke credential: {credential_id}")
    db_credential = crud.credential.revoke(db=db, credential_id=credential_id)

    if db_credential is None:
        logger.warning(f"Credential not found for revocation: {credential_id}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Credential not found")

    status_message = "revoked"
    revoked_at_aware = db_credential.revoked_at
    if revoked_at_aware and revoked_at_aware.tzinfo is None:
        revoked_at_aware = revoked_at_aware.replace(tzinfo=timezone.utc)

    if revoked_at_aware is None: # Should not happen if revoke worked, but check
        status_message = "revocation_failed"
        logger.error(f"Revocation failed unexpectedly for credential {credential_id}")
    # Check if it was already revoked before this call (within a small tolerance)
    elif datetime.now(timezone.utc) > revoked_at_aware + timedelta(seconds=1):
         status_message = "already_revoked"

    return schemas.CredentialRevokeResponse(credential_id=credential_id, status=status_message)

@router.post("/agents/{agent_id}/rotate-identity", status_code=status.HTTP_204_NO_CONTENT)
def rotate_agent_identity_key(
    agent_id: str,
    rotation_request: schemas.agent.AgentRotateRequest,
    db: deps.DbDep,
    _: Any = deps.FlexibleAuthDep
):
    """Update the long-term identity public key for an agent.

    - Requires valid API Key authentication.

    Args:
        agent_id: The ID of the agent whose key is being rotated.
        rotation_request: Request body containing the new public key (base64 encoded).
        db: Database session dependency.

    Raises:
        HTTPException 404: If the agent_id is not found.
        HTTPException 400: If the new_public_key format is invalid.
        HTTPException 500: If a database error occurs during update.
    """
    logger.info(f"Attempting to rotate identity key for agent: {agent_id}")
    agent = crud.agent.get_by_agent_id(db=db, agent_id=agent_id)
    if not agent:
        logger.warning(f"Agent not found for key rotation: {agent_id}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    # Decode the new public key
    try:
        # Basic validation - assumes Ed25519 key in Base64
        new_public_key_bytes = base64.b64decode(rotation_request.new_public_key)
        if len(new_public_key_bytes) != 32:
             raise ValueError("New public key must be 32 bytes long after base64 decoding")
        # TODO: Consider adding SSH format parsing/validation here like in agent create?
    except (ValueError, base64.binascii.Error) as e:
        logger.error(f"Invalid new public key format for agent {agent_id}: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid new public key format: {e}")

    # Update the agent record using the base update method
    try:
        update_data = {"public_key": new_public_key_bytes}
        crud.agent.update(db=db, db_obj=agent, obj_in=update_data)
        logger.info(f"Successfully rotated identity key for agent: {agent_id}")
    except Exception as e:
        logger.error(f"Failed to update agent key for {agent_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not rotate agent key")

    # No content response on success
    return

@router.get("/credentials/{credential_id}/verify", response_model=schemas.CredentialVerifyResponse)
def verify_credential(
    credential_id: str,
    db: deps.DbDep,
    # This endpoint is typically public, no API key dep by default
):
    logger.debug(f"Verifying credential: {credential_id}")
    db_credential = crud.credential.get_by_credential_id(db=db, credential_id=credential_id)

    now = datetime.now(timezone.utc) # Ensure timezone is imported
    status_message = "valid"
    is_valid = True
    issued_at_aware: Optional[datetime] = None
    expires_at_aware: Optional[datetime] = None
    scope_val: Optional[str] = None
    agent_id_val: Optional[str] = None
    eph_pub_key_b64: Optional[str] = None

    if not db_credential:
        logger.info(f"Credential not found for verification: {credential_id}")
        status_message = "not_found"
        is_valid = False
    else:
        scope_val = db_credential.scope
        agent_id_val = db_credential.agent_id
        if db_credential.ephemeral_public_key:
            if isinstance(db_credential.ephemeral_public_key, bytes):
                eph_pub_key_b64 = base64.b64encode(db_credential.ephemeral_public_key).decode('utf-8')
            else: # Should not happen if DB stores bytes
                eph_pub_key_b64 = str(db_credential.ephemeral_public_key) 

        revoked_at_aware = db_credential.revoked_at
        if revoked_at_aware and revoked_at_aware.tzinfo is None:
            revoked_at_aware = revoked_at_aware.replace(tzinfo=timezone.utc)

        expires_at_aware = db_credential.expires_at
        if expires_at_aware and expires_at_aware.tzinfo is None:
            expires_at_aware = expires_at_aware.replace(tzinfo=timezone.utc)
        
        issued_at_aware = db_credential.issued_at # From DB
        if issued_at_aware and issued_at_aware.tzinfo is None:
            issued_at_aware = issued_at_aware.replace(tzinfo=timezone.utc)

        if revoked_at_aware is not None and revoked_at_aware <= now:
            status_message = "revoked"
            is_valid = False
        elif expires_at_aware <= now:
            status_message = "expired"
            is_valid = False
        # else: status_message is "valid", is_valid is True (defaults)

    return schemas.CredentialVerifyResponse(
        credential_id=credential_id,
        is_valid=is_valid,
        status=status_message,
        scope=scope_val,
        agent_id=agent_id_val,
        issued_at=issued_at_aware,
        expires_at=expires_at_aware,
        ephemeral_public_key=eph_pub_key_b64,
        verified_at=now 
    )


# ─────────────────────────────────────────────────────────────────────────────
# Vault Browser Endpoints (user-facing metadata views)
# ─────────────────────────────────────────────────────────────────────────────


def _append_refresh_log(
    db,
    token_ref: str,
    status_val: str,
    error: Optional[str] = None,
    latency_ms: Optional[float] = None,
) -> None:
    """Append a refresh event to the token's refresh_log (last 20 entries)."""
    try:
        from app.models.vault_token import VaultToken

        vault_token = db.query(VaultToken).filter(
            VaultToken.token_ref == token_ref
        ).first()
        if vault_token is not None:
            entry: dict = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "status": status_val,
                "latency_ms": round(latency_ms, 1) if latency_ms is not None else None,
            }
            if error:
                entry["error"] = error[:200]
            log = list(vault_token.refresh_log or [])
            log.append(entry)
            vault_token.refresh_log = log[-20:]
            db.commit()
    except Exception:
        pass


def _extract_user_id_from_auth(auth_result: dict) -> Optional[str]:
    """Extract user_id (email) from flexible auth result."""
    if auth_result.get("auth_type") == "jwt":
        claims = auth_result.get("claims", {})
        return claims.get("sub")
    return None


@router.get("/user-tokens", status_code=status.HTTP_200_OK)
def list_user_vault_tokens(
    db: deps.DbDep,
    auth: Any = deps.FlexibleAuthDep,
):
    """List OAuth tokens stored in the vault for the current user.

    Returns metadata only -- access/refresh token values are never exposed.
    """
    from app.models.vault_token import VaultToken

    user_id = _extract_user_id_from_auth(auth)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not determine user identity",
        )

    now = datetime.now(timezone.utc)

    # Build a map of active connections: service_id -> (token_ref, scopes_granted)
    # Used for deduplication (only show the current active token per service)
    # and scope fallback (when vault blob doesn't contain scope).
    connections = (
        db.query(ConnectedService)
        .filter(
            ConnectedService.user_id == user_id,
            ConnectedService.disconnected_at.is_(None),
        )
        .all()
    )
    active_refs: dict[str, str] = {}
    connection_scopes: dict[str, list] = {}
    for conn in connections:
        if conn.oauth_token_ref:
            active_refs[conn.service_id] = conn.oauth_token_ref
        if conn.scopes_granted:
            connection_scopes[conn.service_id] = conn.scopes_granted

    tokens = (
        db.query(VaultToken)
        .filter(VaultToken.user_id == user_id)
        .order_by(VaultToken.created_at.desc())
        .all()
    )

    items = []
    seen_services: set[str] = set()
    for t in tokens:
        # Deduplicate: if this service has an active connection, only keep
        # the vault row that matches the current oauth_token_ref.
        # Orphan rows (from pre-fix reconnects) are skipped.
        if t.service_id in active_refs:
            if t.token_ref != active_refs[t.service_id]:
                continue
        elif t.service_id in seen_services:
            continue
        seen_services.add(t.service_id)

        expires_at = t.expires_at
        if expires_at and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        if expires_at is None:
            token_status = "active"
        elif expires_at <= now:
            token_status = "expired"
        elif expires_at <= now + timedelta(hours=1):
            token_status = "expiring_soon"
        else:
            token_status = "active"

        scopes = None
        try:
            vault = VaultClient()
            data = vault.retrieve_token(t.token_ref, update_usage=False, db=db)
            if data:
                scope_val = data.get("scope")
                if isinstance(scope_val, list):
                    scopes = scope_val
                elif isinstance(scope_val, str):
                    scopes = scope_val.split()
        except Exception:
            pass

        # Fallback: if vault blob had no scope, use connected_services.scopes_granted
        if not scopes and t.service_id in connection_scopes:
            scopes = connection_scopes[t.service_id]

        last_refreshed = getattr(t, "last_refreshed_at", None)
        if last_refreshed and last_refreshed.tzinfo is None:
            last_refreshed = last_refreshed.replace(tzinfo=timezone.utc)

        items.append({
            "service_id": t.service_id,
            "token_ref": t.token_ref,
            "status": token_status,
            "scopes_granted": scopes,
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "expires_at": expires_at.isoformat() if expires_at else None,
            "last_used_at": t.last_used_at.isoformat() if t.last_used_at else None,
            "last_refreshed_at": last_refreshed.isoformat() if last_refreshed else None,
            "refresh_count": t.refresh_count or 0,
            "refresh_log": getattr(t, "refresh_log", None) or [],
        })

    return {"tokens": items, "count": len(items)}


@router.get("/user-tokens/agent-linkage", status_code=status.HTTP_200_OK)
def get_user_token_agent_linkage(
    db: deps.DbDep,
    auth: Any = deps.FlexibleAuthDep,
):
    """Map each of the user's OAuth-connected services to agents with active delegations.

    For each service the user has a vault token for, returns agents that have
    active (non-expired, non-revoked) delegations from this user containing
    permissions for that service.
    """
    from app.models.vault_token import VaultToken
    from app.models.delegation import DelegationToken
    from app.models.agent import Agent

    user_id = _extract_user_id_from_auth(auth)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not determine user identity",
        )

    now = datetime.now(timezone.utc)

    user_services = (
        db.query(VaultToken.service_id)
        .filter(VaultToken.user_id == user_id)
        .distinct()
        .all()
    )
    service_ids = {row[0] for row in user_services}

    if not service_ids:
        return {"linkage": {}}

    active_delegations = (
        db.query(DelegationToken.agent_id, DelegationToken.delegated_permissions)
        .filter(
            DelegationToken.delegator == user_id,
            DelegationToken.revoked_at.is_(None),
            DelegationToken.expires_at > now,
        )
        .all()
    )

    if not active_delegations:
        return {"linkage": {sid: [] for sid in service_ids}}

    service_agents: dict[str, set[str]] = {sid: set() for sid in service_ids}
    for agent_id, perms in active_delegations:
        if not isinstance(perms, list):
            continue
        for perm in perms:
            parts = perm.split(":")
            if parts and parts[0] in service_agents:
                service_agents[parts[0]].add(agent_id)

    all_agent_ids: set[str] = set()
    for aids in service_agents.values():
        all_agent_ids.update(aids)

    agent_names: dict[str, str] = {}
    if all_agent_ids:
        rows = (
            db.query(Agent.agent_id, Agent.name)
            .filter(Agent.agent_id.in_(all_agent_ids))
            .all()
        )
        agent_names = {r[0]: r[1] for r in rows}

    linkage = {}
    for sid in service_ids:
        agents = sorted(service_agents.get(sid, set()))
        linkage[sid] = [
            {"agent_id": aid, "agent_name": agent_names.get(aid, aid)}
            for aid in agents
        ]

    return {"linkage": linkage}


@router.get("/user-credentials", status_code=status.HTTP_200_OK)
def list_user_credentials(
    db: deps.DbDep,
    auth: Any = deps.FlexibleAuthDep,
):
    """List ephemeral credentials issued for agents delegated by the current user.

    Returns metadata only -- key material is never exposed.
    """
    from app.models.credential import Credential
    from app.models.delegation import DelegationToken

    user_id = _extract_user_id_from_auth(auth)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not determine user identity",
        )

    now = datetime.now(timezone.utc)

    delegated_agent_ids = (
        db.query(DelegationToken.agent_id)
        .filter(DelegationToken.delegator == user_id)
        .distinct()
        .all()
    )
    agent_ids = [row[0] for row in delegated_agent_ids]

    if not agent_ids:
        return {"credentials": [], "count": 0}

    credentials = (
        db.query(Credential)
        .filter(Credential.agent_id.in_(agent_ids))
        .order_by(Credential.issued_at.desc())
        .limit(100)
        .all()
    )

    items = []
    for c in credentials:
        expires_at = c.expires_at
        if expires_at and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        revoked_at = c.revoked_at
        if revoked_at and revoked_at.tzinfo is None:
            revoked_at = revoked_at.replace(tzinfo=timezone.utc)

        if revoked_at is not None:
            cred_status = "revoked"
        elif expires_at and expires_at <= now:
            cred_status = "expired"
        else:
            cred_status = "valid"

        items.append({
            "credential_id": c.credential_id,
            "agent_id": c.agent_id,
            "scope": c.scope,
            "status": cred_status,
            "issued_at": c.issued_at.isoformat() if c.issued_at else None,
            "expires_at": expires_at.isoformat() if expires_at else None,
        })

    return {"credentials": items, "count": len(items)}


@router.get("/agent-sessions", status_code=status.HTTP_200_OK)
def list_user_agent_sessions(
    db: deps.DbDep,
    auth: Any = deps.FlexibleAuthDep,
    limit: int = 50,
    offset: int = 0,
):
    """List agent sessions created from the current user's delegations.

    Returns session metadata (no JWT strings) for agents the user has
    delegated permissions to, filtered to sessions where
    ``owner_email == current_user``.
    """
    from app.models.agent_session import AgentSession
    from app.models.delegation import DelegationToken
    from app.models.agent import Agent
    from sqlalchemy import func

    user_id = _extract_user_id_from_auth(auth)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not determine user identity",
        )

    now = datetime.now(timezone.utc)

    delegated_agent_ids = (
        db.query(DelegationToken.agent_id)
        .filter(DelegationToken.delegator == user_id)
        .distinct()
        .all()
    )
    agent_ids = [row[0] for row in delegated_agent_ids]

    if not agent_ids:
        return {"sessions": [], "total": 0}

    base_q = (
        db.query(AgentSession)
        .filter(
            AgentSession.agent_id.in_(agent_ids),
            AgentSession.owner_email == user_id,
            AgentSession.revoked_at.is_(None),
        )
    )

    total = base_q.count()

    sessions = (
        base_q
        .order_by(AgentSession.last_activity_at.desc().nullslast())
        .offset(offset)
        .limit(min(limit, 100))
        .all()
    )

    agent_names: dict[str, str] = {}
    if sessions:
        unique_aids = {s.agent_id for s in sessions}
        rows = db.query(Agent.agent_id, Agent.name).filter(Agent.agent_id.in_(unique_aids)).all()
        agent_names = {r[0]: r[1] for r in rows}

    items = []
    for s in sessions:
        expires_at = s.expires_at
        if expires_at and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        created_at = s.created_at
        if created_at and created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        last_activity = s.last_activity_at
        if last_activity and last_activity.tzinfo is None:
            last_activity = last_activity.replace(tzinfo=timezone.utc)

        if s.revoked_at is not None:
            sess_status = "revoked"
        elif expires_at and expires_at <= now:
            sess_status = "expired"
        else:
            sess_status = "active"

        perms = s.scoped_permissions
        perms_count = len(perms) if isinstance(perms, list) else 0

        items.append({
            "session_id": s.id,
            "agent_id": s.agent_id,
            "agent_name": agent_names.get(s.agent_id, s.agent_id),
            "delegation_id": s.delegation_id,
            "permissions_count": perms_count,
            "status": sess_status,
            "created_at": created_at.isoformat() if created_at else None,
            "expires_at": expires_at.isoformat() if expires_at else None,
            "last_activity_at": last_activity.isoformat() if last_activity else None,
        })

    return {"sessions": items, "total": total}


@router.get("/encryption-status", status_code=status.HTTP_200_OK)
def get_encryption_status(
    _: Any = deps.FlexibleAuthDep,
):
    """Return the encryption backend in use for each secret category.

    Helps admins verify that production is using KMS.
    """
    from app.core.kms import get_kms_client

    kms_client = get_kms_client()
    vault = VaultClient()

    return {
        "service_credentials": kms_client.backend,
        "vault_tokens": vault.encryption_backend,
        "secrets": "shamir_split_key",
    }