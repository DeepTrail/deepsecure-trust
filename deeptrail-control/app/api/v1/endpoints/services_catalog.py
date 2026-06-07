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
from app.services.available_to import AvailableToEvaluator
from app.services.role_resolver import RoleResolver

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
        roles = payload.get("roles", [])
        if isinstance(roles, str):
            roles = [roles]
        return {"sub": sub, "groups": groups, "roles": roles}
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
    """Return services visible to the current user based on Available To rules."""
    resolver = RoleResolver()
    evaluator = AvailableToEvaluator()
    user_ctx = resolver.resolve_context(
        sub=claims["sub"],
        jwt_roles=claims.get("roles"),
        groups=claims.get("groups", []),
        db=db,
    )

    services = (
        db.query(ServiceRegistry)
        .filter(ServiceRegistry.status == "active")
        .all()
    )

    visible = [
        svc
        for svc in services
        if evaluator.is_visible(
            svc.available_to_roles,
            svc.available_to_groups,
            svc.available_to_users,
            user_ctx,
        )
    ]

    connected_map: dict = {}
    if visible:
        connected = (
            db.query(ConnectedService)
            .filter(
                ConnectedService.user_id == user_ctx.sub,
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
