"""OAuth schemas for authorization flows.

This module defines data classes for OAuth 2.0 authorization flows, including:
- Provider enumeration (Notion, Slack, HubSpot)
- Authorization request/response models
- Token exchange request/response models
- PKCE support for enhanced security
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel


class OAuthProvider(str, Enum):
    """Supported OAuth providers.

    Each provider has different OAuth configurations:
    - NOTION: Requires PKCE (code_challenge)
    - SLACK: Standard OAuth 2.0
    - HUBSPOT: Standard OAuth 2.0
    - GOOGLE: Standard OAuth 2.0 (shared by gdrive, gcalendar, gmail)
    """

    NOTION = "notion"
    SLACK = "slack"
    HUBSPOT = "hubspot"
    GOOGLE = "google"


@dataclass
class OAuthConfig:
    """Provider-specific OAuth configuration.

    Attributes:
        provider: The OAuth provider enum value.
        client_id: OAuth application client ID.
        client_secret: OAuth application client secret.
        authorization_url: URL to redirect users for authorization.
        token_url: URL to exchange authorization code for tokens.
        scopes: Default scopes to request during authorization.
        redirect_uri: Callback URL for OAuth redirect.
        uses_pkce: Whether this provider requires PKCE (RFC 7636).
    """

    provider: OAuthProvider
    client_id: str
    client_secret: str
    authorization_url: str
    token_url: str
    scopes: list[str]
    redirect_uri: str
    uses_pkce: bool = False


@dataclass
class AuthorizationRequest:
    """Request to generate an OAuth authorization URL.

    Attributes:
        provider: The OAuth provider to authorize with.
        user_id: User identifier (for state tracking).
        requested_scopes: Optional custom scopes (uses defaults if None).
    """

    provider: OAuthProvider
    user_id: str
    requested_scopes: Optional[list[str]] = None


@dataclass
class AuthorizationResponse:
    """Response containing the OAuth authorization URL.

    Attributes:
        authorization_url: Full URL to redirect user to.
        state: State token for CSRF protection.
        code_verifier: PKCE code verifier (for providers that use PKCE).
    """

    authorization_url: str
    state: str
    code_verifier: Optional[str] = None


@dataclass
class TokenExchangeRequest:
    """Request to exchange authorization code for tokens.

    Attributes:
        provider: The OAuth provider.
        authorization_code: Code received from OAuth callback.
        state: State token from authorization request.
        code_verifier: PKCE code verifier (for PKCE flows).
    """

    provider: OAuthProvider
    authorization_code: str
    state: str
    code_verifier: Optional[str] = None


@dataclass
class OAuthTokenResponse:
    """Response containing OAuth tokens.

    Attributes:
        access_token: Token for API access.
        token_type: Token type (usually "Bearer").
        expires_in: Seconds until access_token expires (None if no expiry).
        refresh_token: Token for refreshing access (None if not provided).
        scope: Granted scopes (space-separated string).
    """

    access_token: str
    token_type: str
    expires_in: Optional[int] = None
    refresh_token: Optional[str] = None
    scope: Optional[str] = None


@dataclass
class TokenRefreshRequest:
    """Request to refresh OAuth tokens.

    Attributes:
        provider: The OAuth provider.
        refresh_token: The refresh token from initial authorization.
        user_id: User identifier (for logging/tracking).
    """

    provider: OAuthProvider
    refresh_token: str
    user_id: str


@dataclass
class OAuthState:
    """Internal state for tracking OAuth flows.

    Stored server-side to validate callback requests and prevent CSRF.

    Attributes:
        user_id: User who initiated the authorization.
        provider: The OAuth provider.
        nonce: Random value for additional entropy.
        created_at: When the state was created.
        expires_at: When the state expires.
        code_verifier: PKCE code verifier (stored for token exchange).
    """

    user_id: str
    provider: str
    nonce: str
    created_at: datetime
    expires_at: datetime
    code_verifier: Optional[str] = None


# =============================================================================
# Pydantic API Response Schemas (for REST endpoints)
# =============================================================================


class AuthorizeApiResponse(BaseModel):
    """Response for GET /api/v1/oauth/{service_id}/authorize."""

    authorization_url: str
    state: str


class CallbackApiResponse(BaseModel):
    """Response for GET /api/v1/oauth/{service_id}/callback."""

    success: bool
    service_id: str
    connected: bool
    scopes_granted: list[str]


class RefreshApiResponse(BaseModel):
    """Response for POST /api/v1/oauth/{service_id}/refresh."""

    refreshed: bool
    expires_in: Optional[int] = None


class OAuthErrorResponse(BaseModel):
    """Standard OAuth error response."""

    error: str
    message: Optional[str] = None
