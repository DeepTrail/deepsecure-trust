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
from app.models.user_session import UserSession
from app.models.task_token import Task, TaskStatus
from app.services.lifecycle_service import LifecycleService


def _ensure_tz(dt: Optional[datetime]) -> Optional[datetime]:
    """Ensure a datetime is timezone-aware (SQLite returns naive datetimes)."""
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

logger = logging.getLogger(__name__)

router = APIRouter()


# --- Request / Response Models ---

class DelegationSummary(BaseModel):
    id: str
    delegator: str
    permissions: List[str]
    services: List[str] = Field(default_factory=list)
    created_at: Optional[str] = None
    expires_at: Optional[str] = None
    is_expired: bool = False


class SessionSummary(BaseModel):
    session_id: str
    created_at: Optional[str] = None
    last_activity_at: Optional[str] = None
    delegator: Optional[str] = None
    delegation_id: Optional[str] = None
    tool_calls: int = 0
    status: str = "active"


class ConnectedServiceSummary(BaseModel):
    service_id: str
    display_name: str
    status: str = "connected"
    scopes_granted: List[str] = Field(default_factory=list)


class DelegatorSummary(BaseModel):
    email: str
    connected_services: List[ConnectedServiceSummary] = Field(default_factory=list)
    active_delegation: Optional[DelegationSummary] = None
    delegation_count: int = 0


class SessionEventSummary(BaseModel):
    id: str
    tool: Optional[str] = None
    event_type: str
    success: Optional[bool] = None
    timestamp: str
    result_summary: Optional[str] = None


class SessionEventsResponse(BaseModel):
    events: List[SessionEventSummary]
    total: int


class AgentFleetEntry(BaseModel):
    agent_id: str
    name: str = ""
    status: str = "active"
    public_key: Optional[str] = None
    platform: Optional[str] = None
    selector: Optional[str] = None
    auth_method: str = "ed25519"
    created_at: Optional[str] = None
    last_active_at: Optional[str] = None
    delegation_count: int = 0
    delegating_users: List[str] = Field(default_factory=list)
    active_sessions: int = 0
    delegations: List[DelegationSummary] = Field(default_factory=list)
    sessions: List[SessionSummary] = Field(default_factory=list)
    delegators: List[DelegatorSummary] = Field(default_factory=list)


class AgentFleetResponse(BaseModel):
    agents: List[AgentFleetEntry]
    total: int


class DelegationListResponse(BaseModel):
    id: str
    agent_id: str
    delegator: str
    delegated_permissions: Any
    source: str
    status: str
    created_at: Optional[str] = None
    expires_at: Optional[str] = None
    revoked_at: Optional[str] = None
    template_id: Optional[str] = None


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
    available_to_groups: List[str] = Field(default_factory=list)
    available_to_users: List[str] = Field(default_factory=list)
    max_actions_per_day: Optional[int] = None
    working_hours_start: Optional[str] = None
    working_hours_end: Optional[str] = None


class TemplateUpdateRequest(BaseModel):
    max_permissions: Optional[List[str]] = None
    blocked_permissions: Optional[List[str]] = None
    default_ttl_days: Optional[int] = None
    available_to_roles: Optional[List[str]] = None
    available_to_groups: Optional[List[str]] = None
    available_to_users: Optional[List[str]] = None
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
    available_to_groups: Any = Field(default_factory=list)
    available_to_users: Any = Field(default_factory=list)
    max_actions_per_day: Optional[int] = None
    working_hours_start: Optional[str] = None
    working_hours_end: Optional[str] = None
    created_by: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class DelegationListWrapper(BaseModel):
    delegations: List[DelegationListResponse]
    total: int


class TemplateListWrapper(BaseModel):
    templates: List[TemplateResponse]
    total: int


class EmergencyResponse(BaseModel):
    action: str
    agents_affected: int = 0
    delegations_revoked: int = 0
    affected_count: int
    executed_by: str = ""
    timestamp: str = ""
    message: str


# --- Fleet Endpoints (D1, D2) ---

