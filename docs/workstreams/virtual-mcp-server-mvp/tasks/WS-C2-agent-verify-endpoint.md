# Task: WS-C2 Implement Agent Verify Endpoint

---

## Metadata

| Field | Value |
|-------|-------|
| **Status** | `ready` |
| **Design Doc** | [deepsecure-virtual-mcp-server-mvp.md](../../../design/internal/markdowns/deepsecure-virtual-mcp-server-mvp.md) |
| **Workstream** | WS-C: Auth & Permissions |
| **Dependencies** | C1 (Agent Challenge Endpoint) |
| **Blocked By** | None (C1 ticket created, A8 complete ✅) |
| **Assigned** | - |
| **Created** | February 4, 2026 |
| **Estimated Complexity** | `M` (2-4 hours) |
| **Batch** | 4 |

---

## Validation Mapping

| Mapping | Value |
|---------|-------|
| **Validates Demo** | Demo 3: Delegation Execution, Demo 4: Permission Enforcement |
| **Validates User Journey Step** | Step 5: Agent Authenticates (completion) |

---

## Pre-Conditions

Before starting this task, ensure:

- [x] C1 (Agent Challenge Endpoint) ticket created
- [x] A8 (AgentSessionService) is complete
- [x] A7 (Agent Session model) is complete
- [x] A6 (DelegationService) is complete
- [ ] `deeptrail-control/app/api/v1/endpoints/agent_auth.py` exists (from C1)
- [ ] `deeptrail-control/app/schemas/agent_auth.py` exists (from C1)
- [ ] AgentSessionService can be imported from `app.services`

---

## Task Description

Implement the `/api/v1/auth/agent/verify` endpoint that verifies an agent's Ed25519 signature and issues an Agent Session JWT. This completes the agent authentication flow from the MVP design.

### Context

From the MVP design (Section 2.6 - Step 5: Agent Authenticates):

```
Agent Authentication Flow (Step 3-5):

3. Agent signs challenge with private key:
   POST /api/v1/auth/agent/verify
   {
     "agent_id": "agent-sdr-001",
     "challenge": "random-nonce-xyz",
     "signature": "ed25519-signature-of-challenge"
   }

4. Control Plane validates and issues Agent Session JWT:
   
   LAYER 3: AGENT SESSION JWT
   {
     "sub": "agent-sdr-001",
     "owner": "sarah@acme.com",          // From delegation
     "idp_issuer": "https://acme.okta.com",
     "party_type": "first_party",
     "delegated_permissions": [           // From delegation token
       "notion:pages:search",
       "notion:pages:read",
       "slack:messages:search",
       "slack:channels:list"
     ],
     "delegation_id": "del-sarah-sdr-001",
     "groups": ["sales"],                 // Sarah's groups
     "session_id": "asess-sdr-001-ghi789",
     "exp": 1737936000                    // 8 hours
   }

5. Control Plane creates Agent Session in database

RESULT: Agent has authenticated session linked to Sarah
```

The endpoint must:
- **Validate Signature**: Verify Ed25519 signature against agent's registered public key
- **Clear Challenge**: Remove the single-use nonce after verification
- **Find Delegation**: Locate valid delegation for the agent
- **Create Session**: Persist AgentSession to database
- **Issue JWT**: Return Agent Session JWT (Layer 3) with scoped permissions

### Technical Notes

