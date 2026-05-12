"""Service for computing agent lifecycle state.

The four-state lifecycle model tracks an agent's progression:
    registered → delegated → authenticated → active

State is computed from database state (delegations + sessions), not stored
as a column. This ensures the lifecycle always reflects current reality.

State priority (highest to lowest):
    active:        Has a session with last_activity_at within 24 hours
    authenticated: Has at least 1 AgentSession row (ever authenticated)
    delegated:     Has at least 1 active DelegationToken
    registered:    Agent exists but none of the above conditions are met
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.agent_session import AgentSession
from app.models.delegation import DelegationToken

logger = logging.getLogger(__name__)

REGISTERED = "registered"
DELEGATED = "delegated"
AUTHENTICATED = "authenticated"
ACTIVE = "active"


class LifecycleService:
    """Computes agent lifecycle state from delegations and sessions."""

    ACTIVE_WINDOW = timedelta(hours=24)

    def __init__(self, db_session: Session) -> None:
        self._db = db_session

    def compute_state(self, agent_id: str) -> str:
        """Compute the lifecycle state for a single agent.

        Checks conditions top-down (highest priority first):
        active → authenticated → delegated → registered.
        """
        now = datetime.now(timezone.utc)
        cutoff = now - self.ACTIVE_WINDOW

        has_active_session = (
            self._db.query(AgentSession.id)
            .filter(
                AgentSession.agent_id == agent_id,
                AgentSession.last_activity_at >= cutoff,
                AgentSession.is_active.is_(True),
            )
            .first()
            is not None
        )
        if has_active_session:
            return ACTIVE

        has_any_session = (
            self._db.query(AgentSession.id)
            .filter(AgentSession.agent_id == agent_id)
            .first()
            is not None
        )
        if has_any_session:
            return AUTHENTICATED

        has_active_delegation = (
            self._db.query(DelegationToken.id)
            .filter(
                DelegationToken.agent_id == agent_id,
                DelegationToken.revoked_at.is_(None),
                DelegationToken.expires_at > now,
            )
            .first()
            is not None
        )
        if has_active_delegation:
            return DELEGATED

        return REGISTERED

    def compute_state_bulk(self, agent_ids: List[str]) -> Dict[str, str]:
        """Compute lifecycle state for multiple agents using bulk queries.

        Uses at most 3 DB queries regardless of agent count.
        """
        if not agent_ids:
            return {}

        now = datetime.now(timezone.utc)
        cutoff = now - self.ACTIVE_WINDOW

        active_agents = set(
            row[0]
            for row in self._db.query(AgentSession.agent_id)
            .filter(
                AgentSession.agent_id.in_(agent_ids),
                AgentSession.last_activity_at >= cutoff,
                AgentSession.is_active.is_(True),
            )
            .distinct()
            .all()
        )

        authed_agents = set(
            row[0]
            for row in self._db.query(AgentSession.agent_id)
            .filter(AgentSession.agent_id.in_(agent_ids))
            .distinct()
            .all()
        )

        delegated_agents = set(
            row[0]
            for row in self._db.query(DelegationToken.agent_id)
            .filter(
                DelegationToken.agent_id.in_(agent_ids),
                DelegationToken.revoked_at.is_(None),
                DelegationToken.expires_at > now,
            )
            .distinct()
            .all()
        )

        result: Dict[str, str] = {}
        for agent_id in agent_ids:
            if agent_id in active_agents:
                result[agent_id] = ACTIVE
            elif agent_id in authed_agents:
                result[agent_id] = AUTHENTICATED
            elif agent_id in delegated_agents:
                result[agent_id] = DELEGATED
            else:
                result[agent_id] = REGISTERED
        return result

    def get_last_authenticated_at(self, agent_id: str) -> Optional[datetime]:
        """Return the created_at of the most recent AgentSession, or None."""
        row = (
            self._db.query(AgentSession.created_at)
            .filter(AgentSession.agent_id == agent_id)
            .order_by(AgentSession.created_at.desc())
            .first()
        )
        return row[0] if row else None

    def get_last_active_at(self, agent_id: str) -> Optional[datetime]:
        """Return the last_activity_at of the most recent active session, or None."""
        row = (
            self._db.query(AgentSession.last_activity_at)
            .filter(
                AgentSession.agent_id == agent_id,
                AgentSession.is_active.is_(True),
            )
            .order_by(AgentSession.last_activity_at.desc())
            .first()
        )
        return row[0] if row else None

    def get_session_count(self, agent_id: str) -> int:
        """Return total count of AgentSession rows for this agent."""
        return (
            self._db.query(func.count(AgentSession.id))
            .filter(AgentSession.agent_id == agent_id)
            .scalar()
        ) or 0

    def get_delegation_count(self, agent_id: str) -> int:
        """Return count of active (non-revoked, non-expired) delegations."""
        now = datetime.now(timezone.utc)
        return (
            self._db.query(func.count(DelegationToken.id))
            .filter(
                DelegationToken.agent_id == agent_id,
                DelegationToken.revoked_at.is_(None),
                DelegationToken.expires_at > now,
            )
            .scalar()
        ) or 0
