"""OIDC Identity Provider abstraction layer.

Defines the OIDCProvider protocol, data models, error hierarchy,
factory function, and user provisioning from OIDC claims.

Design: Option C — generic OIDC abstraction with Keycloak as dev-time IdP,
swappable to Okta/Entra in production via IDP_PROVIDER env var.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Protocol

from app.core.idp_config import IdPConfig, IdPProviderType

logger = logging.getLogger(__name__)


# ============================================================================
# Data Models
# ============================================================================


@dataclass
class OIDCTokens:
    """Token set returned by OIDC code exchange."""

    id_token: str
    access_token: str
    refresh_token: Optional[str] = None
    expires_at: Optional[datetime] = None
    token_type: str = "Bearer"


@dataclass
class OIDCClaims:
    """Validated claims from an OIDC ID token."""

    sub: str
    email: str
    email_verified: bool = False
    name: Optional[str] = None
    given_name: Optional[str] = None
    family_name: Optional[str] = None
    groups: list[str] | None = None
    roles: list[str] | None = None
    issuer: Optional[str] = None
    audience: Optional[str] = None
    issued_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    raw_claims: dict | None = field(default=None, repr=False)


@dataclass
class UserInfo:
    """User profile information from the IdP userinfo endpoint."""

    sub: str
    email: str
    name: Optional[str] = None
    groups: list[str] | None = None
    roles: list[str] | None = None
    organization_id: Optional[str] = None


# ============================================================================
# Error Hierarchy
# ============================================================================


class OIDCError(Exception):
    """Base exception for OIDC operations."""

    def __init__(
        self,
        message: str,
        error_code: str | None = None,
        details: dict | None = None,
    ):
        super().__init__(message)
        self.error_code = error_code
        self.details = details or {}


class OIDCTokenExpiredError(OIDCError):
    """Token has expired."""

    pass


class OIDCTokenInvalidError(OIDCError):
    """Token signature or claims validation failed."""

    pass


class OIDCProviderUnavailableError(OIDCError):
    """IdP is unreachable or returned an error."""

    pass


# ============================================================================
# OIDCProvider Protocol
# ============================================================================


class OIDCProvider(Protocol):
    """Protocol defining the contract for OIDC identity providers.

    Implementations must support the Authorization Code flow with PKCE.
    Dev: KeycloakProvider (local docker container)
    Prod: OktaProvider, EntraIDProvider (SaaS)
    """

    async def get_authorization_url(
        self,
        state: str,
        redirect_uri: str,
        scopes: list[str] | None = None,
    ) -> str:
        """Generate the IdP authorization URL for the OIDC Authorization Code flow.

        Args:
            state: CSRF protection state parameter (opaque, caller-generated).
            redirect_uri: Where the IdP should redirect after authentication.
            scopes: OIDC scopes to request. Defaults to ["openid", "profile", "email"].

        Returns:
            Full authorization URL to redirect the user to.
        """
        ...

    async def exchange_code(
        self,
        code: str,
        redirect_uri: str,
    ) -> OIDCTokens:
        """Exchange an authorization code for tokens.

        Args:
            code: The authorization code from the IdP callback.
            redirect_uri: Must match the redirect_uri used in get_authorization_url.

        Returns:
            OIDCTokens with id_token, access_token, and optional refresh_token.

        Raises:
            OIDCError: If code exchange fails (expired, invalid, etc.).
        """
        ...

    async def validate_token(self, id_token: str) -> OIDCClaims:
        """Validate an OIDC ID token and extract claims.

        Validates signature (JWKS), issuer, audience, and expiration.

        Args:
            id_token: The raw JWT ID token string.

        Returns:
            OIDCClaims with validated, extracted claims.

        Raises:
            OIDCTokenInvalidError: If token validation fails.
            OIDCProviderUnavailableError: If JWKS endpoint is unreachable.
        """
        ...

    async def get_user_info(self, access_token: str) -> UserInfo:
        """Fetch user profile from the IdP's userinfo endpoint.

        Args:
            access_token: A valid OIDC access token.

        Returns:
            UserInfo with user profile data.

        Raises:
            OIDCError: If the userinfo request fails.
        """
        ...

    async def refresh_token(self, refresh_token: str) -> OIDCTokens:
        """Refresh an expired access token using a refresh token.

        Args:
            refresh_token: A valid OIDC refresh token.

        Returns:
            New OIDCTokens with fresh access_token.

        Raises:
            OIDCError: If refresh fails (token revoked, expired, etc.).
        """
        ...

    async def logout_url(
        self,
        id_token_hint: Optional[str] = None,
        post_logout_redirect_uri: Optional[str] = None,
    ) -> str:
        """Generate the IdP logout URL.

        Args:
            id_token_hint: The ID token to hint which session to end.
            post_logout_redirect_uri: Where to redirect after logout.

        Returns:
            Logout URL to redirect the user to.
        """
        ...


# ============================================================================
# Factory
# ============================================================================


def create_oidc_provider(config: IdPConfig | None = None) -> OIDCProvider:
    """Factory to create the configured OIDC provider.

    Args:
        config: IdP configuration. If None, loads from environment.

    Returns:
        An OIDCProvider implementation based on the configured provider type.

    Raises:
        NotImplementedError: If the provider type is not yet implemented (okta, entra).
        ValueError: If the provider type is unknown.
    """
    if config is None:
        config = IdPConfig()

    if config.provider == IdPProviderType.KEYCLOAK:
        from app.services.providers.keycloak import KeycloakProvider

        logger.info(
            "Creating KeycloakProvider: issuer=%s, realm=%s",
            config.issuer_url,
            config.realm,
        )
        return KeycloakProvider(
            issuer_url=config.issuer_url,
            client_id=config.client_id,
            client_secret=config.client_secret,
            realm=config.realm,
        )
    elif config.provider == IdPProviderType.OKTA:
        raise NotImplementedError(
            "OktaProvider not yet implemented. "
            "Use KeycloakProvider with Okta identity brokering."
        )
    elif config.provider == IdPProviderType.ENTRA:
        raise NotImplementedError(
            "EntraIDProvider not yet implemented. "
            "Use KeycloakProvider with Entra identity brokering."
        )
    else:
        raise ValueError(f"Unknown IdP provider: {config.provider}")


# ============================================================================
# User Provisioning
# ============================================================================


_GROUP_TO_ROLE_MAP = {
    "acme-org": "user",
    "admin-org": "admin",
}


async def provision_user_from_claims(claims: OIDCClaims) -> dict:
    """Create or update a user record from OIDC claims.

    Called after successful OIDC authentication. Maps IdP claims
    to DeepSecure's internal user model.

    In the current implementation this operates in-memory. A future
    iteration will persist to PostgreSQL via SQLAlchemy.

    Args:
        claims: Validated OIDC claims from the ID token.

    Returns:
        Dict with user_id, email, is_new_user, and mapped roles.
    """
    mapped_roles: list[str] = list(claims.roles or [])
    for group in claims.groups or []:
        if group in _GROUP_TO_ROLE_MAP:
            role = _GROUP_TO_ROLE_MAP[group]
            if role not in mapped_roles:
                mapped_roles.append(role)

    user_record = _provisioned_users.get(claims.sub)
    is_new = user_record is None

    user_data = {
        "user_id": claims.sub,
        "email": claims.email,
        "name": claims.name or claims.email,
        "roles": mapped_roles,
        "groups": claims.groups or [],
        "organization_id": (claims.groups[0] if claims.groups else None),
        "is_new_user": is_new,
        "idp_issuer": claims.issuer,
        "last_login": datetime.now(tz=None).isoformat(),
    }

    _provisioned_users[claims.sub] = user_data
    logger.info(
        "Provisioned user: sub=%s email=%s is_new=%s",
        claims.sub,
        claims.email,
        is_new,
    )
    return user_data


# In-memory store; replaced by DB in production
_provisioned_users: dict[str, dict] = {}
