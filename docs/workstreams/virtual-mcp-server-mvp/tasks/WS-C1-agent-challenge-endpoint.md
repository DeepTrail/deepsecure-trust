# Task: WS-C1 Implement Agent Challenge Endpoint

---

## Metadata

| Field | Value |
|-------|-------|
| **Status** | `ready` |
| **Design Doc** | [deepsecure-virtual-mcp-server-mvp.md](../../../design/internal/markdowns/deepsecure-virtual-mcp-server-mvp.md) |
| **Workstream** | WS-C: Auth & Permissions |
| **Dependencies** | A8 (AgentSessionService) |
| **Blocked By** | None (A8 is complete ✅) |
| **Assigned** | - |
| **Created** | February 4, 2026 |
| **Estimated Complexity** | `M` (2-4 hours) |
| **Batch** | 4 |

---

## Validation Mapping

| Mapping | Value |
|---------|-------|
| **Validates Demo** | Demo 3: Delegation Execution, Demo 4: Permission Enforcement |
| **Validates User Journey Step** | Step 5: Agent Authenticates |

---

## Pre-Conditions

Before starting this task, ensure:

- [x] A8 (AgentSessionService) is complete
- [x] A7 (Agent Session model) is complete
- [x] A6 (DelegationService) is complete
- [ ] `deeptrail-control/` service structure exists
- [ ] AgentSessionService can be imported from `app.services`
- [ ] Existing auth router at `app/api/v1/endpoints/auth.py` is available

---

## Task Description

Implement the `/api/v1/auth/agent/challenge` endpoint that generates a cryptographic challenge nonce for Ed25519-based agent authentication. This is the first step in the agent authentication flow from the MVP design.

### Context

From the MVP design (Section 2.6 - Step 5: Agent Authenticates):

```
SDR-Assistant Agent (running somewhere):

1. Agent has Ed25519 keypair from registration

2. Agent authenticates to DeepTrail Control Plane:
   POST /api/v1/auth/agent/challenge
   { "agent_id": "agent-sdr-001" }

   Response: { "challenge": "random-nonce-xyz" }

3. Agent signs challenge with private key
   (Handled by C2: verify endpoint)
```

The endpoint must:
- **Accept agent_id**: Validate the agent exists in the registry
- **Generate Challenge**: Create a cryptographically secure nonce
- **Store with TTL**: Challenge expires after 5 minutes
- **Return Challenge**: Base64url-encoded nonce for agent to sign

### Technical Notes

- Use AgentSessionService.create_challenge() from A8
- Challenge is 256-bit (32 bytes) cryptographically secure random
- Challenge is base64url-encoded for transport
- 5-minute TTL for challenges (configurable)
- Single-use: cleared after verification (handled in C2)

---

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `deeptrail-control/app/api/v1/endpoints/agent_auth.py` | **CREATE** | Agent authentication endpoints |
| `deeptrail-control/app/api/v1/api.py` | **MODIFY** | Register new router |
| `deeptrail-control/app/schemas/agent_auth.py` | **CREATE** | Request/Response schemas |
| `deeptrail-control/app/schemas/__init__.py` | **MODIFY** | Export new schemas |
| `deeptrail-control/tests/api/test_agent_auth.py` | **CREATE** | API endpoint tests |

---

## Implementation Details

### 1. Request/Response Schemas (`app/schemas/agent_auth.py`)

