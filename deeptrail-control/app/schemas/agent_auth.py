"""Schemas for agent authentication endpoints.

These schemas define the request/response formats for the agent
challenge-response authentication flow (Step 5 of Sarah's journey).

This is part of WS-C: Auth & Permissions for the Virtual MCP Server MVP.
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
    refresh_token: str | None = Field(
        default=None,
        description="Opaque refresh token for obtaining new access tokens",
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
