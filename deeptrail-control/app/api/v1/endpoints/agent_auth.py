"""Agent authentication endpoints for Virtual MCP Server.

Implements the Ed25519 challenge-response authentication flow:
1. POST /challenge - Generate challenge nonce
2. POST /verify - Verify signature and issue JWT (C2)

These endpoints enable Step 5 of Sarah's journey: Agent Authenticates.

Security:
- Challenges are single-use (cleared after verification)
- Challenges expire after 5 minutes
- Signatures verified against registered Ed25519 public keys
- JWTs are scoped to delegation permissions
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api import deps
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

    delegation_service = DelegationService(db)

    # MVP: Load agent registry from settings or database
    # Production: Would use proper registry service
    agent_registry = getattr(settings, "AGENT_REGISTRY", {})

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
