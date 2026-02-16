"""User-related endpoints for Virtual MCP Server MVP.

This module provides endpoints for:
- Connecting backend services (Notion, Slack, etc.)

These endpoints support Step 3 of Sarah's Journey: Sarah Connects Services.

MVP Simplification: Tokens stored in-memory vault only (no database table).
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Annotated, Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Header, status
from pydantic import BaseModel, Field

from app.api import deps
from app.services.vault_client import VaultClient

logger = logging.getLogger(__name__)

router = APIRouter()

# In-memory storage for connected services (MVP only)
# Format: {user_id: {service_id: connection_info}}
_connected_services: Dict[str, Dict[str, Dict[str, Any]]] = {}

# Shared vault instance for MVP
_vault_client: Optional[VaultClient] = None


def get_vault_client() -> VaultClient:
    """Get singleton VaultClient instance."""
    global _vault_client
    if _vault_client is None:
        _vault_client = VaultClient()
    return _vault_client


# =============================================================================
# Request/Response Models
# =============================================================================


class OAuthToken(BaseModel):
    """OAuth token data from provider."""

    access_token: str
    token_type: str = "bearer"
    refresh_token: Optional[str] = None
    expires_in: Optional[int] = None
    scope: Optional[str] = None


class ConnectServiceRequest(BaseModel):
    """Request to connect a backend service."""

    service_id: str = Field(..., description="Service identifier (e.g., 'notion', 'slack')")
    oauth_token: OAuthToken = Field(..., description="OAuth token from provider")

    model_config = {
        "json_schema_extra": {
            "example": {
                "service_id": "notion",
                "oauth_token": {
                    "access_token": "secret_xxx",
                    "token_type": "bearer",
                    "scope": "read_content search",
                },
            }
        }
    }


class ConnectedServiceResponse(BaseModel):
    """Response for a connected service."""

    id: str
    service_id: str
    service_name: Optional[str]
    scopes_granted: List[str]
    connected_at: str


class ConnectServiceResponseModel(BaseModel):
    """Response after connecting a service."""

    success: bool
    connection: ConnectedServiceResponse


# =============================================================================
# Dependencies
# =============================================================================


def get_current_user_id(
    authorization: str = Header(..., description="Bearer token"),
) -> str:
    """Extract user ID from authorization header.
    
    MVP: Simple token parsing.
    Production: JWT validation with proper claims extraction.
    """
    import jwt
    from app.core.config import settings
    
    try:
        # Remove 'Bearer ' prefix
        token = authorization.replace("Bearer ", "")
        
        # Check if it's a mock token
        if token.startswith("mock_user_token_"):
            return token.replace("mock_user_token_", "")
        
        # Try to decode JWT
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
            return payload.get("sub", "sarah@acme.com")
        except jwt.exceptions.PyJWTError:
            return "sarah@acme.com"
            
    except Exception as e:
        logger.warning(f"Failed to extract user from token: {e}")
        return "sarah@acme.com"


CurrentUserDep = Annotated[str, Depends(get_current_user_id)]


# =============================================================================
# Endpoints
# =============================================================================


@router.post(
    "/me/services/connect",
    response_model=ConnectServiceResponseModel,
    summary="Connect a backend service",
    description="""
    Connect a backend service (Notion, Slack, etc.) to the user's account.
    
    This is Step 3 of Sarah's Journey: Sarah Connects Services.
    
    MVP: Tokens stored in-memory vault only.
    """,
)
def connect_service(
    request: ConnectServiceRequest,
    current_user: CurrentUserDep,
) -> ConnectServiceResponseModel:
    """Connect a backend service for the current user."""
    try:
        # Get vault client
        vault = get_vault_client()
        
        # Parse scopes from OAuth response
        scopes = []
        if request.oauth_token.scope:
            scopes = request.oauth_token.scope.split()
        
        # Build oauth response dict
        oauth_response = {
            "access_token": request.oauth_token.access_token,
            "token_type": request.oauth_token.token_type,
        }
        if request.oauth_token.refresh_token:
            oauth_response["refresh_token"] = request.oauth_token.refresh_token
        if request.oauth_token.expires_in:
            oauth_response["expires_in"] = request.oauth_token.expires_in
        
        # Store token in vault
        token_ref = vault.store_token(current_user, request.service_id, oauth_response)
        
        # Service name mapping
        service_names = {
            "notion": "Notion",
            "slack": "Slack",
            "hubspot": "HubSpot",
            "github": "GitHub",
            "google": "Google Calendar",
        }
        
        # Store connection info in memory
        connection_id = f"conn-{uuid.uuid4()}"
        connected_at = datetime.now(timezone.utc)
        
        connection_info = {
            "id": connection_id,
            "service_id": request.service_id,
            "service_name": service_names.get(request.service_id, request.service_id),
            "scopes_granted": scopes,
            "connected_at": connected_at.isoformat(),
            "token_ref": token_ref,
        }
        
        # Store in memory
        if current_user not in _connected_services:
            _connected_services[current_user] = {}
        _connected_services[current_user][request.service_id] = connection_info
        
        logger.info(f"User {current_user} connected service {request.service_id}")
        
        return ConnectServiceResponseModel(
            success=True,
            connection=ConnectedServiceResponse(
                id=connection_id,
                service_id=request.service_id,
                service_name=connection_info["service_name"],
                scopes_granted=scopes,
                connected_at=connection_info["connected_at"],
            ),
        )
        
    except Exception as e:
        logger.error(f"Failed to connect service: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to connect service: {str(e)}",
        )
