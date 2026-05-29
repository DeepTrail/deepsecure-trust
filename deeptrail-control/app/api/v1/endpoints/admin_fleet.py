"""Admin fleet management, delegation template, and emergency control endpoints.

Implements:
  GET    /api/v1/admin/agents                            — List all agents cross-user
  POST   /api/v1/admin/agents/{agent_id}/suspend         — Suspend agent
  GET    /api/v1/admin/delegations                       — List all delegations
  POST   /api/v1/admin/delegations                       — Create delegation for user
  DELETE /api/v1/admin/delegations/{id}                  — Revoke delegation
  GET    /api/v1/admin/delegation-templates               — List templates
  POST   /api/v1/admin/delegation-templates               — Create template
  PATCH  /api/v1/admin/delegation-templates/{id}          — Update template
  DELETE /api/v1/admin/delegation-templates/{id}          — Delete template
  POST   /api/v1/admin/emergency/suspend-all              — Suspend all agents
  POST   /api/v1/admin/emergency/disable-delegations      — Revoke all delegations
  POST   /api/v1/admin/emergency/lockdown                 — Block all activity

All endpoints require admin role.
"""

import logging
from datetime import datetime, time, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.middleware.admin_auth import require_admin
from app.models.agent import Agent
from app.models.agent_session import AgentSession
from app.models.delegation import DelegationToken
from app.models.delegation_template import DelegationTemplate
from app.models.audit_event import AuditEvent

logger = logging.getLogger(__name__)

router = APIRouter()


# --- Request / Response Models ---

class AgentFleetResponse(BaseModel):
    agent_id: str
    name: Optional[str] = None
    delegator_count: int = 0
    active_sessions: int = 0
    status: str = "active"


class DelegationListResponse(BaseModel):
    id: str
    agent_id: str
    delegator: str
    delegated_permissions: Any
    source: str
    status: str
    created_at: Optional[str] = None
    expires_at: Optional[str] = None


class CreateDelegationRequest(BaseModel):
    agent_id: str
    delegator: str
    delegated_permissions: List[str]
    constraints: Dict[str, Any] = Field(default_factory=dict)
    source: str = "admin"


class TemplateCreateRequest(BaseModel):
    agent_id: str
    max_permissions: List[str]
    blocked_permissions: List[str] = Field(default_factory=list)
    default_ttl_days: int = 7
    available_to_roles: List[str] = Field(default=["all"])
    max_actions_per_day: Optional[int] = None
    working_hours_start: Optional[str] = None
    working_hours_end: Optional[str] = None


class TemplateUpdateRequest(BaseModel):
    max_permissions: Optional[List[str]] = None
    blocked_permissions: Optional[List[str]] = None
    default_ttl_days: Optional[int] = None
    available_to_roles: Optional[List[str]] = None
    max_actions_per_day: Optional[int] = None
    working_hours_start: Optional[str] = None
    working_hours_end: Optional[str] = None


class TemplateResponse(BaseModel):
    id: str
    agent_id: str
    max_permissions: Any
    blocked_permissions: Any
    default_ttl_days: int
    available_to_roles: Any
    max_actions_per_day: Optional[int] = None
    working_hours_start: Optional[str] = None
    working_hours_end: Optional[str] = None
    created_by: Optional[str] = None


class EmergencyResponse(BaseModel):
    action: str
    affected_count: int
    message: str


# --- Fleet Endpoints (D1, D2) ---

@router.get("/agents", response_model=List[AgentFleetResponse])
def list_agents_fleet(
    db: Session = Depends(get_db),
    _admin: dict = Depends(require_admin),
):
    """List all agents cross-user with delegation and session counts."""
    agents = db.query(Agent).all()
    result = []
    for agent in agents:
        del_count = (
            db.query(DelegationToken)
            .filter(
                DelegationToken.agent_id == agent.agent_id,
                DelegationToken.revoked_at.is_(None),
            )
            .count()
        )
        session_count = (
            db.query(AgentSession)
            .filter(
                AgentSession.agent_id == agent.agent_id,
                AgentSession.revoked_at.is_(None),
            )
            .count()
        )
        result.append(AgentFleetResponse(
            agent_id=agent.agent_id,
            name=getattr(agent, "name", None),
            delegator_count=del_count,
            active_sessions=session_count,
        ))
    return result


