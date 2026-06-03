"""User-related endpoints for Virtual MCP Server MVP.

This module provides endpoints for:
- Connecting backend services (Notion, Slack, etc.)
- User profile management (onboarding status)

These endpoints support Step 3 of Sarah's Journey: Sarah Connects Services.

MVP Simplification: Tokens stored in-memory vault only (no database table).
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Annotated, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Header, status
from pydantic import BaseModel, Field

from app.api import deps
from app.schemas.user import UserUpdate, UserResponse
from app.models.user import User
from app.services.vault_client import VaultClient
from app.services.scope_mapper import ScopeMapper
from app.services.cache_events import publish_service_disconnected
from app.models.connected_service import ConnectedService
from app.models.user_session import UserSession

logger = logging.getLogger(__name__)

router = APIRouter()

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
    expires_at: Optional[str] = None  # ISO timestamp when token expires
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


class ServicePermissions(BaseModel):
    """Permissions available for a single connected service."""

    connected: bool = True
    service_name: Optional[str] = None
    scopes_granted: List[str] = Field(default_factory=list)
    available_permissions: List[str] = Field(default_factory=list)
    connected_at: Optional[str] = None


class AvailablePermissionsResponse(BaseModel):
    """Response for available permissions endpoint."""

    services: Dict[str, ServicePermissions] = Field(
        default_factory=dict,
        description="Map of service_id to permissions info",
    )
    all_permissions: List[str] = Field(
        default_factory=list,
        description="Flat list of all available permissions",
    )
    total_services: int = Field(
        default=0,
        description="Number of connected services",
    )
    total_permissions: int = Field(
        default=0,
        description="Total unique permissions available",
    )


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
    import jwt as pyjwt
    from app.core.config import settings

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = authorization[len("Bearer "):]

    if token.startswith("mock_user_token_"):
        return token.replace("mock_user_token_", "")

    try:
        payload = pyjwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        sub = payload.get("sub")
        if not sub:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token missing 'sub' claim",
            )
        return sub
    except pyjwt.exceptions.PyJWTError as e:
        logger.warning(f"JWT decode failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


CurrentUserDep = Annotated[str, Depends(get_current_user_id)]


# =============================================================================
# User Profile Endpoints
# =============================================================================


@router.patch(
    "/me",
    response_model=UserResponse,
    summary="Update current user profile",
    description="Update the authenticated user's profile fields (e.g., onboarding_completed).",
)
def update_current_user(
    user_update: UserUpdate,
    current_user: CurrentUserDep,
    db: deps.DbDep,
) -> UserResponse:
    """Update the current user's profile."""
    # Get or create user record
    user = db.query(User).filter(User.user_id == current_user).first()

    if user is None:
        user = User(
            user_id=current_user,
            email=current_user,
            onboarding_completed=False,
        )
        db.add(user)
        db.flush()

    # Apply updates
    update_data = user_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(user, field, value)

    db.commit()
    db.refresh(user)

    return UserResponse.model_validate(user)


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user profile",
    description="Get the authenticated user's profile.",
)
def get_current_user_profile(
    current_user: CurrentUserDep,
    db: deps.DbDep,
) -> UserResponse:
    """Get the current user's profile, including role from user_sessions."""
    user = db.query(User).filter(User.user_id == current_user).first()

    session = (
        db.query(UserSession)
        .filter(
            UserSession.user_id == current_user,
            UserSession.revoked_at.is_(None),
        )
        .order_by(UserSession.created_at.desc())
        .first()
    )
    role = getattr(session, "role", "employee") if session else "employee"

    if user is None:
        now = datetime.now(timezone.utc)
        return UserResponse(
            user_id=current_user,
            email=current_user,
            role=role,
            onboarding_completed=False,
            created_at=now,
            updated_at=now,
        )

    resp = UserResponse.model_validate(user)
    resp.role = role
    return resp


