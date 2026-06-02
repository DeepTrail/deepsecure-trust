"""Admin role middleware for the Control Plane.

Two-layer admin check:
  1. JWT 'roles' claim (populated by SSO from IdP groups) — primary
  2. DB user_sessions.role column — fallback for non-SSO logins

Usage in endpoint routers:
    @router.get("/admin/...", dependencies=[Depends(require_admin)])
    async def admin_endpoint(...):
        ...

Or to get the full claims dict:
    @router.get("/admin/...")
    async def admin_endpoint(claims: dict = Depends(require_admin)):
        user_id = claims["sub"]
"""

import logging
from typing import Optional

import jwt
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import settings
from app.models.user_session import UserSession

logger = logging.getLogger(__name__)


def get_current_user_claims(
    authorization: str = Header(..., description="Bearer token"),
) -> dict:
    """Parse user JWT and return full claims dict.

    Supports:
      - Real JWTs (HS256 signed, with 'sub' claim)
      - Mock tokens for development (mock_user_token_{user_id})
    """
    try:
        token = authorization.replace("Bearer ", "")

        if token.startswith("mock_user_token_"):
            user_id = token.replace("mock_user_token_", "")
            return {"sub": user_id, "roles": []}

        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        if "sub" not in payload and "agent_id" in payload:
            payload["sub"] = payload["agent_id"]
        if "sub" not in payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token missing 'sub' claim",
            )
        return payload

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
        )
    except jwt.exceptions.PyJWTError as exc:
        logger.warning("JWT decode failed in admin middleware: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Failed to parse authorization header: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header",
        )


def require_admin(
    claims: dict = Depends(get_current_user_claims),
    db: Session = Depends(get_db),
) -> dict:
    """Verify the current user has admin role.

    Check order:
      1. JWT 'roles' claim (SSO path) — if it contains 'admin', allow.
      2. DB user_sessions.role column (non-SSO path) — if role == 'admin', allow.
      3. Otherwise, raise 403.

    Returns the claims dict so downstream endpoints can use the user identity.
    """
    jwt_roles = claims.get("roles", [])
    if isinstance(jwt_roles, list) and "admin" in jwt_roles:
        return claims

    user_id = claims.get("sub")
    if user_id:
        session = (
            db.query(UserSession)
            .filter(
                UserSession.user_id == user_id,
                UserSession.revoked_at.is_(None),
            )
            .order_by(UserSession.created_at.desc())
            .first()
        )
        if session and getattr(session, "role", None) == "admin":
            return claims

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Admin role required",
    )