@router.get("/agents", response_model=AgentFleetResponse)
def list_agents_fleet(
    db: Session = Depends(get_db),
    _admin: dict = Depends(require_admin),
):
    """List all agents cross-user with delegation and session counts."""
    import base64
    from sqlalchemy import func as sa_func
    from app.models.connected_service import ConnectedService

    agents = db.query(Agent).all()
    lifecycle_svc = LifecycleService(db)
    agent_ids = [a.agent_id for a in agents]
    lifecycle_states = lifecycle_svc.compute_state_bulk(agent_ids) if agent_ids else {}

    entries: List[AgentFleetEntry] = []
    for agent in agents:
        delegations = (
            db.query(DelegationToken)
            .filter(
                DelegationToken.agent_id == agent.agent_id,
                DelegationToken.revoked_at.is_(None),
            )
            .all()
        )
        session_count = (
            db.query(AgentSession)
            .filter(
                AgentSession.agent_id == agent.agent_id,
                AgentSession.revoked_at.is_(None),
            )
            .count()
        )
        delegating_users = list({d.delegator for d in delegations if d.delegator})

        pub_key_str = None
        if agent.public_key:
            try:
                pub_key_str = base64.b64encode(agent.public_key).decode()
            except Exception:
                pub_key_str = None

        last_active = lifecycle_svc.get_last_active_at(agent.agent_id)
        state = lifecycle_states.get(agent.agent_id, "registered")

        auth_method = "workload_identity" if agent.platform else ("ed25519" if agent.public_key else "unknown")

        now = datetime.now(timezone.utc)
        delegation_summaries = []
        for d in delegations:
            exp = _ensure_tz(d.expires_at)
            is_exp = bool(exp and now > exp)
            perms = d.delegated_permissions if isinstance(d.delegated_permissions, list) else []
            services = sorted({p.split(":")[0] for p in perms if ":" in p})
            delegation_summaries.append(DelegationSummary(
                id=d.id,
                delegator=d.delegator or "",
                permissions=perms,
                services=services,
                created_at=d.created_at.isoformat() if d.created_at else None,
                expires_at=exp.isoformat() if exp else None,
                is_expired=is_exp,
            ))

        sessions = (
            db.query(AgentSession)
            .filter(
                AgentSession.agent_id == agent.agent_id,
                AgentSession.revoked_at.is_(None),
            )
            .order_by(AgentSession.last_activity_at.desc().nullslast())
            .limit(10)
            .all()
        )

        session_ids = [s.id for s in sessions]
        tool_call_counts: Dict[str, int] = {}
        if session_ids:
            rows = (
                db.query(AuditEvent.agent_session_id, sa_func.count(AuditEvent.id))
                .filter(AuditEvent.agent_session_id.in_(session_ids))
                .group_by(AuditEvent.agent_session_id)
                .all()
            )
            tool_call_counts = dict(rows)

        session_summaries = []
        for s in sessions:
            s_expired = bool(s.expires_at and now > _ensure_tz(s.expires_at))
            session_summaries.append(SessionSummary(
                session_id=s.id,
                created_at=s.created_at.isoformat() if s.created_at else None,
                last_activity_at=s.last_activity_at.isoformat() if s.last_activity_at else None,
                delegator=s.owner_email,
                delegation_id=s.delegation_id,
                tool_calls=tool_call_counts.get(s.id, 0),
                status="expired" if s_expired else "active",
            ))

        # Build delegators with connected services (batched query)
        delegator_summaries: List[DelegatorSummary] = []
        if delegating_users:
            all_connected = (
                db.query(ConnectedService)
                .filter(
                    ConnectedService.user_id.in_(delegating_users),
                    ConnectedService.disconnected_at.is_(None),
                )
                .all()
            )
            connected_by_user: Dict[str, List[ConnectedService]] = {}
            for cs in all_connected:
                connected_by_user.setdefault(cs.user_id, []).append(cs)

            for email in sorted(delegating_users):
                user_delegations = [d for d in delegations if d.delegator == email]
                active_del = next(
                    (d for d in user_delegations if not (_ensure_tz(d.expires_at) and now > _ensure_tz(d.expires_at))),
                    None,
                )
                user_connected = connected_by_user.get(email, [])
                cs_summaries = [
                    ConnectedServiceSummary(
                        service_id=cs.service_id,
                        display_name=cs.service_name or cs.service_id,
                        status="connected",
                        scopes_granted=cs.scopes_granted if isinstance(cs.scopes_granted, list) else [],
                    )
                    for cs in user_connected
                ]

                active_del_summary = None
                if active_del:
                    perms = active_del.delegated_permissions if isinstance(active_del.delegated_permissions, list) else []
                    active_del_summary = DelegationSummary(
                        id=active_del.id,
                        delegator=active_del.delegator or "",
                        permissions=perms,
                        services=sorted({p.split(":")[0] for p in perms if ":" in p}),
                        created_at=active_del.created_at.isoformat() if active_del.created_at else None,
                        expires_at=active_del.expires_at.isoformat() if active_del.expires_at else None,
                        is_expired=False,
                    )

                delegator_summaries.append(DelegatorSummary(
                    email=email,
                    connected_services=cs_summaries,
                    active_delegation=active_del_summary,
                    delegation_count=len(user_delegations),
                ))

        entries.append(AgentFleetEntry(
            agent_id=agent.agent_id,
            name=agent.name or agent.agent_id,
            status=state,
            public_key=pub_key_str,
            platform=agent.platform,
            selector=agent.selector,
            auth_method=auth_method,
            created_at=agent.created_at.isoformat() if agent.created_at else None,
            last_active_at=last_active.isoformat() if last_active else None,
            delegation_count=len(delegations),
            delegating_users=delegating_users,
            active_sessions=session_count,
            delegations=delegation_summaries,
            sessions=session_summaries,
            delegators=delegator_summaries,
        ))
    return AgentFleetResponse(agents=entries, total=len(entries))


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
        agents_affected=1,
        delegations_revoked=delegations_revoked,
        affected_count=sessions_revoked + delegations_revoked,
        executed_by=admin_claims.get("sub", "admin"),
        timestamp=now.isoformat(),
        message=f"Agent '{agent_id}' suspended. {sessions_revoked} sessions, {delegations_revoked} delegations revoked.",
    )