# =============================================================================
# Service Connection Endpoints
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
    db: deps.DbDep,
) -> ConnectServiceResponseModel:
    """Connect a backend service for the current user."""
    try:
        # Get vault client
        vault = get_vault_client()

        # Parse scopes from OAuth response
        scopes = []
        if request.oauth_token.scope:
            scopes = request.oauth_token.scope.split()

        # Build oauth response dict with timestamps
        now = datetime.now(timezone.utc)
        oauth_response = {
            "access_token": request.oauth_token.access_token,
            "token_type": request.oauth_token.token_type,
            "stored_at": now.isoformat(),
        }
        if request.oauth_token.refresh_token:
            oauth_response["refresh_token"] = request.oauth_token.refresh_token
        if request.oauth_token.expires_at:
            # Store the expires_at timestamp directly
            oauth_response["expires_at"] = request.oauth_token.expires_at
        if request.oauth_token.scope:
            oauth_response["scope"] = request.oauth_token.scope

        # Store token in vault (with db for persistence)
        token_ref = vault.store_token(current_user, request.service_id, oauth_response, db=db)

        # Service name mapping
        service_names = {
            "notion": "Notion",
            "slack": "Slack",
            "hubspot": "HubSpot",
            "github": "GitHub",
            "google": "Google Calendar",
        }

        # Generate connection ID
        connection_id = f"conn-{uuid.uuid4()}"
        connected_at = datetime.now(timezone.utc)
        service_name = service_names.get(request.service_id, request.service_id)

        # Check if connection already exists and update, or create new
        existing = db.query(ConnectedService).filter(
            ConnectedService.user_id == current_user,
            ConnectedService.service_id == request.service_id,
        ).first()

        if existing:
            # Clean up old vault row before storing new ref (prevent orphans)
            if existing.oauth_token_ref and existing.oauth_token_ref != token_ref:
                try:
                    vault.delete_token(existing.oauth_token_ref, db=db)
                except Exception:
                    logger.warning("Failed to delete old vault token: ref=%s", existing.oauth_token_ref)
            # Update existing connection (reconnect)
            existing.oauth_token_ref = token_ref
            existing.scopes_granted = scopes
            existing.disconnected_at = None  # Re-enable if was disconnected
            existing.connected_at = connected_at
            connection_id = existing.id
            db.commit()
            db.refresh(existing)
            logger.info(f"User {current_user} reconnected service {request.service_id}")
        else:
            # Create new connection in database
            connection = ConnectedService(
                id=connection_id,
                user_id=current_user,
                service_id=request.service_id,
                service_name=service_name,
                oauth_token_ref=token_ref,
                scopes_granted=scopes,
                connected_at=connected_at,
            )
            db.add(connection)
            db.commit()
            db.refresh(connection)
            logger.info(f"User {current_user} connected service {request.service_id}")

        return ConnectServiceResponseModel(
            success=True,
            connection=ConnectedServiceResponse(
                id=connection_id,
                service_id=request.service_id,
                service_name=service_name,
                scopes_granted=scopes,
                connected_at=connected_at.isoformat(),
            ),
        )

    except Exception as e:
        logger.error(f"Failed to connect service: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to connect service: {str(e)}",
        )


@router.get(
    "/me/available-permissions",
    response_model=AvailablePermissionsResponse,
    summary="Get available permissions for delegation",
    description="""
    Returns all permissions the user can delegate based on their connected services.
    
    This helps users discover what permissions they can grant to agents without
    having to know the permission string format.
    
    **Use case:** Before creating a delegation, UI can show a picker of available
    permissions instead of requiring manual input.
    """,
)
def get_available_permissions(
    current_user: CurrentUserDep,
    db: deps.DbDep,
) -> AvailablePermissionsResponse:
    """Get all permissions available for delegation based on connected services.

    Returns:
        AvailablePermissionsResponse with services map and flat permission list
    """
    # Get all active connected services for user
    connections = (
        db.query(ConnectedService)
        .filter(
            ConnectedService.user_id == current_user,
            ConnectedService.disconnected_at.is_(None),
        )
        .all()
    )

    services: Dict[str, ServicePermissions] = {}
    all_permissions: set = set()

    for conn in connections:
        # Get permissions for this service's scopes
        scopes = conn.scopes_granted or []
        perms = ScopeMapper.get_permissions_for_scopes(conn.service_id, scopes)

        services[conn.service_id] = ServicePermissions(
            connected=True,
            service_name=conn.service_name,
            scopes_granted=scopes,
            available_permissions=sorted(list(perms)),
            connected_at=conn.connected_at.isoformat() if conn.connected_at else None,
        )

        all_permissions.update(perms)

    return AvailablePermissionsResponse(
        services=services,
        all_permissions=sorted(list(all_permissions)),
        total_services=len(services),
        total_permissions=len(all_permissions),
    )


class DisconnectServiceResponse(BaseModel):
    """Response after disconnecting a service."""

    success: bool
    service_id: str
    message: str


@router.delete(
    "/me/services/{service_id}",
    response_model=DisconnectServiceResponse,
    summary="Disconnect a backend service",
    description="""
    Disconnect a backend service from the user's account.
    
    This marks the service as disconnected but preserves the connection record
    for audit purposes. The token remains in the vault but is invalidated.
    
    Publishes a cache invalidation event so Gateway clears cached tokens.
    """,
)
def disconnect_service(
    service_id: str,
    current_user: CurrentUserDep,
    db: deps.DbDep,
) -> DisconnectServiceResponse:
    """Disconnect a backend service for the current user."""
    # Find the connection
    connection = db.query(ConnectedService).filter(
        ConnectedService.user_id == current_user,
        ConnectedService.service_id == service_id,
        ConnectedService.disconnected_at.is_(None),
    ).first()

    if not connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Service '{service_id}' not connected or already disconnected",
        )

    # Mark as disconnected (soft delete)
    connection.disconnected_at = datetime.now(timezone.utc)
    db.commit()

    # Publish cache invalidation event
    publish_service_disconnected(current_user, service_id)

    logger.info(f"User {current_user} disconnected service {service_id}")

    return DisconnectServiceResponse(
        success=True,
        service_id=service_id,
        message=f"Service '{service_id}' disconnected successfully",
    )
