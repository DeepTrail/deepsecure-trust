from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import Any, Dict, List, Optional
import logging
import uuid
import jwt

from app import models, schemas
from app.api import deps
from app.models.connected_service import ConnectedService
from app.models.delegation import DelegationToken
from app.services.macaroon_service import macaroon_service
from app.services.scope_mapper import ScopeMapper
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


# =============================================================================
# User Delegation Schemas (Step 4 of Sarah's Journey)
# =============================================================================


class UserDelegationRequest(BaseModel):
    """Request for a user to delegate permissions to an agent."""
    
    agent_id: str = Field(..., description="Agent to delegate to")
    permissions: List[str] = Field(..., description="Permissions to delegate")
    constraints: Optional[Dict[str, Any]] = Field(
        default=None, description="Optional constraints"
    )


class UserDelegationResponse(BaseModel):
    """Response after creating a delegation."""
    
    delegation_token: str
    delegation_id: str
    permissions: List[str]
    expires_in: int = 28800  # 8 hours


def get_current_user_from_token(
    authorization: str = Header(..., description="Bearer token"),
) -> str:
    """Extract user ID from authorization header."""
    return _parse_user_token(authorization)["sub"]


def _parse_user_token(authorization: str) -> Dict[str, Any]:
    """Parse the full User JWT payload from the authorization header.

    Returns a dict with at least 'sub'. Other claims (organization_id,
    session_id, etc.) are included when present.
    """
    try:
        token = authorization.replace("Bearer ", "")

        if token.startswith("mock_user_token_"):
            return {"sub": token.replace("mock_user_token_", "")}

        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
            payload.setdefault("sub", "sarah@acme.com")
            return payload
        except jwt.exceptions.PyJWTError:
            return {"sub": "sarah@acme.com"}

    except Exception as e:
        logger.warning(f"Failed to extract user from token: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header",
        )


# =============================================================================
# User Delegation Endpoint (Step 4 of Sarah's Journey)
# =============================================================================


@router.post("/delegate", response_model=UserDelegationResponse)
def create_user_delegation(
    request: UserDelegationRequest,
    authorization: str = Header(...),
    db: Session = Depends(deps.get_db),
):
    """
    Create a delegation from a user to an agent.
    
    This is Step 4 of Sarah's Journey: Sarah Delegates to Agent.
    
    Validates that requested permissions are allowed by the user's
    connected service scopes (monotonic attenuation principle).
    
    MVP: Creates a macaroon-based delegation token.
    """
    user_claims = _parse_user_token(authorization)
    current_user = user_claims["sub"]
    user_org_id = user_claims.get("organization_id")
    
    # Get user's connected services for permission validation
    connections = (
        db.query(ConnectedService)
        .filter(
            ConnectedService.user_id == current_user,
            ConnectedService.disconnected_at.is_(None),
        )
        .all()
    )
    
    if not connections:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "no_connected_services",
                "message": "User has no connected services",
                "hint": "Connect a service before creating delegations",
            },
        )
    
    # Build list of (service_id, scopes) for ScopeMapper
    connected_services = [
        (conn.service_id, conn.scopes_granted or [])
        for conn in connections
    ]
    
    # Validate permissions using ScopeMapper
    is_valid, invalid_perms = ScopeMapper.validate_permissions(
        request.permissions,
        connected_services,
    )
    
    if not is_valid:
        allowed = ScopeMapper.get_all_allowed_permissions(connected_services)
        logger.warning(
            "Permission validation failed: user=%s invalid=%s",
            current_user,
            invalid_perms,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "permission_validation_failed",
                "message": "Requested permissions not allowed by connected scopes",
                "invalid_permissions": invalid_perms,
                "allowed_permissions": sorted(list(allowed)),
                "hint": "Connect service with additional scopes or remove invalid permissions",
            },
        )
    
    # Calculate TTL from constraints
    ttl_hours = 8  # Default
    if request.constraints and "expires_in_hours" in request.constraints:
        ttl_hours = request.constraints["expires_in_hours"]
    ttl_seconds = ttl_hours * 3600

    # Generate delegation ID
    delegation_id = f"del-{uuid.uuid4()}"

    # Create delegation token using macaroon service
    delegation_token = macaroon_service.mint_delegation_macaroon(
        target_agent_id=request.agent_id,
        resource="*",  # All resources for MVP
        permissions=request.permissions,
        ttl_seconds=ttl_seconds,
    )

    now = datetime.now(timezone.utc)
    delegation_row = DelegationToken(
        id=delegation_id,
        agent_id=request.agent_id,
        delegator=current_user,
        delegated_permissions=request.permissions,
        constraints=request.constraints or {},
        organization_id=user_org_id,
        created_at=now,
        expires_at=now + timedelta(seconds=ttl_seconds),
    )
    db.add(delegation_row)
    db.commit()

    logger.info(
        "User %s created delegation %s for agent %s",
        current_user,
        delegation_id,
        request.agent_id,
    )

    return UserDelegationResponse(
        delegation_token=delegation_token,
        delegation_id=delegation_id,
        permissions=request.permissions,
        expires_in=ttl_seconds,
    )


# =============================================================================
# List User Delegations
# =============================================================================


class DelegationSummary(BaseModel):
    """Summary of a delegation for listing."""

    delegation_id: str
    agent_id: str
    permissions: List[str]
    expires_in: int
    created_at: Optional[str] = None


@router.get("/delegations", response_model=List[DelegationSummary])
def list_user_delegations(
    authorization: str = Header(...),
    db: Session = Depends(deps.get_db),
):
    """List all delegations created by the current user."""
    current_user = get_current_user_from_token(authorization)

    rows = (
        db.query(DelegationToken)
        .filter(DelegationToken.delegator == current_user)
        .order_by(DelegationToken.created_at.desc())
        .all()
    )

    result = []
    for d in rows:
        expires_in = int((d.expires_at - d.created_at).total_seconds()) if d.expires_at and d.created_at else 28800
        result.append(
            DelegationSummary(
                delegation_id=d.id,
                agent_id=d.agent_id,
                permissions=d.delegated_permissions or [],
                expires_in=expires_in,
                created_at=d.created_at.isoformat() if d.created_at else None,
            )
        )
    return result


# =============================================================================
# Agent-to-Agent Delegation (Original Endpoint)
# =============================================================================


@router.post("/agent-delegate", response_model=schemas.DelegationResponse)
def delegate_access(
    *,
    delegation_in: schemas.DelegationRequest,
    current_agent: models.Agent = Depends(deps.get_current_active_agent),
):
    """
    Delegate access from one agent to another by minting a macaroon.

    This endpoint allows an authenticated agent to generate a temporary,
    scoped credential (a macaroon) and delegate it to another agent.
    """
    delegation_token = macaroon_service.mint_delegation_macaroon(
        target_agent_id=delegation_in.target_agent_id,
        resource=delegation_in.resource,
        permissions=delegation_in.permissions,
        ttl_seconds=delegation_in.ttl_seconds,
    )
    return {"delegation_token": delegation_token} 