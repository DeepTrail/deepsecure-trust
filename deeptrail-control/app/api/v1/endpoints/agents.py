import base64

from fastapi import APIRouter, HTTPException, status, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
import logging
from typing import List, Any

from app import schemas, crud
from app.api import deps
from app.models.agent_session import AgentSession
from app.models.delegation import DelegationToken
from app.services.lifecycle_service import LifecycleService
from app.services.scope_mapper import ScopeMapper

logger = logging.getLogger(__name__)
router = APIRouter()


# Permission-to-tool mapping for known backends
PERMISSION_TOOL_MAP = {
    "notion:pages:search": {"name": "notion.search_pages", "backend": "notion"},
    "notion:pages:read": {"name": "notion.get_page", "backend": "notion"},
    "notion:pages:create": {"name": "notion.create_page", "backend": "notion"},
    "notion:pages:update": {"name": "notion.update_page", "backend": "notion"},
    "notion:pages:delete": {"name": "notion.delete_page", "backend": "notion"},
    "notion:blocks:read": {"name": "notion.get_block", "backend": "notion"},
    "notion:databases:list": {"name": "notion.list_databases", "backend": "notion"},
    "notion:databases:query": {"name": "notion.query_database", "backend": "notion"},
    "slack:messages:search": {"name": "slack.search_messages", "backend": "slack"},
    "slack:messages:send": {"name": "slack.send_message", "backend": "slack"},
    "slack:channels:list": {"name": "slack.list_channels", "backend": "slack"},
    "slack:channels:history": {"name": "slack.channel_history", "backend": "slack"},
    "slack:users:list": {"name": "slack.list_users", "backend": "slack"},
    "hubspot:contacts:read": {"name": "hubspot.get_contact", "backend": "hubspot"},
    "hubspot:contacts:list": {"name": "hubspot.list_contacts", "backend": "hubspot"},
    "hubspot:contacts:create": {"name": "hubspot.create_contact", "backend": "hubspot"},
    "hubspot:deals:list": {"name": "hubspot.list_deals", "backend": "hubspot"},
}


def _generate_ed25519_keypair() -> tuple:
    """Generate an Ed25519 keypair and return (public_key_bytes, private_key_b64, public_key_b64)."""
    from nacl.signing import SigningKey

    signing_key = SigningKey.generate()
    verify_key = signing_key.verify_key
    private_key_b64 = base64.b64encode(signing_key.encode()).decode()
    public_key_b64 = base64.b64encode(verify_key.encode()).decode()
    public_key_bytes = verify_key.encode()
    return public_key_bytes, private_key_b64, public_key_b64


@router.post("/", response_model=schemas.AgentCreateResponse, status_code=status.HTTP_201_CREATED)
def register_agent(agent_in: schemas.AgentCreate, db: Session = Depends(deps.get_db)):
    """Register a new agent in the system.

    When public_key is provided, the agent is registered with the given key.
    When public_key is omitted, the backend generates an Ed25519 keypair and
    returns the private key in the response (never stored server-side).
    """
    backend_generated_key = False
    private_key_b64 = None
    public_key_b64 = None

    if agent_in.public_key is None:
        public_key_bytes, private_key_b64, public_key_b64 = _generate_ed25519_keypair()
        agent_in.public_key = public_key_bytes
        backend_generated_key = True

    try:
        agent = crud.agent.create(db=db, obj_in=agent_in)
    except IntegrityError as e:
        db.rollback()
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

    response_public_key = public_key_b64 if backend_generated_key else base64.b64encode(agent.public_key).decode()

    response = schemas.AgentCreateResponse(
        agent_id=agent.agent_id,
        name=agent.name,
        description=agent.description,
        public_key=response_public_key,
        status=agent.status,
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

@router.get("/", response_model=schemas.AgentList)
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

@router.delete("/{agent_id}", response_model=schemas.Agent)
def delete_agent(agent_id: str, db: Session = Depends(deps.get_db)):
    """Deactivate an agent by setting its status to 'inactive' (soft delete)."""
    
    # The crud.agent.remove() method now performs a deactivation (soft delete)
    # and returns the updated agent object or None if not found.
    deactivated_agent = crud.agent.remove(db=db, id=agent_id) 
    
    if not deactivated_agent:
        logger.warning(f"Attempt to delete/deactivate non-existent agent: {agent_id}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    
    logger.info(f"Agent {agent_id} successfully deactivated (soft deleted). Status: {deactivated_agent.status}")
    return deactivated_agent


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
    """Get tools available to an agent based on its delegated permissions.

    Returns all known tools with availability status based on what
    permissions have been delegated to this agent.
    """
    db_agent = crud.agent.get_by_agent_id(db=db, agent_id=agent_id)
    if db_agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    # Collect all delegated permissions across active delegations
    delegated_permissions: set = set()
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

    # Build tools list from the permission-to-tool map
    tools = []
    for permission, tool_info in PERMISSION_TOOL_MAP.items():
        available = permission in delegated_permissions
        tool = schemas.AgentToolInfo(
            name=tool_info["name"],
            backend=tool_info["backend"],
            permission=permission,
            available=available,
            reason=None if available else "Not in delegation",
        )
        tools.append(tool)

    return schemas.AgentToolsResponse(agent_id=agent_id, tools=tools)