@router.post("/agents/{agent_id}/suspend", response_model=EmergencyResponse)
def suspend_agent(
    agent_id: str,
    db: Session = Depends(get_db),
    admin_claims: dict = Depends(require_admin),
):
    """Suspend a specific agent — revoke all sessions and delegations."""
    now = datetime.now(timezone.utc)

    sessions_revoked = (
        db.query(AgentSession)
        .filter(AgentSession.agent_id == agent_id, AgentSession.revoked_at.is_(None))
        .update({"revoked_at": now})
    )
    delegations_revoked = (
        db.query(DelegationToken)
        .filter(DelegationToken.agent_id == agent_id, DelegationToken.revoked_at.is_(None))
        .update({"revoked_at": now})
    )

    db.add(AuditEvent(
        event_type="agent_suspended",
        agent_id=agent_id,
        on_behalf_of=admin_claims.get("sub", "admin"),
        success=True,
        extra_data={"sessions_revoked": sessions_revoked, "delegations_revoked": delegations_revoked},
    ))
    db.commit()

    return EmergencyResponse(
        action="suspend_agent",
        affected_count=sessions_revoked + delegations_revoked,
        message=f"Agent '{agent_id}' suspended. {sessions_revoked} sessions, {delegations_revoked} delegations revoked.",
    )


# --- Delegation Endpoints (D3, D4) ---

@router.get("/delegations", response_model=List[DelegationListResponse])
def list_delegations(
    agent_id: Optional[str] = None,
    delegator: Optional[str] = None,
    db: Session = Depends(get_db),
    _admin: dict = Depends(require_admin),
):
    """List all delegations, optionally filtered."""
    q = db.query(DelegationToken)
    if agent_id:
        q = q.filter(DelegationToken.agent_id == agent_id)
    if delegator:
        q = q.filter(DelegationToken.delegator == delegator)
    delegations = q.order_by(DelegationToken.created_at.desc()).all()

    return [
        DelegationListResponse(
            id=d.id,
            agent_id=d.agent_id,
            delegator=d.delegator,
            delegated_permissions=d.delegated_permissions,
            source=getattr(d, "source", "manual"),
            status="revoked" if d.revoked_at else ("expired" if d.is_expired else "active"),
            created_at=d.created_at.isoformat() if d.created_at else None,
            expires_at=d.expires_at.isoformat() if d.expires_at else None,
        )
        for d in delegations
    ]


