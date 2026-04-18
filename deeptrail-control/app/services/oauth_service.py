"""OAuth service for handling OAuth 2.0 authorization flows.

This service manages the complete OAuth lifecycle for external services:
- Authorization URL generation with state/PKCE
- Token exchange (code → tokens)
- Token refresh
- State management for CSRF protection

Supported providers:
- Notion (requires PKCE)
- Slack (standard OAuth 2.0)
- HubSpot (standard OAuth 2.0)

Security features:
- State tokens are cryptographically random (32 bytes)
- State tokens are single-use (consumed on validation)
- PKCE code_verifier is 43-128 characters (RFC 7636)
- Client secrets read from environment variables
"""

import base64
import hashlib
import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urlencode

import httpx

from app.schemas.oauth import (
    AuthorizationRequest,
    AuthorizationResponse,
    OAuthConfig,
    OAuthProvider,
    OAuthState,
    OAuthTokenResponse,
    TokenExchangeRequest,
    TokenRefreshRequest,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Exceptions
# ============================================================================


class OAuthError(Exception):
    """Base exception for OAuth operations."""

    pass


class OAuthConfigError(OAuthError):
    """Raised when OAuth configuration is missing or invalid."""

    pass


class OAuthStateError(OAuthError):
    """Raised when state validation fails."""

    pass


class OAuthExchangeError(OAuthError):
    """Raised when token exchange fails."""

    pass


class OAuthRefreshError(OAuthError):
    """Raised when token refresh fails."""

    pass


# ============================================================================
# Provider Configuration
# ============================================================================


# Default scopes for each provider
DEFAULT_SCOPES = {
    OAuthProvider.NOTION: [],  # Notion uses integration-level permissions
    OAuthProvider.SLACK: ["chat:write", "channels:read", "users:read"],
    OAuthProvider.HUBSPOT: ["crm.objects.contacts.read", "crm.objects.contacts.write"],
    OAuthProvider.GOOGLE: [],  # Service-specific scopes used instead
}

# Service-specific default scopes (for providers shared by multiple services)
SERVICE_DEFAULT_SCOPES = {
    "gdrive": ["https://www.googleapis.com/auth/drive.readonly"],
    "gcalendar": ["https://www.googleapis.com/auth/calendar.readonly"],
    "gmail": ["https://www.googleapis.com/auth/gmail.readonly"],
}

# Provider OAuth URLs
PROVIDER_URLS = {
    OAuthProvider.NOTION: {
        "authorization_url": "https://api.notion.com/v1/oauth/authorize",
        "token_url": "https://api.notion.com/v1/oauth/token",
        "uses_pkce": True,
    },
    OAuthProvider.SLACK: {
        "authorization_url": "https://slack.com/oauth/v2/authorize",
        "token_url": "https://slack.com/api/oauth.v2.access",
        "uses_pkce": False,
    },
    OAuthProvider.HUBSPOT: {
        "authorization_url": "https://app.hubspot.com/oauth/authorize",
        "token_url": "https://api.hubapi.com/oauth/v1/token",
        "uses_pkce": False,
    },
    OAuthProvider.GOOGLE: {
        "authorization_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "uses_pkce": False,
    },
}


# ============================================================================
# OAuth Service
# ============================================================================


class OAuthService:
    """Service for managing OAuth 2.0 authorization flows.

    Handles:
    - Authorization URL generation with state/PKCE
    - Token exchange (code → tokens)
    - Token refresh
    - State validation for CSRF protection

    Example:
        service = OAuthService()

        # Generate authorization URL
        request = AuthorizationRequest(
            provider=OAuthProvider.NOTION,
            user_id="user-123"
        )
        response = await service.get_authorization_url(request)
        # response.authorization_url → redirect user here
        # response.state → returned in callback
        # response.code_verifier → store for token exchange (PKCE)

        # After callback, exchange code for tokens
        exchange_request = TokenExchangeRequest(
            provider=OAuthProvider.NOTION,
            authorization_code="code_from_callback",
            state=response.state,
            code_verifier=response.code_verifier
        )
        tokens = await service.exchange_code_for_tokens(exchange_request)
    """

    # Environment variable names
    ENV_STATE_TTL = "OAUTH_STATE_TTL_SECONDS"
    ENV_REDIRECT_BASE = "OAUTH_REDIRECT_BASE_URL"

    # Default state TTL: 10 minutes
    DEFAULT_STATE_TTL_SECONDS = 600

    def __init__(self):
        """Initialize the OAuth service.

        State is stored in-memory for MVP. In production, this would use
        Redis or similar for distributed state management.
        """
        self._pending_states: dict[str, OAuthState] = {}
        self._http_client: Optional[httpx.AsyncClient] = None

    async def _get_http_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client for API calls."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=30.0)
        return self._http_client

    async def close(self) -> None:
        """Close HTTP client."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None

    # ========================================================================
    # Public Methods
    # ========================================================================

    def get_provider_config(
        self, provider: OAuthProvider, service_id: str | None = None
    ) -> OAuthConfig:
        """Get OAuth configuration for a provider.

        Reads client credentials from environment variables.

        Args:
            provider: The OAuth provider.
            service_id: Optional service identifier for multi-service providers
                (e.g., "gdrive" for Google). Used for service-specific redirect
                URIs and scopes.

        Returns:
            OAuthConfig with provider-specific settings.

        Raises:
            OAuthConfigError: If required environment variables are missing.
        """
        provider_name = provider.value.upper()

        # Required environment variables
        client_id = os.environ.get(f"{provider_name}_CLIENT_ID")
        client_secret = os.environ.get(f"{provider_name}_CLIENT_SECRET")
        redirect_base = os.environ.get(self.ENV_REDIRECT_BASE)

        # Validate required config
        missing = []
        if not client_id:
            missing.append(f"{provider_name}_CLIENT_ID")
        if not client_secret:
            missing.append(f"{provider_name}_CLIENT_SECRET")
        if not redirect_base:
            missing.append(self.ENV_REDIRECT_BASE)

        if missing:
            raise OAuthConfigError(
                f"Missing required environment variables: {', '.join(missing)}"
            )

        # Use service_id for redirect URI when provided (e.g., "gdrive" not "google")
        redirect_path = service_id or provider.value
        redirect_uri = f"{redirect_base.rstrip('/')}/api/v1/oauth/{redirect_path}/callback"

        # Get provider-specific URLs
        urls = PROVIDER_URLS[provider]

        # Use service-specific scopes if available, otherwise provider defaults
        scopes = (
            SERVICE_DEFAULT_SCOPES.get(service_id, [])
            if service_id
            else DEFAULT_SCOPES.get(provider, [])
        )

        return OAuthConfig(
            provider=provider,
            client_id=client_id,
            client_secret=client_secret,
            authorization_url=urls["authorization_url"],
            token_url=urls["token_url"],
            scopes=scopes,
            redirect_uri=redirect_uri,
            uses_pkce=urls["uses_pkce"],
        )

    async def get_authorization_url(
        self, request: AuthorizationRequest, service_id: str | None = None
    ) -> AuthorizationResponse:
        """Generate OAuth authorization URL.

        Creates a secure state token and builds the authorization URL
        with all required parameters. For providers that use PKCE,
        generates and includes the code_challenge.

        Args:
            request: Authorization request with provider and user info.
            service_id: Optional service identifier for multi-service providers.

        Returns:
            AuthorizationResponse containing:
            - authorization_url: URL to redirect user to
            - state: State token for CSRF protection
            - code_verifier: PKCE verifier (if applicable)

        Raises:
            OAuthConfigError: If provider configuration is missing.
        """
        config = self.get_provider_config(request.provider, service_id=service_id)

        # Generate PKCE pair if needed
        code_verifier = None
        code_challenge = None
        if config.uses_pkce:
            code_verifier, code_challenge = self._generate_pkce_pair()

        # Generate and store state
        state_token = await self._store_state(
            user_id=request.user_id,
            provider=request.provider.value,
            code_verifier=code_verifier,
        )

        # Build authorization URL
        scopes = request.requested_scopes or config.scopes
        params = {
            "client_id": config.client_id,
            "redirect_uri": config.redirect_uri,
            "response_type": "code",
            "state": state_token,
        }

        # Add scopes (Notion uses different parameter name)
        if request.provider == OAuthProvider.NOTION:
            # Notion doesn't use scopes in OAuth URL
            params["owner"] = "user"
        elif scopes:
            params["scope"] = " ".join(scopes)

        # Google-specific: request offline access for refresh tokens
        if request.provider == OAuthProvider.GOOGLE:
            params["access_type"] = "offline"
            params["prompt"] = "consent"

        # Add PKCE parameters
        if code_challenge:
            params["code_challenge"] = code_challenge
            params["code_challenge_method"] = "S256"

        authorization_url = f"{config.authorization_url}?{urlencode(params)}"

        logger.info(
            "Generated authorization URL: provider=%s user=%s",
            request.provider.value,
            request.user_id,
        )

        return AuthorizationResponse(
            authorization_url=authorization_url,
            state=state_token,
            code_verifier=code_verifier,
        )

    async def exchange_code_for_tokens(
        self, request: TokenExchangeRequest, service_id: str | None = None
    ) -> OAuthTokenResponse:
        """Exchange authorization code for OAuth tokens.

        Validates the state token, then exchanges the authorization code
        for access/refresh tokens with the provider.

        Args:
            request: Token exchange request with code and state.

        Returns:
            OAuthTokenResponse containing access_token, refresh_token, etc.

        Raises:
            OAuthStateError: If state validation fails.
            OAuthExchangeError: If token exchange fails.
            OAuthConfigError: If provider configuration is missing.
        """
        # Validate and consume state
        state = await self._validate_and_consume_state(request.state)

        # Verify provider matches
        if state.provider != request.provider.value:
            raise OAuthStateError(
                f"Provider mismatch: expected {state.provider}, got {request.provider.value}"
            )

        # Get provider config
        config = self.get_provider_config(request.provider, service_id=service_id)

        # Build token request
        data = {
            "grant_type": "authorization_code",
            "code": request.authorization_code,
            "redirect_uri": config.redirect_uri,
        }

        # Add client credentials (method varies by provider)
        if request.provider == OAuthProvider.NOTION:
            # Notion uses Basic auth
            auth = (config.client_id, config.client_secret)
            headers = {"Content-Type": "application/json"}
            # Notion expects JSON body
            json_data = data
            data = None
        else:
            # Slack and HubSpot use POST body
            auth = None
            headers = {"Content-Type": "application/x-www-form-urlencoded"}
            data["client_id"] = config.client_id
            data["client_secret"] = config.client_secret
            json_data = None

        # Add PKCE code_verifier
        code_verifier = request.code_verifier or state.code_verifier
        if code_verifier:
            if json_data:
                json_data["code_verifier"] = code_verifier
            else:
                data["code_verifier"] = code_verifier

        # Make token request
        client = await self._get_http_client()
        try:
            if json_data:
                response = await client.post(
                    config.token_url,
                    json=json_data,
                    auth=auth,
                    headers=headers,
                )
            else:
                response = await client.post(
                    config.token_url,
                    data=data,
                    auth=auth,
                    headers=headers,
                )

            if response.status_code != 200:
                error_detail = response.text[:200]  # Truncate for logging
                logger.error(
                    "Token exchange failed: provider=%s status=%d error=%s",
                    request.provider.value,
                    response.status_code,
                    error_detail,
                )
                raise OAuthExchangeError(
                    f"Token exchange failed with status {response.status_code}"
                )

            token_data = response.json()

            # Normalize response (providers have different formats)
            return self._normalize_token_response(request.provider, token_data)

        except httpx.RequestError as e:
            logger.error(
                "Token exchange HTTP error: provider=%s error=%s",
                request.provider.value,
                str(e),
            )
            raise OAuthExchangeError(f"HTTP error during token exchange: {e}") from e

    async def refresh_tokens(
        self, request: TokenRefreshRequest, service_id: str | None = None
    ) -> OAuthTokenResponse:
        """Refresh OAuth tokens using a refresh token.

        Args:
            request: Token refresh request with refresh_token.

        Returns:
            OAuthTokenResponse containing new access_token and possibly new refresh_token.

        Raises:
            OAuthRefreshError: If token refresh fails.
            OAuthConfigError: If provider configuration is missing.
        """
        config = self.get_provider_config(request.provider, service_id=service_id)

        # Build refresh request
        data = {
            "grant_type": "refresh_token",
            "refresh_token": request.refresh_token,
        }

        # Add client credentials
        if request.provider == OAuthProvider.NOTION:
            auth = (config.client_id, config.client_secret)
            headers = {"Content-Type": "application/json"}
            json_data = data
            data = None
        else:
            auth = None
            headers = {"Content-Type": "application/x-www-form-urlencoded"}
            data["client_id"] = config.client_id
            data["client_secret"] = config.client_secret
            json_data = None

        # Make refresh request
        client = await self._get_http_client()
        try:
            if json_data:
                response = await client.post(
                    config.token_url,
                    json=json_data,
                    auth=auth,
                    headers=headers,
                )
            else:
                response = await client.post(
                    config.token_url,
                    data=data,
                    auth=auth,
                    headers=headers,
                )

            if response.status_code != 200:
                error_detail = response.text[:200]
                logger.error(
                    "Token refresh failed: provider=%s user=%s status=%d error=%s",
                    request.provider.value,
                    request.user_id,
                    response.status_code,
                    error_detail,
                )
                raise OAuthRefreshError(
                    f"Token refresh failed with status {response.status_code}"
                )

            token_data = response.json()

            logger.info(
                "Token refreshed: provider=%s user=%s",
                request.provider.value,
                request.user_id,
            )

            return self._normalize_token_response(request.provider, token_data)

        except httpx.RequestError as e:
            logger.error(
                "Token refresh HTTP error: provider=%s user=%s error=%s",
                request.provider.value,
                request.user_id,
                str(e),
            )
            raise OAuthRefreshError(f"HTTP error during token refresh: {e}") from e

    # ========================================================================
    # PKCE Implementation
    # ========================================================================

    def _generate_pkce_pair(self) -> tuple[str, str]:
        """Generate PKCE code_verifier and code_challenge.

        Per RFC 7636:
        - code_verifier: 43-128 characters, unreserved URI characters
        - code_challenge: SHA256 hash of verifier, base64url encoded

        Returns:
            Tuple of (code_verifier, code_challenge).
        """
        # Generate verifier (43-128 chars, we use 64 for good entropy)
        code_verifier = secrets.token_urlsafe(48)  # 64 chars after encoding

        # Generate challenge
        challenge_bytes = hashlib.sha256(code_verifier.encode("ascii")).digest()
        code_challenge = (
            base64.urlsafe_b64encode(challenge_bytes).rstrip(b"=").decode("ascii")
        )

        return code_verifier, code_challenge

    # ========================================================================
    # State Management
    # ========================================================================

    async def _store_state(
        self,
        user_id: str,
        provider: str,
        code_verifier: Optional[str] = None,
    ) -> str:
        """Generate and store a state token.

        Args:
            user_id: User initiating authorization.
            provider: OAuth provider name.
            code_verifier: PKCE verifier to store with state.

        Returns:
            The state token (to include in authorization URL).
        """
        state_token = secrets.token_urlsafe(32)
        ttl = int(os.environ.get(self.ENV_STATE_TTL, self.DEFAULT_STATE_TTL_SECONDS))
        now = datetime.now(timezone.utc)

        state = OAuthState(
            user_id=user_id,
            provider=provider,
            nonce=secrets.token_hex(16),
            created_at=now,
            expires_at=now + timedelta(seconds=ttl),
            code_verifier=code_verifier,
        )

        self._pending_states[state_token] = state

        logger.debug(
            "Stored OAuth state: user=%s provider=%s expires_at=%s",
            user_id,
            provider,
            state.expires_at.isoformat(),
        )

        return state_token

    async def _validate_and_consume_state(self, state_token: str) -> OAuthState:
        """Validate and consume a state token.

        State tokens are single-use: validated once, then deleted.

        Args:
            state_token: The state token from callback.

        Returns:
            The OAuthState associated with the token.

        Raises:
            OAuthStateError: If token is invalid, expired, or not found.
        """
        if state_token not in self._pending_states:
            logger.warning("Invalid OAuth state token: not found")
            raise OAuthStateError("Invalid or expired state token")

        # Pop state (single-use)
        state = self._pending_states.pop(state_token)

        # Check expiration
        if datetime.now(timezone.utc) > state.expires_at:
            logger.warning(
                "Expired OAuth state token: user=%s provider=%s",
                state.user_id,
                state.provider,
            )
            raise OAuthStateError("State token expired")

        logger.debug(
            "Validated OAuth state: user=%s provider=%s",
            state.user_id,
            state.provider,
        )

        return state

    def get_pending_state(self, state_token: str) -> Optional[OAuthState]:
        """Get pending state without consuming it (for testing/debugging).

        Args:
            state_token: The state token to look up.

        Returns:
            The OAuthState if found, None otherwise.
        """
        return self._pending_states.get(state_token)

    def clear_expired_states(self) -> int:
        """Remove all expired states from memory.

        Returns:
            Number of states cleared.
        """
        now = datetime.now(timezone.utc)
        expired = [
            token
            for token, state in self._pending_states.items()
            if state.expires_at <= now
        ]

        for token in expired:
            del self._pending_states[token]

        if expired:
            logger.debug("Cleared %d expired OAuth states", len(expired))

        return len(expired)

    # ========================================================================
    # Response Normalization
    # ========================================================================

    def _normalize_token_response(
        self, provider: OAuthProvider, data: dict
    ) -> OAuthTokenResponse:
        """Normalize provider-specific token response to common format.

        Different providers return different field names:
        - Notion: access_token, token_type, bot_id, workspace_id
        - Slack: access_token, token_type, scope, bot_user_id, etc.
        - HubSpot: access_token, token_type, expires_in, refresh_token

        Args:
            provider: The OAuth provider.
            data: Raw response data from provider.

        Returns:
            Normalized OAuthTokenResponse.
        """
        # Slack has nested structure
        if provider == OAuthProvider.SLACK:
            access_token = data.get("access_token") or data.get("authed_user", {}).get(
                "access_token"
            )
            scope = data.get("scope")
        else:
            access_token = data.get("access_token")
            scope = data.get("scope")

        return OAuthTokenResponse(
            access_token=access_token,
            token_type=data.get("token_type", "Bearer"),
            expires_in=data.get("expires_in"),
            refresh_token=data.get("refresh_token"),
            scope=scope,
        )


# ============================================================================
# Service Factory
# ============================================================================


# Global instance for dependency injection
_oauth_service: Optional[OAuthService] = None


def get_oauth_service() -> OAuthService:
    """Get or create the OAuth service singleton.

    Returns:
        OAuthService instance.
    """
    global _oauth_service
    if _oauth_service is None:
        _oauth_service = OAuthService()
    return _oauth_service
