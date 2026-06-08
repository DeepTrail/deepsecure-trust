from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session
from typing import Any, Dict, List, Optional
import logging
import uuid
import jwt

from app import models, schemas
from app.api import deps
from app.models.connected_service import ConnectedService
from app.models.delegation import DelegationToken
from app.services.delegation_service import (
    AcceptDelegationResult,
    DelegationForbiddenError,
    DelegationInvalidStateError,
    DelegationNotFoundError,
    DelegationNotPendingError,
    DelegationService,
    PermissionValidationError,
    PermissionWideningError,
    PatchDelegationResult,
)
from app.services.macaroon_service import macaroon_service
from app.services.scope_mapper import ScopeMapper
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()
user_delegations_router = APIRouter()


# =============================================================================
# User Delegation Schemas (Step 4 of Sarah's Journey)
# =============================================================================


class UserDelegationRequest(BaseModel):
    """Request for a user to delegate permissions to an agent."""
    
    agent_id: str = Field(..., description="Agent to delegate to")
    permissions: List[str] = Field(..., description="Permissions to delegate")
    constraints: Optional[Dict[str, Any]] = Field(
        default=None, description="Optional constraints"
    )


class UserDelegationResponse(BaseModel):
    """Response after creating a delegation."""
    
    delegation_token: str
    delegation_id: str
    permissions: List[str]
    expires_in: int = 28800  # 8 hours


def get_current_user_from_token(
    authorization: str = Header(..., description="Bearer token"),
) -> str:
    """Extract user ID from authorization header."""
    return _parse_user_token(authorization)["sub"]


def _parse_user_token(authorization: str) -> Dict[str, Any]:
    """Parse the full User JWT payload from the authorization header.

    Returns a dict with at least 'sub'. Other claims (organization_id,
    session_id, etc.) are included when present.
    """
    try:
        token = authorization.replace("Bearer ", "")

        if token.startswith("mock_user_token_"):
            return {"sub": token.replace("mock_user_token_", "")}

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
            detail="Token expired. Please log in again.",
        )
    except jwt.exceptions.PyJWTError as e:
        logger.warning(f"JWT decode failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"Failed to extract user from token: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header",
        )


# =============================================================================
# User Delegation Endpoint (Step 4 of Sarah's Journey)
# =============================================================================


