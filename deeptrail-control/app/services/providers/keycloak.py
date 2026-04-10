"""Keycloak OIDC provider implementation.

Implements the OIDCProvider protocol for Keycloak using httpx for HTTP
and python-jose for RS256/JWKS token validation.

In production Keycloak can also serve as an SSO broker, federating
to upstream IdPs (Okta, Entra ID) via identity brokering.
"""

from __future__ import annotations

import logging
from urllib.parse import urlencode

import httpx
from jose import JWTError, jwt

from app.services.idp_service import (
    OIDCClaims,
    OIDCError,
    OIDCProviderUnavailableError,
    OIDCTokenInvalidError,
    OIDCTokens,
    UserInfo,
)

logger = logging.getLogger(__name__)


class KeycloakProvider:
    """OIDC provider implementation for Keycloak.

    Used as the dev-time IdP and as the default provider.
    Derives standard OIDC endpoints from the issuer URL.
    """

    def __init__(
        self,
        issuer_url: str,
        client_id: str,
        client_secret: str | None = None,
        realm: str = "deepsecure",
        browser_url: str | None = None,
    ):
        self._issuer_url = issuer_url.rstrip("/")
        self._client_id = client_id
        self._client_secret = client_secret
        self._realm = realm

        # Browser-facing base (for auth redirects the user's browser follows).
        # Falls back to issuer_url when not set (non-Docker environments).
        browser_base = (browser_url or issuer_url).rstrip("/")
        self._browser_issuer = browser_base

        # Backend endpoints (container-to-container in Docker)
        backend_base = self._issuer_url
        self._token_endpoint = f"{backend_base}/protocol/openid-connect/token"
        self._userinfo_endpoint = f"{backend_base}/protocol/openid-connect/userinfo"
        self._jwks_uri = f"{backend_base}/protocol/openid-connect/certs"

        # Browser-facing endpoints (must be resolvable by the user's browser)
        self._auth_endpoint = f"{browser_base}/protocol/openid-connect/auth"
        self._logout_endpoint = f"{browser_base}/protocol/openid-connect/logout"

        self._jwks_cache: dict | None = None

    async def get_authorization_url(
        self,
        state: str,
        redirect_uri: str,
        scopes: list[str] | None = None,
        code_challenge: str | None = None,
        code_challenge_method: str | None = None,
    ) -> str:
        scopes = scopes or ["openid", "profile", "email"]
        params = {
            "response_type": "code",
            "client_id": self._client_id,
            "redirect_uri": redirect_uri,
            "scope": " ".join(scopes),
            "state": state,
        }
        if code_challenge:
            params["code_challenge"] = code_challenge
            params["code_challenge_method"] = code_challenge_method or "S256"
        return f"{self._auth_endpoint}?{urlencode(params)}"

    async def exchange_code(
        self, code: str, redirect_uri: str, code_verifier: str | None = None
    ) -> OIDCTokens:
        data: dict[str, str] = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": self._client_id,
        }
        if self._client_secret:
            data["client_secret"] = self._client_secret
        if code_verifier:
            data["code_verifier"] = code_verifier

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self._token_endpoint,
                    data=data,
                    timeout=10.0,
                )
        except httpx.HTTPError as exc:
            raise OIDCProviderUnavailableError(
                f"Token endpoint unreachable: {exc}",
                error_code="provider_unavailable",
            ) from exc

        if response.status_code != 200:
            error_detail = {}
            content_type = response.headers.get("content-type", "")
            if content_type.startswith("application/json"):
                error_detail = response.json()
            raise OIDCError(
                f"Token exchange failed: {response.status_code}",
                error_code="token_exchange_failed",
                details=error_detail,
            )

        token_data = response.json()
        return OIDCTokens(
            id_token=token_data["id_token"],
            access_token=token_data["access_token"],
            refresh_token=token_data.get("refresh_token"),
            token_type=token_data.get("token_type", "Bearer"),
        )

    async def validate_token(
        self, id_token: str, access_token: str | None = None
    ) -> OIDCClaims:
        jwks = await self._get_jwks()

        # Accept tokens issued under either the backend (Docker-internal) or
        # browser-facing issuer URL.  Keycloak sets `iss` based on the request
        # hostname, which may differ between the two.
        valid_issuers = [self._issuer_url]
        if self._browser_issuer != self._issuer_url:
            valid_issuers.append(self._browser_issuer)

        last_exc: JWTError | None = None
        claims: dict | None = None
        for issuer in valid_issuers:
            try:
                claims = jwt.decode(
                    id_token,
                    jwks,
                    algorithms=["RS256"],
                    audience=self._client_id,
                    issuer=issuer,
                    access_token=access_token,
                )
                break
            except JWTError as exc:
                last_exc = exc

        if claims is None:
            raise OIDCTokenInvalidError(
                f"ID token validation failed: {last_exc}",
                error_code="token_invalid",
            ) from last_exc

        return OIDCClaims(
            sub=claims["sub"],
            email=claims.get("email", ""),
            email_verified=claims.get("email_verified", False),
            name=claims.get("name"),
            given_name=claims.get("given_name"),
            family_name=claims.get("family_name"),
            groups=claims.get("groups"),
            roles=claims.get("realm_access", {}).get("roles"),
            issuer=claims.get("iss"),
            audience=claims.get("aud"),
            raw_claims=claims,
        )

    async def get_user_info(self, access_token: str) -> UserInfo:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    self._userinfo_endpoint,
                    headers={"Authorization": f"Bearer {access_token}"},
                    timeout=10.0,
                )
        except httpx.HTTPError as exc:
            raise OIDCProviderUnavailableError(
                f"Userinfo endpoint unreachable: {exc}",
                error_code="provider_unavailable",
            ) from exc

        if response.status_code != 200:
            raise OIDCError(
                f"Userinfo request failed: {response.status_code}",
                error_code="userinfo_failed",
            )

        data = response.json()
        return UserInfo(
            sub=data["sub"],
            email=data.get("email", ""),
            name=data.get("name"),
            groups=data.get("groups"),
            roles=data.get("realm_access", {}).get("roles"),
        )

    async def refresh_token(self, refresh_token: str) -> OIDCTokens:
        data: dict[str, str] = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": self._client_id,
        }
        if self._client_secret:
            data["client_secret"] = self._client_secret

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self._token_endpoint,
                    data=data,
                    timeout=10.0,
                )
        except httpx.HTTPError as exc:
            raise OIDCProviderUnavailableError(
                f"Token endpoint unreachable: {exc}",
                error_code="provider_unavailable",
            ) from exc

        if response.status_code != 200:
            raise OIDCError(
                f"Token refresh failed: {response.status_code}",
                error_code="refresh_failed",
            )

        token_data = response.json()
        return OIDCTokens(
            id_token=token_data.get("id_token", ""),
            access_token=token_data["access_token"],
            refresh_token=token_data.get("refresh_token", refresh_token),
            token_type=token_data.get("token_type", "Bearer"),
        )

    async def logout_url(
        self,
        id_token_hint: str | None = None,
        post_logout_redirect_uri: str | None = None,
    ) -> str:
        params: dict[str, str] = {}
        if id_token_hint:
            params["id_token_hint"] = id_token_hint
        if post_logout_redirect_uri:
            params["post_logout_redirect_uri"] = post_logout_redirect_uri
        if params:
            return f"{self._logout_endpoint}?{urlencode(params)}"
        return self._logout_endpoint

    async def _get_jwks(self) -> dict:
        """Fetch JWKS from the IdP, with in-memory caching."""
        if self._jwks_cache is not None:
            return self._jwks_cache

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(self._jwks_uri, timeout=10.0)
        except httpx.HTTPError as exc:
            raise OIDCProviderUnavailableError(
                f"JWKS endpoint unreachable: {exc}",
                error_code="jwks_unavailable",
            ) from exc

        if response.status_code != 200:
            raise OIDCProviderUnavailableError(
                f"JWKS fetch failed: {response.status_code}",
                error_code="jwks_unavailable",
            )

        self._jwks_cache = response.json()
        return self._jwks_cache
