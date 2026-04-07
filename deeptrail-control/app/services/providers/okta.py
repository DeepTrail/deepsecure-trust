"""Okta OIDC provider stub.

Placeholder for future enterprise SSO integration via Okta.
In the meantime, use KeycloakProvider with Okta identity brokering
(Keycloak as SSO broker federating to an upstream Okta tenant).
"""

from __future__ import annotations

from typing import Optional

from app.services.idp_service import OIDCClaims, OIDCTokens, UserInfo


class OktaProvider:
    """OIDC provider for Okta — not yet implemented."""

    def __init__(self, **kwargs: object) -> None:
        raise NotImplementedError(
            "OktaProvider is not yet implemented. "
            "Use KeycloakProvider with Okta identity brokering as a bridge."
        )

    async def get_authorization_url(
        self, state: str, redirect_uri: str, scopes: list[str] | None = None
    ) -> str:
        raise NotImplementedError

    async def exchange_code(self, code: str, redirect_uri: str) -> OIDCTokens:
        raise NotImplementedError

    async def validate_token(self, id_token: str) -> OIDCClaims:
        raise NotImplementedError

    async def get_user_info(self, access_token: str) -> UserInfo:
        raise NotImplementedError

    async def refresh_token(self, refresh_token: str) -> OIDCTokens:
        raise NotImplementedError

    async def logout_url(
        self,
        id_token_hint: Optional[str] = None,
        post_logout_redirect_uri: Optional[str] = None,
    ) -> str:
        raise NotImplementedError
