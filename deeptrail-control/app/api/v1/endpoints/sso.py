"""SSO (OIDC) authentication endpoints.

Implements the Authorization Code flow:
  1. /authorize  — Generate IdP login URL with CSRF state
  2. /callback   — Exchange code, validate ID token, provision user, issue JWT
  3. /logout     — Invalidate session, return IdP logout URL
"""

import base64
import hashlib
import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import jwt as pyjwt
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordBearer

from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import settings
from app.core.idp_config import IdPProviderType, get_idp_config_for_provider
from app.models.pending_oauth_state import PendingOAuthState
from app.schemas.sso import (
    SSOAuthorizeResponse,
    SSOCallbackResponse,
    SSOLogoutRequest,
    SSOLogoutResponse,
    SSORefreshResponse,
    SSOUserInfo,
)
from app.services.group_policy import GroupPolicyMapper
from app.services.idp_service import (
    OIDCError,
    OIDCProviderUnavailableError,
    OIDCTokenInvalidError,
    create_oidc_provider,
    provision_user_from_claims,
)

logger = logging.getLogger(__name__)

# ============================================================================
# Group Policy Mapper (lazy singleton)
# ============================================================================

_group_mapper: GroupPolicyMapper | None = None


def _get_group_policy_mapper() -> GroupPolicyMapper:
    """Lazily load the GroupPolicyMapper singleton from group_policies.yaml."""
    global _group_mapper
    if _group_mapper is None:
        config_path = Path(__file__).resolve().parents[4] / "group_policies.yaml"
        if config_path.exists():
            _group_mapper = GroupPolicyMapper.from_yaml(config_path)
            logger.info("Loaded group policies from %s", config_path)
        else:
            logger.warning(
                "No group_policies.yaml found at %s — using empty policy", config_path
            )
            _group_mapper = GroupPolicyMapper([])
    return _group_mapper

router = APIRouter()

# JWT expiry for SSO sessions (24 hours)
SSO_SESSION_EXPIRY_HOURS = 24

# Expired tokens are accepted for refresh up to this many seconds past exp
REFRESH_GRACE_WINDOW_SECONDS = 3600

SUPPORTED_IDPS = {t.value for t in IdPProviderType}


# ============================================================================
# SSO State Management  (DB-backed — replaces former _pending_sso dict)
# ============================================================================


def _cleanup_expired(db: Session) -> None:
    """Delete expired pending SSO rows (lazy garbage collection)."""
    now = datetime.now(timezone.utc)
    db.query(PendingOAuthState).filter(PendingOAuthState.expires_at < now).delete(
        synchronize_session=False
    )
    db.commit()


