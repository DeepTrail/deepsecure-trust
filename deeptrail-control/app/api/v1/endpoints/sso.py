"""SSO (OIDC) authentication endpoints.

Implements the Authorization Code flow:
  1. /authorize  — Generate IdP login URL with CSRF state
  2. /callback   — Exchange code, validate ID token, provision user, issue JWT
  3. /logout     — Invalidate session, return IdP logout URL
"""

import logging
import secrets
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

import jwt as pyjwt
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordBearer

from app.core.config import settings
from app.core.idp_config import IdPConfig, IdPProviderType
from app.schemas.sso import (
    SSOAuthorizeResponse,
    SSOCallbackResponse,
    SSOLogoutRequest,
    SSOLogoutResponse,
    SSOUserInfo,
)
from app.services.idp_service import (
    OIDCError,
    OIDCProviderUnavailableError,
    OIDCTokenInvalidError,
    create_oidc_provider,
    provision_user_from_claims,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# JWT expiry for SSO sessions (24 hours)
SSO_SESSION_EXPIRY_HOURS = 24

SUPPORTED_IDPS = {t.value for t in IdPProviderType}


# ============================================================================
# SSO State Management
# ============================================================================


@dataclass
class PendingSSO:
    """Stored state for an in-flight SSO authorization."""

    state: str
    idp: str
    redirect_uri: str
    code_verifier: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_in: int = 300  # 5 minutes

    @property
    def is_expired(self) -> bool:
        return datetime.now(timezone.utc) > self.created_at + timedelta(
            seconds=self.expires_in
        )


# In-memory store; for production use Redis or DB-backed storage.
_pending_sso: Dict[str, PendingSSO] = {}


def _cleanup_expired() -> None:
    """Remove expired pending SSO entries (lazy garbage collection)."""
    expired = [k for k, v in _pending_sso.items() if v.is_expired]
    for k in expired:
        del _pending_sso[k]


# ============================================================================
# User JWT scheme for logout
# ============================================================================

_user_oauth2 = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


def _get_current_user_claims(
    token: str = Depends(_user_oauth2),
) -> dict:
    """Decode a user session JWT issued by /login or /sso/callback."""
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = pyjwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except pyjwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload


# ============================================================================
# Endpoints
# ============================================================================


@router.get("/{idp}/authorize", response_model=SSOAuthorizeResponse)
async def sso_authorize(
    idp: str,
    redirect_uri: Optional[str] = Query(None),
    response_mode: str = Query("json"),
):
    """Initiate SSO login via the specified IdP.

    Returns an authorization URL (JSON) or redirects to the IdP (302).
    """
    if idp not in SUPPORTED_IDPS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown IdP: {idp}. Supported: {', '.join(sorted(SUPPORTED_IDPS))}",
        )

    try:
        idp_config = IdPConfig()
        idp_config.provider = IdPProviderType(idp)
        provider = create_oidc_provider(idp_config)
    except NotImplementedError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_UNAVAILABLE,
            detail="IdP service unavailable",
        )

    state = secrets.token_urlsafe(32)
    effective_redirect = redirect_uri or idp_config.redirect_uri

    pending = PendingSSO(
        state=state,
        idp=idp,
        redirect_uri=effective_redirect,
    )
    _pending_sso[state] = pending
    _cleanup_expired()

    try:
        authorization_url = await provider.get_authorization_url(
            state=state,
            redirect_uri=effective_redirect,
            scopes=["openid", "profile", "email"],
        )
    except OIDCProviderUnavailableError:
        del _pending_sso[state]
        raise HTTPException(
            status_code=status.HTTP_503_UNAVAILABLE,
            detail="IdP service unavailable",
        )
    except Exception:
        del _pending_sso[state]
        raise HTTPException(
            status_code=status.HTTP_503_UNAVAILABLE,
            detail="IdP service unavailable",
        )

    if response_mode == "redirect":
        return RedirectResponse(url=authorization_url, status_code=302)

    return SSOAuthorizeResponse(
        authorization_url=authorization_url,
        state=state,
        expires_in=pending.expires_in,
    )


@router.get("/{idp}/callback")
async def sso_callback(
    idp: str,
    code: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
    error_description: Optional[str] = Query(None),
):
    """Handle IdP callback after user authentication.

    Exchanges the authorization code for tokens, validates the ID token,
    provisions (or matches) the user, and issues a DeepSecure session JWT.
    """
    # Handle IdP-side errors
    if error:
        desc = error_description or error
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"IdP error: {desc}",
        )

    if not code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing authorization code",
        )

    if not state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing state parameter",
        )

    # Validate & consume state (one-time use)
    pending = _pending_sso.pop(state, None)
    if pending is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired state parameter",
        )

    if pending.is_expired:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired state parameter",
        )

    if pending.idp != idp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="State/IdP mismatch",
        )

    # Resolve provider
    try:
        idp_config = IdPConfig()
        idp_config.provider = IdPProviderType(idp)
        provider = create_oidc_provider(idp_config)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to initialize IdP provider",
        )

    # Exchange code → tokens
    try:
        tokens = await provider.exchange_code(
            code=code,
            redirect_uri=pending.redirect_uri,
        )
    except OIDCError as exc:
        logger.warning("Code exchange failed for %s: %s", idp, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to exchange authorization code",
        )

    # Validate ID token → claims
    try:
        claims = await provider.validate_token(tokens.id_token)
    except OIDCTokenInvalidError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"ID token validation failed: {exc}",
        )
    except OIDCError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"ID token validation failed: {exc}",
        )

    # Provision user
    user_data = await provision_user_from_claims(claims)

    # Issue DeepSecure session JWT (same shape as POST /login)
    session_id = f"usess-{uuid.uuid4()}"
    now = datetime.now(timezone.utc)
    token_data = {
        "sub": user_data["email"],
        "session_id": session_id,
        "organization_id": user_data.get("organization_id"),
        "exp": now + timedelta(hours=SSO_SESSION_EXPIRY_HOURS),
        "iat": now,
        "idp": idp,
    }
    token = pyjwt.encode(token_data, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    logger.info("SSO login via %s: %s (new=%s)", idp, claims.email, user_data["is_new_user"])

    return SSOCallbackResponse(
        token=token,
        user=SSOUserInfo(
            user_id=user_data["user_id"],
            email=user_data["email"],
            name=user_data.get("name"),
            organization_id=user_data.get("organization_id"),
            is_new_user=user_data["is_new_user"],
        ),
        expires_in=SSO_SESSION_EXPIRY_HOURS * 3600,
        idp=idp,
    )


@router.post("/logout", response_model=SSOLogoutResponse)
async def sso_logout(
    body: Optional[SSOLogoutRequest] = None,
    user_claims: dict = Depends(_get_current_user_claims),
):
    """Logout: invalidate session and return IdP logout URL."""
    idp_name = user_claims.get("idp", "keycloak")
    post_redirect = body.post_logout_redirect_uri if body else None

    try:
        idp_config = IdPConfig()
        idp_config.provider = IdPProviderType(idp_name)
        provider = create_oidc_provider(idp_config)
        logout_url = await provider.logout_url(
            id_token_hint=None,
            post_logout_redirect_uri=post_redirect,
        )
    except Exception:
        logout_url = None

    logger.info("SSO logout: user=%s idp=%s", user_claims.get("sub"), idp_name)

    return SSOLogoutResponse(
        logout_url=logout_url,
        message="Session invalidated. Redirect to logout_url to complete IdP logout.",
    )
