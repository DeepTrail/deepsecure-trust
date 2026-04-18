"""Google OIDC provider implementation.

Implements the OIDCProvider protocol for Google Workspace and personal
Google accounts using httpx for HTTP and python-jose for RS256/JWKS
token validation.

Google uses fixed, well-known OIDC endpoints rather than deriving them
from the issuer URL. Supports the optional ``hd`` parameter to restrict
login to a specific Google Workspace domain.
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

_GOOGLE_AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
_GOOGLE_JWKS_URI = "https://www.googleapis.com/oauth2/v3/certs"
_GOOGLE_USERINFO_ENDPOINT = "https://openidconnect.googleapis.com/v1/userinfo"
_GOOGLE_ACCOUNT_URL = "https://myaccount.google.com"
_GOOGLE_DIRECTORY_API = "https://admin.googleapis.com/admin/directory/v1"
_DIRECTORY_SCOPE = "https://www.googleapis.com/auth/admin.directory.group.readonly"


class GoogleProvider:
    """OIDC provider implementation for Google.

    Supports both Google Workspace (with ``hd`` domain restriction) and
    personal Google accounts.  Uses hardcoded Google OIDC endpoints.
    """

    def __init__(
        self,
        issuer_url: str,
        client_id: str,
        client_secret: str | None = None,
        hd: str | None = None,
    ):
        self._issuer_url = issuer_url.rstrip("/")
        self._client_id = client_id
        self._client_secret = client_secret
        self._hd = hd

        self._auth_endpoint = _GOOGLE_AUTH_ENDPOINT
        self._token_endpoint = _GOOGLE_TOKEN_ENDPOINT
        self._jwks_uri = _GOOGLE_JWKS_URI
        self._userinfo_endpoint = _GOOGLE_USERINFO_ENDPOINT

        self._jwks_cache: dict | None = None

    async def get_authorization_url(
        self,
        state: str,
        redirect_uri: str,
        scopes: list[str] | None = None,
        code_challenge: str | None = None,
        code_challenge_method: str | None = None,
        fetch_groups: bool = False,
    ) -> str:
        scopes = list(scopes or ["openid", "profile", "email"])
        if fetch_groups and _DIRECTORY_SCOPE not in scopes:
            scopes.append(_DIRECTORY_SCOPE)
        params: dict[str, str] = {
            "response_type": "code",
            "client_id": self._client_id,
            "redirect_uri": redirect_uri,
            "scope": " ".join(scopes),
            "state": state,
        }
        if code_challenge:
            params["code_challenge"] = code_challenge
            params["code_challenge_method"] = code_challenge_method or "S256"
        if self._hd:
            params["hd"] = self._hd
            params["login_hint"] = f"@{self._hd}"
        params["prompt"] = "consent select_account"
        params["access_type"] = "offline"
        params["include_granted_scopes"] = "true"
        return f"{self._auth_endpoint}?{urlencode(params)}"

    async def fetch_user_groups(self, access_token: str, email: str) -> list[str]:
        """Fetch user's group memberships from Google Admin Directory API.

        Args:
            access_token: OAuth access token with admin.directory.group.readonly scope.
            email: User's email address to query groups for.

        Returns:
            List of group email addresses the user belongs to.
            Returns empty list on any error (fail-open for availability).
        """
        url = f"{_GOOGLE_DIRECTORY_API}/groups"
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url,
                    params={"userKey": email},
                    headers={"Authorization": f"Bearer {access_token}"},
                    timeout=10.0,
                )
        except httpx.HTTPError as exc:
            logger.warning("Failed to fetch groups for %s: %s", email, exc)
            return []

        if response.status_code != 200:
            logger.warning(
                "Directory API returned %d for %s: %s",
                response.status_code,
                email,
                response.text[:200],
            )
            return []

        try:
            data = response.json()
            return [g["email"] for g in data.get("groups", [])]
        except (KeyError, ValueError) as exc:
            logger.warning("Failed to parse groups response for %s: %s", email, exc)
            return []

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

        try:
            claims = jwt.decode(
                id_token,
                jwks,
                algorithms=["RS256"],
                audience=self._client_id,
                issuer=self._issuer_url,
                access_token=access_token,
            )
        except JWTError as exc:
            raise OIDCTokenInvalidError(
                f"ID token validation failed: {exc}",
                error_code="token_invalid",
            ) from exc

        return OIDCClaims(
            sub=claims["sub"],
            email=claims.get("email", ""),
            email_verified=claims.get("email_verified", False),
            name=claims.get("name"),
            given_name=claims.get("given_name"),
            family_name=claims.get("family_name"),
            groups=None,
            roles=None,
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
        return _GOOGLE_ACCOUNT_URL

    async def _get_jwks(self) -> dict:
        """Fetch JWKS from Google, with in-memory caching."""
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
