"""Vault token schemas for OAuth token retrieval.

These schemas are used for the token retrieval endpoint that allows
the Gateway to fetch OAuth access tokens for connected services.

Security Note:
    The response schema intentionally EXCLUDES refresh_token.
    Refresh tokens are never exposed to agents.
"""

from datetime import datetime
from pydantic import BaseModel, Field
from typing import List, Optional


class TokenResponse(BaseModel):
    """Response schema for token retrieval.

    Returns the OAuth access token and metadata for a connected service.

    Attributes:
        service_id: The service identifier (e.g., 'notion', 'slack').
        access_token: The OAuth access token for API calls.
        token_type: Token type, typically "bearer".
        scopes_granted: List of granted scopes (optional).
        expires_at: ISO timestamp when token expires (optional).

    Security:
        - Does NOT include refresh_token (security requirement)
        - Agents should never see refresh tokens
    """

    service_id: str = Field(..., description="Service identifier")
    access_token: str = Field(..., description="OAuth access token")
    token_type: str = Field(default="bearer", description="Token type")
    scopes_granted: Optional[List[str]] = Field(
        default=None,
        description="List of granted scopes"
    )
    expires_at: Optional[str] = Field(
        default=None,
        description="ISO timestamp when token expires"
    )


class TokenErrorResponse(BaseModel):
    """Error response schema for token retrieval.

    Used for 401, 403, and 404 error responses.

    Attributes:
        error: Error code (unauthorized, forbidden, not_found).
        message: Human-readable error message.
    """

    error: str = Field(..., description="Error code")
    message: str = Field(..., description="Human-readable error message")


class TokenRefreshRequest(BaseModel):
    """Request schema for token refresh.

    Attributes:
        force: If True, refresh even if token is not expired.
               If False, only refresh if token is expired or expiring soon.
    """

    force: bool = Field(
        default=False,
        description="Force refresh even if token is not expired"
    )


class TokenRefreshResponse(BaseModel):
    """Response schema for token refresh.

    Returns the OAuth access token after refresh attempt.
    Never includes refresh_token for security.

    Attributes:
        access_token: The OAuth access token for API calls.
        token_type: Token type, typically "bearer".
        expires_in: Seconds until token expiration (optional).
        refreshed: True if token was actually refreshed, False if still valid.
        message: Human-readable status message.
    """

    access_token: str = Field(..., description="OAuth access token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: Optional[int] = Field(
        default=None,
        description="Seconds until token expiration"
    )
    refreshed: bool = Field(..., description="Whether token was actually refreshed")
    message: str = Field(..., description="Status message")