- Use `AgentSessionService.verify_and_create_session()` from A8
- Signature is base64url-encoded Ed25519 signature of the challenge
- Challenge must match what was issued by `/challenge` endpoint
- If no valid delegation exists, return 403 Forbidden
- JWT contains permissions from delegation (monotonic attenuation)
- Session TTL: 8 hours (shorter than delegation's 7 days)

---

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `deeptrail-control/app/api/v1/endpoints/agent_auth.py` | **MODIFY** | Add verify endpoint |
| `deeptrail-control/tests/api/test_agent_auth.py` | **MODIFY** | Add verify tests |

---

## Implementation Details

### 1. Add Verify Endpoint to `agent_auth.py`

Add this endpoint to the existing `app/api/v1/endpoints/agent_auth.py` file (created in C1):

```python
# Add these imports at the top (if not already present)
from app.schemas.agent_auth import (
    AgentChallengeRequest,
    AgentChallengeResponse,
    AgentVerifyRequest,
    AgentVerifyResponse,
    AgentAuthError,
)
from app.services.agent_session_service import (
    AgentSessionService,
    AgentNotFoundError,
    ChallengeExpiredError,
    InvalidSignatureError,
    NoDelegationError,
)


# ─────────────────────────────────────────────────────────────────────────────
# Verify Endpoint
# ─────────────────────────────────────────────────────────────────────────────


@router.post(
    "/verify",
    response_model=AgentVerifyResponse,
    responses={
        400: {"model": AgentAuthError, "description": "Invalid signature or expired challenge"},
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
    """
    Verify agent signature and issue Agent Session JWT.
    
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
        session, token = service.verify_and_create_session(
            agent_id=request.agent_id,
            challenge=request.challenge,
            signature=request.signature,
            delegation_id=request.delegation_id,
        )
        
        logger.info(
            "Agent authenticated successfully: %s, session: %s",
            request.agent_id,
            session.id,
        )
        
        return AgentVerifyResponse(
            access_token=token,
            token_type="Bearer",
            expires_in=service.SESSION_TTL_HOURS * 3600,  # Convert to seconds
            session_id=session.id,
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
        
    except InvalidSignatureError as e:
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
```

### 2. Complete `agent_auth.py` File

Here's the complete file for reference (combining C1 and C2):

```python
"""Agent authentication endpoints for Virtual MCP Server.

Implements the Ed25519 challenge-response authentication flow:
1. POST /challenge - Generate challenge nonce (C1)
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
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.agent_auth import (
    AgentChallengeRequest,
    AgentChallengeResponse,
    AgentVerifyRequest,
    AgentVerifyResponse,
    AgentAuthError,
)
from app.services.agent_session_service import (
    AgentSessionService,
    AgentNotFoundError,
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
    """
    Get configured AgentSessionService.
    
    In MVP, agent registry is loaded from config or database.
    Production would use proper dependency injection.
    """
    from app.core.config import settings
    
    delegation_service = DelegationService(db)
    
    # MVP: Load agent registry from settings or database
    # Production: Would use proper registry service
    agent_registry = getattr(settings, 'AGENT_REGISTRY', {})
    
    return AgentSessionService(
        db_session=db,
        delegation_service=delegation_service,
        jwt_secret=settings.SECRET_KEY,
        agent_registry=agent_registry,
    )


AgentSessionServiceDep = Annotated[
    AgentSessionService,
    Depends(get_agent_session_service)
]


# ─────────────────────────────────────────────────────────────────────────────
# Challenge Endpoint (C1)
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
    """
    Generate a challenge nonce for an agent to sign.
    
    This is Step 5.1 of Sarah's journey: Agent requests challenge.
    """
    try:
        challenge = service.create_challenge(request.agent_id)
        
        logger.info(
            "Created challenge for agent: %s",
            request.agent_id
        )
        
        return AgentChallengeResponse(
            challenge=challenge,
            expires_in=service.CHALLENGE_TTL_SECONDS,
        )
        
    except AgentNotFoundError as e:
        logger.warning(
            "Challenge requested for unknown agent: %s",
            request.agent_id
        )
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
        400: {"model": AgentAuthError, "description": "Invalid signature or expired challenge"},
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
    """
    Verify agent signature and issue Agent Session JWT.
    
    This completes Step 5 of Sarah's journey: Agent Authenticates.
    """
    try:
        session, token = service.verify_and_create_session(
            agent_id=request.agent_id,
            challenge=request.challenge,
            signature=request.signature,
            delegation_id=request.delegation_id,
        )
        
        logger.info(
            "Agent authenticated successfully: %s, session: %s",
            request.agent_id,
            session.id,
        )
        
        return AgentVerifyResponse(
            access_token=token,
            token_type="Bearer",
            expires_in=service.SESSION_TTL_HOURS * 3600,
            session_id=session.id,
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
        
    except InvalidSignatureError as e:
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
```

---

## Acceptance Criteria

### Endpoint Behavior Criteria

- [ ] `POST /api/v1/auth/agent/verify` accepts `agent_id`, `challenge`, `signature`
- [ ] Returns 200 with JWT and session_id for valid signature
- [ ] Returns 400 with `challenge_expired` for expired/missing challenge
- [ ] Returns 400 with `invalid_signature` for failed signature verification
- [ ] Returns 403 with `no_delegation` if agent has no valid delegation
- [ ] Returns 404 with `agent_not_found` for unknown agents
- [ ] Optional `delegation_id` parameter to use specific delegation

### JWT Criteria

- [ ] JWT contains `sub` (agent_id)
- [ ] JWT contains `owner` (delegator email from delegation)
- [ ] JWT contains `delegated_permissions` (from delegation)
- [ ] JWT contains `delegation_id` (reference to delegation)
- [ ] JWT contains `session_id` (unique identifier)
- [ ] JWT contains `exp` (8 hours from issuance)
- [ ] JWT contains `iss` (deeptrail-control)
- [ ] JWT contains `aud` (deeptrail-gateway)

### Integration Criteria

- [ ] Uses `AgentSessionService.verify_and_create_session()` from A8
- [ ] Challenge cleared (single-use) after verification
- [ ] AgentSession persisted to database
- [ ] Endpoint registered at `/api/v1/auth/agent/verify`
- [ ] Proper OpenAPI documentation generated

### Security Criteria

- [ ] Ed25519 signature verified against registered public key
- [ ] Challenge must match issued challenge exactly
- [ ] Expired challenges rejected (5-minute TTL)
- [ ] Single-use: same challenge cannot be used twice
- [ ] Error messages don't leak internal details

### Test Criteria

- [ ] Test successful verification with valid signature
- [ ] Test 400 for invalid signature
- [ ] Test 400 for expired challenge
- [ ] Test 400 for challenge mismatch
- [ ] Test 403 for agent with no delegation
- [ ] Test 404 for unknown agent
- [ ] Test JWT contains required claims
- [ ] Test optional delegation_id parameter
- [ ] All tests pass with `pytest tests/api/test_agent_auth.py`

---

## Test Cases

Add these tests to `deeptrail-control/tests/api/test_agent_auth.py`:

```python
"""Tests for agent verify endpoint (C2)."""

import jwt
import base64
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch, AsyncMock
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.services.agent_session_service import (
    AgentNotFoundError,
    ChallengeExpiredError,
    InvalidSignatureError,
    NoDelegationError,
)


class TestAgentVerify:
    """Tests for POST /api/v1/auth/agent/verify"""
    
    def test_verify_success(self, client, ed25519_keypair):
        """Test successful signature verification and JWT issuance."""
        private_key, public_b64 = ed25519_keypair
        
        # Create a challenge
        challenge = base64.urlsafe_b64encode(b"x" * 32).decode()
        
        # Sign the challenge
        signature_bytes = private_key.sign(challenge.encode('utf-8'))
        signature = base64.urlsafe_b64encode(signature_bytes).decode()
        
        with patch("app.api.v1.endpoints.agent_auth.get_agent_session_service") as mock_get:
            mock_service = MagicMock()
            mock_session = MagicMock()
            mock_session.id = "asess-abc123"
            mock_service.verify_and_create_session.return_value = (
                mock_session,
                "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test-token"
            )
            mock_service.SESSION_TTL_HOURS = 8
            mock_get.return_value = mock_service
            
            response = client.post(
                "/api/v1/auth/agent/verify",
                json={
                    "agent_id": "agent-sdr-001",
                    "challenge": challenge,
                    "signature": signature,
                }
            )
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "Bearer"
        assert data["expires_in"] == 28800  # 8 hours in seconds
        assert data["session_id"] == "asess-abc123"
    
    def test_verify_invalid_signature(self, client):
        """Test 400 for invalid signature."""
        with patch("app.api.v1.endpoints.agent_auth.get_agent_session_service") as mock_get:
            mock_service = MagicMock()
            mock_service.verify_and_create_session.side_effect = InvalidSignatureError(
                "Signature verification failed"
            )
            mock_get.return_value = mock_service
            
            response = client.post(
                "/api/v1/auth/agent/verify",
                json={
                    "agent_id": "agent-sdr-001",
                    "challenge": "test-challenge",
                    "signature": "invalid-signature",
                }
            )
        
        assert response.status_code == 400
        data = response.json()
        assert data["detail"]["error"] == "invalid_signature"
    
    def test_verify_challenge_expired(self, client):
        """Test 400 for expired challenge."""
        with patch("app.api.v1.endpoints.agent_auth.get_agent_session_service") as mock_get:
            mock_service = MagicMock()
            mock_service.verify_and_create_session.side_effect = ChallengeExpiredError(
                "Challenge has expired"
            )
            mock_get.return_value = mock_service
            
            response = client.post(
                "/api/v1/auth/agent/verify",
                json={
                    "agent_id": "agent-sdr-001",
                    "challenge": "expired-challenge",
                    "signature": "some-signature",
                }
            )
        
        assert response.status_code == 400
        data = response.json()
        assert data["detail"]["error"] == "challenge_expired"
    
    def test_verify_no_delegation(self, client):
        """Test 403 when agent has no valid delegation."""
        with patch("app.api.v1.endpoints.agent_auth.get_agent_session_service") as mock_get:
            mock_service = MagicMock()
            mock_service.verify_and_create_session.side_effect = NoDelegationError(
                "No valid delegation found for agent"
            )
            mock_get.return_value = mock_service
            
            response = client.post(
                "/api/v1/auth/agent/verify",
                json={
                    "agent_id": "agent-sdr-001",
                    "challenge": "test-challenge",
                    "signature": "valid-signature",
                }
            )
        
        assert response.status_code == 403
        data = response.json()
        assert data["detail"]["error"] == "no_delegation"
    
    def test_verify_agent_not_found(self, client):
        """Test 404 for unknown agent."""
        with patch("app.api.v1.endpoints.agent_auth.get_agent_session_service") as mock_get:
            mock_service = MagicMock()
            mock_service.verify_and_create_session.side_effect = AgentNotFoundError(
                "Agent 'unknown-agent' not found"
            )
            mock_get.return_value = mock_service
            
            response = client.post(
                "/api/v1/auth/agent/verify",
                json={
                    "agent_id": "unknown-agent",
                    "challenge": "test-challenge",
                    "signature": "some-signature",
                }
            )
        
        assert response.status_code == 404
        data = response.json()
        assert data["detail"]["error"] == "agent_not_found"
    
    def test_verify_with_specific_delegation(self, client, ed25519_keypair):
        """Test verification with specific delegation_id."""
        private_key, _ = ed25519_keypair
        challenge = base64.urlsafe_b64encode(b"y" * 32).decode()
        signature_bytes = private_key.sign(challenge.encode('utf-8'))
        signature = base64.urlsafe_b64encode(signature_bytes).decode()
        
        with patch("app.api.v1.endpoints.agent_auth.get_agent_session_service") as mock_get:
            mock_service = MagicMock()
            mock_session = MagicMock()
            mock_session.id = "asess-specific-del"
            mock_service.verify_and_create_session.return_value = (
                mock_session,
                "test-token"
            )
            mock_service.SESSION_TTL_HOURS = 8
            mock_get.return_value = mock_service
            
            response = client.post(
                "/api/v1/auth/agent/verify",
                json={
                    "agent_id": "agent-sdr-001",
                    "challenge": challenge,
                    "signature": signature,
                    "delegation_id": "del-sarah-sdr-001",
                }
            )
        
        assert response.status_code == 200
        # Verify delegation_id was passed to service
        mock_service.verify_and_create_session.assert_called_once_with(
            agent_id="agent-sdr-001",
            challenge=challenge,
            signature=signature,
            delegation_id="del-sarah-sdr-001",
        )
    
    def test_verify_missing_required_fields(self, client):
        """Test validation error for missing fields."""
        response = client.post(
            "/api/v1/auth/agent/verify",
            json={"agent_id": "agent-sdr-001"}  # Missing challenge and signature
        )
        
        assert response.status_code == 422  # Validation error


class TestFullAuthFlow:
    """Integration test for complete auth flow (challenge + verify)."""
    
    def test_full_auth_flow(self, client, ed25519_keypair):
        """Test complete challenge-response flow."""
        private_key, public_b64 = ed25519_keypair
        agent_id = "agent-sdr-001"
        
        with patch("app.api.v1.endpoints.agent_auth.get_agent_session_service") as mock_get:
            # Setup mock service that tracks state
            mock_service = MagicMock()
            stored_challenge = base64.urlsafe_b64encode(b"z" * 32).decode()
            mock_service.create_challenge.return_value = stored_challenge
            mock_service.CHALLENGE_TTL_SECONDS = 300
            
            def verify_side_effect(agent_id, challenge, signature, delegation_id=None):
                # Verify the challenge matches
                assert challenge == stored_challenge
                mock_session = MagicMock()
                mock_session.id = "asess-full-flow"
                return mock_session, "test-jwt-token"
            
            mock_service.verify_and_create_session.side_effect = verify_side_effect
            mock_service.SESSION_TTL_HOURS = 8
            mock_get.return_value = mock_service
            
            # Step 1: Request challenge
            challenge_response = client.post(
                "/api/v1/auth/agent/challenge",
                json={"agent_id": agent_id}
            )
            assert challenge_response.status_code == 200
            challenge = challenge_response.json()["challenge"]
            
            # Step 2: Sign challenge
            signature_bytes = private_key.sign(challenge.encode('utf-8'))
            signature = base64.urlsafe_b64encode(signature_bytes).decode()
            
            # Step 3: Verify and get JWT
            verify_response = client.post(
                "/api/v1/auth/agent/verify",
                json={
                    "agent_id": agent_id,
                    "challenge": challenge,
                    "signature": signature,
                }
            )
            
            assert verify_response.status_code == 200
            data = verify_response.json()
            assert "access_token" in data
            assert data["session_id"] == "asess-full-flow"


class TestVerifyOpenAPI:
    """Test OpenAPI documentation for verify endpoint."""
    
    def test_openapi_includes_verify(self, client):
        """Test OpenAPI schema includes verify endpoint."""
        response = client.get("/openapi.json")
        
        assert response.status_code == 200
        schema = response.json()
        
        # Check verify endpoint is documented
        assert "/api/v1/auth/agent/verify" in schema["paths"]
        
        verify_path = schema["paths"]["/api/v1/auth/agent/verify"]
        assert "post" in verify_path
        
        # Check response codes are documented
        responses = verify_path["post"]["responses"]
        assert "200" in responses
        assert "400" in responses
        assert "403" in responses
        assert "404" in responses
```

---

## Post-Conditions

After completing this task:

- [ ] `/api/v1/auth/agent/verify` endpoint is operational
- [ ] Agents can complete authentication via challenge-response
- [ ] Agent Session JWTs are issued after successful verification
- [ ] AgentSessions are persisted to database
- [ ] C3 (JWT validation middleware) can validate issued tokens
- [ ] All unit tests pass

---

## References

- **Design Doc Section**: 2.6 Step 5: Agent Authenticates
- **Token Architecture**: Section 4.1 (Three-Layer Token Model - Layer 3)
- **Related Services**: 
  - [WS-A8: AgentSessionService](./WS-A8-agent-session-service.md) - Core service
- **Related Tasks**:
  - [WS-C1: Agent Challenge Endpoint](./WS-C1-agent-challenge-endpoint.md) - First half of auth flow
- **Downstream Tasks**:
  - [WS-C3: JWT Validation Middleware](./WS-C3-jwt-validation-middleware.md) - Uses issued JWT
  - [WS-C5: Permission Filter](./WS-C5-permission-filter.md) - Uses JWT permissions

---

## Notes

- This endpoint completes the agent authentication flow started by C1
- The JWT issued here (Layer 3) is used for all subsequent Gateway requests
- Permissions in JWT are copied from delegation (monotonic attenuation)
- Session TTL (8 hours) is deliberately shorter than delegation TTL (7 days)
- Challenge single-use property ensures replay attack protection
- In production, would add rate limiting to prevent brute-force attacks
