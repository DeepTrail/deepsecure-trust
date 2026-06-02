"""Google OIDC provider implementation.

Implements the OIDCProvider protocol for Google Workspace and personal
Google accounts using httpx for HTTP and python-jose for RS256/JWKS
token validation.

Google uses fixed, well-known OIDC endpoints rather than deriving them
from the issuer URL. Supports the optional ``hd`` parameter to restrict
login to a specific Google Workspace domain.

Directory API integration uses a service account with domain-wide
delegation to fetch groups and admin status for any user — no
user-level admin privileges required.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
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
_DIRECTORY_GROUP_SCOPE = "https://www.googleapis.com/auth/admin.directory.group.readonly"
_DIRECTORY_USER_SCOPE = "https://www.googleapis.com/auth/admin.directory.user.readonly"
_DIRECTORY_SCOPE = _DIRECTORY_GROUP_SCOPE


@dataclass
class WorkspaceUserInfo:
    """Information about a user from Google Workspace Directory API."""
    groups: list[str]
    is_admin: bool


def _get_delegated_credentials(admin_email: str):
    """Build delegated credentials using the service account with domain-wide delegation.

    Works transparently in both environments:
      - Local dev: uses ADC from ~/.config/gcloud/application_default_credentials.json
        and impersonates the service account
      - Production (Cloud Run): the service IS the service account, no impersonation needed
    """
    try:
        import google.auth
        from google.auth import impersonated_credentials
        from google.oauth2 import service_account
    except ImportError:
        logger.error("google-auth library not installed — cannot use Directory API")
        return None

    scopes = [_DIRECTORY_GROUP_SCOPE, _DIRECTORY_USER_SCOPE]
    sa_email = os.environ.get(
        "GOOGLE_SERVICE_ACCOUNT_EMAIL",
        "deepsecure-admin@gen-lang-client-0227820266.iam.gserviceaccount.com",
    )

    try:
        source_credentials, project = google.auth.default()

        if hasattr(source_credentials, "service_account_email") and \
                source_credentials.service_account_email == sa_email:
            # Running AS the service account (Cloud Run) — delegate directly
            delegated = service_account.Credentials(
                signer=source_credentials.signer,
                service_account_email=sa_email,
                token_uri="https://oauth2.googleapis.com/token",
                scopes=scopes,
                subject=admin_email,
            )
        else:
            # Running with user ADC (local dev) — impersonate, then delegate
            target_credentials = impersonated_credentials.Credentials(
                source_credentials=source_credentials,
                target_principal=sa_email,
                target_scopes=scopes,
                delegates=[],
            )
            delegated = impersonated_credentials.Credentials(
                source_credentials=source_credentials,
                target_principal=sa_email,
                target_scopes=scopes,
                delegates=[],
                subject=admin_email,
            )

        return delegated
    except Exception:
        logger.warning(
            "Failed to build delegated credentials for Directory API",
            exc_info=True,
        )
        return None


async def fetch_workspace_user_info(email: str, admin_email: str | None = None) -> WorkspaceUserInfo | None:
    """Fetch a user's groups and admin status from Google Workspace Directory API.

    Uses the service account with domain-wide delegation — works for ANY user,
    not just Workspace admins.

    Args:
        email: User's email address to query.
        admin_email: Workspace admin email to impersonate for API calls.
                     Defaults to GOOGLE_ADMIN_EMAIL env var.

    Returns:
        WorkspaceUserInfo with groups and admin status, or None on failure.
    """
    admin_email = admin_email or os.environ.get("GOOGLE_ADMIN_EMAIL", "mahendra@deeptrail.com")

    creds = _get_delegated_credentials(admin_email)
    if creds is None:
        return None

    try:
        from google.auth.transport.requests import Request
        creds.refresh(Request())
        access_token = creds.token
    except Exception:
        logger.warning("Failed to obtain delegated access token for Directory API", exc_info=True)
        return None

    groups: list[str] = []
    is_admin = False

    async with httpx.AsyncClient() as client:
        # Fetch groups
        try:
            resp = await client.get(
                f"{_GOOGLE_DIRECTORY_API}/groups",
                params={"userKey": email},
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=10.0,
            )
            if resp.status_code == 200:
                data = resp.json()
                groups = [g["email"] for g in data.get("groups", [])]
            else:
                logger.warning(
                    "Directory API groups returned %d for %s: %s",
                    resp.status_code, email, resp.text[:200],
                )
        except Exception:
            logger.warning("Failed to fetch groups for %s", email, exc_info=True)

        # Fetch admin status
        try:
            resp = await client.get(
                f"{_GOOGLE_DIRECTORY_API}/users/{email}",
                params={"projection": "basic", "viewType": "admin_view"},
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=10.0,
            )
            if resp.status_code == 200:
                user_data = resp.json()
                is_admin = user_data.get("isAdmin", False)
            else:
                logger.warning(
                    "Directory API users returned %d for %s: %s",
                    resp.status_code, email, resp.text[:200],
                )
        except Exception:
            logger.warning("Failed to fetch admin status for %s", email, exc_info=True)

    return WorkspaceUserInfo(groups=groups, is_admin=is_admin)


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

        Prefers service-account-based delegation (works for all users).
        Falls back to user's access token only if service account is not configured.
        """
        workspace_info = await fetch_workspace_user_info(email)
        if workspace_info is not None:
            return workspace_info.groups

        logger.info("Service account delegation unavailable — falling back to user access token for %s", email)
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
                response.status_code, email, response.text[:200],
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