def _generate_pkce_pair() -> tuple[str, str]:
    """Generate a PKCE code_verifier and code_challenge (S256)."""
    code_verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return code_verifier, code_challenge


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
    post_login_redirect: Optional[str] = Query(None),
    db: Session = Depends(get_db),
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
        idp_config = get_idp_config_for_provider(idp)
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

    # Build the callback redirect_uri with the {idp} segment so it matches
    # the /{idp}/callback route.  Fall back to the configured base only when
    # an explicit redirect_uri is supplied by the caller.
    if redirect_uri:
        effective_redirect = redirect_uri
    else:
        base = idp_config.redirect_uri.rstrip("/")
        if not base.endswith(f"/{idp}/callback"):
            base = base.rsplit("/callback", 1)[0]
            effective_redirect = f"{base}/{idp}/callback"
        else:
            effective_redirect = idp_config.redirect_uri

    code_verifier, code_challenge = _generate_pkce_pair()

    ttl_seconds = 300
    pending = PendingOAuthState(
        state=state,
        idp=idp,
        redirect_uri=effective_redirect,
        code_verifier=code_verifier,
        post_login_redirect=post_login_redirect,
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds),
    )
    db.add(pending)
    db.commit()
    _cleanup_expired(db)

    auth_kwargs: dict = {
        "state": state,
        "redirect_uri": effective_redirect,
        "scopes": ["openid", "profile", "email"],
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    if idp == "google" and idp_config.fetch_groups:
        auth_kwargs["fetch_groups"] = True

    try:
        authorization_url = await provider.get_authorization_url(**auth_kwargs)
    except (OIDCProviderUnavailableError, Exception):
        db.query(PendingOAuthState).filter(PendingOAuthState.state == state).delete(
            synchronize_session=False
        )
        db.commit()
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
    db: Session = Depends(get_db),
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

    # Validate & consume state (one-time use) — DB-backed
    pending = db.query(PendingOAuthState).filter(
        PendingOAuthState.state == state
    ).first()
    if pending is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired state parameter",
        )

    if pending.is_expired:
        db.delete(pending)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired state parameter",
        )

    # Consume: delete now so the state cannot be replayed
    db.delete(pending)
    db.commit()

    if pending.idp != idp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="State/IdP mismatch",
        )

    # Resolve provider
    try:
        idp_config = get_idp_config_for_provider(idp)
        provider = create_oidc_provider(idp_config)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to initialize IdP provider",
        )

    # Exchange code → tokens (include PKCE code_verifier when available)
    try:
        tokens = await provider.exchange_code(
            code=code,
            redirect_uri=pending.redirect_uri,
            code_verifier=pending.code_verifier,
        )
    except OIDCError as exc:
        logger.warning("Code exchange failed for %s: %s", idp, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to exchange authorization code",
        )

    # Validate ID token → claims (pass access_token for at_hash verification)
    try:
        claims = await provider.validate_token(tokens.id_token, tokens.access_token)
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

    # Fetch groups from Directory API for Google when configured
    if idp == "google" and idp_config.fetch_groups:
        try:
            from app.services.providers.google import GoogleProvider

            if isinstance(provider, GoogleProvider):
                groups = await provider.fetch_user_groups(
                    access_token=tokens.access_token,
                    email=claims.email,
                )
                claims.groups = groups
        except Exception:
            logger.warning(
                "Failed to fetch groups for %s — continuing without group policy",
                claims.email,
                exc_info=True,
            )

    # Fallback: use the hosted domain (hd) as a synthetic group when
    # Directory API returned nothing.  This lets group_policies.yaml
    # map domain-level roles (e.g. "deeptrail.com" → engineer).
    if idp == "google" and not claims.groups:
        hd = (claims.raw_claims or {}).get("hd")
        if hd:
            claims.groups = [hd]
            logger.info(
                "No Directory API groups for %s — using hd=%s as synthetic group",
                claims.email,
                hd,
            )

    # Provision user (applies static _GROUP_TO_ROLE_MAP as a baseline)
    user_data = await provision_user_from_claims(claims)

    # Resolve group policy (merges YAML-driven roles and permissions)
    if user_data.get("groups"):
        group_mapper = _get_group_policy_mapper()
        policy_result = group_mapper.resolve(user_data["groups"])
        if policy_result.roles:
            merged_roles = list(
                dict.fromkeys(user_data.get("roles", []) + policy_result.roles)
            )
            user_data["roles"] = merged_roles
        if policy_result.default_permissions:
            user_data["default_permissions"] = policy_result.default_permissions
        logger.info(
            "Group policy resolved: matched=%s roles=%s perms=%d",
            policy_result.matched_groups,
            policy_result.roles,
            len(policy_result.default_permissions),
        )

    # Issue DeepSecure session JWT (same shape as POST /login)
    session_id = f"usess-{uuid.uuid4()}"
    now = datetime.now(timezone.utc)
    token_data = {
        "sub": user_data["email"],
        "session_id": session_id,
        "organization_id": user_data.get("organization_id"),
        "groups": user_data.get("groups", []),
        "roles": user_data.get("roles", []),
        "exp": now + timedelta(hours=SSO_SESSION_EXPIRY_HOURS),
        "iat": now,
        "idp": idp,
    }
    token = pyjwt.encode(token_data, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    # Store IdP tokens for future refresh (Feature 2 — offline access)
    refresh_available = False
    if tokens.refresh_token:
        try:
            from app.services.idp_session_service import IdPSessionService

            idp_session_svc = IdPSessionService(db)
            idp_session_svc.store(
                session_id=session_id,
                user_id=user_data["email"],
                idp=idp,
                tokens=tokens,
                id_token_claims=claims.raw_claims,
            )
            refresh_available = True
        except Exception:
            logger.warning(
                "Failed to store IdP session for %s — session continues without refresh capability",
                user_data["email"],
                exc_info=True,
            )

    logger.info("SSO login via %s: %s (new=%s)", idp, claims.email, user_data["is_new_user"])

    if pending.post_login_redirect:
        from urllib.parse import urlencode as _urlencode

        redirect_params = {"token": token, "email": user_data["email"]}
        if user_data.get("name"):
            redirect_params["name"] = user_data["name"]
        return RedirectResponse(
            url=f"{pending.post_login_redirect}?{_urlencode(redirect_params)}",
            status_code=302,
        )

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
        refresh_available=refresh_available,
    )


@router.post("/logout", response_model=SSOLogoutResponse)
async def sso_logout(
    body: Optional[SSOLogoutRequest] = None,
    user_claims: dict = Depends(_get_current_user_claims),
    db: Session = Depends(get_db),
):
    """Logout: revoke stored IdP session, invalidate session, return IdP logout URL."""
    idp_name = user_claims.get("idp", "keycloak")
    session_id = user_claims.get("session_id")
    post_redirect = body.post_logout_redirect_uri if body else None

    # Revoke stored IdP session (if exists)
    idp_session_revoked = False
    if session_id:
        try:
            from app.services.idp_session_service import IdPSessionService

            idp_session_svc = IdPSessionService(db)
            idp_session_revoked = idp_session_svc.revoke(session_id)
        except Exception:
            logger.warning(
                "Failed to revoke IdP session for %s — continuing logout",
                session_id,
                exc_info=True,
            )

    try:
        idp_config = get_idp_config_for_provider(idp_name)
        provider = create_oidc_provider(idp_config)
        logout_url = await provider.logout_url(
            id_token_hint=None,
            post_logout_redirect_uri=post_redirect,
        )
    except Exception:
        logout_url = None

    logger.info(
        "SSO logout: user=%s idp=%s session_revoked=%s",
        user_claims.get("sub"),
        idp_name,
        idp_session_revoked,
    )

    return SSOLogoutResponse(
        logout_url=logout_url,
        message="Session invalidated. Redirect to logout_url to complete IdP logout.",
    )


