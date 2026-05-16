"""Tests for GET /api/v1/agents/{id}/tools endpoint."""

import base64
import uuid
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.connected_service import ConnectedService
from app.models.delegation import DelegationToken

VALID_PUB_KEY_B64 = "CgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgo="


def _create_agent(client: TestClient, agent_id: str, public_key: str = VALID_PUB_KEY_B64):
    """Helper to create an agent."""
    data = {"agent_id": agent_id, "public_key": public_key}
    response = client.post(f"{settings.API_V1_STR}/agents/", json=data)
    return response


def _create_delegation(db: Session, agent_id: str, delegator: str, permissions: list):
    """Helper to create a delegation in the DB."""
    delegation = DelegationToken(
        agent_id=agent_id,
        delegator=delegator,
        delegated_permissions=permissions,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    db.add(delegation)
    db.commit()
    db.refresh(delegation)
    return delegation


def _create_connected_service(db: Session, user_id: str, service_id: str):
    """Helper to create a connected service record for a delegator."""
    svc = ConnectedService(
        id=f"conn-{uuid.uuid4().hex[:12]}",
        user_id=user_id,
        service_id=service_id,
        service_name=service_id.capitalize(),
        scopes_granted=[],
        oauth_token_ref=f"vault://{user_id}-{service_id}-token",
        connected_at=datetime.now(timezone.utc),
    )
    db.add(svc)
    db.commit()
    return svc


def test_get_agent_tools_not_found(client: TestClient, db: Session):
    """Test tools endpoint with non-existent agent returns 404."""
    response = client.get(f"{settings.API_V1_STR}/agents/nonexistent-agent/tools")
    assert response.status_code == 404
    assert response.json()["detail"] == "Agent not found"


def test_get_agent_tools_no_delegation(client: TestClient, db: Session):
    """Test tools endpoint for agent with no delegation returns empty tools list."""
    agent_id = "tools-test-no-del"
    pub_key = "CwsLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCwsLCws="
    _create_agent(client, agent_id, pub_key)

    response = client.get(f"{settings.API_V1_STR}/agents/{agent_id}/tools")
    assert response.status_code == 200
    data = response.json()
    assert data["agent_id"] == agent_id
    assert len(data["tools"]) == 0


def test_get_agent_tools_with_delegation(client: TestClient, db: Session):
    """Test tools endpoint for agent with active delegation shows correct availability."""
    agent_id = "tools-test-with-del"
    pub_key = "DAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAw="
    _create_agent(client, agent_id, pub_key)

    delegator = "sarah@acme.com"

    _create_connected_service(db, delegator, "notion")
    _create_connected_service(db, delegator, "slack")

    _create_delegation(
        db,
        agent_id=agent_id,
        delegator=delegator,
        permissions=["notion:pages:search", "notion:pages:read", "slack:messages:send"],
    )

    response = client.get(f"{settings.API_V1_STR}/agents/{agent_id}/tools")
    assert response.status_code == 200
    data = response.json()
    assert data["agent_id"] == agent_id

    tools_by_name = {t["name"]: t for t in data["tools"]}

    assert tools_by_name["notion.search_pages"]["available"] is True
    assert tools_by_name["notion.search_pages"]["reason"] is None
    assert tools_by_name["notion.get_page"]["available"] is True
    assert tools_by_name["slack.send_message"]["available"] is True

    assert tools_by_name["notion.create_page"]["available"] is False
    assert tools_by_name["notion.create_page"]["reason"] == "Not in delegation"


def test_get_agent_tools_expired_delegation_excluded(client: TestClient, db: Session):
    """Test that expired delegations are not considered for tool availability."""
    agent_id = "tools-test-expired"
    pub_key = "DQ0NDQ0NDQ0NDQ0NDQ0NDQ0NDQ0NDQ0NDQ0NDQ0NDQ0="
    _create_agent(client, agent_id, pub_key)

    # Create an expired delegation
    delegation = DelegationToken(
        agent_id=agent_id,
        delegator="sarah@acme.com",
        delegated_permissions=["notion:pages:search"],
        expires_at=datetime.now(timezone.utc) - timedelta(days=1),
    )
    db.add(delegation)
    db.commit()

    response = client.get(f"{settings.API_V1_STR}/agents/{agent_id}/tools")
    assert response.status_code == 200
    data = response.json()

    # All tools should be unavailable since delegation is expired
    for tool in data["tools"]:
        assert tool["available"] is False
