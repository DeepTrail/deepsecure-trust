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

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.v1.endpoints.delegation import (
    PatchDelegationRequest,
    PatchDelegationResponse,
    build_patch_delegation_response,
    raise_patch_delegation_http_error,
)
from app.middleware.admin_auth import require_admin
from app.services.delegation_service import (
    DelegationForbiddenError,
    DelegationInvalidStateError,
    DelegationNotFoundError,
    DelegationService,
    PermissionValidationError,
    PermissionWideningError,
)
from app.core.config import settings
from app.models.agent import Agent
from app.models.agent_session import AgentSession
from app.models.delegation import DelegationToken
from app.models.delegation_template import DelegationTemplate
from app.models.audit_event import AuditEvent
from app.models.user_session import UserSession
from app.models.task_token import Task, TaskStatus
from app.models.idp_session import IdPSession
from app.models.org_directory import OrgDirectory
from app.services.lifecycle_service import LifecycleService
from app.services.scope_mapper import ScopeMapper
from app.models.service_registry import ServiceRegistry
from app.schemas.agent import ProvisionRequest


def _ensure_tz(dt: Optional[datetime]) -> Optional[datetime]:
    """Ensure a datetime is timezone-aware (SQLite returns naive datetimes)."""
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

logger = logging.getLogger(__name__)

router = APIRouter()


def _validate_permission_strings(
    permissions: list[str],
    db: Session,
) -> list[str]:
    """Validate that each permission string is a known permission.

    Returns list of invalid permission strings.  A permission is valid if it
    appears in ScopeMapper (any service, any scope) OR in the ``permission_map``
    of an active MCP service in the service_registry.
    """
    if not permissions:
        return []

    known: set[str] = set()
    for service_id in ScopeMapper.get_supported_services():
        known.update(ScopeMapper.get_all_permissions_for_service(service_id))

    mcp_services = (
        db.query(ServiceRegistry)
        .filter(
            ServiceRegistry.backend_type == "mcp",
            ServiceRegistry.status == "active",
        )
        .all()
    )
    for svc in mcp_services:
        if svc.permission_map:
            pmap = svc.permission_map if isinstance(svc.permission_map, dict) else {}
            known.update(pmap.values())

    return [p for p in permissions if p not in known]


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


LIFECYCLE_STATES = frozenset({"registered", "delegated", "authenticated", "active"})


class FleetSummary(BaseModel):
    total_agents: int = 0
    delegating_users: int = 0
    active: int = 0
    authenticated: int = 0
    delegated: int = 0
    registered: int = 0


class AgentFleetEntry(BaseModel):
    agent_id: str
    name: str = ""
    status: str = "active"
    lifecycle_state: str = "registered"
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
    summary: FleetSummary = Field(default_factory=FleetSummary)


def _matches_fleet_filters(
    entry: AgentFleetEntry,
    lifecycle_state: Optional[str],
    user_id: Optional[str],
    service: Optional[str],
    q: Optional[str],
) -> bool:
    if lifecycle_state and entry.lifecycle_state != lifecycle_state:
        return False
    if user_id:
        uid = user_id.lower()
        if not any(u.lower() == uid for u in entry.delegating_users):
            if not any(d.delegator.lower() == uid for d in entry.delegations):
                return False
    if service:
        svc = service.lower()
        has_perm = any(
            svc in (p.split(":")[0].lower() if ":" in p else "")
            for d in entry.delegations
            for p in (d.permissions or [])
        )
        has_connected = any(
            cs.service_id.lower() == svc
            for delegator in entry.delegators
            for cs in delegator.connected_services
        )
        if not has_perm and not has_connected:
            return False
    if q:
        needle = q.lower()
        if needle not in entry.agent_id.lower() and needle not in entry.name.lower():
            return False
    return True


def _compute_fleet_summary(entries: List[AgentFleetEntry]) -> FleetSummary:
    delegators: set[str] = set()
    counts = {state: 0 for state in LIFECYCLE_STATES}
    for entry in entries:
        counts[entry.lifecycle_state] = counts.get(entry.lifecycle_state, 0) + 1
        delegators.update(entry.delegating_users)
    return FleetSummary(
        total_agents=len(entries),
        delegating_users=len(delegators),
        active=counts.get("active", 0),
        authenticated=counts.get("authenticated", 0),
        delegated=counts.get("delegated", 0),
        registered=counts.get("registered", 0),
    )


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
    auto_provision: Optional[bool] = None
    provision_mode: Optional[str] = None


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
    auto_provision: bool = False
    provision_mode: str = "off"
    created_by: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class TemplateInviteRequest(BaseModel):
    user_emails: List[str] = Field(..., min_length=1)