@router.post("/delegate", response_model=UserDelegationResponse)
def create_user_delegation(
    request: UserDelegationRequest,
    authorization: str = Header(...),
    db: Session = Depends(deps.get_db),
):
    """
    Create a delegation from a user to an agent.
    
    This is Step 4 of Sarah's Journey: Sarah Delegates to Agent.
    
    Validates that requested permissions are allowed by the user's
    connected service scopes (monotonic attenuation principle).
    
    MVP: Creates a macaroon-based delegation token.
    """
    user_claims = _parse_user_token(authorization)
    current_user = user_claims["sub"]
    user_org_id = user_claims.get("organization_id")
    
    # Get user's connected services for permission validation
    connections = (
        db.query(ConnectedService)
        .filter(
            ConnectedService.user_id == current_user,
            ConnectedService.disconnected_at.is_(None),
        )
        .all()
    )
    
    from app.models.service_registry import ServiceRegistry

    # Build allowed permissions from OAuth-connected services
    connected_services = [
        (conn.service_id, conn.scopes_granted or [])
        for conn in connections
    ]
    allowed = ScopeMapper.get_all_allowed_permissions(connected_services)

    # Also include MCP-discovered permissions
    mcp_services = (
        db.query(ServiceRegistry)
        .filter(
            ServiceRegistry.backend_type == "mcp",
            ServiceRegistry.status.in_(["active", "sandbox"]),
            ServiceRegistry.discovered_tools.isnot(None),
        )
        .all()
    )
    for svc in mcp_services:
        perm_map = svc.permission_map or {}
        allowed.update(perm_map.values())

    if not connections and not mcp_services:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "no_connected_services",
                "message": "User has no connected services",
                "hint": "Connect a service before creating delegations",
            },
        )

    invalid_perms = [p for p in request.permissions if p not in allowed]

    if invalid_perms:
        logger.warning(
            "Permission validation failed: user=%s invalid=%s",
            current_user,
            invalid_perms,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "permission_validation_failed",
                "message": "Requested permissions not allowed by connected scopes",
                "invalid_permissions": invalid_perms,
                "allowed_permissions": sorted(list(allowed)),
                "hint": "Connect service with additional scopes or remove invalid permissions",
            },
        )
    
    # Calculate TTL from constraints
    ttl_hours = 8  # Default
    if request.constraints and "expires_in_hours" in request.constraints:
        ttl_hours = request.constraints["expires_in_hours"]
    ttl_seconds = ttl_hours * 3600

    # Generate delegation ID
    delegation_id = f"del-{uuid.uuid4()}"

    # Create delegation token using macaroon service
    delegation_token = macaroon_service.mint_delegation_macaroon(
        target_agent_id=request.agent_id,
        resource="*",  # All resources for MVP
        permissions=request.permissions,
        ttl_seconds=ttl_seconds,
    )

    now = datetime.now(timezone.utc)
    delegation_row = DelegationToken(
        id=delegation_id,
        agent_id=request.agent_id,
        delegator=current_user,
        delegated_permissions=request.permissions,
        constraints=request.constraints or {},
        organization_id=user_org_id,
        created_at=now,
        expires_at=now + timedelta(seconds=ttl_seconds),
    )
    db.add(delegation_row)
    db.commit()

    logger.info(
        "User %s created delegation %s for agent %s",
        current_user,
        delegation_id,
        request.agent_id,
    )

    return UserDelegationResponse(
        delegation_token=delegation_token,
        delegation_id=delegation_id,
        permissions=request.permissions,
        expires_in=ttl_seconds,
    )


# =============================================================================
# List User Delegations
# =============================================================================


class DelegationSummary(BaseModel):
    """Summary of a delegation for listing."""

    delegation_id: str
    agent_id: str
    permissions: List[str]
    expires_in: int
    created_at: Optional[str] = None
    status: str = "active"
    source: str = "manual"
    template_id: Optional[str] = None


@router.delete("/delegations/{delegation_id}")
def revoke_delegation(
    delegation_id: str,
    authorization: str = Header(...),
    db: Session = Depends(deps.get_db),
):
    """
    Revoke a delegation by setting its revoked_at timestamp.

    Only the delegator (the user who created it) can revoke it.
    """
    current_user = get_current_user_from_token(authorization)

    delegation = (
        db.query(DelegationToken)
        .filter(DelegationToken.id == delegation_id)
        .first()
    )

    if not delegation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Delegation not found",
        )

    if delegation.delegator != current_user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only revoke your own delegations",
        )

    if delegation.is_revoked:
        return {"detail": "Delegation already revoked", "delegation_id": delegation_id}

    delegation.revoke()
    db.commit()

    logger.info(
        "User %s revoked delegation %s for agent %s",
        current_user,
        delegation_id,
        delegation.agent_id,
    )

    return {"detail": "Delegation revoked", "delegation_id": delegation_id}


@router.get("/delegations", response_model=List[DelegationSummary])
def list_user_delegations(
    authorization: str = Header(...),
    db: Session = Depends(deps.get_db),
):
    """List all delegations created by the current user."""
    current_user = get_current_user_from_token(authorization)

    rows = (
        db.query(DelegationToken)
        .filter(
            DelegationToken.delegator == current_user,
            DelegationToken.revoked_at.is_(None),
        )
        .order_by(DelegationToken.created_at.desc())
        .all()
    )

    result = []
    for d in rows:
        expires_in = int((d.expires_at - d.created_at).total_seconds()) if d.expires_at and d.created_at else 28800
        result.append(
            DelegationSummary(
                delegation_id=d.id,
                agent_id=d.agent_id,
                permissions=d.delegated_permissions or [],
                expires_in=expires_in,
                created_at=d.created_at.isoformat() if d.created_at else None,
                status=d.status or "active",
                source=d.source or "manual",
                template_id=getattr(d, "template_id", None),
            )
        )
    return result


