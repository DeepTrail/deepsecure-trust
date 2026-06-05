"""Agent authentication endpoints for Virtual MCP Server.

Implements the Ed25519 challenge-response authentication flow:
1. POST /challenge - Generate challenge nonce
2. POST /verify - Verify signature and issue JWT (C2)

Agent delegation management (round-robin multi-user support):
3. GET /delegations - Agent lists its active delegations
4. POST /delegation-token - Exchange agent JWT + delegation_id for scoped JWT

These endpoints enable Step 5 of Sarah's journey: Agent Authenticates.

Security:
- Challenges are single-use (cleared after verification)
- Challenges expire after 5 minutes
- Signatures verified against registered Ed25519 public keys
- JWTs are scoped to delegation permissions
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api import deps
from app.core.security import create_access_token
from app.models.agent_session import AgentSession
from app.models.delegation import DelegationToken
from app.schemas.agent_auth import (
    AgentAuthError,
    AgentChallengeRequest,
    AgentChallengeResponse,
    AgentVerifyRequest,
    AgentVerifyResponse,
)
from app.services.agent_session_service import (
    AgentNotFoundError,
    AgentSessionService,
    ChallengeExpiredError,
    InvalidSignatureError,
    NoDelegationError,
)
from app.services.delegation_service import DelegationService

logger = logging.getLogger(__name__)

router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────────
# Dependencies
# ─────────────────────────────────────────────────────────────────────────────


def get_agent_session_service(
    db: deps.DbDep,
) -> AgentSessionService:
    """Get configured AgentSessionService.

    In MVP, agent registry is loaded from config or database.
    Production would use proper dependency injection.
    """
    from app.core.config import settings
    from app import crud
    import base64

    delegation_service = DelegationService(db)

    # MVP: Load agent registry from settings AND database
    agent_registry = dict(getattr(settings, "AGENT_REGISTRY", {}))
    
    # Also load agents from database
    try:
        db_agents = crud.agent.get_multi(db, limit=1000)
        for agent in db_agents:
            if agent.public_key and agent.agent_id:
                # Convert bytes to base64 for the registry
                if isinstance(agent.public_key, bytes):
                    public_key_b64 = base64.b64encode(agent.public_key).decode()
                else:
                    public_key_b64 = agent.public_key
                agent_registry[agent.agent_id] = public_key_b64
    except Exception as e:
        logger.warning(f"Failed to load agents from database: {e}")

    return AgentSessionService(
        db_session=db,
        delegation_service=delegation_service,
        jwt_secret=settings.SECRET_KEY,
        agent_registry=agent_registry,
    )


AgentSessionServiceDep = Annotated[AgentSessionService, Depends(get_agent_session_service)]


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────


@router.post(
    "/challenge",
    response_model=AgentChallengeResponse,
    responses={
        404: {"model": AgentAuthError, "description": "Agent not found"},
    },
    summary="Create authentication challenge",
    description="""
    Generate a cryptographic challenge for agent authentication.

    The agent must sign this challenge with their Ed25519 private key
    and submit to the /verify endpoint within 5 minutes.

    **Flow:**
    1. Agent calls this endpoint with their agent_id
    2. Server generates a 256-bit random nonce
    3. Agent receives nonce and signs it with private key
    4. Agent submits signature to /verify endpoint
    """,
)
async def create_challenge(
    request: AgentChallengeRequest,
    service: AgentSessionServiceDep,
) -> AgentChallengeResponse:
    """Generate a challenge nonce for an agent to sign.

    This is Step 5.1 of Sarah's journey: Agent requests challenge.

    Args:
        request: Contains agent_id
        service: AgentSessionService instance

    Returns:
        Challenge nonce and expiration time

    Raises:
        HTTPException 404: If agent not found in registry
    """
    try:
        challenge = service.create_challenge(request.agent_id)

        logger.info("Created challenge for agent: %s", request.agent_id)

        return AgentChallengeResponse(
            challenge=challenge,
            expires_in=service.CHALLENGE_TTL_SECONDS,
        )

    except AgentNotFoundError as e:
        logger.warning("Challenge requested for unknown agent: %s", request.agent_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "agent_not_found",
                "message": str(e),
            },
        )


# ─────────────────────────────────────────────────────────────────────────────
# Verify Endpoint (C2)
# ─────────────────────────────────────────────────────────────────────────────


@router.post(
    "/verify",
    response_model=AgentVerifyResponse,
    responses={
        400: {
            "model": AgentAuthError,
            "description": "Invalid signature or expired challenge",
        },
        403: {"model": AgentAuthError, "description": "No valid delegation"},
        404: {"model": AgentAuthError, "description": "Agent not found"},
    },
    summary="Verify signature and create session",
    description="""
    Verify an agent's Ed25519 signature and issue an Agent Session JWT.

    This is Step 5.2 of Sarah's journey: Agent submits signed challenge.

    **Security Flow:**
    1. Validate the challenge matches what was issued
    2. Verify Ed25519 signature against agent's registered public key
    3. Clear the challenge (single-use)
    4. Find valid delegation for the agent
    5. Create AgentSession in database
    6. Issue JWT with scoped permissions

    **JWT Claims (Layer 3):**
    - `sub`: Agent ID
    - `owner`: Delegator's email (e.g., sarah@acme.com)
    - `delegated_permissions`: Permissions from delegation
    - `delegation_id`: Reference to active delegation
    - `session_id`: Unique session identifier
    - `exp`: Expiration (8 hours from issuance)
    """,
)
async def verify_and_create_session(
    request: AgentVerifyRequest,
    service: AgentSessionServiceDep,
) -> AgentVerifyResponse:
    """Verify agent signature and issue Agent Session JWT.

    This completes Step 5 of Sarah's journey: Agent Authenticates.

    Args:
        request: Contains agent_id, challenge, signature, optional delegation_id
        service: AgentSessionService instance

    Returns:
        Agent Session JWT and session metadata

    Raises:
        HTTPException 400: If signature invalid or challenge expired
        HTTPException 403: If no valid delegation exists
        HTTPException 404: If agent not found in registry
    """
    try:
        # Verify signature and create session
        result = service.verify_and_create_session(
            agent_id=request.agent_id,
            challenge=request.challenge,
            signature=request.signature,
            delegation_id=request.delegation_id,
        )

        logger.info(
            "Agent authenticated successfully: %s, session: %s",
            request.agent_id,
            result.session.id,
        )

        return AgentVerifyResponse(
            access_token=result.token,
            token_type="Bearer",
            expires_in=result.expires_in,
            session_id=result.session.id,
        )

    except AgentNotFoundError as e:
        logger.warning(
            "Verify failed - agent not found: %s",
            request.agent_id,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "agent_not_found",
                "message": str(e),
            },
        )

    except ChallengeExpiredError as e:
        logger.warning(
            "Verify failed - challenge expired/invalid: %s",
            request.agent_id,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "challenge_expired",
                "message": str(e),
            },
        )

    except InvalidSignatureError:
        logger.warning(
            "Verify failed - invalid signature: %s",
            request.agent_id,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "invalid_signature",
                "message": "Signature verification failed",
            },
        )

    except NoDelegationError as e:
        logger.warning(
            "Verify failed - no valid delegation: %s",
            request.agent_id,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "no_delegation",
                "message": str(e),
            },
        )


# ─────────────────────────────────────────────────────────────────────────────
# Agent Delegation Listing & Scoped Token Exchange
# ─────────────────────────────────────────────────────────────────────────────


class AgentDelegationEntry(BaseModel):
    """A single delegation visible to the agent."""

    delegation_id: str
    delegator: str
    delegated_permissions: List[str]
    expires_at: str
    created_at: str


class DelegationTokenRequest(BaseModel):
    """Request to exchange a delegation_id for a scoped JWT."""

    delegation_id: str = Field(..., description="ID of the delegation to activate")


class DelegationTokenResponse(BaseModel):
    """Response with a JWT scoped to a single delegation."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int
    session_id: str
    delegation_id: str
    owner: str