# ============================================================================
# Refresh
# ============================================================================


def _decode_jwt_for_refresh(authorization: str | None) -> dict:
    """Decode a session JWT for refresh, tolerating tokens expired within the grace window."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization")

    token = authorization.removeprefix("Bearer ").strip()

    try:
        return pyjwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except pyjwt.ExpiredSignatureError:
        try:
            claims = pyjwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM],
                options={"verify_exp": False},
            )
        except pyjwt.InvalidTokenError:
            raise HTTPException(status_code=401, detail="Invalid token")

        exp = claims.get("exp")
        if exp:
            expired_at = datetime.fromtimestamp(exp, tz=timezone.utc)
            grace_deadline = expired_at + timedelta(seconds=REFRESH_GRACE_WINDOW_SECONDS)
            if datetime.now(timezone.utc) > grace_deadline:
                raise HTTPException(
                    status_code=401, detail="Token expired beyond refresh grace window"
                )
        return claims
    except pyjwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


@router.post("/refresh", response_model=SSORefreshResponse)
async def sso_refresh(
    authorization: str | None = Header(None),
    db: Session = Depends(get_db),
):
    """Silent session renewal using a stored IdP refresh token.

    Accepts JWTs that have expired within a 1-hour grace window so clients
    can call this endpoint even after the session JWT's ``exp`` has passed.
    """
    claims = _decode_jwt_for_refresh(authorization)

    session_id = claims.get("session_id")
    if not session_id:
        raise HTTPException(status_code=401, detail="Token missing session_id claim")

    idp = claims.get("idp", "keycloak")
    sub = claims.get("sub")

    # --- Load stored IdP session ---
    from app.services.idp_session_service import IdPSessionService

    idp_session_svc = IdPSessionService(db)
    idp_session = idp_session_svc.get_by_session(session_id)
    if idp_session is None:
        raise HTTPException(status_code=404, detail="No refresh session found")

    decrypted = idp_session_svc.get_decrypted_tokens(session_id)
    if not decrypted or not decrypted.get("refresh_token"):
        raise HTTPException(status_code=404, detail="No refresh token available")

    # --- Refresh tokens with IdP provider ---
    idp_config = get_idp_config_for_provider(idp)
    provider = create_oidc_provider(idp_config)

    try:
        new_tokens = await provider.refresh_token(decrypted["refresh_token"])
    except (OIDCError, Exception) as exc:
        raise HTTPException(status_code=502, detail=f"IdP refresh failed: {exc}")

    # Optionally validate new ID token for updated claims; fall back to old JWT claims
    refreshed_claims = dict(claims)
    if new_tokens.id_token:
        try:
            validated = await provider.validate_token(
                new_tokens.id_token, new_tokens.access_token
            )
            if validated.email:
                refreshed_claims["sub"] = validated.email
            if hasattr(validated, "groups") and validated.groups:
                refreshed_claims["groups"] = validated.groups
        except Exception:
            logger.debug("Could not validate refreshed ID token — using previous claims")

    # --- Mint new session JWT ---
    new_session_id = f"usess-{uuid.uuid4().hex[:16]}"
    now = datetime.now(timezone.utc)
    token_data = {
        "sub": refreshed_claims.get("sub", sub),
        "session_id": new_session_id,
        "organization_id": refreshed_claims.get("organization_id"),
        "groups": refreshed_claims.get("groups", []),
        "roles": refreshed_claims.get("roles", []),
        "exp": now + timedelta(hours=SSO_SESSION_EXPIRY_HOURS),
        "iat": now,
        "idp": idp,
    }
    new_jwt = pyjwt.encode(token_data, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    # --- Store new IdP session, revoke old ---
    try:
        idp_session_svc.store(
            session_id=new_session_id,
            user_id=refreshed_claims.get("sub", sub),
            idp=idp,
            tokens=new_tokens,
        )
    except Exception:
        logger.warning(
            "Failed to store new IdP session for %s — JWT still issued",
            new_session_id,
            exc_info=True,
        )

    try:
        idp_session_svc.revoke(session_id)
    except Exception:
        logger.warning(
            "Failed to revoke old IdP session %s after refresh",
            session_id,
            exc_info=True,
        )

    logger.info(
        "SSO refresh: user=%s idp=%s old_session=%s new_session=%s",
        refreshed_claims.get("sub", sub),
        idp,
        session_id,
        new_session_id,
    )

    return SSORefreshResponse(
        token=new_jwt,
        expires_in=SSO_SESSION_EXPIRY_HOURS * 3600,
        idp=idp,
        refreshed_at=now.isoformat(),
    )