```python
"""Schemas for agent authentication endpoints.

These schemas define the request/response formats for the agent
challenge-response authentication flow (Step 5 of Sarah's journey).
"""

from pydantic import BaseModel, Field


class AgentChallengeRequest(BaseModel):
    """Request to create authentication challenge for an agent.
    
    Example:
        {
            "agent_id": "agent-sdr-001"
        }
    """
    agent_id: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Unique agent identifier",
        examples=["agent-sdr-001"],
    )


class AgentChallengeResponse(BaseModel):
    """Response containing the challenge nonce.
    
    The agent must sign this challenge with their Ed25519 private key
    and submit to the /verify endpoint.
    
    Example:
        {
            "challenge": "dGhpcyBpcyBhIHRlc3QgY2hhbGxlbmdl...",
            "expires_in": 300
        }
    """
    challenge: str = Field(
        ...,
        description="Base64url-encoded challenge nonce (256-bit)",
    )
    expires_in: int = Field(
        default=300,
        description="Seconds until challenge expires",
    )


class AgentVerifyRequest(BaseModel):
    """Request to verify agent's signature and create session.
    
    Example:
        {
            "agent_id": "agent-sdr-001",
            "challenge": "dGhpcyBpcyBhIHRlc3QgY2hhbGxlbmdl...",
            "signature": "c2lnbmF0dXJlLW9mLWNoYWxsZW5nZQ..."
        }
    """
    agent_id: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Unique agent identifier",
    )
    challenge: str = Field(
        ...,
        description="The challenge nonce that was signed",
    )
    signature: str = Field(
        ...,
        description="Base64url-encoded Ed25519 signature of the challenge",
    )
    delegation_id: str | None = Field(
        default=None,
        description="Optional specific delegation to use (else uses latest valid)",
    )


class AgentVerifyResponse(BaseModel):
    """Response containing the Agent Session JWT.
    
    Example:
        {
            "access_token": "eyJhbGciOiJIUzI1NiIs...",
            "token_type": "Bearer",
            "expires_in": 28800,
            "session_id": "asess-abc123def456"
        }
    """
    access_token: str = Field(
        ...,
        description="Agent Session JWT (Layer 3)",
    )
    token_type: str = Field(
        default="Bearer",
        description="Token type for Authorization header",
    )
    expires_in: int = Field(
        default=28800,  # 8 hours
        description="Seconds until token expires",
    )
    session_id: str = Field(
        ...,
        description="Agent session identifier",
    )


class AgentAuthError(BaseModel):
    """Error response for agent authentication failures.
    
    Example:
        {
            "error": "agent_not_found",
            "message": "Agent 'agent-unknown' not found in registry"
        }
    """
    error: str = Field(
        ...,
        description="Error code",
    )
    message: str = Field(
        ...,
        description="Human-readable error message",
    )
```

### 2. Agent Auth Endpoint (`app/api/v1/endpoints/agent_auth.py`)

```python
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
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.agent_auth import (
    AgentChallengeRequest,
    AgentChallengeResponse,
    AgentAuthError,
)
from app.services.agent_session_service import (
    AgentSessionService,
    AgentNotFoundError,
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
    """
    Generate a challenge nonce for an agent to sign.
    
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
```

### 3. Update API Router (`app/api/v1/api.py`)

```python
# Add to app/api/v1/api.py

from app.api.v1.endpoints import agent_auth

# Add this line with other router includes:
api_router.include_router(
    agent_auth.router,
    prefix="/auth/agent",
    tags=["agent-auth"],
)
```

### 4. Update Schemas Init (`app/schemas/__init__.py`)

```python
# Add to app/schemas/__init__.py

from .agent_auth import (
    AgentChallengeRequest,
    AgentChallengeResponse,
    AgentVerifyRequest,
    AgentVerifyResponse,
    AgentAuthError,
)

__all__ = [
    # ... existing exports ...
    "AgentChallengeRequest",
    "AgentChallengeResponse",
    "AgentVerifyRequest",
    "AgentVerifyResponse",
    "AgentAuthError",
]
```

---

## Acceptance Criteria

### Endpoint Behavior Criteria

- [ ] `POST /api/v1/auth/agent/challenge` accepts `agent_id` in request body
- [ ] Returns 200 with challenge nonce for registered agents
- [ ] Returns 404 with error details for unknown agents
- [ ] Challenge is base64url-encoded 256-bit random nonce
- [ ] Response includes `expires_in` (300 seconds)

### Integration Criteria

- [ ] Uses AgentSessionService.create_challenge() from A8
- [ ] Agent registry loaded from config or database
- [ ] JWT secret from settings (same as other auth)
- [ ] Endpoint registered at `/api/v1/auth/agent/challenge`
- [ ] Proper OpenAPI documentation generated

### Security Criteria

- [ ] Challenge is cryptographically secure (256-bit random)
- [ ] Challenge stored with 5-minute TTL
- [ ] No authentication required for challenge endpoint (agent proves identity via signature)
- [ ] Proper error handling without leaking internal details

### Test Criteria

- [ ] Test successful challenge creation for registered agent
- [ ] Test 404 for unknown agent
- [ ] Test challenge format (base64url, proper length)
- [ ] Test challenge TTL in response
- [ ] All tests pass with `pytest tests/api/test_agent_auth.py`

---

## Test Cases

Create `deeptrail-control/tests/api/test_agent_auth.py`:

