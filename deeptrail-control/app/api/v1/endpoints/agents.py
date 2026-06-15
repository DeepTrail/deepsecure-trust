import base64

from fastapi import APIRouter, HTTPException, status, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
import logging
from typing import List, Any

from app import schemas, crud
from app.api import deps
from app.api.v1.endpoints.internal import verify_internal_api_key
from app.models.attestation_policy import PlatformType
from app.models.agent_session import AgentSession
from app.schemas.attestation_policy import AttestationPolicyCreate
from app.models.delegation import DelegationToken
from app.models.credential import Credential
from app.models.policy import Policy
from app.models.connected_service import ConnectedService
from app.models.service_registry import ServiceRegistry
from app.services.lifecycle_service import LifecycleService
from app.services.scope_mapper import ScopeMapper

logger = logging.getLogger(__name__)
router = APIRouter()


# Default permission-to-tool mapping for REST backends that don't store
# their tool schemas in service_registry.  Kept as a fallback — the
# primary source of truth is `service_registry.permission_map` (populated
# for MCP services and optionally for REST services via admin API).
_DEFAULT_PERMISSION_TOOL_MAP: dict[str, dict[str, str]] = {
    # Notion
    "notion:pages:search": {"name": "notion.search_pages", "backend": "notion"},
    "notion:pages:read": {"name": "notion.get_page", "backend": "notion"},
    "notion:pages:create": {"name": "notion.create_page", "backend": "notion"},
    "notion:pages:update": {"name": "notion.update_page", "backend": "notion"},
    "notion:pages:delete": {"name": "notion.delete_page", "backend": "notion"},
    "notion:blocks:read": {"name": "notion.get_block", "backend": "notion"},
    "notion:databases:list": {"name": "notion.list_databases", "backend": "notion"},
    "notion:databases:query": {"name": "notion.query_database", "backend": "notion"},
    # Slack
    "slack:messages:search": {"name": "slack.search_messages", "backend": "slack"},
    "slack:messages:send": {"name": "slack.send_message", "backend": "slack"},
    "slack:channels:list": {"name": "slack.list_channels", "backend": "slack"},
    "slack:channels:history": {"name": "slack.channel_history", "backend": "slack"},
    "slack:channels:join": {"name": "slack.join_channel", "backend": "slack"},
    "slack:users:list": {"name": "slack.list_users", "backend": "slack"},
    "slack:users:search": {"name": "slack.search_users", "backend": "slack"},
    "slack:reactions:write": {"name": "slack.add_reaction", "backend": "slack"},
    # Google Drive
    "gdrive:files:search": {"name": "gdrive.search_files", "backend": "gdrive"},
    "gdrive:files:read": {"name": "gdrive.get_file", "backend": "gdrive"},
    "gdrive:files:list": {"name": "gdrive.list_files", "backend": "gdrive"},
    "gdrive:files:metadata": {"name": "gdrive.get_metadata", "backend": "gdrive"},
    # Google Calendar
    "gcalendar:calendars:list": {"name": "gcalendar.list_calendars", "backend": "gcalendar"},
    "gcalendar:events:list": {"name": "gcalendar.list_events", "backend": "gcalendar"},
    "gcalendar:events:read": {"name": "gcalendar.get_event", "backend": "gcalendar"},
    "gcalendar:events:search": {"name": "gcalendar.search_events", "backend": "gcalendar"},
    # Gmail
    "gmail:messages:list": {"name": "gmail.list_messages", "backend": "gmail"},
    "gmail:messages:read": {"name": "gmail.get_message", "backend": "gmail"},
    "gmail:messages:search": {"name": "gmail.search_messages", "backend": "gmail"},
    "gmail:labels:list": {"name": "gmail.list_labels", "backend": "gmail"},
    # GitHub
    "github:repos:list": {"name": "github.list_repos", "backend": "github"},
    "github:repos:read": {"name": "github.read_repo", "backend": "github"},
    "github:issues:read": {"name": "github.list_issues", "backend": "github"},
    "github:issues:create": {"name": "github.create_issue", "backend": "github"},
    "github:pulls:read": {"name": "github.list_pulls", "backend": "github"},
    "github:pulls:create": {"name": "github.create_pull", "backend": "github"},
    "github:commits:read": {"name": "github.list_commits", "backend": "github"},
    "github:orgs:read": {"name": "github.read_org", "backend": "github"},
    "github:teams:list": {"name": "github.list_teams", "backend": "github"},
    "github:users:read": {"name": "github.read_user", "backend": "github"},
}