# --- Session Events Endpoint ---

@router.get("/agents/{agent_id}/sessions/{session_id}/events", response_model=SessionEventsResponse)
def get_session_events(
    agent_id: str,
    session_id: str,
    db: Session = Depends(get_db),
    _admin: dict = Depends(require_admin),
):
    """Get audit events for a specific agent session (lazy-loaded on UI expand)."""
    events = (
        db.query(AuditEvent)
        .filter(
            AuditEvent.agent_id == agent_id,
            AuditEvent.agent_session_id == session_id,
        )
        .order_by(AuditEvent.timestamp.asc())
        .limit(50)
        .all()
    )
    items = [
        SessionEventSummary(
            id=e.id,
            tool=e.tool,
            event_type=e.event_type,
            success=e.success,
            timestamp=e.timestamp.isoformat() if e.timestamp else "",
            result_summary=e.result_summary,
        )
        for e in events
    ]
    return SessionEventsResponse(events=items, total=len(items))


# --- Identity Stack Endpoint ---

class IdentityStackItem(BaseModel):
    id: str
    status: str
    created_at: Optional[str] = None
    expires_at: Optional[str] = None


class UserSessionStackItem(IdentityStackItem):
    user: str
    idp: Optional[str] = None


class DelegationStackItem(IdentityStackItem):
    delegator: str
    permissions_count: int
    services: List[str]


class AgentSessionStackItem(IdentityStackItem):
    session_id: str
    delegator: str
    delegation_id: str


class TaskTokenStackItem(IdentityStackItem):
    agent_session_id: Optional[str] = None
    scoped_permissions_count: int = 0
    task_status: str = "pending"


class IdentityStackLayer(BaseModel):
    type: str
    description: str
    count: int
    active: int
    items: List[dict] = Field(default_factory=list)


class IdentityStackResponse(BaseModel):
    agent_id: str
    layers: List[IdentityStackLayer]