@router.post("/delegations", response_model=DelegationListResponse, status_code=201)
def create_delegation_admin(
    body: CreateDelegationRequest,
    db: Session = Depends(get_db),
    admin_claims: dict = Depends(require_admin),
):
    """Create a delegation on behalf of a user (admin action)."""
    from datetime import timedelta

    delegation = DelegationToken(
        agent_id=body.agent_id,
        delegator=body.delegator,
        delegated_permissions=body.delegated_permissions,
        constraints=body.constraints,
        source="admin",
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    db.add(delegation)
    db.commit()
    db.refresh(delegation)

    return DelegationListResponse(
        id=delegation.id,
        agent_id=delegation.agent_id,
        delegator=delegation.delegator,
        delegated_permissions=delegation.delegated_permissions,
        source="admin",
        status="active",
        created_at=delegation.created_at.isoformat() if delegation.created_at else None,
        expires_at=delegation.expires_at.isoformat() if delegation.expires_at else None,
    )


@router.delete("/delegations/{delegation_id}", status_code=204)
def revoke_delegation_admin(
    delegation_id: str,
    db: Session = Depends(get_db),
    _admin: dict = Depends(require_admin),
):
    delegation = db.query(DelegationToken).filter(DelegationToken.id == delegation_id).first()
    if not delegation:
        raise HTTPException(status_code=404, detail="Delegation not found")
    delegation.revoked_at = datetime.now(timezone.utc)
    db.commit()


# --- Delegation Template Endpoints (D3) ---

@router.get("/delegation-templates", response_model=List[TemplateResponse])
def list_templates(
    db: Session = Depends(get_db),
    _admin: dict = Depends(require_admin),
):
    templates = db.query(DelegationTemplate).all()
    return [
        TemplateResponse(
            id=str(t.id),
            agent_id=t.agent_id,
            max_permissions=t.max_permissions,
            blocked_permissions=t.blocked_permissions,
            default_ttl_days=t.default_ttl_days or 7,
            available_to_roles=t.available_to_roles,
            max_actions_per_day=t.max_actions_per_day,
            working_hours_start=str(t.working_hours_start) if t.working_hours_start else None,
            working_hours_end=str(t.working_hours_end) if t.working_hours_end else None,
            created_by=t.created_by,
        )
        for t in templates
    ]


@router.post("/delegation-templates", response_model=TemplateResponse, status_code=201)
def create_template(
    body: TemplateCreateRequest,
    db: Session = Depends(get_db),
    admin_claims: dict = Depends(require_admin),
):
    wh_start = time.fromisoformat(body.working_hours_start) if body.working_hours_start else None
    wh_end = time.fromisoformat(body.working_hours_end) if body.working_hours_end else None

    template = DelegationTemplate(
        agent_id=body.agent_id,
        max_permissions=body.max_permissions,
        blocked_permissions=body.blocked_permissions,
        default_ttl_days=body.default_ttl_days,
        available_to_roles=body.available_to_roles,
        max_actions_per_day=body.max_actions_per_day,
        working_hours_start=wh_start,
        working_hours_end=wh_end,
        created_by=admin_claims.get("sub"),
    )
    db.add(template)
    db.commit()
    db.refresh(template)

    return TemplateResponse(
        id=str(template.id),
        agent_id=template.agent_id,
        max_permissions=template.max_permissions,
        blocked_permissions=template.blocked_permissions,
        default_ttl_days=template.default_ttl_days or 7,
        available_to_roles=template.available_to_roles,
        max_actions_per_day=template.max_actions_per_day,
        working_hours_start=str(template.working_hours_start) if template.working_hours_start else None,
        working_hours_end=str(template.working_hours_end) if template.working_hours_end else None,
        created_by=template.created_by,
    )


@router.patch("/delegation-templates/{template_id}", response_model=TemplateResponse)
def update_template(
    template_id: str,
    body: TemplateUpdateRequest,
    db: Session = Depends(get_db),
    _admin: dict = Depends(require_admin),
):
    template = db.query(DelegationTemplate).filter(DelegationTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    updates = body.model_dump(exclude_none=True)
    for key, value in updates.items():
        if key == "working_hours_start" and value:
            setattr(template, key, time.fromisoformat(value))
        elif key == "working_hours_end" and value:
            setattr(template, key, time.fromisoformat(value))
        elif hasattr(template, key):
            setattr(template, key, value)

    template.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(template)

    return TemplateResponse(
        id=str(template.id),
        agent_id=template.agent_id,
        max_permissions=template.max_permissions,
        blocked_permissions=template.blocked_permissions,
        default_ttl_days=template.default_ttl_days or 7,
        available_to_roles=template.available_to_roles,
        max_actions_per_day=template.max_actions_per_day,
        working_hours_start=str(template.working_hours_start) if template.working_hours_start else None,
        working_hours_end=str(template.working_hours_end) if template.working_hours_end else None,
        created_by=template.created_by,
    )


@router.delete("/delegation-templates/{template_id}", status_code=204)
def delete_template(
    template_id: str,
    db: Session = Depends(get_db),
    _admin: dict = Depends(require_admin),
):
    template = db.query(DelegationTemplate).filter(DelegationTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    db.delete(template)
    db.commit()


# --- Emergency Endpoints (D5) ---

@router.post("/emergency/suspend-all", response_model=EmergencyResponse)
def emergency_suspend_all(
    db: Session = Depends(get_db),
    admin_claims: dict = Depends(require_admin),
):
    """Suspend all agents — revoke all active sessions."""
    now = datetime.now(timezone.utc)
    count = db.query(AgentSession).filter(AgentSession.revoked_at.is_(None)).update({"revoked_at": now})

    db.add(AuditEvent(
        event_type="emergency_suspend_all",
        on_behalf_of=admin_claims.get("sub", "admin"),
        success=True,
        extra_data={"sessions_revoked": count},
    ))
    db.commit()

    return EmergencyResponse(
        action="suspend_all",
        affected_count=count,
        message=f"All agents suspended. {count} sessions revoked.",
    )


@router.post("/emergency/disable-delegations", response_model=EmergencyResponse)
def emergency_disable_delegations(
    db: Session = Depends(get_db),
    admin_claims: dict = Depends(require_admin),
):
    """Revoke all active delegations."""
    now = datetime.now(timezone.utc)
    count = db.query(DelegationToken).filter(DelegationToken.revoked_at.is_(None)).update({"revoked_at": now})

    db.add(AuditEvent(
        event_type="emergency_disable_delegations",
        on_behalf_of=admin_claims.get("sub", "admin"),
        success=True,
        extra_data={"delegations_revoked": count},
    ))
    db.commit()

    return EmergencyResponse(
        action="disable_delegations",
        affected_count=count,
        message=f"All delegations disabled. {count} revoked.",
    )


@router.post("/emergency/lockdown", response_model=EmergencyResponse)
def emergency_lockdown(
    db: Session = Depends(get_db),
    admin_claims: dict = Depends(require_admin),
):
    """Full lockdown — suspend all agents AND revoke all delegations."""
    now = datetime.now(timezone.utc)
    sessions = db.query(AgentSession).filter(AgentSession.revoked_at.is_(None)).update({"revoked_at": now})
    delegations = db.query(DelegationToken).filter(DelegationToken.revoked_at.is_(None)).update({"revoked_at": now})

    db.add(AuditEvent(
        event_type="emergency_lockdown",
        on_behalf_of=admin_claims.get("sub", "admin"),
        success=True,
        extra_data={"sessions_revoked": sessions, "delegations_revoked": delegations},
    ))
    db.commit()

    return EmergencyResponse(
        action="lockdown",
        affected_count=sessions + delegations,
        message=f"Lockdown active. {sessions} sessions + {delegations} delegations revoked.",
    )