@router.get(
    "/delegations",
    response_model=List[AgentDelegationEntry],
    summary="List active delegations for this agent",
    description="""
    Returns all active (non-revoked, non-expired) delegations granted to the
    calling agent. Used during round-robin execution to discover which users
    have delegated to this agent and what permissions are available.

    Auth: Any valid Agent JWT (discovery or delegation-scoped).
    """,
)
def list_agent_delegations(
    identity: deps.AgentIdentityDep,
    db: Session = Depends(deps.get_db),
) -> List[AgentDelegationEntry]:
    """List active delegations for the authenticated agent."""
    agent_id = identity["agent_id"]

    rows = (
        db.query(DelegationToken)
        .filter(
            DelegationToken.agent_id == agent_id,
            DelegationToken.revoked_at.is_(None),
            DelegationToken.expires_at > datetime.now(timezone.utc),
        )
        .order_by(DelegationToken.created_at.desc())
        .all()
    )

    logger.info(
        "Agent %s listed delegations: %d active",
        agent_id,
        len(rows),
    )

    return [
        AgentDelegationEntry(
            delegation_id=d.id,
            delegator=d.delegator,
            delegated_permissions=d.delegated_permissions or [],
            expires_at=d.expires_at.isoformat() if d.expires_at else "",
            created_at=d.created_at.isoformat() if d.created_at else "",
        )
        for d in rows
    ]