```python
"""Tests for agent authentication endpoints."""

import pytest
import base64
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.main import app
from app.services.agent_session_service import AgentNotFoundError


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def ed25519_keypair():
    """Generate Ed25519 keypair for testing."""
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    public_bytes = public_key.public_bytes_raw()
    public_b64 = base64.urlsafe_b64encode(public_bytes).decode()
    return private_key, public_b64


class TestAgentChallenge:
    """Tests for POST /api/v1/auth/agent/challenge"""
    
    def test_create_challenge_success(self, client, ed25519_keypair):
        """Test successful challenge creation."""
        _, public_b64 = ed25519_keypair
        
        with patch("app.api.v1.endpoints.agent_auth.get_agent_session_service") as mock_get:
            mock_service = MagicMock()
            mock_service.create_challenge.return_value = "dGVzdC1jaGFsbGVuZ2UtYWJjMTIz"
            mock_service.CHALLENGE_TTL_SECONDS = 300
            mock_get.return_value = mock_service
            
            response = client.post(
                "/api/v1/auth/agent/challenge",
                json={"agent_id": "agent-sdr-001"}
            )
        
        assert response.status_code == 200
        data = response.json()
        assert "challenge" in data
        assert data["expires_in"] == 300
    
    def test_create_challenge_agent_not_found(self, client):
        """Test 404 for unknown agent."""
        with patch("app.api.v1.endpoints.agent_auth.get_agent_session_service") as mock_get:
            mock_service = MagicMock()
            mock_service.create_challenge.side_effect = AgentNotFoundError(
                "Agent 'unknown-agent' not found in registry"
            )
            mock_get.return_value = mock_service
            
            response = client.post(
                "/api/v1/auth/agent/challenge",
                json={"agent_id": "unknown-agent"}
            )
        
        assert response.status_code == 404
        data = response.json()
        assert data["detail"]["error"] == "agent_not_found"
    
    def test_challenge_format(self, client):
        """Test challenge is valid base64url."""
        with patch("app.api.v1.endpoints.agent_auth.get_agent_session_service") as mock_get:
            # Generate a real challenge
            challenge_bytes = b"x" * 32  # 256-bit
            challenge_b64 = base64.urlsafe_b64encode(challenge_bytes).decode()
            
            mock_service = MagicMock()
            mock_service.create_challenge.return_value = challenge_b64
            mock_service.CHALLENGE_TTL_SECONDS = 300
            mock_get.return_value = mock_service
            
            response = client.post(
                "/api/v1/auth/agent/challenge",
                json={"agent_id": "agent-sdr-001"}
            )
        
        assert response.status_code == 200
        challenge = response.json()["challenge"]
        
        # Verify it's valid base64url
        decoded = base64.urlsafe_b64decode(challenge)
        assert len(decoded) == 32  # 256 bits
    
    def test_challenge_missing_agent_id(self, client):
        """Test validation error for missing agent_id."""
        response = client.post(
            "/api/v1/auth/agent/challenge",
            json={}
        )
        
        assert response.status_code == 422  # Validation error
    
    def test_challenge_empty_agent_id(self, client):
        """Test validation error for empty agent_id."""
        response = client.post(
            "/api/v1/auth/agent/challenge",
            json={"agent_id": ""}
        )
        
        assert response.status_code == 422  # Validation error


class TestOpenAPIDocumentation:
    """Test OpenAPI documentation is generated."""
    
    def test_openapi_includes_agent_auth(self, client):
        """Test OpenAPI schema includes agent auth endpoints."""
        response = client.get("/openapi.json")
        
        assert response.status_code == 200
        schema = response.json()
        
        # Check endpoint is documented
        assert "/api/v1/auth/agent/challenge" in schema["paths"]
        
        # Check request body schema
        challenge_path = schema["paths"]["/api/v1/auth/agent/challenge"]
        assert "post" in challenge_path
        assert "requestBody" in challenge_path["post"]
```

---

## Post-Conditions

After completing this task:

- [ ] `/api/v1/auth/agent/challenge` endpoint is operational
- [ ] Agents can request authentication challenges
- [ ] Challenges are stored with 5-minute TTL
- [ ] C2 (verify endpoint) can use the stored challenge
- [ ] All unit tests pass

---

## References

- **Design Doc Section**: 2.6 Step 5: Agent Authenticates
- **Token Architecture**: Section 4.1 (Three-Layer Token Model - Layer 3)
- **Related Services**: 
  - [WS-A8: AgentSessionService](./WS-A8-agent-session-service.md) - Core service
- **Downstream Tasks**:
  - [WS-C2: Agent Verify Endpoint](./WS-C2-agent-verify-endpoint.md) - Completes auth flow
  - [WS-C3: JWT Validation Middleware](./WS-C3-jwt-validation-middleware.md) - Uses issued JWT

---

## Notes

- The existing `/challenge` endpoint in `auth.py` is for general agent auth; this new endpoint is specifically for Virtual MCP Server MVP flow
- Challenge endpoint doesn't require authentication (agent proves identity via signature in verify step)
- MVP uses in-memory challenge storage; production should use Redis with TTL
- Agent registry can be loaded from settings or database in MVP