@router.get("/agents/{agent_id}/identity-stack", response_model=IdentityStackResponse)
def get_identity_stack(
    agent_id: str,
    session_limit: int = 10,
    session_offset: int = 0,
    db: Session = Depends(get_db),
    _admin: dict = Depends(require_admin),
):
    """Get the 5-layer identity stack for an agent."""
    now = datetime.now(timezone.utc)

    # Layer 1: User ID-Token (always empty — external IdP tokens not stored)
    layer_id_token = IdentityStackLayer(
        type="User ID-Token",
        description="OIDC JWT from identity provider (Google, Keycloak). Consumed during login, not stored by DeepSecure.",
        count=0,
        active=0,
        items=[],
    )

    # Layer 2: User Session — sessions for users who delegated to this agent
    delegations = (
        db.query(DelegationToken)
        .filter(
            DelegationToken.agent_id == agent_id,
            DelegationToken.revoked_at.is_(None),
        )
        .all()
    )
    delegator_emails = list({d.delegator for d in delegations if d.delegator})

    user_sessions_items = []
    if delegator_emails:
        u_sessions = (
            db.query(UserSession)
            .filter(UserSession.user_id.in_(delegator_emails))
            .order_by(UserSession.created_at.desc())
            .all()
        )
        for us in u_sessions:
            exp = _ensure_tz(us.expires_at)
            is_exp = bool(exp and now > exp)
            is_rev = us.revoked_at is not None
            st = "revoked" if is_rev else ("expired" if is_exp else "active")
            user_sessions_items.append(UserSessionStackItem(
                id=us.session_id,
                user=us.user_id,
                idp=us.idp_issuer.split("/")[-1] if us.idp_issuer and "/" in us.idp_issuer else us.idp_issuer,
                created_at=us.created_at.isoformat() if us.created_at else None,
                expires_at=exp.isoformat() if exp else None,
                status=st,
            ).model_dump())

    active_user_sessions = sum(1 for i in user_sessions_items if i["status"] == "active")
    layer_user_session = IdentityStackLayer(
        type="User Session",
        description="Console/API session for delegating users",
        count=len(user_sessions_items),
        active=active_user_sessions,
        items=user_sessions_items,
    )

    # Layer 3: Delegation
    delegation_items = []
    for d in delegations:
        exp = _ensure_tz(d.expires_at)
        is_exp = bool(exp and now > exp)
        perms = d.delegated_permissions if isinstance(d.delegated_permissions, list) else []
        services = sorted({p.split(":")[0] for p in perms if ":" in p})
        delegation_items.append(DelegationStackItem(
            id=d.id,
            delegator=d.delegator or "",
            permissions_count=len(perms),
            services=services,
            created_at=d.created_at.isoformat() if d.created_at else None,
            expires_at=exp.isoformat() if exp else None,
            status="expired" if is_exp else "active",
        ).model_dump())

    active_delegations = sum(1 for i in delegation_items if i["status"] == "active")
    layer_delegation = IdentityStackLayer(
        type="Delegation",
        description="User → agent permission grants",
        count=len(delegation_items),
        active=active_delegations,
        items=delegation_items,
    )

    # Layer 4: Agent Session — with pagination
    total_agent_sessions = (
        db.query(AgentSession)
        .filter(
            AgentSession.agent_id == agent_id,
            AgentSession.revoked_at.is_(None),
        )
        .count()
    )
    a_sessions = (
        db.query(AgentSession)
        .filter(
            AgentSession.agent_id == agent_id,
            AgentSession.revoked_at.is_(None),
        )
        .order_by(AgentSession.created_at.desc())
        .offset(session_offset)
        .limit(session_limit)
        .all()
    )
    agent_session_items = []
    for s in a_sessions:
        exp = _ensure_tz(s.expires_at)
        is_exp = bool(exp and now > exp)
        is_act = bool(s.is_active) and not is_exp
        agent_session_items.append(AgentSessionStackItem(
            id=s.id,
            session_id=s.id,
            delegator=s.owner_email or "",
            delegation_id=s.delegation_id or "",
            created_at=s.created_at.isoformat() if s.created_at else None,
            expires_at=exp.isoformat() if exp else None,
            status="active" if is_act else "expired",
        ).model_dump())

    active_agent_sessions = (
        db.query(AgentSession)
        .filter(
            AgentSession.agent_id == agent_id,
            AgentSession.revoked_at.is_(None),
            AgentSession.is_active.is_(True),
        )
        .count()
    )
    layer_agent_session = IdentityStackLayer(
        type="Agent Session",
        description="Authenticated agent sessions with delegated permissions",
        count=total_agent_sessions,
        active=active_agent_sessions,
        items=agent_session_items,
    )

    # Layer 5: Task Token
    try:
        tasks = (
            db.query(Task)
            .filter(
                Task.agent_id == agent_id,
                Task.status.notin_(list(TaskStatus.TERMINAL)),
            )
            .order_by(Task.created_at.desc())
            .all()
        )
        total_tasks = len(tasks)
        task_items = []
        for t in tasks:
            perms = t.scoped_permissions if isinstance(t.scoped_permissions, list) else []
            task_items.append(TaskTokenStackItem(
                id=t.id,
                agent_session_id=t.delegation_id,
                scoped_permissions_count=len(perms),
                task_status=t.status,
                created_at=t.created_at.isoformat() if t.created_at else None,
                expires_at=t.deadline.isoformat() if t.deadline else None,
                status="active" if t.status in TaskStatus.ACTIVE_STATES else "expired",
            ).model_dump())
        active_tasks = sum(1 for t in tasks if t.status in TaskStatus.ACTIVE_STATES)
    except Exception:
        task_items = []
        total_tasks = 0
        active_tasks = 0

    layer_task_token = IdentityStackLayer(
        type="Task Token",
        description="Per-task scoped permissions (narrowest scope)",
        count=total_tasks,
        active=active_tasks,
        items=task_items,
    )

    return IdentityStackResponse(
        agent_id=agent_id,
        layers=[
            layer_id_token,
            layer_user_session,
            layer_delegation,
            layer_agent_session,
            layer_task_token,
        ],
    )