class TemplateInviteResponse(BaseModel):
    invited: int
    delegation_ids: List[str]
    skipped: List[str] = Field(default_factory=list)


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
    lifecycle_state: Optional[str] = Query(None, description="Filter by lifecycle state"),
    user_id: Optional[str] = Query(None, description="Filter by delegating user email"),
    service: Optional[str] = Query(None, description="Filter by service_id"),
    q: Optional[str] = Query(None, description="Search agent id or name"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _admin: dict = Depends(require_admin),
):
    """List all agents cross-user with delegation and session counts."""
    if lifecycle_state and lifecycle_state not in LIFECYCLE_STATES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid lifecycle_state. Must be one of: {', '.join(sorted(LIFECYCLE_STATES))}",
        )
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
            lifecycle_state=state,
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

    filtered = [
        e
        for e in entries
        if _matches_fleet_filters(e, lifecycle_state, user_id, service, q)
    ]
    summary = _compute_fleet_summary(filtered)
    page = filtered[offset : offset + limit]
    return AgentFleetResponse(agents=page, total=len(filtered), summary=summary)


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


class UserIdTokenStackItem(BaseModel):
    """IdP login context per delegator — ID tokens are not stored; groups come from claims/directory."""

    id: str
    user: str
    idp: Optional[str] = None
    groups: List[str] = Field(default_factory=list)


class UserSessionStackItem(IdentityStackItem):
    user: str
    session_id: str
    idp: Optional[str] = None


class DelegationStackItem(IdentityStackItem):
    delegator: str
    permissions_count: int
    permissions: List[str] = Field(default_factory=list)
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


def _groups_for_delegator(db: Session, user_email: str) -> List[str]:
    """Resolve IdP groups for a user from cached ID token claims or org directory."""
    groups: List[str] = []

    idp_sess = (
        db.query(IdPSession)
        .filter(IdPSession.user_id == user_email)
        .order_by(IdPSession.created_at.desc())
        .first()
    )
    if idp_sess and idp_sess.id_token_claims:
        claims = idp_sess.id_token_claims
        raw = claims.get("groups") or claims.get("group")
        if isinstance(raw, list):
            groups.extend(str(g) for g in raw)
        elif isinstance(raw, str) and raw:
            groups.append(raw)

    if not groups:
        for entry in db.query(OrgDirectory).filter(OrgDirectory.entity_type == "group").all():
            members = entry.members or []
            if user_email in members:
                groups.append(entry.display_name or entry.email)

    return sorted(set(groups))


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

    # Delegations for this agent (used by multiple layers below)
    delegations = (
        db.query(DelegationToken)
        .filter(
            DelegationToken.agent_id == agent_id,
            DelegationToken.revoked_at.is_(None),
        )
        .all()
    )
    delegator_emails = sorted({d.delegator for d in delegations if d.delegator})

    # Layer 1: User ID-Token — OIDC tokens not stored; show groups from login claims / directory
    id_token_items = []
    for email in delegator_emails:
        groups = _groups_for_delegator(db, email)
        latest_us = (
            db.query(UserSession)
            .filter(UserSession.user_id == email)
            .order_by(UserSession.created_at.desc())
            .first()
        )
        idp_label = None
        if latest_us and latest_us.idp_issuer:
            idp_label = (
                latest_us.idp_issuer.split("/")[-1]
                if "/" in latest_us.idp_issuer
                else latest_us.idp_issuer
            )
        id_token_items.append(
            UserIdTokenStackItem(
                id=email,
                user=email,
                idp=idp_label,
                groups=groups,
            ).model_dump()
        )

    layer_id_token = IdentityStackLayer(
        type="User ID-Token",
        description=(
            "OIDC ID tokens from the identity provider are consumed at login and not stored. "
            "Groups below are from cached login claims and organization directory membership."
        ),
        count=len(id_token_items),
        active=len(id_token_items),
        items=id_token_items,
    )

    # Layer 2: User Session — sessions for users who delegated to this agent

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
                session_id=us.session_id,
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
            permissions=perms,
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
            status=(
                "revoked"
                if d.revoked_at
                else ("expired" if d.is_expired else (d.status or "active"))
            ),
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