# =============================================================================
# PATCH Delegation (narrow permissions in place)
# =============================================================================


class PatchDelegationRequest(BaseModel):
    permissions: Optional[List[str]] = None
    constraints: Optional[Dict[str, Any]] = None
    expires_at: Optional[datetime] = None

    @model_validator(mode="after")
    def require_at_least_one_field(self) -> "PatchDelegationRequest":
        if (
            self.permissions is None
            and self.constraints is None
            and self.expires_at is None
        ):
            raise ValueError("At least one of permissions, constraints, or expires_at is required")
        return self


class PatchDelegationResponse(BaseModel):
    delegation_id: str
    agent_id: str
    permissions: List[str]
    source: str
    template_id: Optional[str] = None
    status: str
    expires_at: Optional[str] = None
    sessions_revoked: int


def build_patch_delegation_response(result: PatchDelegationResult) -> PatchDelegationResponse:
    delegation = result.delegation
    return PatchDelegationResponse(
        delegation_id=delegation.id,
        agent_id=delegation.agent_id,
        permissions=list(delegation.delegated_permissions or []),
        source=delegation.source or "manual",
        template_id=getattr(delegation, "template_id", None),
        status=delegation.status or "active",
        expires_at=delegation.expires_at.isoformat() if delegation.expires_at else None,
        sessions_revoked=result.sessions_revoked,
    )


def raise_patch_delegation_http_error(exc: Exception) -> None:
    if isinstance(exc, DelegationNotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Delegation not found")
    if isinstance(exc, DelegationForbiddenError):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    if isinstance(exc, DelegationInvalidStateError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    if isinstance(exc, PermissionWideningError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "permission_widening_not_allowed",
                "message": exc.message,
                "attempted": exc.attempted,
                "current": exc.current,
                "allowed_ceiling": exc.allowed_ceiling,
            },
        )
    if isinstance(exc, PermissionValidationError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "permission_validation_failed",
                "message": exc.message,
                "invalid_permissions": exc.invalid_permissions,
                "allowed_permissions": exc.allowed_permissions,
            },
        )
    raise exc


@user_delegations_router.patch(
    "/{delegation_id}",
    response_model=PatchDelegationResponse,
)
def patch_user_delegation(
    delegation_id: str,
    body: PatchDelegationRequest,
    authorization: str = Header(...),
    db: Session = Depends(deps.get_db),
):
    """Narrow an existing delegation's permissions (delegator only)."""
    current_user = get_current_user_from_token(authorization)
    service = DelegationService(db)
    try:
        result = service.patch_delegation_permissions(
            delegation_id,
            current_user,
            new_permissions=body.permissions,
            constraints=body.constraints,
            expires_at=body.expires_at,
        )
    except (
        DelegationNotFoundError,
        DelegationForbiddenError,
        DelegationInvalidStateError,
        PermissionWideningError,
        PermissionValidationError,
    ) as exc:
        raise_patch_delegation_http_error(exc)
    return build_patch_delegation_response(result)


# =============================================================================
# Accept Pending Delegation Invite
# =============================================================================


class AcceptDelegationResponse(BaseModel):
    delegation_id: str
    status: str
    permissions: List[str]
    agent_id: str


def build_accept_delegation_response(result: AcceptDelegationResult) -> AcceptDelegationResponse:
    delegation = result.delegation
    return AcceptDelegationResponse(
        delegation_id=delegation.id,
        status=delegation.status,
        permissions=list(delegation.delegated_permissions or []),
        agent_id=delegation.agent_id,
    )


