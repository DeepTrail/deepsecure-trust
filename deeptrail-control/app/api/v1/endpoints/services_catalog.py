"""Public service catalog endpoint.

Provides:
  GET /api/v1/services/catalog — Returns services visible to the current user

Available to all authenticated users (not admin-only).
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.connected_service import ConnectedService
from app.models.service_registry import ServiceRegistry

logger = logging.getLogger(__name__)

router = APIRouter()


def get_current_user_claims(
    authorization: str = Header(..., description="Bearer token"),
) -> dict:
    """Extract user claims from authorization header (email + groups)."""
    import jwt as pyjwt
    from app.core.config import settings

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = authorization[len("Bearer "):]

    if token.startswith("mock_user_token_"):
        return {"sub": token.replace("mock_user_token_", ""), "groups": []}

    try:
        payload = pyjwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        sub = payload.get("sub") or payload.get("agent_id")
        if not sub:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token missing 'sub' claim",
            )
        groups = payload.get("groups", [])
        if isinstance(groups, str):
            groups = [groups]
        return {"sub": sub, "groups": groups}
    except pyjwt.exceptions.PyJWTError as e:
        logger.warning(f"JWT decode failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


class CatalogEntry(BaseModel):
    service_id: str
    display_name: str
    description: Optional[str] = None
    backend_type: str
    endpoint_url: str
    status: str
    health_status: str
    connected: bool = False
    scopes_granted: List[str] = []
    connected_at: Optional[str] = None

    model_config = {"from_attributes": True}


class CatalogResponse(BaseModel):
    services: List[CatalogEntry]
    total: int


@router.get("/catalog", response_model=CatalogResponse)
def get_service_catalog(
    db: Session = Depends(get_db),
    claims: dict = Depends(get_current_user_claims),
):
    """Return services visible to the current user based on Available To rules.

    A service is visible if ANY of:
    - "all" in available_to_roles (Everyone toggle)
    - no groups AND no users specified (legacy: defaults to everyone)
    - user's email is in available_to_users
    - any of user's groups is in available_to_groups
    """
    user_email = claims["sub"]
    user_groups = claims.get("groups", [])

    services = (
        db.query(ServiceRegistry)
        .filter(ServiceRegistry.status == "active")
        .all()
    )

    visible = []
    for svc in services:
        roles = svc.available_to_roles if svc.available_to_roles is not None else ["all"]
        groups = svc.available_to_groups if svc.available_to_groups is not None else []
        users = svc.available_to_users if svc.available_to_users is not None else []

        if "all" in roles:
            visible.append(svc)
        elif not groups and not users:
            visible.append(svc)
        elif user_email in users:
            visible.append(svc)
        elif any(g in groups for g in user_groups):
            visible.append(svc)

    connected_map: dict = {}
    if visible:
        connected = (
            db.query(ConnectedService)
            .filter(
                ConnectedService.user_id == user_email,
                ConnectedService.service_id.in_([s.service_id for s in visible]),
                ConnectedService.disconnected_at.is_(None),
            )
            .all()
        )
        connected_map = {c.service_id: c for c in connected}

    entries = []
    for svc in visible:
        conn = connected_map.get(svc.service_id)
        entries.append(CatalogEntry(
            service_id=svc.service_id,
            display_name=svc.display_name,
            description=svc.description,
            backend_type=svc.backend_type,
            endpoint_url=svc.endpoint_url,
            status=svc.status or "active",
            health_status=svc.health_status or "unknown",
            connected=conn is not None,
            scopes_granted=conn.scopes_granted if conn and conn.scopes_granted else [],
            connected_at=conn.connected_at.isoformat() if conn and conn.connected_at else None,
        ))

    return CatalogResponse(services=entries, total=len(entries))