@router.patch(
    "/delegations/{delegation_id}",
    response_model=PatchDelegationResponse,
)
def patch_delegation_admin(
    delegation_id: str,
    body: PatchDelegationRequest,
    db: Session = Depends(get_db),
    admin_claims: dict = Depends(require_admin),
):
    """Admin narrow-in-place for any user's delegation."""
    actor = admin_claims.get("sub", "admin")
    service = DelegationService(db)
    try:
        result = service.patch_delegation_permissions(
            delegation_id,
            actor,
            is_admin=True,
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


# --- Delegation Template Endpoints (D3) ---

def _template_to_response(template: DelegationTemplate) -> TemplateResponse:
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
        working_hours_start=(
            str(template.working_hours_start) if template.working_hours_start else None
        ),
        working_hours_end=(
            str(template.working_hours_end) if template.working_hours_end else None
        ),
        auto_provision=bool(getattr(template, "auto_provision", False)),
        provision_mode=getattr(template, "provision_mode", None) or "off",
        created_by=template.created_by,
        created_at=template.created_at.isoformat() if template.created_at else None,
        updated_at=template.updated_at.isoformat() if template.updated_at else None,
    )


@router.get("/delegation-templates", response_model=TemplateListWrapper)
def list_templates(
    db: Session = Depends(get_db),
    _admin: dict = Depends(require_admin),
):
    templates = db.query(DelegationTemplate).all()
    items = [_template_to_response(t) for t in templates]
    return TemplateListWrapper(templates=items, total=len(items))


@router.post("/delegation-templates", response_model=TemplateResponse, status_code=201)
def create_template(
    body: TemplateCreateRequest,
    db: Session = Depends(get_db),
    admin_claims: dict = Depends(require_admin),
):
    if body.max_permissions:
        invalid = _validate_permission_strings(body.max_permissions, db)
        if invalid:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Unknown permission strings: {invalid}",
            )

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

    return _template_to_response(template)


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
    if "max_permissions" in updates and updates["max_permissions"]:
        invalid = _validate_permission_strings(updates["max_permissions"], db)
        if invalid:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Unknown permission strings: {invalid}",
            )
    if "provision_mode" in updates:
        mode = updates["provision_mode"]
        if mode not in ("off", "on_login", "on_invite"):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="provision_mode must be one of: off, on_login, on_invite",
            )
    for key, value in updates.items():
        if key == "working_hours_start" and value:
            setattr(template, key, time.fromisoformat(value))
        elif key == "working_hours_end" and value:
            setattr(template, key, time.fromisoformat(value))
        elif hasattr(template, key):
            setattr(template, key, value)

    if updates.get("provision_mode") == "on_login":
        template.auto_provision = True
    elif updates.get("provision_mode") == "off":
        template.auto_provision = False

    template.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(template)

    return _template_to_response(template)


@router.post(
    "/delegation-templates/{template_id}/invite",
    response_model=TemplateInviteResponse,
    status_code=201,
)
def invite_users_to_template(
    template_id: str,
    body: TemplateInviteRequest,
    db: Session = Depends(get_db),
    admin_claims: dict = Depends(require_admin),
):
    """Invite users to accept a pending delegation from a template."""
    template = (
        db.query(DelegationTemplate)
        .filter(DelegationTemplate.id == template_id)
        .first()
    )
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    actor = admin_claims.get("sub", "admin")
    service = DelegationService(db)
    try:
        result = service.invite_users_to_template(
            template_id,
            body.user_emails,
            actor,
        )
    except DelegationNotFoundError:
        raise HTTPException(status_code=404, detail="Template not found")

    return TemplateInviteResponse(
        invited=result.invited,
        delegation_ids=result.delegation_ids,
        skipped=result.skipped,
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


# --- Composite Provisioning Endpoint ---

@router.post("/agents/provision", status_code=201)
def provision_agent(
    body: ProvisionRequest,
    db: Session = Depends(get_db),
    admin_claims: dict = Depends(require_admin),
):
    """Atomic agent provisioning: register + config + delegation template in one call.

    Rolls back DB changes on failure. Scheduler resume is best-effort.
    """
    from app.services.provision_service import AgentProvisionService, ProvisionError

    admin_email = admin_claims.get("sub", "")
    service = AgentProvisionService(db)
    try:
        result = service.provision(
            agent_name=body.agent.name,
            agent_description=body.agent.description,
            platform=body.agent.platform,
            selector=body.agent.selector,
            config=body.config.model_dump() if hasattr(body.config, "model_dump") else body.config,
            template_max_permissions=body.delegation_template.max_permissions,
            template_default_ttl_days=body.delegation_template.default_ttl_days,
            template_available_to_roles=body.delegation_template.available_to_roles,
            admin_email=admin_email,
        )
    except ProvisionError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Agent with this selector already exists",
        )

    return result


