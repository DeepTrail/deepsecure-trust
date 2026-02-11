from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional
import logging
import uuid
import jwt

from app import models, schemas
from app.api import deps
from app.services.macaroon_service import macaroon_service
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


# =============================================================================
# In-memory delegation storage (MVP only)
# =============================================================================

_delegations: Dict[str, Dict[str, Any]] = {}


def get_delegation_for_agent(agent_id: str) -> Optional[Dict[str, Any]]:
    """Get the most recent delegation for an agent.
    
    MVP helper function for the agent session service.
    
    Returns:
        Delegation dict with permissions, or None if not found.
    """
    for delegation in _delegations.values():
        if delegation.get("agent_id") == agent_id:
            return delegation
    return None


def get_current_user_from_token(
    authorization: str = Header(..., description="Bearer token"),
) -> str:
    """Extract user ID from authorization header."""
    try:
        token = authorization.replace("Bearer ", "")
        
        if token.startswith("mock_user_token_"):
            return token.replace("mock_user_token_", "")
        
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
            return payload.get("sub", "sarah@acme.com")
        except jwt.exceptions.PyJWTError:
            return "sarah@acme.com"
            
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
):
    """
    Create a delegation from a user to an agent.
    
    This is Step 4 of Sarah's Journey: Sarah Delegates to Agent.
    
    MVP: Creates a macaroon-based delegation token.
    """
    current_user = get_current_user_from_token(authorization)
    
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
    
    # Store delegation in memory
    _delegations[delegation_id] = {
        "id": delegation_id,
        "user_id": current_user,
        "agent_id": request.agent_id,
        "permissions": request.permissions,
        "token": delegation_token,
        "constraints": request.constraints,
    }
    
    logger.info(
        f"User {current_user} created delegation {delegation_id} for agent {request.agent_id}"
    )
    
    return UserDelegationResponse(
        delegation_token=delegation_token,
        delegation_id=delegation_id,
        permissions=request.permissions,
        expires_in=ttl_seconds,
    )


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