@router.post(
    "/delegation-token",
    response_model=DelegationTokenResponse,
    summary="Get a JWT scoped to a specific delegation",
    description="""
    Exchange a valid Agent JWT and a delegation_id for a new JWT that is
    scoped to that single delegation's owner and permissions. This avoids
    re-doing OIDC exchange when switching between delegations during
    round-robin execution.

    Auth: Any valid Agent JWT (discovery or delegation-scoped).
    """,
)
def issue_delegation_token(
    request: DelegationTokenRequest,
    identity: deps.AgentIdentityDep,
    db: Session = Depends(deps.get_db),
) -> DelegationTokenResponse:
    """Issue a scoped JWT for a specific delegation."""
    agent_id = identity["agent_id"]

    delegation = (
        db.query(DelegationToken)
        .filter(DelegationToken.id == request.delegation_id)
        .first()
    )

    if not delegation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "delegation_not_found",
                "message": f"Delegation {request.delegation_id} not found",
            },
        )

    if delegation.agent_id != agent_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "delegation_not_owned",
                "message": "This delegation does not belong to your agent",
            },
        )

    if delegation.is_revoked:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "delegation_revoked",
                "message": "This delegation has been revoked",
            },
        )

    if delegation.is_expired:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "delegation_expired",
                "message": "This delegation has expired",
            },
        )

    session = AgentSession.from_delegation(
        delegation=delegation,
        agent_id=agent_id,
    )
    db.add(session)
    db.commit()

    access_token = create_access_token(
        subject=agent_id,
        expires_delta=timedelta(hours=1),
        extra_claims={
            "sub": agent_id,
            "owner": delegation.delegator or "",
            "delegation_id": str(delegation.id),
            "delegated_permissions": delegation.delegated_permissions or [],
            "session_id": str(session.id),
        },
    )

    logger.info(
        "Issued delegation-scoped JWT for agent %s, delegation %s (owner=%s), session %s",
        agent_id,
        delegation.id,
        delegation.delegator,
        session.id,
    )

    return DelegationTokenResponse(
        access_token=access_token,
        expires_in=3600,
        session_id=str(session.id),
        delegation_id=str(delegation.id),
        owner=delegation.delegator or "",
    )