def _build_permission_tool_map(db: Session) -> dict[str, dict[str, str]]:
    """Build a merged permission→tool map from the default fallback and service_registry.

    For services with a non-null ``permission_map`` in the DB (e.g. MCP services
    configured via the admin UI), those DB entries take precedence.  For services
    without one (most REST services), the hardcoded default is used.
    """
    merged = dict(_DEFAULT_PERMISSION_TOOL_MAP)

    services = (
        db.query(ServiceRegistry)
        .filter(
            ServiceRegistry.status == "active",
            ServiceRegistry.permission_map.isnot(None),
        )
        .all()
    )
    for svc in services:
        perm_map: dict[str, str] = svc.permission_map or {}
        for tool_name, perm_string in perm_map.items():
            namespaced = f"{svc.service_id}.{tool_name}" if "." not in tool_name else tool_name
            merged[perm_string] = {"name": namespaced, "backend": svc.service_id}

    return merged


def _generate_ed25519_keypair() -> tuple:
    """Generate an Ed25519 keypair and return (public_key_bytes, private_key_b64, public_key_b64)."""
    from nacl.signing import SigningKey

    signing_key = SigningKey.generate()
    verify_key = signing_key.verify_key
    private_key_b64 = base64.b64encode(signing_key.encode()).decode()
    public_key_b64 = base64.b64encode(verify_key.encode()).decode()
    public_key_bytes = verify_key.encode()
    return public_key_bytes, private_key_b64, public_key_b64


PLATFORM_TYPE_MAP = {
    "gcp_workload_identity": PlatformType.GCP_WORKLOAD_IDENTITY,
    "aws_iam": PlatformType.AWS_IAM,
    "kubernetes": PlatformType.KUBERNETES,
}


@router.post("", response_model=schemas.AgentCreateResponse, status_code=status.HTTP_201_CREATED)
def register_agent(agent_in: schemas.AgentCreate, db: Session = Depends(deps.get_db)):
    """Register a new agent in the system.

    Supports two registration flows:
    - **Key-based**: Ed25519 keypair (provided or backend-generated).
    - **Platform-based**: Platform identity (GCP, AWS, K8s) with auto-created
      attestation policy. No cryptographic key is involved.
    """
    is_platform_agent = agent_in.platform is not None

    backend_generated_key = False
    private_key_b64 = None
    public_key_b64 = None

    if not is_platform_agent and agent_in.public_key is None:
        public_key_bytes, private_key_b64, public_key_b64 = _generate_ed25519_keypair()
        agent_in.public_key = public_key_bytes
        backend_generated_key = True

    try:
        agent = crud.agent.create(db=db, obj_in=agent_in)
    except IntegrityError as e:
        db.rollback()
        error_str = str(e).lower()
        if "selector" in error_str or (is_platform_agent and "unique" in error_str):
            logger.warning(f"Duplicate selector during platform agent registration: {e}")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An agent is already registered with this platform identity.",
            )
        logger.warning(f"Integrity error during agent registration: {e}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Agent already exists (duplicate agent_id or public key).",
        )
    except ValueError as e:
        db.rollback()
        logger.error(f"Value error during agent creation: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected error creating agent: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not create agent due to an internal error."
        )

    if is_platform_agent:
        try:
            policy_in = AttestationPolicyCreate(
                agent_name_to_bootstrap=agent.agent_id,
                platform=PLATFORM_TYPE_MAP[agent_in.platform],
                selector=agent_in.selector,
            )
            crud.attestation_policy.create(db=db, obj_in=policy_in)
        except IntegrityError:
            db.rollback()
            logger.warning(
                f"Duplicate attestation policy selector '{agent_in.selector}' "
                f"for agent {agent.agent_id}"
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An agent is already registered with this platform identity.",
            )
        except Exception as e:
            db.rollback()
            logger.error(
                f"Failed to create attestation policy for agent {agent.agent_id}: {e}",
                exc_info=True,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Agent created but attestation policy creation failed.",
            )

    if is_platform_agent:
        return schemas.AgentCreateResponse(
            agent_id=agent.agent_id,
            name=agent.name,
            description=agent.description,
            public_key=None,
            private_key=None,
            private_key_warning=None,
            platform=agent.platform,
            selector=agent.selector,
            created_at=agent.created_at,
            updated_at=agent.updated_at,
        )

    response_public_key = (
        public_key_b64
        if backend_generated_key
        else base64.b64encode(agent.public_key).decode()
    )

    response = schemas.AgentCreateResponse(
        agent_id=agent.agent_id,
        name=agent.name,
        description=agent.description,
        public_key=response_public_key,
        platform=None,
        selector=None,
        created_at=agent.created_at,
        updated_at=agent.updated_at,
    )

    if backend_generated_key:
        response.private_key = private_key_b64
        response.private_key_warning = "This private key will not be shown again. Store it securely."

    return response