# --- Delegation Endpoints (D3, D4) ---

@router.get("/delegations", response_model=DelegationListWrapper)
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

    items = [
        DelegationListResponse(
            id=d.id,
            agent_id=d.agent_id,
            delegator=d.delegator,
            delegated_permissions=d.delegated_permissions,
            source=getattr(d, "source", "manual"),
            status="revoked" if d.revoked_at else ("expired" if d.is_expired else "active"),
            created_at=d.created_at.isoformat() if d.created_at else None,
            expires_at=d.expires_at.isoformat() if d.expires_at else None,
            revoked_at=d.revoked_at.isoformat() if d.revoked_at else None,
            template_id=getattr(d, "template_id", None),
        )
        for d in delegations
    ]
    return DelegationListWrapper(delegations=items, total=len(items))


@router.post("/delegations", response_model=DelegationListResponse, status_code=201)
def create_delegation_admin(
    body: CreateDelegationRequest,
    db: Session = Depends(get_db),
    admin_claims: dict = Depends(require_admin),
):
    """Create a delegation on behalf of a user (admin action)."""
    from datetime import timedelta

    ttl_hours = body.constraints.get("expires_in_hours", 168)  # default 7 days
    delegation = DelegationToken(
        agent_id=body.agent_id,
        delegator=body.delegator,
        delegated_permissions=body.delegated_permissions,
        constraints=body.constraints,
        source="admin",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=ttl_hours),
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

@router.get("/delegation-templates", response_model=TemplateListWrapper)
def list_templates(
    db: Session = Depends(get_db),
    _admin: dict = Depends(require_admin),
):
    templates = db.query(DelegationTemplate).all()
    items = [
        TemplateResponse(
            id=str(t.id),
            agent_id=t.agent_id,
            max_permissions=t.max_permissions,
            blocked_permissions=t.blocked_permissions,
            default_ttl_days=t.default_ttl_days or 7,
            available_to_roles=t.available_to_roles,
            available_to_groups=t.available_to_groups or [],
            available_to_users=t.available_to_users or [],
            max_actions_per_day=t.max_actions_per_day,
            working_hours_start=str(t.working_hours_start) if t.working_hours_start else None,
            working_hours_end=str(t.working_hours_end) if t.working_hours_end else None,
            created_by=t.created_by,
            created_at=t.created_at.isoformat() if t.created_at else None,
            updated_at=t.updated_at.isoformat() if t.updated_at else None,
        )
        for t in templates
    ]
    return TemplateListWrapper(templates=items, total=len(items))


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
        available_to_groups=body.available_to_groups,
        available_to_users=body.available_to_users,
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
        available_to_groups=template.available_to_groups or [],
        available_to_users=template.available_to_users or [],
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
        available_to_groups=template.available_to_groups or [],
        available_to_users=template.available_to_users or [],
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
        agents_affected=count,
        delegations_revoked=0,
        affected_count=count,
        executed_by=admin_claims.get("sub", "admin"),
        timestamp=now.isoformat(),
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
        agents_affected=0,
        delegations_revoked=count,
        affected_count=count,
        executed_by=admin_claims.get("sub", "admin"),
        timestamp=now.isoformat(),
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
        agents_affected=sessions,
        delegations_revoked=delegations,
        affected_count=sessions + delegations,
        executed_by=admin_claims.get("sub", "admin"),
        timestamp=now.isoformat(),
        message=f"Lockdown active. {sessions} sessions + {delegations} delegations revoked.",
    )
