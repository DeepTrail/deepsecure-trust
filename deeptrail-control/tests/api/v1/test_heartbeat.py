"""Unit tests for the internal heartbeat endpoint."""
import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.agent_session import AgentSession


HEARTBEAT_URL = "/api/v1/agents/internal/sessions/{agent_id}/heartbeat"
VALID_HEADERS = {"X-Internal-API-Token": settings.GATEWAY_INTERNAL_API_TOKEN}


def _create_agent_session(db: Session, agent_id: str, is_active: bool = True) -> AgentSession:
    """Create a minimal AgentSession for testing."""
    session = AgentSession(
        agent_id=agent_id,
        delegation_id="test-delegation-001",
        owner_email="test@example.com",
        scoped_permissions=["notion:pages:search"],
        is_active=is_active,
        last_activity_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def test_heartbeat_updates_last_activity(client: TestClient, db: Session):
    """Heartbeat with valid token updates last_activity_at for active session."""
    agent_id = "heartbeat-test-agent-1"
    session = _create_agent_session(db, agent_id)
    old_activity = session.last_activity_at

    response = client.post(
        HEARTBEAT_URL.format(agent_id=agent_id),
        headers=VALID_HEADERS,
    )

    assert response.status_code == 204

    db.refresh(session)
    assert session.last_activity_at > old_activity


def test_heartbeat_no_session_returns_204(client: TestClient, db: Session):
    """Heartbeat for agent with no active session still returns 204 (best-effort)."""
    response = client.post(
        HEARTBEAT_URL.format(agent_id="nonexistent-agent"),
        headers=VALID_HEADERS,
    )
    assert response.status_code == 204


def test_heartbeat_inactive_session_not_updated(client: TestClient, db: Session):
    """Heartbeat does not update inactive sessions."""
    agent_id = "heartbeat-test-agent-inactive"
    session = _create_agent_session(db, agent_id, is_active=False)
    old_activity = session.last_activity_at

    response = client.post(
        HEARTBEAT_URL.format(agent_id=agent_id),
        headers=VALID_HEADERS,
    )

    assert response.status_code == 204
    db.refresh(session)
    assert session.last_activity_at == old_activity


def test_heartbeat_no_token_returns_403(client: TestClient):
    """Missing X-Internal-API-Token header returns 403."""
    response = client.post(
        HEARTBEAT_URL.format(agent_id="some-agent"),
    )
    assert response.status_code == 401


def test_heartbeat_wrong_token_returns_401(client: TestClient):
    """Invalid X-Internal-API-Token returns 401."""
    response = client.post(
        HEARTBEAT_URL.format(agent_id="some-agent"),
        headers={"X-Internal-API-Token": "wrong-token-value"},
    )
    assert response.status_code == 401