# --- Agent Slots Endpoints ---


class AgentSlotEntry(BaseModel):
    name: str
    sa_email: str
    job_name: str
    scheduler_name: str
    schedule: str
    claimed_by: Optional[str] = None


class AgentSlotsResponse(BaseModel):
    slots: List[AgentSlotEntry]
    total: int
    available: int


def _get_agent_slots() -> list[dict]:
    """Parse AGENT_SLOTS_JSON from settings."""
    import json

    raw = settings.AGENT_SLOTS_JSON
    try:
        return json.loads(raw) if raw else []
    except (json.JSONDecodeError, TypeError):
        logger.warning("Invalid AGENT_SLOTS_JSON: %s", raw[:200] if raw else "empty")
        return []


@router.get("/agent-slots", response_model=AgentSlotsResponse)
def list_agent_slots(
    db: Session = Depends(get_db),
    _admin: dict = Depends(require_admin),
):
    """List pre-provisioned agent identity slots with claim status."""
    raw_slots = _get_agent_slots()

    claimed_selectors: dict[str, str] = {}
    if raw_slots:
        sa_emails = [s.get("sa_email") for s in raw_slots if s.get("sa_email")]
        if sa_emails:
            agents = db.query(Agent).filter(Agent.selector.in_(sa_emails)).all()
            for a in agents:
                claimed_selectors[a.selector] = a.agent_id

    slots = []
    for s in raw_slots:
        sa = s.get("sa_email", "")
        slots.append(AgentSlotEntry(
            name=s.get("name", ""),
            sa_email=sa,
            job_name=s.get("job_name", ""),
            scheduler_name=s.get("scheduler_name", ""),
            schedule=s.get("schedule", ""),
            claimed_by=claimed_selectors.get(sa),
        ))

    available = sum(1 for sl in slots if sl.claimed_by is None)
    return AgentSlotsResponse(slots=slots, total=len(slots), available=available)


# --- Scheduler Health Endpoint ---


class SchedulerHealthEntry(BaseModel):
    name: str
    status_code: Optional[int] = None
    status_message: Optional[str] = None
    last_attempt: Optional[str] = None


class SchedulerHealthResponse(BaseModel):
    healthy: List[str]
    unhealthy: List[SchedulerHealthEntry]
    total: int


@router.get("/health/agents", response_model=SchedulerHealthResponse)
async def get_agent_scheduler_health(
    _admin: dict = Depends(require_admin),
):
    """Check Cloud Scheduler status for all agent-related jobs.

    Queries the GCP Cloud Scheduler API for jobs containing
    'deepsecure-agent' in the name. Classifies each as healthy
    (status code 0 or no status) or unhealthy (non-zero status code).
    """
    try:
        from google.cloud import scheduler_v1
    except ImportError:
        return SchedulerHealthResponse(healthy=[], unhealthy=[], total=0)

    healthy: list[str] = []
    unhealthy: list[SchedulerHealthEntry] = []

    try:
        client = scheduler_v1.CloudSchedulerClient()
        parent = f"projects/{settings.GCP_PROJECT}/locations/{settings.GCP_REGION}"

        for job in client.list_jobs(parent=parent):
            if "deepsecure-agent" not in job.name:
                continue
            short_name = job.name.split("/")[-1]
            if job.status and job.status.code != 0:
                unhealthy.append(SchedulerHealthEntry(
                    name=short_name,
                    status_code=job.status.code,
                    status_message=job.status.message,
                    last_attempt=(
                        job.last_attempt_time.isoformat()
                        if job.last_attempt_time
                        else None
                    ),
                ))
            else:
                healthy.append(short_name)
    except Exception as exc:
        logger.warning("Failed to query Cloud Scheduler: %s", exc)

    return SchedulerHealthResponse(
        healthy=healthy,
        unhealthy=unhealthy,
        total=len(healthy) + len(unhealthy),
    )