@router.get("/{agent_id}", response_model=schemas.Agent)
def read_agent(agent_id: str, db: Session = Depends(deps.get_db)):
    """Get agent details by agent_id, enriched with lifecycle state."""
    db_agent = crud.agent.get_by_agent_id(db=db, agent_id=agent_id)
    if db_agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    lifecycle = LifecycleService(db)
    agent_data = schemas.Agent.model_validate(db_agent)
    agent_data.lifecycle_state = lifecycle.compute_state(agent_id)
    agent_data.last_authenticated_at = lifecycle.get_last_authenticated_at(agent_id)
    agent_data.last_active_at = lifecycle.get_last_active_at(agent_id)
    agent_data.session_count = lifecycle.get_session_count(agent_id)
    agent_data.delegation_count = lifecycle.get_delegation_count(agent_id)
    return agent_data

@router.get("", response_model=schemas.AgentList)
def list_agents(
    db: Session = Depends(deps.get_db),
    skip: int = Query(0, ge=0, description="Number of records to skip for pagination"),
    limit: int = Query(100, ge=1, le=500, description="Maximum number of records to return")
):
    """Retrieve a list of agents with pagination, enriched with lifecycle states."""
    try:
        agents = crud.agent.get_multi(db, skip=skip, limit=limit)
        lifecycle = LifecycleService(db)
        agent_ids = [a.agent_id for a in agents]
        states = lifecycle.compute_state_bulk(agent_ids) if agent_ids else {}

        enriched = []
        for a in agents:
            agent_data = schemas.Agent.model_validate(a)
            agent_data.lifecycle_state = states.get(a.agent_id, "registered")
            enriched.append(agent_data)

        return schemas.AgentList(agents=enriched, total=len(enriched))
    except Exception as e:
        logger.error(f"Error listing agents in endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve agent list.")

@router.patch("/{agent_id}", response_model=schemas.Agent)
def update_agent(
    agent_id: str,
    agent_in: schemas.AgentUpdate,
    db: Session = Depends(deps.get_db)
):
    """Update an agent's details (name, description, status)."""
    db_agent = crud.agent.get_by_agent_id(db=db, agent_id=agent_id)
    if not db_agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    try:
        updated_agent = crud.agent.update(db=db, db_obj=db_agent, obj_in=agent_in)
    except Exception as e: # Catch potential errors from CRUDBase update
        logger.error(f"Error updating agent {agent_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not update agent.")
    return updated_agent