def raise_accept_delegation_http_error(exc: Exception) -> None:
    if isinstance(exc, DelegationNotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Delegation not found")
    if isinstance(exc, DelegationForbiddenError):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    if isinstance(exc, DelegationNotPendingError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    if isinstance(exc, DelegationInvalidStateError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    if isinstance(exc, PermissionValidationError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "permission_validation_failed",
                "message": exc.message,
                "invalid_permissions": exc.invalid_permissions,
                "allowed_permissions": exc.allowed_permissions,
                "hint": "Connect required services before accepting this invite",
            },
        )
    raise exc


@user_delegations_router.post(
    "/{delegation_id}/accept",
    response_model=AcceptDelegationResponse,
)
def accept_user_delegation(
    delegation_id: str,
    authorization: str = Header(...),
    db: Session = Depends(deps.get_db),
):
    """Accept a pending delegation invite (delegator only)."""
    current_user = get_current_user_from_token(authorization)
    service = DelegationService(db)
    try:
        result = service.accept_delegation(delegation_id, current_user)
    except (
        DelegationNotFoundError,
        DelegationForbiddenError,
        DelegationNotPendingError,
        DelegationInvalidStateError,
        PermissionValidationError,
    ) as exc:
        raise_accept_delegation_http_error(exc)
    return build_accept_delegation_response(result)


# =============================================================================
# Public Delegation Templates (filtered by user role)
# =============================================================================


class PublicTemplateResponse(BaseModel):
    """Template summary visible to employees."""
    id: str
    agent_id: str
    max_permissions: List[str]
    blocked_permissions: List[str]
    default_ttl_days: int


class PublicTemplateListResponse(BaseModel):
    templates: List[PublicTemplateResponse]
    total: int


@router.get("/delegation-templates", response_model=PublicTemplateListResponse)
def list_user_delegation_templates(
    authorization: str = Header(...),
    db: Session = Depends(deps.get_db),
):
    """List delegation templates available to the current user."""
    from app.models.delegation_template import DelegationTemplate as DT
    from app.services.available_to import AvailableToEvaluator
    from app.services.role_resolver import RoleResolver

    user_claims = _parse_user_token(authorization)
    groups = user_claims.get("groups", [])
    if isinstance(groups, str):
        groups = [groups]
    roles = user_claims.get("roles", [])
    if isinstance(roles, str):
        roles = [roles]

    resolver = RoleResolver()
    evaluator = AvailableToEvaluator()
    user_ctx = resolver.resolve_context(
        sub=user_claims.get("sub", ""),
        jwt_roles=roles,
        groups=groups,
        db=db,
    )

    all_templates = db.query(DT).all()

    visible = []
    for t in all_templates:
        if evaluator.is_visible(
            t.available_to_roles,
            getattr(t, "available_to_groups", None),
            getattr(t, "available_to_users", None),
            user_ctx,
        ):
            visible.append(
                PublicTemplateResponse(
                    id=str(t.id),
                    agent_id=t.agent_id,
                    max_permissions=t.max_permissions or [],
                    blocked_permissions=t.blocked_permissions or [],
                    default_ttl_days=t.default_ttl_days or 7,
                )
            )

    return PublicTemplateListResponse(templates=visible, total=len(visible))


# =============================================================================
# Agent-to-Agent Delegation (Original Endpoint)
# =============================================================================


@router.post("/agent-delegate", response_model=schemas.DelegationResponse)
def delegate_access(
    *,
    delegation_in: schemas.DelegationRequest,
    current_agent: models.Agent = Depends(deps.get_current_active_agent),
):
    """
    Delegate access from one agent to another by minting a macaroon.

    This endpoint allows an authenticated agent to generate a temporary,
    scoped credential (a macaroon) and delegate it to another agent.
    """
    delegation_token = macaroon_service.mint_delegation_macaroon(
        target_agent_id=delegation_in.target_agent_id,
        resource=delegation_in.resource,
        permissions=delegation_in.permissions,
        ttl_seconds=delegation_in.ttl_seconds,
    )
    return {"delegation_token": delegation_token} 