@router.delete("/{agent_id}", status_code=status.HTTP_200_OK)
def delete_agent(agent_id: str, db: Session = Depends(deps.get_db)):
    """Hard delete an agent and all related records (delegations, sessions, credentials, policies)."""
    db_agent = crud.agent.get_by_agent_id(db=db, agent_id=agent_id)
    if db_agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    try:
        del_count = db.query(DelegationToken).filter(DelegationToken.agent_id == agent_id).delete()
        cred_count = db.query(Credential).filter(Credential.agent_id == agent_id).delete()
        pol_count = db.query(Policy).filter(Policy.agent_id == agent_id).delete()
        db.delete(db_agent)
        db.commit()
        logger.info(
            f"Agent {agent_id} hard-deleted. "
            f"Cleaned up: {del_count} delegations, {cred_count} credentials, {pol_count} policies"
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting agent {agent_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete agent",
        )

    return {"detail": f"Agent {agent_id} deleted", "agent_id": agent_id}


@router.get("/{agent_id}/sessions", response_model=schemas.AgentSessionList)
def list_agent_sessions(
    agent_id: str,
    db: Session = Depends(deps.get_db),
    active_only: bool = Query(False, description="If true, return only active sessions"),
):
    """List sessions for an agent, ordered by most recent first."""
    db_agent = crud.agent.get_by_agent_id(db=db, agent_id=agent_id)
    if db_agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    query = db.query(AgentSession).filter(AgentSession.agent_id == agent_id)
    if active_only:
        query = query.filter(AgentSession.is_active.is_(True))
    sessions = query.order_by(AgentSession.created_at.desc()).all()

    items = []
    for s in sessions:
        items.append(schemas.AgentSessionSummary(
            session_id=s.id,
            agent_id=s.agent_id,
            delegation_id=s.delegation_id or "",
            is_active=s.is_active,
            source_ip=s.source_ip,
            created_at=s.created_at,
            expires_at=s.expires_at,
            last_activity_at=getattr(s, "last_activity_at", None),
        ))

    return schemas.AgentSessionList(sessions=items, total=len(items))


@router.get("/{agent_id}/tools", response_model=schemas.AgentToolsResponse)
def get_agent_tools(
    agent_id: str,
    db: Session = Depends(deps.get_db),
):
    """Get tools available to an agent based on delegated permissions and connected services.

    REST backends require the delegator to have an active OAuth connection.
    MCP backends (API-key auth managed by admin) are always available when
    delegated — no per-user OAuth connection is needed.
    """
    db_agent = crud.agent.get_by_agent_id(db=db, agent_id=agent_id)
    if db_agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    # Collect all delegated permissions and identify the delegator(s)
    delegated_permissions: set = set()
    delegators: set = set()
    active_delegations = (
        db.query(DelegationToken)
        .filter(
            DelegationToken.agent_id == agent_id,
            DelegationToken.revoked_at.is_(None),
        )
        .all()
    )
    for delegation in active_delegations:
        if delegation.is_valid:
            perms = delegation.delegated_permissions or []
            delegated_permissions.update(perms)
            if delegation.delegator:
                delegators.add(delegation.delegator)

    # Find which REST backends the delegator(s) have OAuth-connected
    connected_backends: set = set()
    if delegators:
        connected_services = (
            db.query(ConnectedService.service_id)
            .filter(
                ConnectedService.user_id.in_(delegators),
                ConnectedService.disconnected_at.is_(None),
            )
            .distinct()
            .all()
        )
        connected_backends = {row[0] for row in connected_services}

    # Identify MCP backends — these don't require per-user OAuth
    mcp_backends: set = set()
    mcp_services = (
        db.query(ServiceRegistry.service_id)
        .filter(
            ServiceRegistry.status == "active",
            ServiceRegistry.backend_type == "mcp",
        )
        .all()
    )
    mcp_backends = {row[0] for row in mcp_services}

    # Build the full permission→tool map (defaults + DB-stored MCP maps)
    permission_tool_map = _build_permission_tool_map(db)

    # Build tools list: REST requires OAuth connection, MCP always available
    tools = []
    for permission, tool_info in permission_tool_map.items():
        backend = tool_info["backend"]
        is_mcp = backend in mcp_backends
        has_connection = backend in connected_backends

        if not is_mcp and not has_connection:
            continue

        available = permission in delegated_permissions
        tool = schemas.AgentToolInfo(
            name=tool_info["name"],
            backend=backend,
            permission=permission,
            available=available,
            reason=None if available else "Not in delegation",
        )
        tools.append(tool)

    return schemas.AgentToolsResponse(agent_id=agent_id, tools=tools)


@router.get("/{agent_id}/config", response_model=schemas.AgentConfig)
def get_agent_config(
    agent_id: str,
    db: Session = Depends(deps.get_db),
):
    """Return the agent's runtime configuration.

    Merges stored JSONB with schema defaults so callers always get a
    complete config object even if the DB column is empty or sparse.
    Auth: User token or Agent JWT (agents can read their own config).
    """
    db_agent = crud.agent.get_by_agent_id(db=db, agent_id=agent_id)
    if db_agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    stored = db_agent.config or {}
    return schemas.AgentConfig(**stored)


@router.put("/{agent_id}/config", response_model=schemas.AgentConfig)
def update_agent_config(
    agent_id: str,
    payload: schemas.AgentConfigUpdate,
    db: Session = Depends(deps.get_db),
):
    """Update the agent's runtime configuration.

    Only fields present in the request body are changed; omitted fields
    keep their current values.  Returns the full merged config.
    Auth: User token (admin operation).
    """
    db_agent = crud.agent.get_by_agent_id(db=db, agent_id=agent_id)
    if db_agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    current = dict(db_agent.config or {})
    update_data = payload.model_dump(exclude_none=True)

    if "tagged_prompts" in update_data:
        update_data["tagged_prompts"] = [
            tp.model_dump() if hasattr(tp, "model_dump") else tp
            for tp in update_data["tagged_prompts"]
        ]

    current.update(update_data)
    db_agent.config = current
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(db_agent, "config")
    db.commit()
    db.refresh(db_agent)

    return schemas.AgentConfig(**(db_agent.config or {}))


@router.post(
    "/internal/sessions/{agent_id}/heartbeat",
    status_code=204,
    include_in_schema=False,
    dependencies=[Depends(verify_internal_api_key)],
)
async def session_heartbeat(
    agent_id: str,
    db: Session = Depends(deps.get_db),
):
    """Update last_activity_at for the agent's most recent active session.

    Called by the gateway after each successful tools/call.
    Best-effort: returns 204 even if no session found (avoids gateway retries).
    """
    session = (
        db.query(AgentSession)
        .filter(
            AgentSession.agent_id == agent_id,
            AgentSession.is_active.is_(True),
        )
        .order_by(AgentSession.created_at.desc())
        .first()
    )
    if session:
        session.touch()
        db.commit()
    else:
        logger.info("Heartbeat: no active session for agent %s", agent_id)
    return Response(status_code=204)